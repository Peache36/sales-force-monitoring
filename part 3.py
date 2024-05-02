import os
from dotenv import load_dotenv
import telebot
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

bot = telebot.TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))


# Fungsi untuk mengakses Google Sheets
def get_google_sheet():
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    creds = Credentials.from_service_account_file('credentials.json',
                                                  scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open(
        'Data-Telegram').sheet1  # Ganti dengan nama spreadsheet Anda
    return sheet


# Command untuk melakukan registrasi
@bot.message_handler(commands=['register'])
def register(message):
    chat_id = message.chat.id
    username = message.chat.username

    sheet = get_google_sheet()
    usernames = sheet.col_values(2)  # Ambil semua usernames dari kolom B
    if username in usernames:
        bot.send_message(chat_id, "Anda sudah terdaftar.")
    else:
        new_row = [str(len(usernames) + 1), username, '', '0', '0', 'inactive']
        sheet.append_row(new_row)
        bot.send_message(chat_id, "Registrasi berhasil.")


# Command untuk melakukan login
@bot.message_handler(commands=['login'])
def login(message):
    chat_id = message.chat.id
    username = message.chat.username

    sheet = get_google_sheet()
    usernames = sheet.col_values(2)  # Ambil semua usernames dari kolom B
    if username not in usernames:
        bot.send_message(chat_id, "Anda belum terdaftar.")
    else:
        cell = sheet.find(username)  # Cari baris yang sesuai dengan username
        sheet.update_cell(cell.row, 6,
                          'active')  # Update status menjadi 'active'
        bot.send_message(chat_id, "Login berhasil.")


# Command untuk melihat data pengguna
@bot.message_handler(commands=['profile'])
def profile(message):
    chat_id = message.chat.id
    username = message.chat.username

    sheet = get_google_sheet()
    usernames = sheet.col_values(2)  # Ambil semua usernames dari kolom B
    if username not in usernames:
        bot.send_message(chat_id, "Anda belum terdaftar.")
    else:
        cell = sheet.find(username)  # Cari baris yang sesuai dengan username
        user_data = sheet.row_values(
            cell.row)  # Ambil data pengguna dari baris tersebut
        msg = f"ID: {user_data[0]}\nUsername: {user_data[1]}\nSales Target: {user_data[3]}\nSales Today: {user_data[4]}\nStatus: {user_data[5]}"
        bot.send_message(chat_id, msg)


# Command untuk melakukan logout
@bot.message_handler(commands=['logout'])
def logout(message):
    chat_id = message.chat.id
    username = message.chat.username

    sheet = get_google_sheet()
    usernames = sheet.col_values(2)  # Ambil semua usernames dari kolom B
    if username not in usernames:
        bot.send_message(chat_id, "Anda belum terdaftar.")
    else:
        cell = sheet.find(username)  # Cari baris yang sesuai dengan username
        sheet.update_cell(cell.row, 6,
                          'inactive')  # Update status menjadi 'inactive'
        bot.send_message(chat_id, "Logout berhasil.")


bot.polling()
