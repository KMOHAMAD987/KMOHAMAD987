"""
وب‌سرور Flask — API برای داشبورد و Mini App تلگرام
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, render_template, request
from signals.tracker import get_open_trades, get_stats, _load_db
from data.bitunix_client import get_ticker
from telegram.bot import load_users, ADMIN_IDS
from datetime import datetime

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")


@app.route("/")
def landing():
    return render_template("landing_v5.html")


@app.route("/dashboard")
def dashboard():
    return render_template("user_dashboard.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


# ── API ──

@app.route("/api/signals")
def api_signals():
    trades = get_open_trades()
    return jsonify({"ok": True, "signals": trades})


@app.route("/api/stats")
def api_stats():
    stats = get_stats()
    return jsonify({"ok": True, "stats": stats})


@app.route("/api/trades")
def api_trades():
    db = _load_db()
    all_trades = list(db.get("trades", {}).values())
    all_trades.sort(key=lambda t: t.get("opened_at", ""), reverse=True)
    limit = int(request.args.get("limit", 50))
    return jsonify({"ok": True, "trades": all_trades[:limit]})


@app.route("/api/prices")
def api_prices():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    prices = {}
    for sym in symbols:
        try:
            t = get_ticker(sym)
            prices[sym] = {"price": float(t.get("lastPrice", 0)), "change": float(t.get("priceChangePercent", 0))}
        except:
            prices[sym] = {"price": 0, "change": 0}
    return jsonify({"ok": True, "prices": prices})


@app.route("/api/users")
def api_users():
    users = load_users()
    return jsonify({
        "ok": True,
        "total": len(users),
        "active": sum(1 for u in users.values() if u.get("active")),
        "users": [{"id": uid, "name": u.get("first_name", "?"), "plan": u.get("plan", "trial"),
                    "active": u.get("active", False)} for uid, u in users.items()]
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
