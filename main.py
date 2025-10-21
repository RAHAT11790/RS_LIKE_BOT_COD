import os
import time
import logging
import requests
import telebot
from requests.adapters import HTTPAdapter, Retry
from threading import Thread
from flask import Flask

# --- Config from ENV ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
LIKE_API_URL = os.getenv("LIKE_API_URL")
API_KEY = os.getenv("API_KEY")
ALLOWED_GROUP = int(os.getenv("ALLOWED_GROUP", "-1002892874648"))
PORT = int(os.getenv("PORT", 8080))

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)
log = logging.getLogger("rs-like-bot")

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# HTTP session with retries
session = requests.Session()
retries = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))
session.mount("http://", HTTPAdapter(max_retries=retries))

# --- Flask server ---
app = Flask(__name__)

@app.route("/")
def home():
    return "RS Like Bot is Alive!", 200

def run_flask():
    log.info(f"Starting Flask server on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)

# --- Global default photo ---
DEFAULT_PHOTO_FILE = None

# --- Helpers ---
def human_bar(pct, width=20):
    full = int((pct / 100) * width)
    return "█" * full + "░" * (width - full)

def animate_loading(chat_id, message_id, base_text, stages, delay=0.5):
    emojis = ["🔥", "⚡", "✨", "💎", "🌟", "🚀"]
    try:
        for i, p in enumerate(stages):
            bar = human_bar(p)
            emoji = emojis[i % len(emojis)]
            txt = (
                f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
                f"┃ ⚡ <b>RS LIKE — PROCESSING</b> ⚡ ┃\n"
                f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                f"{base_text}\n\n"
                f"📊 Progress: <b>{p}%</b> {emoji}\n{bar}"
            )
            try:
                bot.edit_message_text(txt, chat_id=chat_id, message_id=message_id, parse_mode="HTML")
            except Exception as e:
                log.error("Failed to edit loading message: %s", e)
            time.sleep(delay)
    except Exception as e:
        log.exception("Loading animation error: %s", e)

def get_user_photo(user_id):
    global DEFAULT_PHOTO_FILE
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            return photos.photos[0][0].file_id
        elif DEFAULT_PHOTO_FILE and os.path.exists(DEFAULT_PHOTO_FILE):
            return DEFAULT_PHOTO_FILE
        else:
            return None
    except Exception as e:
        log.error("Failed to fetch user photo: %s", e)
        return None

# --- Commands ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    log.info("Received /start in chat %s", message.chat.id)
    bot.reply_to(
        message,
        "👋 <b>Welcome to RS Like Bot</b>\n"
        "Send likes: <code>/like &lt;region&gt; &lt;uid&gt;</code>\n"
        "Example: <code>/like bd 123456789</code>\n\n"
        "Use /photo to see your profile or default photo.",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(
        message,
        "📖 <b>Help</b>\n"
        "<code>/like &lt;region&gt; &lt;uid&gt;</code> — send likes.\n"
        "<code>/status</code> — bot status.\n"
        "<code>/photo</code> — show profile/default photo.\n"
        "<code>/setdefaultphoto</code> — admin sets default photo.",
        parse_mode="HTML"
    )

@bot.message_handler(commands=['status'])
def status_cmd(message):
    bot.reply_to(message, "⚙️ <b>Bot is running</b>\nLogs: see bot.log", parse_mode="HTML")

@bot.message_handler(commands=['setdefaultphoto'])
def set_default_photo(message):
    global DEFAULT_PHOTO_FILE
    if not message.reply_to_message or not message.reply_to_message.photo:
        bot.reply_to(message, "⚠️ Please reply to a photo to set it as default.")
        return
    photo = message.reply_to_message.photo[-1]
    file_info = bot.get_file(photo.file_id)
    downloaded = bot.download_file(file_info.file_path)
    DEFAULT_PHOTO_FILE = f"default_photo_{message.chat.id}.jpg"
    with open(DEFAULT_PHOTO_FILE, "wb") as f:
        f.write(downloaded)
    bot.reply_to(message, "✅ Default photo set successfully!")

@bot.message_handler(commands=['photo'])
def photo_cmd(message):
    file_ref = get_user_photo(message.from_user.id)
    if not file_ref:
        bot.send_message(message.chat.id, "⚠️ No profile photo or default photo found.")
    else:
        if os.path.exists(file_ref):
            with open(file_ref, "rb") as f:
                bot.send_photo(message.chat.id, f)
        else:
            bot.send_photo(message.chat.id, file_ref)

@bot.message_handler(commands=['like'])
def like_cmd(message):
    if message.chat.type in ["group", "supergroup"] and message.chat.id != ALLOWED_GROUP:
        bot.reply_to(message, "⚠️ Only allowed in VIP group.", parse_mode="HTML")
        bot.leave_chat(message.chat.id)
        return
    if message.chat.type not in ["group", "supergroup"]:
        bot.reply_to(message, "⚠️ /like command only works in VIP group.", parse_mode="HTML")
        return

    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ Usage: /like <region> <uid>", parse_mode="HTML")
        return

    region, uid = args[1].lower(), args[2]
    base_text = "🔒 Preparing secure like session...\n🔎 Validating details..."
    loading_msg = bot.send_message(message.chat.id, "⏳ Initializing...", parse_mode="HTML")
    stages = [10, 25, 45, 65, 85, 100]
    animate_loading(message.chat.id, loading_msg.message_id, base_text, stages, delay=0.5)

    api_url = f"{LIKE_API_URL}?server_name={region}&uid={uid}&key={API_KEY}"
    try:
        resp = session.get(api_url, timeout=25)
        if resp.status_code != 200:
            bot.delete_message(message.chat.id, loading_msg.message_id)
            bot.send_message(message.chat.id, "🚨 API not responding.", parse_mode="HTML")
            return
        data = resp.json()
    except Exception as e:
        bot.delete_message(message.chat.id, loading_msg.message_id)
        bot.send_message(message.chat.id, f"❌ Connection Error: <code>{e}</code>", parse_mode="HTML")
        return

    try:
        bot.delete_message(message.chat.id, loading_msg.message_id)
    except: pass

    status = int(data.get("status", 0) or 0)

    likes_given = int(data.get("LikesGivenByAPI", 0) or 0)
    likes_before = int(data.get("LikesbeforeCommand", 0) or 0)
    likes_after = int(data.get("LikesafterCommand", 0) or 0)
    nick = data.get("PlayerNickname", "Unknown")
    uid_resp = data.get("UID", uid)

    full_txt = ""
    if status == 1:
        full_txt = (
            f"╔══════🌟👑🌟══════╗\n"
            f"      ✨ RS LIKE SUCCESS ✨\n"
            f"╚══════🌟👑🌟══════╝\n\n"
            f"🏆 PLAYER DETAILS\n╭──────────────────╮\n"
            f"  🪪 Name: {nick}\n  🆔 UID: {uid_resp}\n  🌍 Region: {region.upper()}\n"
            f"╰──────────────────╯\n\n💎 LIKE DETAILS\n╭───────────╮\n"
            f"  🎯 Sent: {likes_given}\n  📊 Before: {likes_before}\n  📈 After: {likes_after}\n"
            f"╰───────────╯\n\n🌟 STATUS: ✅ Success\n🔥 Join @CARTOONFUNNY03"
        )
    elif status == 2:
        full_txt = (
            f"╔══════⚠️💔⚠️══════╗\n"
            f"     ALREADY LIKED\n"
            f"╚══════⚠️💔⚠️══════╝\n\n"
            f"🏆 PLAYER DETAILS\n╭──────────────────╮\n"
            f"  🪪 Name: {nick}\n  🆔 UID: {uid_resp}\n  🌍 Region: {region.upper()}\n"
            f"╰──────────────────╯\n\n💎 LIKE STATUS\n╭───────────╮\n"
            f"  💖 Current Likes: {likes_after}\n  ⚡ VIP Credit restored\n╰───────────╯\n\n"
            f"⏳ You can try again later\n🔥 Join @CARTOONFUNNY03"
        )
    else:
        full_txt = (
            f"╔══════❌⚡❌══════╗\n"
            f"       LIKE FAILED\n"
            f"╚══════❌⚡❌══════╝\n\n"
            f"🏆 PLAYER DETAILS\n╭──────────────────╮\n"
            f"  🪪 Name: {nick}\n  🆔 UID: {uid_resp}\n  🌍 Region: {region.upper()}\n"
            f"╰──────────────────╯\n\n💎 LIKE ATTEMPT\n╭───────────╮\n"
            f"  🎯 Sent: 0\n  📊 Before: {likes_before}\n  📈 After: {likes_before}\n"
            f"╰───────────╯\n\n⚠️ Reason: Invalid UID / Server error\n🔥 Join @CARTOONFUNNY03"
        )

    # Send photo + text
    file_ref = get_user_photo(message.from_user.id)
    try:
        if file_ref:
            if os.path.exists(file_ref):
                with open(file_ref, "rb") as f:
                    bot.send_photo(message.chat.id, f, caption=full_txt, parse_mode="HTML")
            else:
                bot.send_photo(message.chat.id, file_ref, caption=full_txt, parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, full_txt, parse_mode="HTML")
    except Exception as e:
        log.error("Failed to send like photo: %s", e)
        bot.send_message(message.chat.id, full_txt, parse_mode="HTML")

# --- Run bot & flask ---
def run_bot():
    log.info("Starting Telegram polling...")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=40)
        except Exception as e:
            log.exception("Polling crashed, restarting in 5s: %s", e)
            time.sleep(5)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    log.info("Flask ping server started")
    run_bot()
