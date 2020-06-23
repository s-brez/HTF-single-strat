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
    2. Load relevant auth tokens from environment variables.
    3. Parse incoming signal and calculate entry/stop/TP order size.
    4. Raise orders with venue.

    """

    # Set true for live trading.
    LIVE = False

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
            return {
                'statusCode': 400,
                'body': json.dumps(
                    "IG Markets demo authentication tokens missing")}

    # Prepare request for IG.
    headers = {
        'X-IG-API-KEY': IG_API_KEY,
        'Content-Type': 'application/json',
        'Accept': 'application/json; charset=UTF-8'}

    body = {
        "identifier": IG_USERNAME,
        "password": IG_PASSWORD}

    # Open new session with IG.
    request = Request('POST', IG_URL, json=body,
                      headers=headers, params='').prepare()

    response = Session().send(request)

    print(response)

    # Parse the incoming webhook json.
    tradingview_webhook_signal = json.loads(event['body'])

    # START ORDER SIZING & SUBMISSION
    # Add logic here to prepare prders to be sent to IG.
    orders_to_send = None
    # Send prepared prders to IG with provided client methods.
    order_confirmations = None


lambda_handler({"body": '{"text": "Test"}'}, None)
