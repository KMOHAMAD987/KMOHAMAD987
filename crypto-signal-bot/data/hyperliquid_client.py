"""
Hyperliquid API Client — نسخه کامل
Funding Rate + Open Interest + Liquidation Levels + Volume/OI Analysis
"""

import requests
import json
import os
import time
from typing import Optional

API_URL = "https://api.hyperliquid.xyz/info"

SYMBOL_MAP = {
    "BTCUSDT": "BTC", "ETHUSDT": "ETH", "SOLUSDT": "SOL",
    "BNBUSDT": "BNB", "XRPUSDT": "XRP", "DOGEUSDT": "DOGE",
    "ADAUSDT": "ADA", "AVAXUSDT": "AVAX", "LINKUSDT": "LINK",
    "ATOMUSDT": "ATOM", "SUIUSDT": "SUI", "ARBUSDT": "ARB",
    "OPUSDT": "OP", "INJUSDT": "INJ", "NEARUSDT": "NEAR",
    "TONUSDT": "TON", "SEIUSDT": "SEI",
}

# کش OI برای مقایسه تغییرات
_OI_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oi_cache.json")


def _post(payload):
    try:
        r = requests.post(API_URL, json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Hyperliquid API error: {e}")
        return None


def _load_oi_cache():
    if not os.path.exists(_OI_CACHE_FILE):
        return {}
    try:
        with open(_OI_CACHE_FILE) as f:
            return json.load(f)
    except:
        return {}


def _save_oi_cache(cache):
    with open(_OI_CACHE_FILE, "w") as f:
        json.dump(cache, f)


# ─────────────────────────────────────────
# دریافت داده بازار
# ─────────────────────────────────────────

def get_market_data():
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
            "prev_day_px": float(c.get("prevDayPx", 0)) if c.get("prevDayPx") else 0,
        }
    return result


def get_user_positions(user_address):
    """دریافت پوزیشن‌های یک آدرس (برای تحلیل نهنگ‌ها)"""
    data = _post({"type": "clearinghouseState", "user": user_address})
    return data


# ─────────────────────────────────────────
# ۱. Funding Rate Analysis
# ─────────────────────────────────────────

def get_funding_signal(symbol):
    hl_name = SYMBOL_MAP.get(symbol)
    if not hl_name:
        return {"funding_rate": 0, "bias": "neutral", "score_adj": 0, "reason": "ارز در Hyperliquid نیست"}

    data = get_market_data()
    if not data or hl_name not in data:
        return {"funding_rate": 0, "bias": "neutral", "score_adj": 0, "reason": "خطا در دریافت"}

    info = data[hl_name]
    fr = info["funding_rate"]
    fr_pct = fr * 100

    if fr > 0.01:
        bias = "long_squeeze"
        score_adj = -0.5
        reason = "⚠️ فاندینگ بالا ({:+.3f}%) — ریسک لانگ اسکوییز".format(fr_pct)
    elif fr > 0.005:
        bias = "long_heavy"
        score_adj = -0.2
        reason = "⚠️ فاندینگ مثبت ({:+.3f}%) — لانگ‌ها سنگین".format(fr_pct)
    elif fr < -0.01:
        bias = "short_squeeze"
        score_adj = -0.5
        reason = "⚠️ فاندینگ منفی ({:+.3f}%) — ریسک شورت اسکوییز".format(fr_pct)
    elif fr < -0.005:
        bias = "short_heavy"
        score_adj = -0.2
        reason = "⚠️ فاندینگ منفی ({:+.3f}%) — شورت‌ها سنگین".format(fr_pct)
    else:
        bias = "neutral"
        score_adj = 0.3
        reason = "✅ فاندینگ متعادل ({:+.3f}%)".format(fr_pct)

    return {
        "funding_rate": fr,
        "funding_pct": round(fr_pct, 4),
        "bias": bias,
        "oi": info["open_interest"],
        "mark_price": info["mark_price"],
        "volume_24h": info["volume_24h"],
        "score_adj": score_adj,
        "reason": reason,
    }


def get_funding_direction_score(symbol, direction):
    sig = get_funding_signal(symbol)
    fr = sig["funding_rate"]
    is_long = direction == "LONG"

    if is_long:
        if fr > 0.01:
            return -1.0, "⛔ Funding بالا ({:+.3f}%) ضد LONG".format(sig['funding_pct'])
        elif fr > 0.005:
            return -0.3, "⚠️ Funding مثبت ({:+.3f}%)".format(sig['funding_pct'])
        elif fr < -0.005:
            return 0.5, "✅ Funding منفی ({:+.3f}%) — LONG تأیید".format(sig['funding_pct'])
        else:
            return 0.2, "✅ Funding متعادل"
    else:
        if fr < -0.01:
            return -1.0, "⛔ Funding پایین ({:+.3f}%) ضد SHORT".format(sig['funding_pct'])
        elif fr < -0.005:
            return -0.3, "⚠️ Funding منفی ({:+.3f}%)".format(sig['funding_pct'])
        elif fr > 0.005:
            return 0.5, "✅ Funding مثبت ({:+.3f}%) — SHORT تأیید".format(sig['funding_pct'])
        else:
            return 0.2, "✅ Funding متعادل"


# ─────────────────────────────────────────
# ۲. Open Interest Analysis
# ─────────────────────────────────────────

def get_oi_analysis(symbol):
    """
    تحلیل تغییرات Open Interest
    OI بالا رفتن + قیمت بالا = روند قوی صعودی
    OI بالا رفتن + قیمت پایین = روند قوی نزولی
    OI پایین اومدن + قیمت بالا = شورت اسکوییز (ضعیف)
    OI پایین اومدن + قیمت پایین = لانگ اسکوییز (ضعیف)
    """
    hl_name = SYMBOL_MAP.get(symbol)
    if not hl_name:
        return {"score_adj": 0, "reason": "ارز ندارد", "oi_change_pct": 0, "signal": "neutral"}

    data = get_market_data()
    if not data or hl_name not in data:
        return {"score_adj": 0, "reason": "خطا", "oi_change_pct": 0, "signal": "neutral"}

    info = data[hl_name]
    current_oi = info["open_interest"]
    mark_price = info["mark_price"]

    cache = _load_oi_cache()
    prev = cache.get(hl_name, {})
    prev_oi = prev.get("oi", current_oi)
    prev_price = prev.get("price", mark_price)
    prev_time = prev.get("time", 0)

    # ذخیره OI فعلی
    cache[hl_name] = {"oi": current_oi, "price": mark_price, "time": time.time()}
    _save_oi_cache(cache)

    # محاسبه تغییرات
    if prev_oi == 0:
        oi_change_pct = 0
    else:
        oi_change_pct = ((current_oi - prev_oi) / prev_oi) * 100

    if prev_price == 0:
        price_change_pct = 0
    else:
        price_change_pct = ((mark_price - prev_price) / prev_price) * 100

    oi_rising = oi_change_pct > 1.0
    oi_falling = oi_change_pct < -1.0
    price_up = price_change_pct > 0.1
    price_down = price_change_pct < -0.1

    # اگه داده قبلی نداریم (اولین بار)
    time_diff = time.time() - prev_time
    if prev_time == 0 or time_diff > 7200:
        return {
            "score_adj": 0,
            "reason": "📊 OI: ${:,.0f} (بدون مقایسه)".format(current_oi),
            "oi_change_pct": 0,
            "oi_value": current_oi,
            "signal": "no_data",
        }

    if oi_rising and price_up:
        signal = "strong_bullish"
        score_adj = 0.8
        reason = "✅ OI افزایشی + قیمت بالا ({:+.1f}%) — روند صعودی قوی".format(oi_change_pct)
    elif oi_rising and price_down:
        signal = "strong_bearish"
        score_adj = 0.8
        reason = "✅ OI افزایشی + قیمت پایین ({:+.1f}%) — روند نزولی قوی".format(oi_change_pct)
    elif oi_falling and price_up:
        signal = "short_squeeze"
        score_adj = 0.3
        reason = "⚠️ OI کاهشی + قیمت بالا ({:+.1f}%) — شورت اسکوییز".format(oi_change_pct)
    elif oi_falling and price_down:
        signal = "long_squeeze"
        score_adj = 0.3
        reason = "⚠️ OI کاهشی + قیمت پایین ({:+.1f}%) — لانگ اسکوییز".format(oi_change_pct)
    elif abs(oi_change_pct) > 5:
        signal = "spike"
        score_adj = 0.5
        reason = "🔥 تغییر شدید OI ({:+.1f}%) — حرکت بزرگ در راه".format(oi_change_pct)
    else:
        signal = "neutral"
        score_adj = 0
        reason = "📊 OI ثابت ({:+.1f}%)".format(oi_change_pct)

    return {
        "score_adj": score_adj,
        "reason": reason,
        "oi_change_pct": round(oi_change_pct, 2),
        "oi_value": current_oi,
        "price_change_pct": round(price_change_pct, 2),
        "signal": signal,
    }


def get_oi_direction_score(symbol, direction):
    """امتیاز OI بر اساس جهت سیگنال"""
    oi = get_oi_analysis(symbol)
    sig = oi["signal"]
    is_long = direction == "LONG"

    if sig == "no_data":
        return 0, oi["reason"]

    if sig == "strong_bullish":
        if is_long:
            return 0.8, oi["reason"]
        else:
            return -0.5, "⚠️ OI صعودی — ضد SHORT"
    elif sig == "strong_bearish":
        if not is_long:
            return 0.8, oi["reason"]
        else:
            return -0.5, "⚠️ OI نزولی — ضد LONG"
    elif sig == "short_squeeze":
        if is_long:
            return 0.5, oi["reason"]
        else:
            return -0.8, "⛔ شورت اسکوییز — SHORT خطرناک"
    elif sig == "long_squeeze":
        if not is_long:
            return 0.5, oi["reason"]
        else:
            return -0.8, "⛔ لانگ اسکوییز — LONG خطرناک"
    elif sig == "spike":
        return 0.3, oi["reason"]
    else:
        return 0, oi["reason"]


# ─────────────────────────────────────────
# ۳. Liquidation Magnet Analysis
# ─────────────────────────────────────────

def get_liquidation_levels(symbol):
    """
    تخمین سطوح لیکوییدیشن بر اساس OI و Funding
    وقتی لیکوییدیشن زیادی در یک سطح جمع شده = مگنت قیمت
    """
    hl_name = SYMBOL_MAP.get(symbol)
    if not hl_name:
        return {"score_adj": 0, "reason": "ارز ندارد", "levels": []}

    data = get_market_data()
    if not data or hl_name not in data:
        return {"score_adj": 0, "reason": "خطا", "levels": []}

    info = data[hl_name]
    price = info["mark_price"]
    oi = info["open_interest"]
    fr = info["funding_rate"]

    if price == 0:
        return {"score_adj": 0, "reason": "قیمت صفر", "levels": []}

    # تخمین سطوح لیکوییدیشن بر اساس لوریج‌های رایج
    liq_levels = []
    for lev in [5, 10, 20, 50]:
        liq_long = price * (1 - 1.0 / lev)
        liq_short = price * (1 + 1.0 / lev)
        liq_levels.append({
            "leverage": lev,
            "long_liq": round(liq_long, 2),
            "short_liq": round(liq_short, 2),
        })

    # فاندینگ بالا = لانگ‌های زیاد = لیکوییدیشن لانگ نزدیک‌تره
    # فاندینگ پایین = شورت‌های زیاد = لیکوییدیشن شورت نزدیک‌تره
    if fr > 0.005:
        dominant_side = "long"
        liq_target = price * 0.95  # لیک لانگ‌ها ~5% پایین
        magnet_dir = "down"
        reason = "🧲 لیکوییدیشن لانگ‌ها زیر ${:,.0f} — مگنت نزولی".format(liq_target)
        score_adj = 0.3
    elif fr < -0.005:
        dominant_side = "short"
        liq_target = price * 1.05  # لیک شورت‌ها ~5% بالا
        magnet_dir = "up"
        reason = "🧲 لیکوییدیشن شورت‌ها بالای ${:,.0f} — مگنت صعودی".format(liq_target)
        score_adj = 0.3
    else:
        dominant_side = "balanced"
        liq_target = 0
        magnet_dir = "none"
        reason = "📊 لیکوییدیشن متعادل"
        score_adj = 0

    return {
        "score_adj": score_adj,
        "reason": reason,
        "levels": liq_levels,
        "dominant_side": dominant_side,
        "magnet_dir": magnet_dir,
        "liq_target": liq_target,
    }


def get_liquidation_direction_score(symbol, direction):
    """امتیاز لیکوییدیشن بر اساس جهت"""
    liq = get_liquidation_levels(symbol)
    magnet = liq["magnet_dir"]
    is_long = direction == "LONG"

    if magnet == "none":
        return 0, liq["reason"]

    if magnet == "up" and is_long:
        return 0.5, "✅ " + liq["reason"] + " — هم‌جهت LONG"
    elif magnet == "down" and not is_long:
        return 0.5, "✅ " + liq["reason"] + " — هم‌جهت SHORT"
    elif magnet == "up" and not is_long:
        return -0.5, "⚠️ مگنت صعودی — ضد SHORT"
    elif magnet == "down" and is_long:
        return -0.5, "⚠️ مگنت نزولی — ضد LONG"
    else:
        return 0, liq["reason"]


# ─────────────────────────────────────────
# ۴. Volume + OI Combo
# ─────────────────────────────────────────

def get_volume_oi_combo(symbol):
    """
    حجم ۲۴ ساعته + OI ترکیبی
    حجم بالا + OI بالا = روند قوی (تأیید)
    حجم بالا + OI پایین = فیک‌آوت احتمالی
    حجم پایین + OI بالا = فشرده‌سازی (حرکت بزرگ نزدیک)
    حجم پایین + OI پایین = بازار مرده
    """
    hl_name = SYMBOL_MAP.get(symbol)
    if not hl_name:
        return {"score_adj": 0, "reason": "ارز ندارد", "signal": "neutral"}

    data = get_market_data()
    if not data or hl_name not in data:
        return {"score_adj": 0, "reason": "خطا", "signal": "neutral"}

    info = data[hl_name]
    vol = info["volume_24h"]
    oi = info["open_interest"]
    price = info["mark_price"]

    if price == 0 or oi == 0:
        return {"score_adj": 0, "reason": "داده ناقص", "signal": "neutral"}

    # نسبت حجم به OI — بالای ۲ یعنی حجم خیلی بالاست
    vol_oi_ratio = vol / oi if oi > 0 else 0

    # OI نسبت به مارکت‌کپ تخمینی
    oi_intensity = oi / (price * 1000000) if price > 0 else 0

    if vol_oi_ratio > 3.0:
        signal = "high_vol_high_oi"
        score_adj = 0.7
        reason = "🔥 حجم خیلی بالا (Vol/OI: {:.1f}) — روند قوی".format(vol_oi_ratio)
    elif vol_oi_ratio > 1.5:
        signal = "active_market"
        score_adj = 0.4
        reason = "✅ بازار فعال (Vol/OI: {:.1f})".format(vol_oi_ratio)
    elif vol_oi_ratio > 0.5:
        signal = "normal"
        score_adj = 0.1
        reason = "📊 بازار عادی (Vol/OI: {:.1f})".format(vol_oi_ratio)
    elif vol_oi_ratio > 0.2:
        signal = "compression"
        score_adj = 0.3
        reason = "🔸 فشرده‌سازی (Vol/OI: {:.1f}) — حرکت بزرگ نزدیک".format(vol_oi_ratio)
    else:
        signal = "dead"
        score_adj = -0.5
        reason = "❌ بازار مرده (Vol/OI: {:.1f}) — ورود ممنوع".format(vol_oi_ratio)

    return {
        "score_adj": score_adj,
        "reason": reason,
        "signal": signal,
        "vol_oi_ratio": round(vol_oi_ratio, 2),
        "volume_24h": vol,
        "open_interest": oi,
        "oi_intensity": round(oi_intensity, 4),
    }


# ─────────────────────────────────────────
# ۵. تحلیل کامل Hyperliquid
# ─────────────────────────────────────────

def get_full_hl_analysis(symbol, direction):
    """
    تحلیل کامل Hyperliquid — ترکیب همه فاکتورها
    Returns: (total_score_adj, reasons_list, details_dict)
    """
    total_adj = 0.0
    reasons = []
    details = {}

    # ۱. Funding Rate
    try:
        fr_adj, fr_reason = get_funding_direction_score(symbol, direction)
        total_adj += fr_adj
        reasons.append(fr_reason)
        details["funding"] = {"adj": fr_adj, "reason": fr_reason}
    except:
        details["funding"] = {"adj": 0, "reason": "خطا"}

    # ۲. OI Changes
    try:
        oi_adj, oi_reason = get_oi_direction_score(symbol, direction)
        total_adj += oi_adj
        reasons.append(oi_reason)
        details["oi"] = {"adj": oi_adj, "reason": oi_reason}
    except:
        details["oi"] = {"adj": 0, "reason": "خطا"}

    # ۳. Liquidation Magnet
    try:
        liq_adj, liq_reason = get_liquidation_direction_score(symbol, direction)
        total_adj += liq_adj
        reasons.append(liq_reason)
        details["liquidation"] = {"adj": liq_adj, "reason": liq_reason}
    except:
        details["liquidation"] = {"adj": 0, "reason": "خطا"}

    # ۴. Volume + OI Combo
    try:
        combo = get_volume_oi_combo(symbol)
        total_adj += combo["score_adj"]
        reasons.append(combo["reason"])
        details["vol_oi"] = {"adj": combo["score_adj"], "reason": combo["reason"]}
    except:
        details["vol_oi"] = {"adj": 0, "reason": "خطا"}

    # سقف و کف
    total_adj = max(-3.0, min(3.0, total_adj))

    return round(total_adj, 1), reasons, details


if __name__ == "__main__":
    print("Testing Hyperliquid API (Full)...")
    data = get_market_data()
    if data:
        for sym in ["BTC", "ETH", "SOL", "BNB", "XRP"]:
            if sym in data:
                d = data[sym]
                print("  {:5s} | FR: {:+.4f}% | OI: ${:,.0f} | Vol24h: ${:,.0f}".format(
                    sym, d['funding_rate']*100, d['open_interest'], d['volume_24h']))

        print("\nFull analysis:")
        for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
            for direction in ["LONG", "SHORT"]:
                adj, reasons, details = get_full_hl_analysis(symbol, direction)
                print("\n  {} {} | Total adj: {:+.1f}".format(symbol, direction, adj))
                for r in reasons:
                    print("    {}".format(r))
    else:
        print("API not available")
