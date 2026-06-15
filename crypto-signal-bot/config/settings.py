"""
تنظیمات کلی ربات سیگنال
"""

# ─── صرافی ───
EXCHANGE = "bitunix"
BASE_URL = "https://fapi.bitunix.com"

# ─── جفت ارزهای پیش‌فرض برای آنالیز ───
SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
]

# ─── بازه زمانی پیش‌فرض ───
DEFAULT_INTERVAL = "15m"
DEFAULT_LIMIT = 200  # تعداد کندل برای آنالیز

# ─── تلگرام (بعداً پر می‌کنیم) ───
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID = ""

# ─── آستانه سیگنال ───
RSI_OVERSOLD = 30       # زیر این = سیگنال BUY
RSI_OVERBOUGHT = 70     # بالای این = سیگنال SELL
MIN_SIGNAL_STRENGTH = 2  # حداقل تعداد تاییدیه برای صدور سیگنال
