"""
Hyperliquid API Client
Funding Rate + Open Interest + Liquidation Data
"""

import requests
import json
from typing import Optional

API_URL = "https://api.hyperliquid.xyz/info"

# نقشه نام ارزها: Bitunix → Hyperliquid
SYMBOL_MAP = {
    "BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL",
    "BNBUSDT": "BNB", "XRPUSDT": "XRP", "DOGEUSDT": "DOGE",
    "ADAUSDT": "ADA", "AVAXUSDT": "AVAX", "LINKUSDT": "LINK",
    "ATOMUSDT": "ATOM", "SUIUSDT": "SUI", "ARBUSDT": "ARB",
    "OPUSDT": "OP", "INJUSDT": "INJ", "NEARUSDT": "NEAR",
    "TONUSDT": "TON", "SEIUSDT": "SEI",
}


def _post(payload: dict) -> Optional[dict]:
    try:
        r = requests.post(API_URL, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Hyperliquid API error: {e}")
        return None


def get_market_data() -> Optional[dict]:
    """دریافت Funding Rate و Open Interest همه ارزها"""
    data = _post({"type": "metaAndAssetCtxs"})
    if not data:
        return None

    meta = data[0]["universe"]
    ctxs = data[1]

    result = {}
    for m, c in zip(meta, ctxs):
        name = m["name"]
        result[name] = {
            "funding_rate": float(c.get("funding", 0)),
            "open_interest": float(c.get("openInterest", 0)),
            "mark_price": float(c.get("markPx", 0)),
            "volume_24h": float(c.get("dayNtlVlm", 0)),
            "premium": float(c.get("premium", 0)) if c.get("premium") else 0,
        }
    return result


def get_funding_signal(symbol: str) -> dict:
    """
    تحلیل Funding Rate برای یک ارز

    Returns:
        {
            "funding_rate":  float,
            "funding_pct":   float,  ← درصد
            "bias":          "long_squeeze" | "short_squeeze" | "neutral",
            "oi":            float,
            "oi_signal":     "high" | "normal" | "low",
            "score_adj":     float,  ← تنظیم نمره (+ یا -)
            "reason":        str,
        }
    """
    hl_name = SYMBOL_MAP.get(symbol)
    if not hl_name:
        return {"funding_rate": 0, "bias": "neutral", "score_adj": 0, "reason": "ارز در Hyperliquid نیست"}

    data = get_market_data()
    if not data or hl_name not in data:
        return {"funding_rate": 0, "bias": "neutral", "score_adj": 0, "reason": "خطا در دریافت"}

    info = data[hl_name]
    fr = info["funding_rate"]
    fr_pct = fr * 100
    oi = info["open_interest"]

    # ── تفسیر Funding Rate ──
    # فاندینگ مثبت بالا = لانگ‌ها زیادن = ریسک لانگ اسکوییز → شورت بهتر
    # فاندینگ منفی پایین = شورت‌ها زیادن = ریسک شورت اسکوییز → لانگ بهتر
    if fr > 0.01:
        bias = "long_squeeze"
        score_adj = -0.5
        reason = f"⚠️ فاندینگ بالا ({fr_pct:+.3f}%) — ریسک لانگ اسکوییز"
    elif fr > 0.005:
        bias = "long_heavy"
        score_adj = -0.2
        reason = f"⚠️ فاندینگ مثبت ({fr_pct:+.3f}%) — لانگ‌ها سنگین"
    elif fr < -0.01:
        bias = "short_squeeze"
        score_adj = -0.5
        reason = f"⚠️ فاندینگ منفی ({fr_pct:+.3f}%) — ریسک شورت اسکوییز"
    elif fr < -0.005:
        bias = "short_heavy"
        score_adj = -0.2
        reason = f"⚠️ فاندینگ منفی ({fr_pct:+.3f}%) — شورت‌ها سنگین"
    else:
        bias = "neutral"
        score_adj = 0.3
        reason = f"✅ فاندینگ متعادل ({fr_pct:+.3f}%)"

    return {
        "funding_rate": fr,
        "funding_pct": round(fr_pct, 4),
        "bias": bias,
        "oi": oi,
        "mark_price": info["mark_price"],
        "volume_24h": info["volume_24h"],
        "score_adj": score_adj,
        "reason": reason,
    }


def get_funding_direction_score(symbol: str, direction: str) -> tuple:
    """
    چک می‌کنه آیا فاندینگ با جهت سیگنال هم‌خوانی داره

    Returns: (score_adjustment, reason_text)
    """
    sig = get_funding_signal(symbol)
    fr = sig["funding_rate"]
    is_long = direction == "LONG"

    if is_long:
        if fr > 0.01:
            return -1.0, f"⛔ Funding بالا ({sig['funding_pct']:+.3f}%) ضد LONG"
        elif fr > 0.005:
            return -0.3, f"⚠️ Funding مثبت ({sig['funding_pct']:+.3f}%)"
        elif fr < -0.005:
            return 0.5, f"✅ Funding منفی ({sig['funding_pct']:+.3f}%) — LONG تأیید"
        else:
            return 0.2, f"✅ Funding متعادل"
    else:
        if fr < -0.01:
            return -1.0, f"⛔ Funding پایین ({sig['funding_pct']:+.3f}%) ضد SHORT"
        elif fr < -0.005:
            return -0.3, f"⚠️ Funding منفی ({sig['funding_pct']:+.3f}%)"
        elif fr > 0.005:
            return 0.5, f"✅ Funding مثبت ({sig['funding_pct']:+.3f}%) — SHORT تأیید"
        else:
            return 0.2, f"✅ Funding متعادل"


if __name__ == "__main__":
    print("Testing Hyperliquid API...")
    data = get_market_data()
    if data:
        for sym in ["BTC", "ETH", "SOL", "BNB", "XRP"]:
            if sym in data:
                d = data[sym]
                print(f"  {sym:5s} | FR: {d['funding_rate']*100:+.4f}% | OI: ${d['open_interest']:,.0f}")
        print("\nFunding signals:")
        for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
            sig = get_funding_signal(symbol)
            print(f"  {symbol}: {sig['reason']}")
    else:
        print("API not available")
