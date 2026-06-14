"""
موتور سیگنال استراتژی Amir — نسخه کامل
قوانین دقیق: BTC اول، نمره ۸+، R:R حداقل ۱:۳، ناحیه OB/Liquidity
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from analysis.indicators import compute_indicators
from analysis.vwap import compute_vwap
from analysis.structure import compute_structure

# ─────────────────────────────────────────
# ارزهای مجاز
# ─────────────────────────────────────────
ALLOWED_SYMBOLS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","DOGEUSDT",
    "XRPUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","ATOMUSDT",
    "ICPUSDT","INJUSDT","ARBUSDT","OPUSDT","TONUSDT",
    "NOTUSDT","SUIUSDT","SEIUSDT","STXUSDT","TAOUSDT",
    "HYPEUSDT","PENDLEUSDT","ONDOUSDT","RENDERUSDT","IMXUSDT",
    "PYTHUSDT","JUPUSDT","ZROUSDT","LDOUSDT","COTIUSDT",
    "TIAUSDT","AXSUSDT","ETCUSDT","XLMUSDT","ZECUSDT",
    "MAGICUSDT","POLUSDT","MEWUSDT","UNIUSDT","NEARUSDT",
    "1000FLOKIUSDT",
]

# حداقل‌ها
MIN_SCORE  = 8.0   # از ۱۰
MIN_RR     = 3.0   # حداقل ۱:۳
MIN_PROB   = 60    # درصد احتمال

@dataclass
class Signal:
    symbol:      str
    direction:   str        # LONG | SHORT | NO_SIGNAL
    timeframe:   str
    price:       float
    score:       float      # از ۱۰
    probability: int        # درصد
    confidence:  str        # HIGH | MEDIUM | LOW | REJECTED

    entry:       float = 0.0
    stop_loss:   float = 0.0
    tp1:         float = 0.0
    tp2:         float = 0.0
    tp3:         float = 0.0
    rr:          float = 0.0
    leverage:    int   = 5

    btc_score:   float = 0.0   # نمره BTC از ۱۰
    btc_bias:    str   = "neutral"

    reasons:     list = field(default_factory=list)
    failed:      list = field(default_factory=list)
    reject_reason: str = ""

    def to_dict(self): return self.__dict__


def _no(symbol, price, reason, failed=None):
    return Signal(
        symbol=symbol, direction="NO_SIGNAL",
        timeframe="–", price=price,
        score=0, probability=0, confidence="REJECTED",
        reject_reason=reason,
        failed=failed or [reason],
    )


def _compute(df):
    df, ind = compute_indicators(df)
    df, vwap = compute_vwap(df)
    df, struct = compute_structure(df)
    return df, {
        "price":   ind["price"],
        "ema":     ind["ema"],
        "rsi":     ind["rsi"],
        "volume":  ind["volume"],
        "vwap":    vwap,
        "bos":     struct["bos"],
        "ob":      struct["ob"],
        "fvg":     struct["fvg"],
        "swings":  struct["swings"],
    }


# ─────────────────────────────────────────
# مرحله ۱: تحلیل BTC
# ─────────────────────────────────────────

def analyze_btc(df_4h, df_1h, df_15m) -> dict:
    """
    تحلیل BTC در سه تایم‌فریم و نمره‌دهی ۱۰
    """
    try:
        _, s4h  = _compute(df_4h)
        _, s1h  = _compute(df_1h)
        _, s15m = _compute(df_15m)
    except Exception as e:
        return {"score": 5.0, "bias": "neutral", "reasons": [f"خطا: {e}"]}

    score   = 0.0
    reasons = []
    price   = s4h["price"]

    # ── روند کلی 4H (2 امتیاز) ──
    if s4h["ema"]["above_200"]:
        score += 1.0
        reasons.append("✅ 4H بالای EMA200")
    else:
        reasons.append("❌ 4H زیر EMA200")

    if s4h["ema"]["trend"] == "bullish":
        score += 1.0
        reasons.append("✅ 4H روند صعودی")
    elif s4h["ema"]["trend"] == "bearish":
        reasons.append("❌ 4H روند نزولی")
    else:
        score += 0.5
        reasons.append("⚠️ 4H روند خنثی")

    # ── ساختار 1H BOS/CHOCH (2 امتیاز) ──
    if s1h["bos"]["bos_bullish"]:
        score += 2.0
        reasons.append("✅ 1H BOS صعودی")
    elif s1h["bos"]["bos_bearish"]:
        reasons.append("❌ 1H BOS نزولی")
    else:
        score += 1.0
        reasons.append("⚠️ 1H ساختار خنثی")

    # ── VWAP (1.5 امتیاز) ──
    if s1h["vwap"]["above_vwap"]:
        score += 1.5
        reasons.append("✅ 1H بالای VWAP")
    else:
        reasons.append("❌ 1H زیر VWAP")

    # ── RSI (1.5 امتیاز) ──
    rsi_4h = s4h["rsi"]["value"]
    if rsi_4h:
        if 50 < rsi_4h < 70:
            score += 1.5
            reasons.append(f"✅ RSI 4H مناسب ({rsi_4h:.0f})")
        elif 30 < rsi_4h <= 50:
            score += 0.5
            reasons.append(f"⚠️ RSI 4H ضعیف ({rsi_4h:.0f})")
        elif rsi_4h >= 70:
            score += 0.5
            reasons.append(f"⚠️ RSI 4H اشباع ({rsi_4h:.0f})")
        else:
            reasons.append(f"❌ RSI 4H خیلی پایین ({rsi_4h:.0f})")

    # ── Order Block 4H (1 امتیاز) ──
    if s4h["ob"]["nearest_bull_ob"] or s4h["fvg"]["nearest_bull_fvg"]:
        score += 1.0
        reasons.append("✅ OB/FVG صعودی در 4H")
    elif s4h["ob"]["nearest_bear_ob"] or s4h["fvg"]["nearest_bear_fvg"]:
        reasons.append("❌ OB/FVG نزولی در 4H")
    else:
        score += 0.5

    # ── حجم 15m (1 امتیاز) ──
    if s15m["volume"]["above_average"]:
        score += 1.0
        reasons.append(f"✅ حجم BTC بالا ({s15m['volume']['ratio']:.1f}x)")
    else:
        reasons.append(f"⚠️ حجم BTC پایین ({s15m['volume']['ratio']:.1f}x)")

    score = min(10.0, score)

    # بایاس
    if score >= 7:   bias = "bullish"
    elif score <= 4: bias = "bearish"
    else:            bias = "neutral"

    return {"score": round(score, 1), "bias": bias, "reasons": reasons, "price": price}


# ─────────────────────────────────────────
# مرحله ۲: تحلیل ارز
# ─────────────────────────────────────────

def _score_coin(s1h, s15m, s5m, btc_bias, direction) -> tuple:
    """
    نمره‌دهی ۱۰ برای یک ارز در جهت مشخص
    """
    score   = 0.0
    reasons = []
    price   = s5m["price"]

    is_long = (direction == "LONG")

    # ── ۱. همسویی با BTC (1.5 امتیاز) ──
    if btc_bias == ("bullish" if is_long else "bearish"):
        score += 1.5
        reasons.append(f"✅ BTC هم‌جهت ({btc_bias})")
    elif btc_bias == "neutral":
        score += 0.7
        reasons.append("⚠️ BTC خنثی")
    else:
        reasons.append(f"❌ BTC مخالف ({btc_bias})")

    # ── ۲. روند 1H (1.5 امتیاز) ──
    trend_ok = s1h["ema"]["trend"] == ("bullish" if is_long else "bearish")
    if trend_ok:
        score += 1.5
        reasons.append(f"✅ 1H روند {'صعودی' if is_long else 'نزولی'}")
    else:
        reasons.append(f"❌ 1H روند مخالف")

    # ── ۳. BOS/CHOCH (1.5 امتیاز) ──
    bos_ok = (s15m["bos"]["bos_bullish"] or s5m["bos"]["bos_bullish"]) if is_long else \
             (s15m["bos"]["bos_bearish"] or s5m["bos"]["bos_bearish"])
    if bos_ok:
        score += 1.5
        reasons.append(f"✅ BOS {'صعودی' if is_long else 'نزولی'} تأیید شد")
    else:
        reasons.append("❌ BOS تأیید نشد")

    # ── ۴. Order Block (1.5 امتیاز) ──
    in_ob  = (s15m["ob"]["price_in_bull_ob"] or s5m["ob"]["price_in_bull_ob"]) if is_long else \
             (s15m["ob"]["price_in_bear_ob"] or s5m["ob"]["price_in_bear_ob"])
    near_ob= (s15m["ob"]["nearest_bull_ob"] or s5m["ob"]["nearest_bull_ob"]) if is_long else \
             (s15m["ob"]["nearest_bear_ob"] or s5m["ob"]["nearest_bear_ob"])

    if in_ob:
        score += 1.5
        reasons.append(f"✅ داخل Order Block {'صعودی' if is_long else 'نزولی'}")
    elif near_ob:
        score += 0.8
        reasons.append(f"⚠️ نزدیک Order Block")
    else:
        reasons.append("❌ خارج از Order Block")

    # ── ۵. FVG (1 امتیاز) ──
    in_fvg  = (s15m["fvg"]["price_in_bull_fvg"] or s5m["fvg"]["price_in_bull_fvg"]) if is_long else \
              (s15m["fvg"]["price_in_bear_fvg"] or s5m["fvg"]["price_in_bear_fvg"])
    near_fvg= (s15m["fvg"]["nearest_bull_fvg"] or s5m["fvg"]["nearest_bull_fvg"]) if is_long else \
              (s15m["fvg"]["nearest_bear_fvg"] or s5m["fvg"]["nearest_bear_fvg"])

    if in_fvg:
        score += 1.0
        reasons.append("✅ داخل FVG")
    elif near_fvg:
        score += 0.5
        reasons.append("⚠️ نزدیک FVG")

    # ── ۶. VWAP (1 امتیاز) ──
    vwap_ok = s1h["vwap"]["above_vwap"] if is_long else not s1h["vwap"]["above_vwap"]
    if vwap_ok:
        score += 1.0
        reasons.append(f"✅ {'بالای' if is_long else 'زیر'} VWAP 1H")
    else:
        reasons.append(f"❌ {'زیر' if is_long else 'بالای'} VWAP 1H")

    # ── ۷. RSI (1 امتیاز) ──
    rsi = s15m["rsi"]["value"]
    if rsi:
        if is_long:
            if 45 < rsi < 68:   score += 1.0; reasons.append(f"✅ RSI مناسب ({rsi:.0f})")
            elif rsi <= 45:     score += 0.5; reasons.append(f"⚠️ RSI ضعیف ({rsi:.0f})")
            else:               reasons.append(f"❌ RSI اشباع ({rsi:.0f})")
        else:
            if 32 < rsi < 55:   score += 1.0; reasons.append(f"✅ RSI مناسب ({rsi:.0f})")
            elif rsi >= 55:     score += 0.5; reasons.append(f"⚠️ RSI بالا ({rsi:.0f})")
            else:               reasons.append(f"❌ RSI اشباع فروش ({rsi:.0f})")

    # ── ۸. حجم (1 امتیاز) ──
    if s5m["volume"]["above_average"]:
        score += 1.0
        reasons.append(f"✅ حجم قوی ({s5m['volume']['ratio']:.1f}x)")
    elif s15m["volume"]["above_average"]:
        score += 0.5
        reasons.append(f"⚠️ حجم متوسط")
    else:
        reasons.append(f"❌ حجم ضعیف ({s5m['volume']['ratio']:.1f}x)")

    # ── پنالتی: وسط رنج ──
    p = s15m["price"]
    v = s15m["vwap"]["vwap"]
    if v:
        dist = abs(p - v) / p * 100
        if dist < 0.15:
            score -= 1.5
            reasons.append("⛔ قیمت وسط رنج (نزدیک VWAP) — کسر امتیاز")

    score = max(0.0, min(10.0, score))
    return round(score, 1), reasons


# ─────────────────────────────────────────
# سطوح ورود
# ─────────────────────────────────────────

def _levels_long(price, s5m, s1h, s15m):
    # SL زیر OB یا Swing Low
    sls = []
    ob  = s15m["ob"].get("nearest_bull_ob") or s5m["ob"].get("nearest_bull_ob")
    if ob: sls.append(ob["bottom"] * 0.998)
    ll  = s5m["swings"]["last_low"]
    if ll: sls.append(ll * 0.998)
    fvg = s15m["fvg"].get("nearest_bull_fvg")
    if fvg: sls.append(fvg["bottom"] * 0.999)

    sl   = min(sls) if sls else price * 0.985
    risk = max(price - sl, price * 0.004)

    tp1  = price + risk * 1.0
    tp2  = price + risk * 2.0
    tp3  = price + risk * 3.5

    # اصلاح با Swing High
    sh = s1h["swings"]["last_high"]
    if sh and sh > price:
        tp1 = min(tp1, sh * 0.998)
        tp2 = min(tp2, sh)
    bear_ob = s1h["ob"].get("nearest_bear_ob")
    if bear_ob and bear_ob["bottom"] > price:
        tp2 = min(tp2, bear_ob["bottom"] * 0.998)
        tp3 = min(tp3, bear_ob["top"])

    rr = round((tp2 - price) / risk, 2) if risk > 0 else 0
    return price, sl, tp1, tp2, tp3, rr


def _levels_short(price, s5m, s1h, s15m):
    sls = []
    ob  = s15m["ob"].get("nearest_bear_ob") or s5m["ob"].get("nearest_bear_ob")
    if ob: sls.append(ob["top"] * 1.002)
    lh  = s5m["swings"]["last_high"]
    if lh: sls.append(lh * 1.002)
    fvg = s15m["fvg"].get("nearest_bear_fvg")
    if fvg: sls.append(fvg["top"] * 1.001)

    sl   = max(sls) if sls else price * 1.015
    risk = max(sl - price, price * 0.004)

    tp1  = price - risk * 1.0
    tp2  = price - risk * 2.0
    tp3  = price - risk * 3.5

    sl2 = s1h["swings"]["last_low"]
    if sl2 and sl2 < price:
        tp1 = max(tp1, sl2 * 1.002)
        tp2 = max(tp2, sl2)
    bull_ob = s1h["ob"].get("nearest_bull_ob")
    if bull_ob and bull_ob["top"] < price:
        tp2 = max(tp2, bull_ob["top"] * 1.002)
        tp3 = max(tp3, bull_ob["bottom"])

    rr = round((price - tp2) / risk, 2) if risk > 0 else 0
    return price, sl, tp1, tp2, tp3, rr


def _suggest_leverage(score, rr):
    if score >= 9.5 and rr >= 4: return 20
    if score >= 9.0 and rr >= 3.5: return 15
    if score >= 8.5 and rr >= 3: return 10
    if score >= 8.0: return 7
    return 5


def _probability(score, rr, btc_score):
    base = (score / 10) * 60 + (min(rr, 5) / 5) * 20 + (btc_score / 10) * 20
    return min(95, max(50, int(base)))


# ─────────────────────────────────────────
# تابع اصلی
# ─────────────────────────────────────────

def analyze(
    symbol:   str,
    df_4h:    pd.DataFrame,
    df_1h:    pd.DataFrame,
    df_15m:   pd.DataFrame,
    df_5m:    pd.DataFrame,
    btc_bias: str = "neutral",
    btc_score: float = 5.0,
) -> Signal:

    price = 0.0
    try:
        _, s1h  = _compute(df_1h)
        _, s15m = _compute(df_15m)
        _, s5m  = _compute(df_5m)
        price   = s5m["price"]
    except Exception as e:
        return _no(symbol, 0.0, f"خطا در محاسبه: {e}")

    # ── فیلتر ارز مجاز ──
    if symbol not in ALLOWED_SYMBOLS:
        return _no(symbol, price, f"ارز {symbol} در لیست مجاز نیست")

    # ── فیلترهای اجباری ──
    rsi_5m = s5m["rsi"]["value"]
    if rsi_5m and rsi_5m > 85:
        return _no(symbol, price, f"RSI 5m اشباع شدید ({rsi_5m:.0f}) — ورود ممنوع")
    if rsi_5m and rsi_5m < 15:
        return _no(symbol, price, f"RSI 5m فروش شدید ({rsi_5m:.0f}) — ورود ممنوع")

    if s5m["volume"]["ratio"] < 0.4 and s15m["volume"]["ratio"] < 0.4:
        return _no(symbol, price, "حجم خیلی کم — بازار بی‌رمق")

    # ── نمره هر دو جهت ──
    l_score, l_reasons = _score_coin(s1h, s15m, s5m, btc_bias, "LONG")
    s_score, s_reasons = _score_coin(s1h, s15m, s5m, btc_bias, "SHORT")

    # انتخاب جهت
    if l_score >= s_score and l_score >= MIN_SCORE:
        direction, score, reasons = "LONG",  l_score, l_reasons
        entry, sl, tp1, tp2, tp3, rr = _levels_long(price, s5m, s1h, s15m)
    elif s_score > l_score and s_score >= MIN_SCORE:
        direction, score, reasons = "SHORT", s_score, s_reasons
        entry, sl, tp1, tp2, tp3, rr = _levels_short(price, s5m, s1h, s15m)
    else:
        best = max(l_score, s_score)
        return _no(symbol, price,
            f"نمره ناکافی: {best:.1f}/10 (حداقل {MIN_SCORE})",
            [f"LONG: {l_score}/10", f"SHORT: {s_score}/10"])

    # ── چک R:R ──
    if rr < MIN_RR:
        return _no(symbol, price,
            f"R/R ناکافی: {rr} (حداقل {MIN_RR})",
            reasons)

    # ── همسویی BTC ──
    if btc_bias == "bearish" and direction == "LONG" and btc_score < 4:
        return _no(symbol, price, "BTC شدیداً نزولی — لانگ ممنوع")
    if btc_bias == "bullish" and direction == "SHORT" and btc_score > 7:
        return _no(symbol, price, "BTC شدیداً صعودی — شورت ممنوع")

    # ── کانفیدنس ──
    if score >= 9.5:   conf = "HIGH"
    elif score >= 8.0: conf = "MEDIUM"
    else:              conf = "LOW"

    lev  = _suggest_leverage(score, rr)
    prob = _probability(score, rr, btc_score)

    return Signal(
        symbol=symbol, direction=direction, timeframe="15m/5m",
        price=price, score=score, probability=prob, confidence=conf,
        entry=round(entry,4), stop_loss=round(sl,4),
        tp1=round(tp1,4), tp2=round(tp2,4), tp3=round(tp3,4),
        rr=rr, leverage=lev,
        btc_score=btc_score, btc_bias=btc_bias,
        reasons=reasons,
    )


# ─────────────────────────────────────────
# فرمت خروجی
# ─────────────────────────────────────────

def format_signal_text(sig: Signal) -> str:
    if sig.direction == "NO_SIGNAL":
        return (
            f"🔴 رد شد — {sig.symbol}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"دلیل: {sig.reject_reason}\n"
        )

    d = "Long 🟢" if sig.direction == "LONG" else "Short 🔴"
    conf_emoji = {"HIGH":"🔥","MEDIUM":"⚡","LOW":"🔹"}.get(sig.confidence,"")

    lines = [
        f"━━━━━━━━━━━━━━━━━━━━",
        f"✅ ورود مجاز — {sig.symbol}",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"Coin:         {sig.symbol}",
        f"Direction:    {d}",
        f"Entry:        {sig.entry}",
        f"Stop Loss:    {sig.stop_loss}",
        f"TP1:          {sig.tp1}",
        f"TP2:          {sig.tp2}",
        f"TP3:          {sig.tp3}",
        f"Risk/Reward:  1:{sig.rr}",
        f"Score:        {sig.score}/10  {conf_emoji}",
        f"Probability:  {sig.probability}%",
        f"Leverage:     {sig.leverage}x پیشنهادی",
        f"",
        f"BTC Score:    {sig.btc_score}/10 ({sig.btc_bias})",
        f"",
        f"دلیل ورود:",
    ]

    for r in sig.reasons[:6]:
        lines.append(f"  {r}")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


if __name__ == "__main__":
    import numpy as np
    np.random.seed(42)
    n = 300
    def mk(start, tr="up"):
        p = start + np.cumsum(np.abs(np.random.randn(n))*60) if tr=="up" else start - np.cumsum(np.abs(np.random.randn(n))*60)
        v = np.abs(np.random.randn(n)*1000+6000)
        return pd.DataFrame({"time":pd.date_range("2024-01-01",periods=n,freq="5min"),
            "open":p-30,"high":p+80,"low":p-80,"close":p,"baseVol":v,"quoteVol":v*p})

    btc = analyze_btc(mk(58000), mk(59500), mk(60200))
    print(f"BTC: نمره {btc['score']}/10 — {btc['bias']}")

    sig = analyze("BTCUSDT", mk(58000), mk(59500), mk(60200), mk(60400),
                  btc_bias=btc["bias"], btc_score=btc["score"])
    print(format_signal_text(sig))
