from telegram.ext import Updater, MessageHandler, Filters
import trading_ig
import requests
import os


def run():
    """

    Copy function body into AWS lambda and set required enviroment vars.

    Event flow:

    1. Target timeframe bar close occurs.
    2. Fetch n required historic bars.
    3. Evaluate price data and generate trade signal if appropriate.
    4. If signal generated, send telegram notification and raise orders.
    """

    # Lookback period.
    N_REQUIRED_BARS = 100

    # Container for bars and indicator values.
    bars = {}

    if os.environ['IG_API_KEY'] and os.environ['IG_API_SECRET']:
        IG_API_KEY = os.environ['IG_API_KEY']
        IG_API_SECRET = os.environ['IG_API_SECRET']
    else:
        raise Exception("IG Markets API keys missing.")

    if os.environ['TELEGRAM_BOT_TOKEN']:
        TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
    else:
        raise Exception("Telegram auth token missing.")

    # Get n required previous bars.
    # TODO

    # Calculate indicators.
    # TODO

    # Run strategy logic.
    # TODO

    # If signal generated, notify user via telegram and place orders.
    # TODO
