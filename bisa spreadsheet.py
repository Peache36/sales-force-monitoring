import os.path
import bcrypt
from datetime import datetime
import time
import urllib3  # Import urllib3 module

from google.auth.exceptions import RefreshError
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
RANGE_NAME = os.getenv('RANGE_NAME')
RANGE_CAPAIAN = os.getenv('RANGE_CAPAIAN')

# State constants
USERNAME, PASSWORD, MAIN_MENU, LOGGED_OUT = range(4)


def authenticate():
    # Hapus token atau kredensial yang tersimpan jika ada
    if os.path.exists("token.json"):
        os.remove("token.json")

    # Minta pengguna untuk melakukan autentikasi
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json",
                                                     SCOPES)
    credentials = flow.run_local_server(port=0)

    # Simpan kredensial yang baru dibuat
    with open("token.json", "w") as token:
        token.write(credentials.to_json())

    return credentials


def get_credentials():
    creds = None
    # Mencoba memuat kredensial yang tersimpan
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # Jika kredensial tidak ada atau tidak valid, lakukan autentikasi ulang
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("Token refreshed successfully.")
            except RefreshError as e:
                print("Error refreshing credentials:", e)
                print("Token expired or revoked. Re-authenticating...")
                creds = authenticate()
        else:
            # Jika tidak ada kredensial yang tersimpan, atau kredensial tidak valid
            # Minta pengguna untuk login
            print("No valid credentials found. Authenticating...")
            creds = authenticate()
    return creds


def main() -> None:
    """Start the bot."""
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


# Function to start
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Pilih /login atau /register ")
    return


def help(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Terdapat pilihan menu /login, /register, /logout")
    return


# Function to start registration process
def register_start(update: Update, context: CallbackContext) -> int:
    # Cek apakah pengguna sudah login
    if context.user_data.get('logged_in'):
        update.message.reply_text(
            "Anda sudah login. Untuk mendaftar ulang, silakan logout terlebih dahulu."
        )
        return ConversationHandler.END
    else:
        update.message.reply_text("Please choose a username:")
        return USERNAME


# Function to handle username registration
def register_username(update: Update, context: CallbackContext) -> int:
    username = update.message.text

    # Check if the username is unique
    if is_username_unique(username):
        context.user_data['username'] = username
        update.message.reply_text("Please choose a password:")
        return PASSWORD
    else:
        update.message.reply_text(
            "Username already exists. Please choose another username.")
        return ConversationHandler.END


# Function to check if the username is unique
def is_username_unique(username):
    creds = get_credentials()
    if not creds:
        return False

    service = build("sheets", "v4", credentials=creds)

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        values = result.get("values", [])

        if not values:
            return True

        for row in values:
            if row[0] == username:
                return False

        return True
    except HttpError as e:
        print("Error while checking username uniqueness", e)
        return False


# Function to handle password registration
def register_password(update: Update, context: CallbackContext) -> int:
    username = context.user_data['username']
    password = update.message.text

    # Hash the password and convert it to string
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    hashed_password_str = hashed_password.decode('utf-8')

    # Insert new user into spreadsheet
    if insert_user(username, hashed_password_str):
        update.message.reply_text(
            "Registration successful! You can now login.")
    else:
        update.message.reply_text("Registration failed. Please try again.")

    return ConversationHandler.END


# Function to insert new user into spreadsheet
def insert_user(username, password):
    creds = get_credentials()
    if not creds:
        return False

    service = build("sheets", "v4", credentials=creds)

    try:
        values = [[username, password]]
        body = {"values": values}
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=RANGE_NAME,
            valueInputOption="USER_ENTERED",
            body=body).execute()

        return True
    except HttpError as e:
        print("Error while inserting new user into spreadsheet", e)
        return False


# Function to handle login
def login(update: Update, context: CallbackContext) -> int:
    # Cek apakah pengguna sudah login
    if context.user_data.get('logged_in'):
        update.message.reply_text(
            "Anda sudah login. Untuk login ulang, silakan logout terlebih dahulu."
        )
        return ConversationHandler.END
    else:
        update.message.reply_text("Please enter your username:")
        return USERNAME


def authenticate_username(update: Update, context: CallbackContext) -> int:
    context.user_data['username'] = update.message.text
    update.message.reply_text("Please enter your password:")
    return PASSWORD


def authenticate_password(update: Update, context: CallbackContext) -> int:
    username = context.user_data['username']
    password = update.message.text

    # Retrieve hashed password from the spreadsheet
    hashed_password = retrieve_hashed_password(username)

    if hashed_password and bcrypt.checkpw(password.encode('utf-8'),
                                          hashed_password.encode('utf-8')):
        update.message.reply_text(
            "Authentication successful! Accessing main menu.")
        context.user_data['logged_in'] = True
        return MAIN_MENU
    else:
        update.message.reply_text(
            "Invalid username or password. Please try again.")
        return ConversationHandler.END


# Function to retrieve hashed password from the spreadsheet
def retrieve_hashed_password(username):
    creds = get_credentials()
    if not creds:
        return None

    service = build("sheets", "v4", credentials=creds)

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME).execute()
        values = result.get("values", [])

        if not values:
            return None

        for row in values:
            if row[0] == username:
                return row[1]

        return None
    except HttpError as e:
        print("Error while retrieving hashed password from spreadsheet", e)
        return None


# Function to handle logout
def logout(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "You have been logged out. You can log in again using /login.")
    context.user_data.pop('logged_in',
                          None)  # Remove 'logged_in' key from user_data
    return ConversationHandler.END


# Function to handle login after logout
def login_after_logout(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Please enter your username:")
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
                              '/sales_achivement - View today\'s sales data')


def sales_target(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        update.message.reply_text("======= Data Target =======\n" +
                                  "Update Tgl 26 Maret 2024\n" + " SPMMU11\n" +
                                  "Total Pencapaian : 40")
    else:
        update.message.reply_text("Please log in first using /login.")


# Function to handle /today_sales command
def sales_achivement(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        user_id = context.user_data['username']
        # Mendapatkan nama bulan saat ini
        bulan_dict = {
            "January": "Januari",
            "February": "Februari",
            "March": "Maret",
            "April": "April",
            "May": "Mei",
            "June": "Juni",
            "July": "Juli",
            "August": "Agustus",
            "September": "September",
            "October": "Oktober",
            "November": "November",
            "December": "Desember"
        }

        # Format: Month (English)
        current_month_en = datetime.now().strftime("%B")
        # Mendapatkan nama bulan dalam bahasa Indonesia
        current_month_id = bulan_dict.get(current_month_en)

        achievement = get_achievement_for_user(user_id)
        name = get_name_for_user(user_id)
        update_date = get_update_date()
        if achievement is not None:
            update.message.reply_text(
                f"=== Pencapaian Bulan {current_month_id} ===\n Update {update_date}\n \n User id : {user_id} \n Nama user : {name} \n Pencapaian saat ini : {achievement}"
            )
        else:
            update.message.reply_text("No sales achievement found for today.")
    else:
        update.message.reply_text("Please log in first using /login.")


def get_achievement_for_user(user_id):
    creds = get_credentials()
    if not creds:
        return None

    service = build("sheets", "v4", credentials=creds)

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_CAPAIAN).execute()
        values = result.get("values", [])

        if not values:
            return None

        for row in values:
            if row[0] == user_id:
                # Mengembalikan nilai pencapaian (sales) untuk pengguna yang ditemukan
                return row[1]
        return None
    except HttpError as e:
        print("Error while retrieving sales achievement from spreadsheet", e)
        return None


def get_name_for_user(user_id):
    creds = get_credentials()
    if not creds:
        return None

    service = build("sheets", "v4", credentials=creds)

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_CAPAIAN).execute()
        values = result.get("values", [])

        if not values:
            return None

        for row in values:
            if row[0] == user_id:
                # Mengembalikan nilai pencapaian (sales) untuk pengguna yang ditemukan
                return row[2]
        return None
    except HttpError as e:
        print("Error while retrieving name from spreadsheet", e)
        return None


def get_update_date():
    creds = get_credentials()
    if not creds:
        return None

    service = build("sheets", "v4", credentials=creds)

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_CAPAIAN).execute()
        values = result.get("values", [])

        if not values:
            return None

        # Mengambil tanggal update dari baris pertama (indeks 0) dan kolom ketiga (indeks 2)
        update_date = values[1][4]

        return update_date
    except HttpError as e:
        print("Error while retrieving update date from spreadsheet", e)
        return None


# Function to handle unknown commands/messages
def unknown(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Sorry, I didn't understand that command.")


def get_credentials():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                # Tunggu beberapa detik sebelum mencoba lagi
                time.sleep(5)
                # Coba lagi untuk menyegarkan kredensial
                try:
                    creds.refresh(Request())
                except Exception as e:
                    print(f"Error refreshing credentials after retry: {e}")
                    # Handle kesalahan refreshing credentials
                    return None
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    "credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
                # Simpan kredensial yang baru disegarkan
                with open("token.json", "w") as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Error getting new credentials: {e}")
                # Handle kesalahan mendapatkan kredensial baru
                return None
    return creds


if __name__ == '__main__':
    main()
