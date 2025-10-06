import os
import time
import logging
from threading import Thread
from flask import Flask
import requests
import telebot

# --- Config ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
LIKE_API_URL = os.getenv("LIKE_API_URL")
API_KEY = os.getenv("API_KEY")
ALLOWED_GROUP = int(os.getenv("ALLOWED_GROUP","-1002892874648"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("rs-like-bot")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

session = requests.Session()
from requests.adapters import HTTPAdapter, Retry
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504])
session.mount("https://", HTTPAdapter(max_retries=retries))
session.mount("http://", HTTPAdapter(max_retries=retries))

# --- Flask server for ping ---
app = Flask(__name__)
@app.route("/")
def home():
    return "RS Like Bot Final Demo UI (Alive!)",200
def run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))

# --- Helpers ---
def human_bar(pct,width=20):
    full = int((pct/100)*width)
    return "█"*full + "░"*(width-full)

def animate_loading(chat_id,message_id,base_text,stages,delay=0.5):
    emojis=["🔥","⚡","✨","💎","🌟","🚀"]
    try:
        for i,p in enumerate(stages):
            bar=human_bar(p)
            emoji=emojis[i%len(emojis)]
            txt=f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n" \
                f"┃ ⚡ <b>RS LIKE — PROCESSING</b> ⚡ ┃\n" \
                f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n" \
                f"{base_text}\n\n" \
                f"📊 Progress: <b>{p}%</b> {emoji}\n{bar}"
            try:
                bot.edit_message_text(txt,chat_id=chat_id,message_id=message_id,parse_mode="HTML")
            except: pass
            time.sleep(delay)
    except Exception as e:
        log.exception("Loading animation error: %s",e)

# --- Group restriction ---
@bot.message_handler(func=lambda msg: msg.chat.type in ["group","supergroup"])
def group_guard(message):
    if message.chat.id != ALLOWED_GROUP:
        bot.leave_chat(message.chat.id)
        return

# --- Commands ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    bot.reply_to(message,"👋 <b>Welcome to RS Like Bot Demo UI</b>\nSend likes: <code>/like &lt;region&gt; &lt;uid&gt;</code>\nExample: <code>/like bd 123456789</code>\n✨ Only allowed in VIP group.",parse_mode="HTML")

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(message,"📖 <b>Help</b>\n<code>/like &lt;region&gt; &lt;uid&gt;</code> — send likes.\n<code>/status</code> — bot status.",parse_mode="HTML")

@bot.message_handler(commands=['status'])
def status_cmd(message):
    bot.reply_to(message,"⚙️ <b>Bot is running</b>\nLogs: see bot.log",parse_mode="HTML")

@bot.message_handler(commands=['like'])
def like_cmd(message):
    args = message.text.split()
    if len(args)<3:
        bot.reply_to(message,"⚠️ Wrong usage!\n<code>/like &lt;region&gt; &lt;uid&gt;</code>",parse_mode="HTML")
        return
    region,uid=args[1].lower(),args[2]
    base_text="🔒 Preparing secure like session...\n🔎 Validating details..."
    loading_msg=bot.send_message(message.chat.id,"⏳ Initializing...",parse_mode="HTML")
    stages=[10,25,45,65,85,100]
    animate_loading(message.chat.id,loading_msg.message_id,base_text,stages,delay=0.5)

    api_url=f"{LIKE_API_URL}?server_name={region}&uid={uid}&key={API_KEY}"
    try:
        resp=session.get(api_url,timeout=25)
        if resp.status_code!=200:
            bot.delete_message(message.chat.id,loading_msg.message_id)
            bot.send_message(message.chat.id,"🚨 API not responding.",parse_mode="HTML")
            return
        data=resp.json()
    except Exception as e:
        bot.delete_message(message.chat.id,loading_msg.message_id)
        bot.send_message(message.chat.id,f"❌ Connection Error: <code>{e}</code>",parse_mode="HTML")
        return

    try: bot.delete_message(message.chat.id,loading_msg.message_id)
    except: pass

    status=int(data.get("status",0) or 0)

    # --- 2-step flashy success preview (2s) ---
    if status==1:
        quick_txt=f"┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n" \
                  f"┃   ⚡ LIKE — SUCCESSFUL   ┃\n" \
                  f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n" \
                  f"[📌 Preparing secure like successful]\n\n" \
                  f"📊 Progress: 100% ✅✅💎\n\n[RS LIKE BOT GOT {data.get('LikesGivenByAPI',0)} LIKE 😍]"
        msg_quick=bot.send_message(message.chat.id,quick_txt,parse_mode="HTML")
        time.sleep(2)
        try: bot.delete_message(message.chat.id,msg_quick.message_id)
        except: pass

        # --- Full success UI ---
        likes_given=int(data.get("LikesGivenByAPI",0) or 0)
        likes_before=int(data.get("LikesbeforeCommand",0) or 0)
        likes_after=int(data.get("LikesafterCommand",0) or 0)
        nick=data.get("PlayerNickname","Unknown")
        uid_resp=data.get("UID",uid)
        full_txt=f"╔══════🌟👑🌟══════╗\n" \
                 f"      ✨ RS LIKE SUCCESS ✨\n" \
                 f"╚══════🌟👑🌟══════╝\n\n" \
                 f"🏆 PLAYER DETAILS\n╭──────────────────╮\n" \
                 f"  🪪 Name: {nick}\n  🆔 UID: {uid_resp}\n  🌍 Region: {region.upper()}\n" \
                 f"╰──────────────────╯\n\n💎 LIKE DETAILS\n╭───────────╮\n" \
                 f"  🎯 Sent: {likes_given}\n  📊 Before: {likes_before}\n  📈 After: {likes_after}\n" \
                 f"\n╰───────────╯\n\n🌟 STATUS: ✅ Success\n🔥 Join @CARTOONFUNNY03"
        bot.send_message(message.chat.id,full_txt,parse_mode="HTML")
        return

    # --- Already Liked UI ---
    if status==2:
        nick=data.get("PlayerNickname","Unknown")
        uid_resp=data.get("UID",uid)
        txt=f"╔══════⚠️💖⚠️══════╗\n" \
            f"     ALREADY LIKED\n" \
            f"╚══════⚠️💖⚠️══════╝\n\n" \
            f"🏆 PLAYER DETAILS\n╭──────────────────╮\n" \
            f"  🪪 Name: {nick}\n  🆔 UID: {uid_resp}\n  🌍 Region: {region.upper()}\n" \
            f"╰──────────────────╯\n\n💎 LIKE STATUS\n╭───────────╮\n" \
            f"  💖 Current Likes: {data.get('LikesafterCommand','?')}\n  ⚡ VIP Credit restored\n╰───────────╯\n\n" \
            f"⏳ You can try again later\n🔥 Join @CARTOONFUNNY03"
        bot.send_message(message.chat.id,txt,parse_mode="HTML")
        return

    # --- Fail UI ---
    nick=data.get("PlayerNickname","Unknown")
    uid_resp=data.get("UID",uid)
    fail_txt=f"╔══════❌⚡❌══════╗\n" \
             f"       LIKE FAILED\n" \
             f"╚══════❌⚡❌══════╝\n\n" \
             f"🏆 PLAYER DETAILS\n╭──────────────────╮\n" \
             f"  🪪 Name: {nick}\n  🆔 UID: {uid_resp}\n  🌍 Region: {region.upper()}\n" \
             f"╰──────────────────╯\n\n💎 LIKE ATTEMPT\n╭───────────╮\n" \
             f"  🎯 Sent: 0\n  📊 Before: {data.get('LikesbeforeCommand',0)}\n  📈 After: {data.get('LikesbeforeCommand',0)}\n" \
             f"\n╰───────────╯\n\n⚠️ Reason: Invalid UID / Server error\n🔥 Join @CARTOONFUNNY03"
    bot.send_message(message.chat.id,fail_txt,parse_mode="HTML")

# --- Run bot & flask ---
def run_bot():
    log.info("Starting Telegram polling...")
    while True:
        try:
            bot.infinity_polling(timeout=60,long_polling_timeout=70)
        except Exception as e:
            log.exception("Polling crashed, restarting in 5s: %s",e)
            time.sleep(5)

if __name__=="__main__":
    Thread(target=run_web,daemon=True).start()
    log.info("Flask ping server started")
    run_bot()
