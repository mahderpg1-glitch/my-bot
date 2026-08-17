# =============================================
# 🇮🇶 بوت معرفة الرقم والاستعلامات الشاملة + صيد يوزرات تيليجرام
# =============================================

import subprocess
import sys
import sqlite3
import re
import os
import time
import requests
import json
import random
import string
import secrets
import base64
import threading
from datetime import datetime, timedelta
from io import BytesIO

def install_packages():
    packages = ['pyTelegramBotAPI', 'requests', 'phonenumbers', 'openpyxl', 'ms4', 'rich']
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
install_packages()

import telebot
from telebot import types
import phonenumbers
from phonenumbers import carrier, geocoder, timezone
from ms4 import InfoTik

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    console = Console()
except Exception:
    pass

# الإعدادات الرئيسية
API_TOKEN = "8817031444:AAEA-rOM2w8JWqCrU3cPPMqiFbkhiwTpbUU"
ADMIN_ID = 7551388111

CHANNEL_USERNAME = "@XHX313"
CHANNEL_LINK = "https://t.me/XHX313"

bot = telebot.TeleBot(API_TOKEN)

# =============================================
# إعداد قواعد البيانات والمؤشرات لتفادي أخطاء النظام
# =============================================
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS searches 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, phone TEXT, name TEXT, location TEXT, source TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id TEXT PRIMARY KEY, first_name TEXT, username TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS banned 
             (user_id TEXT PRIMARY KEY)''')
c.execute('''CREATE TABLE IF NOT EXISTS feedback 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, message TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# جدول حد الصيد اليومي وساعات الحظر
c.execute('''CREATE TABLE IF NOT EXISTS hunting_limits 
             (user_id TEXT PRIMARY KEY, count INTEGER DEFAULT 0, last_hunt TIMESTAMP, blocked_until TIMESTAMP)''')
conn.commit()

# =============================================
# إعدادات وأنماط صيد يوزرات تيليجرام
# =============================================
USERNAME_PATTERNS = [
    "@HJ_JK",
    "@WXC_K", 
    "@WX_C_J",
    "@F_GH_K",
    "@KLM_L",
    "@X_C_V_7",
    "@H_7_G_N",
    "@G5_KL",
    "@C_H_6_H",
    "@A_O_4_4",
    "@h_h_b9",
    "@k_l_gx"
]

ADDITIONAL_PATTERNS = [
    ("@??_??", lambda: f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}_{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"),
    ("@???_?", lambda: f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}_{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"),
    ("@?_??_?", lambda: f"{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}_{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}_{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}")
]

hunting_active = {}
fb_hunting_active = {}

# =============================================
# دوال النظام والدعم
# =============================================
def check_hunt_limit(user_id):
    try:
        c.execute("SELECT count, last_hunt, blocked_until FROM hunting_limits WHERE user_id=?", (str(user_id),))
        row = c.fetchone()
        now = datetime.now()
        
        if not row:
            return True, 0, None
        
        count, last_hunt_str, blocked_until_str = row
        
        if blocked_until_str:
            blocked_until = datetime.strptime(blocked_until_str, "%Y-%m-%d %H:%M:%S")
            if now < blocked_until:
                return False, count, blocked_until
            else:
                c.execute("UPDATE hunting_limits SET count=0, blocked_until=NULL WHERE user_id=?", (str(user_id),))
                conn.commit()
                return True, 0, None

        if last_hunt_str:
            last_hunt = datetime.strptime(last_hunt_str, "%Y-%m-%d %H:%M:%S")
            if now.date() > last_hunt.date():
                c.execute("UPDATE hunting_limits SET count=0, blocked_until=NULL WHERE user_id=?", (str(user_id),))
                conn.commit()
                return True, 0, None

        if count >= 50:
            blocked_until = now + timedelta(hours=2)
            c.execute("UPDATE hunting_limits SET blocked_until=? WHERE user_id=?", 
                      (blocked_until.strftime("%Y-%m-%d %H:%M:%S"), str(user_id)))
            conn.commit()
            return False, count, blocked_until

        return True, count, None
    except Exception as e:
        print(f"خطأ في دالة check_hunt_limit: {e}")
        return True, 0, None

def increment_hunt_count(user_id):
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("SELECT count FROM hunting_limits WHERE user_id=?", (str(user_id),))
        row = c.fetchone()
        if row:
            new_count = row[0] + 1
            c.execute("UPDATE hunting_limits SET count=?, last_hunt=? WHERE user_id=?", (new_count, now_str, str(user_id)))
        else:
            c.execute("INSERT INTO hunting_limits (user_id, count, last_hunt) VALUES (?, 1, ?)", (str(user_id), now_str))
        conn.commit()
    except Exception as e:
        print(f"خطأ في زيادة حد الصيد: {e}")

def save_search(user_id, phone, name, location, source="عام"):
    try:
        c.execute("INSERT INTO searches (user_id, phone, name, location, source) VALUES (?,?,?,?,?)",
                  (str(user_id), phone, name, location, source))
        conn.commit()
        return True
    except Exception:
        return False

def save_user(user_id, first_name, username):
    try:
        c.execute("SELECT user_id FROM users WHERE user_id=?", (str(user_id),))
        is_new = c.fetchone() is None
        
        if is_new:
            c.execute("INSERT INTO users (user_id, first_name, username) VALUES (?,?,?)",
                      (str(user_id), first_name or "", username or ""))
            conn.commit()
            
            total_users = get_user_count()
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_uname = f"@{username}" if username else "لا يوجد"
            
            notify_msg = (
                f"🌟 مستخدم جديد!\n\n"
                f"🆔 المعرف: {user_id}\n"
                f"👤 اليوزر: {user_uname}\n"
                f"📛 الاسم: {first_name or '—'}\n"
                f"📅 التاريخ: {now_str}\n"
                f"👥 إجمالي المستخدمين: {total_users}\n"
                f"━━━━━━━━━━━━━━\n"
                f"━━━━━━━"
            )
            try:
                bot.send_message(ADMIN_ID, notify_msg)
            except Exception as e:
                print(f"خطأ إرسال الإشعار للمطور: {e}")
                
        return True
    except Exception as e:
        print(f"خطأ حفظ المستخدم: {e}")
        return False

def is_banned(user_id):
    try:
        c.execute("SELECT * FROM banned WHERE user_id=?", (str(user_id),))
        return c.fetchone() is not None
    except Exception:
        return False

def get_user_count():
    try:
        c.execute("SELECT COUNT(*) FROM users")
        return c.fetchone()[0]
    except Exception:
        return 0

def get_search_count():
    try:
        c.execute("SELECT COUNT(*) FROM searches")
        return c.fetchone()[0]
    except Exception:
        return 0

def get_active_users():
    try:
        c.execute("SELECT COUNT(DISTINCT user_id) FROM searches")
        return c.fetchone()[0]
    except Exception:
        return 0

def save_feedback(user_id, message):
    try:
        c.execute("INSERT INTO feedback (user_id, message) VALUES (?,?)",
                  (str(user_id), message))
        conn.commit()
        return True
    except Exception:
        return False

def is_subscribed(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

# =============================================
# دوال صيد يوزرات تيليجرام
# =============================================
def check_username(username):
    try:
        url = f"https://t.me/{username.replace('@', '')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if '"robots"' in response.text or '"tgme_username_link"' in response.text:
            return True
        return False
    except Exception:
        return None

def generate_similar_username(pattern):
    if pattern == "@HJ_JK":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return f"{random.choice(letters)}{random.choice(letters)}_{random.choice(letters)}{random.choice(letters)}"
    
    elif pattern == "@WXC_K":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return f"{random.choice(letters)}{random.choice(letters)}{random.choice(letters)}_{random.choice(letters)}"
    
    elif pattern == "@WX_C_J":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return f"{random.choice(letters)}{random.choice(letters)}{random.choice(letters)}_{random.choice(letters)}"
    
    elif pattern == "@F_GH_K":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return f"{random.choice(letters)}_{random.choice(letters)}{random.choice(letters)}_{random.choice(letters)}"
    
    elif pattern == "@KLM_L":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return f"{random.choice(letters)}{random.choice(letters)}{random.choice(letters)}_{random.choice(letters)}"
    
    elif pattern == "@X_C_V_7":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        numbers = "1234567890"
        return f"{random.choice(letters)}_{random.choice(letters)}_{random.choice(letters)}_{random.choice(numbers)}"
    
    elif pattern == "@H_7_G_N":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        numbers = "1234567890"
        return f"{random.choice(letters)}_{random.choice(numbers)}_{random.choice(letters)}_{random.choice(letters)}"
    
    elif pattern == "@G5_KL":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        numbers = "1234567890"
        return f"{random.choice(letters)}{random.choice(numbers)}_{random.choice(letters)}{random.choice(letters)}"
    
    elif pattern == "@C_H_6_H":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        numbers = "1234567890"
        return f"{random.choice(letters)}_{random.choice(letters)}_{random.choice(numbers)}_{random.choice(letters)}"
    
    elif pattern == "@A_O_4_4":
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        numbers = "1234567890"
        return f"{random.choice(letters)}_{random.choice(letters)}_{random.choice(numbers)}_{random.choice(numbers)}"
    
    elif pattern == "@h_h_b9":
        letters = "abcdefghijklmnopqrstuvwxyz"
        numbers = "1234567890"
        return f"{random.choice(letters)}_{random.choice(letters)}_{random.choice(letters)}{random.choice(numbers)}"
    
    elif pattern == "@k_l_gx":
        letters = "abcdefghijklmnopqrstuvwxyz"
        return f"{random.choice(letters)}_{random.choice(letters)}_{random.choice(letters)}{random.choice(letters)}"
    
    else:
        for pattern_template, generator in ADDITIONAL_PATTERNS:
            if pattern == pattern_template:
                return generator()
        return None

def hunt_usernames(message, user_id):
    chat_id = message.chat.id
    found_count = 0
    checked_count = 0
    
    try:
        status_msg = bot.send_message(
            chat_id,
            "🪈 **بدء الصيد**\n"
            "👌🏾 تم العثور على: 0\n"
            "🪝 تم فحص: 0\n"
            "⏳ جاري البحث..."
        )
        status_msg_id = status_msg.message_id
    except Exception:
        status_msg_id = None
    
    while hunting_active.get(chat_id, False):
        try:
            can_hunt, count, blocked_until = check_hunt_limit(user_id)
            if not can_hunt:
                hunting_active[chat_id] = False
                bot.send_message(chat_id, "قد نفذ حدك لل الصيد اليوم حاول بعد 2 ساعتين")
                break

            pattern = random.choice(USERNAME_PATTERNS + [p[0] for p in ADDITIONAL_PATTERNS])
            username = generate_similar_username(pattern)
            
            if not username:
                continue
            
            checked_count += 1
            increment_hunt_count(user_id)
            
            is_available = check_username(username)
            
            if is_available is True:
                found_count += 1
                bot.send_message(
                    chat_id,
                    f" 🥇 **تم العثور على يوزر!**\n\n"
                    f"➗ اليوزر: @{username}\n"
                    f"📊 الرقم: #{found_count}\n"
                    f"🔗 الرابط: https://t.me/{username}\n\n"
                    f"⚡️ سارع بحجزه!",
                    disable_web_page_preview=True
                )
            
            if status_msg_id and checked_count % 10 == 0:
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_msg_id,
                        text=f"🥇 **جاري الصيد**\n"
                             f"➗ تم العثور على: {found_count}\n"
                             f"🔍 تم فحص: {checked_count}\n"
                             f"🀄 النمط: {pattern}\n"
                             f"⏳ جاري البحث...",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error in hunting loop: {e}")
            time.sleep(1)
            continue
    
    if status_msg_id and hunting_active.get(chat_id, False) == False:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg_id,
                text=f"🆘 **توقف الصيد**\n\n"
                     f"📊 الإحصائيات النهائية:\n"
                     f"✅ تم العثور على: {found_count}\n"
                     f"🎴 تم فحص: {checked_count}\n"
                     f"🔕 نسبة النجاح: {found_count/max(checked_count,1)*100:.2f}%",
                parse_mode="Markdown"
            )
        except Exception:
            pass

# =============================================
# الخدمة الخاصة بـ: كشف الرقم عبر API Caller
# =============================================
def search_caller_api(phone_code, phone_number):
    url = "https://caller-uegx.vercel.app/api/search"
    headers = {
        "authority": "caller-uegx.vercel.app",
        "accept": "*/*",
        "content-type": "application/json",
        "cookie": "sin_user_id=5a2f2f0eabaf0f11",
        "origin": "https://caller-uegx.vercel.app",
        "referer": "https://caller-uegx.vercel.app/",
        "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36"
    }
    payload = {"code": phone_code, "phone": phone_number}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.json()
        return {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}        

# =============================================
# الخدمة الخاصة بـ: معلومات الرقم عبر phonenumbers
# =============================================
def get_phone_network_info(user_phone):
    default_region = "IQ"
    try:
        parsed_number = phonenumbers.parse(user_phone, default_region)
        region_code = phonenumbers.region_code_for_number(parsed_number)
        jenis_provider = carrier.name_for_number(parsed_number, "en") or "غير معروف"
        location = geocoder.description_for_number(parsed_number, "id") or "غير معروف"
        is_valid_number = phonenumbers.is_valid_number(parsed_number)
        is_possible_number = phonenumbers.is_possible_number(parsed_number)
        formatted_number = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        formatted_number_for_mobile = phonenumbers.format_number_for_mobile_dialing(parsed_number, default_region, with_formatting=True)
        number_type = phonenumbers.number_type(parsed_number)
        timezone1 = timezone.time_zones_for_number(parsed_number)
        timezoneF = ', '.join(timezone1)

        response = (
            f"Location             : {location}\n"
            f"Region Code          : {region_code}\n"
            f"Timezone             : {timezoneF}\n"
            f"Operator             : {jenis_provider}\n"
            f"Valid number         : {is_valid_number}\n"
            f"Possible number      : {is_possible_number}\n"
            f"International format : {formatted_number}\n"
            f"Mobile format        : {formatted_number_for_mobile}\n"
            f"Original number      : {parsed_number.national_number}\n"
            f"E.164 format         : {phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)}\n"
            f"Country code         : {parsed_number.country_code}\n"
            f"Local number         : {parsed_number.national_number}\n"
        )

        if number_type == phonenumbers.PhoneNumberType.MOBILE:
            response += "Type                 : This is a mobile number"
        elif number_type == phonenumbers.PhoneNumberType.FIXED_LINE:
            response += "Type                 : This is a fixed-line number"
        else:
            response += "Type                 : This is another type of number"

        national_num = parsed_number.national_number
        return response, national_num
    except Exception:
        return None, None

# =============================================
# أزرار الواجهة التفاعلية الشفافة (Inline)
# =============================================
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    btn1 = types.InlineKeyboardButton("معلومات الرقم", callback_data="btn_search_name", style="success")   
    btn_hunt = types.InlineKeyboardButton("صيد يوزرات تيليجرام مميزه", callback_data="btn_hunt_menu", style="success")
    btn2 = types.InlineKeyboardButton("كشف الرقم - من خلال الاسم", callback_data="btn_caller_api", style="success")
         
    btn4 = types.InlineKeyboardButton("المالك", url="https://t.me/l_ROK", style="primary")
    btn5 = types.InlineKeyboardButton("قناتي ", url="https://t.me/XHX313", style="primary")
    
    markup.add(btn1)
    markup.add(btn_hunt)
    markup.add(btn2)
    markup.row(btn4, btn5)
    return markup

def back():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("↩️ رجوع", callback_data="main", style="danger"))
    return markup

def admin_buttons():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 الإحصائيات الكاملة", callback_data="admin_stats", style="primary"),
        types.InlineKeyboardButton("🏆 لوحة المتصدرين", callback_data="admin_leaderboard", style="danger"),
        types.InlineKeyboardButton("📢 إذاعة للجميع", callback_data="admin_broadcast", style="danger"),
        types.InlineKeyboardButton("🚫 حظر مستخدم", callback_data="admin_ban", style="danger"),
        types.InlineKeyboardButton("✅ إلغاء حظر المستخدم", callback_data="admin_unban", style="success"),
        types.InlineKeyboardButton(" رجوع", callback_data="close_admin", style="danger")
    )
    return markup

def subscribe_check():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 اشترك في القناة", url=CHANNEL_LINK, style="danger"),
        types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub", style="success")
    )
    return markup

def hunt_menu():
    markup = types.InlineKeyboardMarkup()
    start_btn = types.InlineKeyboardButton("بدء الصيد", callback_data='start_hunting', style="success")
    stop_btn = types.InlineKeyboardButton("إيقاف الصيد", callback_data='stop_hunting', style="danger")
    back_btn = types.InlineKeyboardButton("↩️ رجوع", callback_data="main", style="danger")
    markup.row(start_btn, stop_btn)
    markup.add(back_btn)
    return markup

# =============================================
# أوامر البوت والتفاعل
# =============================================
@bot.message_handler(commands=['start', 'help'])
def start(msg):
    user = msg.from_user
    if is_banned(user.id):
        bot.send_message(msg.chat.id, "🚫 أنت محظور من استخدام البوت.")
        return
    
    save_user(user.id, user.first_name, user.username)
    if not is_subscribed(user.id):
        welcome = f"👋 **أهلاً بك {user.first_name}**\n\n📢 **يجب الاشتراك في القناة أولاً:**"
        bot.send_message(msg.chat.id, welcome, parse_mode='Markdown', reply_markup=subscribe_check())
        return
    
    welcome_msg = f"اهلا عزيزي {user.first_name} في بوت كايدو"
    bot.send_message(msg.chat.id, welcome_msg, reply_markup=main_menu())

# =============================================
# أمر /admin في الشات (الخاص بالأدمن فقط)
# =============================================
@bot.message_handler(commands=['admin'])
def admin_command(msg):
    user_id = msg.from_user.id
    if user_id != ADMIN_ID:
        bot.reply_to(msg, "•غير مصرح لك باستخدام هاذا •")
        return
    
    bot.send_message(
        msg.chat.id,
        "👑 **أهلاً بك في لوحة الأدمن والتحكم الخاص بالمالك:**",
        parse_mode="Markdown",
        reply_markup=admin_buttons()
    )

# =============================================
# معالج الكولباك الشامل (Callback Handler)
# =============================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    global hunting_active, fb_hunting_active
    user = call.from_user
    
    if is_banned(user.id):
        bot.answer_callback_query(call.id, "🚫 أنت محظور", show_alert=True)
        return

    if call.data != "check_sub" and not is_subscribed(user.id):
        bot.answer_callback_query(call.id, "❌ اشترك في القناة أولاً", show_alert=True)
        return
    
    if call.data == "check_sub":
        if is_subscribed(user.id):
            welcome_msg = f"اهلا عزيزي {user.first_name} في بوت كايدو"
            bot.edit_message_text(welcome_msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
            bot.answer_callback_query(call.id, "✅ تم التحقق")
        else:
            bot.answer_callback_query(call.id, "❌ اشترك في القناة أولاً", show_alert=True)
        return
    
    if call.data == "main":
        welcome_msg = f"اهلا عزيزي {user.first_name} في بوت كايدو"
        bot.edit_message_text(welcome_msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return
        
    # 1. زر: معلومات الرقم (معلومات الشبكة)
    elif call.data == "btn_search_name":
        bot.edit_message_text("📱 **معلومات رقم الهاتف**\n\nأرسل لي رقم الهاتف بصيغة دولية لتحصل على المعلومات:\nمثال: `+9647800000000` أو `07800000000`", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back())
        bot.answer_callback_query(call.id)
        bot.register_next_step_handler(call.message, process_phone_info)
        return

    elif call.data == "btn_user_lookup":
        # فتح زر داخلي (ليس شفاف) لاختيار الحساب
        reply_kb = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
        btn_user = types.KeyboardButton("•اختار الحساب•", request_user=types.KeyboardButtonRequestUser(request_id=1, user_is_bot=False))
        reply_kb.add(btn_user)
        bot.send_message(call.message.chat.id, "👇 اضغط على الزر الأدنى واختار الحساب المطلوب لكشفه:", reply_markup=reply_kb)
        bot.answer_callback_query(call.id)
        return

    # زر: صيد يوزرات تيليجرام مميزه
    elif call.data == "btn_hunt_menu":
        user_name = call.from_user.first_name
        txt = (
            f"شلون الحجي ❓ {user_name}\n\n"
            "🚸 بوت كايدو VIP\n"
            "يتم الصيد نفس الانماط:\n"
            f"{' | '.join(USERNAME_PATTERNS)}\n\n"
            "🧨 انقر على بدء الصيد للبدء"
        )
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, reply_markup=hunt_menu())
        bot.answer_callback_query(call.id)
        return

    elif call.data == 'start_hunting':
        chat_id = call.message.chat.id
        can_hunt, count, blocked_until = check_hunt_limit(user.id)
        if not can_hunt:
            bot.answer_callback_query(call.id, "⚠️ نفذ حد الصيد!", show_alert=True)
            bot.send_message(chat_id, "قد نفذ حدك لل الصيد اليوم حاول بعد 2 ساعتين")
            return

        hunting_active[chat_id] = True
        bot.answer_callback_query(call.id, "🏴‍☠️ بدأ الصيد!")
        bot.send_message(chat_id, "🎣 بدأ الصيد...\n\nيتم البحث عن اليوزرات بالأنماط المحددة")
        
        thread = threading.Thread(target=hunt_usernames, args=(call.message, user.id))
        thread.daemon = True
        thread.start()
        return

    elif call.data == 'stop_hunting':
        chat_id = call.message.chat.id
        hunting_active[chat_id] = False
        bot.answer_callback_query(call.id, "🆘 توقف الصيد!")
        bot.send_message(chat_id, "💯 توقف الصيد بنجاح")
        return
    
    # 2. زر: كشف الرقم - من خلال الاسم (API)
    elif call.data == "btn_caller_api":
        bot.edit_message_text("📞 **كشف الرقم ~ من خلال الاسم**\n\nأرسل الرقم بدون صفر (مثال: `7700000000`):", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back())
        bot.answer_callback_query(call.id)
        bot.register_next_step_handler(call.message, process_caller_api)
        return

    elif call.data == "help":
        help_msg = "🛠️ **تعليمات البوت:**\n\n📌 **الخدمات المتاحة:**\n\n1️⃣ **معلومات الرقم:** لجلب معلومات المشغل والدولة وروابط التواصل.\n2️⃣ **كشف الرقم - من خلال الاسم:** للبحث عبر API الخارجي.\n3️⃣ **صيد يوزرات تيليجرام مميزه:** للصيد التلقائي لليوزرات المتاحة."
        bot.edit_message_text(help_msg, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back())
        bot.answer_callback_query(call.id)
        return
    
    elif call.data == "admin_panel":
        if user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⛔ للمطور فقط", show_alert=True)
            return
        bot.edit_message_text("⚙️ **لوحة الأدمن:**", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=admin_buttons())
        bot.answer_callback_query(call.id)
        return
    
    # ===== وظائف لوحة الأدمن =====
    elif call.data in ["stats", "admin_stats"]:
        if user.id != ADMIN_ID: return
        stats_msg = f"📊 **الإحصائيات:**\n\n👥 **المستخدمين:** {get_user_count()}\n🔍 **عمليات البحث:** {get_search_count()}\n👤 **المستخدمين النشطين:** {get_active_users()}"
        bot.edit_message_text(stats_msg, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=admin_buttons())
        bot.answer_callback_query(call.id)
        return

    elif call.data in ["users_list", "admin_leaderboard"]:
        if user.id != ADMIN_ID: return
        c.execute("SELECT user_id, COUNT(*) FROM searches GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 20")
        rows = c.fetchall()
        txt = "👥 **أكثر المستخدمين نشاطاً:**\n\n" + "\n".join([f"{i}. 🆔 `{r[0]}` → {r[1]} بحث" for i, r in enumerate(rows, 1)]) if rows else "📭 لا يوجد مستخدمين"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=admin_buttons())
        bot.answer_callback_query(call.id)
        return

    elif call.data == "clear_all":
        if user.id != ADMIN_ID: return
        c.execute("DELETE FROM searches")
        conn.commit()
        bot.answer_callback_query(call.id, "✅ تم مسح السجل", show_alert=True)
        return

    elif call.data in ["broadcast", "admin_broadcast"]:
        if user.id != ADMIN_ID: return
        bot.edit_message_text("📢 **أرسل الرسالة للإرسال الجماعي:**", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back())
        bot.register_next_step_handler(call.message, process_broadcast)
        bot.answer_callback_query(call.id)
        return

    elif call.data in ["ban_user", "admin_ban"]:
        if user.id != ADMIN_ID: return
        bot.edit_message_text("🚫 **أرسل ID المستخدم للحظر:**", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back())
        bot.register_next_step_handler(call.message, process_ban_user)
        bot.answer_callback_query(call.id)
        return

    elif call.data in ["unban_user", "admin_unban"]:
        if user.id != ADMIN_ID: return
        bot.edit_message_text("✅ **أرسل ID المستخدم لإلغاء الحظر:**", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back())
        bot.register_next_step_handler(call.message, process_unban_user)
        bot.answer_callback_query(call.id)
        return

    elif call.data == "close_admin":
        welcome_msg = f"اهلا عزيزي {user.first_name} في بوت كايدو"
        bot.edit_message_text(welcome_msg, call.message.chat.id, call.message.message_id, reply_markup=main_menu())
        bot.answer_callback_query(call.id)
        return

    elif call.data == "export_log":
        if user.id != ADMIN_ID: return
        c.execute("SELECT * FROM searches ORDER BY date DESC")
        rows = c.fetchall()
        if not rows:
            bot.answer_callback_query(call.id, "📭 لا يوجد سجل", show_alert=True)
            return
        with open("log.txt", "w", encoding='utf-8') as f:
            f.write("ID|USER_ID|PHONE|NAME|LOCATION|SOURCE|DATE\n")
            for r in rows:
                f.write(f"{r[0]}|{r[1]}|{r[2]}|{r[3]}|{r[4]}|{r[5]}|{r[6]}\n")
        bot.send_document(call.message.chat.id, open("log.txt", "rb"))
        bot.answer_callback_query(call.id)
        return

    elif call.data == "view_feedback":
        if user.id != ADMIN_ID: return
        c.execute("SELECT * FROM feedback ORDER BY date DESC LIMIT 20")
        rows = c.fetchall()
        txt = "📋 **الاقتراحات والشكاوى:**\n\n" + "\n\n".join([f"🆔 `{r[1]}`\n💬 {r[2]}\n📅 {r[3]}" for r in rows]) if rows else "📭 لا يوجد اقتراحات"
        bot.edit_message_text(txt, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=admin_buttons())
        bot.answer_callback_query(call.id)
        return

# =============================================
# استقبال اختيار الحساب التلقائي مع الكشف
# =============================================
@bot.message_handler(content_types=['user_shared'])
def handle_user_shared(msg):
    shared_user_id = msg.user_shared.user_id
    remove_kb = types.ReplyKeyboardRemove()
    
    wait_msg = bot.send_message(msg.chat.id, f"🔍 **جاري البحث والكشف للحساب المختار:** `{shared_user_id}` ...", parse_mode='Markdown', reply_markup=remove_kb)
    
    try:
        chat_info = bot.get_chat(shared_user_id)
        target_username = chat_info.username if chat_info.username else "لا يوجد يوزر"
        first_name = chat_info.first_name or "—"
        
        res_text = (
            f"🎯 **نتائج الكشف التلقائي:**\n\n"
            f"🆔 **معرف الحساب (ID):** `{shared_user_id}`\n"
            f"👤 **اليوزر:** @{target_username if chat_info.username else 'لا يوجد'}\n"
            f"📛 **الاسم:** {first_name}\n\n"
            f"🔍 جاري البحث عن البيانات المرتبطة في السجلات..."
        )
        
        bot.edit_message_text(res_text, msg.chat.id, wait_msg.message_id, parse_mode='Markdown', reply_markup=main_menu())
        save_search(msg.from_user.id, str(shared_user_id), f"كشف الحساب: {first_name}", "Telegram DB", "User Lookup")
    except Exception as e:
        bot.edit_message_text(f"🎯 **معرف الحساب (ID):** `{shared_user_id}`\n\n❌ تعذر جلب تفاصيل إضافية عن الحساب.", msg.chat.id, wait_msg.message_id, parse_mode='Markdown', reply_markup=main_menu())

# =============================================
# دوال معالجة الإدخال والنتائج
# =============================================

# 1. معالجة زر معلومات الرقم (phonenumbers)
def process_phone_info(msg):
    user_phone = msg.text.strip()
    response_text, national_num = get_phone_network_info(user_phone)
    
    if response_text and national_num:
        markup = types.InlineKeyboardMarkup()
        whatsapp_button = types.InlineKeyboardButton("حسابه في واتساب", url=f"https://wa.me/{national_num}", style="success")
        telegram_button = types.InlineKeyboardButton("حسابه في تيلجرام", url=f"https://t.me/{user_phone}", style="primary")
        lookup_button = types.InlineKeyboardButton("كشف الرقم من اليوزر", callback_data="btn_user_lookup", style="primary")
        
        markup.add(whatsapp_button, telegram_button)
        markup.add(lookup_button)
        
        bot.reply_to(msg, f"```\n{response_text}\n```", parse_mode='Markdown', reply_markup=markup)
        save_search(msg.from_user.id, user_phone, "معلومات الشبكة", "phonenumbers", "phonenumbers")
    else:
        bot.reply_to(msg, "❌ **عذراً، لم أتمكن من الحصول على معلومات لهذا الرقم. تأكد من صحته.**", parse_mode='Markdown', reply_markup=back())

# 2. معالجة زر كشف الرقم عبر API
def process_caller_api(msg):
    if msg.text and msg.text.startswith('/'): return
    phone = msg.text.strip()
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if phone.startswith('0'):
        phone = phone[1:]
        
    phone_code = "964"
    
    wait_msg = bot.reply_to(msg, "⏳ جاري البحث...")
    data = search_caller_api(phone_code, phone)
    
    try:
        bot.delete_message(msg.chat.id, wait_msg.message_id)
    except Exception:
        pass
    
    if isinstance(data, dict) and "error" not in data:
        formatted_json = json.dumps(data, ensure_ascii=False, indent=2)
        if len(formatted_json) > 3900:
            formatted_json = formatted_json[:3900] + "\n...تم اختصار النتيجة"
        
        reply_text = "🔍 **نتيجة البحث:**\n\n```json\n" + formatted_json + "\n```"
        bot.reply_to(msg, reply_text, parse_mode='Markdown', reply_markup=back())
        save_search(msg.from_user.id, phone, "بحث API", "العراق", "Caller API")
    else:
        error_info = data.get("error", "فشل جلب البيانات") if isinstance(data, dict) else "خطأ غير معروف"
        bot.reply_to(msg, f"❌ لم يتم العثور على نتائج أو حدث خطأ:\n`{error_info}`", parse_mode='Markdown', reply_markup=back())

# 3. معالجة دوال الأدمن
def process_broadcast(msg):
    if msg.from_user.id != ADMIN_ID: return
    c.execute("SELECT user_id FROM users")
    users = c.fetchall()
    count = 0
    for u in users:
        try:
            bot.send_message(u[0], msg.text)
            count += 1
            time.sleep(0.05)
        except Exception:
            pass
    bot.reply_to(msg, f"✅ تم إرسال الرسالة إلى {count} مستخدم.")

def process_ban_user(msg):
    if msg.from_user.id != ADMIN_ID: return
    uid = msg.text.strip()
    c.execute("INSERT OR REPLACE INTO banned (user_id) VALUES (?)" , (uid,))
    conn.commit()
    bot.reply_to(msg, f"🚫 تم حظر المستخدم `{uid}` بنجاح.", parse_mode='Markdown')

def process_unban_user(msg):
    if msg.from_user.id != ADMIN_ID: return
    uid = msg.text.strip()
    c.execute("DELETE FROM banned WHERE user_id=?", (uid,))
    conn.commit()
    bot.reply_to(msg, f"✅ تم إلغاء حظر المستخدم `{uid}` بنجاح.", parse_mode='Markdown')

# =============================================
# تشغيل البوت
# =============================================
if __name__ == '__main__':
    print("🚀 البوت يعمل الآن بنجاح...")
    bot.infinity_polling(skip_pending=True)