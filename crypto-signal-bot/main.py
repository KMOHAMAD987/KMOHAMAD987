"""
main.py - لوپ اصلی ربات سیگنال سبک امیر
هر ۱۵ دقیقه ۵ ارز برتر رو اسکن می‌کنه
سیگنال کامل → تلگرام + ذخیره در tracker
"""

import time
import threading
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.bitunix_client import get_klines, get_ticker
from signals.amir_strategy import analyze
from signals.tracker import (
    save_signal, update_trade, get_open_trades,
    expire_old_trades, get_winrate_report, get_trade_by_id,
    cleanup_test_trades
)
from telegram.bot import (
    send_signal, send_message,
    send_tp_notification, handle_commands
)


# ─────────────────────────────────────────
# تنظیمات
# ─────────────────────────────────────────

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

SCAN_INTERVAL   = 15 * 60   # هر ۱۵ دقیقه اسکن
TRACK_INTERVAL  = 60         # هر ۱ دقیقه TP/SL چک

MIN_CONFIDENCE  = "LOW"      # حداقل کانفیدنس برای ارسال
MIN_SCORE       = 8.5        # حداقل امتیاز — AMIR V6
MIN_RR          = 3.0        # حداقل R/R — 1:3

# cooldown — فاصله بین سیگنال‌های یک نماد
SIGNAL_COOLDOWN = 60 * 60   # ۱ ساعت
_COOLDOWN_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/cooldown.json")


def _load_cooldown() -> dict:
    os.makedirs(os.path.dirname(_COOLDOWN_FILE), exist_ok=True)
    if not os.path.exists(_COOLDOWN_FILE):
        return {}
    try:
        with open(_COOLDOWN_FILE) as f:
            return json.load(f)
    except:
        return {}


def _save_cooldown(cd: dict):
    with open(_COOLDOWN_FILE, "w") as f:
        json.dump(cd, f)


# ─────────────────────────────────────────
# دریافت داده چند تایم‌فریم
# ─────────────────────────────────────────

def fetch_all_timeframes(symbol: str):
    """دریافت کندل‌های ۴H، ۱H، ۱۵m، ۵m"""
    try:
        return {
            "4h":  get_klines(symbol, interval="4h",  limit=250),
            "1h":  get_klines(symbol, interval="1h",  limit=250),
            "15m": get_klines(symbol, interval="15m", limit=250),
            "5m":  get_klines(symbol, interval="5m",  limit=250),
        }
    except Exception as e:
        print(f"⚠️  خطا در دریافت داده {symbol}: {e}")
        return None


def get_btc_bias():
    """تحلیل کامل BTC — نمره و بایاس"""
    try:
        from signals.amir_strategy import analyze_btc
        df_4h  = get_klines("BTCUSDT", interval="4h",  limit=250)
        df_1h  = get_klines("BTCUSDT", interval="1h",  limit=250)
        df_15m = get_klines("BTCUSDT", interval="15m", limit=250)
        result = analyze_btc(df_4h, df_1h, df_15m)
        return result.get("bias", "neutral"), result.get("score", 5.0)
    except:
        return "neutral", 5.0


# ─────────────────────────────────────────
# اسکن یک نماد
# ─────────────────────────────────────────

def scan_symbol(symbol: str, btc_bias: str, btc_score: float = 5.0) -> None:
    """تحلیل کامل یک نماد و ارسال سیگنال اگه شرایط داشت"""

    # کولداون چک — از فایل می‌خونه (restart-safe)
    now = time.time()
    cooldown_db = _load_cooldown()
    last = cooldown_db.get(symbol, 0)
    if now - last < SIGNAL_COOLDOWN:
        remaining = int((SIGNAL_COOLDOWN - (now - last)) / 60)
        print(f"  ⏳ {symbol}: کولداون {remaining} دقیقه مانده")
        return

    print(f"  🔍 آنالیز {symbol}...")

    data = fetch_all_timeframes(symbol)
    if not data:
        return

    # اگه BTC خودشه، bias رو neutral بذار
    bias = "neutral" if symbol == "BTCUSDT" else btc_bias

    try:
        signal = analyze(
            symbol    = symbol,
            df_4h     = data["4h"],
            df_1h     = data["1h"],
            df_15m    = data["15m"],
            df_5m     = data["5m"],
            btc_bias  = bias,
            btc_score = btc_score if symbol != "BTCUSDT" else 5.0,
        )
    except Exception as e:
        print(f"  ⚠️  خطا در آنالیز {symbol}: {e}")
        return

    # فیلتر سیگنال
    if signal.direction == "NO_SIGNAL":
        detail = signal.reject_reason or "نامشخص"
        failed_info = ""
        if signal.failed:
            failed_info = " | " + " / ".join(str(f) for f in signal.failed[:4])
        print(f"  ➖ {symbol}: {detail}{failed_info}")
        return

    if signal.score < MIN_SCORE:
        print(f"  ➖ {symbol}: امتیاز کم ({signal.score}/10)")
        return

    if signal.rr < MIN_RR:
        print(f"  ➖ {symbol}: R/R پایین ({signal.rr})")
        return

    conf_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    if conf_order.get(signal.confidence, 0) < conf_order.get(MIN_CONFIDENCE, 2):
        print(f"  ➖ {symbol}: کانفیدنس پایین ({signal.confidence})")
        return

    # ✅ سیگنال معتبر
    print(f"  ✅ {symbol}: سیگنال {signal.direction} | امتیاز {signal.score}/10 | R/R {signal.rr}")

    # ذخیره در tracker
    trade_id = save_signal(signal)

    # ارسال به تلگرام
    ok = send_signal(signal)
    if ok:
        # cooldown رو در فایل ذخیره کن
        cooldown_db[symbol] = now
        _save_cooldown(cooldown_db)
        print(f"  📨 تلگرام ارسال شد")
    else:
        print(f"  ❌ ارسال تلگرام ناموفق")


# ─────────────────────────────────────────
# ردیابی معاملات باز
# ─────────────────────────────────────────

def track_open_trades() -> None:
    """چک TP/SL برای همه معاملات باز"""
    trades = get_open_trades()
    if not trades:
        return

    print(f"📋 ردیابی {len(trades)} معامله باز...")

    for trade in trades:
        symbol = trade["symbol"]
        tid    = trade["id"]

        try:
            ticker = get_ticker(symbol)
            # فیلدهای احتمالی قیمت در API
            price = float(ticker.get("lastPrice") or ticker.get("last") or ticker.get("markPrice") or ticker.get("close") or 0)
            if price <= 0:
                print(f"  ⚠️ {symbol}: قیمت نامعتبر از ticker: {ticker}")
                continue
        except Exception as e:
            print(f"  ⚠️ {symbol}: خطا در دریافت قیمت: {e}")
            continue

        hit = update_trade(tid, price)

        if hit:
            print(f"  🎯 {symbol}: {hit} زده شد!")
            # trade آپدیت‌شده رو از DB بخون (pnl_r و status به‌روزه)
            updated_trade = get_trade_by_id(tid)
            send_tp_notification(updated_trade or trade, hit)


# ─────────────────────────────────────────
# لوپ اسکن اصلی
# ─────────────────────────────────────────

def scan_loop() -> None:
    """لوپ اسکن هر ۱۵ دقیقه"""
    while True:
        now_str = datetime.now().strftime("%H:%M:%S")
        print(f"\n{'='*50}")
        print(f"🔄 اسکن شروع شد: {now_str}")
        print(f"{'='*50}")

        # expire کردن معاملات قدیمی
        expire_old_trades(max_hours=48)

        # بایاس BTC
        btc_bias, btc_score = get_btc_bias()
        print(f"₿  BTC Bias: {btc_bias}")

        # اسکن همه نمادها
        for symbol in SYMBOLS:
            scan_symbol(symbol, btc_bias, btc_score)
            time.sleep(2)  # فاصله بین درخواست‌ها

        print(f"\n⏰ اسکن بعدی: {SCAN_INTERVAL // 60} دقیقه دیگه")
        time.sleep(SCAN_INTERVAL)


# ─────────────────────────────────────────
# لوپ ردیابی
# ─────────────────────────────────────────

def track_loop() -> None:
    """لوپ ردیابی هر ۱ دقیقه"""
    time.sleep(10)  # صبر کن اسکن اول شروع بشه
    while True:
        try:
            track_open_trades()
        except Exception as e:
            print(f"⚠️ خطا در track: {e}")
        time.sleep(TRACK_INTERVAL)


# ─────────────────────────────────────────
# اجرای ربات
# ─────────────────────────────────────────

def main():
    # جلوگیری از اجرای هم‌زمان
    import fcntl
    lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data/.bot.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    lock_fp = open(lock_file, "w")
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("⛔ یه instance دیگه از ربات در حال اجراست!")
        sys.exit(1)

    # پاکسازی trade‌های تست
    cleanup_test_trades()

    print("🤖 ربات سیگنال سبک امیر شروع شد")
    print(f"📊 نمادها: {', '.join(SYMBOLS)}")
    print(f"⚙️  حداقل امتیاز: {MIN_SCORE}/10")
    print(f"⚙️  حداقل R/R: {MIN_RR}")
    print(f"⚙️  حداقل کانفیدنس: {MIN_CONFIDENCE}")
    print(f"⏱  فاصله اسکن: {SCAN_INTERVAL // 60} دقیقه")

    # پیام شروع به تلگرام
    send_message(
        "🤖 *ربات سیگنال سبک امیر شروع شد*\n\n"
        f"📊 نمادها: `{' | '.join(SYMBOLS)}`\n"
        f"⚙️ حداقل امتیاز: `{MIN_SCORE}/10`\n"
        f"⚙️ حداقل R/R: `{MIN_RR}`\n"
        f"⏱ اسکن هر: `{SCAN_INTERVAL // 60} دقیقه`\n\n"
        "دستورات:\n"
        "/winrate - گزارش وین‌ریت\n"
        "/trades  - معاملات باز\n"
        "/stats   - آمار کلی"
    )

    # Thread ردیابی
    t_track = threading.Thread(target=track_loop, daemon=True)
    t_track.start()

    # Thread دستورات تلگرام
    t_cmd = threading.Thread(target=handle_commands, daemon=True)
    t_cmd.start()

    # لوپ اصلی اسکن (در thread اصلی)
    scan_loop()


if __name__ == "__main__":
    main()
