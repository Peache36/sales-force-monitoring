import os
import uuid
import bcrypt
import logging
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

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logger = logging.getLogger(__name__)

# State constants
USERNAME, PASSWORD, MAIN_MENU, LOGGED_OUT = range(4)

# Google Sheets API setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SAMPLE_SPREADSHEET_ID = "1Xy2bxI0DW4R20nNKLw5um8j43Vh5zZiweWAYYryFf9s"  # Replace with your spreadsheet ID


def create_google_sheets_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json')
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('sheets', 'v4', credentials=creds)
    return service


def ensure_header(service):
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                range="Sheet1").execute()
    values = result.get('values', [])
    if not values:
        header = [
            'id', 'username', 'password', 'sales_target', 'sales_today',
            'status'
        ]
        body = {'values': [header]}
        sheet.values().update(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                              range="Sheet1!A:F",
                              valueInputOption="RAW",
                              body=body).execute()


def insert_user(username, password):
    service = create_google_sheets_service()
    ensure_header(service)
    sheet = service.spreadsheets()
    values = [[str(uuid.uuid4()), username, password, 0, 0,
               True]]  # Using uuid for unique id
    body = {'values': values}
    try:
        result = sheet.values().append(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                       range="Sheet1",
                                       valueInputOption="RAW",
                                       body=body).execute()
        return result
    except HttpError as e:
        logger.error(f"An error occurred: {e}")
        return None


def retrieve_user_credentials(username):
    service = create_google_sheets_service()
    sheet = service.spreadsheets()
    try:
        result = sheet.values().get(spreadsheetId=SAMPLE_SPREADSHEET_ID,
                                    range="Sheet1").execute()
        values = result.get('values', [])
        if not values:
            return None, None  # Return None for both username and password if no data is found
        header = values[0]  # Assuming the first row contains header
        username_index = header.index('username')
        password_index = header.index('password')
        for row in values[1:]:  # Start from the second row to skip the header
            if row[username_index] == username:
                return row[username_index], row[password_index]
        return None, None  # Return None if username is not found
    except HttpError as e:
        logger.error(f"An error occurred: {e}")
        return None, None


def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Pilih /login atau /register ")
    return


def register_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Please choose a username:")
    return USERNAME


def register_username(update: Update, context: CallbackContext) -> int:
    context.user_data['username'] = update.message.text
    update.message.reply_text("Please choose a password:")
    return PASSWORD


def register_password(update: Update, context: CallbackContext) -> int:
    username = context.user_data['username']
    password = update.message.text
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    if insert_user(username, hashed_password):
        update.message.reply_text(
            "Registration successful! You can now login.")
    else:
        update.message.reply_text("Registration failed. Please try again.")
    return ConversationHandler.END


def login(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Please enter your username:")
    return USERNAME


def authenticate_username(update: Update, context: CallbackContext) -> int:
    context.user_data['username'] = update.message.text
    update.message.reply_text("Please enter your password:")
    return PASSWORD


def authenticate_password(update: Update, context: CallbackContext) -> int:
    username = context.user_data['username']
    password = update.message.text
    stored_username, stored_password = retrieve_user_credentials(username)
    if stored_username and bcrypt.checkpw(password.encode('utf-8'),
                                          stored_password.encode('utf-8')):
        update.message.reply_text(
            "Authentication successful! Accessing main menu.")
        context.user_data['logged_in'] = True
        return MAIN_MENU
    else:
        update.message.reply_text(
            "Invalid username or password. Please try again.")
        return ConversationHandler.END


def main_menu(update: Update, context: CallbackContext) -> None:
    reply_keyboard = [['/salestarget', '/todaysales']]
    update.message.reply_text(
        'Main Menu:',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                         one_time_keyboard=True),
    )


def menu_options(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Main Menu:\n'
                              '/sales_target - View your sales target\n'
                              '/today_sales - View today\'s sales data')


def sales_target(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        update.message.reply_text("Your sales target is...")
    else:
        update.message.reply_text("Please log in first using /login.")


def today_sales(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        update.message.reply_text("Today's sales data is...")
    else:
        update.message.reply_text("Please log in first using /login.")


def unknown(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Sorry, I didn't understand that command.")


def logout(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "You have been logged out. You can log in again using /login.")
    context.user_data.pop('logged_in', None)
    return ConversationHandler.END


def login_after_logout(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Please enter your username:")
    return USERNAME


def handle_logged_out(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Please log in using /login.")
    return ConversationHandler.END


def main() -> None:
    updater = Updater(os.getenv('TELEGRAM_BOT_TOKEN'))
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("register", register_start))
    dispatcher.add_handler(CommandHandler("login", login))
    dispatcher.add_handler(CommandHandler("logout", logout))
    dispatcher.add_handler(CommandHandler("salestarget", sales_target))
    dispatcher.add_handler(CommandHandler("todaysales", today_sales))

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
            ]
        },
        fallbacks=[CommandHandler("login", login_after_logout)])
    dispatcher.add_handler(conv_handler_login)

    dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
