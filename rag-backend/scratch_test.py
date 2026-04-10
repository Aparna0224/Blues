import urllib.request
import json
import sys

req = urllib.request.Request(
    'http://127.0.0.1:8000/api/query',
    data=json.dumps({'query': 'nlp'}).encode(),
    headers={'Content-Type': 'application/json'}
)

try:
    response = urllib.request.urlopen(req)
    print(response.read().decode())
except Exception as e:
    if hasattr(e, 'read'):
        print("ERROR:", e.read().decode())
    else:
        print("ERROR:", e)
