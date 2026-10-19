import glob
import os
import telebot
import yt_dlp

# Botingizning tokeni qo'shildi:
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

  # Foydalanuvchiga qidirilayotgani haqida xabar beramiz
  wait_msg = bot.send_message(
      chat_id, "🔍 Qo‘shiq qidirilmoqda va yuklanmoqda, biroz kuting..."
  )

  try:
    # Oldingi qolgan vaqtincha fayllarni tozalaymiz
    for f in glob.glob("song.*"):
      os.remove(f)

    # YouTube'dan audio qidirish va yuklab olish sozlamalari
    ydl_opts = {
        "format": "bestaudio",
        "outtmpl": "song.%(ext)s",
        "default_search": "ytsearch1",
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      ydl.download([query])

    # Yuklab olingan musiqani topib Telegramga yuboramiz
    files = glob.glob("song.*")
    if files:
      audio_file_path = files[0]
      with open(audio_file_path, "rb") as audio:
        bot.send_audio(chat_id, audio)

      # Xabarni o'chirib, telefon xotirasidagi vaqtincha faylni tozalaymiz
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
  print("Bot muvaffaqiyatli ishga tushdi...")
  bot.polling(none_stop=True)
