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


# Function to update last login time in the database
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


# Function to check session expiry
def check_session_expiry(username):
    connection = connect_to_database()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute("SELECT last_login FROM user WHERE username = %s",
                           (username, ))
            last_login = cursor.fetchone()
            if last_login:
                last_login_time = last_login[0]
                # Check if last login was more than 24 hours ago
                if (datetime.datetime.now() -
                        last_login_time).total_seconds() > 24 * 3600:
                    return True  # Session expired
        except Error as e:
            print("Error checking session expiry:", e)
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return False  # Session is still active


# Function to handle login
def login(update: Update, context: CallbackContext) -> int:
    if context.user_data.get('logged_in'):
        update.message.reply_text("You are already logged in.")
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "Please enter your Sales Force ID (Format: SFxxx):")
        # Remove login data if exists
        context.user_data.pop('username', None)
        context.user_data.pop('logged_in', None)
        return USERNAME


# Function to handle username authentication
def authenticate_username(update: Update, context: CallbackContext) -> int:
    username = update.message.text
    context.user_data['username'] = username
    chat_id = update.message.chat_id
    otp, hashed_otp = generate_otp()
    global global_otp_hash
    global_otp_hash[chat_id] = hashed_otp  # Store OTP hash in global variable
    # Automatically send OTP request to Bot Y when user starts conversation with the bot
    url = f"https://api.telegram.org/bot{os.getenv('OTP_BOT_TOKEN')}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text":
        f"Your OTP Code: {otp}"  # This will be the message sent to the OTP Bot
    }
    response = requests.post(url, json=data)

    if response.status_code == 200:
        context.bot.send_message(chat_id=chat_id,
                                 text="Please enter the OTP code:")
    else:
        context.bot.send_message(chat_id=chat_id,
                                 text="Failed to request OTP code")
    context.user_data.pop('logged_in', None)
    return OTP


# Function to handle OTP authentication
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
                    "Authentication successful! You can now access available menu"
                )
                context.user_data['logged_in'] = True
                context.user_data['last_login'] = datetime.datetime.now(
                )  # Update last login time
                update_last_login(
                    username)  # Update last login time in the database
                return MAIN_MENU
            else:
                update.message.reply_text(
                    "Your account is currently inactive. Please contact the administrator."
                )
                return ConversationHandler.END
    else:
        update.message.reply_text(
            "Verification failed. OTP code is not valid.")
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
                return 'inactive'
        except Error as e:
            print("Error while retrieving user status from MySQL", e)
            return 'inactive'
        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()
    return 'inactive'


# Function to handle logout
def logout(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "You have been logged out. Please log in again to access available menu."
    )
    context.user_data.pop('logged_in', None)
    context.user_data.pop('last_login', None)  # Remove last login time
    return ConversationHandler.END


# Function to handle login after logout
def login_after_logout(update: Update, context: CallbackContext) -> int:
    if context.user_data.get('logged_in'):
        update.message.reply_text("You are already logged in.")
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "Please enter your Sales Force ID (Format: SFxxx):")
        return USERNAME


# Function to access main menu
def main_menu(update: Update, context: CallbackContext) -> None:
    reply_keyboard = [['/salestarget', '/salesachievement']]

    update.message.reply_text(
        'Main Menu:',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard,
                                         one_time_keyboard=True),
    )


# Function to handle menu options
def menu_options(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(
        'Main Menu:\n'
        '/salestarget - View your sales target\n'
        '/salesachievement - View your sales achievement')


# Function to handle /salestarget command
def sales_target(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        # Get username of logged in user
        username = context.user_data.get('username')

        # Check if session has expired
        if check_session_expiry(username):
            update.message.reply_text(
                "Your session has expired. Please log in again.")
            context.user_data.pop('logged_in', None)
            context.user_data.pop('last_login', None)
            return ConversationHandler.END

        # Proceed with fetching sales target data
        # Your implementation here
        update.message.reply_text("Fetching sales target data...")
    else:
        update.message.reply_text("Please log in first!")


# Function to handle /salesachievement command
def sales_achievement(update: Update, context: CallbackContext) -> None:
    if context.user_data.get('logged_in'):
        # Get username of logged in user
        username = context.user_data.get('username')

        # Check if session has expired
        if check_session_expiry(username):
            update.message.reply_text(
                "Your session has expired. Please log in again.")
            context.user_data.pop('logged_in', None)
            context.user_data.pop('last_login', None)
            return ConversationHandler.END

        # Proceed with fetching sales achievement data
        # Your implementation here
        update.message.reply_text("Fetching sales achievement data...")
    else:
        update.message.reply_text("Please log in first!")


# Function to handle unknown commands/messages
def unknown(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("Sorry, I didn't understand that command.")


def main() -> None:
    # Create the Updater and pass it your bot's token
    updater = Updater(os.getenv('TELEGRAM_BOT_TOKEN'))

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # Add command handlers
    dispatcher.add_handler(CommandHandler("start", login))
    dispatcher.add_handler(CommandHandler("salestarget", sales_target))
    dispatcher.add_handler(
        CommandHandler("salesachievement", sales_achievement))
    dispatcher.add_handler(CommandHandler("logout", logout))
    dispatcher.add_handler(CommandHandler("help", menu_options))

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
                    Filters.regex('^(Sales Target|Sales Achievement)$'),
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
