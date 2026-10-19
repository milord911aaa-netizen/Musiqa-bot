import glob
import os
from threading import Thread
from flask import Flask
import telebot
from telebot import types
import yt_dlp

# Веб-сервер для поддержания активности на Render
app = Flask("")


@app.route("/")
def home():
  return "Bot ishlayapti va 24/7 rejimda!"


def run_web():
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


# Ваш токен бота
TOKEN = "8879769179:AAEO_10-ElzL59qpU-RfjEdGJ9OPp7gdVyA"
bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=["start"])
def start(message):
  bot.reply_to(
      message,
      "Salom! 🎵 Menga qo‘shiqchi ismi yoki qo‘shiq nomini yuboring. Men"
      " sizga bir nechta variantlarni chiqarib beraman.",
  )


@bot.message_handler(func=lambda m: True)
def search_songs(message):
  query = message.text
  chat_id = message.chat.id

  msg = bot.send_message(chat_id, "🔍 Qidirilmoqda, biroz kuting...")

  try:
    # yt-dlp орқали 5 та вариант қидирамиз (VK бот каби)
    ydl_opts = {
        "extract_flat": True,
        "default_search": "ytsearch5",
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      info = ydl.extract_info(query, download=False)
      entries = info.get("entries", [])

    if not entries:
      bot.edit_message_text(
          "❌ Afsuski, hech qanday musiqa topilmadi.",
          chat_id,
          msg.message_id,
      )
      return

    # Inline тугмачалар яратимиз (VK бот дизайне)
    markup = types.InlineKeyboardMarkup()
    for entry in entries:
      title = entry.get("title", "Noma'lum qo'shiq")
      video_id = entry.get("id")

      # Текст жуда узун бўлиб кетмаслиги учун қисқартирамиз
      if len(title) > 45:
        title = title[:42] + "..."

      btn = types.InlineKeyboardButton(
          text=f"🎵 {title}", callback_data=f"dl_{video_id}"
      )
      markup.add(btn)

    bot.edit_message_text(
        "🎧 O'zingizga kerakli musiqani tanlang:",
        chat_id,
        msg.message_id,
        reply_markup=markup,
    )

  except Exception as e:
    bot.edit_message_text(
        f"⚠️ Xatolik yuz berdi: {str(e)}", chat_id, msg.message_id
    )


# Фойдаланувчи тугмани босганда ишлайдиган қисм
@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_"))
def download_selected_song(call):
  video_id = call.data.split("_")[1]
  chat_id = call.message.chat.id
  video_url = f"https://www.youtube.com/watch?v={video_id}"

  bot.answer_callback_query(call.id, "Musiqa yuklab olinmoqda...")
  wait_msg = bot.send_message(
      chat_id, "📥 Tanlangan musiqa yuklanmoqda, kuting..."
  )

  try:
    for f in glob.glob("song.*"):
      os.remove(f)

    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": "song.%(ext)s",
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      ydl.download([video_url])

    files = glob.glob("song.*")
    if files:
      audio_file_path = files[0]
      with open(audio_file_path, "rb") as audio:
        bot.send_audio(chat_id, audio)

      bot.delete_message(chat_id, wait_msg.message_id)
      os.remove(audio_file_path)
    else:
      bot.edit_message_text(
          "❌ Yuklab olishda xatolik yuz berdi.", chat_id, wait_msg.message_id
      )

  except Exception as e:
    bot.edit_message_text(
        f"⚠️ Xatolik: {str(e)}", chat_id, wait_msg.message_id
    )


if __name__ == "__main__":
  t = Thread(target=run_web)
  t.start()
  print("Bot ishga tushdi...")
  bot.polling(none_stop=True)
