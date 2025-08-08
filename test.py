import requests

url = "http://192.168.1.20:8090/api/main/view"
payload = {
    "j2000": {
        "ra": 83.8221,
        "dec": -5.3911
    },
    "fov": 1.0
}
headers = {"Content-Type": "application/json"}
response = requests.post(url, json=payload, headers=headers)
print(response.text)
