# Простое окно входа и регистрации клиента CatCorp на PyQt6

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox
)

from client_network import (
    ClientNetwork,
    load_auth_token,
    save_auth_token,
    clear_auth_token,
    load_server_config_dict,
    save_server_config
)
from client_gui.main_window import MainWindow, load_settings, save_settings


class AuthWorker(QThread):
    """
    Поток для подключения к серверу, входа, регистрации и автоматического входа.
    """
    finished_signal = pyqtSignal(dict)

    def __init__(self, network: ClientNetwork, mode: str, username: str = "", password: str = "", token: str = ""):
        super().__init__()
        self.network = network
        self.mode = mode
        self.username = username
        self.password = password
        self.token = token

    def run(self):
        """
        Выполняется в отдельном потоке, чтобы окно не зависало.
        """
        if not self.network.connected:
            connected = self.network.connect()

            if not connected:
                self.finished_signal.emit({
                    "status": "error",
                    "message": "Не удалось подключиться к серверу",
                    "data": None
                })
                return

        if self.mode == "register":
            response = self.network.register(self.username, self.password)
        elif self.mode == "token":
            response = self.network.login_with_token(self.token)
        else:
            response = self.network.login(self.username, self.password)

        self.finished_signal.emit(response)


class ServerConfigDialog(QDialog):
    """
    Окно настройки адреса сервера перед входом.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Сервер")
        self.resize(320, 160)

        config = load_server_config_dict()

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("Хост сервера")
        self.host_input.setText(str(config.get("host", "127.0.0.1")))

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("Порт сервера")
        self.port_input.setText(str(config.get("port", 5000)))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Хост сервера:"))
        layout.addWidget(self.host_input)
        layout.addWidget(QLabel("Порт сервера:"))
        layout.addWidget(self.port_input)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_data(self) -> tuple[str, int] | None:
        host = self.host_input.text().strip()

        try:
            port = int(self.port_input.text().strip())
        except ValueError:
            return None

        if not host:
            return None

        if not 1 <= port <= 65535:
            return None

        return host, port



class LoginWindow(QWidget):
    """
    Простое окно авторизации и регистрации CatCorp.
    """

    def __init__(self):
        super().__init__()

        self.network = ClientNetwork()
        self.auth_worker = None
        self.main_window = None
        self.mode = "login"
        self.auto_login_started = False

        self.setWindowTitle("CatCorp — Вход")
        self.setFixedSize(380, 340)

        self._build_ui()
        self.apply_mode()

        QTimer.singleShot(150, self.try_auto_login)

    def _build_ui(self):
        """
        Создаёт простой интерфейс без кастомного дизайна.
        """
        title_label = QLabel("CatCorp")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.subtitle_label = QLabel("")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Логин")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.repeat_password_input = QLineEdit()
        self.repeat_password_input.setPlaceholderText("Повторите пароль")
        self.repeat_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.remember_login_checkbox = QCheckBox("Запомнить вход на этом ПК")
        self.remember_login_checkbox.setChecked(load_settings().get("remember_login", False))

        self.action_button = QPushButton()
        self.action_button.clicked.connect(self.handle_action)

        self.switch_button = QPushButton()
        self.switch_button.clicked.connect(self.switch_mode)

        self.server_button = QPushButton("Сервер")
        self.server_button.clicked.connect(self.open_server_dialog)

        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)

        form_layout = QVBoxLayout()
        form_layout.addWidget(title_label)
        form_layout.addWidget(self.subtitle_label)
        form_layout.addSpacing(10)
        form_layout.addWidget(self.username_input)
        form_layout.addWidget(self.password_input)
        form_layout.addWidget(self.repeat_password_input)
        form_layout.addWidget(self.remember_login_checkbox)
        form_layout.addWidget(self.action_button)
        form_layout.addWidget(self.switch_button)
        form_layout.addWidget(self.server_button)
        form_layout.addWidget(self.status_label)

        main_layout = QHBoxLayout()
        main_layout.addStretch()
        main_layout.addLayout(form_layout)
        main_layout.addStretch()

        self.setLayout(main_layout)

        self.username_input.returnPressed.connect(self.handle_action)
        self.password_input.returnPressed.connect(self.handle_action)
        self.repeat_password_input.returnPressed.connect(self.handle_action)

    def try_auto_login(self):
        """
        Пытается автоматически войти по сохранённому токену.
        """
        if self.auto_login_started:
            return

        settings = load_settings()

        if not settings.get("remember_login", False):
            clear_auth_token()
            return

        token = load_auth_token()

        if not token:
            return

        self.auto_login_started = True
        self.show_status("Автоматический вход...", is_error=False)
        self.set_form_enabled(False)

        self.auth_worker = AuthWorker(
            network=self.network,
            mode="token",
            token=token
        )

        self.auth_worker.finished_signal.connect(self.handle_auth_result)
        self.auth_worker.finished.connect(self.auth_worker.deleteLater)
        self.auth_worker.start()

    def apply_mode(self):
        """
        Переключает окно между входом и регистрацией.
        """
        self.status_label.setText("")

        if self.mode == "login":
            self.setWindowTitle("CatCorp — Вход")
            self.subtitle_label.setText("Вход в систему")
            self.repeat_password_input.hide()
            self.remember_login_checkbox.show()
            self.action_button.setText("Войти")
            self.switch_button.setText("Нет аккаунта? Зарегистрироваться")
        else:
            self.setWindowTitle("CatCorp — Регистрация")
            self.subtitle_label.setText("Создание аккаунта")
            self.repeat_password_input.show()
            self.remember_login_checkbox.hide()
            self.action_button.setText("Зарегистрироваться")
            self.switch_button.setText("Уже есть аккаунт? Войти")

    def switch_mode(self):
        """
        Переключает режим входа и регистрации.
        """
        if self.mode == "login":
            self.mode = "register"
        else:
            self.mode = "login"

        self.apply_mode()

    def handle_action(self):
        """
        Обрабатывает вход или регистрацию.
        """
        username = self.username_input.text().strip()
        password = self.password_input.text()
        repeat_password = self.repeat_password_input.text()

        if not username:
            self.show_status("Введите логин", is_error=True)
            return

        if not password:
            self.show_status("Введите пароль", is_error=True)
            return

        if self.mode == "register":
            if len(username) < 3:
                self.show_status("Логин должен быть не короче 3 символов", is_error=True)
                return

            if len(password) < 4:
                self.show_status("Пароль должен быть не короче 4 символов", is_error=True)
                return

            if password != repeat_password:
                self.show_status("Пароли не совпадают", is_error=True)
                return

        if self.mode == "login":
            self.show_status("Подключение...", is_error=False)
        else:
            self.show_status("Создание аккаунта...", is_error=False)

        self.set_form_enabled(False)

        self.auth_worker = AuthWorker(
            network=self.network,
            mode=self.mode,
            username=username,
            password=password
        )

        self.auth_worker.finished_signal.connect(self.handle_auth_result)
        self.auth_worker.finished.connect(self.auth_worker.deleteLater)
        self.auth_worker.start()

    def handle_auth_result(self, response: dict):
        """
        Получает результат входа, регистрации или автоматического входа из фонового потока.
        """
        self.set_form_enabled(True)

        status = response.get("status")
        message = response.get("message", "")

        if status == "ok" and self.mode == "register":
            self.show_status("Аккаунт создан. Выполните вход.", is_error=False)
            self.mode = "login"
            self.apply_mode()
            self.password_input.clear()
            self.repeat_password_input.clear()
            return

        if status == "ok":
            data = response.get("data", {})

            if isinstance(data, dict):
                token = data.get("auth_token")
                settings = load_settings()
                settings["remember_login"] = self.remember_login_checkbox.isChecked()
                save_settings(settings)

                if token and self.remember_login_checkbox.isChecked():
                    save_auth_token(token)
                else:
                    clear_auth_token()

            self.show_status("Авторизация успешна", is_error=False)
            self.open_main_window()
            return

        if self.auto_login_started:
            clear_auth_token()
            self.auto_login_started = False
            self.show_status("Сохранённый вход недействителен. Войдите вручную.", is_error=True)
            return

        self.show_status(message or "Ошибка", is_error=True)

    def open_server_dialog(self):
        """
        Открывает меню настройки host/port сервера.
        """
        dialog = ServerConfigDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()

        if data is None:
            QMessageBox.warning(self, "Ошибка", "Введите корректный хост и порт от 1 до 65535")
            return

        host, port = data

        if not save_server_config(host, port):
            QMessageBox.warning(self, "Ошибка", "Не удалось сохранить настройки сервера")
            return

        if self.network.connected:
            self.network.disconnect()

        self.show_status(f"Сервер сохранён: {host}:{port}", is_error=False)

    def show_status(self, text: str, is_error: bool):
        """
        Показывает сообщение о результате операции.
        """
        if is_error:
            self.status_label.setStyleSheet("color: red;")
        else:
            self.status_label.setStyleSheet("color: green;")

        self.status_label.setText(text)

    def set_form_enabled(self, enabled: bool):
        """
        Включает или отключает элементы формы.
        """
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.repeat_password_input.setEnabled(enabled)
        self.action_button.setEnabled(enabled)
        self.switch_button.setEnabled(enabled)
        self.server_button.setEnabled(enabled)

    def open_main_window(self):
        """
        Открывает главное окно после успешного входа.
        """
        self.main_window = MainWindow(self.network)
        self.main_window.show()
        self.close()

    def closeEvent(self, event):
        """
        Если главное окно не открыто, отключаем сеть при закрытии окна входа.
        """
        if self.main_window is None and self.network:
            self.network.disconnect()

        event.accept()
