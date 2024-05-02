import os
import mysql.connector
from mysql.connector import Error
from telegram import Update, ReplyKeyboardMarkup
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# State constants
USERNAME, PASSWORD, MAIN_MENU, LOGGED_OUT = range(4)


# Function to start
def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Pilih /login atau /register ")
    return


def help(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Terdapat pilihan menu /login , /register , /logout")
    return


# Function to start registration process
def register_start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Please choose a username:")
    return USERNAME


# Function to handle username registration
def register_username(update: Update, context: CallbackContext) -> int:
    context.user_data['username'] = update.message.text
    update.message.reply_text("Please choose a password:")
    return PASSWORD


# Function to handle password registration
def register_password(update: Update, context: CallbackContext) -> int:
    username = context.user_data['username']
    password = update.message.text

    # Insert new user into database
    if insert_user(username, password):
        update.message.reply_text(
            "Registration successful! You can now login.")
    else:
        update.message.reply_text("Registration failed. Please try again.")

    return ConversationHandler.END


# Function to insert new user into database
def insert_user(username, password):
    try:
        connection = mysql.connector.connect(host=os.getenv('DB_HOST'),
                                             user=os.getenv('DB_USER'),
                                             password=os.getenv('DB_PASSWORD'),
                                             database=os.getenv('DB_NAME'))
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO users (username, password, sales_today) VALUES (%s, %s, 0)",
            (username, password))
        connection.commit()
        return True
    except Error as e:
        print("Error while inserting new user into MySQL", e)
        return False
    finally:
        if (connection.is_connected()):
            cursor.close()
            connection.close()


# Function to authenticate user
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

    # Authenticate username and password
    if check_credentials(username, password):
        update.message.reply_text(
            "Authentication successful! Accessing main menu.")
        context.user_data['logged_in'] = True
        return MAIN_MENU
    else:
        update.message.reply_text(
            "Invalid username or password. Please try again.")
        return ConversationHandler.END


# Function to check user credentials from database
def check_credentials(username, password):
    try:
        connection = mysql.connector.connect(host=os.getenv('DB_HOST'),
                                             user=os.getenv('DB_USER'),
                                             password=os.getenv('DB_PASSWORD'),
                                             database=os.getenv('DB_NAME'))
        cursor = connection.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND password = %s",
            (username, password))
        user = cursor.fetchone()
        if user:
            return True
        else:
            return False
    except Error as e:
        print("Error while connecting to MySQL", e)
    finally:
        if (connection.is_connected()):
            cursor.close()
            connection.close()


# Function to handle logout
def logout(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "You have been logged out. You can log in again using /login.")
    context.user_data.pop('logged_in',
                          None)  # Remove 'logged_in' key from user_data
    return ConversationHandler.END


# Function to access main menu
def main_menu(update: Update, context: CallbackContext) -> None:
    reply_keyboard = [['/salestarget', '/todaysales']]

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


def sales_target(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        update.message.reply_text("Your sales target is...")
    else:
        update.message.reply_text("Please log in first using /login.")


# Function to handle /today_sales command
def today_sales(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        update.message.reply_text("Today's sales data is...")
    else:
        update.message.reply_text("Please log in first using /login.")


# Function to handle unknown commands/messages
def unknown(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Sorry, I didn't understand that command.")


def main() -> None:
    # Create the Updater and pass it your bot's token
    updater = Updater(os.getenv('TELEGRAM_BOT_TOKEN'))

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("help", help))
    dispatcher.add_handler(CommandHandler("logout",
                                          logout))  # Add logout command
    dispatcher.add_handler(CommandHandler("salestarget", sales_target))
    dispatcher.add_handler(CommandHandler("todaysales", today_sales))

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
        fallbacks=[])
    dispatcher.add_handler(conv_handler_login)

    # Add conversation handler when logged out

    # Add handler for unknown commands/messages
    dispatcher.add_handler(MessageHandler(Filters.command, unknown))

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C
    updater.idle()


def handle_logged_out(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Please log in using /login.")
    return ConversationHandler.END


if __name__ == '__main__':
    main()
