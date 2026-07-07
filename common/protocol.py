# Общий модуль сетевого протокола CatCorp для обмена JSON-сообщениями через TCP

import json
import socket
import struct


HEADER_SIZE = 4
ENCODING = "utf-8"


def send_json(sock: socket.socket, data: dict) -> bool:
    """
    Отправляет словарь Python как JSON-сообщение через TCP-сокет.

    Формат передачи:
    1. Сначала 4 байта с длиной JSON-сообщения.
    2. Потом само JSON-сообщение в UTF-8.

    Возвращает True при успехе и False при ошибке.
    """
    try:
        # Преобразуем словарь в JSON-строку
        json_text = json.dumps(data, ensure_ascii=False)

        # Преобразуем JSON-строку в байты
        json_bytes = json_text.encode(ENCODING)

        # Упаковываем длину сообщения в 4 байта
        header = struct.pack("!I", len(json_bytes))

        # Отправляем заголовок и само сообщение
        sock.sendall(header + json_bytes)

        return True

    except (OSError, TypeError, ValueError) as error:
        print("Ошибка отправки JSON-сообщения:")
        print(error)
        return False


def recv_exact(sock: socket.socket, size: int) -> bytes | None:
    """
    Читает из сокета ровно size байт.

    Это нужно, потому что TCP может вернуть данные частями.
    Например, мы ждём 100 байт, а recv() может сначала вернуть только 30.
    """
    data = b""

    try:
        while len(data) < size:
            chunk = sock.recv(size - len(data))

            # Если chunk пустой — соединение закрыто
            if not chunk:
                return None

            data += chunk

        return data

    except OSError as error:
        print("Ошибка чтения из сокета:")
        print(error)
        return None


def recv_json(sock: socket.socket) -> dict | None:
    """
    Получает JSON-сообщение из TCP-сокета.

    Сначала читает 4 байта длины сообщения.
    Потом читает само JSON-сообщение.
    Возвращает словарь Python или None при ошибке/отключении.
    """
    try:
        # Читаем заголовок с длиной сообщения
        header = recv_exact(sock, HEADER_SIZE)

        if header is None:
            return None

        # Распаковываем длину сообщения
        message_size = struct.unpack("!I", header)[0]

        # Защита от слишком больших сообщений
        if message_size <= 0 or message_size > 50_000_000:
            print("Некорректный размер сообщения:", message_size)
            return None

        # Читаем JSON-сообщение
        json_bytes = recv_exact(sock, message_size)

        if json_bytes is None:
            return None

        # Декодируем UTF-8
        json_text = json_bytes.decode(ENCODING)

        # Преобразуем JSON в словарь Python
        data = json.loads(json_text)

        if not isinstance(data, dict):
            print("Полученное JSON-сообщение не является объектом")
            return None

        return data

    except (OSError, UnicodeDecodeError, json.JSONDecodeError, struct.error) as error:
        print("Ошибка получения JSON-сообщения:")
        print(error)
        return None


def make_response(status: str, message: str = "", data: dict | list | None = None) -> dict:
    """
    Создаёт стандартный ответ сервера.

    status:
    - ok
    - error

    Пример:
    {
        "status": "ok",
        "message": "Авторизация успешна",
        "data": {...}
    }
    """
    return {
        "status": status,
        "message": message,
        "data": data
    }


def make_error(message: str) -> dict:
    """
    Быстро создаёт ответ с ошибкой.
    """
    return make_response(
        status="error",
        message=message,
        data=None
    )


def make_ok(message: str = "", data: dict | list | None = None) -> dict:
    """
    Быстро создаёт успешный ответ.
    """
    return make_response(
        status="ok",
        message=message,
        data=data
    )