"""
ZandiBot Telegram Bot — نسخه امن
دکمه‌های ثابت پایین + امنیت Webhook + تشخیص ادمین
"""

import requests
import time
import json
import os
import sys
import hashlib
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOT_TOKEN   = "8681715370:AAGgpqThXK2SpdxA8WE7ZrAZDoEJfqrUJ8s"
ADMIN_IDS   = ["1813614997"]
BASE_URL    = "https://api.telegram.org/bot{}".format(BOT_TOKEN)
USERS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/tg_users.json")


# ─────────────────────────────────────────
# امنیت
# ─────────────────────────────────────────

def security_check():
    """حذف webhook مخرب + بررسی امنیت در شروع"""
    try:
        r = requests.get("{}/getWebhookInfo".format(BASE_URL), timeout=10).json()
        url = r.get("result", {}).get("url", "")
        if url:
            print("⚠️ Webhook فعال پیدا شد: {}".format(url))
            requests.get("{}/deleteWebhook".format(BASE_URL), timeout=10)
            print("🔒 Webhook حذف شد")

            for adm_id in ADMIN_IDS:
                send(adm_id,
                    "🚨 <b>هشدار امنیتی!</b>\n\n"
                    "یک Webhook مشکوک روی ربات پیدا و حذف شد:\n"
                    "<code>{}</code>\n\n"
                    "اگه شما تنظیم نکردید، توکن ربات رو از BotFather عوض کنید!".format(url))
        else:
            print("🔒 امنیت OK — بدون Webhook")
    except Exception as e:
        print("⚠️ خطا در بررسی امنیت: {}".format(e))


def _allowed_update(update):
    """فیلتر آپدیت‌های مشکوک"""
    if "message" in update:
        chat_id = str(update["message"]["chat"]["id"])
        text = update["message"].get("text", "")
        if len(text) > 4096:
            return False
    return True


# ─────────────────────────────────────────
# کاربران
# ─────────────────────────────────────────

def load_users():
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE) as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def is_admin(chat_id):
    return str(chat_id) in ADMIN_IDS

def register_user(chat_id, username, first_name):
    users = load_users()
    uid = str(chat_id)
    if uid not in users:
        users[uid] = {
            "chat_id": uid, "username": username, "first_name": first_name,
            "active": False, "plan": "trial",
            "symbols": ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT"],
            "notify_tp1": True, "notify_tp2": True, "notify_sl": True,
            "joined_at": datetime.utcnow().isoformat(),
        }
        save_users(users)
        for adm_id in ADMIN_IDS:
            send(adm_id, "👤 <b>کاربر جدید!</b>\n\n{} (@{})\nID: <code>{}</code>".format(
                first_name, username or "—", uid))
    return users[uid]


# ─────────────────────────────────────────
# ارسال پیام
# ─────────────────────────────────────────

def send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post("{}/sendMessage".format(BASE_URL), json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print("خطا: {}".format(e))
        return {}

def edit_msg(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post("{}/editMessageText".format(BASE_URL), json=payload, timeout=10)
    except: pass

def answer_cb(cb_id, text="", alert=False):
    try:
        requests.post("{}/answerCallbackQuery".format(BASE_URL),
            json={"callback_query_id": cb_id, "text": text, "show_alert": alert}, timeout=5)
    except: pass


# ─────────────────────────────────────────
# کیبورد ثابت پایین (ReplyKeyboard)
# ─────────────────────────────────────────

def kb_reply(adm=False):
    """دکمه‌های ثابت پایین صفحه"""
    rows = [
        ["🎯 سیگنال‌ها", "📊 وین‌ریت"],
        ["🪙 ارزهای من", "⚙️ تنظیمات"],
        ["📈 آمار کلی", "❓ راهنما"],
    ]
    if adm:
        rows.append(["👑 پنل ادمین"])
    return {"keyboard": rows, "resize_keyboard": True, "is_persistent": True}


# ─────────────────────────────────────────
# کیبوردهای اینلاین (برای زیرمنوها)
# ─────────────────────────────────────────

def kb_inline_main(adm):
    rows = [
        [{"text":"🎯 سیگنال‌های باز","callback_data":"open_signals"},
         {"text":"📊 وین‌ریت","callback_data":"my_winrate"}],
        [{"text":"🪙 ارزهای من","callback_data":"my_symbols"},
         {"text":"⚙️ تنظیمات","callback_data":"settings"}],
        [{"text":"📈 آمار کلی","callback_data":"global_stats"},
         {"text":"❓ راهنما","callback_data":"help"}],
        [{"text":"🌐 داشبورد وب","web_app":{"url":"https://zandibot.it.com/dashboard"}}],
    ]
    if adm:
        rows.append([{"text":"👑 پنل ادمین","callback_data":"admin_panel"}])
    return {"inline_keyboard": rows}

def kb_admin():
    return {"inline_keyboard": [
        [{"text":"👥 کاربران","callback_data":"admin_users"},
         {"text":"🎯 سیگنال‌ها","callback_data":"admin_signals"}],
        [{"text":"📊 آمار سیستم","callback_data":"admin_stats"},
         {"text":"🔄 ری‌استارت","callback_data":"admin_restart"}],
        [{"text":"📢 ارسال همگانی","callback_data":"admin_broadcast"},
         {"text":"💎 مدیریت اشتراک","callback_data":"admin_plans"}],
        [{"text":"🔒 چک امنیت","callback_data":"admin_security"}],
        [{"text":"🌐 پنل وب","url":"http://zandibot.it.com/admin"}],
        [{"text":"◀️ بازگشت","callback_data":"main_menu"}],
    ]}

def kb_back(to="main_menu"):
    return {"inline_keyboard": [[{"text":"◀️ بازگشت","callback_data":to}]]}

def kb_symbols(user_syms):
    ALL = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT","DOGEUSDT","LINKUSDT"]
    rows = [[{"text":"{} {}".format('✅' if s in user_syms else '⬜', s),"callback_data":"sym_{}".format(s)}] for s in ALL]
    rows.append([{"text":"💾 ذخیره","callback_data":"save_symbols"},
                 {"text":"◀️ بازگشت","callback_data":"settings"}])
    return {"inline_keyboard": rows}

def kb_settings():
    return {"inline_keyboard": [
        [{"text":"🔔 TP1","callback_data":"toggle_tp1"},
         {"text":"🔔 TP2","callback_data":"toggle_tp2"}],
        [{"text":"🔕 SL","callback_data":"toggle_sl"},
         {"text":"🪙 ارزها","callback_data":"my_symbols"}],
        [{"text":"◀️ بازگشت","callback_data":"main_menu"}],
    ]}


# ─────────────────────────────────────────
# فرمت پیام
# ─────────────────────────────────────────

def fmt_signal(sig):
    d = "🟢" if sig.get("direction")=="LONG" else "🔴"
    ce = {"HIGH":"🔥","MEDIUM":"⚡","LOW":"🔹"}.get(sig.get("confidence",""),"")
    sc = sig.get("score", 0)
    filled = int(round(sc))
    bar = "█" * filled + "░" * (10 - filled)
    sl_pct = ""
    entry = sig.get("entry", 0)
    sl = sig.get("stop_loss", 0)
    if entry and sl:
        sl_pct = "  ({:.2f}%)".format(abs(entry-sl)/entry*100)
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🪙 <b>{}</b>  {} <b>{}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💰 <b>ورود:</b>  <code>{}</code>\n"
        "🔴 <b>استاپ:</b> <code>{}</code>{}\n\n"
        "🎯 <b>تارگت‌ها:</b>\n"
        "  🟡 TP1: <code>{}</code>\n"
        "  🟠 TP2: <code>{}</code>\n"
        "  🟢 TP3: <code>{}</code>\n\n"
        "📊 R/R: <code>{}R</code>  {} <b>{}</b>\n"
        "🎯 امتیاز: <code>{}/10</code>  [{}]\n"
        "📈 احتمال: <code>{}%</code>\n"
        "🔗 لوریج: <code>{}x</code>\n"
    ).format(
        sig.get('symbol'), d, sig.get('direction'),
        entry, sl, sl_pct,
        sig.get('tp1'), sig.get('tp2'), sig.get('tp3'),
        sig.get('rr'), ce, sig.get('confidence'),
        sc, bar,
        sig.get('probability', 0),
        sig.get('leverage', 5),
    )


def fmt_welcome(name, adm):
    role = "👑 <b>ادمین</b>" if adm else "🔹 کاربر"
    return (
        "⚡ <b>خوش آمدید به ZandiBot</b>\n\n"
        "سلام <b>{}</b> عزیز!\n"
        "نقش: {}\n\n"
        "🤖 دستیار هوشمند سیگنال‌دهی کریپتو\n"
        "📊 تحلیل ۴ تایم‌فریم | ۱۰ شرط تأیید\n"
        "🔒 محافظت امنیتی فعال\n\n"
        "از دکمه‌های پایین استفاده کنید 👇"
    ).format(name, role)


# ─────────────────────────────────────────
# state
# ─────────────────────────────────────────
user_states = {}


# ─────────────────────────────────────────
# پردازش دکمه‌های متنی (ReplyKeyboard)
# ─────────────────────────────────────────

def handle_text(chat_id, text, user_d):
    adm = is_admin(chat_id)

    if text == "🎯 سیگنال‌ها":
        try:
            from signals.tracker import get_open_trades
            signals = get_open_trades()
        except: signals = []
        if not signals:
            send(chat_id, "📭 <b>سیگنال باز فعالی وجود ندارد</b>\n\nاسکن هر ۱۵ دقیقه انجام میشه.")
        else:
            txt = "🎯 <b>{} سیگنال باز</b>\n━━━━━━━━━━━━━━━━━━━━\n\n".format(len(signals))
            for s in signals[:5]:
                d = "🟢" if s.get("direction")=="LONG" else "🔴"
                txt += "{} <b>{}</b> | <code>{}</code>\n".format(d, s.get('symbol'), s.get('entry'))
                txt += "  TP1: <code>{}</code> | SL: <code>{}</code>\n\n".format(s.get('tp1'), s.get('stop_loss'))
            send(chat_id, txt)

    elif text == "📊 وین‌ریت":
        try:
            from signals.tracker import get_stats
            st = get_stats()
        except: st = {}
        send(chat_id,
            "📊 <b>وین‌ریت ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "📈 کل: <code>{}</code>  |  باز: <code>{}</code>\n"
            "✅ TP1: <b>{}%</b>  ({} بار)\n"
            "✅ TP2: <b>{}%</b>  ({} بار)\n"
            "❌ SL: <code>{}</code> بار\n"
            "💹 میانگین R/R: <code>{}R</code>".format(
                st.get('total',0), st.get('open',0),
                st.get('winrate_tp1',0), st.get('tp1_hit',0),
                st.get('winrate_tp2',0), st.get('tp2_hit',0),
                st.get('sl_hit',0), st.get('avg_rr',0)))

    elif text == "🪙 ارزهای من":
        user = load_users().get(str(chat_id), {})
        syms = user.get("symbols", ["BTCUSDT","ETHUSDT"])
        send(chat_id, "🪙 <b>ارزهای فعال شما</b>\n\n✅ = فعال | ⬜ = غیرفعال", kb_symbols(syms))

    elif text == "⚙️ تنظیمات":
        user = load_users().get(str(chat_id), {})
        tp1 = "✅" if user.get("notify_tp1",True) else "❌"
        tp2 = "✅" if user.get("notify_tp2",True) else "❌"
        sl  = "✅" if user.get("notify_sl",True) else "❌"
        send(chat_id,
            "⚙️ <b>تنظیمات شما</b>\n\nTP1: {}  |  TP2: {}  |  SL: {}".format(tp1, tp2, sl),
            kb_settings())

    elif text == "📈 آمار کلی":
        try:
            from signals.tracker import get_stats
            st = get_stats()
        except: st = {}
        send(chat_id,
            "📊 <b>آمار کلی سیستم</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 کل: <b>{}</b>  |  باز: <b>{}</b>\n"
            "✅ وین‌ریت TP1: <b>{}%</b>\n"
            "💹 R/R: <b>{}R</b>\n"
            "🤖 ربات: <b>فعال ✅</b>\n"
            "🔒 امنیت: <b>فعال ✅</b>".format(
                st.get('total',0), st.get('open',0),
                st.get('winrate_tp1',0), st.get('avg_rr',0)))

    elif text == "❓ راهنما":
        send(chat_id,
            "❓ <b>راهنمای ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <b>سیگنال‌ها</b> — مشاهده سیگنال‌های فعال\n"
            "📊 <b>وین‌ریت</b> — آمار عملکرد سیستم\n"
            "🪙 <b>ارزهای من</b> — انتخاب ارزهای دریافتی\n"
            "⚙️ <b>تنظیمات</b> — کنترل اطلاع‌رسانی\n"
            "📈 <b>آمار کلی</b> — وضعیت کلی ربات\n\n"
            "🌐 <a href='https://zandibot.it.com'>zandibot.it.com</a>")

    elif text == "👑 پنل ادمین" and adm:
        send(chat_id,
            "👑 <b>پنل ادمین ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🕐 <code>{}</code>  📅 <code>{}</code>\n\n"
            "انتخاب کنید:".format(
                datetime.now().strftime('%H:%M:%S'),
                datetime.now().strftime('%Y-%m-%d')),
            kb_admin())

    else:
        return False
    return True


# ─────────────────────────────────────────
# پردازش Callback (اینلاین)
# ─────────────────────────────────────────

def handle_cb(chat_id, cb_id, data, msg_id, user_d):
    adm = is_admin(chat_id)

    if data == "main_menu":
        answer_cb(cb_id)
        edit_msg(chat_id, msg_id, fmt_welcome(user_d.get("first_name","کاربر"), adm), kb_inline_main(adm))

    elif data == "open_signals":
        answer_cb(cb_id, "در حال دریافت...")
        try:
            from signals.tracker import get_open_trades
            signals = get_open_trades()
        except: signals = []
        if not signals:
            edit_msg(chat_id, msg_id, "📭 <b>سیگنال باز فعالی وجود ندارد</b>\n\nاسکن بعدی: ۱۵ دقیقه دیگر", kb_back())
        else:
            txt = "🎯 <b>{} سیگنال باز</b>\n━━━━━━━━━━━━━━━━━━━━\n\n".format(len(signals))
            for s in signals[:5]:
                d = "🟢" if s.get("direction")=="LONG" else "🔴"
                txt += "{} <b>{}</b> | <code>{}</code>\n".format(d, s.get('symbol'), s.get('entry'))
                txt += "  TP1: <code>{}</code> | SL: <code>{}</code>\n\n".format(s.get('tp1'), s.get('stop_loss'))
            edit_msg(chat_id, msg_id, txt, kb_back())

    elif data == "my_winrate":
        answer_cb(cb_id, "در حال محاسبه...")
        try:
            from signals.tracker import get_stats
            st = get_stats()
        except: st = {}
        text = (
            "📊 <b>وین‌ریت ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "📈 کل: <code>{}</code>  |  باز: <code>{}</code>\n"
            "✅ TP1: <b>{}%</b>  ({} بار)\n"
            "✅ TP2: <b>{}%</b>  ({} بار)\n"
            "❌ SL: <code>{}</code> بار\n"
            "💹 میانگین R/R: <code>{}R</code>"
        ).format(st.get('total',0), st.get('open',0),
                 st.get('winrate_tp1',0), st.get('tp1_hit',0),
                 st.get('winrate_tp2',0), st.get('tp2_hit',0),
                 st.get('sl_hit',0), st.get('avg_rr',0))
        edit_msg(chat_id, msg_id, text, kb_back())

    elif data == "my_symbols":
        answer_cb(cb_id)
        user = load_users().get(str(chat_id), {})
        syms = user.get("symbols", ["BTCUSDT","ETHUSDT"])
        edit_msg(chat_id, msg_id, "🪙 <b>ارزهای فعال شما</b>\n\n✅ = فعال | ⬜ = غیرفعال", kb_symbols(syms))

    elif data.startswith("sym_"):
        sym = data[4:]
        users = load_users()
        uid = str(chat_id)
        if uid not in users: users[uid] = {}
        syms = users[uid].get("symbols", [])
        if sym in syms:
            syms.remove(sym)
            answer_cb(cb_id, "❌ {} غیرفعال شد".format(sym))
        else:
            syms.append(sym)
            answer_cb(cb_id, "✅ {} فعال شد".format(sym))
        users[uid]["symbols"] = syms
        save_users(users)
        try:
            requests.post("{}/editMessageReplyMarkup".format(BASE_URL), json={
                "chat_id":chat_id,"message_id":msg_id,
                "reply_markup":json.dumps(kb_symbols(syms))
            }, timeout=5)
        except: pass

    elif data == "save_symbols":
        answer_cb(cb_id, "✅ ارزها ذخیره شدند!", alert=True)

    elif data == "settings":
        answer_cb(cb_id)
        user = load_users().get(str(chat_id), {})
        tp1 = "✅" if user.get("notify_tp1",True) else "❌"
        tp2 = "✅" if user.get("notify_tp2",True) else "❌"
        sl  = "✅" if user.get("notify_sl",True) else "❌"
        edit_msg(chat_id, msg_id,
            "⚙️ <b>تنظیمات شما</b>\n\nTP1: {}  |  TP2: {}  |  SL: {}".format(tp1, tp2, sl),
            kb_settings())

    elif data.startswith("toggle_"):
        key = "notify_" + data[7:]
        users = load_users()
        uid = str(chat_id)
        if uid not in users: users[uid] = {}
        val = not users[uid].get(key, True)
        users[uid][key] = val
        save_users(users)
        answer_cb(cb_id, "{'✅ فعال' if val else '❌ غیرفعال'} شد".format('✅ فعال' if val else '❌ غیرفعال'))
        handle_cb(chat_id, cb_id, "settings", msg_id, user_d)

    elif data == "global_stats":
        answer_cb(cb_id, "...")
        try:
            from signals.tracker import get_stats
            st = get_stats()
        except: st = {}
        edit_msg(chat_id, msg_id,
            "📊 <b>آمار کلی سیستم</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 کل: <b>{}</b>  |  باز: <b>{}</b>\n"
            "✅ وین‌ریت TP1: <b>{}%</b>\n"
            "💹 R/R: <b>{}R</b>\n"
            "🤖 ربات: <b>فعال ✅</b>".format(
                st.get('total',0), st.get('open',0),
                st.get('winrate_tp1',0), st.get('avg_rr',0)),
            kb_back())

    elif data == "help":
        answer_cb(cb_id)
        edit_msg(chat_id, msg_id,
            "❓ <b>راهنمای ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <b>سیگنال‌های باز</b> — مشاهده سیگنال‌های فعال\n"
            "📊 <b>وین‌ریت</b> — آمار عملکرد سیستم\n"
            "🪙 <b>ارزهای من</b> — انتخاب ارزهای دریافتی\n"
            "⚙️ <b>تنظیمات</b> — کنترل اطلاع‌رسانی\n\n"
            "🌐 <a href='https://zandibot.it.com'>zandibot.it.com</a>", kb_back())

    # ── ادمین ──

    elif data == "admin_panel":
        if not adm:
            answer_cb(cb_id, "⛔ دسترسی ندارید!", alert=True); return
        answer_cb(cb_id)
        edit_msg(chat_id, msg_id,
            "👑 <b>پنل ادمین ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🕐 <code>{}</code>  📅 <code>{}</code>\n\n"
            "انتخاب کنید:".format(
                datetime.now().strftime('%H:%M:%S'),
                datetime.now().strftime('%Y-%m-%d')),
            kb_admin())

    elif data == "admin_users":
        if not adm: answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "...")
        users = load_users()
        text = "👥 <b>کاربران ({}):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n".format(len(users))
        rows = []
        for uid, u in list(users.items())[:10]:
            st = "✅" if u.get("active") else "⏳"
            text += "{} <b>{}</b> | {} | <code>{}</code>\n".format(st, u.get('first_name','?'), u.get('plan','?'), uid)
            rows.append([{"text": "{} {}".format('✅' if u.get('active') else '❌', u.get('first_name','?')), "callback_data": "user_detail_{}".format(uid)}])
        rows.append([{"text": "◀️ بازگشت", "callback_data": "admin_panel"}])
        edit_msg(chat_id, msg_id, text, {"inline_keyboard": rows})

    elif data.startswith("user_detail_"):
        if not adm: answer_cb(cb_id, "⛔", alert=True); return
        uid = data[len("user_detail_"):]
        answer_cb(cb_id)
        users = load_users()
        u = users.get(uid, {})
        st = "✅ فعال" if u.get("active") else "❌ غیرفعال"
        text = (
            "👤 <b>{}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "🆔 <code>{}</code>\n"
            "📛 @{}\n"
            "📦 پلن: <b>{}</b>\n"
            "وضعیت: <b>{}</b>\n"
            "📅 عضویت: <code>{}</code>"
        ).format(u.get('first_name','?'), uid, u.get('username','—'),
                 u.get('plan','trial'), st, u.get('joined_at','—'))
        kb = {"inline_keyboard": [
            [{"text": "✅ فعال", "callback_data": "activate_{}".format(uid)},
             {"text": "❌ غیرفعال", "callback_data": "deactivate_{}".format(uid)}],
            [{"text": "💎 VIP", "callback_data": "plan_vip_{}".format(uid)},
             {"text": "⚡ حرفه‌ای", "callback_data": "plan_pro_{}".format(uid)},
             {"text": "📦 پایه", "callback_data": "plan_basic_{}".format(uid)}],
            [{"text": "◀️ بازگشت", "callback_data": "admin_users"}],
        ]}
        edit_msg(chat_id, msg_id, text, kb)

    elif data == "admin_stats":
        if not adm: answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "...")
        users = load_users()
        try:
            from signals.tracker import get_stats
            st = get_stats()
        except: st = {}
        edit_msg(chat_id, msg_id,
            "📊 <b>آمار کامل</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "👥 کاربران: <b>{}</b>  |  فعال: <b>{}</b>\n"
            "🎯 سیگنال: <b>{}</b>\n"
            "📈 وین‌ریت: <b>{}%</b>\n"
            "🤖 ربات: <b>فعال ✅</b>\n"
            "🔒 امنیت: <b>فعال ✅</b>".format(
                len(users), sum(1 for u in users.values() if u.get('active')),
                st.get('total',0), st.get('winrate_tp1',0)),
            kb_back("admin_panel"))

    elif data == "admin_signals":
        if not adm: answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "...")
        try:
            from signals.tracker import get_open_trades
            sigs = get_open_trades()
        except: sigs = []
        text = "🎯 <b>سیگنال‌های باز: {}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n".format(len(sigs))
        for s in sigs[:5]:
            d = "🟢" if s.get("direction")=="LONG" else "🔴"
            text += "{} <b>{}</b> | <code>{}</code> | {}/10\n".format(d, s.get('symbol'), s.get('entry'), s.get('score',0))
        edit_msg(chat_id, msg_id, text, kb_back("admin_panel"))

    elif data == "admin_restart":
        if not adm: answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "🔄 ری‌استارت...", alert=True)
        send(chat_id, "🔄 <b>ربات ری‌استارت می‌شود...</b>")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    elif data == "admin_broadcast":
        if not adm: answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id)
        user_states[str(chat_id)] = "awaiting_broadcast"
        edit_msg(chat_id, msg_id, "📢 <b>ارسال همگانی</b>\n\nمتن پیام را بفرستید:", kb_back("admin_panel"))

    elif data == "admin_plans":
        if not adm: answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id)
        users = load_users()
        text = "💎 <b>مدیریت اشتراک‌ها</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        plans = {}
        for u in users.values():
            p = u.get("plan","trial")
            plans[p] = plans.get(p,0) + 1
        for p, count in plans.items():
            text += "• {}: <b>{}</b> کاربر\n".format(p, count)
        edit_msg(chat_id, msg_id, text, kb_back("admin_panel"))

    elif data == "admin_security":
        if not adm: answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "🔒 بررسی...")
        security_check()
        edit_msg(chat_id, msg_id, "🔒 <b>بررسی امنیت انجام شد</b>\n\nWebhook حذف شد (اگه وجود داشت).", kb_back("admin_panel"))

    elif data.startswith("activate_"):
        if not adm: return
        uid = data[9:]
        users = load_users()
        if uid in users:
            users[uid]["active"] = True
            save_users(users)
            answer_cb(cb_id, "✅ فعال شد!", alert=True)
            send(uid, "🎉 <b>حساب شما فعال شد!</b>\nاکنون سیگنال‌ها را دریافت می‌کنید.")

    elif data.startswith("deactivate_"):
        if not adm: return
        uid = data[11:]
        users = load_users()
        if uid in users:
            users[uid]["active"] = False
            save_users(users)
            answer_cb(cb_id, "❌ غیرفعال شد", alert=True)

    elif data.startswith("plan_"):
        if not adm: return
        parts = data.split("_")
        plan = parts[1]
        uid = parts[2]
        users = load_users()
        if uid in users:
            users[uid]["plan"] = plan
            users[uid]["active"] = True
            save_users(users)
            answer_cb(cb_id, "💎 پلن {} تنظیم شد!".format(plan), alert=True)
            send(uid, "💎 <b>پلن شما به {} ارتقا یافت!</b>".format(plan))


# ─────────────────────────────────────────
# ارسال سیگنال و نوتیف
# ─────────────────────────────────────────

def broadcast_signal(signal):
    users = load_users()
    sig_dict = signal.__dict__ if hasattr(signal,'__dict__') else signal
    text = fmt_signal(sig_dict) + "\n⚠️ <i>مدیریت ریسک را رعایت کنید</i>"
    sent = 0
    for uid, user in users.items():
        if not user.get("active") and uid not in ADMIN_IDS: continue
        sym = sig_dict.get('symbol','')
        if sym not in user.get("symbols",[]): continue
        if send(uid, text).get("ok"): sent += 1
        time.sleep(0.05)
    print("📨 سیگنال به {} کاربر ارسال شد".format(sent))
    return sent


def broadcast_tp_sl(trade, hit):
    users = load_users()
    emoji = {"TP1":"🟡","TP2":"🟠","TP3":"🏆","SL":"❌"}.get(hit, "📍")
    default_pnl = {"TP1": 1.5, "TP2": 2.5, "TP3": 4.0, "SL": -1.0}.get(hit, 0)
    pnl = trade.get("pnl_r") or default_pnl
    pnl_str = "+{}R".format(pnl) if pnl > 0 else "{}R".format(pnl)

    entry = trade.get("entry", 0)
    exit_p = trade.get("exit_price", 0)
    if not exit_p or exit_p <= 0:
        if hit == "SL":
            exit_p = trade.get("stop_loss", 0)
        elif hit == "TP1":
            exit_p = trade.get("tp1", 0)
        elif hit == "TP2":
            exit_p = trade.get("tp2", 0)
        elif hit == "TP3":
            exit_p = trade.get("tp3", 0)

    pnl_pct = ""
    if entry and exit_p:
        pct = abs(exit_p - entry) / entry * 100
        pnl_pct = " ({:.2f}%)".format(pct)

    text = (
        "{} <b>{} زده شد!</b>\n\n"
        "🪙 <b>{}</b> | {}\n"
        "📍 ورود: <code>{}</code>\n"
        "🎯 قیمت خروج: <code>{}</code>{}\n"
        "💰 نتیجه: <code>{}</code>"
    ).format(emoji, hit, trade.get('symbol'), trade.get('direction'),
             entry, exit_p, pnl_pct, pnl_str)

    nk_map = {"TP1": "notify_tp1", "TP2": "notify_tp2", "TP3": "notify_tp2", "SL": "notify_sl"}
    nk = nk_map.get(hit, "notify_tp1")

    for uid, user in users.items():
        if not user.get("active") and uid not in ADMIN_IDS: continue
        if not user.get(nk, True): continue
        if trade.get("symbol") not in user.get("symbols", []): continue
        send(uid, text)
        time.sleep(0.05)


# ─────────────────────────────────────────
# دریافت آپدیت
# ─────────────────────────────────────────

def get_updates(offset=0):
    try:
        r = requests.get("{}/getUpdates".format(BASE_URL), params={"offset":offset,"timeout":30}, timeout=35)
        return r.json().get("result",[])
    except: return []


def process_update(update):
    if not _allowed_update(update):
        return

    if "message" in update:
        msg     = update["message"]
        chat_id = str(msg["chat"]["id"])
        text    = msg.get("text","")
        user_d  = msg.get("from",{})

        # ارسال همگانی
        if user_states.get(chat_id) == "awaiting_broadcast" and is_admin(chat_id):
            user_states.pop(chat_id, None)
            users = load_users()
            sent = 0
            for uid in users:
                if users[uid].get("active") or uid in ADMIN_IDS:
                    send(uid, "📢 <b>پیام از ادمین:</b>\n\n{}".format(text))
                    sent += 1
                    time.sleep(0.05)
            send(chat_id, "✅ پیام به <b>{}</b> کاربر ارسال شد.".format(sent))
            return

        # دستورات
        if text == "/start":
            register_user(chat_id, user_d.get("username",""), user_d.get("first_name","کاربر"))
            adm = is_admin(chat_id)
            send(chat_id, fmt_welcome(user_d.get("first_name","کاربر"), adm), kb_reply(adm))
            send(chat_id, "از دکمه‌های زیر استفاده کنید:", kb_inline_main(adm))
        elif text == "/menu":
            adm = is_admin(chat_id)
            send(chat_id, fmt_welcome(user_d.get("first_name","کاربر"), adm), kb_reply(adm))
        elif text == "/admin" and is_admin(chat_id):
            send(chat_id, "👑 <b>پنل ادمین</b>", kb_admin())
        elif text == "/security" and is_admin(chat_id):
            security_check()
            send(chat_id, "🔒 بررسی امنیت انجام شد.")
        elif text == "/users" and is_admin(chat_id):
            users = load_users()
            t = "👥 <b>کاربران ({}):</b>\n\n".format(len(users))
            for uid, u in users.items():
                t += "• {} | {} | {}\n".format(
                    u.get('first_name','?'), u.get('plan','?'),
                    '✅' if u.get('active') else '⏳')
            send(chat_id, t)
        else:
            if not handle_text(chat_id, text, user_d):
                pass

    elif "callback_query" in update:
        cb = update["callback_query"]
        handle_cb(str(cb["from"]["id"]), cb["id"], cb.get("data",""),
                  cb["message"]["message_id"], cb.get("from",{}))


# ─────────────────────────────────────────
# Alias توابع (سازگاری با main.py)
# ─────────────────────────────────────────

def send_signal(signal):
    sent = broadcast_signal(signal)
    return sent > 0

def send_message(text):
    ok = False
    for adm_id in ADMIN_IDS:
        r = send(adm_id, text)
        if r.get("ok"):
            ok = True
    return ok

def send_tp_notification(trade, hit):
    broadcast_tp_sl(trade, hit)

def handle_commands():
    run()


# ─────────────────────────────────────────
# اجرا
# ─────────────────────────────────────────

def run():
    print("🤖 ZandiBot Telegram شروع شد")

    # بررسی امنیت اول
    security_check()

    r = requests.get("{}/getMe".format(BASE_URL), timeout=10).json()
    if r.get("ok"):
        bot = r["result"]
        print("✅ متصل: @{}".format(bot['username']))
        for adm_id in ADMIN_IDS:
            send(adm_id,
                "🚀 <b>ZandiBot راه‌اندازی شد</b>\n\n"
                "🕐 <code>{}</code>\n"
                "🔒 امنیت: بررسی شد ✅\n"
                "👑 شما ادمین این ربات هستید".format(
                    datetime.now().strftime('%H:%M:%S')),
                kb_reply(True))
    else:
        print("❌ خطا: {}".format(r))
        return

    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for u in updates:
                offset = u["update_id"] + 1
                threading.Thread(target=process_update, args=(u,), daemon=True).start()
        except KeyboardInterrupt:
            print("\n⛔ متوقف شد")
            break
        except Exception as e:
            print("⚠️ {}".format(e))
            time.sleep(5)


if __name__ == "__main__":
    run()
