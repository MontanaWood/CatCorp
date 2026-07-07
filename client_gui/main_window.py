# client_gui/main_window.py
# Простое главное окно CatCorp без кастомного дизайна, но с новыми функциями

from html import escape
import base64
import json
import os
import sys
import winsound
from pathlib import Path
from datetime import datetime, timedelta

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QPoint, QSize
from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QComboBox,
    QMenu,
    QInputDialog,
    QFileDialog,
    QListView,
    QSystemTrayIcon,
    QApplication,
    QStyle,
    QFrame,
    QAbstractItemView
)
from PyQt6.QtGui import QAction, QIcon, QShortcut, QKeySequence

from client_network import ClientNetwork, load_auth_token, clear_auth_token


DEFAULT_SETTINGS = {
    "sound_enabled": True,
    "tray_notifications_enabled": True,
    "minimize_to_tray": True,
    "hide_notification_preview": False,
    "remember_login": False,
    "theme": "light",
    "muted_room_ids": [],
    "muted_user_ids": []
}


STATUS_LABELS = {
    "available": "доступен",
    "busy": "занят",
    "do_not_disturb": "не беспокоить",
    "away": "отошёл"
}


THEME_LABELS = {
    "light": "Светлая",
    "dark": "Тёмная"
}


LIGHT_THEME_QSS = """
QWidget {
    background-color: #f4f6fb;
    color: #1f2937;
    font-size: 10pt;
}

QDialog {
    background-color: #f4f6fb;
}

QLabel {
    color: #1f2937;
}

QLineEdit, QComboBox {
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 7px 9px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #2563eb;
}

QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 7px 12px;
}

QPushButton:hover {
    background-color: #1d4ed8;
}

QPushButton:pressed {
    background-color: #1e40af;
}

QPushButton:disabled {
    background-color: #94a3b8;
    color: #e5e7eb;
}

QCheckBox {
    spacing: 8px;
}

QListWidget {
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #dbe3ef;
    border-radius: 10px;
    padding: 4px;
}

QListWidget::item {
    padding: 8px;
    border-radius: 8px;
}

QListWidget::item:selected {
    background-color: #dbeafe;
    color: #111827;
}

QListWidget::item:hover {
    background-color: #eef2ff;
}

QMenu {
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #dbe3ef;
}

QMenu::item {
    padding: 7px 22px;
}

QMenu::item:selected {
    background-color: #dbeafe;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 5px;
    min-height: 32px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    border-radius: 5px;
    min-width: 32px;
}

QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
    background: transparent;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
}

QFrame#MessageBubbleOwn {
    background-color: #dbeafe;
    border: 1px solid #bfdbfe;
    border-radius: 12px;
}

QFrame#MessageBubbleOther {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}

QFrame#FileBubbleOwn {
    background-color: #e0f2fe;
    border: 1px solid #7dd3fc;
    border-radius: 12px;
}

QFrame#FileBubbleOther {
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
}

QFrame#ReplyPreview {
    background-color: #eff6ff;
    border-left: 3px solid #2563eb;
    border-radius: 6px;
}

QLabel#MessageSender {
    background-color: transparent;
    font-weight: 600;
    color: #111827;
}

QLabel#MessageText {
    background-color: transparent;
    color: #111827;
}

QLabel#MessageMeta {
    background-color: transparent;
    color: #64748b;
    font-size: 8pt;
}

QLabel#FileTitle {
    background-color: transparent;
    color: #111827;
    font-weight: 600;
}

QLabel#FileHint {
    background-color: transparent;
    color: #64748b;
    font-size: 8pt;
}

QWidget#MessageRow {
    background-color: transparent;
}
"""


DARK_THEME_QSS = """
QWidget {
    background-color: #111827;
    color: #e5e7eb;
    font-size: 10pt;
}

QDialog {
    background-color: #111827;
}

QLabel {
    color: #e5e7eb;
}

QLineEdit, QComboBox {
    background-color: #1f2937;
    color: #f9fafb;
    border: 1px solid #374151;
    border-radius: 8px;
    padding: 7px 9px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #60a5fa;
}

QPushButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 7px 12px;
}

QPushButton:hover {
    background-color: #3b82f6;
}

QPushButton:pressed {
    background-color: #1d4ed8;
}

QPushButton:disabled {
    background-color: #374151;
    color: #9ca3af;
}

QCheckBox {
    spacing: 8px;
}

QListWidget {
    background-color: #1f2937;
    color: #f9fafb;
    border: 1px solid #374151;
    border-radius: 10px;
    padding: 4px;
}

QListWidget::item {
    padding: 8px;
    border-radius: 8px;
}

QListWidget::item:selected {
    background-color: #1d4ed8;
    color: #ffffff;
}

QListWidget::item:hover {
    background-color: #374151;
}

QMenu {
    background-color: #1f2937;
    color: #f9fafb;
    border: 1px solid #374151;
}

QMenu::item {
    padding: 7px 22px;
}

QMenu::item:selected {
    background-color: #2563eb;
}

QDialogButtonBox QPushButton {
    min-width: 80px;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #4b5563;
    border-radius: 5px;
    min-height: 32px;
}

QScrollBar::handle:vertical:hover {
    background: #6b7280;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}

QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}

QScrollBar::handle:horizontal {
    background: #4b5563;
    border-radius: 5px;
    min-width: 32px;
}

QScrollBar::handle:horizontal:hover {
    background: #6b7280;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0px;
    background: transparent;
}

QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
}

QFrame#MessageBubbleOwn {
    background-color: #1d4ed8;
    border: 1px solid #2563eb;
    border-radius: 12px;
}

QFrame#MessageBubbleOther {
    background-color: #1f2937;
    border: 1px solid #374151;
    border-radius: 12px;
}

QFrame#FileBubbleOwn {
    background-color: #0f766e;
    border: 1px solid #14b8a6;
    border-radius: 12px;
}

QFrame#FileBubbleOther {
    background-color: #111827;
    border: 1px solid #4b5563;
    border-radius: 12px;
}

QFrame#ReplyPreview {
    background-color: #111827;
    border-left: 3px solid #60a5fa;
    border-radius: 6px;
}

QLabel#MessageSender {
    background-color: transparent;
    font-weight: 600;
    color: #f9fafb;
}

QLabel#MessageText {
    background-color: transparent;
    color: #f9fafb;
}

QLabel#MessageMeta {
    background-color: transparent;
    color: #cbd5e1;
    font-size: 8pt;
}

QLabel#FileTitle {
    background-color: transparent;
    color: #f9fafb;
    font-weight: 600;
}

QLabel#FileHint {
    background-color: transparent;
    color: #cbd5e1;
    font-size: 8pt;
}

QWidget#MessageRow {
    background-color: transparent;
}
"""


def normalize_theme(theme: str) -> str:
    """
    Возвращает корректное имя темы.
    """
    theme = str(theme or "").strip().lower()

    if theme not in THEME_LABELS:
        return "light"

    return theme


def apply_app_theme(settings: dict | None = None):
    """
    Применяет тему ко всему QApplication.
    """
    app = QApplication.instance()

    if app is None:
        return

    settings = settings or {}
    theme = normalize_theme(settings.get("theme", DEFAULT_SETTINGS.get("theme", "light")))

    if theme == "dark":
        app.setStyleSheet(DARK_THEME_QSS)
    else:
        app.setStyleSheet(LIGHT_THEME_QSS)


MAX_FILE_SIZE = 25 * 1024 * 1024


def format_file_size(size_bytes) -> str:
    """
    Форматирует размер файла для карточки.
    """
    try:
        size = int(size_bytes)
    except (TypeError, ValueError):
        size = 0

    units = ["Б", "КБ", "МБ", "ГБ"]
    value = float(size)

    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "Б":
                return f"{int(value)} {unit}"

            return f"{value:.1f} {unit}"

        value /= 1024

    return f"{size} Б"


def sanitize_download_filename(filename: str) -> str:
    """
    Очищает имя файла для сохранения в папку Загрузки.
    """
    filename = os.path.basename(str(filename or "file")).strip()

    for char in '<>:"|?*':
        filename = filename.replace(char, "_")

    filename = "".join(char for char in filename if ord(char) >= 32).strip(" .")

    if not filename:
        filename = "file"

    return filename[:255]


def unique_download_path(directory: Path, filename: str) -> Path:
    """
    Возвращает путь без перезаписи существующих файлов.
    """
    filename = sanitize_download_filename(filename)
    path = directory / filename

    if not path.exists():
        return path

    stem = Path(filename).stem
    suffix = Path(filename).suffix

    for index in range(1, 1000):
        candidate = directory / f"{stem} ({index}){suffix}"

        if not candidate.exists():
            return candidate

    return directory / f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"


def settings_path() -> str:
    """
    Возвращает путь к settings.json рядом с client.py или client.exe.
    """
    if getattr(sys, "frozen", False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    return os.path.join(app_dir, "settings.json")


def load_settings() -> dict:
    """
    Загружает локальные настройки клиента.
    """
    path = settings_path()

    if not os.path.exists(path):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(path, "r", encoding="utf-8") as file:
            loaded = json.load(file)

        settings = DEFAULT_SETTINGS.copy()
        settings.update(loaded)

        if not isinstance(settings.get("muted_room_ids"), list):
            settings["muted_room_ids"] = []

        if not isinstance(settings.get("muted_user_ids"), list):
            settings["muted_user_ids"] = []

        settings["theme"] = normalize_theme(settings.get("theme", DEFAULT_SETTINGS["theme"]))

        return settings

    except (OSError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    """
    Сохраняет локальные настройки клиента.
    """
    path = settings_path()

    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump(settings, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


def short_text(text: str, max_len: int = 70) -> str:
    """
    Делает короткий предпросмотр текста.
    """
    text = str(text or "").replace("\n", " ")

    if len(text) > max_len:
        return text[:max_len] + "..."

    return text


class NetworkSignals(QObject):
    """
    Сигналы для безопасной передачи событий из сетевого потока в GUI.
    """
    new_message = pyqtSignal(dict)
    users_status = pyqtSignal(list)
    disconnected = pyqtSignal()
    typing = pyqtSignal(dict)
    recent_chats = pyqtSignal(dict)
    edited_message = pyqtSignal(dict)
    new_room_message = pyqtSignal(dict)
    room_typing = pyqtSignal(dict)
    edited_room_message = pyqtSignal(dict)


class UserSelectDialog(QDialog):
    """
    Простое окно выбора пользователя для нового чата.
    """

    def __init__(self, users: list, current_user_id: int, parent=None):
        super().__init__(parent)

        self.selected_user = None
        self.setWindowTitle("Новый чат")
        self.resize(340, 440)

        self.users_list = QListWidget()

        for user in users:
            if user.get("id") == current_user_id:
                continue

            online = bool(user.get("online"))
            online_text = "online" if online else "offline"
            display_name = user.get("display_name") or user.get("username", "unknown")
            username = user.get("username", "unknown")
            status_text = STATUS_LABELS.get(user.get("user_status", "available"), "доступен")

            if online:
                item_text = f"{display_name} [{online_text}, {status_text}]"
            else:
                item_text = f"{display_name} [{online_text}]"

            if display_name != username:
                item_text += f" @{username}"

            if user.get("role") == "admin":
                item_text += " ★"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, user)
            self.users_list.addItem(item)

        self.users_list.itemDoubleClicked.connect(self.accept_selected_user)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept_selected_user)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Выберите пользователя:"))
        layout.addWidget(self.users_list)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def accept_selected_user(self):
        item = self.users_list.currentItem()

        if item is None:
            return

        self.selected_user = item.data(Qt.ItemDataRole.UserRole)
        self.accept()


class GroupCreateDialog(QDialog):
    """
    Окно создания группового чата.
    """

    def __init__(self, users: list, current_user_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Новая группа")
        self.resize(360, 460)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Название группы")

        self.users_list = QListWidget()

        for user in users:
            if user.get("id") == current_user_id:
                continue

            display_name = user.get("display_name") or user.get("username", "unknown")
            item = QListWidgetItem(display_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, user)
            self.users_list.addItem(item)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Название группы:"))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel("Участники:"))
        layout.addWidget(self.users_list)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_data(self) -> dict:
        member_ids = []

        for index in range(self.users_list.count()):
            item = self.users_list.item(index)

            if item.checkState() == Qt.CheckState.Checked:
                user = item.data(Qt.ItemDataRole.UserRole)
                member_ids.append(user.get("id"))

        return {
            "name": self.name_input.text().strip(),
            "member_ids": member_ids
        }


class GroupAddMembersDialog(QDialog):
    """
    Окно добавления новых участников в существующую группу.
    """

    def __init__(self, users: list, existing_member_ids: set[int], current_user_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить участников")
        self.resize(360, 460)

        self.users_list = QListWidget()

        for user in users:
            user_id = user.get("id")

            if user_id == current_user_id:
                continue

            if user_id in existing_member_ids:
                continue

            display_name = user.get("display_name") or user.get("username", "unknown")
            username = user.get("username", "unknown")

            item_text = display_name

            if display_name != username:
                item_text += f" @{username}"

            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, user)
            self.users_list.addItem(item)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Выберите пользователей:"))
        layout.addWidget(self.users_list)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_member_ids(self) -> list[int]:
        member_ids = []

        for index in range(self.users_list.count()):
            item = self.users_list.item(index)

            if item.checkState() == Qt.CheckState.Checked:
                user = item.data(Qt.ItemDataRole.UserRole)
                member_ids.append(user.get("id"))

        return member_ids


class SettingsDialog(QDialog):
    """
    Окно настроек клиента.
    """

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Настройки")
        self.resize(420, 330)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(THEME_LABELS["light"], "light")
        self.theme_combo.addItem(THEME_LABELS["dark"], "dark")

        current_theme = normalize_theme(settings.get("theme", DEFAULT_SETTINGS["theme"]))
        theme_index = self.theme_combo.findData(current_theme)

        if theme_index >= 0:
            self.theme_combo.setCurrentIndex(theme_index)

        self.sound_checkbox = QCheckBox("Звук уведомлений")
        self.sound_checkbox.setChecked(settings.get("sound_enabled", True))

        self.tray_notifications_checkbox = QCheckBox("Показывать уведомления в трее")
        self.tray_notifications_checkbox.setChecked(settings.get("tray_notifications_enabled", True))

        self.minimize_to_tray_checkbox = QCheckBox("Сворачивать в трей при закрытии окна")
        self.minimize_to_tray_checkbox.setChecked(settings.get("minimize_to_tray", True))

        self.hide_notification_preview_checkbox = QCheckBox("Скрывать текст сообщения в уведомлениях")
        self.hide_notification_preview_checkbox.setChecked(settings.get("hide_notification_preview", False))

        self.remember_login_checkbox = QCheckBox("Запоминать вход на этом ПК")
        self.remember_login_checkbox.setChecked(settings.get("remember_login", False))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Внешний вид"))
        layout.addWidget(QLabel("Тема"))
        layout.addWidget(self.theme_combo)
        layout.addSpacing(8)
        layout.addWidget(QLabel("Уведомления"))
        layout.addWidget(self.sound_checkbox)
        layout.addWidget(self.tray_notifications_checkbox)
        layout.addWidget(self.hide_notification_preview_checkbox)
        layout.addSpacing(8)
        layout.addWidget(QLabel("Окно"))
        layout.addWidget(self.minimize_to_tray_checkbox)
        layout.addSpacing(8)
        layout.addWidget(QLabel("Безопасность"))
        layout.addWidget(self.remember_login_checkbox)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_settings(self) -> dict:
        return {
            "sound_enabled": self.sound_checkbox.isChecked(),
            "tray_notifications_enabled": self.tray_notifications_checkbox.isChecked(),
            "minimize_to_tray": self.minimize_to_tray_checkbox.isChecked(),
            "hide_notification_preview": self.hide_notification_preview_checkbox.isChecked(),
            "remember_login": self.remember_login_checkbox.isChecked(),
            "theme": normalize_theme(self.theme_combo.currentData())
        }


class ProfileDialog(QDialog):
    """
    Окно профиля пользователя.
    """

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Профиль")
        self.resize(380, 360)

        self.display_name_input = QLineEdit()
        self.display_name_input.setPlaceholderText("Отображаемое имя")
        self.display_name_input.setText(user.get("display_name") or user.get("username", ""))

        self.department_input = QLineEdit()
        self.department_input.setPlaceholderText("Отдел")
        self.department_input.setText(user.get("department") or "")

        self.position_input = QLineEdit()
        self.position_input.setPlaceholderText("Должность")
        self.position_input.setText(user.get("position") or "")

        self.status_combo = QComboBox()
        self.status_combo.addItem("Доступен", "available")
        self.status_combo.addItem("Занят", "busy")
        self.status_combo.addItem("Не беспокоить", "do_not_disturb")
        self.status_combo.addItem("Отошёл", "away")

        current_status = user.get("user_status", "available")
        index = self.status_combo.findData(current_status)

        if index >= 0:
            self.status_combo.setCurrentIndex(index)

        self.old_password_input = QLineEdit()
        self.old_password_input.setPlaceholderText("Старый пароль")
        self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.new_password_input = QLineEdit()
        self.new_password_input.setPlaceholderText("Новый пароль")
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.repeat_password_input = QLineEdit()
        self.repeat_password_input.setPlaceholderText("Повторите новый пароль")
        self.repeat_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Профиль"))
        layout.addWidget(self.display_name_input)
        layout.addWidget(QLabel("Отдел"))
        layout.addWidget(self.department_input)
        layout.addWidget(QLabel("Должность"))
        layout.addWidget(self.position_input)
        layout.addWidget(QLabel("Статус"))
        layout.addWidget(self.status_combo)
        layout.addSpacing(10)
        layout.addWidget(QLabel("Смена пароля"))
        layout.addWidget(self.old_password_input)
        layout.addWidget(self.new_password_input)
        layout.addWidget(self.repeat_password_input)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_profile_data(self) -> dict:
        return {
            "display_name": self.display_name_input.text().strip(),
            "department": self.department_input.text().strip(),
            "position": self.position_input.text().strip(),
            "user_status": self.status_combo.currentData(),
            "old_password": self.old_password_input.text(),
            "new_password": self.new_password_input.text(),
            "repeat_password": self.repeat_password_input.text()
        }


class MiniProfileDialog(QDialog):
    """
    Мини-профиль собеседника.
    """

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Мини-профиль")
        self.resize(340, 240)

        display_name = user.get("display_name") or user.get("username", "Пользователь")
        role = user.get("role", "user")
        status = STATUS_LABELS.get(user.get("user_status", "available"), "доступен")
        department = user.get("department") or "не указан"
        position = user.get("position") or "не указана"
        last_login = user.get("last_login_at") or "нет данных"
        online = "online" if user.get("online") else "offline"

        info = QLabel(
            f"Имя: {display_name}\n"
            f"Роль: {role}\n"
            f"Статус: {status}\n"
            f"Сеть: {online}\n"
            f"Отдел: {department}\n"
            f"Должность: {position}\n"
            f"Последний вход: {last_login}"
        )
        info.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Мини-профиль"))
        layout.addWidget(info)
        layout.addWidget(buttons)
        self.setLayout(layout)




class MainWindow(QWidget):
    """
    Главное окно чата CatCorp.
    """

    def __init__(self, network: ClientNetwork):
        super().__init__()

        self.network = network
        self.current_user = self.network.user
        self.selected_user = None
        self.selected_chat_type = None
        self.reply_message = None
        self.tray_icon = None
        self.force_close = False
        self.setAcceptDrops(True)

        self.users = []
        self.recent_chats = []
        self.current_messages = []
        self.selected_file_paths = []
        self.total_unread = 0

        self.settings = load_settings()
        apply_app_theme(self.settings)

        self.signals = NetworkSignals()
        self.signals.new_message.connect(self.handle_new_message)
        self.signals.users_status.connect(self.update_users_data)
        self.signals.disconnected.connect(self.handle_disconnected)
        self.signals.typing.connect(self.handle_typing)
        self.signals.recent_chats.connect(self.handle_recent_chats_event)
        self.signals.edited_message.connect(self.handle_edited_message)
        self.signals.new_room_message.connect(self.handle_new_room_message)
        self.signals.room_typing.connect(self.handle_room_typing)
        self.signals.edited_room_message.connect(self.handle_edited_room_message)

        self.network.on_new_message = self.signals.new_message.emit
        self.network.on_users_status = self.signals.users_status.emit
        self.network.on_disconnected = self.signals.disconnected.emit
        self.network.on_typing = self.signals.typing.emit
        self.network.on_recent_chats = self.signals.recent_chats.emit
        self.network.on_edited_message = self.signals.edited_message.emit
        self.network.on_new_room_message = self.signals.new_room_message.emit
        self.network.on_room_typing = self.signals.room_typing.emit
        self.network.on_edited_room_message = self.signals.edited_room_message.emit

        self.typing_timer = QTimer(self)
        self.typing_timer.setInterval(1200)
        self.typing_timer.timeout.connect(self.stop_typing)
        self.is_typing_sent = False

        self.setWindowTitle("CatCorp — Чат")
        self.resize(940, 600)

        self._build_ui()
        self.setup_tray_icon()
        self.setup_shortcuts()
        self.load_initial_data()
        self.close_current_chat()

    def setup_shortcuts(self):
        """
        Горячие клавиши главного окна.
        Esc закрывает текущий открытый чат.
        """
        self.escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self.escape_shortcut.activated.connect(self.close_current_chat)

    def set_chat_open_state(self, is_open: bool):
        """
        Переключает правую часть окна между открытым чатом и пустым состоянием.
        """
        self.chat_title_label.setVisible(is_open)
        self.messages_list.setVisible(is_open)
        self.input_panel.setVisible(is_open)
        self.typing_label.setVisible(is_open)
        self.reply_panel.setVisible(is_open and self.reply_message is not None)
        self.empty_chat_label.setVisible(not is_open)

        if not is_open:
            self.chat_title_label.setText("")
            self.typing_label.setText("")
            self.message_input.clear()
            self.messages_list.clear()
            self.clear_selected_files()

    def close_current_chat(self):
        """
        Закрывает текущий чат по Esc без выхода из аккаунта.
        """
        if self.selected_chat_type == "room" and self.selected_user and self.is_typing_sent:
            room_id = self.selected_user.get("room_id") or self.selected_user.get("id")
            self.network.send_room_typing(room_id=room_id, is_typing=False)

        elif self.selected_user and self.is_typing_sent:
            self.network.send_typing(receiver_id=self.selected_user.get("id"), is_typing=False)

        self.is_typing_sent = False
        self.selected_user = None
        self.selected_chat_type = None
        self.current_messages = []

        self.reply_message = None
        self.reply_label.setText("")
        self.reply_panel.hide()

        self.chats_list.clearSelection()
        self.set_chat_open_state(False)

    def keyPressEvent(self, event):
        """
        Esc закрывает текущий чат даже если фокус находится внутри окна.
        """
        if event.key() == Qt.Key.Key_Escape:
            self.close_current_chat()
            return

        super().keyPressEvent(event)


    def _build_ui(self):
        self.user_info_label = QLabel()
        self.update_user_info_label()

        self.profile_button = QPushButton("Профиль")
        self.profile_button.clicked.connect(self.open_profile_dialog)

        self.settings_button = QPushButton("Настройки")
        self.settings_button.clicked.connect(self.open_settings_dialog)

        self.logout_button = QPushButton("Выйти")
        self.logout_button.clicked.connect(self.logout_from_account)

        self.chats_label = QLabel("Недавние чаты")

        self.new_chat_button = QPushButton("+ Новый чат")
        self.new_chat_button.clicked.connect(self.open_new_chat_dialog)

        self.new_group_button = QPushButton("+ Группа")
        self.new_group_button.clicked.connect(self.open_new_group_dialog)

        self.chats_list = QListWidget()
        self.chats_list.setWordWrap(True)
        self.chats_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.chats_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.chats_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.chats_list.verticalScrollBar().setSingleStep(12)
        self.chats_list.itemClicked.connect(self.handle_chat_selected)
        self.chats_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chats_list.customContextMenuRequested.connect(self.open_chat_context_menu)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.user_info_label)

        left_buttons_layout = QHBoxLayout()
        left_buttons_layout.addWidget(self.profile_button)
        left_buttons_layout.addWidget(self.settings_button)
        left_buttons_layout.addWidget(self.logout_button)
        left_layout.addLayout(left_buttons_layout)

        left_layout.addWidget(self.chats_label)
        chat_buttons_layout = QHBoxLayout()
        chat_buttons_layout.addWidget(self.new_chat_button)
        chat_buttons_layout.addWidget(self.new_group_button)
        left_layout.addLayout(chat_buttons_layout)
        left_layout.addWidget(self.chats_list)

        self.chat_title_label = QLabel("Выберите чат")
        self.chat_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.chat_title_label.mousePressEvent = self.handle_chat_title_clicked

        self.typing_label = QLabel("")
        self.typing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.empty_chat_label = QLabel("Выберите чат")
        self.empty_chat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.messages_list = QListWidget()
        self.messages_list.setAcceptDrops(True)
        self.messages_list.setWordWrap(True)
        self.messages_list.setSpacing(8)
        self.messages_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.messages_list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.messages_list.verticalScrollBar().setSingleStep(12)
        self.messages_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.messages_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.messages_list.setUniformItemSizes(False)
        self.messages_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.messages_list.customContextMenuRequested.connect(self.open_message_context_menu)
        self.messages_list.itemDoubleClicked.connect(self.handle_message_double_clicked)

        self.reply_panel = QWidget()
        reply_layout = QHBoxLayout()
        reply_layout.setContentsMargins(0, 0, 0, 0)

        self.reply_label = QLabel("")
        self.cancel_reply_button = QPushButton("Отмена")
        self.cancel_reply_button.clicked.connect(self.cancel_reply)

        reply_layout.addWidget(self.reply_label)
        reply_layout.addWidget(self.cancel_reply_button)
        self.reply_panel.setLayout(reply_layout)
        self.reply_panel.hide()

        self.attachment_panel = QWidget()
        self.attachment_panel.hide()

        self.attachment_label = QLabel("")
        self.attachment_label.setWordWrap(True)

        self.clear_attachment_button = QPushButton("Очистить")
        self.clear_attachment_button.setToolTip("Убрать выбранные файлы")
        self.clear_attachment_button.clicked.connect(self.clear_selected_files)

        attachment_layout = QHBoxLayout()
        attachment_layout.setContentsMargins(0, 0, 0, 0)
        attachment_layout.addWidget(self.attachment_label, 1)
        attachment_layout.addWidget(self.clear_attachment_button)
        self.attachment_panel.setLayout(attachment_layout)

        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Введите сообщение...")
        self.message_input.textChanged.connect(self.handle_text_changed)
        self.message_input.returnPressed.connect(self.send_message)

        self.attach_button = QPushButton("+")
        self.attach_button.setToolTip("Прикрепить файлы")
        self.attach_button.clicked.connect(self.select_files)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send_message)

        self.input_panel = QWidget()
        self.input_panel.setAcceptDrops(True)
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.addWidget(self.attach_button)
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.send_button)
        self.input_panel.setLayout(input_layout)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.chat_title_label)
        right_layout.addWidget(self.typing_label)
        right_layout.addWidget(self.empty_chat_label, 1)
        right_layout.addWidget(self.messages_list)
        right_layout.addWidget(self.reply_panel)
        right_layout.addWidget(self.attachment_panel)
        right_layout.addWidget(self.input_panel)

        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 1)
        main_layout.addLayout(right_layout, 3)

        self.setLayout(main_layout)

    def status_to_text(self, status: str) -> str:
        return STATUS_LABELS.get(status, "доступен")


    def setup_tray_icon(self):
        """
        Создаёт иконку в трее Windows и меню для неё.
        """
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = self.windowIcon()

        if icon.isNull():
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray_icon = QSystemTrayIcon(icon, self)
        self.tray_icon.setToolTip("CatCorp")

        tray_menu = QMenu(self)
        open_action = QAction("Открыть CatCorp", self)
        quit_action = QAction("Закрыть приложение", self)

        open_action.triggered.connect(self.show_from_tray)
        quit_action.triggered.connect(self.quit_from_tray)

        tray_menu.addAction(open_action)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.handle_tray_activated)
        self.tray_icon.show()

    def show_from_tray(self):
        """
        Показывает окно из трея.
        """
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self):
        """
        Полностью закрывает приложение из меню трея.
        """
        self.force_close = True
        self.close()

    def handle_tray_activated(self, reason):
        """
        Открывает окно по двойному клику по иконке в трее.
        """
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_from_tray()

    def show_tray_notification(self, title: str, message: str):
        """
        Показывает всплывающее уведомление в Windows tray.
        """
        if self.tray_icon is None:
            return

        if not self.settings.get("tray_notifications_enabled", True):
            return

        if self.settings.get("hide_notification_preview", False):
            message = "Новое сообщение"

        self.tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 5000)

    def update_user_info_label(self):
        if self.current_user:
            display_name = self.current_user.get("display_name") or self.current_user.get("username")
            username = self.current_user.get("username")
            role = self.current_user.get("role")
            user_status = self.status_to_text(self.current_user.get("user_status", "available"))
            self.user_info_label.setText(f"Вы вошли как: {display_name} ({role}, {user_status})\nЛогин: {username}")
        else:
            self.user_info_label.setText("Пользователь не определён")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self.settings, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings.update(dialog.get_settings())
            save_settings(self.settings)
            apply_app_theme(self.settings)

            if not self.settings.get("remember_login", False):
                clear_auth_token()

    def open_profile_dialog(self):
        if not self.current_user:
            return

        dialog = ProfileDialog(self.current_user, self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_profile_data()

        if not data["display_name"]:
            QMessageBox.warning(self, "Ошибка", "Введите отображаемое имя")
            return

        response = self.network.update_profile(
            display_name=data["display_name"],
            user_status=data["user_status"],
            department=data["department"],
            position=data["position"]
        )

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось обновить профиль"))
            return

        self.current_user = self.network.user
        self.update_user_info_label()

        if data["user_status"] == "do_not_disturb":
            self.settings["sound_enabled"] = False
            save_settings(self.settings)

        old_password = data["old_password"]
        new_password = data["new_password"]
        repeat_password = data["repeat_password"]

        if old_password or new_password or repeat_password:
            if not old_password or not new_password or not repeat_password:
                QMessageBox.warning(self, "Ошибка", "Для смены пароля заполните все поля пароля")
                return

            if new_password != repeat_password:
                QMessageBox.warning(self, "Ошибка", "Новые пароли не совпадают")
                return

            password_response = self.network.change_password(old_password, new_password)

            if password_response.get("status") != "ok":
                QMessageBox.warning(self, "Ошибка", password_response.get("message", "Не удалось изменить пароль"))
                return

        QMessageBox.information(self, "Профиль", "Профиль сохранён")

    def logout_from_account(self):
        answer = QMessageBox.question(
            self,
            "Выход",
            "Выйти из аккаунта? При следующем запуске нужно будет снова ввести логин и пароль."
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        token = load_auth_token()

        if token:
            self.network.logout_token(token)

        clear_auth_token()

        if self.network:
            self.network.disconnect()

        from client_gui.login_window import LoginWindow

        self.login_window = LoginWindow()
        self.login_window.show()
        self.close()

    def load_initial_data(self):
        self.load_users()
        self.load_recent_chats()

    def load_users(self):
        response = self.network.get_users()

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось загрузить список пользователей"))
            return

        data = response.get("data", {})
        self.users = data.get("users", [])

    def load_recent_chats(self):
        response = self.network.get_recent_chats()

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось загрузить недавние чаты"))
            return

        data = response.get("data", {})
        self.recent_chats = data.get("chats", [])
        self.total_unread = int(data.get("total_unread", 0))
        self.clear_open_room_unread_local()

        self.render_recent_chats()
        self.update_window_title()

    def update_users_data(self, users: list):
        self.users = users
        users_by_id = {user.get("id"): user for user in users}

        for chat in self.recent_chats:
            if chat.get("chat_type", "user") == "room":
                continue

            user = users_by_id.get(chat.get("id"))

            if user:
                chat["online"] = user.get("online", False)
                chat["role"] = user.get("role", chat.get("role", "user"))
                chat["display_name"] = user.get("display_name", chat.get("display_name"))
                chat["user_status"] = user.get("user_status", chat.get("user_status", "available"))
                chat["last_login_at"] = user.get("last_login_at", chat.get("last_login_at"))

        self.render_recent_chats()

    def handle_recent_chats_event(self, data: dict):
        if not isinstance(data, dict):
            return

        self.recent_chats = data.get("chats", [])
        self.total_unread = int(data.get("total_unread", 0))
        self.clear_open_room_unread_local()

        self.render_recent_chats()
        self.update_window_title()

    def clear_open_room_unread_local(self):
        """
        Если группа сейчас открыта, локально убирает у неё счётчик новых сообщений.
        Это защищает UI от гонки событий recent_chats, которые могут прийти раньше mark_room_read.
        """
        if self.selected_chat_type != "room" or not self.selected_user:
            return

        current_room_id = self.selected_user.get("room_id") or self.selected_user.get("id")

        for chat in self.recent_chats:
            if chat.get("chat_type") == "room":
                chat_room_id = chat.get("room_id") or chat.get("id")

                if int(chat_room_id) == int(current_room_id):
                    chat["unread_count"] = 0

    def render_recent_chats(self):
        self.clear_open_room_unread_local()
        self.chats_list.clear()

        for chat in self.recent_chats:
            chat_type = chat.get("chat_type", "user")
            display_name = chat.get("display_name") or chat.get("username", "unknown")
            last_message = chat.get("last_message") or ""
            unread_count = int(chat.get("unread_count", 0))

            if chat_type == "room":
                room_id = chat.get("room_id") or chat.get("id")
                item_text = f"{display_name} [группа]"

                if self.is_room_muted(room_id):
                    item_text += " [без уведомлений]"

                if unread_count > 0:
                    item_text += f" ({unread_count})"
            else:
                online = bool(chat.get("online"))
                status = "online" if online else "offline"
                pinned = bool(chat.get("pinned", False))

                if online:
                    profile_status = self.status_to_text(chat.get("user_status", "available"))
                    item_text = f"{'📌 ' if pinned else ''}{display_name} [{status}, {profile_status}]"
                else:
                    item_text = f"{'📌 ' if pinned else ''}{display_name} [{status}]"

                if self.is_user_muted(chat.get("id")):
                    item_text += " [без уведомлений]"

                if unread_count > 0:
                    item_text += f" ({unread_count})"

            if last_message:
                item_text += f"\n{short_text(last_message, 40)}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, chat)

            if unread_count > 0:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

            self.chats_list.addItem(item)

        if self.selected_user:
            selected_id = self.selected_user.get("id")
            selected_type = self.selected_chat_type or self.selected_user.get("chat_type", "user")

            for chat in self.recent_chats:
                chat_type = chat.get("chat_type", "user")

                if chat.get("id") == selected_id and chat_type == selected_type:
                    self.selected_user = chat
                    break

    def update_window_title(self):
        if self.total_unread > 0:
            self.setWindowTitle(f"CatCorp — Чат ({self.total_unread})")
        else:
            self.setWindowTitle("CatCorp — Чат")

    def open_new_chat_dialog(self):
        current_user_id = self.current_user.get("id") if self.current_user else None

        dialog = UserSelectDialog(
            users=self.users,
            current_user_id=current_user_id,
            parent=self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_user:
            self.open_chat(dialog.selected_user)

    def open_new_group_dialog(self):
        """
        Открывает окно создания группового чата.
        """
        current_user_id = self.current_user.get("id") if self.current_user else None
        dialog = GroupCreateDialog(self.users, current_user_id, self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        data = dialog.get_data()

        if not data["name"]:
            QMessageBox.warning(self, "Ошибка", "Введите название группы")
            return

        if not data["member_ids"]:
            QMessageBox.warning(self, "Ошибка", "Выберите хотя бы одного участника")
            return

        response = self.network.create_room(data["name"], data["member_ids"])

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось создать группу"))
            return

        self.load_recent_chats()

        room = response.get("data", {}).get("room")

        if room:
            room["chat_type"] = "room"
            room["display_name"] = room.get("name", data["name"])
            self.open_chat(room)

    def open_chat_context_menu(self, position: QPoint):
        item = self.chats_list.itemAt(position)

        if item is None:
            return

        chat = item.data(Qt.ItemDataRole.UserRole)

        if not chat:
            return

        menu = QMenu(self)

        if chat.get("chat_type", "user") == "room":
            room_id = self.get_room_id_from_chat(chat)
            muted = self.is_room_muted(room_id)

            members_action = QAction("Участники", self)
            add_members_action = QAction("Добавить участников", self)
            mute_action = QAction("Включить уведомления" if muted else "Отключить уведомления", self)
            leave_action = QAction("Выйти из группы", self)
            delete_action = QAction("Удалить группу", self)

            members_action.triggered.connect(lambda: self.show_room_members(chat))
            add_members_action.triggered.connect(lambda: self.add_members_to_room(chat))
            mute_action.triggered.connect(lambda: self.toggle_room_notifications(chat))
            leave_action.triggered.connect(lambda: self.leave_room(chat))
            delete_action.triggered.connect(lambda: self.delete_room(chat))

            menu.addAction(members_action)
            menu.addAction(add_members_action)
            menu.addAction(mute_action)
            menu.addSeparator()
            menu.addAction(leave_action)
            menu.addAction(delete_action)
            menu.exec(self.chats_list.mapToGlobal(position))
            return

        pinned = bool(chat.get("pinned", False))
        muted = self.is_user_muted(chat.get("id"))

        pin_action = QAction("Открепить чат" if pinned else "Закрепить чат", self)
        mute_action = QAction("Включить уведомления" if muted else "Отключить уведомления", self)
        hide_action = QAction("Удалить чат у себя", self)

        pin_action.triggered.connect(lambda: self.toggle_pin_chat(chat))
        mute_action.triggered.connect(lambda: self.toggle_user_notifications(chat))
        hide_action.triggered.connect(lambda: self.hide_chat_for_me(chat))

        menu.addAction(pin_action)
        menu.addAction(mute_action)
        menu.addAction(hide_action)

        menu.exec(self.chats_list.mapToGlobal(position))

    def get_room_id_from_chat(self, chat: dict) -> int:
        """
        Возвращает ID группы из объекта чата.
        """
        return chat.get("room_id") or chat.get("id")

    def clear_current_chat_if_room(self, room_id: int):
        """
        Очищает открытую область чата, если сейчас открыта эта группа.
        """
        if not self.selected_user:
            return

        if self.selected_chat_type != "room":
            return

        selected_room_id = self.selected_user.get("room_id") or self.selected_user.get("id")

        if selected_room_id != room_id:
            return

        self.selected_user = None
        self.selected_chat_type = None
        self.chat_title_label.setText("")
        self.typing_label.setText("")
        self.messages_list.clear()
        self.current_messages = []
        self.cancel_reply()

    def show_room_members(self, chat: dict):
        """
        Показывает список участников группы.
        """
        room_id = self.get_room_id_from_chat(chat)
        response = self.network.get_room_members(room_id)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось загрузить участников"))
            return

        members = response.get("data", {}).get("members", [])
        lines = []

        for member in members:
            display_name = member.get("display_name") or member.get("username", "unknown")
            username = member.get("username", "unknown")
            online = "online" if member.get("online") else "offline"
            role = member.get("role", "user")

            line = f"{display_name} [{online}, {role}]"

            if display_name != username:
                line += f" @{username}"

            lines.append(line)

        QMessageBox.information(
            self,
            "Участники группы",
            "\n".join(lines) if lines else "Участников нет"
        )

    def add_members_to_room(self, chat: dict):
        """
        Открывает окно добавления участников в группу.
        """
        room_id = self.get_room_id_from_chat(chat)
        response = self.network.get_room_members(room_id)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось загрузить участников"))
            return

        members = response.get("data", {}).get("members", [])
        existing_member_ids = {member.get("id") for member in members}
        current_user_id = self.current_user.get("id") if self.current_user else None
        self.load_users()

        dialog = GroupAddMembersDialog(
            users=self.users,
            existing_member_ids=existing_member_ids,
            current_user_id=current_user_id,
            parent=self
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        member_ids = dialog.get_member_ids()

        if not member_ids:
            QMessageBox.information(self, "Группа", "Новые участники не выбраны")
            return

        add_response = self.network.add_room_members(room_id, member_ids)

        if add_response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", add_response.get("message", "Не удалось добавить участников"))
            return

        QMessageBox.information(self, "Группа", "Участники добавлены")
        self.load_recent_chats()

    def leave_room(self, chat: dict):
        """
        Выходит из группы.
        """
        room_id = self.get_room_id_from_chat(chat)
        display_name = chat.get("display_name") or chat.get("name", "группы")

        answer = QMessageBox.question(
            self,
            "Выйти из группы",
            f"Выйти из группы '{display_name}'?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        response = self.network.leave_room(room_id)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось выйти из группы"))
            return

        self.clear_current_chat_if_room(room_id)
        self.load_recent_chats()

    def delete_room(self, chat: dict):
        """
        Удаляет группу. Сервер разрешит это только создателю или администратору.
        """
        room_id = self.get_room_id_from_chat(chat)
        display_name = chat.get("display_name") or chat.get("name", "группы")

        answer = QMessageBox.question(
            self,
            "Удалить группу",
            f"Удалить группу '{display_name}'?\nЭто удалит группу у всех участников."
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        response = self.network.delete_room(room_id)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось удалить группу"))
            return

        self.clear_current_chat_if_room(room_id)
        self.load_recent_chats()

    def toggle_pin_chat(self, chat: dict):
        user_id = chat.get("id")
        new_state = not bool(chat.get("pinned", False))

        response = self.network.pin_chat(user_id, new_state)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось изменить закрепление чата"))
            return

        data = response.get("data", {})
        self.recent_chats = data.get("chats", self.recent_chats)
        self.total_unread = int(data.get("total_unread", self.total_unread))

        self.render_recent_chats()
        self.update_window_title()

    def hide_chat_for_me(self, chat: dict):
        user_id = chat.get("id")
        display_name = chat.get("display_name") or chat.get("username", "пользователем")

        answer = QMessageBox.question(
            self,
            "Удалить чат",
            f"Скрыть чат с {display_name}?\nСообщения не будут удалены. При новом сообщении чат появится снова."
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        response = self.network.hide_chat(user_id)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось скрыть чат"))
            return

        data = response.get("data", {})
        self.recent_chats = data.get("chats", self.recent_chats)
        self.total_unread = int(data.get("total_unread", self.total_unread))

        if self.selected_user and self.selected_user.get("id") == user_id:
            self.selected_user = None
            self.chat_title_label.setText("")
            self.typing_label.setText("")
            self.messages_list.clear()
            self.current_messages = []
            self.cancel_reply()

        self.render_recent_chats()
        self.update_window_title()

    def handle_chat_selected(self, item: QListWidgetItem):
        user = item.data(Qt.ItemDataRole.UserRole)
        self.open_chat(user)

    def open_chat(self, user: dict):
        self.set_chat_open_state(True)
        self.selected_user = user
        self.selected_chat_type = user.get("chat_type", "user")

        if self.selected_chat_type == "room":
            display_name = user.get("display_name") or user.get("name", "Группа")
            self.chat_title_label.setText(f"Группа: {display_name}")
            self.typing_label.setText("групповой чат")
            self.is_typing_sent = False
            self.typing_timer.stop()
            self.cancel_reply()
            room_id = user.get("room_id") or user.get("id")
            self.load_room_history(room_id)
            self.mark_current_room_read(room_id)
            return

        display_name = user.get("display_name") or user.get("username", "Чат")
        is_online = user.get("online", False)
        last_login = user.get("last_login_at")

        if is_online:
            status_text = "в сети"
        elif last_login:
            status_text = f"не в сети, был: {last_login}"
        else:
            status_text = "не в сети"

        self.chat_title_label.setText(f"Чат с {display_name}")
        self.typing_label.setText(status_text)

        self.is_typing_sent = False
        self.typing_timer.stop()
        self.cancel_reply()

        self.load_history(user.get("id"))
        self.mark_current_chat_read(user.get("id"))

    def load_history(self, user_id: int):
        response = self.network.get_history(user_id)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось загрузить историю"))
            return

        data = response.get("data", {})
        messages = data.get("messages", [])

        self.render_messages(messages)

    def mark_current_room_read(self, room_id: int):
        """
        Помечает открытую группу как прочитанную.
        """
        response = self.network.mark_room_read(room_id)

        if response.get("status") != "ok":
            return

        data = response.get("data", {})
        self.recent_chats = data.get("chats", self.recent_chats)
        self.total_unread = int(data.get("total_unread", self.total_unread))

        self.render_recent_chats()
        self.update_window_title()

    def load_room_history(self, room_id: int):
        response = self.network.get_room_history(room_id)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось загрузить историю группы"))
            return

        data = response.get("data", {})
        messages = data.get("messages", [])
        self.render_messages(messages)

    def mark_current_chat_read(self, user_id: int):
        response = self.network.mark_chat_read(user_id)

        if response.get("status") != "ok":
            return

        data = response.get("data", {})
        self.recent_chats = data.get("chats", self.recent_chats)
        self.total_unread = int(data.get("total_unread", self.total_unread))

        self.render_recent_chats()
        self.update_window_title()

    def get_full_user_info(self, user_id: int) -> dict:
        """
        Берёт самые свежие данные пользователя из списков users/recent_chats.
        """
        for user in self.users:
            if int(user.get("id", -1)) == int(user_id):
                return user

        for chat in self.recent_chats:
            if chat.get("chat_type", "user") == "user" and int(chat.get("id", -1)) == int(user_id):
                return chat

        if self.selected_user and int(self.selected_user.get("id", -1)) == int(user_id):
            return self.selected_user

        return {}

    def handle_chat_title_clicked(self, event):
        """
        Открывает мини-профиль собеседника по клику на имя в открытом личном чате.
        """
        self.open_selected_user_profile()

    def open_selected_user_profile(self):
        if self.selected_chat_type != "user" or not self.selected_user:
            return

        user_id = self.selected_user.get("id")
        user = self.get_full_user_info(user_id)

        if not user:
            user = self.selected_user

        dialog = MiniProfileDialog(user, self)
        dialog.exec()

    def can_edit_message(self, message: dict) -> bool:
        """
        Сообщение можно редактировать только первые 48 часов.
        """
        sent_at = str(message.get("sent_at") or "").strip()

        if not sent_at:
            return False

        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                sent_dt = datetime.strptime(sent_at[:19], fmt)
                return datetime.now() - sent_dt <= timedelta(hours=48)
            except ValueError:
                continue

        return False

    def render_messages(self, messages: list):
        self.messages_list.clear()
        self.current_messages = []

        for message in messages:
            self.append_message(message)

        self.messages_list.scrollToBottom()

    def is_own_message(self, message: dict) -> bool:
        """
        Проверяет, является ли сообщение исходящим.
        """
        if not self.current_user:
            return False

        try:
            return int(message.get("sender_id")) == int(self.current_user.get("id"))
        except (TypeError, ValueError):
            return False

    def format_message_time(self, sent_at: str) -> str:
        """
        Возвращает короткое время сообщения для пузырька.
        """
        sent_at = str(sent_at or "").strip()

        if len(sent_at) >= 16 and sent_at[10] in (" ", "T"):
            return sent_at[11:16]

        return sent_at

    def message_row_width(self) -> int:
        """
        Возвращает рабочую ширину строки сообщения с небольшими боковыми отступами.
        """
        if not hasattr(self, "messages_list"):
            return 620

        viewport_width = self.messages_list.viewport().width()

        if viewport_width <= 0:
            return 620

        return max(260, viewport_width - 28)

    def message_bubble_max_width(self) -> int:
        """
        Ограничивает ширину пузырька, чтобы сообщения не растягивались на весь чат.
        """
        row_width = self.message_row_width()
        return max(240, min(620, int(row_width * 0.76)))

    def create_message_widget(self, message: dict) -> QWidget:
        """
        Создаёт визуальный пузырёк сообщения.
        """
        is_own = self.is_own_message(message)
        message_type = message.get("message_type", "text")

        row = QWidget()
        row.setObjectName("MessageRow")

        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(10, 4, 18, 4)
        row_layout.setSpacing(0)

        if is_own:
            row_layout.addStretch(1)

        bubble = QFrame()
        bubble.setObjectName(
            ("FileBubbleOwn" if is_own else "FileBubbleOther")
            if message_type == "file"
            else ("MessageBubbleOwn" if is_own else "MessageBubbleOther")
        )
        bubble_max_width = self.message_bubble_max_width()
        bubble.setMaximumWidth(bubble_max_width)

        bubble_layout = QVBoxLayout()
        bubble_layout.setContentsMargins(10, 8, 10, 8)
        bubble_layout.setSpacing(5)

        sender_name = "Вы" if is_own else str(message.get("sender_username", "unknown"))
        sender_label = QLabel(sender_name)
        sender_label.setObjectName("MessageSender")
        sender_label.setWordWrap(False)
        sender_label.setMaximumWidth(max(160, bubble_max_width - 26))
        bubble_layout.addWidget(sender_label)

        reply_content = message.get("reply_content")
        reply_sender = message.get("reply_sender_username")

        if reply_content:
            reply_frame = QFrame()
            reply_frame.setObjectName("ReplyPreview")
            reply_layout = QVBoxLayout()
            reply_layout.setContentsMargins(8, 5, 8, 5)
            reply_layout.setSpacing(2)

            reply_text = QLabel(f"Ответ на {reply_sender}: {short_text(reply_content, 90)}")
            reply_text.setObjectName("MessageMeta")
            reply_text.setWordWrap(True)
            reply_text.setMaximumWidth(max(150, bubble_max_width - 44))
            reply_layout.addWidget(reply_text)

            reply_frame.setLayout(reply_layout)
            bubble_layout.addWidget(reply_frame)

        content = str(message.get("content", ""))

        if message_type == "file":
            file_name = str(message.get("file_original_name") or content or "Файл")
            file_size = format_file_size(message.get("file_size_bytes"))

            file_title = QLabel(f"📎 {file_name}")
            file_title.setObjectName("FileTitle")
            file_title.setWordWrap(True)
            file_title.setMaximumWidth(max(160, bubble_max_width - 26))
            bubble_layout.addWidget(file_title)

            file_hint = QLabel(f"{file_size} · двойной клик или ПКМ → Скачать")
            file_hint.setObjectName("FileHint")
            file_hint.setWordWrap(True)
            file_hint.setMaximumWidth(max(160, bubble_max_width - 26))
            bubble_layout.addWidget(file_hint)
        else:
            content_label = QLabel(content)
            content_label.setObjectName("MessageText")
            content_label.setWordWrap(True)
            content_label.setMaximumWidth(max(160, bubble_max_width - 26))
            content_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            bubble_layout.addWidget(content_label)

        sent_at = self.format_message_time(message.get("sent_at", ""))
        edited_at = message.get("edited_at")
        meta_text = sent_at

        if edited_at:
            meta_text += " · изменено"

        meta_label = QLabel(meta_text)
        meta_label.setObjectName("MessageMeta")
        meta_label.setMaximumWidth(max(160, bubble_max_width - 26))
        meta_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        bubble_layout.addWidget(meta_label)

        bubble.setLayout(bubble_layout)
        row_layout.addWidget(bubble)

        if not is_own:
            row_layout.addStretch(1)

        row.setLayout(row_layout)
        return row

    def update_message_item_size(self, item: QListWidgetItem, widget: QWidget):
        """
        Принудительно пересчитывает высоту кастомного элемента сообщения.

        Без этого QLabel с переносом строк иногда считает высоту слишком рано,
        и нижняя часть пузырька или карточки файла обрезается.
        """
        if item is None or widget is None or not hasattr(self, "messages_list"):
            return

        row_width = self.message_row_width()
        widget.setMinimumWidth(row_width)
        widget.setMaximumWidth(row_width)

        layout = widget.layout()

        if layout is not None:
            layout.invalidate()
            layout.activate()

        widget.updateGeometry()
        widget.adjustSize()

        height = max(widget.sizeHint().height(), widget.minimumSizeHint().height()) + 24
        item.setSizeHint(QSize(row_width, height))

    def refresh_message_widget_sizes(self):
        """
        Пересчитывает ширину пузырьков после изменения размера окна.
        """
        if not hasattr(self, "messages_list"):
            return

        max_width = self.message_bubble_max_width()

        for index in range(self.messages_list.count()):
            item = self.messages_list.item(index)
            widget = self.messages_list.itemWidget(item)

            if widget is None:
                continue

            for frame in widget.findChildren(QFrame):
                if frame.objectName() in {
                    "MessageBubbleOwn",
                    "MessageBubbleOther",
                    "FileBubbleOwn",
                    "FileBubbleOther"
                }:
                    frame.setMaximumWidth(max_width)

            for label in widget.findChildren(QLabel):
                if label.objectName() in {
                    "MessageSender",
                    "MessageText",
                    "MessageMeta",
                    "FileTitle",
                    "FileHint"
                }:
                    label.setMaximumWidth(max(160, max_width - 26))

            self.update_message_item_size(item, widget)

    def format_message_item(self, message: dict) -> str:
        """
        Текстовый fallback для сообщения.
        """
        sender_name = str(message.get("sender_username", "unknown"))
        content = str(message.get("content", ""))
        sent_at = str(message.get("sent_at", ""))
        edited_at = message.get("edited_at")
        message_type = message.get("message_type", "text")

        title = f"{sender_name} [{sent_at}]"

        if edited_at:
            title += " (изменено)"

        if message_type == "file":
            file_name = message.get("file_original_name") or content or "Файл"
            file_size = format_file_size(message.get("file_size_bytes"))
            return f"{title}\n📎 {file_name}\n{file_size} — двойной клик, чтобы скачать"

        return f"{title}\n{content}"

    def append_message(self, message: dict):
        self.current_messages.append(message)

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.UserRole, message)

        widget = self.create_message_widget(message)

        self.messages_list.addItem(item)
        self.messages_list.setItemWidget(item, widget)
        self.update_message_item_size(item, widget)

        QTimer.singleShot(
            0,
            lambda current_item=item, current_widget=widget: self.update_message_item_size(
                current_item,
                current_widget
            )
        )
        QTimer.singleShot(
            30,
            lambda current_item=item, current_widget=widget: self.update_message_item_size(
                current_item,
                current_widget
            )
        )

        self.messages_list.scrollToBottom()

    def open_message_context_menu(self, position: QPoint):
        item = self.messages_list.itemAt(position)

        if item is None:
            return

        message = item.data(Qt.ItemDataRole.UserRole)

        if not message:
            return

        menu = QMenu(self)

        if message.get("message_type") == "file":
            download_action = QAction("Скачать файл", self)
            download_action.triggered.connect(lambda: self.download_file_message(message))
            menu.addAction(download_action)
            menu.addSeparator()

        reply_action = QAction("Ответить", self)
        reply_action.triggered.connect(lambda: self.start_reply(message))
        menu.addAction(reply_action)

        current_user_id = self.current_user.get("id") if self.current_user else None

        if (
            message.get("message_type") != "file"
            and message.get("sender_id") == current_user_id
            and self.can_edit_message(message)
        ):
            edit_action = QAction("Редактировать", self)
            edit_action.triggered.connect(lambda: self.edit_own_message(message))
            menu.addAction(edit_action)

        menu.exec(self.messages_list.mapToGlobal(position))

    def start_reply(self, message: dict):
        self.reply_message = message
        sender = message.get("sender_username", "unknown")
        if message.get("message_type") == "file":
            content = "📎 " + str(message.get("file_original_name") or message.get("content", "Файл"))
        else:
            content = short_text(message.get("content", ""), 90)

        self.reply_label.setText(f"Ответ на {sender}: {content}")
        self.reply_panel.show()
        self.message_input.setFocus()

    def cancel_reply(self):
        self.reply_message = None
        self.reply_label.setText("")
        self.reply_panel.hide()

    def edit_own_message(self, message: dict):
        old_content = str(message.get("content", ""))

        new_content, ok = QInputDialog.getMultiLineText(
            self,
            "Редактировать сообщение",
            "Новый текст:",
            old_content
        )

        if not ok:
            return

        new_content = new_content.strip()

        if not new_content:
            return

        if self.selected_chat_type == "room":
            response = self.network.edit_room_message(message.get("id"), new_content)
        else:
            response = self.network.edit_message(message.get("id"), new_content)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка", response.get("message", "Не удалось отредактировать сообщение"))
            return

        if self.selected_user:
            if self.selected_chat_type == "room":
                room_id = self.selected_user.get("room_id") or self.selected_user.get("id")
                self.load_room_history(room_id)
                self.mark_current_room_read(room_id)
            else:
                self.load_history(self.selected_user.get("id"))

    def handle_text_changed(self):
        if not self.selected_user:
            return

        if self.selected_chat_type == "room":
            text = self.message_input.text()
            room_id = self.selected_user.get("room_id") or self.selected_user.get("id")

            if text and not self.is_typing_sent:
                self.network.send_room_typing(room_id=room_id, is_typing=True)
                self.is_typing_sent = True

            if text:
                self.typing_timer.start()
            else:
                self.stop_typing()

            return

        text = self.message_input.text()

        if text and not self.is_typing_sent:
            self.network.send_typing(receiver_id=self.selected_user.get("id"), is_typing=True)
            self.is_typing_sent = True

        if text:
            self.typing_timer.start()
        else:
            self.stop_typing()

    def stop_typing(self):
        self.typing_timer.stop()

        if not self.selected_user:
            self.is_typing_sent = False
            return

        if self.is_typing_sent and self.selected_chat_type == "room":
            room_id = self.selected_user.get("room_id") or self.selected_user.get("id")
            self.network.send_room_typing(room_id=room_id, is_typing=False)

        elif self.is_typing_sent:
            self.network.send_typing(receiver_id=self.selected_user.get("id"), is_typing=False)

        self.is_typing_sent = False

    def handle_typing(self, typing_data: dict):
        if not typing_data:
            return

        sender_id = typing_data.get("sender_id")
        sender_username = typing_data.get("sender_username", "Пользователь")
        is_typing = typing_data.get("is_typing", False)

        if not self.selected_user:
            return

        if self.selected_user.get("id") != sender_id:
            return

        if is_typing:
            self.typing_label.setText(f"{sender_username} печатает...")
        else:
            is_online = self.selected_user.get("online", False)
            last_login = self.selected_user.get("last_login_at")

            if is_online:
                self.typing_label.setText("в сети")
            elif last_login:
                self.typing_label.setText(f"не в сети, был: {last_login}")
            else:
                self.typing_label.setText("не в сети")

    def play_new_message_sound(self):
        if not self.settings.get("sound_enabled", True):
            return

        try:
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except RuntimeError:
            pass

    def get_muted_room_ids(self) -> set[int]:
        """
        Возвращает локальный список групп с отключёнными уведомлениями.
        Хранится в settings.json рядом с exe.
        """
        raw_ids = self.settings.get("muted_room_ids", [])
        result = set()

        if not isinstance(raw_ids, list):
            return result

        for room_id in raw_ids:
            try:
                result.add(int(room_id))
            except (TypeError, ValueError):
                pass

        return result

    def is_room_muted(self, room_id) -> bool:
        """
        Проверяет, отключены ли уведомления для группы.
        """
        try:
            room_id = int(room_id)
        except (TypeError, ValueError):
            return False

        return room_id in self.get_muted_room_ids()

    def set_room_muted(self, room_id, muted: bool):
        """
        Включает или отключает уведомления для конкретной группы.
        """
        try:
            room_id = int(room_id)
        except (TypeError, ValueError):
            return

        muted_ids = self.get_muted_room_ids()

        if muted:
            muted_ids.add(room_id)
        else:
            muted_ids.discard(room_id)

        self.settings["muted_room_ids"] = sorted(muted_ids)
        save_settings(self.settings)
        self.render_recent_chats()

    def toggle_room_notifications(self, chat: dict):
        """
        Переключает уведомления группы из контекстного меню.
        """
        room_id = self.get_room_id_from_chat(chat)
        currently_muted = self.is_room_muted(room_id)
        self.set_room_muted(room_id, not currently_muted)

    def get_muted_user_ids(self) -> set[int]:
        """
        Возвращает локальный список личных чатов с отключёнными уведомлениями.
        Хранится в settings.json рядом с exe.
        """
        raw_ids = self.settings.get("muted_user_ids", [])
        result = set()

        if not isinstance(raw_ids, list):
            return result

        for user_id in raw_ids:
            try:
                result.add(int(user_id))
            except (TypeError, ValueError):
                pass

        return result

    def is_user_muted(self, user_id) -> bool:
        """
        Проверяет, отключены ли уведомления для личного чата.
        """
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return False

        return user_id in self.get_muted_user_ids()

    def set_user_muted(self, user_id, muted: bool):
        """
        Включает или отключает уведомления для конкретного личного чата.
        """
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return

        muted_ids = self.get_muted_user_ids()

        if muted:
            muted_ids.add(user_id)
        else:
            muted_ids.discard(user_id)

        self.settings["muted_user_ids"] = sorted(muted_ids)
        save_settings(self.settings)
        self.render_recent_chats()

    def toggle_user_notifications(self, chat: dict):
        """
        Переключает уведомления личного чата из контекстного меню.
        """
        user_id = chat.get("id")
        currently_muted = self.is_user_muted(user_id)
        self.set_user_muted(user_id, not currently_muted)

    def select_files(self):
        """
        Выбирает один или несколько файлов для отправки через Explorer.
        """
        if not self.selected_user:
            QMessageBox.information(self, "Нет чата", "Сначала выберите личный чат или группу")
            return

        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Выбор файлов",
            str(Path.home() / "Downloads"),
            "Все файлы (*.*)"
        )

        self.add_files_to_selection(file_paths)

    def add_files_to_selection(self, file_paths: list[str]):
        """
        Добавляет файлы в очередь отправки.

        Используется и кнопкой '+', и drag-and-drop.
        """
        if not file_paths:
            return

        if not self.selected_user:
            QMessageBox.information(self, "Нет чата", "Сначала выберите личный чат или группу")
            return

        accepted = []
        skipped = []

        existing_paths = set(self.selected_file_paths)

        for file_path in file_paths:
            path = Path(file_path)

            if not path.exists() or not path.is_file():
                skipped.append(path.name or str(file_path))
                continue

            try:
                size = path.stat().st_size
            except OSError:
                skipped.append(path.name)
                continue

            if size <= 0 or size > MAX_FILE_SIZE:
                skipped.append(path.name)
                continue

            normalized_path = str(path)

            if normalized_path not in existing_paths:
                accepted.append(normalized_path)
                existing_paths.add(normalized_path)

        if accepted:
            self.selected_file_paths.extend(accepted)
            self.update_attachment_label()

        if skipped:
            QMessageBox.warning(
                self,
                "Некоторые файлы не добавлены",
                "Файл должен быть не пустым и не больше 25 МБ:\\n" + "\\n".join(skipped[:10])
            )

    def extract_local_file_paths_from_drop(self, event) -> list[str]:
        """
        Достаёт локальные файлы из drag-and-drop события.
        Папки не добавляются.
        """
        mime_data = event.mimeData()

        if not mime_data.hasUrls():
            return []

        file_paths = []

        for url in mime_data.urls():
            if not url.isLocalFile():
                continue

            local_path = url.toLocalFile()

            if local_path:
                file_paths.append(local_path)

        return file_paths

    def dragEnterEvent(self, event):
        """
        Разрешает перетаскивание файлов в окно чата.
        """
        if not self.selected_user:
            event.ignore()
            return

        if self.extract_local_file_paths_from_drop(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        """
        Поддерживает drag-and-drop во время движения мыши над окном.
        """
        if not self.selected_user:
            event.ignore()
            return

        if self.extract_local_file_paths_from_drop(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """
        Добавляет перетащенные файлы в очередь отправки.
        После этого пользователь нажимает 'Отправить'.
        """
        file_paths = self.extract_local_file_paths_from_drop(event)

        if not file_paths:
            event.ignore()
            return

        self.add_files_to_selection(file_paths)
        event.acceptProposedAction()

    def update_attachment_label(self):
        """
        Показывает список выбранных файлов перед отправкой.
        """
        if not hasattr(self, "attachment_panel"):
            return

        if not self.selected_file_paths:
            self.attachment_panel.hide()
            self.attachment_label.setText("")
            return

        names = [Path(path).name for path in self.selected_file_paths]
        preview = ", ".join(names[:3])

        if len(names) > 3:
            preview += f" и ещё {len(names) - 3}"

        self.attachment_label.setText(f"Прикреплено: {preview} — нажмите «Отправить»")
        self.attachment_panel.show()

    def clear_selected_files(self):
        """
        Очищает список выбранных файлов.
        """
        self.selected_file_paths = []

        if hasattr(self, "attachment_panel"):
            self.attachment_panel.hide()
            self.attachment_label.setText("")

    def downloads_dir(self) -> Path:
        """
        Возвращает папку Downloads/CatCorp.
        """
        directory = Path.home() / "Downloads" / "CatCorp"
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def handle_message_double_clicked(self, item: QListWidgetItem):
        """
        Двойной клик по file-сообщению скачивает файл.
        """
        if item is None:
            return

        message = item.data(Qt.ItemDataRole.UserRole)

        if not message or message.get("message_type") != "file":
            return

        self.download_file_message(message)

    def download_file_message(self, message: dict):
        """
        Скачивает файл в Downloads/CatCorp.
        """
        file_id = message.get("file_id")

        if not file_id:
            QMessageBox.warning(self, "Файл", "ID файла отсутствует")
            return

        response = self.network.download_file(file_id)

        if response.get("status") != "ok":
            QMessageBox.warning(self, "Ошибка скачивания", response.get("message", "Не удалось скачать файл"))
            return

        data = response.get("data", {}) or {}
        original_name = data.get("original_name") or message.get("file_original_name") or message.get("content") or "file"
        data_b64 = data.get("data_b64", "")

        try:
            file_bytes = base64.b64decode(str(data_b64).encode("ascii"), validate=True)
        except (ValueError, UnicodeEncodeError):
            QMessageBox.warning(self, "Ошибка скачивания", "Файл повреждён при передаче")
            return

        save_path = unique_download_path(self.downloads_dir(), original_name)

        try:
            save_path.write_bytes(file_bytes)
        except OSError:
            QMessageBox.warning(self, "Ошибка скачивания", "Не удалось сохранить файл")
            return

        QMessageBox.information(self, "Файл скачан", f"Файл сохранён:\\n{save_path}")

    def send_message(self):
        if not self.selected_user:
            QMessageBox.information(self, "Нет получателя", "Сначала выберите чат или нажмите '+ Новый чат'")
            return

        content = self.message_input.text().strip()
        selected_files = list(self.selected_file_paths)

        if not content and not selected_files:
            return

        self.send_button.setEnabled(False)
        self.message_input.setEnabled(False)
        self.attach_button.setEnabled(False)

        if hasattr(self, "clear_attachment_button"):
            self.clear_attachment_button.setEnabled(False)

        try:
            if content:
                if self.selected_chat_type == "room":
                    room_id = self.selected_user.get("room_id") or self.selected_user.get("id")
                    reply_to_message_id = None

                    if self.reply_message:
                        reply_to_message_id = self.reply_message.get("id")

                    response = self.network.send_room_message(room_id, content, reply_to_message_id)
                else:
                    receiver_id = self.selected_user.get("id")
                    reply_to_message_id = None

                    if self.reply_message:
                        reply_to_message_id = self.reply_message.get("id")

                    response = self.network.send_message(receiver_id, content, reply_to_message_id)

                if response.get("status") != "ok":
                    QMessageBox.warning(self, "Ошибка отправки", response.get("message", "Не удалось отправить сообщение"))
                    return

                data = response.get("data", {})
                message = data.get("message")

                if message:
                    self.append_message(message)

            for file_path in selected_files:
                if self.selected_chat_type == "room":
                    target_id = self.selected_user.get("room_id") or self.selected_user.get("id")
                    response = self.network.upload_file(file_path, "room", target_id)
                else:
                    target_id = self.selected_user.get("id")
                    response = self.network.upload_file(file_path, "user", target_id)

                if response.get("status") != "ok":
                    QMessageBox.warning(
                        self,
                        "Ошибка отправки файла",
                        f"{Path(file_path).name}: {response.get('message', 'Не удалось отправить файл')}"
                    )
                    continue

                data = response.get("data", {})
                message = data.get("message")

                if message:
                    self.append_message(message)

            self.message_input.clear()
            self.clear_selected_files()
            self.cancel_reply()
            self.stop_typing()
            self.load_recent_chats()

        finally:
            self.send_button.setEnabled(True)
            self.message_input.setEnabled(True)
            self.attach_button.setEnabled(True)

            if hasattr(self, "clear_attachment_button"):
                self.clear_attachment_button.setEnabled(True)

            self.message_input.setFocus()

    def handle_new_message(self, message: dict):
        if not message:
            return

        sender_id = message.get("sender_id")
        muted = self.is_user_muted(sender_id)

        if self.selected_user and self.selected_chat_type == "user" and self.selected_user.get("id") == sender_id:
            self.append_message(message)
            self.mark_current_chat_read(sender_id)
        else:
            if not muted:
                sender_name = message.get("sender_username", "Новое сообщение")
                preview = "📎 " + str(message.get("file_original_name") or message.get("content", "Файл")) if message.get("message_type") == "file" else short_text(message.get("content", ""), 120)
                self.play_new_message_sound()
                self.show_tray_notification(sender_name, preview)

            self.load_recent_chats()

    def handle_room_typing(self, typing_data: dict):
        """
        Показывает, кто печатает в открытой группе.
        """
        if not typing_data:
            return

        if self.selected_chat_type != "room" or not self.selected_user:
            return

        room_id = typing_data.get("room_id")
        current_room_id = self.selected_user.get("room_id") or self.selected_user.get("id")

        if room_id != current_room_id:
            return

        sender_username = typing_data.get("sender_username", "Пользователь")
        is_typing = typing_data.get("is_typing", False)

        if is_typing:
            self.typing_label.setText(f"{sender_username} печатает...")
        else:
            self.typing_label.setText("Групповой чат")

    def handle_edited_room_message(self, message: dict):
        """
        Обновляет открытый групповой чат после редактирования сообщения.
        """
        if not message:
            return

        room_id = message.get("room_id")

        if self.selected_chat_type == "room" and self.selected_user:
            current_room_id = self.selected_user.get("room_id") or self.selected_user.get("id")

            if int(current_room_id) == int(room_id):
                self.load_room_history(room_id)
                self.mark_current_room_read(room_id)
                return

        self.load_recent_chats()

    def handle_new_room_message(self, message: dict):
        if not message:
            return

        room_id = message.get("room_id")

        if self.selected_user and self.selected_chat_type == "room":
            selected_room_id = self.selected_user.get("room_id") or self.selected_user.get("id")

            if selected_room_id == room_id:
                self.append_message(message)
                self.load_recent_chats()
                return

        if not self.is_room_muted(room_id):
            sender_name = message.get("sender_username", "Группа")
            preview = "📎 " + str(message.get("file_original_name") or message.get("content", "Файл")) if message.get("message_type") == "file" else short_text(message.get("content", ""), 120)
            self.play_new_message_sound()
            self.show_tray_notification(f"Группа: {sender_name}", preview)

        self.load_recent_chats()

    def handle_edited_message(self, message: dict):
        if not message:
            return

        if not self.selected_user:
            return

        sender_id = message.get("sender_id")
        receiver_id = message.get("receiver_id")
        selected_id = self.selected_user.get("id")
        current_id = self.current_user.get("id") if self.current_user else None

        if selected_id in (sender_id, receiver_id) and current_id in (sender_id, receiver_id):
            self.load_history(selected_id)

        self.load_recent_chats()


    def resizeEvent(self, event):
        """
        При изменении размера окна просим список сообщений пересчитать перенос строк.
        """
        super().resizeEvent(event)

        if hasattr(self, "messages_list"):
            self.refresh_message_widget_sizes()
            self.messages_list.doItemsLayout()

    def handle_disconnected(self):
        QMessageBox.warning(self, "Соединение потеряно", "Соединение с сервером закрыто")

    def closeEvent(self, event):
        if (
            self.tray_icon is not None
            and not self.force_close
            and self.settings.get("minimize_to_tray", True)
        ):
            event.ignore()
            self.hide()
            self.show_tray_notification("CatCorp", "Приложение продолжает работать в трее")
            return

        self.stop_typing()

        if self.network:
            self.network.disconnect()

        event.accept()
