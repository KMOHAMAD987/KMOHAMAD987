"""
ساختار بازار - سبک امیر
Order Block + FVG + Swing High/Low + Break of Structure
"""

import pandas as pd
import numpy as np


# ─────────────────────────────────────────
# Swing High / Swing Low
# ─────────────────────────────────────────

def find_swings(df: pd.DataFrame, pivot_len: int = 5) -> pd.DataFrame:
    """
    پیدا کردن Swing High و Swing Low

    pivot_len: هر طرف چند کندل چک بشه (مثل TradingView pivot)
    """
    df = df.copy()
    df["swing_high"] = False
    df["swing_low"]  = False

    for i in range(pivot_len, len(df) - pivot_len):
        window_high = df["high"].iloc[i - pivot_len: i + pivot_len + 1]
        window_low  = df["low"].iloc[i - pivot_len: i + pivot_len + 1]

        if df["high"].iloc[i] == window_high.max():
            df.at[df.index[i], "swing_high"] = True
        if df["low"].iloc[i] == window_low.min():
            df.at[df.index[i], "swing_low"] = True

    return df


def get_recent_swings(df: pd.DataFrame, count: int = 3) -> dict:
    """آخرین Swing High و Swing Low ها"""
    highs = df[df["swing_high"]].tail(count)
    lows  = df[df["swing_low"]].tail(count)

    return {
        "swing_highs": [
            {"time": r["time"], "price": round(r["high"], 4)}
            for _, r in highs.iterrows()
        ],
        "swing_lows": [
            {"time": r["time"], "price": round(r["low"], 4)}
            for _, r in lows.iterrows()
        ],
        "last_high": round(highs["high"].iloc[-1], 4) if len(highs) > 0 else None,
        "last_low":  round(lows["low"].iloc[-1], 4)  if len(lows) > 0 else None,
    }


# ─────────────────────────────────────────
# Break of Structure (BOS)
# ─────────────────────────────────────────

def detect_bos(df: pd.DataFrame) -> dict:
    """
    تشخیص Break of Structure

    صعودی: قیمت بالای آخرین Swing High بسته شد
    نزولی: قیمت زیر آخرین Swing Low بسته شد
    """
    swings = get_recent_swings(df, count=5)
    last_price = df["close"].iloc[-1]

    bos_bull = False
    bos_bear = False
    bos_level = None

    if swings["last_high"] and last_price > swings["last_high"]:
        bos_bull  = True
        bos_level = swings["last_high"]

    if swings["last_low"] and last_price < swings["last_low"]:
        bos_bear  = True
        bos_level = swings["last_low"]

    return {
        "bos_bullish": bos_bull,
        "bos_bearish": bos_bear,
        "bos_level":   bos_level,
        "last_high":   swings["last_high"],
        "last_low":    swings["last_low"],
    }


# ─────────────────────────────────────────
# Order Block
# ─────────────────────────────────────────

def find_order_blocks(df: pd.DataFrame, lookback: int = 50) -> dict:
    """
    پیدا کردن Order Block های معتبر

    Bullish OB: آخرین کندل نزولی قبل از یه حرکت صعودی قوی
    Bearish OB: آخرین کندل صعودی قبل از یه حرکت نزولی قوی

    lookback: چند کندل اخیر رو چک کنیم
    """
    recent = df.tail(lookback).copy().reset_index(drop=True)
    n = len(recent)

    bullish_obs = []
    bearish_obs = []

    for i in range(2, n - 3):
        candle = recent.iloc[i]
        next3  = recent.iloc[i+1: i+4]

        is_bearish_candle = candle["close"] < candle["open"]
        is_bullish_candle = candle["close"] > candle["open"]

        ob_size_pct = (candle["high"] - candle["low"]) / candle["close"] if candle["close"] > 0 else 0

        # Bullish OB: کندل نزولی + بعدش ۳ کندل صعودی قوی + حداقل سایز OB
        if is_bearish_candle and ob_size_pct >= 0.002:
            move_up = (next3["close"] > next3["open"]).sum() >= 2
            strong_move = next3["close"].max() > candle["high"] * 1.002  # حداقل ۰.۲٪ بالاتر
            impulse = (next3["close"].max() - candle["close"]) / candle["close"] >= 0.003
            if move_up and strong_move and impulse:
                bullish_obs.append({
                    "type":   "bullish",
                    "top":    round(candle["open"], 4),
                    "bottom": round(candle["low"], 4),
                    "time":   candle["time"],
                    "mitigated": recent.iloc[i+1:]["low"].min() < candle["low"],
                })

        # Bearish OB: کندل صعودی + بعدش ۳ کندل نزولی قوی + حداقل سایز OB
        if is_bullish_candle and ob_size_pct >= 0.002:
            move_down = (next3["close"] < next3["open"]).sum() >= 2
            strong_move = next3["close"].min() < candle["low"] * 0.998
            impulse = (candle["close"] - next3["close"].min()) / candle["close"] >= 0.003
            if move_down and strong_move and impulse:
                bearish_obs.append({
                    "type":   "bearish",
                    "top":    round(candle["high"], 4),
                    "bottom": round(candle["open"], 4),
                    "time":   candle["time"],
                    "mitigated": recent.iloc[i+1:]["high"].max() > candle["high"],
                })

    # فقط OB های mitigate نشده معتبرن
    valid_bull_obs = [ob for ob in bullish_obs if not ob["mitigated"]]
    valid_bear_obs = [ob for ob in bearish_obs if not ob["mitigated"]]

    # نزدیک‌ترین OB به قیمت فعلی
    price = df["close"].iloc[-1]

    nearest_bull_ob = None
    nearest_bear_ob = None

    if valid_bull_obs:
        # نزدیک‌ترین Bullish OB زیر قیمت
        below = [ob for ob in valid_bull_obs if ob["top"] < price]
        if below:
            nearest_bull_ob = min(below, key=lambda ob: price - ob["top"])

    if valid_bear_obs:
        # نزدیک‌ترین Bearish OB بالای قیمت
        above = [ob for ob in valid_bear_obs if ob["bottom"] > price]
        if above:
            nearest_bear_ob = min(above, key=lambda ob: ob["bottom"] - price)

    return {
        "bullish_obs":      valid_bull_obs[-3:],   # آخرین ۳ تا
        "bearish_obs":      valid_bear_obs[-3:],
        "nearest_bull_ob":  nearest_bull_ob,
        "nearest_bear_ob":  nearest_bear_ob,
        "price_in_bull_ob": nearest_bull_ob is not None and (
            nearest_bull_ob["bottom"] <= price <= nearest_bull_ob["top"]
        ),
        "price_in_bear_ob": nearest_bear_ob is not None and (
            nearest_bear_ob["bottom"] <= price <= nearest_bear_ob["top"]
        ),
    }


# ─────────────────────────────────────────
# Fair Value Gap (FVG)
# ─────────────────────────────────────────

def find_fvg(df: pd.DataFrame, lookback: int = 50) -> dict:
    """
    پیدا کردن Fair Value Gap های پر نشده

    Bullish FVG: low کندل i+2 > high کندل i  (گپ صعودی)
    Bearish FVG: high کندل i+2 < low کندل i  (گپ نزولی)
    """
    recent = df.tail(lookback).copy().reset_index(drop=True)
    n = len(recent)
    price = df["close"].iloc[-1]

    bull_fvgs = []
    bear_fvgs = []

    for i in range(n - 2):
        c1 = recent.iloc[i]
        c3 = recent.iloc[i + 2]

        # Bullish FVG
        if c3["low"] > c1["high"]:
            gap_size = c3["low"] - c1["high"]
            mitigated = recent.iloc[i+2:]["low"].min() <= c1["high"]
            if not mitigated:
                bull_fvgs.append({
                    "type":      "bullish",
                    "top":       round(c3["low"], 4),
                    "bottom":    round(c1["high"], 4),
                    "size":      round(gap_size, 4),
                    "time":      recent.iloc[i+1]["time"],
                    "mitigated": mitigated,
                })

        # Bearish FVG
        if c3["high"] < c1["low"]:
            gap_size = c1["low"] - c3["high"]
            mitigated = recent.iloc[i+2:]["high"].max() >= c1["low"]
            if not mitigated:
                bear_fvgs.append({
                    "type":      "bearish",
                    "top":       round(c1["low"], 4),
                    "bottom":    round(c3["high"], 4),
                    "size":      round(gap_size, 4),
                    "time":      recent.iloc[i+1]["time"],
                    "mitigated": mitigated,
                })

    # نزدیک‌ترین FVG به قیمت
    nearest_bull_fvg = None
    nearest_bear_fvg = None

    if bull_fvgs:
        below = [f for f in bull_fvgs if f["top"] < price]
        if below:
            nearest_bull_fvg = min(below, key=lambda f: price - f["top"])

    if bear_fvgs:
        above = [f for f in bear_fvgs if f["bottom"] > price]
        if above:
            nearest_bear_fvg = min(above, key=lambda f: f["bottom"] - price)

    return {
        "bull_fvgs":          bull_fvgs[-3:],
        "bear_fvgs":          bear_fvgs[-3:],
        "nearest_bull_fvg":   nearest_bull_fvg,
        "nearest_bear_fvg":   nearest_bear_fvg,
        "price_in_bull_fvg":  nearest_bull_fvg is not None and (
            nearest_bull_fvg["bottom"] <= price <= nearest_bull_fvg["top"]
        ),
        "price_in_bear_fvg":  nearest_bear_fvg is not None and (
            nearest_bear_fvg["bottom"] <= price <= nearest_bear_fvg["top"]
        ),
    }


# ─────────────────────────────────────────
# تابع اصلی
# ─────────────────────────────────────────

def compute_structure(df: pd.DataFrame, pivot_len: int = 5) -> tuple[pd.DataFrame, dict]:
    """همه ساختار بازار رو حساب می‌کنه"""
    df = find_swings(df, pivot_len=pivot_len)

    summary = {
        "bos":     detect_bos(df),
        "ob":      find_order_blocks(df),
        "fvg":     find_fvg(df),
        "swings":  get_recent_swings(df),
        "price":   round(df["close"].iloc[-1], 4),
    }

    return df, summary


# ─────────────────────────────────────────
# تست
# ─────────────────────────────────────────

if __name__ == "__main__":
    np.random.seed(7)
    n = 300
    price = 60000 + np.cumsum(np.random.randn(n) * 150)
    volume = np.abs(np.random.randn(n) * 800 + 4000)

    df = pd.DataFrame({
        "time":     pd.date_range("2024-01-01", periods=n, freq="15min"),
        "open":     price - np.random.rand(n) * 80,
        "high":     price + np.random.rand(n) * 120,
        "low":      price - np.random.rand(n) * 120,
        "close":    price,
        "baseVol":  volume,
        "quoteVol": volume * price,
    })

    df, summary = compute_structure(df)

    print("=" * 55)
    print(f"💰 قیمت: {summary['price']}")

    print("\n🔷 BOS:")
    b = summary["bos"]
    print(f"  صعودی: {b['bos_bullish']} | نزولی: {b['bos_bearish']}")
    print(f"  آخرین High: {b['last_high']} | آخرین Low: {b['last_low']}")

    print("\n🟩 Order Blocks:")
    ob = summary["ob"]
    print(f"  Bullish OBs معتبر: {len(ob['bullish_obs'])}")
    print(f"  Bearish OBs معتبر: {len(ob['bearish_obs'])}")
    if ob["nearest_bull_ob"]:
        nob = ob["nearest_bull_ob"]
        print(f"  نزدیک‌ترین Bull OB: {nob['bottom']} - {nob['top']}")
    print(f"  قیمت داخل Bull OB: {ob['price_in_bull_ob']}")

    print("\n🟦 FVG:")
    fvg = summary["fvg"]
    print(f"  Bull FVGها: {len(fvg['bull_fvgs'])} | Bear FVGها: {len(fvg['bear_fvgs'])}")
    if fvg["nearest_bull_fvg"]:
        nf = fvg["nearest_bull_fvg"]
        print(f"  نزدیک‌ترین Bull FVG: {nf['bottom']} - {nf['top']}")

    print("=" * 55)
    print("✅ Structure OK")
