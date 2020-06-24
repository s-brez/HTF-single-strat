from botocore.vendored import requests
from datetime import datetime
import json
import os


def lambda_handler(event, context):
    """
    Setup:
    Copy run() function body into AWS lambda and set required enviroment vars.
    Ensure the incoming signal parameter is JSON format or otherwise parsable.

    Event flow:
    1. Signal received from TradingView alert webhook.
    2. Check signal token is valid, otherwise do nothing further.
    3. Load relevant auth tokens from environment variables.
    4. Parse incoming signal and calculate entry/stop/TP order size.
    5. Raise orders with venue.

    """

    # Set True for live trading, false for demo acount.
    LIVE = False

    # % value as integer. Value of 1 will place orders 1% away from entry.
    STOP_DISTANCE = 1
    TP_DISTANCE = 1

    # Position size multiplier. Value of 1 will place smallest allowable order size.
    SIZE_MULTI = 1

    # ticker_code: (instrument name, search term, instrument class)
    TICKER_MAP = {
        "UKOIL": ("Oil - Brent Crude", "brent", "COMMODITIES"),
        "CFDs on Brent Crude Oil": ("Oil - Brent Crude", "brent", "COMMODITIES"),
        "DE30EUR": ("Germany 30 Cash", "dax", "INDICES"),
        "DAX": ("Germany 30 Cash", "dax", "INDICES"),
        "WHTUSD": ("Chicago Wheat", "chicago%20wheat", "COMMODITIES"),
        "WHEATUSD": ("Chicago Wheat", "chicago%20wheat", "COMMODITIES")}

    # Load webhook token. Incoming signals must match token to be actioned.
    if os.environ['WEBHOOK_TOKEN']:
        WEBHOOK_TOKEN = os.environ['WEBHOOK_TOKEN']
    else:
        print("Error: Tradingview webhook token missing")
        return {
            'statusCode': 400,
            'body': json.dumps("Tradingview webhook token missing")}

    # Parse incoming webhook signal.
    webhook_signal = json.loads(event['body'])

    # Action the signal if webhook token matches stored token.
    if webhook_signal['token'] == WEBHOOK_TOKEN:

        # Load IG auth tokens from environment variables.
        if LIVE:
            if(  # Live.
                os.environ['IG_API_KEY_LIVE'] and os.environ['IG_USERNAME_LIVE'] and
                    os.environ['IG_PASSWORD_LIVE']):
                IG_API_KEY = os.environ['IG_API_KEY_LIVE']
                IG_USERNAME = os.environ['IG_USERNAME_LIVE']
                IG_PASSWORD = os.environ['IG_PASSWORD_LIVE']
                IG_URL = "https://api.ig.com/gateway/deal"
            else:
                print("Error: IG Markets live authentication tokens missing")
                return {
                    'statusCode': 400,
                    'body': json.dumps(
                        "IG Markets live authentication tokens missing")}
        else:
            if(  # Demo.
                os.environ['IG_API_KEY_DEMO'] and os.environ['IG_USERNAME_DEMO'] and
                    os.environ['IG_PASSWORD_DEMO']):
                IG_API_KEY = os.environ['IG_API_KEY_DEMO']
                IG_USERNAME = os.environ['IG_USERNAME_DEMO']
                IG_PASSWORD = os.environ['IG_PASSWORD_DEMO']
                IG_URL = "https://demo-api.ig.com/gateway/deal"
            else:
                print("Error: IG Markets demo authentication tokens missing")
                return {
                    'statusCode': 400,
                    'body': json.dumps(
                        "IG Markets demo authentication tokens missing")}

        # Create a session with IG.
        s = requests.Session()

        headers = {
            'X-IG-API-KEY': IG_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8'}

        body = {
            "identifier": IG_USERNAME,
            "password": IG_PASSWORD}

        response = s.send(
            requests.Request('POST', IG_URL + "/session", json=body, headers=headers,
                    params='').prepare())

        # CST and X-SECURITY-TOKEN must be included in subsequent requests.Requests.
        CST, XST = response.headers['CST'], response.headers['X-SECURITY-TOKEN']

        # Prepare headers for new requests.Requests.
        headers = {
            'X-IG-API-KEY': IG_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8',
            'X-SECURITY-TOKEN': XST,
            'CST': CST}

        name, search, iclass, idetails, epic, expiry, psize, minsize, currencies, unit = None, None, None, None, None, None, None, None, None, None

        # Action the signal only if the ticker code is known.
        if webhook_signal['ticker'].upper() in TICKER_MAP.keys():

            name = TICKER_MAP[webhook_signal['ticker'].upper()][0]
            search = TICKER_MAP[webhook_signal['ticker'].upper()][1]
            iclass = TICKER_MAP[webhook_signal['ticker'].upper()][2]

            # Find the appropriate instrument to match the given webhook ticker code.
            markets = s.send(requests.Request('GET', IG_URL + "/markets?searchTerm=" + search, headers=headers, params='').prepare())
            for market in markets.json()['markets']:
                if market['expiry'] != "DFB" and market['instrumentName'][:len(name)] == name and market['instrumentType'] == iclass:
                    epic, expiry = market["epic"], market["expiry"]
                    break

            # Fetch remaining instrument info.
            idetails = s.send(requests.Request('GET', IG_URL + "/markets/" + epic, headers=headers, params='').prepare()).json()
            psize = idetails['instrument']['lotSize']
            currencies = [c['name'] for c in idetails['instrument']['currencies']]
            minsize = idetails['dealingRules']['minDealSize']['value']
            unit = idetails['dealingRules']['minDealSize']['unit']

        else:
            print("Error: Webhook ticker code not recognised.")
            return {
                'statusCode': 400,
                'body': json.dumps("Webhook ticker code not recognised.")}

        # Use best current bid and offer to calculate stop and tp level price.
        side = webhook_signal['side'].upper()
        if side == "BUY":
            stop = (idetails['snapshot']['bid'] / 100) * (100 - STOP_DISTANCE)
            tp = (idetails['snapshot']['offer'] / 100) * (100 + TP_DISTANCE)
        elif side == "SELL":
            stop = (idetails['snapshot']['offer'] / 100) * (100 + TP_DISTANCE)
            tp = (idetails['snapshot']['bid'] / 100) * (100 - STOP_DISTANCE)
        else:
            print("Error: Side value incorrect")
            return {
                'statusCode': 400,
                'body': json.dumps(side)}

        position_size = SIZE_MULTI * minsize

        # Specify order details.
        order = {
            "epic": epic,
            "expiry": expiry,
            "direction": side,
            "size": position_size,
            "orderType": "MARKET",
            # "timeInForce": None,
            "level": None,
            "guaranteedStop": False,
            "stopLevel": int(stop),
            "stopDistance": None,
            # "trailingStop": False,
            # "trailingStopIncrement": None,
            "forceOpen": "true",
            "limitLevel": int(tp),
            "limitDistance": None,
            "quoteId": None,
            "currencyCode": currencies[0]
        }

        print(webhook_signal['ticker'].upper(), name, "Expiry:", expiry, psize,
              currencies, "Min. deal size:", minsize, "Deal unit:", unit)

        # Open a position.
        print(json.dumps(order, indent=2))
        r = s.send(requests.Request('POST', IG_URL + "/positions/otc", headers=headers, json=order, params='').prepare())

        if r.status_code == 200:
            success_msg = "Orders placed. Deal ref#: " + r.json()['dealReference']
            return {
                'statusCode': 200,
                'body': json.dumps(success_msg)}
        else:
            print("Order placement failure.")
            return {
                'statusCode': r.status_code,
                'body': json.dumps("Order placement failure.")}

    else:
        print("Webhook signal token error")
        return {
            'statusCode': 400,
            'body': json.dumps("Webhook signal token error")}