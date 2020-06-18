import requests
import os


def run(tradingview_webhook_signal):
    """
    Setup:
    Copy run() function body into AWS lambda and set required enviroment vars.
    Ensure the incoming signal parameter is JSON format or otherwise parsable.

    Event flow:
    1. Signal received from TradingView alert webhook.
    2. Calculate entry/stop/TP order size.
    3. Raise orders with venue.

    """

    # START AUTH TOKENS
    if os.environ['IG_API_KEY'] and os.environ['IG_API_SECRET']:
        IG_API_KEY = os.environ['IG_API_KEY']
        IG_API_SECRET = os.environ['IG_API_SECRET']
    else:
        raise Exception("IG Markets API keys missing.")
    # END AUTH TOKENS

    # START IG API CLIENT
    # Instantiate an IG Markets python client, using the keys loaded above.
    # END IG API CLIENT

    # START PARSE WEBHOOK SIGNAL
    # Add logic to parse incoming webhook signal here.
    # END PARSE WEBHOOK SIGNAL

    # START ORDER SIZING & SUBMISSION
    # Add logic here to prepare your prders to be sent to IG.
    # Send prepared prders to IG with their provided client methods.
    # END ORDER SIZING & SUBMISSION

    # START SEND USER NOTIFICATION (OPTIONAL)
    # Add messaging client logic here (e.g Telegram or email) to notify user
    # of signals/trades taken.
    # END SEND USER NOTIFICATION
