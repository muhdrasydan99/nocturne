import sys
from PySide6.QtWidgets import QApplication
from main import create_nocturne_icon_pixmap

app = QApplication(sys.argv)
if not create_nocturne_icon_pixmap(256).save("nocturne.ico", "ICO"):
    sys.exit("Gagal hasilkan nocturne.ico")
print("nocturne.ico siap")
