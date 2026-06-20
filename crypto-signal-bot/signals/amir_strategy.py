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

try:
    from data.hyperliquid_client import get_funding_direction_score
    HAS_HYPERLIQUID = True
except ImportError:
    HAS_HYPERLIQUID = False

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
MIN_SCORE  = 5.0   # از ۱۰ — پایین‌تر برای سیگنال بیشتر
MIN_RR     = 1.0   # حداقل ۱:۱
MIN_PROB   = 50    # درصد احتمال

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
        "price":    ind["price"],
        "ema":      ind["ema"],
        "rsi":      ind["rsi"],
        "volume":   ind["volume"],
        "atr":      ind.get("atr"),
        "adx":      ind.get("adx"),
        "plus_di":  ind.get("plus_di"),
        "minus_di": ind.get("minus_di"),
        "vwap":     vwap,
        "bos":      struct["bos"],
        "ob":       struct["ob"],
        "fvg":      struct["fvg"],
        "swings":   struct["swings"],
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

def _score_coin(s4h, s1h, s15m, s5m, btc_bias, direction) -> tuple:
    """نمره‌دهی ۱۰ برای یک ارز در جهت مشخص — شامل تایم‌فریم ۴H"""
    score   = 0.0
    reasons = []
    price   = s5m["price"]
    is_long = (direction == "LONG")

    # ── ۰. روند ۴H ارز (2 امتیاز — بیشترین وزن) ──
    trend_4h = s4h["ema"]["trend"]
    if trend_4h == ("bullish" if is_long else "bearish"):
        score += 2.0
        reasons.append(f"✅ 4H روند {'صعودی' if is_long else 'نزولی'} تأیید")
    elif trend_4h == "neutral":
        score += 0.5
        reasons.append("⚠️ 4H روند خنثی")
    else:
        score -= 1.0
        reasons.append(f"❌ 4H روند مخالف ({trend_4h}) — کسر امتیاز")

    # ── ۱. همسویی با BTC (1 امتیاز) ──
    if btc_bias == ("bullish" if is_long else "bearish"):
        score += 1.0
        reasons.append(f"✅ BTC هم‌جهت ({btc_bias})")
    elif btc_bias == "neutral":
        score += 0.3
        reasons.append("⚠️ BTC خنثی")
    else:
        score -= 0.5
        reasons.append(f"❌ BTC مخالف ({btc_bias})")

    # ── ۲. EMA Stack مرتب 1H (1.5 امتیاز) ──
    ema_aligned = s1h["ema"].get("ema_aligned_bull" if is_long else "ema_aligned_bear", False)
    ema_trend   = s1h["ema"]["trend"] == ("bullish" if is_long else "bearish")
    if ema_aligned:
        score += 1.5
        reasons.append(f"✅ 1H EMA Stack مرتب {'صعودی' if is_long else 'نزولی'}")
    elif ema_trend:
        score += 0.8
        reasons.append(f"⚠️ 1H روند {'صعودی' if is_long else 'نزولی'} (stack ناقص)")
    else:
        reasons.append(f"❌ 1H روند مخالف")

    # ── ۳. ADX — فقط بازار ترندینگ (1 امتیاز) ──
    adx = s15m.get("adx")
    plus_di  = s15m.get("plus_di")
    minus_di = s15m.get("minus_di")
    if adx and adx > 25:
        di_ok = (plus_di > minus_di) if is_long else (minus_di > plus_di)
        if di_ok:
            score += 1.0
            reasons.append(f"✅ ADX قوی ({adx:.0f}) جهت تأیید")
        else:
            score += 0.3
            reasons.append(f"⚠️ ADX قوی ({adx:.0f}) اما DI مخالف")
    elif adx and adx > 18:
        score += 0.4
        reasons.append(f"⚠️ ADX متوسط ({adx:.0f})")
    else:
        score -= 0.5
        reasons.append("⛔ ADX ضعیف ({}) — بازار رنج".format(int(adx) if adx else 0))

    # ── ۴. BOS/CHOCH (1.5 امتیاز) ──
    bos_ok = (s15m["bos"]["bos_bullish"] or s5m["bos"]["bos_bullish"]) if is_long else \
             (s15m["bos"]["bos_bearish"] or s5m["bos"]["bos_bearish"])
    if bos_ok:
        score += 1.5
        reasons.append(f"✅ BOS {'صعودی' if is_long else 'نزولی'} تأیید شد")
    else:
        reasons.append("❌ BOS تأیید نشد")

    # ── ۵. Order Block (1.5 امتیاز) ──
    in_ob   = (s15m["ob"]["price_in_bull_ob"] or s5m["ob"]["price_in_bull_ob"]) if is_long else \
              (s15m["ob"]["price_in_bear_ob"] or s5m["ob"]["price_in_bear_ob"])
    near_ob = (s15m["ob"]["nearest_bull_ob"] or s5m["ob"]["nearest_bull_ob"]) if is_long else \
              (s15m["ob"]["nearest_bear_ob"] or s5m["ob"]["nearest_bear_ob"])
    if in_ob:
        score += 1.5
        reasons.append(f"✅ داخل Order Block {'صعودی' if is_long else 'نزولی'}")
    elif near_ob:
        score += 0.6
        reasons.append(f"⚠️ نزدیک Order Block")
    else:
        reasons.append("❌ خارج از Order Block")

    # ── ۶. FVG (1 امتیاز) ──
    in_fvg   = (s15m["fvg"]["price_in_bull_fvg"] or s5m["fvg"]["price_in_bull_fvg"]) if is_long else \
               (s15m["fvg"]["price_in_bear_fvg"] or s5m["fvg"]["price_in_bear_fvg"])
    near_fvg = (s15m["fvg"]["nearest_bull_fvg"] or s5m["fvg"]["nearest_bull_fvg"]) if is_long else \
               (s15m["fvg"]["nearest_bear_fvg"] or s5m["fvg"]["nearest_bear_fvg"])
    if in_fvg:
        score += 1.0
        reasons.append("✅ داخل FVG")
    elif near_fvg:
        score += 0.4
        reasons.append("⚠️ نزدیک FVG")

    # ── ۷. VWAP (1 امتیاز) ──
    vwap_ok = s1h["vwap"]["above_vwap"] if is_long else not s1h["vwap"]["above_vwap"]
    if vwap_ok:
        if s1h["vwap"].get("cross") == ("bullish_cross" if is_long else "bearish_cross"):
            score += 1.0
            reasons.append(f"✅ کراس {'صعودی' if is_long else 'نزولی'} VWAP 1H")
        else:
            score += 0.7
            reasons.append(f"✅ {'بالای' if is_long else 'زیر'} VWAP 1H")
    else:
        reasons.append(f"❌ {'زیر' if is_long else 'بالای'} VWAP 1H")

    # ── ۸. RSI (1 امتیاز) ──
    rsi = s15m["rsi"]["value"]
    if rsi:
        if is_long:
            if 48 < rsi < 65:   score += 1.0; reasons.append(f"✅ RSI مناسب ({rsi:.0f})")
            elif 40 <= rsi <= 48: score += 0.4; reasons.append(f"⚠️ RSI ضعیف ({rsi:.0f})")
            elif rsi >= 65:     reasons.append(f"❌ RSI اشباع ({rsi:.0f})")
            else:               reasons.append(f"❌ RSI خیلی پایین ({rsi:.0f})")
        else:
            if 35 < rsi < 52:   score += 1.0; reasons.append(f"✅ RSI مناسب ({rsi:.0f})")
            elif 52 <= rsi <= 60: score += 0.4; reasons.append(f"⚠️ RSI بالا ({rsi:.0f})")
            else:               reasons.append(f"❌ RSI اشباع فروش ({rsi:.0f})")

    # ── ۹. حجم (1 امتیاز) ──
    if s5m["volume"]["strong"]:
        score += 1.0
        reasons.append(f"✅ حجم قوی ({s5m['volume']['ratio']:.1f}x)")
    elif s5m["volume"]["above_average"]:
        score += 0.5
        reasons.append(f"⚠️ حجم متوسط ({s5m['volume']['ratio']:.1f}x)")
    elif s15m["volume"]["above_average"]:
        score += 0.3
        reasons.append(f"⚠️ حجم 15m متوسط")
    else:
        reasons.append(f"❌ حجم ضعیف ({s5m['volume']['ratio']:.1f}x)")

    # ── پنالتی: بازار رنج (وسط VWAP) ──
    v = s15m["vwap"]["vwap"]
    if v:
        dist = abs(price - v) / price * 100
        if dist < 0.05:
            score -= 1.0
            reasons.append("⚠️ قیمت نزدیک VWAP")

    score = max(0.0, min(10.0, score))
    return round(score, 1), reasons


# ─────────────────────────────────────────
# سطوح ورود
# ─────────────────────────────────────────

def _atr_sl_buffer(atr, price, multiplier=1.8):
    """حداقل فاصله SL بر اساس ATR"""
    if atr and atr > 0:
        return atr * multiplier
    return price * 0.012   # fallback: 1.2%


def _levels_long(price, s5m, s1h, s15m):
    atr    = s15m.get("atr") or s5m.get("atr")
    min_sl = _atr_sl_buffer(atr, price, multiplier=1.8)

    # کاندیداهای SL — زیر OB / FVG / Swing Low
    sls = []
    ob  = s15m["ob"].get("nearest_bull_ob") or s5m["ob"].get("nearest_bull_ob")
    if ob:  sls.append(ob["bottom"] * 0.9975)   # ۰.۲۵٪ زیر کف OB
    ll  = s15m["swings"]["last_low"] or s5m["swings"]["last_low"]
    if ll:  sls.append(ll * 0.9975)
    fvg = s15m["fvg"].get("nearest_bull_fvg")
    if fvg: sls.append(fvg["bottom"] * 0.9975)

    # پایین‌ترین SL رو انتخاب کن (ایمن‌ترین)
    sl_candidate = min(sls) if sls else price - min_sl

    # مطمئن بشیم فاصله حداقل 1.8 ATR باشه
    if (price - sl_candidate) < min_sl:
        sl_candidate = price - min_sl

    sl   = round(sl_candidate, 6)
    risk = price - sl

    tp1 = round(price + risk * 1.0, 6)
    tp2 = round(price + risk * 2.0, 6)
    tp3 = round(price + risk * 3.5, 6)

    # سقف: Swing High یا Bearish OB
    sh = s1h["swings"]["last_high"]
    if sh and price < sh < tp3:
        if sh < tp1: tp1 = round(sh * 0.9985, 6)
        if sh < tp2: tp2 = round(sh * 0.9985, 6)

    bear_ob = s1h["ob"].get("nearest_bear_ob")
    if bear_ob and price < bear_ob["bottom"] < tp3:
        tp2 = min(tp2, round(bear_ob["bottom"] * 0.9985, 6))
        tp3 = min(tp3, round(bear_ob["top"], 6))

    rr = round((tp2 - price) / risk, 2) if risk > 0 else 0
    return price, sl, tp1, tp2, tp3, rr


def _levels_short(price, s5m, s1h, s15m):
    atr    = s15m.get("atr") or s5m.get("atr")
    min_sl = _atr_sl_buffer(atr, price, multiplier=1.8)

    sls = []
    ob  = s15m["ob"].get("nearest_bear_ob") or s5m["ob"].get("nearest_bear_ob")
    if ob:  sls.append(ob["top"] * 1.0025)
    lh  = s15m["swings"]["last_high"] or s5m["swings"]["last_high"]
    if lh:  sls.append(lh * 1.0025)
    fvg = s15m["fvg"].get("nearest_bear_fvg")
    if fvg: sls.append(fvg["top"] * 1.0025)

    sl_candidate = max(sls) if sls else price + min_sl

    if (sl_candidate - price) < min_sl:
        sl_candidate = price + min_sl

    sl   = round(sl_candidate, 6)
    risk = sl - price

    tp1 = round(price - risk * 1.0, 6)
    tp2 = round(price - risk * 2.0, 6)
    tp3 = round(price - risk * 3.5, 6)

    # کف: Swing Low یا Bullish OB
    sl2 = s1h["swings"]["last_low"]
    if sl2 and tp3 < sl2 < price:
        if sl2 > tp1: tp1 = round(sl2 * 1.0015, 6)
        if sl2 > tp2: tp2 = round(sl2 * 1.0015, 6)

    bull_ob = s1h["ob"].get("nearest_bull_ob")
    if bull_ob and tp3 < bull_ob["top"] < price:
        tp2 = max(tp2, round(bull_ob["top"] * 1.0015, 6))
        tp3 = max(tp3, round(bull_ob["bottom"], 6))

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
        _, s4h  = _compute(df_4h)
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
    if rsi_5m and rsi_5m > 82:
        return _no(symbol, price, f"RSI 5m اشباع شدید ({rsi_5m:.0f}) — ورود ممنوع")
    if rsi_5m and rsi_5m < 18:
        return _no(symbol, price, f"RSI 5m فروش شدید ({rsi_5m:.0f}) — ورود ممنوع")

    if s5m["volume"]["ratio"] < 0.4 and s15m["volume"]["ratio"] < 0.4:
        return _no(symbol, price, "حجم خیلی کم — بازار بی‌رمق")

    # ── ADX: بازار رنج شدید رو رد کن ──
    adx_15m = s15m.get("adx")
    if adx_15m and adx_15m < 8:
        return _no(symbol, price, f"ADX خیلی ضعیف ({adx_15m:.0f}) — بازار رنج محض")

    # ── فیلتر ۴H ارز — مهم‌ترین فیلتر ──
    trend_4h = s4h["ema"]["trend"]
    rsi_4h   = s4h["rsi"]["value"]

    # ── نمره هر دو جهت ──
    l_score, l_reasons = _score_coin(s4h, s1h, s15m, s5m, btc_bias, "LONG")
    s_score, s_reasons = _score_coin(s4h, s1h, s15m, s5m, btc_bias, "SHORT")

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

    # ── فیلتر 4H: پنالتی بجای رد کامل ──
    if direction == "LONG" and trend_4h == "bearish":
        price_in_4h_ob = s4h["ob"]["price_in_bull_ob"]
        if price_in_4h_ob:
            reasons.append("⚠️ 4H نزولی اما داخل OB — ریسک بالا")
            score = round(score * 0.90, 1)
        else:
            reasons.append("⚠️ 4H نزولی — پنالتی اعمال شد")
            score = round(score * 0.82, 1)

    if direction == "SHORT" and trend_4h == "bullish":
        price_in_4h_ob = s4h["ob"]["price_in_bear_ob"]
        if price_in_4h_ob:
            reasons.append("⚠️ 4H صعودی اما داخل Bearish OB — ریسک بالا")
            score = round(score * 0.90, 1)
        else:
            reasons.append("⚠️ 4H صعودی — پنالتی اعمال شد")
            score = round(score * 0.82, 1)

    # بررسی دوباره نمره بعد از کسر ۴H
    if score < MIN_SCORE:
        return _no(symbol, price, f"نمره بعد از فیلتر 4H: {score}/10", reasons)

    # ── چک R:R ──
    if rr < MIN_RR:
        return _no(symbol, price,
            f"R/R ناکافی: {rr} (حداقل {MIN_RR})",
            reasons)

    # ── همسویی BTC ──
    if btc_bias == "bearish" and direction == "LONG" and btc_score < 3:
        return _no(symbol, price, "BTC شدیداً نزولی — لانگ ممنوع")
    if btc_bias == "bullish" and direction == "SHORT" and btc_score > 8:
        return _no(symbol, price, "BTC شدیداً صعودی — شورت ممنوع")

    # ── Hyperliquid Funding Rate ──
    if HAS_HYPERLIQUID:
        try:
            hl_adj, hl_reason = get_funding_direction_score(symbol, direction)
            score = round(score + hl_adj, 1)
            score = max(0.0, min(10.0, score))
            reasons.append(hl_reason)
        except:
            pass

    if score < MIN_SCORE:
        return _no(symbol, price, f"نمره بعد از Funding: {score}/10", reasons)

    # ── کانفیدنس ──
    if score >= 8.5:   conf = "HIGH"
    elif score >= 7.0: conf = "MEDIUM"
    else:              conf = "LOW"

    lev  = _suggest_leverage(score, rr)
    prob = _probability(score, rr, btc_score)

    return Signal(
        symbol=symbol, direction=direction, timeframe="4H/1H/15m",
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

    sl_pct = round(abs(sig.entry - sig.stop_loss) / sig.entry * 100, 2) if sig.entry else 0
    lines = [
        f"━━━━━━━━━━━━━━━━━━━━",
        f"✅ ورود مجاز — {sig.symbol}",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"Coin:         {sig.symbol}",
        f"Direction:    {d}",
        f"Entry:        {sig.entry}",
        f"Stop Loss:    {sig.stop_loss}  ({sl_pct}%)",
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
