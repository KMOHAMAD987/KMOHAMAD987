"""
اندیکاتورهای تکنیکال سبک امیر
EMA 9 / 21 / 50 / 200 + RSI 14 + Volume Analysis
"""

import pandas as pd
import numpy as np


# ─────────────────────────────────────────
# EMA
# ─────────────────────────────────────────

def add_emas(df: pd.DataFrame) -> pd.DataFrame:
    """
    اضافه کردن EMA 9، 21، 50، 200 به دیتافریم
    """
    for length in [9, 21, 50, 200]:
        df[f"ema_{length}"] = df["close"].ewm(span=length, adjust=False).mean()
    return df


def ema_trend(df: pd.DataFrame) -> dict:
    """
    تشخیص روند بر اساس EMAها

    Returns:
        {
            "trend":        "bullish" | "bearish" | "neutral",
            "above_200":    bool,
            "above_50":     bool,
            "above_21":     bool,
            "above_9":      bool,
            "ema_aligned":  bool,   ← همه EMAها مرتب هستن؟ (9>21>50>200)
            "score":        int,     ← 0 تا 4 (هر EMA یه امتیاز)
        }
    """
    last = df.iloc[-1]
    price = last["close"]

    above_200 = price > last["ema_200"]
    above_50  = price > last["ema_50"]
    above_21  = price > last["ema_21"]
    above_9   = price > last["ema_9"]

    # EMA stack مرتب؟ (صعودی: 9 > 21 > 50 > 200)
    ema_aligned_bull = (
        last["ema_9"] > last["ema_21"] > last["ema_50"] > last["ema_200"]
    )
    ema_aligned_bear = (
        last["ema_9"] < last["ema_21"] < last["ema_50"] < last["ema_200"]
    )

    score = sum([above_200, above_50, above_21, above_9])

    if score >= 3:
        trend = "bullish"
    elif score <= 1:
        trend = "bearish"
    else:
        trend = "neutral"

    return {
        "trend":       trend,
        "above_200":   above_200,
        "above_50":    above_50,
        "above_21":    above_21,
        "above_9":     above_9,
        "ema_aligned": ema_aligned_bull or ema_aligned_bear,
        "ema_aligned_bull": ema_aligned_bull,
        "ema_aligned_bear": ema_aligned_bear,
        "score":       score,
        # مقادیر خام
        "ema_9":   round(last["ema_9"], 4),
        "ema_21":  round(last["ema_21"], 4),
        "ema_50":  round(last["ema_50"], 4),
        "ema_200": round(last["ema_200"], 4),
    }


# ─────────────────────────────────────────
# RSI 14
# ─────────────────────────────────────────

def add_rsi(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    """RSI با روش Wilder (همون TradingView)"""
    delta = df["close"].diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1/length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))
    return df


def rsi_signal(df: pd.DataFrame) -> dict:
    """
    تفسیر RSI بر اساس سبک امیر

    Returns:
        {
            "value":     float,
            "zone":      "oversold" | "bullish" | "neutral" | "bearish" | "overbought",
            "momentum":  "bullish" | "bearish" | "neutral",
            "divergence": None  ← بعداً اضافه می‌کنیم
        }
    """
    rsi = df["rsi"].iloc[-1]
    prev_rsi = df["rsi"].iloc[-2]

    if rsi < 30:
        zone = "oversold"
        momentum = "bullish"   # احتمال برگشت
    elif rsi < 50:
        zone = "bearish"
        momentum = "bearish"
    elif rsi < 70:
        zone = "bullish"
        momentum = "bullish"
    else:
        zone = "overbought"
        momentum = "bearish"   # احتمال پولبک

    return {
        "value":    round(rsi, 2),
        "prev":     round(prev_rsi, 2),
        "zone":     zone,
        "momentum": momentum,
        "rising":   rsi > prev_rsi,
    }


# ─────────────────────────────────────────
# Volume Analysis
# ─────────────────────────────────────────

def add_volume_ma(df: pd.DataFrame, length: int = 20) -> pd.DataFrame:
    """میانگین حجم ۲۰ کندل"""
    df["volume_ma"] = df["baseVol"].rolling(window=length).mean()
    return df


def volume_signal(df: pd.DataFrame) -> dict:
    """
    تحلیل حجم بر اساس سبک امیر

    Returns:
        {
            "current_vol":    float,
            "avg_vol":        float,
            "ratio":          float,   ← current/avg
            "above_average":  bool,
            "strong":         bool,    ← بیش از ۱.۵ برابر میانگین
            "signal":         "strong_buy" | "strong_sell" | "normal" | "weak"
        }
    """
    last     = df.iloc[-1]
    vol      = last["baseVol"]
    avg_vol  = last["volume_ma"]
    ratio    = vol / avg_vol if avg_vol > 0 else 1.0

    # کندل صعودی یا نزولی؟
    is_green = last["close"] > last["open"]

    above_avg = ratio > 1.0
    strong    = ratio > 1.5

    if strong and is_green:
        sig = "strong_buy"
    elif strong and not is_green:
        sig = "strong_sell"
    elif above_avg:
        sig = "normal"
    else:
        sig = "weak"

    return {
        "current_vol":   round(vol, 2),
        "avg_vol":       round(avg_vol, 2),
        "ratio":         round(ratio, 2),
        "above_average": above_avg,
        "strong":        strong,
        "signal":        sig,
    }


# ─────────────────────────────────────────
# تابع اصلی — همه اندیکاتورها با هم
# ─────────────────────────────────────────

def compute_indicators(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    دریافت دیتافریم خام → محاسبه همه اندیکاتورها → برگرداندن df + خلاصه

    Returns:
        df:      دیتافریم با ستون‌های جدید
        summary: دیکشنری خلاصه سیگنال‌ها
    """
    if len(df) < 200:
        raise ValueError(f"حداقل ۲۰۰ کندل لازمه، الان {len(df)} داریم")

    df = add_emas(df)
    df = add_rsi(df)
    df = add_volume_ma(df)

    summary = {
        "ema":    ema_trend(df),
        "rsi":    rsi_signal(df),
        "volume": volume_signal(df),
        "price":  round(df["close"].iloc[-1], 4),
    }

    return df, summary


# ─────────────────────────────────────────
# تست
# ─────────────────────────────────────────

if __name__ == "__main__":
    # تست با داده مصنوعی
    np.random.seed(42)
    n = 250
    price = 60000 + np.cumsum(np.random.randn(n) * 100)
    volume = np.abs(np.random.randn(n) * 1000 + 5000)

    df = pd.DataFrame({
        "time":     pd.date_range("2024-01-01", periods=n, freq="15min"),
        "open":     price - np.random.rand(n) * 50,
        "high":     price + np.random.rand(n) * 80,
        "low":      price - np.random.rand(n) * 80,
        "close":    price,
        "baseVol":  volume,
        "quoteVol": volume * price,
    })

    df, summary = compute_indicators(df)

    print("=" * 50)
    print(f"💰 قیمت: {summary['price']}")
    print()
    print("📈 EMA:")
    e = summary["ema"]
    print(f"  روند: {e['trend']} | امتیاز: {e['score']}/4")
    print(f"  بالای EMA200: {e['above_200']} | بالای EMA50: {e['above_50']}")
    print(f"  EMA Stack مرتب صعودی: {e['ema_aligned_bull']}")
    print()
    print("📊 RSI:")
    r = summary["rsi"]
    print(f"  مقدار: {r['value']} | زون: {r['zone']} | مومنتوم: {r['momentum']}")
    print()
    print("📦 Volume:")
    v = summary["volume"]
    print(f"  نسبت به میانگین: {v['ratio']}x | سیگنال: {v['signal']}")
    print("=" * 50)
    print("✅ اندیکاتورها OK")
