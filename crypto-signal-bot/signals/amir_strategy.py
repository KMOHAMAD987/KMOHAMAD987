"""
AMIR TRADING SYSTEM V6 ULTIMATE
سیستم امتیازدهی:
  BTC trend:        0-2
  Market structure:  0-2
  MTS source TF:     0-2
  Entry zone:        0-1.5
  RSI & momentum:    0-1
  Risk/Reward:       0-1.5
  Total:             10
MIN_SCORE = 8.5 | MIN_RR = 3.0
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
from analysis.volume_profile import compute_volume_profile
from analysis.liquidity import compute_liquidity

try:
    from data.hyperliquid_client import get_full_hl_analysis
    HAS_HYPERLIQUID = True
except ImportError:
    HAS_HYPERLIQUID = False

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

MIN_SCORE = 8.5
MIN_RR    = 3.0
MIN_PROB  = 50


@dataclass
class Signal:
    symbol:      str
    direction:   str
    timeframe:   str
    price:       float
    score:       float
    probability: int
    confidence:  str

    entry:       float = 0.0
    stop_loss:   float = 0.0
    tp1:         float = 0.0
    tp2:         float = 0.0
    tp3:         float = 0.0
    rr:          float = 0.0
    leverage:    int   = 5

    btc_score:   float = 0.0
    btc_bias:    str   = "neutral"

    reasons:     list = field(default_factory=list)
    failed:      list = field(default_factory=list)
    reject_reason: str = ""

    score_breakdown: dict = field(default_factory=dict)

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
    vp = compute_volume_profile(df)
    liq = compute_liquidity(df)
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
        "vp":       vp,
        "liq":      liq,
    }


# ─────────────────────────────────────────
# BTC Analysis
# ─────────────────────────────────────────

def analyze_btc(df_4h, df_1h, df_15m) -> dict:
    try:
        _, s4h  = _compute(df_4h)
        _, s1h  = _compute(df_1h)
        _, s15m = _compute(df_15m)
    except Exception as e:
        return {"score": 5.0, "bias": "neutral", "reasons": ["خطا: {}".format(e)]}

    score   = 0.0
    reasons = []
    price   = s4h["price"]

    # 4H Trend (macro)
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

    # 1H Structure
    if s1h["bos"]["bos_bullish"]:
        score += 1.5
        reasons.append("✅ 1H BOS صعودی")
    elif s1h["bos"]["choch_bullish"]:
        score += 1.0
        reasons.append("✅ 1H CHOCH صعودی")
    elif s1h["bos"]["bos_bearish"]:
        reasons.append("❌ 1H BOS نزولی")
    elif s1h["bos"]["choch_bearish"]:
        score -= 0.5
        reasons.append("❌ 1H CHOCH نزولی")
    else:
        score += 0.5
        reasons.append("⚠️ 1H ساختار خنثی")

    # VWAP
    if s1h["vwap"]["above_vwap"]:
        score += 1.5
        reasons.append("✅ 1H بالای VWAP")
    else:
        reasons.append("❌ 1H زیر VWAP")

    # RSI
    rsi_4h = s4h["rsi"]["value"]
    if rsi_4h:
        if 50 < rsi_4h < 70:
            score += 1.5
            reasons.append("✅ RSI 4H مناسب ({:.0f})".format(rsi_4h))
        elif 30 < rsi_4h <= 50:
            score += 0.5
            reasons.append("⚠️ RSI 4H ضعیف ({:.0f})".format(rsi_4h))
        elif rsi_4h >= 70:
            score += 0.5
            reasons.append("⚠️ RSI 4H اشباع ({:.0f})".format(rsi_4h))
        else:
            reasons.append("❌ RSI 4H خیلی پایین ({:.0f})".format(rsi_4h))

    # Volume Profile POC
    vp = s4h["vp"]
    if vp["poc"] and vp["price_vs_poc"] == "above":
        score += 1.0
        reasons.append("✅ 4H بالای POC")
    elif vp["poc"] and vp["price_vs_poc"] == "below":
        reasons.append("❌ 4H زیر POC")
    else:
        score += 0.5

    # OB/FVG
    if s4h["ob"]["nearest_bull_ob"] or s4h["fvg"]["nearest_bull_fvg"]:
        score += 1.0
        reasons.append("✅ OB/FVG صعودی در 4H")
    elif s4h["ob"]["nearest_bear_ob"] or s4h["fvg"]["nearest_bear_fvg"]:
        reasons.append("❌ OB/FVG نزولی در 4H")
    else:
        score += 0.5

    # Liquidity
    liq = s15m["liq"]
    if liq["sweep_signal"] == "bullish_sweep":
        score += 0.5
        reasons.append("✅ Liquidity Sweep صعودی")
    elif liq["sweep_signal"] == "bearish_sweep":
        score -= 0.5
        reasons.append("❌ Liquidity Sweep نزولی")

    # Volume
    if s15m["volume"]["above_average"]:
        score += 0.5
        reasons.append("✅ حجم BTC بالا ({:.1f}x)".format(s15m["volume"]["ratio"]))

    score = min(10.0, max(0.0, score))

    if score >= 7:   bias = "bullish"
    elif score >= 5: bias = "neutral"
    elif score <= 3: bias = "bearish"
    else:            bias = "neutral"

    btc_class = "strong_bullish" if score >= 8.5 else \
                "bullish" if score >= 7 else \
                "neutral" if score >= 4 else \
                "bearish" if score >= 2 else "strong_bearish"

    return {
        "score": round(score, 1),
        "bias": bias,
        "btc_class": btc_class,
        "reasons": reasons,
        "price": price,
    }


# ─────────────────────────────────────────
# V6 Scoring System
# ─────────────────────────────────────────

def _score_btc_alignment(btc_bias, btc_score, direction):
    """BTC trend: 0-2"""
    is_long = direction == "LONG"
    aligned = (btc_bias == "bullish" and is_long) or (btc_bias == "bearish" and not is_long)
    against = (btc_bias == "bearish" and is_long) or (btc_bias == "bullish" and not is_long)

    if aligned and btc_score >= 7:
        return 2.0, "✅ BTC هم‌جهت قوی ({} | {}/10)".format(btc_bias, btc_score)
    elif aligned:
        return 1.5, "✅ BTC هم‌جهت ({})".format(btc_bias)
    elif btc_bias == "neutral":
        return 1.0, "⚠️ BTC خنثی"
    elif against and btc_score <= 3:
        return 0.0, "⛔ BTC شدیداً مخالف ({})".format(btc_bias)
    else:
        return 0.5, "❌ BTC مخالف ({})".format(btc_bias)


def _score_market_structure(s1h, s15m, s5m, direction):
    """Market structure (BOS/CHOCH): 0-2"""
    is_long = direction == "LONG"
    score = 0.0
    reasons = []

    # BOS check across timeframes
    bos_1h = s1h["bos"]["bos_bullish"] if is_long else s1h["bos"]["bos_bearish"]
    bos_15m = s15m["bos"]["bos_bullish"] if is_long else s15m["bos"]["bos_bearish"]
    bos_5m = s5m["bos"]["bos_bullish"] if is_long else s5m["bos"]["bos_bearish"]
    choch_1h = s1h["bos"]["choch_bullish"] if is_long else s1h["bos"]["choch_bearish"]
    choch_15m = s15m["bos"]["choch_bullish"] if is_long else s15m["bos"]["choch_bearish"]

    # Counter-direction BOS (strong against signal)
    bos_against_1h = s1h["bos"]["bos_bearish"] if is_long else s1h["bos"]["bos_bullish"]

    if bos_1h:
        score += 1.2
        reasons.append("✅ BOS {} 1H".format("صعودی" if is_long else "نزولی"))
    elif choch_1h:
        score += 0.8
        reasons.append("✅ CHOCH {} 1H".format("صعودی" if is_long else "نزولی"))
    elif bos_against_1h:
        reasons.append("⛔ BOS مخالف 1H")
        return 0.0, reasons

    if bos_15m:
        score += 0.5
        reasons.append("✅ BOS {} 15M".format("صعودی" if is_long else "نزولی"))
    elif choch_15m:
        score += 0.3
        reasons.append("✅ CHOCH {} 15M".format("صعودی" if is_long else "نزولی"))

    if bos_5m:
        score += 0.3
        reasons.append("✅ BOS {} 5M تأیید".format("صعودی" if is_long else "نزولی"))

    # Liquidity sweep confirmation
    sweep_ok = False
    for tf_data in [s15m, s5m]:
        sweep = tf_data["liq"]["sweep_signal"]
        if (is_long and sweep == "bullish_sweep") or (not is_long and sweep == "bearish_sweep"):
            score = min(2.0, score + 0.3)
            sweep_ok = True
            reasons.append("✅ Liquidity Sweep تأیید")
            break

    return min(2.0, score), reasons


def _score_mts_source(s4h, s1h, s15m, s5m, direction):
    """MTS Source Candle & Timeframe Power: 0-2"""
    is_long = direction == "LONG"
    score = 0.0
    reasons = []

    # Source from higher TF = stronger
    # 4H trend alignment
    trend_4h = s4h["ema"]["trend"]
    trend_1h = s1h["ema"]["trend"]
    expected = "bullish" if is_long else "bearish"

    if trend_4h == expected:
        score += 1.0
        reasons.append("✅ 4H Source هم‌جهت ({})".format(trend_4h))
    elif trend_4h == "neutral":
        score += 0.3
        reasons.append("⚠️ 4H Source خنثی")
    else:
        reasons.append("⛔ 4H Source مخالف ({})".format(trend_4h))
        return 0.0, reasons

    # 1H confirmation
    if trend_1h == expected:
        score += 0.5
        reasons.append("✅ 1H Source تأیید")
    elif trend_1h == "neutral":
        score += 0.2

    # EMA200 alignment
    ema200_ok = s1h["ema"]["above_200"] if is_long else not s1h["ema"]["above_200"]
    if ema200_ok:
        score += 0.3
        reasons.append("✅ {} EMA200 1H".format("بالای" if is_long else "زیر"))
    else:
        reasons.append("❌ EMA200 مخالف")

    # EMA stack aligned
    ema_aligned = s1h["ema"].get("ema_aligned_bull" if is_long else "ema_aligned_bear", False)
    if ema_aligned:
        score += 0.2
        reasons.append("✅ EMA Stack مرتب")

    return min(2.0, score), reasons


def _score_entry_zone(s15m, s5m, s1h, direction):
    """Entry zone confluence: 0-1.5"""
    is_long = direction == "LONG"
    confluences = 0
    score = 0.0
    reasons = []

    # OB
    in_ob = False
    near_ob = False
    for tf in [s15m, s5m]:
        if is_long:
            if tf["ob"]["price_in_bull_ob"]:
                in_ob = True
            elif tf["ob"]["nearest_bull_ob"]:
                near_ob = True
        else:
            if tf["ob"]["price_in_bear_ob"]:
                in_ob = True
            elif tf["ob"]["nearest_bear_ob"]:
                near_ob = True

    if in_ob:
        confluences += 1
        score += 0.4
        reasons.append("✅ داخل Order Block")
    elif near_ob:
        score += 0.15
        reasons.append("⚠️ نزدیک Order Block")

    # FVG
    in_fvg = False
    for tf in [s15m, s5m]:
        if is_long and tf["fvg"]["price_in_bull_fvg"]:
            in_fvg = True
        elif not is_long and tf["fvg"]["price_in_bear_fvg"]:
            in_fvg = True

    if in_fvg:
        confluences += 1
        score += 0.3
        reasons.append("✅ داخل FVG")

    # VWAP
    vwap_ok = s1h["vwap"]["above_vwap"] if is_long else not s1h["vwap"]["above_vwap"]
    vwap_cross = s1h["vwap"].get("cross")
    vwap_cross_ok = (vwap_cross == "bullish_cross" and is_long) or (vwap_cross == "bearish_cross" and not is_long)

    if vwap_cross_ok:
        confluences += 1
        score += 0.3
        reasons.append("✅ کراس VWAP")
    elif vwap_ok:
        confluences += 1
        score += 0.2
        reasons.append("✅ {} VWAP".format("بالای" if is_long else "زیر"))
    else:
        reasons.append("❌ VWAP مخالف")

    # Volume Profile POC
    for tf in [s15m, s1h]:
        vp = tf["vp"]
        if vp["poc"]:
            poc_ok = (vp["price_vs_poc"] == "above" and is_long) or \
                     (vp["price_vs_poc"] == "below" and not is_long)
            if poc_ok:
                confluences += 1
                score += 0.2
                reasons.append("✅ {} POC".format("بالای" if is_long else "زیر"))
            break

    # EMA200
    ema200_ok = s15m["ema"]["above_200"] if is_long else not s15m["ema"]["above_200"]
    if ema200_ok:
        confluences += 1
        score += 0.15

    # Bonus for multi-confluence
    if confluences >= 3:
        score = min(1.5, score + 0.15)
        reasons.append("🔥 {} کانفلوئنس همزمان".format(confluences))

    return min(1.5, score), reasons


def _score_rsi_momentum(s15m, s5m, s1h, direction):
    """RSI & momentum: 0-1"""
    is_long = direction == "LONG"
    score = 0.0
    reasons = []

    rsi = s15m["rsi"]["value"]
    rsi_div = s15m["rsi"].get("divergence")
    rsi_1h = s1h["rsi"]["value"]

    if rsi is None:
        return 0.5, ["⚠️ RSI نامشخص"]

    # RSI zone
    if is_long:
        if 45 < rsi < 65:
            score += 0.4
            reasons.append("✅ RSI مناسب ({:.0f})".format(rsi))
        elif rsi >= 70:
            reasons.append("⛔ RSI اشباع خرید ({:.0f})".format(rsi))
            return 0.0, reasons
        elif rsi <= 30:
            score += 0.3
            reasons.append("⚠️ RSI اشباع فروش ({:.0f}) — احتمال برگشت".format(rsi))
        else:
            score += 0.2
            reasons.append("⚠️ RSI ضعیف ({:.0f})".format(rsi))
    else:
        if 35 < rsi < 55:
            score += 0.4
            reasons.append("✅ RSI مناسب ({:.0f})".format(rsi))
        elif rsi <= 30:
            reasons.append("⛔ RSI اشباع فروش ({:.0f})".format(rsi))
            return 0.0, reasons
        elif rsi >= 70:
            score += 0.3
            reasons.append("⚠️ RSI اشباع خرید ({:.0f}) — احتمال ریزش".format(rsi))
        else:
            score += 0.2

    # RSI Divergence bonus
    if (is_long and rsi_div == "bullish") or (not is_long and rsi_div == "bearish"):
        score += 0.4
        reasons.append("✅ واگرایی {} RSI".format("مثبت" if is_long else "منفی"))
    elif (is_long and rsi_div == "bearish") or (not is_long and rsi_div == "bullish"):
        score -= 0.2
        reasons.append("❌ واگرایی مخالف RSI")

    # ADX momentum
    adx = s15m.get("adx")
    if adx and adx > 25:
        score += 0.2
        reasons.append("✅ ADX قوی ({:.0f})".format(adx))

    return min(1.0, max(0.0, score)), reasons


def _score_rr(rr):
    """Risk/Reward: 0-1.5"""
    if rr >= 3.0:
        return 1.5, "✅ R/R عالی (1:{:.1f})".format(rr)
    elif rr >= 2.0:
        return 0.8, "⚠️ R/R متوسط (1:{:.1f})".format(rr)
    else:
        return 0.0, "❌ R/R ناکافی (1:{:.1f})".format(rr)


# ─────────────────────────────────────────
# Entry Levels
# ─────────────────────────────────────────

def _atr_sl_buffer(atr, price, multiplier=1.8):
    if atr and atr > 0:
        return atr * multiplier
    return price * 0.012


def _levels_long(price, s5m, s1h, s15m):
    atr    = s15m.get("atr") or s5m.get("atr")
    min_sl = _atr_sl_buffer(atr, price, multiplier=1.8)

    sls = []
    ob  = s15m["ob"].get("nearest_bull_ob") or s5m["ob"].get("nearest_bull_ob")
    if ob:  sls.append(ob["bottom"] * 0.9975)
    ll  = s15m["swings"]["last_low"] or s5m["swings"]["last_low"]
    if ll:  sls.append(ll * 0.9975)
    fvg = s15m["fvg"].get("nearest_bull_fvg")
    if fvg: sls.append(fvg["bottom"] * 0.9975)

    sl_candidate = min(sls) if sls else price - min_sl
    if (price - sl_candidate) < min_sl:
        sl_candidate = price - min_sl

    sl   = round(sl_candidate, 6)
    risk = price - sl

    # Single main TP (RR 1:3), secondary TPs for path info
    tp1 = round(price + risk * 3.0, 6)   # Main TP (1:3)
    tp2 = round(price + risk * 4.5, 6)   # Extended
    tp3 = round(price + risk * 6.0, 6)   # Max

    rr = round((tp1 - price) / risk, 2) if risk > 0 else 0
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

    tp1 = round(price - risk * 3.0, 6)
    tp2 = round(price - risk * 4.5, 6)
    tp3 = round(price - risk * 6.0, 6)

    rr = round((price - tp1) / risk, 2) if risk > 0 else 0
    return price, sl, tp1, tp2, tp3, rr


def _suggest_leverage(score, rr):
    if score >= 9.5 and rr >= 4: return 15
    if score >= 9.0 and rr >= 3.5: return 12
    if score >= 9.0: return 10
    if score >= 8.5: return 7
    return 5


def _probability(score, rr, btc_score):
    base = (score / 10) * 60 + (min(rr, 5) / 5) * 20 + (btc_score / 10) * 20
    return min(95, max(50, int(base)))


# ─────────────────────────────────────────
# Main Analysis
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
        return _no(symbol, 0.0, "خطا در محاسبه: {}".format(e))

    if symbol not in ALLOWED_SYMBOLS:
        return _no(symbol, price, "ارز {} در لیست مجاز نیست".format(symbol))

    # Hard filters
    rsi_5m = s5m["rsi"]["value"]
    if rsi_5m and rsi_5m > 85:
        return _no(symbol, price, "RSI 5m اشباع شدید ({:.0f})".format(rsi_5m))
    if rsi_5m and rsi_5m < 15:
        return _no(symbol, price, "RSI 5m فروش شدید ({:.0f})".format(rsi_5m))

    if s5m["volume"]["ratio"] < 0.4 and s15m["volume"]["ratio"] < 0.4:
        return _no(symbol, price, "حجم خیلی کم — بازار بی‌رمق")

    # BTC strong rejection
    if btc_bias == "bearish" and btc_score <= 3:
        # Only allow SHORT
        pass
    if btc_bias == "bullish" and btc_score >= 8:
        # Only allow LONG
        pass

    # Score both directions
    best_signal = None

    for direction in ["LONG", "SHORT"]:
        # BTC hard filter
        if direction == "LONG" and btc_bias == "bearish" and btc_score <= 3:
            continue
        if direction == "SHORT" and btc_bias == "bullish" and btc_score >= 8:
            continue

        breakdown = {}
        all_reasons = []

        # 1. BTC Alignment (0-2)
        s1, r1 = _score_btc_alignment(btc_bias, btc_score, direction)
        breakdown["btc"] = s1
        all_reasons.append(r1)

        # 2. Market Structure (0-2)
        s2, r2 = _score_market_structure(s1h, s15m, s5m, direction)
        breakdown["structure"] = s2
        all_reasons.extend(r2)

        # 3. MTS Source (0-2)
        s3, r3 = _score_mts_source(s4h, s1h, s15m, s5m, direction)
        breakdown["mts"] = s3
        all_reasons.extend(r3)

        # 4. Entry Zone (0-1.5)
        s4, r4 = _score_entry_zone(s15m, s5m, s1h, direction)
        breakdown["zone"] = s4
        all_reasons.extend(r4)

        # 5. RSI & Momentum (0-1)
        s5_score, r5 = _score_rsi_momentum(s15m, s5m, s1h, direction)
        breakdown["rsi"] = s5_score
        all_reasons.extend(r5)

        # Calculate levels first to get RR
        if direction == "LONG":
            entry, sl, tp1, tp2, tp3, rr = _levels_long(price, s5m, s1h, s15m)
        else:
            entry, sl, tp1, tp2, tp3, rr = _levels_short(price, s5m, s1h, s15m)

        # 6. R/R (0-1.5)
        s6, r6 = _score_rr(rr)
        breakdown["rr"] = s6
        all_reasons.append(r6)

        total = round(s1 + s2 + s3 + s4 + s5_score + s6, 1)
        total = min(10.0, max(0.0, total))
        breakdown["total"] = total

        if best_signal is None or total > best_signal["total"]:
            best_signal = {
                "direction": direction,
                "total": total,
                "breakdown": breakdown,
                "reasons": all_reasons,
                "entry": entry, "sl": sl,
                "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "rr": rr,
            }

    if best_signal is None:
        return _no(symbol, price, "BTC مخالف — هر دو جهت مسدود")

    total = best_signal["total"]
    direction = best_signal["direction"]
    reasons = best_signal["reasons"]
    breakdown = best_signal["breakdown"]
    rr = best_signal["rr"]

    # Hyperliquid adjustment
    if HAS_HYPERLIQUID:
        try:
            hl_adj, hl_reasons, hl_details = get_full_hl_analysis(symbol, direction)
            hl_adj_capped = max(-1.0, min(1.0, hl_adj))
            total = round(total + hl_adj_capped, 1)
            total = max(0.0, min(10.0, total))
            reasons.extend(hl_reasons)
            breakdown["hyperliquid"] = hl_adj_capped
        except:
            pass

    if total < MIN_SCORE:
        return _no(symbol, price,
            "امتیاز ناکافی: {}/10 (حداقل {})".format(total, MIN_SCORE),
            ["BTC: {}".format(breakdown.get("btc", 0)),
             "ساختار: {}".format(breakdown.get("structure", 0)),
             "MTS: {}".format(breakdown.get("mts", 0)),
             "ناحیه: {}".format(breakdown.get("zone", 0)),
             "RSI: {}".format(breakdown.get("rsi", 0)),
             "R/R: {}".format(breakdown.get("rr", 0))])

    if rr < MIN_RR:
        return _no(symbol, price,
            "R/R ناکافی: 1:{} (حداقل 1:{})".format(rr, MIN_RR))

    # Confidence
    if total >= 9.5:  conf = "HIGH"
    elif total >= 9.0: conf = "HIGH"
    elif total >= 8.5: conf = "MEDIUM"
    else:              conf = "LOW"

    lev  = _suggest_leverage(total, rr)
    prob = _probability(total, rr, btc_score)

    return Signal(
        symbol=symbol, direction=direction, timeframe="4H/1H/15m/5m",
        price=price, score=total, probability=prob, confidence=conf,
        entry=round(best_signal["entry"], 4),
        stop_loss=round(best_signal["sl"], 4),
        tp1=round(best_signal["tp1"], 4),
        tp2=round(best_signal["tp2"], 4),
        tp3=round(best_signal["tp3"], 4),
        rr=rr, leverage=lev,
        btc_score=btc_score, btc_bias=btc_bias,
        reasons=reasons,
        score_breakdown=breakdown,
    )


# ─────────────────────────────────────────
# Signal Format
# ─────────────────────────────────────────

def format_signal_text(sig: Signal) -> str:
    if sig.direction == "NO_SIGNAL":
        return (
            "🔴 رد شد — {}\n"
            "━━━━━━━━━━━━━━━━\n"
            "دلیل: {}\n"
        ).format(sig.symbol, sig.reject_reason)

    d = "Long 🟢" if sig.direction == "LONG" else "Short 🔴"
    conf_emoji = {"HIGH": "🔥", "MEDIUM": "⚡", "LOW": "🔹"}.get(sig.confidence, "")

    sl_pct = round(abs(sig.entry - sig.stop_loss) / sig.entry * 100, 2) if sig.entry else 0
    tp_pct = round(abs(sig.tp1 - sig.entry) / sig.entry * 100, 2) if sig.entry else 0

    bd = sig.score_breakdown or {}
    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "✅ AMIR V6 — {}".format(sig.symbol),
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "Direction:    {}".format(d),
        "Entry:        {}".format(sig.entry),
        "Stop Loss:    {}  ({:.2f}%)".format(sig.stop_loss, sl_pct),
        "Take Profit:  {}  ({:.2f}%)".format(sig.tp1, tp_pct),
        "Risk/Reward:  1:{}".format(sig.rr),
        "",
        "Score:        {}/10  {}".format(sig.score, conf_emoji),
        "Probability:  {}%".format(sig.probability),
        "Leverage:     {}x پیشنهادی".format(sig.leverage),
        "",
        "━━ امتیاز جزئی ━━",
        "BTC:      {}/2".format(bd.get("btc", "?")),
        "ساختار:   {}/2".format(bd.get("structure", "?")),
        "MTS:      {}/2".format(bd.get("mts", "?")),
        "ناحیه:    {}/1.5".format(bd.get("zone", "?")),
        "RSI:      {}/1".format(bd.get("rsi", "?")),
        "R/R:      {}/1.5".format(bd.get("rr", "?")),
        "",
        "BTC Score:    {}/10 ({})".format(sig.btc_score, sig.btc_bias),
        "",
        "دلیل ورود:",
    ]

    for r in sig.reasons[:8]:
        lines.append("  {}".format(r))

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)
