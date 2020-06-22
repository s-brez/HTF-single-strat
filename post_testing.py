from requests import Request, Session
import json
import os


URL = "https://raz4jv8ir7.execute-api.us-east-1.amazonaws.com/default/1hr_strategy"


payload = {}

request = Request(
    'POST', URL, json=payload, params='').prepare()

request.headers['Content-Type'] = 'application/json'
request.headers['Accept'] = 'application/json'
request.headers['X-Requested-With'] = 'XMLHttpRequest'

response = Session().send(request)

print(response.json())