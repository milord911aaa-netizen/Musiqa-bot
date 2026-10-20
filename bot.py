# bot.py
import os
import glob
import logging
import threading
import time
import traceback
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from flask import Flask

# ------------------------------------------------------------------
# LOGGING SOZLAMALARI (Xatoliklarni Render loglarida ko'rish uchun)
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# SOZLAMALAR
# ------------------------------------------------------------------
TOKEN = "8879769179:AAEO_10-ElzL59qpU-RfjEdGJ9OPp7gdVyA"
bot = telebot.TeleBot(TOKEN)

# Render serverida vaqtinchalik fayllar uchun /tmp papkasidan foydalanish xavfsizroq
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

user_search_results = {}

# ------------------------------------------------------------------
# YT-DLP SOZLAMALARI (Blokirovkalarni chetlab o'tish)
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
    # YouTube blokirovkasini chetlab o'tish uchun mijozlarni kengaytirdik
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'web'],
            'skip': ['hls', 'dash']
        }
    }
}

# ------------------------------------------------------------------
# FLASK VEB-SERVER (Render.com uxlab qolmasligi uchun)
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ------------------------------------------------------------------
# QIDIRUV FUNKSIYASI
# ------------------------------------------------------------------
def search_youtube(query, max_results=7):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'ignoreerrors': True, # Xatoliklarni e'tiborsiz qoldirish
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            results = []
            if info and 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        results.append({
                            'title': entry.get('title', 'Noma\'lum'),
                            'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        })
            return results
        except Exception as e:
            logger.error(f"Qidiruv xatosi: {e}")
            return []

def send_search_results(chat_id, query):
    results = search_youtube(query)
    if not results:
        bot.send_message(chat_id, "😔 Hech narsa topilmadi. Boshqa so'z bilan urinib ko'ring.")
        return

    user_search_results[chat_id] = results

    text = "🎵 **Qidiruv natijalari:**\n\n"
    for i, item in enumerate(results, start=1):
        text += f"{i}. {item['title']}\n"

    text += "\n👇 Yuklab olish uchun raqamni bosing:"

    markup = InlineKeyboardMarkup()
    buttons = [InlineKeyboardButton(text=f" {i+1} ", callback_data=f"dl_{i}") for i in range(len(results))]
    markup.row(*buttons)

    bot.send_message(chat_id, text, reply_markup=markup, parse_mode='Markdown')

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
        send_search_results(message.chat.id, query)
    except Exception as e:
        logger.error(traceback.format_exc()) # Xatoni Render loglariga yozadi
        bot.reply_to(message, "❌ Qidiruvda xatolik yuz berdi. Iltimos, boshqa so'z bilan urinib ko'ring.")

# ------------------------------------------------------------------
# TUGMA BOSILGANDA YUKLASH
# ------------------------------------------------------------------
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
        bot.edit_message_text(
            f"⏳ **Yuklanmoqda:** {title}\n\nIltimos, kuting...",
            chat_id, message_id, parse_mode='Markdown'
        )

        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_id = info.get('id')
            
            # MP3 faylni topish
            mp3_file = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")
            if not os.path.exists(mp3_file):
                possible_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*"))
                mp3_files = [f for f in possible_files if f.endswith('.mp3')]
                if mp3_files:
                    mp3_file = mp3_files[0]
                else:
                    raise FileNotFoundError("MP3 fayl topilmadi.")

        with open(mp3_file, 'rb') as audio:
            bot.send_audio(
                chat_id,
                audio,
                title=title,
                performer="YouTube",
                caption=f"🎵 **{title}**\n\n✅ Bot orqali yuklab olindi."
            )

        bot.edit_message_text(
            f"✅ **Tayyor!** «{title}» yuborildi.",
            chat_id, message_id, parse_mode='Markdown'
        )

        # Barcha ortiqcha fayllarni o'chirish (xotirani tozalash)
        for f in glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*")):
            try:
                os.remove(f)
            except Exception:
                pass

    except Exception as e:
        logger.error(traceback.format_exc()) # Xatoni Render loglariga yozadi
        bot.edit_message_text(
            f"❌ **Yuklashda xatolik yuz berdi.**\n\nYouTube blokirovkasi bo'lishi mumkin. Boshqa qo'shiqni sinab ko'ring.",
            chat_id, message_id, parse_mode='Markdown'
        )

# ------------------------------------------------------------------
# ISHGA TUSHIRISH
# ------------------------------------------------------------------
if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    logger.info("🤖 Bot ishga tushdi...")
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            logger.error(f"Polling xatosi: {e}")
            time.sleep(5)
