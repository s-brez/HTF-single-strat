from requests.packages.urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests import Request, Session
from datetime import datetime
from time import sleep
import json
import sys
import os


def lambda_handler(event, context):
    """
    Setup:
    Copy run() function body into AWS lambda and set required enviroment vars.
    Ensure the incoming signal parameter is JSON format or otherwise parsable.
    """

    # Set True for live trading, false for demo acount.
    LIVE = False

    # ticker_code: (instrument name, search term, instrument class, size multi)
    TICKER_MAP = {
        "UKOIL": ("Oil - Brent Crude", "brent", "COMMODITIES", 1),
        "CFDs on Brent Crude Oil": ("Oil - Brent Crude", "brent", "COMMODITIES", 1),
        "DE30EUR": ("Germany 30", "dax", "INDICES", 1),
        "DAX": ("Germany 30", "dax", "INDICES", 1),
        "WHTUSD": ("Chicago Wheat", "chicago%20wheat", "COMMODITIES", 15),
        "WHEATUSD": ("Chicago Wheat", "chicago%20wheat", "COMMODITIES", 15)}

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

    # Action signal only if webhook token matches stored token.
    if webhook_signal['token'] == WEBHOOK_TOKEN:

        # Action signal only if ticker code is known.
        if webhook_signal['ticker'].upper() in TICKER_MAP.keys():

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
                    os.environ['IG_API_KEY_DEMO_UK'] and os.environ['IG_USERNAME_DEMO_UK'] and
                        os.environ['IG_PASSWORD_DEMO_UK']):
                    IG_API_KEY = os.environ['IG_API_KEY_DEMO_UK']
                    IG_USERNAME = os.environ['IG_USERNAME_DEMO_UK']
                    IG_PASSWORD = os.environ['IG_PASSWORD_DEMO_UK']
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

            # Initiate and reload the session as sometimes first session fails.
            response = s.send(Request('POST', IG_URL + "/session", json=body, headers=headers,
                              params='').prepare())
            sleep(1)
            response = s.send(Request('POST', IG_URL + "/session", json=body, headers=headers,
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

            name = TICKER_MAP[webhook_signal['ticker'].upper()][0]
            search = TICKER_MAP[webhook_signal['ticker'].upper()][1]
            iclass = TICKER_MAP[webhook_signal['ticker'].upper()][2]
            size_multi = TICKER_MAP[webhook_signal['ticker']][3]

            # Check for open positions.
            existing_positions = s.send(Request('GET', IG_URL + "/positions", headers=headers, params='').prepare()).json()
            find_instrument = True

            # If open position exists matching ticker code, use that EPIC and expiry.
            if len(existing_positions['positions']) > 0:
                for pos in existing_positions['positions']:
                    if name in pos['market']['instrumentName'][:len(name)]:
                        print("Open position exists for " + name + ".")
                        print(json.dumps(pos, indent=2))
                        epic = pos['market']["epic"]
                        expiry = pos['market']["expiry"]

                        # Store open position data.
                        position = pos
                        find_instrument = False

            # Otherwise identify appropriate instrument.
            if find_instrument:

                # Find appropriate instrument to match given webhook ticker code.
                markets = s.send(Request('GET', IG_URL + "/markets?searchTerm=" + search, headers=headers, params='').prepare())

                for market in markets.json()['markets']:
                    # print(json.dumps(market, indent=2))
                    if market['expiry'] != "DFB" and market['instrumentName'][:len(name)] == name and market['instrumentType'] == iclass:
                        epic, expiry = market["epic"], market["expiry"]
                        break

            # Fetch remaining instrument info.
            idetails = s.send(Request('GET', IG_URL + "/markets/" + epic, headers=headers, params='').prepare()).json()
            psize = idetails['instrument']['lotSize']
            currencies = [c['name'] for c in idetails['instrument']['currencies']]
            minsize = idetails['dealingRules']['minDealSize']['value'] if idetails['dealingRules']['minDealSize']['value'] >= 1 else 1
            unit = idetails['dealingRules']['minDealSize']['unit']

            # Debug use only.
            # for i in [position, name, search, iclass, idetails, epic, expiry, psize, minsize, currencies, unit]:
            #     print(json.dumps(i, indent=2))

        else:
            print("Error: Webhook ticker code not recognised.")
            return {
                'statusCode': 400,
                'body': json.dumps("Webhook ticker code not recognised.")}

        side = webhook_signal['side'].upper()
        position_size = size_multi * minsize

        # Handle unique trade rules per ticker.
        if name == "Chicago Wheat":

            sl_both = 20
            closed = False

            if position:

                # Filter non-sequential signals
                if position['position']['direction'] == "BUY" and side == "SELL" or position['position']['direction'] == "SELL" and side == "BUY":
                    close_side = "BUY" if position['position']['direction'] == "SELL" else "SELL"
                    body = {
                        "dealId": position['position']['dealId'],
                        "epic": None,
                        "expiry": expiry,
                        "direction": close_side,
                        "size": pos['position']['dealSize'],
                        "level": None,
                        "orderType": "MARKET",
                        "timeInForce": None,
                        "quoteId": None}

                    # Attempt to close the existing position.
                    headers['_method'] = "DELETE"
                    r = s.send(Request("POST", IG_URL + "/positions/otc", headers=headers, json=body, params='').prepare())
                    del headers['_method']
                    ref = r.json()
                    if r.status_code == 200:

                        # Check if position was closed.
                        c = s.send(Request('GET', IG_URL + "/confirms/" + ref['dealReference'], headers=headers, params='').prepare())
                        conf = c.json()
                        closed = True if conf['dealStatus'] == "ACCEPTED" else False

                        # Handle error cases.
                        if conf['dealStatus'] == "REJECTED":
                            if conf['reason'] == "MARKET_OFFLINE" or conf['reason'] == "MARKET_CLOSED_WITH_EDITS":
                                print("Market offline.")
                                return {
                                    'statusCode': 400,
                                    'body': json.dumps("Market offline.")}
                            else:
                                return {
                                    'statusCode': 400,
                                    'body': json.dumps(conf)}
                    else:
                        print("Position closure failure.")
                        return {
                            'statusCode': r.status_code,
                            'body': json.dumps("Order placement failure.")}

            if not position or closed:
                sl = idetails['snapshot']['offer'] - sl_both if side == "BUY" else idetails['snapshot']['bid'] + sl_both
                tp = None

                # Prepare new position order.
                order = {
                    "epic": epic,
                    "expiry": expiry,
                    "direction": side,
                    "size": position_size,
                    "orderType": "MARKET",
                    # "timeInForce": None,
                    "level": None,
                    "guaranteedStop": False,
                    "stopLevel": sl,
                    "stopDistance": None,
                    # "trailingStop": False,
                    # "trailingStopIncrement": None,
                    "forceOpen": True,
                    "limitLevel": tp,
                    "limitDistance": None,
                    "quoteId": None,
                    "currencyCode": "GBP"
                }

                # Attempt to open a new position.
                r = s.send(Request('POST', IG_URL + "/positions/otc", headers=headers, json=order, params='').prepare())
                ref = r.json()
                if r.status_code == 200:

                    # Check if new position was opened.
                    c = s.send(Request('GET', IG_URL + "/confirms/" + ref['dealReference'], headers=headers, params='').prepare())
                    conf = c.json()

                    # Handle error cases.
                    if conf['dealStatus'] == "REJECTED":
                        if conf['reason'] == "MARKET_OFFLINE" or conf['reason'] == "MARKET_CLOSED_WITH_EDITS":
                            print("Market offline.")
                            return {
                                'statusCode': 400,
                                'body': json.dumps("Market offline.")}
                        else:
                            return {
                                'statusCode': 400,
                                'body': json.dumps(conf)}

                    # Return 200 on success.
                    elif conf['dealStatus'] == "ACCEPTED":
                        success_string = name + " position opened successfully."
                        print(success_string)
                        return {
                            'statusCode': 200,
                            'body': json.dumps(success_string)}

                    # Log other cases.
                    else:
                        print(conf)
                        return {
                            'statusCode': 400,
                            'body': json.dumps(conf)}
                else:
                    print("Order placement failure.")
                    return {
                        'statusCode': r.status_code,
                        'body': json.dumps("Order placement failure.")}
            else:
                msg_string = name + " failed to close existing position."
                print(msg_string)
                return {
                    'statusCode': 400,
                    'body': json.dumps(msg_string)}

        elif name == "Germany 30":

            sl_long, sl_short, adjust = 150, 150, 4
            tp_both = 50

            # Signal side must be "BUY" "SELL" "CLOSE_BUY" "CLOSE_SELL"

            # Open a new long or short.
            if side == "BUY" or side == "SELL":

                # sl = idetails['snapshot']['offer'] - sl_long if side == "BUY" else idetails['snapshot']['bid'] + sl_short
                if side == "BUY":
                    stop = idetails['snapshot']['bid'] - sl_short + adjust
                    tp = idetails['snapshot']['offer'] + tp_both
                elif side == "SELL":
                    stop = idetails['snapshot']['offer'] + sl_short - adjust
                    tp = idetails['snapshot']['bid'] - tp_both

                # Prepare new position order.
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
                    "forceOpen": True,
                    "limitLevel": tp,
                    "limitDistance": None,
                    "quoteId": None,
                    "currencyCode": currencies[0]
                }

                # Attempt to open a new position.
                if position is None:
                    r = s.send(Request('POST', IG_URL + "/positions/otc", headers=headers, json=order, params='').prepare())
                    ref = r.json()
                    if r.status_code == 200:

                        # Check if new position was opened.
                        c = s.send(Request('GET', IG_URL + "/confirms/" + ref['dealReference'], headers=headers, params='').prepare())
                        conf = c.json()

                        # Handle error cases.
                        if conf['dealStatus'] == "REJECTED":
                            if conf['reason'] == "MARKET_OFFLINE" or conf['reason'] == "MARKET_CLOSED_WITH_EDITS":
                                print("Market offline.")
                                return {
                                    'statusCode': 400,
                                    'body': json.dumps("Market offline.")}
                            else:
                                return {
                                    'statusCode': 400,
                                    'body': json.dumps(conf)}

                        # Return 200 on success.
                        elif conf['dealStatus'] == "ACCEPTED":
                            success_string = name + " position opened successfully."
                            print(success_string)
                            return {
                                'statusCode': 200,
                                'body': json.dumps(success_string)}

                        # Log other cases.
                        else:
                            print(conf)
                            return {
                                'statusCode': 400,
                                'body': json.dumps(conf)}

                elif position:
                    msg_string = name + " already positioned."
                    print(msg_string)
                    return {
                        'statusCode': 400,
                        'body': json.dumps(msg_string)}

            # Close the existing long or short.
            elif side.upper() == "CLOSE_BUY" or side.upper() == "CLOSE_SELL":

                # Prepare closure order.
                if position:
                    close_side = "BUY" if side.upper() == "CLOSE_SELL" else "SELL"
                    body = {
                        "dealId": position['position']['dealId'],
                        "epic": None,
                        "expiry": expiry,
                        "direction": close_side,
                        "size": pos['position']['dealSize'],
                        "level": None,
                        "orderType": "MARKET",
                        "timeInForce": None,
                        "quoteId": None}

                    # Add new method header for position closures
                    headers['_method'] = "DELETE"
                    r = s.send(Request("POST", IG_URL + "/positions/otc", headers=headers, json=body, params='').prepare())
                    del headers['_method']
                    ref = r.json()

                    if r.status_code == 200:

                        # Check if position was closed.
                        c = s.send(Request('GET', IG_URL + "/confirms/" + ref['dealReference'], headers=headers, params='').prepare())
                        conf = c.json()

                        # Handle error cases.
                        if conf['dealStatus'] == "REJECTED":
                            if conf['reason'] == "MARKET_OFFLINE" or conf['reason'] == "MARKET_CLOSED_WITH_EDITS":
                                print("Market offline.")
                                return {
                                    'statusCode': 400,
                                    'body': json.dumps("Market offline.")}
                            else:
                                return {
                                    'statusCode': 400,
                                    'body': json.dumps(conf)}

                        # Return 200 on success.
                        elif conf['dealStatus'] == "ACCEPTED":
                            success_string = name + " position closed successfully."
                            print(success_string)
                            return {
                                'statusCode': 200,
                                'body': json.dumps(success_string)}

                        # Log other cases.
                        else:
                            print(conf)
                            return {
                                'statusCode': 400,
                                'body': json.dumps(conf)}

                else:
                    print("No existing position.")
                    return {
                        'statusCode': 400,
                        'body': json.dumps("No existing position.")}

            else:
                print("Webhook signal side error")
                return {
                    'statusCode': 400,
                    'body': json.dumps("Webhook signal side error")}

        elif name == "Oil - Brent Crude":

            if not position:
                sl_pips, tp_pips, adjust = 150, 35, 2.8

                # Open positon with linked sl and tp using best bid and offer, then
                # get confirmed entry level and adjust sl and tp to new values.

                if side == "BUY":
                    stop = idetails['snapshot']['bid'] - sl_pips + adjust
                    tp = idetails['snapshot']['offer'] + tp_pips
                elif side == "SELL":
                    stop = idetails['snapshot']['offer'] + sl_pips - adjust
                    tp = idetails['snapshot']['bid'] - tp_pips
                else:
                    print("Webhook signal side error")
                    return {
                        'statusCode': 400,
                        'body': json.dumps("Webhook signal side error")}

                # Prepare new position order.
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
                    "forceOpen": True,
                    "limitLevel": tp,
                    "limitDistance": None,
                    "quoteId": None,
                    "currencyCode": currencies[0]
                }

                # Attempt to open a new position.
                r = s.send(Request('POST', IG_URL + "/positions/otc", headers=headers, json=order, params='').prepare())
                ref = r.json()
                if r.status_code == 200:

                    # Check if new position was opened.
                    c = s.send(Request('GET', IG_URL + "/confirms/" + ref['dealReference'], headers=headers, params='').prepare())
                    conf = c.json()

                    # Handle error cases.
                    if conf['dealStatus'] == "REJECTED":
                        if conf['reason'] == "MARKET_OFFLINE" or conf['reason'] == "MARKET_CLOSED_WITH_EDITS":
                            print("Market offline.")
                            return {
                                'statusCode': 400,
                                'body': json.dumps("Market offline.")}
                        else:
                            print(conf)
                            return {
                                'statusCode': 400,
                                'body': json.dumps(conf)}

                    # Return 200 on success.
                    elif conf['dealStatus'] == "ACCEPTED":
                        success_string = name + " position opened successfully."
                        print(success_string)
                        return {
                            'statusCode': 200,
                            'body': json.dumps(success_string)}

                    # Log other cases.
                    else:
                        print(conf)
                        return {
                            'statusCode': 400,
                            'body': json.dumps(conf)}

            else:
                response_string = name + " position already open."
                print(response_string)
                return {
                    'statusCode': 400,
                    'body': json.dumps(response_string)}

        else:
            print("Error: Instrument name not recognised.")
            return {
                'statusCode': 400,
                'body': json.dumps("Instrument name not recognised.")}

    else:
        print("Webhook signal token error")
        return {
            'statusCode': 400,
            'body': json.dumps("Webhook signal token error")}


event = {"body": '{"ticker": "WHEATUSD", "exchange": "TVC", "side": "buy", "open": 42.42, "close": 42.57, "high": 42.68, "low": 42.34, "volume": 806, "time": "2019-08-27T09:56:00Z", "text": "", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}'}


# Paste into webhook:
# {"ticker": {{ticker}}, "exchange": {{exchange}}, "open": {{open}},  "close": {{close}}, "high": {{high}}, "low": {{low}}, "volume": {{volume}}, "time": {{time}}, "text": "", "token": "7f3c4d9a-9ac3-4819-b997-b8ee294d5a42"}


# print(json.dumps(event, indent=2))
print(lambda_handler(event, context=None))
