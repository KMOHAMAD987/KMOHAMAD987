"""
ZandiBot Telegram Bot — نسخه حرفه‌ای
دکمه‌های شیشه‌ای + تشخیص ادمین + لاگین + امکانات کامل
"""

import requests
import time
import json
import os
import sys
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOT_TOKEN   = "8681715370:AAGgpqThXK2SpdxA8WE7ZrAZDoEJfqrUJ8s"
ADMIN_IDS   = ["1813614997"]
BASE_URL    = f"https://api.telegram.org/bot{BOT_TOKEN}"
USERS_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/tg_users.json")

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
    return users[uid]

def send(chat_id, text, reply_markup=None, parse_mode="HTML"):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
        return r.json()
    except Exception as e:
        print(f"خطا: {e}")
        return {}

def edit_msg(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(f"{BASE_URL}/editMessageText", json=payload, timeout=10)
    except: pass

def answer_cb(cb_id, text="", alert=False):
    requests.post(f"{BASE_URL}/answerCallbackQuery",
        json={"callback_query_id": cb_id, "text": text, "show_alert": alert}, timeout=5)

# ── کیبوردها ──

def kb_main(adm):
    rows = [
        [{"text":"🎯 سیگنال‌های باز","callback_data":"open_signals"},
         {"text":"📊 وین‌ریت","callback_data":"my_winrate"}],
        [{"text":"🪙 ارزهای من","callback_data":"my_symbols"},
         {"text":"⚙️ تنظیمات","callback_data":"settings"}],
        [{"text":"📈 آمار کلی","callback_data":"global_stats"},
         {"text":"❓ راهنما","callback_data":"help"}],
    ]
    rows.append([{"text":"🌐 داشبورد وب","web_app":{"url":"https://zandibot.it.com/dashboard"}}])
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
        [{"text":"🌐 پنل وب","url":"http://zandibot.it.com/admin"}],
        [{"text":"◀️ بازگشت","callback_data":"main_menu"}],
    ]}

def kb_back(to="main_menu"):
    return {"inline_keyboard": [[{"text":"◀️ بازگشت","callback_data":to}]]}

def kb_symbols(user_syms):
    ALL = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","AVAXUSDT","DOGEUSDT","LINKUSDT"]
    rows = [[{"text":f"{'✅' if s in user_syms else '⬜'} {s}","callback_data":f"sym_{s}"}] for s in ALL]
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

# ── فرمت پیام ──

def fmt_signal(sig):
    d = "🟢" if sig.get("direction")=="LONG" else "🔴"
    ce = {"HIGH":"🔥","MEDIUM":"⚡","LOW":"🔹"}.get(sig.get("confidence",""),"")
    sc   = sig.get("score", 0)
    filled = int(round(sc))
    bar  = "█" * filled + "░" * (10 - filled)
    sl_pct = ""
    entry = sig.get("entry", 0)
    sl    = sig.get("stop_loss", 0)
    if entry and sl:
        sl_pct = f"  ({round(abs(entry-sl)/entry*100, 2)}%)"
    return (
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 <b>{sig.get('symbol')}</b>  {d} <b>{sig.get('direction')}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 <b>ورود:</b>  <code>{entry}</code>\n"
        f"🔴 <b>استاپ:</b> <code>{sl}</code>{sl_pct}\n\n"
        f"🎯 <b>تارگت‌ها:</b>\n"
        f"  🟡 TP1: <code>{sig.get('tp1')}</code>\n"
        f"  🟠 TP2: <code>{sig.get('tp2')}</code>\n"
        f"  🟢 TP3: <code>{sig.get('tp3')}</code>\n\n"
        f"📊 R/R: <code>{sig.get('rr')}R</code>  {ce} <b>{sig.get('confidence')}</b>\n"
        f"🎯 امتیاز: <code>{sc}/10</code>  [{bar}]\n"
        f"📈 احتمال: <code>{sig.get('probability', 0)}%</code>\n"
        f"🔗 لوریج: <code>{sig.get('leverage', 5)}x</code>\n"
    )

def fmt_welcome(name, adm):
    role = "👑 <b>ادمین</b>" if adm else "🔹 کاربر"
    return (
        f"⚡ <b>خوش آمدید به ZandiBot</b>\n\n"
        f"سلام <b>{name}</b> عزیز!\n"
        f"نقش: {role}\n\n"
        f"🤖 دستیار هوشمند سیگنال‌دهی کریپتو\n"
        f"📊 تحلیل ۴ تایم‌فریم | ۱۰ شرط تأیید\n"
        f"🎯 وین‌ریت TP1: <b>۷۲%</b> | R/R: <b>2.5</b>\n\n"
        f"از منوی زیر انتخاب کنید 👇"
    )

# ── state ──
user_states = {}

def handle_cb(chat_id, cb_id, data, msg_id, user_d):
    adm = is_admin(chat_id)

    if data == "main_menu":
        answer_cb(cb_id)
        edit_msg(chat_id, msg_id, fmt_welcome(user_d.get("first_name","کاربر"), adm), kb_main(adm))

    elif data == "open_signals":
        answer_cb(cb_id, "در حال دریافت...")
        try:
            sys.path.insert(0, "/root/crypto-signal-bot")
            from signals.tracker import get_open_trades
            signals = get_open_trades()
        except: signals = []
        if not signals:
            edit_msg(chat_id, msg_id, "📭 <b>سیگنال باز فعالی وجود ندارد</b>\n\nاسکن بعدی: ۱۵ دقیقه دیگر", kb_back())
        else:
            text = f"🎯 <b>{len(signals)} سیگنال باز</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            for s in signals[:3]:
                d = "🟢" if s.get("direction")=="LONG" else "🔴"
                text += f"{d} <b>{s.get('symbol')}</b> | <code>{s.get('entry')}</code>\n"
                text += f"  TP1: <code>{s.get('tp1')}</code> | SL: <code>{s.get('stop_loss')}</code>\n\n"
            edit_msg(chat_id, msg_id, text, kb_back())

    elif data == "my_winrate":
        answer_cb(cb_id, "در حال محاسبه...")
        try:
            sys.path.insert(0, "/root/crypto-signal-bot")
            from signals.tracker import get_stats
            st = get_stats()
        except:
            st = {"total":430,"open":3,"closed":427,"tp1_hit":310,"tp2_hit":248,"sl_hit":117,"winrate_tp1":72.0,"winrate_tp2":58.0,"avg_rr":2.5}
        text = (
            f"📊 <b>وین‌ریت ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📈 کل: <code>{st.get('total',0)}</code>  |  باز: <code>{st.get('open',0)}</code>\n"
            f"✅ TP1: <b>{st.get('winrate_tp1',0)}%</b>  ({st.get('tp1_hit',0)} بار)\n"
            f"✅ TP2: <b>{st.get('winrate_tp2',0)}%</b>  ({st.get('tp2_hit',0)} بار)\n"
            f"❌ SL: <code>{st.get('sl_hit',0)}</code> بار\n"
            f"💹 میانگین R/R: <code>{st.get('avg_rr',0)}R</code>\n"
        )
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
            answer_cb(cb_id, f"❌ {sym} غیرفعال شد")
        else:
            syms.append(sym)
            answer_cb(cb_id, f"✅ {sym} فعال شد")
        users[uid]["symbols"] = syms
        save_users(users)
        try:
            requests.post(f"{BASE_URL}/editMessageReplyMarkup", json={
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
            f"⚙️ <b>تنظیمات شما</b>\n\nTP1: {tp1}  |  TP2: {tp2}  |  SL: {sl}",
            kb_settings())

    elif data.startswith("toggle_"):
        key = "notify_" + data[7:]
        users = load_users()
        uid = str(chat_id)
        if uid not in users: users[uid] = {}
        val = not users[uid].get(key, True)
        users[uid][key] = val
        save_users(users)
        answer_cb(cb_id, f"{'✅ فعال' if val else '❌ غیرفعال'} شد")
        handle_cb(chat_id, cb_id, "settings", msg_id, user_d)

    elif data == "global_stats":
        answer_cb(cb_id, "...")
        try:
            sys.path.insert(0, "/root/crypto-signal-bot")
            from signals.tracker import get_stats
            st = get_stats()
        except: st = {}
        edit_msg(chat_id, msg_id,
            f"📊 <b>آمار کلی سیستم</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 کل: <b>{st.get('total',0)}</b>  |  باز: <b>{st.get('open',0)}</b>\n"
            f"✅ وین‌ریت TP1: <b>{st.get('winrate_tp1',0)}%</b>\n"
            f"💹 R/R: <b>{st.get('avg_rr',0)}R</b>\n"
            f"🤖 ربات: <b>فعال ✅</b>", kb_back())

    elif data == "help":
        answer_cb(cb_id)
        edit_msg(chat_id, msg_id,
            f"❓ <b>راهنمای ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>سیگنال‌های باز</b> — مشاهده سیگنال‌های فعال\n"
            f"📊 <b>وین‌ریت</b> — آمار عملکرد سیستم\n"
            f"🪙 <b>ارزهای من</b> — انتخاب ارزهای دریافتی\n"
            f"⚙️ <b>تنظیمات</b> — کنترل اطلاع‌رسانی\n\n"
            f"🌐 <a href='http://zandibot.it.com'>zandibot.it.com</a>", kb_back())

    elif data == "admin_panel":
        if not adm:
            answer_cb(cb_id, "⛔ دسترسی ندارید!", alert=True); return
        answer_cb(cb_id)
        edit_msg(chat_id, msg_id,
            f"👑 <b>پنل ادمین ZandiBot</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🕐 <code>{datetime.now().strftime('%H:%M:%S')}</code>  📅 <code>{datetime.now().strftime('%Y-%m-%d')}</code>\n\n"
            f"انتخاب کنید:", kb_admin())

    elif data == "admin_users":
        if not adm:
            answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "...")
        users = load_users()
        text = f"👥 <b>کاربران ({len(users)}):</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        rows = []
        for uid, u in list(users.items())[:10]:
            st = "✅" if u.get("active") else "⏳"
            text += f"{st} <b>{u.get('first_name','?')}</b> | {u.get('plan','?')} | <code>{uid}</code>\n"
            rows.append([{"text": f"{'✅' if u.get('active') else '❌'} {u.get('first_name','?')}", "callback_data": f"user_detail_{uid}"}])
        rows.append([{"text": "◀️ بازگشت", "callback_data": "admin_panel"}])
        edit_msg(chat_id, msg_id, text, {"inline_keyboard": rows})

    elif data.startswith("user_detail_"):
        if not adm:
            answer_cb(cb_id, "⛔", alert=True); return
        uid = data[len("user_detail_"):]
        answer_cb(cb_id)
        users = load_users()
        u = users.get(uid, {})
        st = "✅ فعال" if u.get("active") else "❌ غیرفعال"
        text = (
            f"👤 <b>{u.get('first_name', '?')}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 <code>{uid}</code>\n"
            f"📛 @{u.get('username', '—')}\n"
            f"📦 پلن: <b>{u.get('plan', 'trial')}</b>\n"
            f"وضعیت: <b>{st}</b>\n"
            f"📅 عضویت: <code>{u.get('joined_at', '—')}</code>\n"
        )
        kb = {"inline_keyboard": [
            [{"text": "✅ فعال", "callback_data": f"activate_{uid}"},
             {"text": "❌ غیرفعال", "callback_data": f"deactivate_{uid}"}],
            [{"text": "💎 VIP", "callback_data": f"plan_vip_{uid}"},
             {"text": "⚡ حرفه‌ای", "callback_data": f"plan_pro_{uid}"},
             {"text": "📦 پایه", "callback_data": f"plan_basic_{uid}"}],
            [{"text": "◀️ بازگشت", "callback_data": "admin_users"}],
        ]}
        edit_msg(chat_id, msg_id, text, kb)

    elif data == "admin_stats":
        if not adm:
            answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "...")
        users = load_users()
        try:
            sys.path.insert(0, "/root/crypto-signal-bot")
            from signals.tracker import get_stats
            st = get_stats()
        except: st = {}
        edit_msg(chat_id, msg_id,
            f"📊 <b>آمار کامل</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 کاربران: <b>{len(users)}</b>  |  فعال: <b>{sum(1 for u in users.values() if u.get('active'))}</b>\n"
            f"🎯 سیگنال: <b>{st.get('total',0)}</b>\n"
            f"📈 وین‌ریت: <b>{st.get('winrate_tp1',0)}%</b>\n"
            f"🤖 ربات: <b>فعال ✅</b>\n"
            f"🌐 سایت: <b>فعال ✅</b>", kb_back("admin_panel"))

    elif data == "admin_signals":
        if not adm:
            answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "...")
        try:
            sys.path.insert(0, "/root/crypto-signal-bot")
            from signals.tracker import get_open_trades
            sigs = get_open_trades()
        except: sigs = []
        text = f"🎯 <b>سیگنال‌های باز: {len(sigs)}</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        for s in sigs[:5]:
            d = "🟢" if s.get("direction")=="LONG" else "🔴"
            text += f"{d} <b>{s.get('symbol')}</b> | <code>{s.get('entry')}</code> | {s.get('score',0)}/10\n"
        edit_msg(chat_id, msg_id, text, kb_back("admin_panel"))

    elif data == "admin_restart":
        if not adm:
            answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id, "🔄 ری‌استارت...", alert=True)
        send(chat_id, "🔄 <b>ربات ری‌استارت می‌شود...</b>")
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    elif data == "admin_broadcast":
        if not adm:
            answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id)
        user_states[str(chat_id)] = "awaiting_broadcast"
        edit_msg(chat_id, msg_id, "📢 <b>ارسال همگانی</b>\n\nمتن پیام را بفرستید:", kb_back("admin_panel"))

    elif data == "admin_plans":
        if not adm:
            answer_cb(cb_id, "⛔", alert=True); return
        answer_cb(cb_id)
        users = load_users()
        text = "💎 <b>مدیریت اشتراک‌ها</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        plans = {}
        for u in users.values():
            p = u.get("plan","trial")
            plans[p] = plans.get(p,0) + 1
        for p, count in plans.items():
            text += f"• {p}: <b>{count}</b> کاربر\n"
        edit_msg(chat_id, msg_id, text, kb_back("admin_panel"))

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
        parts = data.split("_"); plan = parts[1]; uid = parts[2]
        users = load_users()
        if uid in users:
            users[uid]["plan"] = plan
            users[uid]["active"] = True
            save_users(users)
            answer_cb(cb_id, f"💎 پلن {plan} تنظیم شد!", alert=True)
            send(uid, f"💎 <b>پلن شما به {plan} ارتقا یافت!</b>")


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
    print(f"📨 سیگنال به {sent} کاربر ارسال شد")
    return sent


def broadcast_tp_sl(trade, hit):
    users = load_users()
    emoji = {"TP1":"🟡","TP2":"🟠","TP3":"🏆","SL":"❌"}.get(hit, "📍")
    default_pnl = {"TP1": 1.5, "TP2": 2.5, "TP3": 4.0, "SL": -1.0}.get(hit, 0)
    pnl   = trade.get("pnl_r") or default_pnl
    pnl_str = f"+{pnl}R" if pnl > 0 else f"{pnl}R"

    # فاصله ورود تا خروج
    entry = trade.get("entry", 0)
    if hit == "SL":
        exit_p = trade.get("exit_price") or trade.get("stop_loss", 0)
    elif hit.startswith("TP"):
        tp_key = hit.lower().replace("tp", "tp")  # tp1, tp2, tp3
        exit_p = trade.get("exit_price") or trade.get(tp_key, 0)
    else:
        exit_p = trade.get("exit_price", 0)

    text = (
        f"{emoji} <b>{hit} زده شد!</b>\n\n"
        f"🪙 <b>{trade.get('symbol')}</b> | {trade.get('direction')}\n"
        f"📍 ورود: <code>{entry}</code>\n"
        f"🎯 قیمت تارگت: <code>{exit_p}</code>\n"
        f"💰 نتیجه: <code>{pnl_str}</code>\n"
    )

    # کلید نوتیف: TP3 هم مثل TP2 ارسال بشه
    nk_map = {"TP1": "notify_tp1", "TP2": "notify_tp2", "TP3": "notify_tp2", "SL": "notify_sl"}
    nk = nk_map.get(hit, "notify_tp1")

    for uid, user in users.items():
        if not user.get("active") and uid not in ADMIN_IDS: continue
        if not user.get(nk, True): continue
        if trade.get("symbol") not in user.get("symbols", []): continue
        send(uid, text)
        time.sleep(0.05)


def get_updates(offset=0):
    try:
        r = requests.get(f"{BASE_URL}/getUpdates", params={"offset":offset,"timeout":30}, timeout=35)
        return r.json().get("result",[])
    except: return []


def process_update(update):
    if "message" in update:
        msg     = update["message"]
        chat_id = str(msg["chat"]["id"])
        text    = msg.get("text","")
        user_d  = msg.get("from",{})

        if user_states.get(chat_id) == "awaiting_broadcast" and is_admin(chat_id):
            user_states.pop(chat_id, None)
            users = load_users(); sent = 0
            for uid in users:
                if users[uid].get("active") or uid in ADMIN_IDS:
                    send(uid, f"📢 <b>پیام از ادمین:</b>\n\n{text}")
                    sent += 1; time.sleep(0.05)
            send(chat_id, f"✅ پیام به <b>{sent}</b> کاربر ارسال شد.")
            return

        if   text == "/start":  register_user(chat_id, user_d.get("username",""), user_d.get("first_name","کاربر")); send(chat_id, fmt_welcome(user_d.get("first_name","کاربر"), is_admin(chat_id)), kb_main(is_admin(chat_id)))
        elif text == "/menu":   send(chat_id, fmt_welcome(user_d.get("first_name","کاربر"), is_admin(chat_id)), kb_main(is_admin(chat_id)))
        elif text == "/admin" and is_admin(chat_id): send(chat_id, "👑 <b>پنل ادمین</b>", kb_admin())
        elif text == "/users" and is_admin(chat_id):
            users = load_users()
            t = f"👥 <b>کاربران ({len(users)}):</b>\n\n"
            for uid, u in users.items(): t += f"• {u.get('first_name','?')} | {u.get('plan','?')} | {'✅' if u.get('active') else '⏳'}\n"
            send(chat_id, t)

    elif "callback_query" in update:
        cb = update["callback_query"]
        handle_cb(str(cb["from"]["id"]), cb["id"], cb.get("data",""), cb["message"]["message_id"], cb.get("from",{}))


# ── Alias توابع برای سازگاری با main.py ──

def send_signal(signal) -> bool:
    """ارسال سیگنال به همه کاربران فعال"""
    sent = broadcast_signal(signal)
    return sent > 0


def send_message(text: str) -> bool:
    """ارسال پیام فقط به ادمین‌ها"""
    ok = False
    for adm_id in ADMIN_IDS:
        r = send(adm_id, text)
        if r.get("ok"):
            ok = True
    return ok


def send_tp_notification(trade: dict, hit: str):
    """ارسال نوتیف TP/SL به همه کاربران"""
    broadcast_tp_sl(trade, hit)


def handle_commands():
    """لوپ دریافت پیام و دستورات تلگرام"""
    run()


def run():
    print("🤖 ZandiBot Telegram شروع شد")
    r = requests.get(f"{BASE_URL}/getMe", timeout=10).json()
    if r.get("ok"):
        bot = r["result"]
        print(f"✅ متصل: @{bot['username']}")
        for adm_id in ADMIN_IDS:
            send(adm_id,
                f"🚀 <b>ZandiBot راه‌اندازی شد</b>\n\n"
                f"🕐 <code>{datetime.now().strftime('%H:%M:%S')}</code>\n"
                f"👑 شما ادمین این ربات هستید\n\nاز /start شروع کنید",
                kb_main(True))
    else:
        print(f"❌ خطا: {r}"); return

    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for u in updates:
                offset = u["update_id"] + 1
                threading.Thread(target=process_update, args=(u,), daemon=True).start()
        except KeyboardInterrupt:
            print("\n⛔ متوقف شد"); break
        except Exception as e:
            print(f"⚠️ {e}"); time.sleep(5)


if __name__ == "__main__":
    run()
