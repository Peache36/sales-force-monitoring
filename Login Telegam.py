import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import requests
import json
import random
import string
import bcrypt

# Token bot Telegram Bot X
bot_x_token = '7152049232:AAF8he-Slfpu9rSszW9muowx1SZdrs65eoI'
# Token bot Telegram Bot Y
bot_y_token = '6571891328:AAFfo7sknOviOuVYubeiphlXPQkcvNamTyI'

# Variabel global untuk menyimpan kode OTP yang telah di-hash
global_otp_hash = {}


def generate_otp():
    digits = string.digits
    otp = ''.join(random.choice(digits) for i in range(6))
    hashed_otp = bcrypt.hashpw(otp.encode('utf-8'), bcrypt.gensalt())
    return otp, hashed_otp


# Fungsi untuk menangani permintaan login dari pengguna
def start(update, context):
    chat_id = update.message.chat_id
    context.bot.send_message(chat_id=chat_id,
                             text="Silakan masukkan kode OTP:")
    otp, hashed_otp = generate_otp()
    global global_otp_hash
    global_otp_hash[
        chat_id] = hashed_otp  # Simpan hash kode OTP ke variabel global
    # Tambahkan permintaan kode OTP ke Bot Y secara otomatis saat pengguna memulai obrolan dengan bot
    url = f"https://api.telegram.org/bot{bot_y_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text":
        f"Kode OTP Anda: {otp}"  # Ini akan menjadi pesan yang dikirim ke Bot Y
    }
    response = requests.post(url, json=data)

    if response.status_code == 200:
        context.bot.send_message(
            chat_id=chat_id, text="Saya telah meminta kode OTP untuk Anda.")
    else:
        context.bot.send_message(chat_id=chat_id,
                                 text="Gagal meminta kode OTP dari Bot Y.")


# Fungsi untuk menangani pesan yang berisi kode OTP dari pengguna
def handle_otp(update, context):
    chat_id = update.message.chat_id
    user_input_otp = update.message.text
    global global_otp_hash
    if chat_id in global_otp_hash:  # Periksa apakah ada hash kode OTP yang disimpan untuk pengguna ini
        hashed_otp = global_otp_hash[chat_id]
        if bcrypt.checkpw(user_input_otp.encode('utf-8'), hashed_otp):
            context.bot.send_message(
                chat_id=chat_id,
                text="Verifikasi berhasil. Anda berhasil login!")
        else:
            context.bot.send_message(
                chat_id=chat_id,
                text="Verifikasi gagal. Kode OTP tidak valid.")
        del global_otp_hash[chat_id]  # Hapus hash kode OTP setelah digunakan
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text="Kode OTP tidak ditemukan. Silakan mulai kembali proses login."
        )


def main():
    updater = Updater(token=bot_x_token, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(
        MessageHandler(Filters.text & ~Filters.command, handle_otp))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
