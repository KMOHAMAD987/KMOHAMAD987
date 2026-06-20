"""
اضافه کردن endpoint های جدید به سرور zandibot
این فایل رو import کنید یا کد زیر رو به server.py اضافه کنید
"""

# ─── اضافه کنید به server.py قبل از if __name__ ───

PATCH_CODE = '''
@app.get("/api/trades/history")
async def trades_history(limit: int = 20):
    try:
        sys.path.insert(0, "/root/crypto-signal-bot")
        from signals.tracker import _load_db
        db = _load_db()
        all_trades = list(db.get("trades", {}).values())
        closed = [t for t in all_trades if t.get("status") != "OPEN"]
        closed.sort(key=lambda t: t.get("closed_at") or t.get("opened_at", ""), reverse=True)
        return {"ok": True, "data": closed[:limit]}
    except Exception as e:
        return {"ok": True, "data": []}

@app.get("/api/prices")
async def get_prices():
    try:
        sys.path.insert(0, "/root/crypto-signal-bot")
        from data.bitunix_client import get_ticker
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
        prices = {}
        for sym in symbols:
            try:
                t = get_ticker(sym)
                prices[sym] = {"price": float(t.get("lastPrice", 0)), "change": float(t.get("priceChangePercent", 0))}
            except:
                prices[sym] = {"price": 0, "change": 0}
        return {"ok": True, "prices": prices}
    except:
        return {"ok": False, "prices": {}}
'''
