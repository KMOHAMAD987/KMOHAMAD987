# 🤖 ربات سیگنال سبک امیر

ربات سیگنال کریپتو بر اساس استراتژی سبک امیر
(SMC + ICT + Volume Profile + VWAP + OB + FVG + EMA + RSI)

---

## 📦 ساختار پروژه

```
crypto-signal-bot/
├── data/
│   ├── bitunix_client.py   ← اتصال به Bitunix API
│   └── trades.json         ← دیتابیس معاملات (خودکار ساخته میشه)
├── analysis/
│   ├── indicators.py       ← EMA 9/21/50/200 + RSI + Volume
│   ├── vwap.py             ← VWAP + Bands
│   └── structure.py        ← OB + FVG + Swing + BOS
├── signals/
│   ├── amir_strategy.py    ← موتور سیگنال (چک‌لیست ۱۱ شرط)
│   └── tracker.py          ← ردیابی TP/SL + وین‌ریت
├── telegram/
│   └── bot.py              ← ارسال سیگنال + دستورات
├── config/
│   └── settings.py         ← تنظیمات
├── main.py                 ← لوپ اصلی
└── requirements.txt
```

---

## 🚀 نصب و راه‌اندازی

### ۱. نصب پیش‌نیازها
```bash
pip install -r requirements.txt
```

### ۲. اجرا
```bash
python main.py
```

---

## ⚙️ تنظیمات (main.py)

```python
SYMBOLS        = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
SCAN_INTERVAL  = 15 * 60   # هر ۱۵ دقیقه اسکن
MIN_SCORE      = 6          # حداقل امتیاز از ۱۱
MIN_RR         = 1.5        # حداقل R/R
MIN_CONFIDENCE = "MEDIUM"   # HIGH | MEDIUM
SIGNAL_COOLDOWN= 60 * 60   # ۱ ساعت فاصله بین سیگنال‌های یک نماد
```

---

## 📊 چک‌لیست سیگنال (۱۱ شرط)

### LONG
1. ✅ 4H روند صعودی + بالای EMA200
2. ✅ 1H روند صعودی
3. ✅ قیمت بالای VWAP
4. ✅ واکنش از Bullish OB یا FVG مثبت
5. ✅ RSI 1H بالای 50
6. ✅ RSI 5m اشباع نشده (زیر 70)
7. ✅ BOS صعودی در 5m یا 15m
8. ✅ حجم بالای میانگین
9. ✅ EMA Stack صعودی در 15m
10. ✅ BTC هم‌جهت یا neutral
11. ✅ کراس صعودی VWAP (بونوس)

### SHORT (برعکس)

---

## 🎯 سطوح معامله

| سطح | LONG | SHORT |
|-----|------|-------|
| Entry | قیمت فعلی | قیمت فعلی |
| SL | زیر Swing Low / Bull OB | بالای Swing High / Bear OB |
| TP1 | +1.5R | -1.5R |
| TP2 | +2.5R یا Bear OB | -2.5R یا Bull OB |
| TP3 | +4R | -4R |

---

## 📱 دستورات تلگرام

| دستور | توضیح |
|-------|-------|
| /start | شروع و راهنما |
| /winrate | گزارش وین‌ریت کامل |
| /trades | معاملات باز |
| /stats | آمار کلی |

---

## 📈 وین‌ریت

- TP1 و TP2 جداگانه ردیابی میشن
- آمار بر اساس نماد، جهت (LONG/SHORT) و کانفیدنس
- معاملات بیشتر از ۴۸ ساعت خودکار بسته میشن
- دیتابیس در `data/trades.json` ذخیره میشه

---

## ⚠️ نکات مهم

- این ربات **سیگنال** میده، نه اجرای خودکار معامله
- همیشه **مدیریت ریسک** را رعایت کنید
- با اهرم بالا فقط روی سیگنال‌های HIGH وارد شوید
- BTC را همیشه به عنوان فیلتر اصلی در نظر بگیرید
