from twilio.rest import Client
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
import os
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()

# Definisikan status
MEMASUKKAN_USERNAME, MEMASUKKAN_OTP = range(2)


# Fungsi untuk mengirimkan OTP melalui SMS menggunakan Twilio
def kirim_otp_sms(nomor_telepon, otp):
    # Ganti dengan SID, token, dan nomor Twilio yang sesuai
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    twilio_number = os.getenv('TWILIO_PHONE_NUMBER')

    client = Client(account_sid, auth_token)

    message = client.messages.create(body=f"Kode OTP Anda adalah: {otp}",
                                     from_=twilio_number,
                                     to=nomor_telepon)

    print("OTP telah dikirimkan melalui SMS.")


# Fungsi untuk memeriksa OTP yang dimasukkan oleh pengguna
def periksa_otp(otp, input_otp):
    return otp == input_otp


# Fungsi untuk memproses permintaan login
def login(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Silakan masukkan username Anda:")
    return MEMASUKKAN_USERNAME


# Fungsi untuk memproses username yang dimasukkan oleh pengguna
def masukkan_username(update: Update, context: CallbackContext) -> int:
    context.user_data['username'] = update.message.text
    otp = str(random.randint(1000, 9999))  # Generate OTP secara acak
    kirim_otp_sms(os.getenv("RECIPIENT_PHONE_NUMBER"),
                  otp)  # Ganti dengan nomor telepon penerima OTP
    context.user_data[
        'otp'] = otp  # Menyimpan nilai OTP ke dalam data pengguna untuk digunakan nanti
    update.message.reply_text(
        "Kode OTP telah dikirimkan melalui SMS. Silakan cek pesan Anda dan masukkan OTP:"
    )
    return MEMASUKKAN_OTP


# Fungsi untuk memproses OTP yang dimasukkan oleh pengguna
def masukkan_otp(update: Update, context: CallbackContext) -> int:
    input_otp = update.message.text
    otp = context.user_data.get(
        'otp')  # Mengambil OTP yang telah disimpan dari data pengguna
    if periksa_otp(otp, input_otp):
        username = context.user_data.get('username')
        update.message.reply_text(
            f"Login berhasil! Selamat datang, {username}!")
        context.user_data.clear(
        )  # Bersihkan data pengguna setelah login berhasil
    else:
        update.message.reply_text(
            "OTP yang Anda masukkan salah. Silakan coba lagi.")
    return ConversationHandler.END


def main():
    # Ganti dengan token bot Telegram Anda
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Buat handler conversation
    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('login', login)],
        states={
            MEMASUKKAN_USERNAME: [
                MessageHandler(Filters.text & ~Filters.command,
                               masukkan_username)
            ],
            MEMASUKKAN_OTP:
            [MessageHandler(Filters.text & ~Filters.command, masukkan_otp)],
        },
        fallbacks=[],
    )

    # Tambahkan conversation handler ke dispatcher
    dispatcher.add_handler(conversation_handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
