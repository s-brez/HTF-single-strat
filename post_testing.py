from requests import Request, Session
import json
import os


URL = ""


payload = {}

request = Request(
    'POST', URL, json=payload, params='').prepare()

request.headers['Content-Type'] = 'application/json'
request.headers['Accept'] = 'application/json'
request.headers['X-Requested-With'] = 'XMLHttpRequest'

response = Session().send(request)

print(response.json())
