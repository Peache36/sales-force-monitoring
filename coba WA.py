import pywhatkit as pw
from datetime import datetime


# Fungsi untuk mengirim pesan WhatsApp sekarang
def kirim_pesan_sekarang(nomor_telepon, pesan):
    # Dapatkan waktu saat ini
    waktu_sekarang = datetime.now()

    # Kirim pesan menggunakan waktu saat ini
    pw.sendwhatmsg(f"+{nomor_telepon}", pesan, waktu_sekarang.hour,
                   waktu_sekarang.minute)


# Contoh penggunaan
if __name__ == "__main__":
    # Nomor telepon penerima (dengan kode negara)
    nomor_penerima = "+6287840272518"

    # Pesan yang akan dikirim
    pesan_yang_dikirim = "Halo! Ini adalah pesan otomatis."

    # Kirim pesan sekarang
    kirim_pesan_sekarang(nomor_penerima, pesan_yang_dikirim)
