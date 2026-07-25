# APIs & HTTP
# Python can fetch data from the web using urllib.

import urllib.request
import json

# === Fetching a web page ===
# urllib.request.urlopen() sends an HTTP request
url = "https://httpbin.org/get"

try:
    with urllib.request.urlopen(url) as response:
        data = response.read().decode("utf-8")
        result = json.loads(data)
        print("Response from httpbin.org:")
        print(f"  URL: {result['url']}")
        print(f"  Origin: {result['origin']}")
except urllib.error.URLError as e:
    print(f"Could not connect: {e}")
    print("(You may need an internet connection)")

# === Sending data with POST ===
post_url = "https://httpbin.org/post"
post_data = json.dumps({"name": "Alice", "score": 95}).encode("utf-8")

try:
    req = urllib.request.Request(
        post_url,
        data=post_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode("utf-8"))
        print(f"\nPOST response:")
        print(f"  Sent: {result['data']}")
except urllib.error.URLError:
    print("\n(Skipping POST — no internet)")

# === Working with JSON data locally ===
# Even without internet, you can practice with JSON:
api_response = '''{
    "users": [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25}
    ]
}'''

data = json.loads(api_response)
print("\nParsed JSON:")
for user in data["users"]:
    print(f"  {user['name']}, age {user['age']}")
