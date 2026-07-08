# client_network.py
# Клиентский сетевой модуль Intercom: подключение к серверу и обмен JSON-сообщениями

import base64
import socket
import threading
import os
import sys
import json

from common.protocol import send_json, recv_json


DEFAULT_SERVER_CONFIG = {
    "host": "127.0.0.1",
    "port": 5000
}

MAX_FILE_SIZE = 25 * 1024 * 1024


def resource_path(relative_path: str) -> str:
    """
    Возвращает путь к файлу с учётом PyInstaller.

    Если приложение запущено как .py — берём папку проекта.
    Если приложение собрано в .exe — берём временную папку PyInstaller.

    ВАЖНО:
    config.ini по ТЗ лежит рядом с .exe, поэтому для него ниже используется
    отдельная функция external_config_path().
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)


def app_dir_path() -> str:
    """
    Возвращает папку client.py или client.exe.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)

    return os.path.dirname(__file__)




def app_data_path(filename: str) -> str:
    """
    Возвращает путь к локальному файлу рядом с client.py или client.exe.
    Используется для auth_token.json, server_config.json и других клиентских файлов.
    Токен не вшивается в exe: это небезопасно, потому что exe можно скопировать.
    """
    return os.path.join(app_dir_path(), filename)


def auth_token_path() -> str:
    """
    Возвращает путь к файлу сохранённого токена входа.
    """
    return app_data_path("auth_token.json")


def save_auth_token(token: str):
    """
    Сохраняет токен автоматического входа локально.
    Пароль в этот файл не записывается.
    """
    try:
        with open(auth_token_path(), "w", encoding="utf-8") as file:
            json.dump({"token": token}, file, ensure_ascii=False, indent=4)
    except OSError:
        pass


def load_auth_token() -> str | None:
    """
    Загружает сохранённый токен автоматического входа.
    """
    path = auth_token_path()

    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        token = data.get("token")

        if not token:
            return None

        return str(token)

    except (OSError, json.JSONDecodeError):
        return None


def clear_auth_token():
    """
    Удаляет локальный токен автоматического входа.
    """
    try:
        os.remove(auth_token_path())
    except FileNotFoundError:
        pass
    except OSError:
        pass


def server_config_path() -> str:
    """
    Возвращает путь к локальному server_config.json рядом с client.py или client.exe.
    Если файла нет, используются встроенные значения DEFAULT_SERVER_CONFIG.
    """
    return app_data_path("server_config.json")


def load_server_config_dict() -> dict:
    """
    Загружает настройки сервера.

    config.ini больше не обязателен:
    дефолтный host/port встроен в программу, а изменения пользователя
    сохраняются в server_config.json рядом с exe.
    """
    config = DEFAULT_SERVER_CONFIG.copy()
    path = server_config_path()

    if not os.path.exists(path):
        return config

    try:
        with open(path, "r", encoding="utf-8") as file:
            loaded = json.load(file)

        if isinstance(loaded, dict):
            host = str(loaded.get("host", config["host"])).strip()
            port = int(loaded.get("port", config["port"]))

            if host:
                config["host"] = host

            if 1 <= port <= 65535:
                config["port"] = port

    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass

    return config


def save_server_config(host: str, port: int) -> bool:
    """
    Сохраняет настройки сервера рядом с exe.
    """
    host = str(host or "").strip()

    try:
        port = int(port)
    except (TypeError, ValueError):
        return False

    if not host:
        return False

    if not 1 <= port <= 65535:
        return False

    try:
        with open(server_config_path(), "w", encoding="utf-8") as file:
            json.dump({"host": host, "port": port}, file, ensure_ascii=False, indent=4)

        return True

    except OSError:
        return False


def load_server_config() -> tuple[str, int]:
    """
    Возвращает host и port сервера.

    Если server_config.json отсутствует, используются встроенные значения:
    127.0.0.1:5000
    """
    config = load_server_config_dict()
    return config["host"], int(config["port"])


class ClientNetwork:
    """
    Класс сетевого клиента Intercom.

    GUI будет использовать этот класс:
    - connect()
    - login()
    - get_users()
    - send_message()
    - get_history()
    - search_history()
    - disconnect()

    Также здесь есть callback-функции для уведомлений.
    """

    def __init__(self):
        self.sock = None
        self.connected = False
        self.user = None

        self.listen_thread = None
        self.listen_running = False
        self.manual_disconnect = False

        # Событие нужно, чтобы дождаться ответа на конкретный запрос
        self.response_event = threading.Event()
        self.last_response = None
        self.response_lock = threading.Lock()

        # Блокировка для отправки, чтобы разные части клиента не писали в сокет одновременно
        self.send_lock = threading.Lock()

        # Callback-функции для будущего GUI
        self.on_new_message = None
        self.on_users_status = None
        self.on_disconnected = None
        self.on_error = None
        self.on_typing = None
        self.on_recent_chats = None
        self.on_edited_message = None
        self.on_new_room_message = None
        self.on_room_typing = None
        self.on_edited_room_message = None

    def connect(self) -> bool:
        """
        Подключается к серверу из config.ini.
        """
        try:
            host, port = load_server_config()

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))

            self.connected = True
            self.listen_running = True
            self.manual_disconnect = False

            # ВАЖНО: daemon=False.
            # Так Python не завершится аварийно, пока поток ещё читает сокет или пишет в консоль.
            self.listen_thread = threading.Thread(
                target=self._listen_loop
            )
            self.listen_thread.start()

            return True


        except ConnectionRefusedError:
            self._emit_error("Сервер недоступен. Проверьте, что server.py запущен.")
            return False

        except OSError as error:
            self._emit_error(f"Ошибка подключения к серверу: {error}")
            return False

    def disconnect(self):
        """
        Корректно отключается от сервера.
        """
        self.manual_disconnect = True
        self.listen_running = False
        self.connected = False

        current_socket = self.sock

        if current_socket is not None:
            # Сначала пробуем сообщить серверу о выходе
            try:
                with self.send_lock:
                    send_json(current_socket, {"action": "logout"})
            except OSError:
                pass

            # Потом мягко закрываем соединение с двух сторон.
            # Это помогает вывести поток recv_json() из ожидания.
            try:
                current_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

            try:
                current_socket.close()
            except OSError:
                pass

        self.sock = None
        self.user = None

        # Дожидаемся завершения фонового потока.
        # Нельзя делать join(), если disconnect() вдруг вызван из самого listen_thread.
        if (
            self.listen_thread is not None
            and self.listen_thread.is_alive()
            and threading.current_thread() is not self.listen_thread
        ):
            self.listen_thread.join(timeout=2)

        self.listen_thread = None

    def _listen_loop(self):
        """
        Фоновый поток приёма сообщений от сервера.

        Здесь принимаются:
        - обычные ответы на запросы
        - события new_message
        - события users_status
        """
        while self.listen_running:
            try:
                current_socket = self.sock

                if current_socket is None:
                    break

                response = recv_json(current_socket)

                if response is None:
                    break

                data = response.get("data")

                # Сервер может прислать событие
                if isinstance(data, dict):
                    event = data.get("event")

                    if event == "new_message":
                        self._handle_new_message(data.get("message"))
                        continue

                    if event == "users_status":
                        self._handle_users_status(data.get("users"))
                        continue

                    if event == "typing":
                        self._handle_typing(data)
                        continue

                    if event == "recent_chats":
                        self._handle_recent_chats(data)
                        continue

                    if event == "edited_message":
                        self._handle_edited_message(data.get("message"))
                        continue

                    if event == "new_room_message":
                        self._handle_new_room_message(data.get("message"))
                        continue

                    if event == "room_typing":
                        self._handle_room_typing(data)
                        continue

                    if event == "edited_room_message":
                        self._handle_edited_room_message(data.get("message"))
                        continue

                # Если это не событие — считаем обычным ответом на запрос
                with self.response_lock:
                    self.last_response = response
                    self.response_event.set()

            except OSError:
                break

        was_manual_disconnect = self.manual_disconnect

        self.connected = False
        self.listen_running = False

        # Если кто-то ждал ответ от сервера, разблокируем ожидание.
        # Иначе метод _send_request_wait_response() может ждать timeout полностью.
        with self.response_lock:
            if self.last_response is None:
                self.last_response = {
                    "status": "error",
                    "message": "Соединение с сервером закрыто",
                    "data": None
                }
            self.response_event.set()

        # Callback вызываем только при неожиданном отключении.
        # При обычном network.disconnect() он не нужен.
        if not was_manual_disconnect and self.on_disconnected:
            self.on_disconnected()

    def _send_request_wait_response(self, request: dict, timeout: float = 10.0) -> dict:
        """
        Отправляет запрос серверу и ждёт ответ.

        Возвращает словарь ответа:
        {
            "status": "ok" или "error",
            "message": "...",
            "data": ...
        }
        """
        if not self.connected or self.sock is None:
            return {
                "status": "error",
                "message": "Нет подключения к серверу",
                "data": None
            }

        with self.response_lock:
            self.last_response = None
            self.response_event.clear()

        try:
            with self.send_lock:
                success = send_json(self.sock, request)
        except OSError:
            success = False

        if not success:
            return {
                "status": "error",
                "message": "Не удалось отправить запрос серверу",
                "data": None
            }

        received = self.response_event.wait(timeout)

        if not received:
            return {
                "status": "error",
                "message": "Сервер не ответил вовремя",
                "data": None
            }

        with self.response_lock:
            if self.last_response is None:
                return {
                    "status": "error",
                    "message": "Пустой ответ от сервера",
                    "data": None
                }

            return self.last_response

    def register(self, username: str, password: str) -> dict:
        """
        Регистрирует нового пользователя.
        """
        if not self.connected:
            connected = self.connect()

            if not connected:
                return {
                    "status": "error",
                    "message": "Не удалось подключиться к серверу",
                    "data": None
                }

        request = {
            "action": "register",
            "username": username,
            "password": password
        }

        return self._send_request_wait_response(request)

    def login_with_token(self, token: str) -> dict:
        """
        Выполняет автоматический вход по сохранённому токену.
        """
        if not self.connected:
            connected = self.connect()

            if not connected:
                return {
                    "status": "error",
                    "message": "Не удалось подключиться к серверу",
                    "data": None
                }

        request = {
            "action": "login_token",
            "token": token
        }

        response = self._send_request_wait_response(request)

        if response.get("status") == "ok":
            data = response.get("data")

            if isinstance(data, dict):
                self.user = data.get("user")

        return response

    def logout_token(self, token: str | None) -> dict:
        """
        Удаляет сохранённый токен на сервере.
        """
        if not token:
            return {
                "status": "ok",
                "message": "Токен отсутствует",
                "data": None
            }

        if not self.connected:
            connected = self.connect()

            if not connected:
                return {
                    "status": "error",
                    "message": "Не удалось подключиться к серверу",
                    "data": None
                }

        request = {
            "action": "logout_token",
            "token": token
        }

        return self._send_request_wait_response(request, timeout=5.0)

    def login(self, username: str, password: str) -> dict:
        """
        Авторизация пользователя.
        """
        request = {
            "action": "login",
            "username": username,
            "password": password
        }

        response = self._send_request_wait_response(request)

        if response.get("status") == "ok":
            data = response.get("data")

            if isinstance(data, dict):
                self.user = data.get("user")

        return response

    def get_users(self) -> dict:
        """
        Получает список пользователей с online/offline.
        """
        request = {
            "action": "get_users"
        }

        return self._send_request_wait_response(request)

    def get_recent_chats(self) -> dict:
        """
        Получает список недавних чатов.
        """
        request = {
            "action": "get_recent_chats"
        }

        return self._send_request_wait_response(request)

    def mark_chat_read(self, user_id: int) -> dict:
        """
        Помечает сообщения выбранного чата как прочитанные.
        """
        request = {
            "action": "mark_chat_read",
            "user_id": user_id
        }

        return self._send_request_wait_response(request)

    def update_profile(self, display_name: str, user_status: str, department: str = "", position: str = "") -> dict:
        """
        Обновляет профиль текущего пользователя.
        """
        request = {
            "action": "update_profile",
            "display_name": display_name,
            "user_status": user_status,
            "department": department,
            "position": position
        }

        response = self._send_request_wait_response(request)

        if response.get("status") == "ok":
            data = response.get("data")

            if isinstance(data, dict):
                user = data.get("user")

                if isinstance(user, dict):
                    self.user = user

        return response

    def change_password(self, old_password: str, new_password: str) -> dict:
        """
        Меняет пароль текущего пользователя.
        """
        request = {
            "action": "change_password",
            "old_password": old_password,
            "new_password": new_password
        }

        return self._send_request_wait_response(request)

    def hide_chat(self, user_id: int) -> dict:
        """
        Скрывает чат только у текущего пользователя.
        """
        request = {
            "action": "hide_chat",
            "user_id": user_id
        }

        return self._send_request_wait_response(request)

    def pin_chat(self, user_id: int, pinned: bool) -> dict:
        """
        Закрепляет или открепляет чат.
        """
        request = {
            "action": "pin_chat",
            "user_id": user_id,
            "pinned": pinned
        }

        return self._send_request_wait_response(request)


    def create_room(self, name: str, member_ids: list[int]) -> dict:
        """
        Создаёт групповой чат.
        """
        request = {
            "action": "create_room",
            "name": name,
            "member_ids": member_ids
        }

        return self._send_request_wait_response(request)

    def get_room_history(self, room_id: int) -> dict:
        """
        Получает историю группового чата.
        """
        request = {
            "action": "get_room_history",
            "room_id": room_id
        }

        return self._send_request_wait_response(request)

    def upload_file(self, file_path: str, chat_type: str, target_id: int) -> dict:
        """
        Загружает файл на сервер и создаёт file-сообщение.
        MVP-версия: без прогресса и отмены, файл передаётся base64 внутри JSON.
        """
        if not file_path:
            return {
                "status": "error",
                "message": "Файл не выбран",
                "data": None
            }

        try:
            size_bytes = os.path.getsize(file_path)
        except OSError:
            return {
                "status": "error",
                "message": "Не удалось прочитать файл",
                "data": None
            }

        if size_bytes <= 0:
            return {
                "status": "error",
                "message": "Файл пустой",
                "data": None
            }

        if size_bytes > MAX_FILE_SIZE:
            return {
                "status": "error",
                "message": "Файл слишком большой. Максимум 25 МБ",
                "data": None
            }

        try:
            with open(file_path, "rb") as file:
                file_bytes = file.read()
        except OSError:
            return {
                "status": "error",
                "message": "Не удалось прочитать файл",
                "data": None
            }

        request = {
            "action": "upload_file",
            "chat_type": chat_type,
            "original_name": os.path.basename(file_path),
            "size_bytes": len(file_bytes),
            "data_b64": base64.b64encode(file_bytes).decode("ascii")
        }

        if chat_type == "room":
            request["room_id"] = target_id
        else:
            request["receiver_id"] = target_id

        return self._send_request_wait_response(request, timeout=180.0)

    def download_file(self, file_id: int) -> dict:
        """
        Скачивает файл с сервера.
        В ответе data содержит original_name, size_bytes и data_b64.
        """
        request = {
            "action": "download_file",
            "file_id": file_id
        }

        return self._send_request_wait_response(request, timeout=180.0)

    def send_room_message(self, room_id: int, content: str, reply_to_message_id: int | None = None) -> dict:
        """
        Отправляет сообщение в групповой чат.
        """
        request = {
            "action": "send_room_message",
            "room_id": room_id,
            "content": content
        }

        if reply_to_message_id is not None:
            request["reply_to_message_id"] = reply_to_message_id

        return self._send_request_wait_response(request)

    def mark_room_read(self, room_id: int) -> dict:
        """
        Помечает групповой чат как прочитанный.
        """
        request = {
            "action": "mark_room_read",
            "room_id": room_id
        }

        return self._send_request_wait_response(request)

    def send_room_typing(self, room_id: int, is_typing: bool) -> dict:
        """
        Отправляет статус печати в групповой чат.
        """
        request = {
            "action": "room_typing",
            "room_id": room_id,
            "is_typing": is_typing
        }

        return self._send_request_wait_response(request, timeout=3.0)

    def get_room_members(self, room_id: int) -> dict:
        """
        Получает список участников группы.
        """
        request = {
            "action": "get_room_members",
            "room_id": room_id
        }

        return self._send_request_wait_response(request)

    def add_room_members(self, room_id: int, member_ids: list[int]) -> dict:
        """
        Добавляет участников в существующую группу.
        """
        request = {
            "action": "add_room_members",
            "room_id": room_id,
            "member_ids": member_ids
        }

        return self._send_request_wait_response(request)

    def leave_room(self, room_id: int) -> dict:
        """
        Выходит из группы.
        """
        request = {
            "action": "leave_room",
            "room_id": room_id
        }

        return self._send_request_wait_response(request)

    def delete_room(self, room_id: int) -> dict:
        """
        Удаляет группу.
        """
        request = {
            "action": "delete_room",
            "room_id": room_id
        }

        return self._send_request_wait_response(request)

    def send_message(self, receiver_id: int, content: str, reply_to_message_id: int | None = None) -> dict:
        """
        Отправляет личное сообщение.
        """
        request = {
            "action": "send_message",
            "receiver_id": receiver_id,
            "content": content
        }

        if reply_to_message_id is not None:
            request["reply_to_message_id"] = reply_to_message_id

        return self._send_request_wait_response(request)

    def edit_message(self, message_id: int, new_content: str) -> dict:
        """
        Редактирует своё сообщение.
        """
        request = {
            "action": "edit_message",
            "message_id": message_id,
            "new_content": new_content
        }

        return self._send_request_wait_response(request)

    def edit_room_message(self, message_id: int, new_content: str) -> dict:
        """
        Редактирует своё сообщение в группе.
        """
        request = {
            "action": "edit_room_message",
            "message_id": message_id,
            "new_content": new_content
        }

        return self._send_request_wait_response(request)

    def get_history(self, user_id: int) -> dict:
        """
        Получает историю переписки с выбранным пользователем.
        """
        request = {
            "action": "get_history",
            "user_id": user_id
        }

        return self._send_request_wait_response(request)

    def search_history(self, user_id: int, search_text: str) -> dict:
        """
        Ищет сообщения в истории переписки.
        """
        request = {
            "action": "search_history",
            "user_id": user_id,
            "search_text": search_text
        }

        return self._send_request_wait_response(request)

    def send_typing(self, receiver_id: int, is_typing: bool) -> dict:
        """
        Отправляет серверу статус набора текста.
        """
        request = {
            "action": "typing",
            "receiver_id": receiver_id,
            "is_typing": is_typing
        }

        return self._send_request_wait_response(request, timeout=3.0)

    def add_user(self, username: str, password: str, role: str = "user") -> dict:
        """
        Добавляет пользователя.
        Доступно только администратору.
        """
        request = {
            "action": "add_user",
            "username": username,
            "password": password,
            "role": role
        }

        return self._send_request_wait_response(request)

    def delete_user(self, user_id: int) -> dict:
        """
        Удаляет пользователя.
        Доступно только администратору.
        """
        request = {
            "action": "delete_user",
            "user_id": user_id
        }

        return self._send_request_wait_response(request)

    def reset_password(self, user_id: int, new_password: str) -> dict:
        """
        Сбрасывает пароль пользователя.
        Доступно только администратору.
        """
        request = {
            "action": "reset_password",
            "user_id": user_id,
            "new_password": new_password
        }

        return self._send_request_wait_response(request)

    def _handle_new_message(self, message: dict):
        """
        Обрабатывает событие нового сообщения от сервера.
        """
        if self.on_new_message:
            self.on_new_message(message)

    def _handle_users_status(self, users: list):
        """
        Обрабатывает событие обновления статусов пользователей.
        """
        if self.on_users_status:
            self.on_users_status(users)

    def _handle_typing(self, typing_data: dict):
        """
        Обрабатывает событие typing от сервера.
        """
        if self.on_typing:
            self.on_typing(typing_data)

    def _handle_recent_chats(self, data: dict):
        """
        Обрабатывает событие обновления недавних чатов.
        """
        if self.on_recent_chats:
            self.on_recent_chats(data)

    def _handle_edited_message(self, message: dict):
        """
        Обрабатывает событие редактирования сообщения.
        """
        if self.on_edited_message:
            self.on_edited_message(message)

    def _handle_new_room_message(self, message: dict):
        """
        Обрабатывает новое сообщение из группового чата.
        """
        if self.on_new_room_message:
            self.on_new_room_message(message)

    def _handle_room_typing(self, data: dict):
        """
        Обрабатывает событие печати в группе.
        """
        if self.on_room_typing:
            self.on_room_typing(data)

    def _handle_edited_room_message(self, message: dict):
        """
        Обрабатывает событие редактирования сообщения в группе.
        """
        if self.on_edited_room_message:
            self.on_edited_room_message(message)

    def _emit_error(self, message: str):
        """
        Передаёт ошибку наружу, например в GUI.
        """
        if self.on_error:
            self.on_error(message)
        else:
            print("Ошибка:", message)
