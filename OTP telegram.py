from telegram.ext import Updater, CommandHandler
import random


# Fungsi untuk menangani perintah /generateotp
def generate_otp(update, context):
    otp = ''.join(random.choices('0123456789', k=6))
    context.bot.send_message(chat_id=update.message.chat_id,
                             text=f"Kode OTP Anda adalah: {otp}")


def main():
    # Buat objek Updater dan token bot dari BotFather
    updaters = Updater(token='6571891328:AAFfo7sknOviOuVYubeiphlXPQkcvNamTyI',
                       use_context=True)

    # Dapatkan dispatcher untuk mendaftarkan handler
    dispatchers = updaters.dispatcher

    # Daftarkan handler untuk perintah /generateotp
    dispatchers.add_handler(CommandHandler("generateotp", generate_otp))

    # Mulai polling untuk menangani perintah
    updaters.start_polling()

    # Jalankan bot hingga program dihentikan secara manual
    updaters.idle()


if __name__ == '__main__':
    main()
