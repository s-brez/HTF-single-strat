from telegram.ext import Updater, MessageHandler, Filters
import requests
import os


def run():
    """
    Setup:
    Copy function body into AWS lambda and set required enviroment vars.

    Event flow:
    1. Signal received from TradingView alert webhook.
    2. Raise orders

    """

    """
    START AUTH TOKENS
    """
    if os.environ['IG_API_KEY'] and os.environ['IG_API_SECRET']:
        IG_API_KEY = os.environ['IG_API_KEY']
        IG_API_SECRET = os.environ['IG_API_SECRET']
    else:
        raise Exception("IG Markets API keys missing.")

    if os.environ['TELEGRAM_BOT_TOKEN']:
        TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
    else:
        raise Exception("Telegram auth token missing.")
    """
    END AUTH TOKENS
    """

    """
    START IG API CLIENT
    """

    """
    END IG API CLIENT
    """
