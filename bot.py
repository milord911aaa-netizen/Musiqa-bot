# bot.py
import os
import glob
import logging
import traceback
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Update
import yt_dlp
from flask import Flask, request

# ------------------------------------------------------------------
# LOGGING VA SOZLAMALAR
# ------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = "8879769179:AAEO_10-ElzL59qpU-RfjEdGJ9OPp7gdVyA"

# Render.com'dagi havolangiz
RENDER_URL = "https://musiqa-bot-q6xp.onrender.com" 
WEBHOOK_PATH = f"/webhook/{TOKEN}"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
user_search_results = {}

# ------------------------------------------------------------------
# YT-DLP SOZLAMALARI
# ------------------------------------------------------------------
YDL_OPTS = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True,
    'noplaylist': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'web'],
            'skip': ['hls', 'dash']
        }
    }
}

# ------------------------------------------------------------------
# BOT HANDLERLARI
# ------------------------------------------------------------------
@bot.message_handler(commands=['start'])
def start_command(message):
    welcome_text = (
        "👋 **Salom! Men musiqa botiman.**\n\n"
        "🎤 Xonanda ismini yoki qo'shiq nomini yuboring — "
        "men YouTube'dan eng mos qo'shiqlarni topib beraman.\n\n"
        "📥 Keyin raqamli tugmalardan birini bosib, "
        "musiqani MP3 formatida yuklab olasiz."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_query(message):
    query = message.text.strip()
    if not query:
        return
    bot.send_chat_action(message.chat.id, 'typing')
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'ignoreerrors': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web']}}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch7:{query}", download=False)
            results = []
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        results.append({
                            'title': entry.get('title', 'Noma\'lum'),
                            'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        })
        
        if not results:
            bot.send_message(message.chat.id, "😔 Hech narsa topilmadi. Boshqa so'z bilan urinib ko'ring.")
            return

        user_search_results[message.chat.id] = results

        text = "🎵 **Qidiruv natijalari:**\n\n"
        for i, item in enumerate(results, start=1):
            text += f"{i}. {item['title']}\n"
        text += "\n👇 Yuklab olish uchun raqamni bosing:"

        markup = InlineKeyboardMarkup()
        buttons = [InlineKeyboardButton(text=f" {i+1} ", callback_data=f"dl_{i}") for i in range(len(results))]
        markup.row(*buttons)

        bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(traceback.format_exc())
        bot.reply_to(message, "❌ Qidiruvda xatolik yuz berdi. Iltimos, boshqa so'z bilan urinib ko'ring.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('dl_'))
def download_audio(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    results = user_search_results.get(chat_id)
    
    if not results:
        bot.answer_callback_query(call.id, "⚠️ Natijalar topilmadi. Qaytadan qidiring.")
        return

    try:
        index = int(call.data.split('_')[1])
        if index >= len(results):
            bot.answer_callback_query(call.id, "❌ Noto'g'ri tanlov.")
            return

        selected = results[index]
        video_url = selected['url']
        title = selected['title']

        bot.answer_callback_query(call.id, f"⏳ «{title}» yuklanmoqda...")
        bot.edit_message_text(f"⏳ **Yuklanmoqda:** {title}\n\nIltimos, kuting...", chat_id, message_id, parse_mode='Markdown')

        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_id = info.get('id')
            mp3_file = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
            
            if not os.path.exists(mp3_file):
                possible = glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*"))
                mp3s = [f for f in possible if f.endswith('.mp3')]
                if mp3s:
                    mp3_file = mp3s[0]
                else:
                    raise FileNotFoundError("MP3 fayl topilmadi.")

        with open(mp3_file, 'rb') as audio:
            bot.send_audio(
                chat_id, audio, title=title, performer="YouTube",
                caption=f"🎵 **{title}**\n\n✅ Bot orqali yuklab olindi."
            )

        bot.edit_message_text(f"✅ **Tayyor!** «{title}» yuborildi.", chat_id, message_id, parse_mode='Markdown')

        # Fayllarni tozalash
        for f in glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*")):
            try:
                os.remove(f)
            except Exception:
                pass
    except Exception as e:
        logger.error(traceback.format_exc())
        bot.edit_message_text("❌ **Yuklashda xatolik yuz berdi.**", chat_id, message_id, parse_mode='Markdown')

# ------------------------------------------------------------------
# FLASK WEBHOOK ENDPOINTLARI
# ------------------------------------------------------------------
@app.route(WEBHOOK_PATH, methods=['POST'])
def telegram_webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    return "Forbidden", 403

@app.route("/")
def index():
    return "Bot serveri faol va ishlayapti!"

# ------------------------------------------------------------------
# SERVERNI ISHGA TUSHIRISH VA WEBHOOKNI O'RNATISH
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Avvalgi barcha eski webhook va pollinglarni tozalash (409 xatosini yo'qotish uchun)
    bot.remove_webhook()
    
    # Yangi webhookni ro'yxatdan o'tkazish
    full_webhook_url = RENDER_URL + WEBHOOK_PATH
    bot.set_webhook(url=full_webhook_url)
    logger.info(f"🚀 Webhook o'rnatildi: {full_webhook_url}")

    # Flask serverni ishga tushirish
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
