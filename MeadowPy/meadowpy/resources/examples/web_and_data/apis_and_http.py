# APIs & HTTP
# Python can fetch data from the web using urllib.

import json
import os
import urllib.error
import urllib.request

# Tests and offline classrooms can point this example at a local API.
api_base_url = os.environ.get(
    "MEADOWPY_EXAMPLE_API_BASE_URL",
    "https://httpbin.org",
).rstrip("/")

# === Fetching a web page ===
# urllib.request.urlopen() sends an HTTP request
url = f"{api_base_url}/get"

try:
    with urllib.request.urlopen(url, timeout=5) as response:
        data = response.read().decode("utf-8")
        result = json.loads(data)
        print("Response from httpbin.org:")
        print(f"  URL: {result['url']}")
        print(f"  Origin: {result['origin']}")
except (urllib.error.URLError, TimeoutError) as e:
    print(f"Could not connect: {e}")
    print("(You may need an internet connection)")

# === Sending data with POST ===
post_url = f"{api_base_url}/post"
post_data = json.dumps({"name": "Alice", "score": 95}).encode("utf-8")

try:
    req = urllib.request.Request(
        post_url,
        data=post_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        result = json.loads(response.read().decode("utf-8"))
        print("\nPOST response:")
        print(f"  Sent: {result['data']}")
except (urllib.error.URLError, TimeoutError):
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
