from requests import Request, Session
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

    # Action the signal if token matches.
    if webhook_signal['token'] == WEBHOOK_TOKEN:
        print("Actioning webhook signal")

        # Load auth tokens from environment variables.
        if LIVE:
            if(  # Live.
                os.environ['IG_API_KEY'] and os.environ['IG_USERNAME'] and
                    os.environ['IG_PASSWORD']):
                IG_API_KEY = os.environ['IG_API_KEY']
                IG_USERNAME = os.environ['IG_USERNAME']
                IG_PASSWORD = os.environ['IG_PASSWORD']
                IG_URL = "https://api.ig.com/gateway/deal/session"
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
                IG_URL = "https://demo-api.ig.com/gateway/deal/session"
            else:
                print("Error: IG Markets demo authentication tokens missing")
                return {
                    'statusCode': 400,
                    'body': json.dumps(
                        "IG Markets demo authentication tokens missing")}

        # Open new session with IG.
        headers = {
            'X-IG-API-KEY': IG_API_KEY,
            'Content-Type': 'application/json',
            'Accept': 'application/json; charset=UTF-8'}

        body = {
            "identifier": IG_USERNAME,
            "password": IG_PASSWORD}

        response = Session().send(
            Request('POST', IG_URL, json=body, headers=headers,
                    params='').prepare())

        # CST and X-SECURITY-TOKEN must be included in subsequent requests.
        CST, XST = response.headers['CST'], response.headers['X-SECURITY-TOKEN']

        print(response)

        # START ORDER SIZING & SUBMISSION
        # Add logic here to prepare prders to be sent to IG.
        orders_to_send = None
        # Send prepared prders to IG with provided client methods.
        order_confirmations = None

    else:
        print("Webhook signal token error")
        return {
            'statusCode': 400,
            'body': json.dumps("Webhook signal token error")}


event = {"body": '{"text": "Test", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}'}
# {"ticker": {{ticker}}, "exchange": {{exchange}}, "open": {{open}},  "close": {{close}}, "high": {{high}}, "low": {{low}}, "volume": {{volume}}, "time": {{time}}}

lambda_handler(event, context=None)
