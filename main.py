from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests import Request, Session
from datetime import datetime
import json
import sys
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

    # ticker_code: (instrument name, search term, instrument class, stop pips, tp pips, size multi)
    TICKER_MAP = {
        "UKOIL": ("Oil - Brent Crude", "brent", "COMMODITIES", 1, 1, 1),
        "CFDs on Brent Crude Oil": ("Oil - Brent Crude", "brent", "COMMODITIES", 1, 1, 1),
        "DE30EUR": ("Germany 30 Cash", "dax", "INDICES", 1, 1, 1),
        "DAX": ("Germany 30 Cash", "dax", "INDICES", 1, 1, 1),
        "WHTUSD": ("Chicago Wheat", "chicago%20wheat", "COMMODITIES", 0, 0, 1),
        "WHEATUSD": ("Chicago Wheat", "chicago%20wheat", "COMMODITIES", 0, 0, 1)}

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
        retries = Retry(
            total=5,
            backoff_factor=0.25,
            status_forcelist=[502, 503, 504],
            method_whitelist=False)
        s = Session()
        s.mount('https://', HTTPAdapter(max_retries=retries))

        headers = {
            'X-IG-API-KEY': IG_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8'}

        body = {
            "identifier": IG_USERNAME,
            "password": IG_PASSWORD}

        response = s.send( Request('POST', IG_URL + "/session", json=body, headers=headers,
                    params='').prepare())

        # CST and X-SECURITY-TOKEN must be included in subsequent requests.
        CST, XST = response.headers['CST'], response.headers['X-SECURITY-TOKEN']

        # Prepare headers for new requests.
        headers = {
            'X-IG-API-KEY': IG_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8',
            'X-SECURITY-TOKEN': XST,
            'CST': CST}

        position, name, search, iclass, idetails, epic, expiry, psize, minsize, currencies, unit = None, None, None, None, None, None, None, None, None, None, None

        # Action the signal only if the ticker code is known.
        if webhook_signal['ticker'].upper() in TICKER_MAP.keys():

            name = TICKER_MAP[webhook_signal['ticker'].upper()][0]
            search = TICKER_MAP[webhook_signal['ticker'].upper()][1]
            iclass = TICKER_MAP[webhook_signal['ticker'].upper()][2]
            stop_pips = TICKER_MAP[webhook_signal['ticker']][3] if TICKER_MAP[webhook_signal['ticker']][3] else None
            tp_pips = TICKER_MAP[webhook_signal['ticker']][4] if TICKER_MAP[webhook_signal['ticker']][4] else None
            size_multi = TICKER_MAP[webhook_signal['ticker']][5]

            # Check for open positions.
            existing_positions = s.send(Request('GET', IG_URL + "/positions", headers=headers, params='').prepare()).json()

            # If open position exists matching ticker code, use that EPIC and expiry.
            if len(existing_positions['positions']) > 0:
                for pos in existing_positions['positions']:
                    if name in pos['market']['instrumentName'][:len(name)]:
                        print("Open position exists for " + name + ".")
                        print(json.dumps(pos, indent=2))
                        epic = pos['market']["epic"]
                        expiry = pos['market']["expiry"]

                        # Store the open position data.
                        position = pos
                        sys.exit(0)

            # Otherwise identify appropriate instrument.
            else:
                # Find the appropriate instrument to match the given webhook ticker code.
                markets = s.send(Request('GET', IG_URL + "/markets?searchTerm=" + search, headers=headers, params='').prepare())
                for market in markets.json()['markets']:
                    if market['expiry'] != "DFB" and market['instrumentName'][:len(name)] == name and market['instrumentType'] == iclass:
                        epic, expiry = market["epic"], market["expiry"]
                        break

            # Fetch remaining instrument info.
            idetails = s.send(Request('GET', IG_URL + "/markets/" + epic, headers=headers, params='').prepare()).json()
            psize = idetails['instrument']['lotSize']
            currencies = [c['name'] for c in idetails['instrument']['currencies']]
            minsize = idetails['dealingRules']['minDealSize']['value']
            unit = idetails['dealingRules']['minDealSize']['unit']

        else:
            print("Error: Webhook ticker code not recognised.")
            return {
                'statusCode': 400,
                'body': json.dumps("Webhook ticker code not recognised.")}

        side = webhook_signal['side'].upper()

        # Now that we have the instrument, and the status of any open positions,
        # handle actions per ticker.

        # For new trades:
        # Use best current bid and offer to calculate stop and tp level price.

        # Percentage based:
        # if side == "BUY" or side == "SELL":
        #     if side == "BUY":
        #         stop = (idetails['snapshot']['bid'] / 100) * (100 - stop_level)
        #         tp = (idetails['snapshot']['offer'] / 100) * (100 + tp_level)
        #     elif side == "SELL":
        #         stop = (idetails['snapshot']['offer'] / 100) * (100 + tp_level)
        #         tp = (idetails['snapshot']['bid'] / 100) * (100 - stop_level)

        # Pip based:
        if side == "BUY" or side == "SELL":
            if side == "BUY":
                stop = int(idetails['snapshot']['bid'] - stop_pips) if stop_pips else None
                tp = int(idetails['snapshot']['offer'] + tp_pips) if tp_pips else None
            elif side == "SELL":
                stop = int(idetails['snapshot']['offer'] + tp_pips) if tp_pips else None
                tp = int(idetails['snapshot']['bid'] - stop_pips) if stop_pips else None

            position_size = size_multi * minsize

            # Specify position details.
            order = {
                "epic": epic,
                "expiry": expiry,
                "direction": side,
                "size": position_size,
                "orderType": "MARKET",
                # "timeInForce": None,
                "level": None,
                "guaranteedStop": False,
                "stopLevel": stop,
                "stopDistance": None,
                # "trailingStop": False,
                # "trailingStopIncrement": None,
                "forceOpen": "true",
                "limitLevel": tp,
                "limitDistance": None,
                "quoteId": None,
                "currencyCode": currencies[0]
            }

            print(webhook_signal['ticker'].upper(), name, "Expiry:", expiry, psize,
                  currencies, "Min. deal size:", minsize, "Deal unit:", unit)

            # Attempt to open a position.
            r = s.send(Request('POST', IG_URL + "/positions/otc", headers=headers, json=order, params='').prepare())
            pos_r = r.json()

            if r.status_code == 200:
                # Check if a new position was opened.

                success_msg = "Deal ref#: " + pos_r['dealReference']
                return {
                    'statusCode': 200,
                    'body': json.dumps(success_msg)}
            else:
                print("Order placement failure.")
                return {
                    'statusCode': r.status_code,
                    'body': json.dumps("Order placement failure.")}

        # For close signals:
        elif side == "CLOSE_LONG" or side == "CLOSE_SHORT":

            # Get open positions.

            # If any exist, close them.
            pass

        else:
            print("Error: Side value incorrect")
            return {
                'statusCode': 400,
                'body': json.dumps(side)}

    else:
        print("Webhook signal token error")
        return {
            'statusCode': 400,
            'body': json.dumps("Webhook signal token error")}


event = {"body": '{"ticker": "WHEATUSD", "exchange": "TVC", "side": "sell", "open": 42.42, "close": 42.57, "high": 42.68, "low": 42.34, "volume": 806, "time": "2019-08-27T09:56:00Z", "text": "", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}'}


# Paste into webhook:
# {"ticker": {{ticker}}, "exchange": {{exchange}}, "open": {{open}},  "close": {{close}}, "high": {{high}}, "low": {{low}}, "volume": {{volume}}, "time": {{time}}, "text": "", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}


# print(json.dumps(event, indent=2))
print(lambda_handler(event, context=None))


# UKOIL - 210m
# WHEATUSD - 120m
# DE30EUR - 60m