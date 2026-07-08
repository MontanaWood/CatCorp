# client.py
# Точка входа клиентского GUI-приложения Intercom

import sys

from PyQt6.QtWidgets import QApplication

from client_gui.login_window import LoginWindow
from client_gui.main_window import app_icon


def main():
    """
    Запускает клиентское приложение Intercom.
    """
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())

    window = LoginWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
