from src.polymarket.api_client import PolymarketAPIClient

api = PolymarketAPIClient()
trades = api.get_trader_trades('0xb27bc932bf8110d8f78e55da7d5f0497a18b5b82', limit=5)

print(f"Найдено сделок: {len(trades)}\n")

for trade in trades[:5]:
    parsed = api.parse_trade_data(trade)
    print(f"[{parsed['side']}] {parsed['title'][:40]}")
    print(f"  Outcome: {parsed['outcome']} @ ${parsed['price']:.2f}")
    print(f"  Size: ${parsed['size']:.2f}")
    print(f"  Time: {parsed['timestamp']}")
    print()