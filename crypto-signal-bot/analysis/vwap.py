"""
VWAP - Volume Weighted Average Price
سبک امیر: Anchor = Session | Source = hlc3
"""

import pandas as pd
import numpy as np


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """
    محاسبه VWAP بر اساس Session
    هر روز VWAP از صفر شروع می‌کنه (مثل TradingView)

    Source: hlc3 = (high + low + close) / 3
    """
    df = df.copy()
    df["hlc3"] = (df["high"] + df["low"] + df["close"]) / 3
    df["date"] = df["time"].dt.date

    # برای هر session (روز) VWAP جداگانه حساب می‌کنیم
    df["cum_vol"]    = df.groupby("date")["baseVol"].cumsum()
    df["tp_vol"]     = df["hlc3"] * df["baseVol"]
    df["cum_tp_vol"] = df.groupby("date")["tp_vol"].cumsum()

    df["vwap"] = df["cum_tp_vol"] / df["cum_vol"]

    # VWAP Bands (انحراف معیار)
    df["vwap_dev_sq"] = (df["hlc3"] - df["vwap"]) ** 2 * df["baseVol"]
    df["vwap_var"]    = df.groupby("date")["vwap_dev_sq"].cumsum() / df["cum_vol"]

    df["vwap_std"] = np.sqrt(df["vwap_var"])
    df["vwap_upper1"] = df["vwap"] + df["vwap_std"]
    df["vwap_lower1"] = df["vwap"] - df["vwap_std"]
    df["vwap_upper2"] = df["vwap"] + 2 * df["vwap_std"]
    df["vwap_lower2"] = df["vwap"] - 2 * df["vwap_std"]

    # پاک‌سازی ستون‌های موقت
    df.drop(columns=["hlc3", "date", "cum_vol", "cum_tp_vol", "tp_vol", "vwap_var", "vwap_dev_sq"], inplace=True)

    return df


def vwap_signal(df: pd.DataFrame) -> dict:
    """
    تفسیر VWAP بر اساس سبک امیر

    Returns:
        {
            "vwap":          float,
            "price":         float,
            "above_vwap":    bool,
            "distance_pct":  float,   ← فاصله قیمت از VWAP (درصد)
            "band":          str,     ← قیمت در کدام باند هست
            "bias":          "bullish" | "bearish" | "neutral",
            "cross":         "bullish_cross" | "bearish_cross" | None,
            "signal":        str,
        }
    """
    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = last["close"]
    vwap  = last["vwap"]

    above_vwap = price > vwap
    dist_pct   = round((price - vwap) / vwap * 100, 3)

    # کدوم باند؟
    if price > last["vwap_upper2"]:
        band = "above_band2"
    elif price > last["vwap_upper1"]:
        band = "above_band1"
    elif price > vwap:
        band = "above_vwap"
    elif price > last["vwap_lower1"]:
        band = "below_vwap"
    elif price > last["vwap_lower2"]:
        band = "below_band1"
    else:
        band = "below_band2"

    # کراس VWAP (تغییر طرف در آخرین کندل)
    cross = None
    if prev["close"] < prev["vwap"] and price > vwap:
        cross = "bullish_cross"
    elif prev["close"] > prev["vwap"] and price < vwap:
        cross = "bearish_cross"

    # بایاس
    if above_vwap:
        bias = "bullish"
        signal = "قیمت بالای VWAP - تمایل لانگ"
    else:
        bias = "bearish"
        signal = "قیمت زیر VWAP - تمایل شورت"

    if cross == "bullish_cross":
        signal = "⚡ کراس صعودی VWAP - تقویت لانگ"
    elif cross == "bearish_cross":
        signal = "⚡ کراس نزولی VWAP - تقویت شورت"

    return {
        "vwap":         round(vwap, 4),
        "price":        round(price, 4),
        "above_vwap":   above_vwap,
        "distance_pct": dist_pct,
        "band":         band,
        "bias":         bias,
        "cross":        cross,
        "signal":       signal,
        "vwap_upper1":  round(last["vwap_upper1"], 4),
        "vwap_lower1":  round(last["vwap_lower1"], 4),
        "vwap_upper2":  round(last["vwap_upper2"], 4),
        "vwap_lower2":  round(last["vwap_lower2"], 4),
    }


def compute_vwap(df: pd.DataFrame) -> tuple:
    """تابع اصلی - df رو می‌گیره، VWAP اضافه می‌کنه و خلاصه برمی‌گردونه"""
    df = add_vwap(df)
    summary = vwap_signal(df)
    return df, summary


# ─────────────────────────────────────────
# تست
# ─────────────────────────────────────────

if __name__ == "__main__":
    import numpy as np

    np.random.seed(42)
    n = 300

    # شبیه‌سازی چند روز داده 15 دقیقه‌ای
    times  = pd.date_range("2024-01-01 00:00", periods=n, freq="15min")
    price  = 60000 + np.cumsum(np.random.randn(n) * 120)
    volume = np.abs(np.random.randn(n) * 800 + 4000)

    df = pd.DataFrame({
        "time":     times,
        "open":     price - np.random.rand(n) * 60,
        "high":     price + np.random.rand(n) * 100,
        "low":      price - np.random.rand(n) * 100,
        "close":    price,
        "baseVol":  volume,
        "quoteVol": volume * price,
    })

    df, summary = compute_vwap(df)

    print("=" * 50)
    print(f"💰 قیمت:     {summary['price']}")
    print(f"📏 VWAP:     {summary['vwap']}")
    print(f"📐 فاصله:    {summary['distance_pct']}%")
    print(f"🎯 باند:     {summary['band']}")
    print(f"🧭 بایاس:    {summary['bias']}")
    print(f"⚡ کراس:     {summary['cross']}")
    print(f"📢 سیگنال:   {summary['signal']}")
    print(f"\nBand +1σ:  {summary['vwap_upper1']}")
    print(f"Band -1σ:  {summary['vwap_lower1']}")
    print("=" * 50)
    print("✅ VWAP OK")
