#Copyright ©️ 2021 TeLe TiPs. All Rights Reserved
#Enhanced for Arabic support, Line Buttons, Interval Reminders, and Smart NLP by Manus AI

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import os
import asyncio
import re
from datetime import datetime, timedelta
from pyrogram.errors import FloodWait, MessageNotModified

# --- إعدادات البوت المباشرة ---
API_ID = 34257542
API_HASH = "614a1b5c5b712ac6de5530d5c571c42a"
BOT_TOKEN = "8662063487:AAFhVJQSQCpn52tv98ISkZO0ztAWCDml4UU"
# ---------------------------

# Initialize Bot
bot = Client(
    "Countdown-Arabic-Pro",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Dictionary to store user states for interval setting
user_states = {}

# Smart Arabic Time Parser
def parse_advanced_arabic_time(time_str):
    now = datetime.now()
    time_str = time_str.strip().lower()
    
    # Handle Arabic numerals (١٢٣ -> 123)
    arabic_nums = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    time_str = time_str.translate(arabic_nums)
    
    # Remove common prefixes
    time_str = re.sub(r'^(بعد|في|خلال)\s+', '', time_str)
    
    # 1. Handle "Tomorrow" (بكرة / غداً)
    is_tomorrow = False
    if re.search(r'(بكرة|بكرى|غدا|غداً)', time_str):
        is_tomorrow = True
        time_str = re.sub(r'(بكرة|بكرى|غدا|غداً)\s*', '', time_str).strip()

    # 2. Handle specific time like "9 مساء" or "7 صباحا"
    time_match = re.search(r'(\d+)\s*(مساء|صباحا|صباحاً|م|ص)', time_str)
    if time_match:
        hour = int(time_match.group(1))
        period = time_match.group(2)
        
        if 'مساء' in period or period == 'م':
            if hour < 12: hour += 12
        elif 'صباح' in period or period == 'ص':
            if hour == 12: hour = 0
            
        target_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if is_tomorrow:
            target_time += timedelta(days=1)
        elif target_time < now:
            target_time += timedelta(days=1)
            
        diff = (target_time - now).total_seconds()
        return int(diff)

    # 3. Handle relative durations
    time_map = {
        r'ثانية?': 1, r'ثواني': 1,
        r'دقيقة?': 60, r'دقائق': 60, r'دقايق': 60,
        r'ساعة?': 3600, r'ساعات': 3600,
        r'يوم': 86400, r'أيام': 86400, r'ايام': 86400,
        r'أسبوع': 604800, r'اسبوع': 604800, r'أسابيع': 604800,
        r'شهر': 2592000, r'شهور': 2592000,
    }
    
    special_cases = {
        r'نص ساعة?': 1800, r'نصف ساعة?': 1800,
        r'ربع ساعة?': 900, r'ثلث ساعة?': 1200,
        r'ساعتين': 7200, r'دقيقتين': 120, r'يومين': 172800,
        r'خمس دقايق': 300, r'عشر دقايق': 600,
    }
    
    for pattern, seconds in special_cases.items():
        if re.search(pattern, time_str):
            return seconds
            
    match = re.search(r'(\d+)\s*(.*)', time_str)
    if match:
        number = int(match.group(1))
        unit_part = match.group(2).strip()
        for pattern, seconds in time_map.items():
            if re.search(pattern, unit_part):
                return number * seconds
                
    for pattern, seconds in time_map.items():
        if re.fullmatch(pattern, time_str):
            return seconds
            
    return None

def get_timer_buttons(seconds):
    # Calculate days, weeks, months
    days = seconds // 86400
    weeks = days // 7
    months = days // 30
    
    buttons = [
        [
            InlineKeyboardButton(f"{days} يوم", callback_data="none"),
            InlineKeyboardButton(f"{weeks} أسبوع", callback_data="none"),
            InlineKeyboardButton(f"{months} شهر", callback_data="none")
        ]
    ]
    return InlineKeyboardMarkup(buttons)

@bot.on_message(filters.command(['start', 'help', 'مساعدة']))
async def start(client, message):
    help_text = (
        "👋 **أهلاً بك في بوت العداد المطور!**\n\n"
        "**كيفية الاستخدام:**\n"
        "أرسل: `عداد (الحدث) (بعد المدة)`\n\n"
        "**أمثلة:**\n"
        "• `عداد مكالمة بعد 6 ساعات`\n"
        "• `عداد صلاة بعد نص ساعة`\n"
        "• `عداد اجتماع 9 مساء`\n"
        "• `عداد موعد بكرى 8 صباحا`\n\n"
        "**ميزات إضافية:**\n"
        "• سيطلب منك البوت تحديد مدة التذكير الدوري.\n"
        "• لحذف أي رسالة من البوت، قم بالرد عليها بكلمة **(حذف)**."
    )
    await message.reply(help_text)

@bot.on_message(filters.regex(r'^عداد\s+\((.+)\)\s+\((.+)\)$') | filters.regex(r'^عداد\s+(.+)\s+(.+)$'))
async def set_timer_step1(client, message):
    match = re.search(r'^عداد\s+\(?(.+?)\)?\s+\(?(.+?)\)?$', message.text)
    if not match:
        return await message.reply("❌ صيغة غير صحيحة. استخدم: `عداد (الحدث) (بعد المدة)`")

    event_name = match.group(1).strip()
    time_str = match.group(2).strip()
    
    total_seconds = parse_advanced_arabic_time(time_str)
    
    if total_seconds is None:
        return await message.reply(f"❌ لم أفهم الوقت: {time_str}")

    # Store state and ask for interval
    user_states[message.from_user.id] = {
        "event": event_name,
        "total_seconds": total_seconds,
        "original_time_str": time_str
    }
    
    await message.reply("حدد مدة التذكير ⏰\n(مثلاً: كل 5 دقائق، كل ساعة، كل 10 ثواني)")

@bot.on_message(filters.text & ~filters.command(['start', 'help', 'مساعدة', 'stop', 'ايقاف']))
async def handle_responses(client, message):
    user_id = message.from_user.id
    
    # 1. Handle "حذف" (Delete) by reply
    if message.text.strip() == "حذف" and message.reply_to_message:
        if message.reply_to_message.from_user.id == (await client.get_me()).id:
            try:
                await message.reply_to_message.delete()
                await message.delete()
                return
            except Exception as e:
                return await message.reply(f"❌ فشل الحذف: {str(e)}")

    # 2. Handle Interval Setting
    if user_id in user_states:
        state = user_states.pop(user_id)
        interval_str = message.text.replace("كل", "").strip()
        interval_seconds = parse_advanced_arabic_time(interval_str)
        
        if interval_seconds is None:
            return await message.reply(f"❌ لم أفهم مدة التذكير: {message.text}. حاول مرة أخرى بضبط العداد.")

        event = state["event"]
        total_seconds = state["total_seconds"]
        
        await message.reply(f"✅ تم البدء! سأذكرك بـ **{event}** كل **{message.text}**.")
        
        # Start the background countdown task
        asyncio.create_task(run_countdown(client, message.chat.id, event, total_seconds, interval_seconds))

async def run_countdown(client, chat_id, event, total_seconds, interval_seconds):
    remaining = total_seconds
    
    while remaining > 0:
        # Format display text
        d = remaining // 86400
        h = (remaining % 86400) // 3600
        m = (remaining % 3600) // 60
        s = remaining % 60
        
        display = ""
        if d > 0: display += f"{d} يوم "
        if h > 0: display += f"{h} ساعة "
        if m > 0: display += f"{m} دقيقة "
        if s > 0 or not display: display += f"{s} ثانية"
        
        text = f"🌙 **العدّ التنازلي لـ {event}**\nمتبقّي {display.strip()} (تقريبي).\n\n✨ تهيأوا بالطاعة."
        
        await client.send_message(
            chat_id, 
            text, 
            reply_markup=get_timer_buttons(remaining)
        )
        
        if remaining <= interval_seconds:
            await asyncio.sleep(remaining)
            remaining = 0
        else:
            await asyncio.sleep(interval_seconds)
            remaining -= interval_seconds

    await client.send_message(chat_id, f"🚨 **انتهى الوقت!**\n\nحان موعد: **{event}**")

if __name__ == "__main__":
    print("Enhanced Arabic Countdown Bot is starting...")
    bot.run()
