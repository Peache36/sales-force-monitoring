import mysql.connector

# Membuat koneksi ke server MySQL
connection = mysql.connector.connect(
    host="153.92.15.2",  # Ganti dengan host MySQL Anda
    user="u493782111_user",  # Ganti dengan username MySQL Anda
    password="User@user123",  # Ganti dengan password MySQL Anda
    database=
    "u493782111_test_sf"  # Ganti dengan nama database yang ingin Anda gunakan
)

# Membuat kursor untuk menjalankan perintah SQL
cursor = connection.cursor()

# Menjalankan perintah ALTER TABLE
cursor.execute(
    "ALTER TABLE user ADD COLUMN status VARCHAR(10) DEFAULT 'inactive'")

# Melakukan commit (jika diperlukan)
connection.commit()

# Menutup kursor dan koneksi
cursor.close()
connection.close()
