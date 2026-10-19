import glob
import os
from threading import Thread
from flask import Flask
import telebot
import yt_dlp

# Render uchun veb-server
app = Flask("")


@app.route("/")
def home():
  return "Bot ishlayapti va 24/7 rejimda!"


def run_web():
  # Render avtomatik beradigan PORT'ni olamiz
  port = int(os.environ.get("PORT", 8080))
  app.run(host="0.0.0.0", port=port)


# Botingiz tokeni
TOKEN = "8879769179:AAEO_10-ElzL59qpU-RfjEdGJ9OPp7gdVyA"
bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=["start"])
def start(message):
  bot.reply_to(
      message,
      "Salom! 🎵 Menga istalgan qo‘shiq nomini yuboring, men uni topib yuklab"
      " beraman.",
  )


@bot.message_handler(func=lambda m: True)
def handle_message(message):
  query = message.text
  chat_id = message.chat.id

  wait_msg = bot.send_message(
      chat_id, "🔍 Qo‘shiq qidirilmoqda va yuklanmoqda, biroz kuting..."
  )

  try:
    for f in glob.glob("song.*"):
      os.remove(f)

    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": "song.%(ext)s",
        "default_search": "ytsearch1",
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      ydl.download([query])

    files = glob.glob("song.*")
    if files:
      audio_file_path = files[0]
      with open(audio_file_path, "rb") as audio:
        bot.send_audio(chat_id, audio)

      bot.delete_message(chat_id, wait_msg.message_id)
      os.remove(audio_file_path)
    else:
      bot.edit_message_text(
          "❌ Afsuski, bu qo‘shiq topilmadi.", chat_id, wait_msg.message_id
      )

  except Exception as e:
    bot.edit_message_text(
        f"⚠️ Xatolik yuz berdi: {str(e)}", chat_id, wait_msg.message_id
    )


if __name__ == "__main__":
  # Veb-serverni alohida yo'nalishda ishga tushiramiz
  t = Thread(target=run_web)
  t.start()

  print("Bot Render uchun tayyor va ishga tushdi...")
  bot.polling(none_stop=True)
