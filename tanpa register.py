import os
import bcrypt
import datetime
import mysql.connector
import time
from mysql.connector import Error
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
import json
import schedule
import requests
import random
import string
import bcrypt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# State constants
USERNAME, OTP, MAIN_MENU, LOGGED_OUT = range(4)

global_otp_hash = {}


# Function to establish database connection
def connect_to_database():
    try:
        connection = mysql.connector.connect(host=os.getenv('DB_HOST'),
                                             user=os.getenv('DB_USER'),
                                             password=os.getenv('DB_PASSWORD'),
                                             database=os.getenv('DB_NAME'))
        return connection
    except Error as e:
        print("Error connecting to MySQL:", e)
        return None


# Function to establish database connection with reconnection
def connect_with_reconnection():
    max_retries = 3
    retry_count = 0
    while retry_count < max_retries:
        try:
            connection = mysql.connector.connect(
                host=os.getenv('DB_HOST'),
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                database=os.getenv('DB_NAME'))
            return connection
        except (Error, ConnectionResetError) as e:
            print("Error connecting to MySQL. Retrying...")
            time.sleep(5)  # Wait for a few seconds before retrying
            retry_count += 1
    raise RuntimeError("Unable to establish connection after multiple retries")


# Function to generate OTP
def generate_otp():
    digits = string.digits
    otp = ''.join(random.choice(digits) for i in range(6))
    hashed_otp = bcrypt.hashpw(otp.encode('utf-8'), bcrypt.gensalt())
    return otp, hashed_otp


# Function to start
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "=== Selamat datang di Monitor SF === \nUntuk kamu yang belum mempunyai akun silahkan hubungi admin. Atau login dengan menu /login "
    )
    return


# Function to handle help command
def help(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Terdapat menu \n /login - Untuk melakukan login akun \n /logout - Untuk melakukan logout \n /salestarget - Untuk melihat target penjualanmu \n /salesachivement - Untuk melihat capaian penjualanmu"
    )
    return


# Fungsi untuk memperbarui waktu login terakhir dalam basis data
def update_last_login(username):
    connection = connect_to_database()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "UPDATE user SET last_login = %s WHERE username = %s",
                (datetime.datetime.now(), username))
            connection.commit()
        except Error as e:
            print("Error updating last login time:", e)
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()


# Fungsi untuk memeriksa apakah sesi login telah berakhir
def check_session_expiry(username):
    connection = connect_to_database()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT last_login FROM user WHERE username = %s",
                           (username, ))
            last_login = cursor.fetchone()
            if last_login:
                # Mendapatkan waktu login terakhir dari basis data
                last_login_time = last_login[0]
                # Memeriksa apakah sudah melewati 24 jam atau tidak
                if (datetime.datetime.now() -
                        last_login_time).total_seconds() > 24 * 3600:
                    return True  # Sesinya telah berakhir
        except Error as e:
            print("Error checking session expiry:", e)
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return False  # Sesinya masih aktif


# Fungsi untuk menangani autentikasi OTP
def authenticate_otp(update: Update, context: CallbackContext) -> int:
    username = context.user_data['username']

    chat_id = update.message.chat_id
    user_input_otp = update.message.text
    global global_otp_hash
    if chat_id in global_otp_hash:  # Check if there is a stored OTP hash for this user
        hashed_otp = global_otp_hash[chat_id]
        if bcrypt.checkpw(user_input_otp.encode('utf-8'), hashed_otp):
            user_status = check_user_status(username)
            if user_status == 'active':
                update.message.reply_text(
                    "Autentifikasi berhasil ! Kamu sudah bisa mengakses menu tersedia"
                )
                context.user_data['logged_in'] = True
                context.user_data['last_login'] = datetime.datetime.now(
                )  # Update last login time
                update_last_login(
                    username)  # Update last login time in the database
                return MAIN_MENU
            else:
                update.message.reply_text(
                    "Akunmu saat ini tidak aktif. Silahkan hubungi administrator."
                )
                return ConversationHandler.END
        else:
            update.message.reply_text(
                "Verifikasi gagal. Kode OTP tidak valid.")
            return ConversationHandler.END


# Function to check user status
def check_user_status(username):
    connection = connect_with_reconnection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT status FROM user WHERE username = %s",
                           (username, ))
            user_status = cursor.fetchone()
            if user_status:
                return user_status[0]
            else:
                return 0
        except Error as e:
            print("Error while retrieving user status from MySQL", e)
            return 'inactive'
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return 'inactive'


# Function to handle login
def login(update: Update, context: CallbackContext) -> int:
    if context.user_data.get('logged_in'):
        update.message.reply_text("Kamu sudah login.")
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "Masukan Sales Force ID mu (Format: SFxxx) :")
        # Remove login data if exists
        context.user_data.pop('username', None)
        context.user_data.pop('logged_in', None)
        return USERNAME


# Fungsi untuk menangani autentikasi username
def authenticate_username(update: Update, context: CallbackContext) -> int:
    username = update.message.text
    context.user_data['username'] = username
    chat_id = update.message.chat_id
    otp, hashed_otp = generate_otp()
    global global_otp_hash
    global_otp_hash[chat_id] = hashed_otp  # Store OTP hash in global variable
    # Automatically send OTP request to Bot Y when user starts conversation with the bot

    connection = connect_with_reconnection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT telegram_id FROM user WHERE username = %s",
                       (username, ))
        tele_id = cursor.fetchone()
    url = f"https://api.telegram.org/bot{os.getenv('OTP_BOT_TOKEN')}/sendMessage"
    data = {
        "chat_id": tele_id[0],
        "text":
        f"Kode OTP Anda: {otp}"  # This will be the message sent to Bot Y
    }
    response = requests.post(url, json=data)

    if response.status_code == 200:
        context.bot.send_message(chat_id=chat_id,
                                 text="Silakan masukkan kode OTP:")
    else:
        context.bot.send_message(
            chat_id=chat_id,
            text=
            "Gagal meminta kode OTP, silahkan start @otp_sf_monitoring_bot terlebih dahulu "
        )
    context.user_data.pop('logged_in', None)
    return OTP


# Function to retrieve hashed password from the database
def retrieve_hashed_password(username):
    connection = connect_with_reconnection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT password FROM user WHERE username = %s",
                           (username, ))
            user = cursor.fetchone()
            if user:
                return user[0]
            else:
                return None
        except Error as e:
            print("Error while connecting to MySQL", e)
            return None
        finally:
            if (connection.is_connected()):
                cursor.close()
                connection.close()
    return None


# Function to handle logout
def logout(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Kamu telah logout. Silahkan login kembali untuk mengakses menu yang ada"
    )
    context.user_data.pop('logged_in', None)
    context.user_data.pop('last_login', None)  # Remove last login time
    return ConversationHandler.END


# Function to handle login after logout
def login_after_logout(update: Update, context: CallbackContext) -> int:
    if context.user_data.get('logged_in'):
        update.message.reply_text("Kamu sudah login.")
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "Masukan Sales Force ID mu (Format: SFxxx) :")
        return USERNAME


# Function to access main menu
def main_menu(update: Update, context: CallbackContext) -> None:
    reply_keyboard = [['/salestarget', '/salesachivement']]

    update.message.reply_text(
        'Main Menu:',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                         one_time_keyboard=True),
    )


# Function to handle menu options
def menu_options(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Main Menu:\n'
                              '/sales_target - View your sales target\n'
                              '/today_sales - View today\'s sales data')


# Function to handle /salestarget command
def sales_target(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        # Get username of logged in user
        username = context.user_data.get('username')

        # Check session expiry
        if check_session_expiry(username):
            update.message.reply_text(
                "Sesi Anda telah berakhir. Silakan login kembali.")
            context.user_data.pop('logged_in', None)
            return

        # Get first and last day of this month
        today = datetime.date.today()
        first_day_of_month = today.replace(day=1).strftime(
            '%Y%m%d')  # Convert to 'yyyymmdd' format
        last_day_of_month = (today.replace(
            day=1,
            month=today.month % 12 + 1,
            year=today.year if today.month < 12 else today.year + 1) -
                             datetime.timedelta(days=1)).strftime(
                                 '%Y%m%d')  # Convert to 'yyyymmdd' format

        # Get first and last day of last month
        first_day_of_last_month = (
            today.replace(day=1) - datetime.timedelta(days=1)).replace(
                day=1).strftime('%Y%m%d')  # Convert to 'yyyymmdd' format
        last_day_of_last_month = (today.replace(day=1) -
                                  datetime.timedelta(days=1)).strftime(
                                      '%Y%m%d')  # Convert to 'yyyymmdd' format

        try:
            # Connect to database
            connection = connect_with_reconnection()
            if connection:
                cursor = connection.cursor()

                # Count sales for this month from fact_re table based on logged in username
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_re WHERE id_partner = %s AND DATE_FORMAT(id_tgl_re, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_month, last_day_of_month))
                re_count_this_month = cursor.fetchone()[0]

                # Count sales for last month from fact_re table based on logged in username
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_re WHERE id_partner = %s AND DATE_FORMAT(id_tgl_re, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_last_month,
                     last_day_of_last_month))
                re_count_last_month = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_ps WHERE id_partner = %s AND DATE_FORMAT(id_tgl_ps, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_month, last_day_of_month))
                ps_count_this_month = cursor.fetchone()[0]

                # Count sales for last month from fact_re table based on logged in username
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_ps WHERE id_partner = %s AND DATE_FORMAT(id_tgl_ps, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_last_month,
                     last_day_of_last_month))
                ps_count_last_month = cursor.fetchone()[0]

                # Display information
                update.message.reply_text(
                    f"=== <b>Pencapaian</b> ===\nSF ID : {username}\n\n++ <b>Capaian RE</b> ++\nRE Bulan Lalu: {re_count_last_month}\nRE Bulan Ini: {re_count_this_month}\n\n++ <b>Capaian PS</b> ++\nPS Bulan Lalu: {ps_count_last_month}\nPS Bulan Ini: {ps_count_this_month}",
                    parse_mode='HTML')
        except Error as e:
            print("Error while retrieving sales for this month from MySQL", e)
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    else:
        update.message.reply_text("Silahkan login terlebih dahulu !")


# Function to handle /salesachivement command
def sales_achivement(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        # Get username of logged in user
        username = context.user_data.get('username')

        # Check session expiry
        if check_session_expiry(username):
            update.message.reply_text(
                "Sesi Anda telah berakhir. Silakan login kembali.")
            context.user_data.pop('logged_in', None)
            return

        # Get first and last day of this month
        today = datetime.date.today()
        first_day_of_month = today.replace(day=1).strftime(
            '%Y%m%d')  # Convert to 'yyyymmdd' format
        last_day_of_month = (today.replace(
            day=1,
            month=today.month % 12 + 1,
            year=today.year if today.month < 12 else today.year + 1) -
                             datetime.timedelta(days=1)).strftime(
                                 '%Y%m%d')  # Convert to 'yyyymmdd' format

        # Get first and last day of last month
        first_day_of_last_month = (
            today.replace(day=1) - datetime.timedelta(days=1)).replace(
                day=1).strftime('%Y%m%d')  # Convert to 'yyyymmdd' format
        last_day_of_last_month = (today.replace(day=1) -
                                  datetime.timedelta(days=1)).strftime(
                                      '%Y%m%d')  # Convert to 'yyyymmdd' format

        try:
            # Connect to database
            connection = connect_with_reconnection()
            if connection:
                cursor = connection.cursor()

                # Count sales for this month from fact_re table based on logged in username
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_re WHERE id_partner = %s AND DATE_FORMAT(id_tgl_re, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_month, last_day_of_month))
                re_count_this_month = cursor.fetchone()[0]

                # Count sales for last month from fact_re table based on logged in username
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_re WHERE id_partner = %s AND DATE_FORMAT(id_tgl_re, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_last_month,
                     last_day_of_last_month))
                re_count_last_month = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_ps WHERE id_partner = %s AND DATE_FORMAT(id_tgl_ps, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_month, last_day_of_month))
                ps_count_this_month = cursor.fetchone()[0]

                # Count sales for last month from fact_re table based on logged in username
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_ps WHERE id_partner = %s AND DATE_FORMAT(id_tgl_ps, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_last_month,
                     last_day_of_last_month))
                ps_count_last_month = cursor.fetchone()[0]

                # Display information
                update.message.reply_text(
                    f"=== <b>Pencapaian</b> ===\nSF ID : {username}\n\n++ <b>Capaian RE</b> ++\nRE Bulan Lalu: {re_count_last_month}\nRE Bulan Ini: {re_count_this_month}\n\n++ <b>Capaian PS</b> ++\nPS Bulan Lalu: {ps_count_last_month}\nPS Bulan Ini: {ps_count_this_month}",
                    parse_mode='HTML')
        except Error as e:
            print("Error while retrieving sales for this month from MySQL", e)
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    else:
        update.message.reply_text("Silahkan login terlebih dahulu !")


# Function to handle unknown commands/messages
def unknown(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Maaf, coba akses menu tersedia")


# Function to handle logged out state
def handle_logged_out(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Please log in using /login.")
    return ConversationHandler.END


def main() -> None:
    # Create the Updater and pass it your bot's token
    updater = Updater(os.getenv('TELEGRAM_BOT_TOKEN'))

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("logout", logout))
    dispatcher.add_handler(CommandHandler("salestarget", sales_target))
    dispatcher.add_handler(CommandHandler("salesachivement", sales_achivement))

    # Add conversation handler with login states
    conv_handler_login = ConversationHandler(
        entry_points=[CommandHandler('login', login)],
        states={
            USERNAME: [
                MessageHandler(Filters.text & ~Filters.command,
                               authenticate_username)
            ],
            OTP: [
                MessageHandler(Filters.text & ~Filters.command,
                               authenticate_otp)
            ],
            MAIN_MENU: [
                MessageHandler(
                    Filters.regex('^(Sales Target|Today\'s Sales)$'),
                    menu_options)
            ]
        },
        fallbacks=[CommandHandler("login", login_after_logout)])
    dispatcher.add_handler(conv_handler_login)

    # Add handler for unknown commands/messages
    dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()


if __name__ == '__main__':
    main()
