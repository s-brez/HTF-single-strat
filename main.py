from requests import Request, Session
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

    LIVE = False

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
        s = Session()

        headers = {
            'X-IG-API-KEY': IG_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8'}

        body = {
            "identifier": IG_USERNAME,
            "password": IG_PASSWORD}

        response = s.send(
            Request('POST', IG_URL + "/session", json=body, headers=headers,
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

        # ticker_code: (instrument name, search term, instrument class)
        ticker_map = {
            "UKOIL": ("Oil - Brent Crude", "brent", "COMMODITIES"),
            "CFDs on Brent Crude Oil": ("Oil - Brent Crude", "brent", "COMMODITIES"),
            "DE30EUR": ("Germany 30 Cash", "dax", "INDICES"),
            "DAX": ("Germany 30 Cash", "dax", "INDICES"),
            "WHTUSD": ("Chicago Wheat", "chicago%20wheat", "COMMODITIES"),
            "WHEATUSD": ("Chicago Wheat", "chicago%20wheat", "COMMODITIES")}

        name, search, iclass, idetails, epic, expiry, psize, minsize, currencies, unit = None, None, None, None, None, None, None, None, None, None

        # Action the signal only if the ticker code is known.
        if webhook_signal['ticker'].upper() in ticker_map.keys():

            name = ticker_map[webhook_signal['ticker'].upper()][0]
            search = ticker_map[webhook_signal['ticker'].upper()][1]
            iclass = ticker_map[webhook_signal['ticker'].upper()][2]

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

        print(webhook_signal['ticker'].upper(), name, "Expiry:", expiry, psize,
              currencies, "Min. deal size:", minsize, "Deal unit:", unit)

        print(json.dumps(idetails['snapshot'], indent=2))

        # Place entry, stop and take profit orders.

    else:
        print("Webhook signal token error")
        return {
            'statusCode': 400,
            'body': json.dumps("Webhook signal token error")}


event = {"body": '{"ticker": "UKOIL", "exchange": "TVC", "open": 42.42,  "close": 42.57, "high": 42.68, "low": 42.34, "volume": 806, "time": "2019-08-27T09:56:00Z", "text": "", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}'}


# Paste this into webhook
# {"ticker": {{ticker}}, "exchange": {{exchange}}, "open": {{open}},  "close": {{close}}, "high": {{high}}, "low": {{low}}, "volume": {{volume}}, "time": {{time}}, "text": "", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}


lambda_handler(event, context=None)


# UKOIL - 210m
# WHEATUSD - 120m
# DE30EUR - 60m