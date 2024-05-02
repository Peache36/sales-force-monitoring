from telegram import Update
from telegram.ext import Updater, CommandHandler
import random

# Token bot otp_bot
TOKEN = "6571891328:AAFfo7sknOviOuVYubeiphlXPQkcvNamTyI"


# Fungsi untuk menghasilkan kode OTP
def generate_otp(update: Update, context):
    otp = random.randint(1000, 9999)
    update.message.reply_text(f"Kode OTP Anda adalah: {otp}")


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("generateotp", generate_otp))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
