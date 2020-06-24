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

        # Australian ticker code > IG epic mapping.
        # Aus uses non expiring contracts. No need to fetch dynamically.
        ticker_epic = {
            "UKOIL": "CC.D.LCO.UMA.IP",
            "CFDs on Brent Crude Oil": "CC.D.LCO.UMA.IP",
            "DE30EUR": "IX.D.DAX.IFA.IP",
            "DAX": "IX.D.DAX.IFA.IP",
            "WHTUSD": "CC.D.W.UMA.IP",
            "WHEATUSD": "CC.D.W.UMA.IP"}

        # Get epics dynamically for UK markets as UK uses expiring contracts
        brent_markets = Session().send(
            Request('GET', IG_URL + "/markets?searchTerm=brent",
                    headers=headers, params='').prepare())
        brent_epic_uk = None
        for market in brent_markets.json()['markets']:
            if market['expiry'] != "DFB" and market['instrumentName'] == "Oil - Brent Crude" and market['instrumentType'] == "COMMODITIES":
                brent_epic_uk = market["epic"]
                break

        dax_markets = Session().send(
            Request('GET', IG_URL + "/markets?searchTerm=dax",
                    headers=headers, params='').prepare())
        dax_epic_uk = None
        for market in dax_markets.json()['markets']:
            if market['expiry'] != "DFB" and market['instrumentName'] == "Germany 30" and market['instrumentType'] == "INDICES":
                dax_epic_uk = market["epic"]
                break

        wheat_markets = Session().send(
            Request('GET', IG_URL + "/markets?searchTerm=chicago%20wheat",
                    headers=headers, params='').prepare())
        wheat_epic_uk = None
        for market in wheat_markets.json()['markets']:
            if market['expiry'] != "DFB" and market['instrumentName'] == "Chicago Wheat" and market['instrumentType'] == "COMMODITIES":
                wheat_epic_uk = market["epic"]
                break

        # UK ticker code > IG epic mapping.
        ticker_epic = {
            "UKOIL": brent_epic_uk,
            "CFDs on Brent Crude Oil": brent_epic_uk,
            "DE30EUR": dax_epic_uk,
            "DAX": dax_epic_uk,
            "WHTUSD": wheat_epic_uk,
            "WHEATUSD": wheat_epic_uk}

        print(webhook_signal)

        # Place entry, stop, and take profit orders.

    else:
        print("Webhook signal token error")
        return {
            'statusCode': 400,
            'body': json.dumps("Webhook signal token error")}


event = {"body": '{"text": "Test", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}'}

# Format this with real values for testing
# {"ticker": {{ticker}}, "exchange": {{exchange}}, "open": {{open}},  "close": {{close}}, "high": {{high}}, "low": {{low}}, "volume": {{volume}}, "time": {{time}}, "text": "", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}

# Paste this into webhook
# {"ticker": {{ticker}}, "exchange": {{exchange}}, "open": {{open}},  "close": {{close}}, "high": {{high}}, "low": {{low}}, "volume": {{volume}}, "time": {{time}}, "text": "", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}


lambda_handler(event, context=None)
