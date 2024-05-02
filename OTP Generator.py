import random
import string
import telegram
from telegram.ext import Updater, CommandHandler

# Token bot Telegram Bot Y
bot_y_token = '6571891328:AAFfo7sknOviOuVYubeiphlXPQkcvNamTyI'


# Fungsi untuk menghasilkan kode OTP
def generate_otp():
    digits = string.digits
    return ''.join(random.choice(digits) for i in range(
        6))  # Ubah angka 6 sesuai dengan panjang kode OTP yang diinginkan


# Fungsi untuk menangani permintaan kode OTP dari Bot X
def request_otp(update, context):
    chat_id = update.effective_chat.id
    otp = generate_otp()
    context.bot.send_message(chat_id=chat_id, text=f"Kode OTP Anda: {otp}")


def main():
    updater = Updater(token=bot_y_token, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("requestotp", request_otp))
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
