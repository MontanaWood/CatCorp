# Модуль работы серверной части CatCorp с базой данных MySQL/MariaDB

import hashlib
import secrets
import mysql.connector
from mysql.connector import Error


DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3307,
    "user": "root",
    "password": "",
    "database": "catcorp",
    "charset": "utf8mb4"
}


def hash_password(password: str) -> str:
    """
    Возвращает SHA-256 хэш пароля.
    Пароль не хранится в базе в открытом виде.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_connection():
    """
    Создаёт новое подключение к базе данных.
    Каждая операция получает своё подключение, чтобы избежать проблем с потоками.
    """
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection

    except Error as error:
        print("Ошибка подключения к базе данных:")
        print(error)
        return None

def ensure_user_profile_columns() -> bool:
    """
    Добавляет дополнительные поля профиля пользователя, если их ещё нет.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        try:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN department VARCHAR(120) NULL
            """)
        except Error:
            pass

        try:
            cursor.execute("""
                ALTER TABLE users
                ADD COLUMN position VARCHAR(120) NULL
            """)
        except Error:
            pass

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при подготовке дополнительных полей профиля:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()



def ensure_user_tokens_table():
    """
    Создаёт таблицу токенов автоматического входа, если её ещё нет.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_tokens (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                token_hash VARCHAR(64) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при создании таблицы user_tokens:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def create_auth_token(user_id: int) -> str | None:
    """
    Создаёт новый токен автоматического входа.
    Клиент получает сам токен, а сервер хранит только SHA-256 хэш.
    """
    if not ensure_user_tokens_table():
        return None

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor()
        token = secrets.token_urlsafe(32)
        token_hash = hash_password(token)

        query = """
            INSERT INTO user_tokens (user_id, token_hash)
            VALUES (%s, %s)
        """

        cursor.execute(query, (user_id, token_hash))
        connection.commit()

        return token

    except Error as error:
        print("Ошибка при создании токена входа:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def authenticate_by_token(token: str):
    """
    Проверяет токен автоматического входа.
    Возвращает пользователя или None.
    """
    if not token:
        return None

    if not ensure_user_tokens_table():
        return None

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        token_hash = hash_password(token)

        query = """
            SELECT u.id, u.username, u.role, u.display_name, u.user_status, u.last_login_at
            FROM user_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = %s
            LIMIT 1
        """

        cursor.execute(query, (token_hash,))
        user = cursor.fetchone()

        return user

    except Error as error:
        print("Ошибка при входе по токену:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def delete_auth_token(token: str) -> bool:
    """
    Удаляет токен автоматического входа на сервере.
    Используется при кнопке 'Выйти'.
    """
    if not token:
        return True

    if not ensure_user_tokens_table():
        return False

    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        token_hash = hash_password(token)

        query = """
            DELETE FROM user_tokens
            WHERE token_hash = %s
        """

        cursor.execute(query, (token_hash,))
        connection.commit()

        return True

    except Error as error:
        print("Ошибка при удалении токена входа:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def authenticate_user(username: str, password: str):
    """
    Проверяет логин и пароль пользователя.
    """
    ensure_user_profile_columns()
    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        password_hash = hash_password(password)

        query = """
            SELECT id, username, role, display_name, user_status, department, position, last_login_at
            FROM users
            WHERE username = %s AND password_hash = %s
            LIMIT 1
        """

        cursor.execute(query, (username, password_hash))
        user = cursor.fetchone()

        return user

    except Error as error:
        print("Ошибка при авторизации пользователя:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_all_users():
    """
    Возвращает список всех пользователей без паролей.
    """
    ensure_user_profile_columns()
    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT id, username, role, display_name, user_status, department, position, last_login_at, created_at
            FROM users
            ORDER BY username ASC
        """

        cursor.execute(query)
        users = cursor.fetchall()

        return users

    except Error as error:
        print("Ошибка при получении списка пользователей:")
        print(error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def register_user(username: str, password: str) -> tuple[bool, str]:
    """
    Регистрирует нового обычного пользователя.
    """
    username = username.strip()

    if not username:
        return False, "Введите логин"

    if len(username) < 3:
        return False, "Логин должен быть не короче 3 символов"

    if len(username) > 50:
        return False, "Логин должен быть не длиннее 50 символов"

    if not password:
        return False, "Введите пароль"

    if len(password) < 4:
        return False, "Пароль должен быть не короче 4 символов"

    connection = get_connection()

    if connection is None:
        return False, "Нет подключения к базе данных"

    try:
        cursor = connection.cursor()
        password_hash = hash_password(password)

        query = """
            INSERT INTO users (username, password_hash, role, display_name, user_status)
            VALUES (%s, %s, 'user', %s, 'available')
        """

        cursor.execute(query, (username, password_hash, username))
        connection.commit()

        return True, "Пользователь зарегистрирован"

    except Error as error:
        error_text = str(error)

        if "Duplicate entry" in error_text:
            return False, "Пользователь с таким логином уже существует"

        print("Ошибка при регистрации пользователя:")
        print(error)
        return False, "Не удалось зарегистрировать пользователя"

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def add_user(username: str, password: str, role: str = "user") -> bool:
    """
    Добавляет нового пользователя.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        password_hash = hash_password(password)

        query = """
            INSERT INTO users (username, password_hash, role, display_name, user_status)
            VALUES (%s, %s, %s, %s, 'available')
        """

        cursor.execute(query, (username, password_hash, role, username))
        connection.commit()

        return True

    except Error as error:
        print("Ошибка при добавлении пользователя:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def delete_user(user_id: int) -> bool:
    """
    Удаляет пользователя по ID.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        query = """
            DELETE FROM users
            WHERE id = %s
        """

        cursor.execute(query, (user_id,))
        connection.commit()

        return cursor.rowcount > 0

    except Error as error:
        print("Ошибка при удалении пользователя:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def reset_user_password(user_id: int, new_password: str) -> bool:
    """
    Сбрасывает пароль пользователя по ID.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        new_password_hash = hash_password(new_password)

        query = """
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
        """

        cursor.execute(query, (new_password_hash, user_id))
        connection.commit()

        return cursor.rowcount > 0

    except Error as error:
        print("Ошибка при сбросе пароля:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def update_user_profile(user_id: int, display_name: str, user_status: str, department: str = "", position: str = "") -> tuple[bool, str]:
    """
    Обновляет отображаемое имя, статус, отдел и должность пользователя.
    """
    ensure_user_profile_columns()

    display_name = display_name.strip()
    department = str(department or "").strip()
    position = str(position or "").strip()

    if not display_name:
        return False, "Введите отображаемое имя"

    if len(display_name) > 80:
        return False, "Отображаемое имя слишком длинное"

    if len(department) > 120:
        return False, "Название отдела слишком длинное"

    if len(position) > 120:
        return False, "Название должности слишком длинное"

    if user_status not in ("available", "busy", "do_not_disturb", "away"):
        return False, "Некорректный статус"

    connection = get_connection()

    if connection is None:
        return False, "Нет подключения к базе данных"

    try:
        cursor = connection.cursor()

        query = """
            UPDATE users
            SET display_name = %s,
                user_status = %s,
                department = %s,
                position = %s
            WHERE id = %s
        """

        cursor.execute(query, (display_name, user_status, department, position, user_id))
        connection.commit()

        return True, "Профиль обновлён"

    except Error as error:
        print("Ошибка при обновлении профиля:")
        print(error)
        return False, "Не удалось обновить профиль"

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()



def change_user_password(user_id: int, old_password: str, new_password: str) -> tuple[bool, str]:
    """
    Меняет пароль пользователя после проверки старого пароля.
    """
    if not old_password:
        return False, "Введите старый пароль"

    if len(new_password) < 4:
        return False, "Новый пароль должен быть не короче 4 символов"

    connection = get_connection()

    if connection is None:
        return False, "Нет подключения к базе данных"

    try:
        cursor = connection.cursor(dictionary=True)

        old_hash = hash_password(old_password)

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE id = %s AND password_hash = %s
            LIMIT 1
            """,
            (user_id, old_hash)
        )

        user = cursor.fetchone()

        if user is None:
            return False, "Старый пароль указан неверно"

        new_hash = hash_password(new_password)

        cursor.execute(
            """
            UPDATE users
            SET password_hash = %s
            WHERE id = %s
            """,
            (new_hash, user_id)
        )

        connection.commit()

        return True, "Пароль изменён"

    except Error as error:
        print("Ошибка при смене пароля:")
        print(error)
        return False, "Не удалось изменить пароль"

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def save_message(sender_id: int, receiver_id: int, content: str, reply_to_message_id: int | None = None):
    """
    Сохраняет личное сообщение в базу данных.
    Возвращает ID нового сообщения или None при ошибке.
    """
    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor()

        query = """
            INSERT INTO messages (sender_id, receiver_id, content, read_at, reply_to_message_id)
            VALUES (%s, %s, %s, NULL, %s)
        """

        cursor.execute(query, (sender_id, receiver_id, content, reply_to_message_id))
        message_id = cursor.lastrowid

        # Если получатель раньше скрывал этот чат, новое сообщение возвращает чат в список.
        cursor.execute(
            """
            DELETE FROM hidden_chats
            WHERE user_id = %s AND other_user_id = %s
            """,
            (receiver_id, sender_id)
        )

        # Если отправитель сам писал в скрытый чат, тоже возвращаем его в список отправителя.
        cursor.execute(
            """
            DELETE FROM hidden_chats
            WHERE user_id = %s AND other_user_id = %s
            """,
            (sender_id, receiver_id)
        )

        connection.commit()

        return message_id

    except Error as error:
        print("Ошибка при сохранении сообщения:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_message_history(user1_id: int, user2_id: int):
    """
    Возвращает историю переписки между двумя пользователями.
    """
    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                m.id,
                m.sender_id,
                COALESCE(sender.display_name, sender.username) AS sender_username,
                m.receiver_id,
                COALESCE(receiver.display_name, receiver.username) AS receiver_username,
                m.content,
                m.sent_at,
                m.read_at,
                m.edited_at,
                m.reply_to_message_id,
                reply.content AS reply_content,
                COALESCE(reply_sender.display_name, reply_sender.username) AS reply_sender_username
            FROM messages m
            JOIN users sender ON m.sender_id = sender.id
            JOIN users receiver ON m.receiver_id = receiver.id
            LEFT JOIN messages reply ON m.reply_to_message_id = reply.id
            LEFT JOIN users reply_sender ON reply.sender_id = reply_sender.id
            WHERE 
                (m.sender_id = %s AND m.receiver_id = %s)
                OR
                (m.sender_id = %s AND m.receiver_id = %s)
            ORDER BY m.sent_at ASC
        """

        cursor.execute(query, (user1_id, user2_id, user2_id, user1_id))
        messages = cursor.fetchall()

        return messages

    except Error as error:
        print("Ошибка при получении истории сообщений:")
        print(error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def search_message_history(user1_id: int, user2_id: int, search_text: str):
    """
    Ищет сообщения в истории переписки двух пользователей.
    """
    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                m.id,
                m.sender_id,
                COALESCE(sender.display_name, sender.username) AS sender_username,
                m.receiver_id,
                COALESCE(receiver.display_name, receiver.username) AS receiver_username,
                m.content,
                m.sent_at,
                m.read_at,
                m.edited_at,
                m.reply_to_message_id,
                reply.content AS reply_content,
                COALESCE(reply_sender.display_name, reply_sender.username) AS reply_sender_username
            FROM messages m
            JOIN users sender ON m.sender_id = sender.id
            JOIN users receiver ON m.receiver_id = receiver.id
            LEFT JOIN messages reply ON m.reply_to_message_id = reply.id
            LEFT JOIN users reply_sender ON reply.sender_id = reply_sender.id
            WHERE 
                (
                    (m.sender_id = %s AND m.receiver_id = %s)
                    OR
                    (m.sender_id = %s AND m.receiver_id = %s)
                )
                AND m.content LIKE %s
            ORDER BY m.sent_at ASC
        """

        like_text = f"%{search_text}%"
        cursor.execute(query, (user1_id, user2_id, user2_id, user1_id, like_text))
        messages = cursor.fetchall()

        return messages

    except Error as error:
        print("Ошибка при поиске сообщений:")
        print(error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_recent_chats(user_id: int):
    """
    Возвращает список недавних чатов пользователя.
    Скрытые чаты не возвращаются, пока не придёт новое сообщение.
    Закреплённые чаты отображаются сверху.
    """
    ensure_user_profile_columns()
    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                u.id,
                u.username,
                COALESCE(u.display_name, u.username) AS display_name,
                u.role,
                u.user_status,
                u.department,
                u.position,
                u.last_login_at,
                last_msg.content AS last_message,
                last_msg.sent_at AS last_message_time,

                (
                    SELECT COUNT(*)
                    FROM messages unread
                    WHERE unread.sender_id = u.id
                      AND unread.receiver_id = %s
                      AND unread.read_at IS NULL
                ) AS unread_count,

                CASE
                    WHEN pinned.user_id IS NULL THEN 0
                    ELSE 1
                END AS pinned

            FROM users u

            JOIN (
                SELECT
                    CASE
                        WHEN sender_id = %s THEN receiver_id
                        ELSE sender_id
                    END AS other_user_id,
                    MAX(id) AS last_message_id
                FROM messages
                WHERE sender_id = %s OR receiver_id = %s
                GROUP BY other_user_id
            ) recent ON recent.other_user_id = u.id

            JOIN messages last_msg ON last_msg.id = recent.last_message_id

            LEFT JOIN hidden_chats hidden
                ON hidden.user_id = %s
               AND hidden.other_user_id = u.id

            LEFT JOIN pinned_chats pinned
                ON pinned.user_id = %s
               AND pinned.other_user_id = u.id

            WHERE hidden.user_id IS NULL

            ORDER BY pinned DESC, last_msg.sent_at DESC, last_msg.id DESC
        """

        cursor.execute(query, (user_id, user_id, user_id, user_id, user_id, user_id))
        chats = cursor.fetchall()

        return chats

    except Error as error:
        print("Ошибка при получении недавних чатов:")
        print(error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def mark_chat_as_read(current_user_id: int, other_user_id: int) -> bool:
    """
    Помечает сообщения от выбранного собеседника как прочитанные.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        query = """
            UPDATE messages
            SET read_at = NOW()
            WHERE sender_id = %s
              AND receiver_id = %s
              AND read_at IS NULL
        """

        cursor.execute(query, (other_user_id, current_user_id))
        connection.commit()

        return True

    except Error as error:
        print("Ошибка при пометке сообщений как прочитанных:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_total_unread_count(user_id: int) -> int:
    """
    Возвращает общее количество непрочитанных входящих сообщений.
    """
    connection = get_connection()

    if connection is None:
        return 0

    try:
        cursor = connection.cursor()

        query = """
            SELECT COUNT(*)
            FROM messages
            WHERE receiver_id = %s
              AND read_at IS NULL
        """

        cursor.execute(query, (user_id,))
        result = cursor.fetchone()

        if result is None:
            return 0

        return int(result[0])

    except Error as error:
        print("Ошибка при подсчёте непрочитанных сообщений:")
        print(error)
        return 0

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def hide_chat(user_id: int, other_user_id: int) -> bool:
    """
    Скрывает чат только для одного пользователя.
    Сообщения при этом не удаляются.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        query = """
            INSERT INTO hidden_chats (user_id, other_user_id)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE hidden_at = NOW()
        """

        cursor.execute(query, (user_id, other_user_id))
        connection.commit()

        return True

    except Error as error:
        print("Ошибка при скрытии чата:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def set_chat_pinned(user_id: int, other_user_id: int, pinned: bool) -> bool:
    """
    Закрепляет или открепляет чат у конкретного пользователя.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        if pinned:
            query = """
                INSERT INTO pinned_chats (user_id, other_user_id)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE pinned_at = NOW()
            """
            cursor.execute(query, (user_id, other_user_id))
        else:
            query = """
                DELETE FROM pinned_chats
                WHERE user_id = %s AND other_user_id = %s
            """
            cursor.execute(query, (user_id, other_user_id))

        connection.commit()

        return True

    except Error as error:
        print("Ошибка при изменении закрепления чата:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()



def update_last_login(user_id: int) -> bool:
    """
    Обновляет время последнего входа пользователя.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE users
            SET last_login_at = NOW()
            WHERE id = %s
            """,
            (user_id,)
        )

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при обновлении последнего входа:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def edit_message(message_id: int, sender_id: int, new_content: str):
    """
    Редактирует своё сообщение и возвращает обновлённое сообщение.
    """
    new_content = new_content.strip()

    if not new_content:
        return None

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, sender_id, receiver_id, sent_at, (sent_at >= DATE_SUB(NOW(), INTERVAL 48 HOUR)) AS can_edit
            FROM messages
            WHERE id = %s
            LIMIT 1
            """,
            (message_id,)
        )

        message = cursor.fetchone()

        if message is None:
            return None

        if int(message["sender_id"]) != int(sender_id):
            return None

        if not bool(message.get("can_edit")):
            return None

        cursor.execute(
            """
            UPDATE messages
            SET content = %s, edited_at = NOW()
            WHERE id = %s AND sender_id = %s
            """,
            (new_content, message_id, sender_id)
        )

        connection.commit()

        cursor.execute(
            """
            SELECT 
                m.id,
                m.sender_id,
                COALESCE(sender.display_name, sender.username) AS sender_username,
                m.receiver_id,
                COALESCE(receiver.display_name, receiver.username) AS receiver_username,
                m.content,
                m.sent_at,
                m.read_at,
                m.edited_at,
                m.reply_to_message_id,
                reply.content AS reply_content,
                COALESCE(reply_sender.display_name, reply_sender.username) AS reply_sender_username
            FROM messages m
            JOIN users sender ON m.sender_id = sender.id
            JOIN users receiver ON m.receiver_id = receiver.id
            LEFT JOIN messages reply ON m.reply_to_message_id = reply.id
            LEFT JOIN users reply_sender ON reply.sender_id = reply_sender.id
            WHERE m.id = %s
            LIMIT 1
            """,
            (message_id,)
        )

        return cursor.fetchone()

    except Error as error:
        print("Ошибка при редактировании сообщения:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()



def ensure_group_tables() -> bool:
    """
    Создаёт таблицы групповых чатов, если их ещё нет.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rooms (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(120) NOT NULL,
                created_by INT NOT NULL,
                created_at DATETIME DEFAULT NOW(),
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_members (
                room_id INT NOT NULL,
                user_id INT NOT NULL,
                joined_at DATETIME DEFAULT NOW(),
                PRIMARY KEY (room_id, user_id),
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                room_id INT NOT NULL,
                sender_id INT NOT NULL,
                content TEXT NOT NULL,
                sent_at DATETIME DEFAULT NOW(),
                edited_at DATETIME NULL,
                reply_to_message_id INT NULL,
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (reply_to_message_id) REFERENCES room_messages(id) ON DELETE SET NULL
            )
        """)

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при создании таблиц групповых чатов:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def create_room(name: str, creator_id: int, member_ids: list[int]):
    """
    Создаёт групповой чат и добавляет участников.
    """
    if not ensure_group_tables():
        return None

    name = name.strip()

    if not name:
        return None

    if len(name) > 120:
        name = name[:120]

    unique_members = set()

    for member_id in member_ids:
        try:
            unique_members.add(int(member_id))
        except (TypeError, ValueError):
            pass

    unique_members.add(int(creator_id))

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            INSERT INTO rooms (name, created_by)
            VALUES (%s, %s)
            """,
            (name, creator_id)
        )

        room_id = cursor.lastrowid

        for member_id in unique_members:
            cursor.execute(
                """
                INSERT IGNORE INTO room_members (room_id, user_id)
                VALUES (%s, %s)
                """,
                (room_id, member_id)
            )

        connection.commit()

        return get_room_for_user(creator_id, room_id)

    except Error as error:
        print("Ошибка при создании группового чата:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def is_room_member(room_id: int, user_id: int) -> bool:
    """
    Проверяет, состоит ли пользователь в группе.
    """
    if not ensure_group_tables():
        return False

    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM room_members
            WHERE room_id = %s AND user_id = %s
            """,
            (room_id, user_id)
        )
        result = cursor.fetchone()
        return bool(result and int(result[0]) > 0)

    except Error as error:
        print("Ошибка при проверке участника группы:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_room_member_ids(room_id: int):
    """
    Возвращает ID участников группы.
    """
    if not ensure_group_tables():
        return []

    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT user_id
            FROM room_members
            WHERE room_id = %s
            """,
            (room_id,)
        )
        return [int(row[0]) for row in cursor.fetchall()]

    except Error as error:
        print("Ошибка при получении участников группы:")
        print(error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_room_for_user(user_id: int, room_id: int):
    """
    Возвращает информацию о группе, если пользователь является участником.
    """
    if not ensure_group_tables():
        return None

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                r.id,
                r.name,
                r.created_by,
                r.created_at,
                last_msg.content AS last_message,
                last_msg.sent_at AS last_message_time
            FROM rooms r
            JOIN room_members rm ON rm.room_id = r.id AND rm.user_id = %s
            LEFT JOIN (
                SELECT room_id, MAX(id) AS last_message_id
                FROM room_messages
                GROUP BY room_id
            ) recent ON recent.room_id = r.id
            LEFT JOIN room_messages last_msg ON last_msg.id = recent.last_message_id
            WHERE r.id = %s
            LIMIT 1
            """,
            (user_id, room_id)
        )
        return cursor.fetchone()

    except Error as error:
        print("Ошибка при получении группы:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_user_rooms(user_id: int):
    """
    Возвращает группы пользователя для списка недавних чатов.
    """
    if not ensure_group_tables():
        return []

    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                r.id,
                r.name,
                r.created_by,
                r.created_at,
                last_msg.content AS last_message,
                last_msg.sent_at AS last_message_time
            FROM rooms r
            JOIN room_members rm ON rm.room_id = r.id AND rm.user_id = %s
            LEFT JOIN (
                SELECT room_id, MAX(id) AS last_message_id
                FROM room_messages
                GROUP BY room_id
            ) recent ON recent.room_id = r.id
            LEFT JOIN room_messages last_msg ON last_msg.id = recent.last_message_id
            ORDER BY last_msg.sent_at DESC, r.created_at DESC
            """,
            (user_id,)
        )
        return cursor.fetchall()

    except Error as error:
        print("Ошибка при получении групп пользователя:")
        print(error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()



def ensure_room_read_state_table() -> bool:
    """
    Создаёт таблицу отметок прочтения групповых сообщений.
    Также пытается добавить reply_to_message_id в room_messages для ответов.
    """
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS room_read_state (
                room_id INT NOT NULL,
                user_id INT NOT NULL,
                last_read_message_id INT DEFAULT 0,
                updated_at DATETIME DEFAULT NOW(),
                PRIMARY KEY (room_id, user_id),
                FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        try:
            cursor.execute("""
                ALTER TABLE room_messages
                ADD COLUMN reply_to_message_id INT NULL
            """)
        except Error:
            pass

        try:
            cursor.execute("""
                ALTER TABLE room_messages
                ADD COLUMN edited_at DATETIME NULL
            """)
        except Error:
            pass

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при создании room_read_state:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def mark_room_as_read(user_id: int, room_id: int) -> bool:
    """
    Помечает групповой чат как прочитанный для пользователя.
    """
    ensure_room_read_state_table()
    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT MAX(id) AS last_id
            FROM room_messages
            WHERE room_id = %s
            """,
            (room_id,)
        )

        row = cursor.fetchone()
        last_id = int(row.get("last_id") or 0)

        cursor.execute(
            """
            INSERT INTO room_read_state (room_id, user_id, last_read_message_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                last_read_message_id = VALUES(last_read_message_id),
                updated_at = NOW()
            """,
            (room_id, user_id, last_id)
        )

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при отметке группы как прочитанной:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_room_unread_count(user_id: int, room_id: int) -> int:
    """
    Возвращает количество непрочитанных сообщений группы.
    """
    ensure_room_read_state_table()
    connection = get_connection()

    if connection is None:
        return 0

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT COALESCE(last_read_message_id, 0) AS last_read_message_id
            FROM room_read_state
            WHERE room_id = %s AND user_id = %s
            LIMIT 1
            """,
            (room_id, user_id)
        )

        state = cursor.fetchone()
        last_read_id = int(state.get("last_read_message_id") if state else 0)

        cursor.execute(
            """
            SELECT COUNT(*) AS unread_count
            FROM room_messages
            WHERE room_id = %s
              AND id > %s
              AND sender_id <> %s
            """,
            (room_id, last_read_id, user_id)
        )

        row = cursor.fetchone()
        return int(row.get("unread_count") or 0)

    except Error as error:
        print("Ошибка при подсчёте непрочитанных сообщений группы:")
        print(error)
        return 0

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def save_room_message(room_id: int, sender_id: int, content: str, reply_to_message_id: int | None = None):
    """
    Сохраняет сообщение группы.
    Возвращает ID нового сообщения или None при ошибке.
    """
    ensure_room_read_state_table()

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO room_messages (room_id, sender_id, content, reply_to_message_id)
            VALUES (%s, %s, %s, %s)
            """,
            (room_id, sender_id, content, reply_to_message_id)
        )

        message_id = cursor.lastrowid

        # Свои сообщения сразу считаются прочитанными для отправителя.
        cursor.execute(
            """
            INSERT INTO room_read_state (room_id, user_id, last_read_message_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                last_read_message_id = VALUES(last_read_message_id),
                updated_at = NOW()
            """,
            (room_id, sender_id, message_id)
        )

        connection.commit()

        return message_id

    except Error as error:
        print("Ошибка при сохранении сообщения группы:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def get_room_history(user_id: int, room_id: int):
    """
    Возвращает историю группового чата, если пользователь участник.
    """
    ensure_room_read_state_table()

    if not is_room_member(room_id, user_id):
        return []

    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                m.id,
                m.room_id,
                m.sender_id,
                COALESCE(u.display_name, u.username) AS sender_username,
                m.content,
                m.sent_at,
                m.edited_at,
                m.reply_to_message_id,
                reply.content AS reply_content,
                COALESCE(reply_sender.display_name, reply_sender.username) AS reply_sender_username
            FROM room_messages m
            JOIN users u ON u.id = m.sender_id
            LEFT JOIN room_messages reply ON m.reply_to_message_id = reply.id
            LEFT JOIN users reply_sender ON reply.sender_id = reply_sender.id
            WHERE m.room_id = %s
            ORDER BY m.sent_at ASC, m.id ASC
            """,
            (room_id,)
        )
        return cursor.fetchall()

    except Error as error:
        print("Ошибка при получении истории группы:")
        print(error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()



def get_room_message_by_id(user_id: int, message_id: int):
    """
    Возвращает сообщение группы по ID, если пользователь состоит в группе.
    """
    ensure_room_read_state_table()

    if not ensure_group_tables():
        return None

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                m.id,
                m.room_id,
                m.sender_id,
                COALESCE(u.display_name, u.username) AS sender_username,
                m.content,
                m.sent_at,
                m.edited_at,
                m.reply_to_message_id,
                reply.content AS reply_content,
                COALESCE(reply_sender.display_name, reply_sender.username) AS reply_sender_username
            FROM room_messages m
            JOIN users u ON u.id = m.sender_id
            JOIN room_members rm ON rm.room_id = m.room_id AND rm.user_id = %s
            LEFT JOIN room_messages reply ON m.reply_to_message_id = reply.id
            LEFT JOIN users reply_sender ON reply.sender_id = reply_sender.id
            WHERE m.id = %s
            LIMIT 1
            """,
            (user_id, message_id)
        )
        return cursor.fetchone()

    except Error as error:
        print("Ошибка при получении сообщения группы:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()




def edit_room_message(message_id: int, sender_id: int, new_content: str):
    """
    Редактирует своё сообщение в группе и возвращает обновлённое сообщение.
    """
    ensure_room_read_state_table()

    new_content = new_content.strip()

    if not new_content:
        return None

    connection = get_connection()

    if connection is None:
        return None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, room_id, sender_id, sent_at, (sent_at >= DATE_SUB(NOW(), INTERVAL 48 HOUR)) AS can_edit
            FROM room_messages
            WHERE id = %s
            LIMIT 1
            """,
            (message_id,)
        )

        message = cursor.fetchone()

        if message is None:
            return None

        if int(message["sender_id"]) != int(sender_id):
            return None

        if not is_room_member(int(message["room_id"]), int(sender_id)):
            return None

        if not bool(message.get("can_edit")):
            return None

        cursor.execute(
            """
            UPDATE room_messages
            SET content = %s, edited_at = NOW()
            WHERE id = %s AND sender_id = %s
            """,
            (new_content, message_id, sender_id)
        )

        connection.commit()

        return get_room_message_by_id(sender_id, message_id)

    except Error as error:
        print("Ошибка при редактировании сообщения группы:")
        print(error)
        return None

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()



def get_room_members(user_id: int, room_id: int):
    """
    Возвращает участников группы, если текущий пользователь состоит в этой группе.
    """
    if not is_room_member(room_id, user_id):
        return []

    connection = get_connection()

    if connection is None:
        return []

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                COALESCE(u.display_name, u.username) AS display_name,
                u.role,
                u.user_status,
                u.department,
                u.position,
                u.last_login_at,
                rm.joined_at
            FROM room_members rm
            JOIN users u ON u.id = rm.user_id
            WHERE rm.room_id = %s
            ORDER BY u.username ASC
            """,
            (room_id,)
        )
        return cursor.fetchall()

    except Error as error:
        print("Ошибка при получении участников группы:")
        print(error)
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def add_room_members(room_id: int, requester_id: int, member_ids: list[int]) -> bool:
    """
    Добавляет участников в существующую группу.
    Добавлять участников может любой текущий участник группы.
    """
    if not is_room_member(room_id, requester_id):
        return False

    unique_members = set()

    for member_id in member_ids:
        try:
            member_id = int(member_id)
        except (TypeError, ValueError):
            continue

        if member_id != int(requester_id):
            unique_members.add(member_id)

    if not unique_members:
        return True

    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        for member_id in unique_members:
            cursor.execute(
                """
                INSERT IGNORE INTO room_members (room_id, user_id)
                VALUES (%s, %s)
                """,
                (room_id, member_id)
            )

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при добавлении участников группы:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def leave_room(room_id: int, user_id: int) -> bool:
    """
    Позволяет пользователю выйти из группы.
    Если участников не осталось, группа удаляется автоматически.
    """
    if not is_room_member(room_id, user_id):
        return False

    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM room_members
            WHERE room_id = %s AND user_id = %s
            """,
            (room_id, user_id)
        )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM room_members
            WHERE room_id = %s
            """,
            (room_id,)
        )
        result = cursor.fetchone()
        members_left = int(result[0]) if result else 0

        if members_left == 0:
            cursor.execute(
                """
                DELETE FROM rooms
                WHERE id = %s
                """,
                (room_id,)
            )

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при выходе из группы:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def delete_room(room_id: int, requester_id: int, is_admin: bool = False) -> bool:
    """
    Удаляет группу.
    Удалять может создатель группы или администратор.
    """
    if not ensure_group_tables():
        return False

    connection = get_connection()

    if connection is None:
        return False

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, created_by
            FROM rooms
            WHERE id = %s
            LIMIT 1
            """,
            (room_id,)
        )
        room = cursor.fetchone()

        if room is None:
            return False

        if int(room["created_by"]) != int(requester_id) and not is_admin:
            return False

        cursor.execute(
            """
            DELETE FROM rooms
            WHERE id = %s
            """,
            (room_id,)
        )

        connection.commit()
        return True

    except Error as error:
        print("Ошибка при удалении группы:")
        print(error)
        return False

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


def test_database():
    """
    Тестовая функция для проверки работы модуля.
    """
    print("Проверка подключения к базе данных...")

    connection = get_connection()

    if connection is None:
        print("Подключение не удалось")
        return

    print("Подключение успешно")
    connection.close()


if __name__ == "__main__":
    test_database()
