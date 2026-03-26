from src.polymarket.api_client import PolymarketAPIClient

api = PolymarketAPIClient()
trader = "0xb27bc932bf8110d8f78e55da7d5f0497a18b5b82"

print(f"Получение сделок трейдера {trader}...\n")
trades = api.get_trader_trades(trader, limit=5)

if trades:
    print(f"✅ Найдено {len(trades)} сделок:\n")
    for i, trade in enumerate(trades, 1):
        parsed = api.parse_trade_data(trade)
        print(f"{i}. {parsed['title']}")
        print(f"   {parsed['side']} {parsed['outcome']} @ ${parsed['price']:.3f}")
        print(f"   Размер: ${parsed['size']:.2f}")
        print(f"   Время: {parsed['timestamp']}")
        print()
else:
    print("❌ Сделки не найдены")