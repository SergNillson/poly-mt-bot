import requests
import json

query = """
{
  user(id: "0xb27bc932bf8110d8f78e55da7d5f0497a18b5b82") {
    id
    trades(first: 5, orderBy: timestamp, orderDirection: desc) {
      id
      market
      outcome
      size
      price
      timestamp
      transactionHash
    }
  }
}
"""

url = "https://api.thegraph.com/subgraphs/name/polymarket/matic-markets"

response = requests.post(url, json={'query': query})
print("Статус:", response.status_code)
print("\nОтвет:")
print(json.dumps(response.json(), indent=2))