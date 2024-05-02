import os
import bcrypt
import datetime
import mysql.connector
import smtplib
import time
import threading
import requests
from mysql.connector import Error
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# State constants
USERNAME, PASSWORD, MAIN_MENU, LOGGED_OUT = range(4)


# Function to establish database connection
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


# Function to start
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "=== Selamat datang di Monitor SF === \nUntuk kamu yang belum mempunyai akun silahkan lakukan registrasi terlebih dahulu dengan mengakses menu /register. Atau login dengan menu /login "
    )
    return


# Function to handle help command
def help(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Terdapat menu \n /register - Untuk mendaftar akun baru \n /login - Untuk melakukan login akun \n /logout - Untuk melakukan logout \n /salestarget - Untuk melihat target penjualanmu \n /salesachivement - Untuk melihat capaian penjualanmu"
    )
    return


# Function to check duplicate username
def check_duplicate_username(username):
    try:
        connection = mysql.connector.connect(host=os.getenv('DB_HOST'),
                                             user=os.getenv('DB_USER'),
                                             password=os.getenv('DB_PASSWORD'),
                                             database=os.getenv('DB_NAME'))
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM user WHERE username = %s",
                       (username, ))
        count = cursor.fetchone()[0]
        return count > 0  # True jika sudah ada akun dengan nama pengguna yang sama
    except Error as e:
        print("Error while checking duplicate username in MySQL", e)
        return True  # Anggap ada duplikasi jika terjadi kesalahan
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


# Function to handle registration start
def register_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Silahkan masukkan Sales Force ID mu: (Format: SFxxx)")
    # Hapus data registrasi jika ada
    context.user_data.pop('username', None)
    context.user_data.pop('in_registration_process', None)
    return USERNAME


# Function to handle username registration
def register_username(update: Update, context: CallbackContext) -> int:
    username = update.message.text

    if check_duplicate_username(username):
        update.message.reply_text("Maaf, Sales Force ID ini sudah terdaftar")
        return ConversationHandler.END
    else:
        context.user_data['username'] = username
        update.message.reply_text("Silahkan masukkan passwordmu:")
        return PASSWORD


# Function to handle password registration
def register_password(update: Update, context: CallbackContext) -> int:
    username = context.user_data.get('username')
    if not username:
        update.message.reply_text("Proses registrasi dibatalkan.")
        return ConversationHandler.END

    password = update.message.text

    # Hash the password
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Insert new user into database
    if insert_user(username, hashed_password):
        update.message.reply_text(
            "Registrasi berhasil ! Silahkan tunggu konfirmasi admin")
        # Update created_date and status in the database
        # Set status pengguna menjadi 'active' setelah registrasi
        update_user_status(username, 'pending')
    else:
        update.message.reply_text("Registrasi Gagal ! Silahkan coba lagi")
    # Hapus tanda proses registrasi
    context.user_data.pop('in_registration_process', None)
    return ConversationHandler.END


# Function to handle password authentication
def authenticate_password(update: Update, context: CallbackContext) -> int:
    username = context.user_data['username']
    password = update.message.text

    # Retrieve hashed password from the database
    hashed_password = retrieve_hashed_password(username)

    if hashed_password and bcrypt.checkpw(password.encode('utf-8'),
                                          hashed_password.encode('utf-8')):
        # Check user status before allowing login
        user_status = check_user_status(username)
        if user_status == 'active':
            update.message.reply_text(
                "Autentifikasi berhasil ! Kamu sudah bisa mengakses menu tersedia"
            )
            context.user_data['logged_in'] = True
            return MAIN_MENU
        elif user_status == 'pending':
            update.message.reply_text(
                "Akunmu saat ini sedang menunggu konfirmasi administrator. Silahkan tunggu."
            )
            return ConversationHandler.END
        else:
            update.message.reply_text(
                "Akunmu saat ini tidak aktif. Silahkan hubungi administrator.")
            return ConversationHandler.END
    else:
        update.message.reply_text(
            "Sales Force ID atau Passwordmu salah. Silahkan ulangi lagi")
        return ConversationHandler.END


# Function to update user status
def update_user_status(username, status):
    connection = connect_with_reconnection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("UPDATE user SET status = %s WHERE username = %s",
                           (status, username))
            connection.commit()
        except Error as e:
            print("Error while updating user status in MySQL", e)
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()


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
                # Jika tidak ditemukan status pengguna, asumsikan status 'inactive'
                return 0
        except Error as e:
            print("Error while retrieving user status from MySQL", e)
            return 'inactive'
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return 'inactive'


# Function to insert new user into database
def insert_user(username, password):
    connection = connect_with_reconnection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO user (username, password, created_date, status) VALUES (%s, %s, NOW(),'pending')",
                (username, password))
            connection.commit()
            send_registration_notification(username)
            return True
        except Error as e:
            print("Error while inserting new user into MySQL", e)
            return False
        finally:
            if (connection.is_connected()):
                cursor.close()
                connection.close()
    return False


# Function to handle login
def login(update: Update, context: CallbackContext) -> int:
    if context.user_data.get('logged_in'):
        update.message.reply_text("Kamu sudah login.")
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "Masukan Sales Force ID mu (Format: SFxxx) :")
        # Hapus data login jika ada
        context.user_data.pop('username', None)
        context.user_data.pop('logged_in', None)
        return USERNAME


# Function to handle username authentication
def authenticate_username(update: Update, context: CallbackContext) -> int:
    username = update.message.text

    context.user_data['username'] = username
    update.message.reply_text("Masukkan password Anda:")
    # Hapus data login jika ada
    context.user_data.pop('logged_in', None)
    return PASSWORD


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


# Function to send registration notification
def send_registration_notification(username):
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = os.getenv('SMTP_PORT')

    # Subject and body of the email
    subject = "New User Registration"
    body = f"Dear Admin,\n\nA new user has registered with the username: {username}."

    # Create message container
    message = MIMEMultipart()
    message['From'] = sender_email
    message[
        'To'] = sender_email  # Menggunakan alamat email yang sama untuk pengirim dan penerima
    message['Subject'] = subject

    # Attach body to the email
    message.attach(MIMEText(body, 'plain'))

    # Connect to SMTP server and send email
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(message)


# Function to handle logout
def logout(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Kamu telah logout. Silahkan login kembali untuk mengakses menu yang ada"
    )
    context.user_data.pop('logged_in', None)
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
        # Ambil username dari user yang sedang login
        username = context.user_data.get('username')

        # Ambil tanggal awal dan akhir bulan ini
        today = datetime.date.today()
        first_day_of_month = today.replace(day=1).strftime(
            '%Y%m%d')  # Mengonversi ke format 'yyyymmdd'
        last_day_of_month = (today.replace(
            day=1,
            month=today.month % 12 + 1,
            year=today.year if today.month < 12 else today.year + 1) -
                             datetime.timedelta(days=1)).strftime(
                                 '%Y%m%d')  # Mengonversi ke format 'yyyymmdd'

        # Ambil tanggal awal dan akhir bulan lalu
        first_day_of_last_month = (
            today.replace(day=1) - datetime.timedelta(days=1)).replace(
                day=1).strftime('%Y%m%d')  # Mengonversi ke format 'yyyymmdd'
        last_day_of_last_month = (
            today.replace(day=1) - datetime.timedelta(days=1)).strftime(
                '%Y%m%d')  # Mengonversi ke format 'yyyymmdd'

        try:
            # Koneksi ke basis data
            connection = connect_with_reconnection()
            if connection:
                cursor = connection.cursor()

                # Hitung jumlah penjualan bulan ini dari tabel fact_re berdasarkan username yang login
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_re WHERE id_partner = %s AND DATE_FORMAT(id_tgl_re, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_month, last_day_of_month))
                re_count_this_month = cursor.fetchone()[0]

                # Hitung jumlah penjualan bulan lalu dari tabel fact_re berdasarkan username yang login
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_re WHERE id_partner = %s AND DATE_FORMAT(id_tgl_re, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_last_month,
                     last_day_of_last_month))
                re_count_last_month = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_ps WHERE id_partner = %s AND DATE_FORMAT(id_tgl_ps, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_month, last_day_of_month))
                ps_count_this_month = cursor.fetchone()[0]

                # Hitung jumlah penjualan bulan lalu dari tabel fact_re berdasarkan username yang login
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_ps WHERE id_partner = %s AND DATE_FORMAT(id_tgl_ps, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_last_month,
                     last_day_of_last_month))
                ps_count_last_month = cursor.fetchone()[0]

                # Menampilkan informasi
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
        # Ambil username dari user yang sedang login
        username = context.user_data.get('username')

        # Ambil tanggal awal dan akhir bulan ini
        today = datetime.date.today()
        first_day_of_month = today.replace(day=1).strftime(
            '%Y%m%d')  # Mengonversi ke format 'yyyymmdd'
        last_day_of_month = (today.replace(
            day=1,
            month=today.month % 12 + 1,
            year=today.year if today.month < 12 else today.year + 1) -
                             datetime.timedelta(days=1)).strftime(
                                 '%Y%m%d')  # Mengonversi ke format 'yyyymmdd'

        # Ambil tanggal awal dan akhir bulan lalu
        first_day_of_last_month = (
            today.replace(day=1) - datetime.timedelta(days=1)).replace(
                day=1).strftime('%Y%m%d')  # Mengonversi ke format 'yyyymmdd'
        last_day_of_last_month = (
            today.replace(day=1) - datetime.timedelta(days=1)).strftime(
                '%Y%m%d')  # Mengonversi ke format 'yyyymmdd'

        try:
            # Koneksi ke basis data
            connection = connect_with_reconnection()
            if connection:
                cursor = connection.cursor()

                # Hitung jumlah penjualan bulan ini dari tabel fact_re berdasarkan username yang login
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_re WHERE id_partner = %s AND DATE_FORMAT(id_tgl_re, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_month, last_day_of_month))
                re_count_this_month = cursor.fetchone()[0]

                # Hitung jumlah penjualan bulan lalu dari tabel fact_re berdasarkan username yang login
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_re WHERE id_partner = %s AND DATE_FORMAT(id_tgl_re, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_last_month,
                     last_day_of_last_month))
                re_count_last_month = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_ps WHERE id_partner = %s AND DATE_FORMAT(id_tgl_ps, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_month, last_day_of_month))
                ps_count_this_month = cursor.fetchone()[0]

                # Hitung jumlah penjualan bulan lalu dari tabel fact_re berdasarkan username yang login
                cursor.execute(
                    "SELECT COUNT(order_id_new) FROM fact_ps WHERE id_partner = %s AND DATE_FORMAT(id_tgl_ps, '%Y%m%d') BETWEEN %s AND %s",
                    (username, first_day_of_last_month,
                     last_day_of_last_month))
                ps_count_last_month = cursor.fetchone()[0]

                # Menampilkan informasi
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

    # Add conversation handler with registration states
    conv_handler_register = ConversationHandler(
        entry_points=[CommandHandler('register', register_start)],
        states={
            USERNAME: [
                MessageHandler(Filters.text & ~Filters.command,
                               register_username)
            ],
            PASSWORD: [
                MessageHandler(Filters.text & ~Filters.command,
                               register_password)
            ]
        },
        fallbacks=[])
    dispatcher.add_handler(conv_handler_register)

    # Add conversation handler with login states
    conv_handler_login = ConversationHandler(
        entry_points=[CommandHandler('login', login)],
        states={
            USERNAME: [
                MessageHandler(Filters.text & ~Filters.command,
                               authenticate_username)
            ],
            PASSWORD: [
                MessageHandler(Filters.text & ~Filters.command,
                               authenticate_password)
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
