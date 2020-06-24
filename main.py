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
        headers = {
            'X-IG-API-KEY': IG_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8'}

        body = {
            "identifier": IG_USERNAME,
            "password": IG_PASSWORD}

        response = Session().send(
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

        brent_epic, brent_expiry, brent_lotsize = None, None, None
        dax_epic, dax_expiry, dax_lotsize = None, None, None
        wheat_epic, wheat_expiry, wheat_lotsize = None, None, None

        # Fetch instrument details only if webhook signal has an appropriate ticker code.
        if webhook_signal['ticker'] == "UKOIL" or webhook_signal['ticker'] == "CFDs on Brent Crude Oil":
            brent_markets = Session().send(Request('GET', IG_URL + "/markets?searchTerm=brent", headers=headers, params='').prepare())
            for market in brent_markets.json()['markets']:
                if market['expiry'] != "DFB" and market['instrumentName'][:17] == "Oil - Brent Crude" and market['instrumentType'] == "COMMODITIES":
                    brent_epic, brent_expiry = market["epic"], market["expiry"]
                    break
            brent_lotsize = Session().send(Request('GET', IG_URL + "/markets/" + brent_epic, headers=headers, params='').prepare()).json()['instrument']['lotSize']

        elif webhook_signal['ticker'] == "DE30EUR" or webhook_signal['ticker'] == "DAX":
            dax_markets = Session().send(Request('GET', IG_URL + "/markets?searchTerm=dax", headers=headers, params='').prepare())
            for market in dax_markets.json()['markets']:
                if market['expiry'] != "DFB" and market['instrumentName'][:10] == "Germany 30" and market['instrumentType'] == "INDICES":
                    dax_epic, dax_expiry = market["epic"], market["expiry"]
                    break
            dax_lotsize = Session().send(Request('GET', IG_URL + "/markets/" + dax_epic, headers=headers, params='').prepare()).json()['instrument']['lotSize']

        elif webhook_signal['ticker'] == "WHEATUSD" or webhook_signal['ticker'] == "WHTUSD":
            wheat_markets = Session().send(Request('GET', IG_URL + "/markets?searchTerm=chicago%20wheat", headers=headers, params='').prepare())
            for market in wheat_markets.json()['markets']:
                if market['expiry'] != "DFB" and market['instrumentName'][:13] == "Chicago Wheat" and market['instrumentType'] == "COMMODITIES":
                    wheat_epic, wheat_expiry = market["epic"], market["expiry"]
                    break
            wheat_lotsize = Session().send(Request('GET', IG_URL + "/markets/" + wheat_epic, headers=headers, params='').prepare()).json()['instrument']['lotSize']

        else:
            print("Error: Webhook ticker code not recognised.")
            return {
                'statusCode': 400,
                'body': json.dumps("Webhook ticker code not recognised.")}

        # Ticker code: EPIC code mapping.
        ticker_epic_map = {
            "UKOIL": brent_epic,
            "CFDs on Brent Crude Oil": brent_epic,
            "DE30EUR": dax_epic,
            "DAX": dax_epic,
            "WHTUSD": wheat_epic,
            "WHEATUSD": wheat_epic}

        print("Brent", ticker_epic_map['UKOIL'], brent_expiry, brent_lotsize)
        print("DAX", ticker_epic_map['DAX'], dax_expiry, dax_lotsize)
        print("Chicago Wheat", ticker_epic_map['WHEATUSD'], wheat_expiry, wheat_lotsize)

        # Place entry, then place stop and take profit orders  using the returned entry price.

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