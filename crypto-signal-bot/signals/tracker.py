"""
سیستم ردیابی سیگنال و وین‌ریت
هر سیگنال ذخیره میشه → قیمت چک میشه → TP1/TP2/SL ثبت میشه → وین‌ریت محاسبه میشه
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/trades.json")


# ─────────────────────────────────────────
# مدل معامله
# ─────────────────────────────────────────

@dataclass
class Trade:
    id:           str
    symbol:       str
    direction:    str        # LONG | SHORT
    timeframe:    str
    score:        int
    confidence:   str

    entry:        float
    stop_loss:    float
    tp1:          float
    tp2:          float
    tp3:          float
    rr:           float

    opened_at:    str        # ISO datetime
    closed_at:    Optional[str] = None

    # نتیجه
    status:       str  = "OPEN"   # OPEN | TP1 | TP2 | TP3 | SL | EXPIRED
    hit_tp1:      bool = False
    hit_tp2:      bool = False
    hit_tp3:      bool = False
    hit_sl:       bool = False
    exit_price:   Optional[float] = None
    pnl_r:        float = 0.0    # سود/ضرر بر اساس R

    # شرط‌های سبک امیر که برقرار بود
    reasons:      list = None
    failed:       list = None

    def __post_init__(self):
        if self.reasons is None:
            self.reasons = []
        if self.failed is None:
            self.failed = []


# ─────────────────────────────────────────
# دیتابیس ساده (JSON)
# ─────────────────────────────────────────

def _load_db() -> dict:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if not os.path.exists(DB_PATH):
        return {"trades": {}, "stats": _empty_stats()}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_db(db: dict):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2, default=str)


def _empty_stats() -> dict:
    return {
        "total":       0,
        "open":        0,
        "tp1_hit":     0,
        "tp2_hit":     0,
        "tp3_hit":     0,
        "sl_hit":      0,
        "expired":     0,
        "winrate_tp1": 0.0,
        "winrate_tp2": 0.0,
        "avg_rr":      0.0,
        "by_symbol":   {},
        "by_direction": {"LONG": 0, "SHORT": 0},
        "by_confidence": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
    }


# ─────────────────────────────────────────
# ذخیره سیگنال جدید
# ─────────────────────────────────────────

def save_signal(signal) -> str:
    """
    سیگنال جدید رو ذخیره کن
    signal: شیء Signal از amir_strategy

    Returns: trade_id
    """
    db = _load_db()

    trade_id = f"{signal.symbol}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    trade = Trade(
        id          = trade_id,
        symbol      = signal.symbol,
        direction   = signal.direction,
        timeframe   = signal.timeframe,
        score       = signal.score,
        confidence  = signal.confidence,
        entry       = signal.entry,
        stop_loss   = signal.stop_loss,
        tp1         = signal.tp1,
        tp2         = signal.tp2,
        tp3         = signal.tp3,
        rr          = signal.rr,
        opened_at   = datetime.utcnow().isoformat(),
        reasons     = signal.reasons,
        failed      = signal.failed,
    )

    db["trades"][trade_id] = asdict(trade)
    _recalc_stats(db)
    _save_db(db)

    print(f"💾 سیگنال ذخیره شد: {trade_id}")
    return trade_id


# ─────────────────────────────────────────
# آپدیت وضعیت معامله (بررسی TP/SL)
# ─────────────────────────────────────────

def update_trade(trade_id: str, current_price: float) -> Optional[str]:
    """
    قیمت فعلی رو چک کن و اگه TP یا SL خورد ثبت کن

    Returns: "TP1" | "TP2" | "TP3" | "SL" | None
    """
    db = _load_db()

    if trade_id not in db["trades"]:
        return None

    t = db["trades"][trade_id]

    if t["status"] != "OPEN":
        return None

    direction = t["direction"]
    entry     = t["entry"]
    sl        = t["stop_loss"]
    tp1       = t["tp1"]
    tp2       = t["tp2"]
    tp3       = t["tp3"]
    risk      = abs(entry - sl)

    hit = None

    if direction == "LONG":
        if current_price <= sl:
            hit = "SL"
            t["hit_sl"]  = True
            t["pnl_r"]   = -1.0
        else:
            # اگه قیمت مستقیم از TP1 رد شده و به TP2 یا TP3 رسیده، همه رو mark کن
            if not t["hit_tp1"] and current_price >= tp1:
                t["hit_tp1"] = True
                t["pnl_r"]   = 1.5
                t["status"]  = "TP1"
                hit = "TP1"
            if not t["hit_tp2"] and current_price >= tp2:
                t["hit_tp2"] = True
                t["pnl_r"]   = 2.5
                t["status"]  = "TP2"
                hit = "TP2"
            if not t["hit_tp3"] and current_price >= tp3:
                t["hit_tp3"] = True
                t["pnl_r"]   = 4.0
                t["status"]  = "TP3"
                hit = "TP3"

    elif direction == "SHORT":
        if current_price >= sl:
            hit = "SL"
            t["hit_sl"]  = True
            t["pnl_r"]   = -1.0
        else:
            if not t["hit_tp1"] and current_price <= tp1:
                t["hit_tp1"] = True
                t["pnl_r"]   = 1.5
                t["status"]  = "TP1"
                hit = "TP1"
            if not t["hit_tp2"] and current_price <= tp2:
                t["hit_tp2"] = True
                t["pnl_r"]   = 2.5
                t["status"]  = "TP2"
                hit = "TP2"
            if not t["hit_tp3"] and current_price <= tp3:
                t["hit_tp3"] = True
                t["pnl_r"]   = 4.0
                t["status"]  = "TP3"
                hit = "TP3"

    if hit in ["SL"]:
        t["status"]     = "SL"
        t["closed_at"]  = datetime.utcnow().isoformat()
        t["exit_price"] = current_price

    if hit in ["TP3"]:
        t["closed_at"]  = datetime.utcnow().isoformat()
        t["exit_price"] = current_price

    db["trades"][trade_id] = t
    _recalc_stats(db)
    _save_db(db)

    return hit


def expire_old_trades(max_hours: int = 48):
    """
    معاملات بیشتر از X ساعت باز رو expired کن
    """
    db = _load_db()
    now = datetime.utcnow()

    for tid, t in db["trades"].items():
        if t["status"] != "OPEN":
            continue
        opened = datetime.fromisoformat(t["opened_at"])
        diff_h = (now - opened).total_seconds() / 3600
        if diff_h > max_hours:
            t["status"]    = "EXPIRED"
            t["closed_at"] = now.isoformat()

    _recalc_stats(db)
    _save_db(db)


# ─────────────────────────────────────────
# محاسبه آمار و وین‌ریت
# ─────────────────────────────────────────

def _recalc_stats(db: dict):
    trades = list(db["trades"].values())
    closed = [t for t in trades if t["status"] not in ("OPEN",)]

    total    = len(trades)
    open_c   = len([t for t in trades if t["status"] == "OPEN"])
    tp1_hit  = len([t for t in closed if t["hit_tp1"]])
    tp2_hit  = len([t for t in closed if t["hit_tp2"]])
    tp3_hit  = len([t for t in closed if t["hit_tp3"]])
    sl_hit   = len([t for t in closed if t["hit_sl"]])
    expired  = len([t for t in closed if t["status"] == "EXPIRED"])

    finished = len(closed) - expired  # معاملات واقعی بسته شده

    winrate_tp1 = round(tp1_hit / finished * 100, 1) if finished > 0 else 0.0
    winrate_tp2 = round(tp2_hit / finished * 100, 1) if finished > 0 else 0.0

    pnls    = [t["pnl_r"] for t in closed if t["pnl_r"] != 0]
    avg_rr  = round(sum(pnls) / len(pnls), 2) if pnls else 0.0

    # آمار بر اساس نماد
    by_symbol = {}
    for t in trades:
        sym = t["symbol"]
        if sym not in by_symbol:
            by_symbol[sym] = {"total": 0, "tp1": 0, "tp2": 0, "sl": 0, "winrate": 0.0}
        by_symbol[sym]["total"] += 1
        if t["hit_tp1"]: by_symbol[sym]["tp1"] += 1
        if t["hit_tp2"]: by_symbol[sym]["tp2"] += 1
        if t["hit_sl"]:  by_symbol[sym]["sl"]  += 1

    for sym in by_symbol:
        done = by_symbol[sym]["tp1"] + by_symbol[sym]["sl"]
        by_symbol[sym]["winrate"] = round(
            by_symbol[sym]["tp1"] / done * 100, 1
        ) if done > 0 else 0.0

    # آمار بر اساس جهت
    longs  = [t for t in trades if t["direction"] == "LONG"]
    shorts = [t for t in trades if t["direction"] == "SHORT"]
    long_wins  = len([t for t in longs  if t["hit_tp1"]])
    short_wins = len([t for t in shorts if t["hit_tp1"]])

    db["stats"] = {
        "total":         total,
        "open":          open_c,
        "closed":        len(closed),
        "tp1_hit":       tp1_hit,
        "tp2_hit":       tp2_hit,
        "tp3_hit":       tp3_hit,
        "sl_hit":        sl_hit,
        "expired":       expired,
        "winrate_tp1":   winrate_tp1,
        "winrate_tp2":   winrate_tp2,
        "avg_rr":        avg_rr,
        "by_symbol":     by_symbol,
        "by_direction":  {
            "LONG":  {"total": len(longs),  "wins": long_wins},
            "SHORT": {"total": len(shorts), "wins": short_wins},
        },
        "by_confidence": {
            conf: len([t for t in trades if t["confidence"] == conf])
            for conf in ["HIGH", "MEDIUM", "LOW"]
        },
    }


# ─────────────────────────────────────────
# گزارش وین‌ریت
# ─────────────────────────────────────────

def get_winrate_report() -> str:
    """
    گزارش کامل وین‌ریت برای تلگرام
    """
    db    = _load_db()
    stats = db.get("stats", _empty_stats())

    lines = [
        "📊 *گزارش وین‌ریت سبک امیر*",
        "─────────────────────────",
        f"📈 کل سیگنال‌ها:   `{stats['total']}`",
        f"🟢 باز:            `{stats['open']}`",
        f"🔒 بسته:           `{stats['closed']}`",
        "",
        f"✅ TP1 زده:        `{stats['tp1_hit']}`",
        f"✅✅ TP2 زده:      `{stats['tp2_hit']}`",
        f"✅✅✅ TP3 زده:    `{stats['tp3_hit']}`",
        f"❌ SL زده:         `{stats['sl_hit']}`",
        f"⏳ منقضی:          `{stats['expired']}`",
        "",
        f"🎯 وین‌ریت TP1:    `{stats['winrate_tp1']}%`",
        f"🎯 وین‌ریت TP2:    `{stats['winrate_tp2']}%`",
        f"💹 میانگین R/R:   `{stats['avg_rr']}R`",
        "",
        "📌 *بر اساس نماد:*",
    ]

    for sym, s in stats.get("by_symbol", {}).items():
        lines.append(
            f"  {sym}: {s['total']} معامله | "
            f"TP1: {s['tp1']} | SL: {s['sl']} | "
            f"وین‌ریت: {s['winrate']}%"
        )

    lines += [
        "",
        "📌 *بر اساس جهت:*",
    ]
    for direction, s in stats.get("by_direction", {}).items():
        wr = round(s["wins"] / s["total"] * 100, 1) if s["total"] > 0 else 0
        lines.append(f"  {direction}: {s['total']} معامله | وین: {s['wins']} | {wr}%")

    return "\n".join(lines)


def get_open_trades() -> list:
    """لیست معاملات باز"""
    db = _load_db()
    return [t for t in db["trades"].values() if t["status"] == "OPEN"]


def get_trade_by_id(trade_id: str) -> dict | None:
    """دریافت یک معامله با ID — همیشه آخرین state از DB"""
    db = _load_db()
    return db["trades"].get(trade_id)


def get_stats() -> dict:
    db = _load_db()
    return db.get("stats", _empty_stats())


# ─────────────────────────────────────────
# تست
# ─────────────────────────────────────────

if __name__ == "__main__":
    from signals.amir_strategy import Signal

    # سیگنال مصنوعی
    class FakeSig:
        symbol = "BTCUSDT"; direction = "LONG"; timeframe = "15m/5m"
        score = 8; confidence = "HIGH"; entry = 65000.0
        stop_loss = 64000.0; tp1 = 66500.0; tp2 = 67500.0; tp3 = 69000.0; rr = 2.5
        reasons = ["✅ روند صعودی", "✅ VWAP", "✅ OB"]; failed = ["❌ BOS"]

    tid = save_signal(FakeSig())
    print(f"\n📋 Trade ID: {tid}")

    # شبیه‌سازی TP1
    hit = update_trade(tid, 66600.0)
    print(f"🎯 نتیجه چک اول: {hit}")

    # شبیه‌سازی TP2
    hit = update_trade(tid, 67600.0)
    print(f"🎯 نتیجه چک دوم: {hit}")

    # سیگنال دوم با SL
    class FakeSig2:
        symbol = "ETHUSDT"; direction = "SHORT"; timeframe = "15m/5m"
        score = 7; confidence = "MEDIUM"; entry = 3500.0
        stop_loss = 3560.0; tp1 = 3410.0; tp2 = 3350.0; tp3 = 3260.0; rr = 2.3
        reasons = ["✅ نزولی", "✅ زیر VWAP"]; failed = ["❌ BOS"]

    tid2 = save_signal(FakeSig2())
    hit2 = update_trade(tid2, 3570.0)  # SL خورد
    print(f"🎯 نتیجه SL: {hit2}")

    print("\n" + "=" * 55)
    print(get_winrate_report())
    print("=" * 55)
    print("✅ Tracker OK")
