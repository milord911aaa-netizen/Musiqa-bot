# bot.py
import os
import re
import threading
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
from flask import Flask

# ------------------------------------------------------------------
# SOZLAMALAR
# ------------------------------------------------------------------
TOKEN = "8879769179:AAEO_10-ElzL59qpU-RfjEdGJ9OPp7gdVyA"
bot = telebot.TeleBot(TOKEN)

# Qidiruv natijalarini vaqtincha saqlash uchun lug'at
# Kalit: foydalanuvchi ID si, Qiymat: qo'shiqlar ro'yxati
user_search_results = {}

# Audio fayllar saqlanadigan papka
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ------------------------------------------------------------------
# YT-DLP SOZLAMALARI (YouTube blokirovkalarini chetlab o'tish)
# ------------------------------------------------------------------
YDL_OPTS = {
    'format': 'bestaudio/best',
    'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'quiet': True,
    'no_warnings': True,
    # Render IP-manzilini bloklamasligi uchun maxsus sozlama
    'extractor_args': {
        'youtube': {
            'player_client': ['android']
        }
    }
}

# ------------------------------------------------------------------
# FLASK VEB-SERVER (Render.com uchun "keep-alive")
# ------------------------------------------------------------------
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is alive!"

def run_flask():
    """Flask serverni fonda ishga tushirish."""
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ------------------------------------------------------------------
# QIDIRUV VA NATIJALARNI KO'RSATISH
# ------------------------------------------------------------------
def search_youtube(query, max_results=8):
    """
    YouTube'dan qo'shiqlarni qidiradi va natijalarni qaytaradi.
    Har bir natija: {'title': ..., 'url': ...} ko'rinishida.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android']
            }
        }
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            results = []
            for entry in info.get('entries', []):
                if entry:
                    results.append({
                        'title': entry.get('title', 'Noma\'lum'),
                        'url': f"https://www.youtube.com/watch?v={entry['id']}"
                    })
            return results
        except Exception as e:
            print(f"Qidiruv xatosi: {e}")
            return []

def send_search_results(chat_id, query):
    """Qidiruv natijalarini ro'yxat va inline tugmalar bilan yuboradi."""
    results = search_youtube(query)
    if not results:
        bot.send_message(chat_id, "😔 Hech narsa topilmadi. Boshqa so'z bilan urinib ko'ring.")
        return

    # Natijalarni foydalanuvchi uchun saqlash
    user_search_results[chat_id] = results

    # Xabar matnini shakllantirish
    text = "🎵 **Qidiruv natijalari:**\n\n"
    for i, item in enumerate(results, start=1):
        text += f"{i}. {item['title']}\n"

    text += "\n👇 Yuklab olish uchun raqamni bosing:"

    # Inline tugmalar (raqamlar)
    markup = InlineKeyboardMarkup()
    buttons = []
    for i in range(len(results)):
        buttons.append(InlineKeyboardButton(
            text=f" {i+1} ",
            callback_data=f"dl_{i}"
        ))
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
    """Foydalanuvchi yuborgan matn bo'yicha qidiruv."""
    query = message.text.strip()
    if not query:
        bot.reply_to(message, "Iltimos, qo'shiq nomi yoki xonanda ismini yozing.")
        return

    bot.send_chat_action(message.chat.id, 'typing')
    send_search_results(message.chat.id, query)

# ------------------------------------------------------------------
# INLINE TUGMA BOSILGANDA (AUDIO YUKLASH)
# ------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: call.data.startswith('dl_'))
def download_audio(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    # Foydalanuvchi natijalarini olish
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

        # yt-dlp orqali audio yuklash
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=True)
            # Postprocessor natijasidan fayl nomini olish
            filename = ydl.prepare_filename(info)
            # FFmpeg MP3 ga o'girgandan so'ng fayl kengaytmasi .mp3 bo'ladi
            base, _ = os.path.splitext(filename)
            mp3_file = base + '.mp3'

        # Fayl mavjudligini tekshirish
        if not os.path.exists(mp3_file):
            # Ba'zan fayl nomi boshqacha bo'lishi mumkin
            possible = [f for f in os.listdir(DOWNLOAD_DIR) if f.endswith('.mp3')]
            if possible:
                mp3_file = os.path.join(DOWNLOAD_DIR, possible[0])
            else:
                raise FileNotFoundError("MP3 fayl topilmadi.")

        # Audio faylni yuborish
        with open(mp3_file, 'rb') as audio:
            bot.send_audio(
                chat_id,
                audio,
                title=title,
                performer="YouTube",
                caption=f"🎵 **{title}**\n\n✅ @{(bot.get_me()).username} orqali yuklab olindi."
            )

        # Xabarni yangilash
        bot.edit_message_text(
            f"✅ **Tayyor!** «{title}» yuborildi.",
            chat_id, message_id, parse_mode='Markdown'
        )

        # Faylni o'chirish (xotirani tejash)
        try:
            os.remove(mp3_file)
        except Exception as e:
            print(f"Faylni o'chirishda xato: {e}")

    except Exception as e:
        print(f"Yuklash xatosi: {e}")
        bot.edit_message_text(
            f"❌ **Xatolik yuz berdi.**\n\nIltimos, keyinroq qayta urinib ko'ring.",
            chat_id, message_id, parse_mode='Markdown'
        )

# ------------------------------------------------------------------
# ISHGA TUSHIRISH
# ------------------------------------------------------------------
if __name__ == '__main__':
    # Flask serverni fonda ishga tushirish
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("🤖 Bot ishga tushdi...")
    # Botni to'xtovsiz ishlatish (polling)
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=20)
        except Exception as e:
            print(f"Polling xatosi: {e}")
            time.sleep(5)
