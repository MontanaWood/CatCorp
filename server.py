# Серверная часть CatCorp: принимает TCP-подключения клиентов, работает с БД и пересылает сообщения

import socket
import threading
from datetime import datetime

from common.protocol import send_json, recv_json, make_ok, make_error
from server_db import (
    authenticate_user,
    register_user,
    get_all_users,
    save_message,
    get_message_history,
    search_message_history,
    add_user,
    delete_user,
    reset_user_password,
    get_recent_chats,
    mark_chat_as_read,
    get_total_unread_count,
    update_user_profile,
    change_user_password,
    hide_chat,
    set_chat_pinned,
    create_auth_token,
    authenticate_by_token,
    delete_auth_token,
    update_last_login,
    edit_message,
    create_room,
    get_user_rooms,
    get_room_for_user,
    get_room_member_ids,
    save_room_message,
    get_room_history,
    get_room_message_by_id,
    get_room_members,
    add_room_members,
    leave_room,
    delete_room,
    mark_room_as_read,
    get_room_unread_count,
    edit_room_message,
    get_login_block_status,
    register_failed_login_attempt,
    reset_login_attempts
)


SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000


# Словарь онлайн-пользователей:
# user_id -> {
#     "socket": client_socket,
#     "username": username,
#     "role": role
# }
online_users = {}

# Блокировка нужна, потому что с online_users работают разные потоки
online_users_lock = threading.Lock()


def convert_datetime(value):
    """
    Преобразует datetime в строку.
    JSON не умеет напрямую отправлять datetime из MySQL.
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    return value


def prepare_for_json(obj):
    """
    Рекурсивно подготавливает данные к отправке в JSON.
    Преобразует datetime внутри словарей и списков.
    """
    if isinstance(obj, list):
        return [prepare_for_json(item) for item in obj]

    if isinstance(obj, dict):
        return {
            key: prepare_for_json(value)
            for key, value in obj.items()
        }

    return convert_datetime(obj)


def add_online_user(user_id, username, role, client_socket):
    """
    Добавляет пользователя в список онлайн.
    """
    with online_users_lock:
        online_users[user_id] = {
            "socket": client_socket,
            "username": username,
            "role": role
        }


def remove_online_user(user_id):
    """
    Удаляет пользователя из списка онлайн.
    """
    with online_users_lock:
        if user_id in online_users:
            del online_users[user_id]


def get_online_user_ids():
    """
    Возвращает множество ID пользователей, которые сейчас онлайн.
    """
    with online_users_lock:
        return set(online_users.keys())


def get_online_socket(user_id):
    """
    Возвращает сокет онлайн-пользователя по ID.
    Если пользователь офлайн — возвращает None.
    """
    with online_users_lock:
        user_info = online_users.get(user_id)

        if user_info is None:
            return None

        return user_info["socket"]


def build_users_with_status():
    """
    Получает всех пользователей из БД и добавляет им статус online/offline.
    """
    users = get_all_users()
    online_ids = get_online_user_ids()

    result = []

    for user in users:
        user_id = user["id"]

        result.append({
            "id": user_id,
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"],
            "role": user["role"],
            "user_status": user.get("user_status", "available"),
            "department": user.get("department") or "",
            "position": user.get("position") or "",
            "last_login_at": convert_datetime(user.get("last_login_at")),
            "created_at": convert_datetime(user.get("created_at")),
            "online": user_id in online_ids
        })

    return result


def broadcast_users_status():
    """
    Отправляет всем онлайн-клиентам обновлённый список пользователей.
    Например, когда кто-то вошёл или вышел.
    """
    users = build_users_with_status()

    response = make_ok(
        message="Список пользователей обновлён",
        data={
            "event": "users_status",
            "users": users
        }
    )

    with online_users_lock:
        sockets = [
            user_info["socket"]
            for user_info in online_users.values()
        ]

    for client_socket in sockets:
        send_json(client_socket, response)



def build_recent_chats_with_status(user_id):
    """
    Получает недавние личные и групповые чаты.
    """
    chats = get_recent_chats(user_id)
    rooms = get_user_rooms(user_id)
    online_ids = get_online_user_ids()

    result = []

    for chat in chats:
        chat_user_id = chat["id"]

        result.append({
            "chat_type": "user",
            "id": chat_user_id,
            "username": chat["username"],
            "display_name": chat.get("display_name") or chat["username"],
            "role": chat["role"],
            "user_status": chat.get("user_status", "available"),
            "department": chat.get("department") or "",
            "position": chat.get("position") or "",
            "last_login_at": convert_datetime(chat.get("last_login_at")),
            "last_message": chat.get("last_message", ""),
            "last_message_time": convert_datetime(chat.get("last_message_time")),
            "unread_count": int(chat.get("unread_count", 0)),
            "pinned": bool(chat.get("pinned", 0)),
            "online": chat_user_id in online_ids
        })

    for room in rooms:
        result.append({
            "chat_type": "room",
            "id": room["id"],
            "room_id": room["id"],
            "name": room.get("name", "Группа"),
            "display_name": room.get("name", "Группа"),
            "last_message": room.get("last_message") or "Групповой чат создан",
            "last_message_time": convert_datetime(room.get("last_message_time") or room.get("created_at")),
            "unread_count": get_room_unread_count(user_id, room["id"]),
            "pinned": False,
            "online": False
        })

    result.sort(key=lambda item: str(item.get("last_message_time") or ""), reverse=True)
    result.sort(key=lambda item: bool(item.get("pinned", False)), reverse=True)

    return result


def send_recent_chats_update(user_id):
    """
    Отправляет конкретному онлайн-пользователю обновлённый список недавних чатов.
    """
    user_socket = get_online_socket(user_id)

    if user_socket is None:
        return

    chats = build_recent_chats_with_status(user_id)
    total_unread = get_total_unread_count(user_id)

    send_json(
        user_socket,
        make_ok(
            message="Недавние чаты обновлены",
            data={
                "event": "recent_chats",
                "chats": chats,
                "total_unread": total_unread
            }
        )
    )


def require_login(current_user):
    """
    Проверяет, авторизован ли клиент.
    """
    if current_user is None:
        return False

    return True


def require_admin(current_user):
    """
    Проверяет, является ли пользователь администратором.
    """
    if current_user is None:
        return False

    return current_user.get("role") == "admin"



def handle_register(client_socket, request):
    """
    Обрабатывает команду register.
    Создаёт обычного пользователя с ролью user.
    """
    username = request.get("username", "").strip()
    password = request.get("password", "")

    success, message = register_user(username, password)

    if not success:
        send_json(client_socket, make_error(message))
        return

    send_json(
        client_socket,
        make_ok(
            message=message,
            data=None
        )
    )

    # Обновляем список пользователей у всех клиентов.
    broadcast_users_status()


def handle_login(client_socket, request):
    """
    Обрабатывает команду login.
    """
    username = request.get("username", "").strip()
    password = request.get("password", "")

    if not username or not password:
        send_json(client_socket, make_error("Введите логин и пароль"))
        return None

    is_blocked, block_message = get_login_block_status(username)

    if is_blocked:
        send_json(client_socket, make_error(block_message or "Слишком много попыток входа. Повторите позже."))
        return None

    user = authenticate_user(username, password)

    if user is None:
        just_blocked, block_message = register_failed_login_attempt(username)

        if just_blocked:
            send_json(client_socket, make_error(block_message or "Слишком много попыток входа. Повторите позже."))
        else:
            send_json(client_socket, make_error("Неверный логин или пароль"))

        return None

    reset_login_attempts(username)

    user_id = user["id"]
    update_last_login(user_id)

    add_online_user(
        user_id=user_id,
        username=user["username"],
        role=user["role"],
        client_socket=client_socket
    )

    response_data = {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"],
            "role": user["role"],
            "user_status": user.get("user_status", "available"),
            "department": user.get("department") or "",
            "position": user.get("position") or "",
            "last_login_at": convert_datetime(user.get("last_login_at"))
        },
        "users": build_users_with_status(),
        "recent_chats": build_recent_chats_with_status(user_id),
        "total_unread": get_total_unread_count(user_id),
        "auth_token": create_auth_token(user_id)
    }

    send_json(
        client_socket,
        make_ok(
            message="Авторизация успешна",
            data=response_data
        )
    )

    print(f"Пользователь вошёл: {user['username']}")

    broadcast_users_status()

    return user



def handle_login_token(client_socket, request):
    """
    Обрабатывает автоматический вход по токену.
    """
    token = request.get("token", "")

    if not token:
        send_json(client_socket, make_error("Токен отсутствует"))
        return None

    user = authenticate_by_token(token)

    if user is None:
        send_json(client_socket, make_error("Сохранённый вход недействителен"))
        return None

    user_id = user["id"]
    update_last_login(user_id)

    add_online_user(
        user_id=user_id,
        username=user["username"],
        role=user["role"],
        client_socket=client_socket
    )

    response_data = {
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user.get("display_name") or user["username"],
            "role": user["role"],
            "user_status": user.get("user_status", "available"),
            "department": user.get("department") or "",
            "position": user.get("position") or "",
            "last_login_at": convert_datetime(user.get("last_login_at"))
        },
        "users": build_users_with_status(),
        "recent_chats": build_recent_chats_with_status(user_id),
        "total_unread": get_total_unread_count(user_id),
        "auth_token": token
    }

    send_json(
        client_socket,
        make_ok(
            message="Автоматический вход выполнен",
            data=response_data
        )
    )

    print(f"Пользователь вошёл по токену: {user['username']}")

    broadcast_users_status()

    return user


def handle_logout_token(client_socket, request):
    """
    Удаляет токен автоматического входа.
    """
    token = request.get("token", "")

    if not token:
        send_json(client_socket, make_ok("Токен отсутствует"))
        return

    success = delete_auth_token(token)

    if not success:
        send_json(client_socket, make_error("Не удалось удалить токен"))
        return

    send_json(client_socket, make_ok("Токен удалён"))


def send_room_update_to_members(room_id: int):
    """
    Обновляет список недавних чатов у всех участников группы.
    """
    for member_id in get_room_member_ids(room_id):
        send_recent_chats_update(member_id)


def handle_create_room(client_socket, current_user, request):
    """
    Создаёт групповой чат.
    """
    name = request.get("name", "").strip()
    member_ids = request.get("member_ids", [])

    if not name:
        send_json(client_socket, make_error("Введите название группы"))
        return

    if not isinstance(member_ids, list):
        member_ids = []

    room = create_room(name, current_user["id"], member_ids)

    if room is None:
        send_json(client_socket, make_error("Не удалось создать группу"))
        return

    room = prepare_for_json(room)

    send_json(
        client_socket,
        make_ok(
            message="Группа создана",
            data={"room": room}
        )
    )

    send_room_update_to_members(room["id"])


def handle_get_room_history(client_socket, current_user, request):
    """
    Возвращает историю группового чата.
    """
    room_id = request.get("room_id")

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID группы"))
        return

    messages = get_room_history(current_user["id"], room_id)
    messages = prepare_for_json(messages)

    send_json(
        client_socket,
        make_ok(
            message="История группы получена",
            data={"messages": messages}
        )
    )


def handle_send_room_message(client_socket, current_user, request):
    """
    Отправляет сообщение в групповой чат.
    """
    room_id = request.get("room_id")
    content = request.get("content", "").strip()
    reply_to_message_id = request.get("reply_to_message_id")

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID группы"))
        return

    if reply_to_message_id is not None:
        try:
            reply_to_message_id = int(reply_to_message_id)
        except (TypeError, ValueError):
            reply_to_message_id = None

    if not content:
        send_json(client_socket, make_error("Введите текст сообщения"))
        return

    message_id = save_room_message(room_id, current_user["id"], content, reply_to_message_id)

    if not message_id:
        send_json(client_socket, make_error("Не удалось отправить сообщение в группу"))
        return

    message = get_room_message_by_id(current_user["id"], message_id)
    message = prepare_for_json(message)

    send_json(
        client_socket,
        make_ok(
            message="Сообщение отправлено в группу",
            data={
                "event": "room_message_sent",
                "message": message
            }
        )
    )

    for member_id in get_room_member_ids(room_id):
        if member_id == current_user["id"]:
            continue

        member_socket = get_online_socket(member_id)

        if member_socket is not None:
            send_json(
                member_socket,
                make_ok(
                    message="Новое сообщение в группе",
                    data={
                        "event": "new_room_message",
                        "message": message
                    }
                )
            )

    send_room_update_to_members(room_id)



def handle_edit_room_message(client_socket, current_user, request):
    """
    Редактирует своё сообщение в групповом чате.
    """
    message_id = request.get("message_id")
    new_content = request.get("new_content", "").strip()

    if not message_id or not new_content:
        send_json(client_socket, make_error("Не указано сообщение или новый текст"))
        return

    try:
        message_id = int(message_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID сообщения"))
        return

    updated_message = edit_room_message(message_id, current_user["id"], new_content)

    if updated_message is None:
        send_json(client_socket, make_error("Сообщение группы можно редактировать только в течение 48 часов"))
        return

    updated_message = prepare_for_json(updated_message)
    room_id = updated_message.get("room_id")

    send_json(
        client_socket,
        make_ok(
            message="Сообщение группы изменено",
            data={
                "event": "room_message_edited",
                "message": updated_message
            }
        )
    )

    for member_id in get_room_member_ids(room_id):
        if member_id == current_user["id"]:
            continue

        member_socket = get_online_socket(member_id)

        if member_socket is not None:
            send_json(
                member_socket,
                make_ok(
                    message="Сообщение группы изменено",
                    data={
                        "event": "edited_room_message",
                        "message": updated_message
                    }
                )
            )

    send_room_update_to_members(room_id)


def build_room_members_with_status(current_user_id: int, room_id: int):
    """
    Возвращает участников группы с online/offline.
    """
    members = get_room_members(current_user_id, room_id)
    online_ids = get_online_user_ids()
    result = []

    for member in members:
        member_id = member["id"]
        result.append({
            "id": member_id,
            "username": member["username"],
            "display_name": member.get("display_name") or member["username"],
            "role": member.get("role", "user"),
            "user_status": member.get("user_status", "available"),
            "department": member.get("department") or "",
            "position": member.get("position") or "",
            "last_login_at": convert_datetime(member.get("last_login_at")),
            "joined_at": convert_datetime(member.get("joined_at")),
            "online": member_id in online_ids
        })

    return result


def handle_get_room_members(client_socket, current_user, request):
    """
    Возвращает список участников группы.
    """
    room_id = request.get("room_id")

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID группы"))
        return

    members = build_room_members_with_status(current_user["id"], room_id)

    if not members:
        send_json(client_socket, make_error("Вы не состоите в этой группе или участников нет"))
        return

    send_json(
        client_socket,
        make_ok(
            message="Участники группы получены",
            data={"members": members}
        )
    )


def handle_add_room_members(client_socket, current_user, request):
    """
    Добавляет участников в существующую группу.
    """
    room_id = request.get("room_id")
    member_ids = request.get("member_ids", [])

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID группы"))
        return

    if not isinstance(member_ids, list):
        member_ids = []

    old_member_ids = get_room_member_ids(room_id)
    success = add_room_members(room_id, current_user["id"], member_ids)

    if not success:
        send_json(client_socket, make_error("Не удалось добавить участников"))
        return

    new_member_ids = get_room_member_ids(room_id)
    members = build_room_members_with_status(current_user["id"], room_id)

    send_json(
        client_socket,
        make_ok(
            message="Участники добавлены",
            data={"members": members}
        )
    )

    for member_id in set(old_member_ids + new_member_ids):
        send_recent_chats_update(member_id)


def handle_leave_room(client_socket, current_user, request):
    """
    Выход текущего пользователя из группы.
    """
    room_id = request.get("room_id")

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID группы"))
        return

    old_member_ids = get_room_member_ids(room_id)
    success = leave_room(room_id, current_user["id"])

    if not success:
        send_json(client_socket, make_error("Не удалось выйти из группы"))
        return

    send_json(client_socket, make_ok("Вы вышли из группы"))

    for member_id in old_member_ids:
        send_recent_chats_update(member_id)


def handle_delete_room(client_socket, current_user, request):
    """
    Удаляет группу. Доступно создателю группы или администратору.
    """
    room_id = request.get("room_id")

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID группы"))
        return

    old_member_ids = get_room_member_ids(room_id)
    success = delete_room(
        room_id=room_id,
        requester_id=current_user["id"],
        is_admin=current_user.get("role") == "admin"
    )

    if not success:
        send_json(client_socket, make_error("Удалить группу может только создатель или администратор"))
        return

    send_json(client_socket, make_ok("Группа удалена"))

    for member_id in old_member_ids:
        send_recent_chats_update(member_id)



def handle_mark_room_read(client_socket, current_user, request):
    """
    Помечает групповой чат как прочитанный.
    """
    room_id = request.get("room_id")

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID группы"))
        return

    success = mark_room_as_read(current_user["id"], room_id)

    if not success:
        send_json(client_socket, make_error("Не удалось пометить группу как прочитанную"))
        return

    chats = build_recent_chats_with_status(current_user["id"])
    total_unread = get_total_unread_count(current_user["id"])

    send_json(
        client_socket,
        make_ok(
            message="Группа помечена как прочитанная",
            data={
                "chats": chats,
                "total_unread": total_unread
            }
        )
    )


def handle_room_typing(client_socket, current_user, request):
    """
    Пересылает статус печати в групповом чате.
    """
    room_id = request.get("room_id")
    is_typing = request.get("is_typing", False)

    try:
        room_id = int(room_id)
    except (TypeError, ValueError):
        send_json(client_socket, make_error("Некорректный ID группы"))
        return

    room = get_room_for_user(current_user["id"], room_id)

    if room is None:
        send_json(client_socket, make_error("Вы не состоите в этой группе"))
        return

    typing_data = {
        "event": "room_typing",
        "room_id": room_id,
        "sender_id": current_user["id"],
        "sender_username": current_user.get("display_name") or current_user["username"],
        "is_typing": bool(is_typing)
    }

    for member_id in get_room_member_ids(room_id):
        if member_id == current_user["id"]:
            continue

        member_socket = get_online_socket(member_id)

        if member_socket is not None:
            send_json(
                member_socket,
                make_ok(
                    message="Статус набора текста в группе",
                    data=typing_data
                )
            )

    send_json(
        client_socket,
        make_ok(
            message="Статус печати группы отправлен",
            data={"event": "room_typing_sent"}
        )
    )


def handle_get_users(client_socket):
    """
    Обрабатывает команду get_users.
    """
    users = build_users_with_status()

    send_json(
        client_socket,
        make_ok(
            message="Список пользователей получен",
            data={
                "users": users
            }
        )
    )


def handle_send_message(client_socket, current_user, request):
    """
    Обрабатывает команду send_message.
    Сохраняет сообщение и отправляет его получателю, если он онлайн.
    """
    receiver_id = request.get("receiver_id")
    content = request.get("content", "").strip()
    reply_to_message_id = request.get("reply_to_message_id")

    if not receiver_id or not content:
        send_json(client_socket, make_error("Не указан получатель или текст сообщения"))
        return

    try:
        receiver_id = int(receiver_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID получателя"))
        return

    if reply_to_message_id is not None:
        try:
            reply_to_message_id = int(reply_to_message_id)
        except ValueError:
            reply_to_message_id = None

    sender_id = current_user["id"]

    if sender_id == receiver_id:
        send_json(client_socket, make_error("Нельзя отправить сообщение самому себе"))
        return

    message_id = save_message(sender_id, receiver_id, content, reply_to_message_id)

    if not message_id:
        send_json(client_socket, make_error("Не удалось сохранить сообщение"))
        return

    # Загружаем сохранённое сообщение из истории, чтобы получить reply/edited поля.
    history = get_message_history(sender_id, receiver_id)
    message_data = None

    for item in history:
        if item.get("id") == message_id:
            message_data = prepare_for_json(item)
            break

    if message_data is None:
        message_data = {
            "id": message_id,
            "sender_id": sender_id,
            "sender_username": current_user.get("display_name") or current_user["username"],
            "receiver_id": receiver_id,
            "content": content,
            "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "edited_at": None,
            "reply_to_message_id": reply_to_message_id,
            "reply_content": None,
            "reply_sender_username": None
        }

    # Подтверждаем отправителю
    send_json(
        client_socket,
        make_ok(
            message="Сообщение отправлено",
            data={
                "event": "message_sent",
                "message": message_data
            }
        )
    )

    # Если получатель онлайн — отправляем ему уведомление
    receiver_socket = get_online_socket(receiver_id)

    if receiver_socket is not None:
        send_json(
            receiver_socket,
            make_ok(
                message="Новое сообщение",
                data={
                    "event": "new_message",
                    "message": message_data
                }
            )
        )

    # Обновляем список недавних чатов у отправителя и получателя.
    send_recent_chats_update(sender_id)
    send_recent_chats_update(receiver_id)



def handle_typing(client_socket, current_user, request):
    """
    Обрабатывает команду typing.
    Пересылает получателю статус, что пользователь печатает сообщение.
    """
    receiver_id = request.get("receiver_id")
    is_typing = request.get("is_typing", False)

    if not receiver_id:
        send_json(client_socket, make_error("Не указан получатель для статуса печати"))
        return

    try:
        receiver_id = int(receiver_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID получателя"))
        return

    sender_id = current_user["id"]

    if sender_id == receiver_id:
        send_json(client_socket, make_ok("Статус печати проигнорирован"))
        return

    typing_data = {
        "event": "typing",
        "sender_id": sender_id,
        "sender_username": current_user.get("display_name") or current_user["username"],
        "receiver_id": receiver_id,
        "is_typing": bool(is_typing)
    }

    receiver_socket = get_online_socket(receiver_id)

    if receiver_socket is not None:
        send_json(
            receiver_socket,
            make_ok(
                message="Статус набора текста",
                data=typing_data
            )
        )

    send_json(
        client_socket,
        make_ok(
            message="Статус печати отправлен",
            data={
                "event": "typing_sent"
            }
        )
    )


def handle_get_history(client_socket, current_user, request):
    """
    Обрабатывает команду get_history.
    Загружает историю между текущим пользователем и выбранным собеседником.
    """
    other_user_id = request.get("user_id")

    if not other_user_id:
        send_json(client_socket, make_error("Не указан ID пользователя"))
        return

    try:
        other_user_id = int(other_user_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID пользователя"))
        return

    messages = get_message_history(
        current_user["id"],
        other_user_id
    )

    messages = prepare_for_json(messages)

    send_json(
        client_socket,
        make_ok(
            message="История переписки получена",
            data={
                "messages": messages
            }
        )
    )



def handle_get_recent_chats(client_socket, current_user):
    """
    Обрабатывает команду get_recent_chats.
    Возвращает недавние диалоги текущего пользователя.
    """
    chats = build_recent_chats_with_status(current_user["id"])
    total_unread = get_total_unread_count(current_user["id"])

    send_json(
        client_socket,
        make_ok(
            message="Недавние чаты получены",
            data={
                "chats": chats,
                "total_unread": total_unread
            }
        )
    )


def handle_mark_chat_read(client_socket, current_user, request):
    """
    Обрабатывает команду mark_chat_read.
    Помечает входящие сообщения выбранного чата как прочитанные.
    """
    other_user_id = request.get("user_id")

    if not other_user_id:
        send_json(client_socket, make_error("Не указан ID пользователя"))
        return

    try:
        other_user_id = int(other_user_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID пользователя"))
        return

    success = mark_chat_as_read(current_user["id"], other_user_id)

    if not success:
        send_json(client_socket, make_error("Не удалось пометить сообщения как прочитанные"))
        return

    chats = build_recent_chats_with_status(current_user["id"])
    total_unread = get_total_unread_count(current_user["id"])

    send_json(
        client_socket,
        make_ok(
            message="Сообщения помечены как прочитанные",
            data={
                "chats": chats,
                "total_unread": total_unread
            }
        )
    )



def handle_update_profile(client_socket, current_user, request):
    """
    Обрабатывает команду update_profile.
    Меняет отображаемое имя и статус пользователя.
    """
    display_name = request.get("display_name", "").strip()
    user_status = request.get("user_status", "available")
    department = request.get("department", "").strip()
    position = request.get("position", "").strip()

    success, message = update_user_profile(
        current_user["id"],
        display_name,
        user_status,
        department,
        position
    )

    if not success:
        send_json(client_socket, make_error(message))
        return

    current_user["display_name"] = display_name
    current_user["user_status"] = user_status
    current_user["department"] = department
    current_user["position"] = position

    send_json(
        client_socket,
        make_ok(
            message=message,
            data={
                "user": {
                    "id": current_user["id"],
                    "username": current_user["username"],
                    "display_name": display_name,
                    "role": current_user["role"],
                    "user_status": user_status,
                    "department": department,
                    "position": position
                }
            }
        )
    )

    broadcast_users_status()
    send_recent_chats_update(current_user["id"])


def handle_change_password(client_socket, current_user, request):
    """
    Обрабатывает команду change_password.
    Меняет пароль текущего пользователя.
    """
    old_password = request.get("old_password", "")
    new_password = request.get("new_password", "")

    success, message = change_user_password(
        current_user["id"],
        old_password,
        new_password
    )

    if not success:
        send_json(client_socket, make_error(message))
        return

    send_json(client_socket, make_ok(message))


def handle_hide_chat(client_socket, current_user, request):
    """
    Обрабатывает команду hide_chat.
    Скрывает чат только у текущего пользователя.
    """
    other_user_id = request.get("user_id")

    if not other_user_id:
        send_json(client_socket, make_error("Не указан ID пользователя"))
        return

    try:
        other_user_id = int(other_user_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID пользователя"))
        return

    success = hide_chat(current_user["id"], other_user_id)

    if not success:
        send_json(client_socket, make_error("Не удалось скрыть чат"))
        return

    chats = build_recent_chats_with_status(current_user["id"])
    total_unread = get_total_unread_count(current_user["id"])

    send_json(
        client_socket,
        make_ok(
            message="Чат скрыт",
            data={
                "chats": chats,
                "total_unread": total_unread
            }
        )
    )


def handle_pin_chat(client_socket, current_user, request):
    """
    Обрабатывает команду pin_chat.
    Закрепляет или открепляет чат у текущего пользователя.
    """
    other_user_id = request.get("user_id")
    pinned = request.get("pinned", True)

    if not other_user_id:
        send_json(client_socket, make_error("Не указан ID пользователя"))
        return

    try:
        other_user_id = int(other_user_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID пользователя"))
        return

    success = set_chat_pinned(current_user["id"], other_user_id, bool(pinned))

    if not success:
        send_json(client_socket, make_error("Не удалось изменить закрепление чата"))
        return

    chats = build_recent_chats_with_status(current_user["id"])
    total_unread = get_total_unread_count(current_user["id"])

    send_json(
        client_socket,
        make_ok(
            message="Закрепление чата изменено",
            data={
                "chats": chats,
                "total_unread": total_unread
            }
        )
    )



def handle_edit_message(client_socket, current_user, request):
    """
    Обрабатывает команду edit_message.
    Разрешает редактировать только свои сообщения.
    """
    message_id = request.get("message_id")
    new_content = request.get("new_content", "").strip()

    if not message_id or not new_content:
        send_json(client_socket, make_error("Не указано сообщение или новый текст"))
        return

    try:
        message_id = int(message_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID сообщения"))
        return

    updated_message = edit_message(message_id, current_user["id"], new_content)

    if updated_message is None:
        send_json(client_socket, make_error("Сообщение можно редактировать только в течение 48 часов"))
        return

    updated_message = prepare_for_json(updated_message)

    send_json(
        client_socket,
        make_ok(
            message="Сообщение изменено",
            data={
                "event": "message_edited",
                "message": updated_message
            }
        )
    )

    receiver_id = updated_message.get("receiver_id")
    receiver_socket = get_online_socket(receiver_id)

    if receiver_socket is not None:
        send_json(
            receiver_socket,
            make_ok(
                message="Сообщение изменено",
                data={
                    "event": "edited_message",
                    "message": updated_message
                }
            )
        )

    send_recent_chats_update(current_user["id"])
    send_recent_chats_update(receiver_id)


def handle_search_history(client_socket, current_user, request):
    """
    Обрабатывает команду search_history.
    Ищет текст в истории переписки.
    """
    other_user_id = request.get("user_id")
    search_text = request.get("search_text", "").strip()

    if not other_user_id or not search_text:
        send_json(client_socket, make_error("Не указан пользователь или текст поиска"))
        return

    try:
        other_user_id = int(other_user_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID пользователя"))
        return

    messages = search_message_history(
        current_user["id"],
        other_user_id,
        search_text
    )

    messages = prepare_for_json(messages)

    send_json(
        client_socket,
        make_ok(
            message="Поиск выполнен",
            data={
                "messages": messages
            }
        )
    )


def handle_add_user(client_socket, current_user, request):
    """
    Обрабатывает команду add_user.
    Доступно только администратору.
    """
    if not require_admin(current_user):
        send_json(client_socket, make_error("Недостаточно прав"))
        return

    username = request.get("username", "").strip()
    password = request.get("password", "")
    role = request.get("role", "user")

    if not username or not password:
        send_json(client_socket, make_error("Введите логин и пароль нового пользователя"))
        return

    if role not in ("admin", "user"):
        send_json(client_socket, make_error("Некорректная роль пользователя"))
        return

    success = add_user(username, password, role)

    if not success:
        send_json(client_socket, make_error("Не удалось добавить пользователя"))
        return

    send_json(client_socket, make_ok("Пользователь добавлен"))
    broadcast_users_status()


def handle_delete_user(client_socket, current_user, request):
    """
    Обрабатывает команду delete_user.
    Доступно только администратору.
    """
    if not require_admin(current_user):
        send_json(client_socket, make_error("Недостаточно прав"))
        return

    user_id = request.get("user_id")

    if not user_id:
        send_json(client_socket, make_error("Не указан ID пользователя"))
        return

    try:
        user_id = int(user_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID пользователя"))
        return

    if user_id == current_user["id"]:
        send_json(client_socket, make_error("Нельзя удалить самого себя"))
        return

    success = delete_user(user_id)

    if not success:
        send_json(client_socket, make_error("Не удалось удалить пользователя"))
        return

    send_json(client_socket, make_ok("Пользователь удалён"))
    broadcast_users_status()


def handle_reset_password(client_socket, current_user, request):
    """
    Обрабатывает команду reset_password.
    Доступно только администратору.
    """
    if not require_admin(current_user):
        send_json(client_socket, make_error("Недостаточно прав"))
        return

    user_id = request.get("user_id")
    new_password = request.get("new_password", "")

    if not user_id or not new_password:
        send_json(client_socket, make_error("Не указан пользователь или новый пароль"))
        return

    try:
        user_id = int(user_id)
    except ValueError:
        send_json(client_socket, make_error("Некорректный ID пользователя"))
        return

    success = reset_user_password(user_id, new_password)

    if not success:
        send_json(client_socket, make_error("Не удалось сбросить пароль"))
        return

    send_json(client_socket, make_ok("Пароль сброшен"))


def handle_client(client_socket, client_address):
    """
    Главная функция потока клиента.
    Каждый подключившийся клиент обслуживается в отдельном потоке.
    """
    print(f"Клиент подключился: {client_address}")

    current_user = None

    try:
        while True:
            request = recv_json(client_socket)

            if request is None:
                print(f"Клиент отключился: {client_address}")
                break

            action = request.get("action")

            if not action:
                send_json(client_socket, make_error("Не указано действие"))
                continue

            if action == "register":
                handle_register(client_socket, request)
                continue

            if action == "login":
                current_user = handle_login(client_socket, request)
                continue

            if action == "login_token":
                current_user = handle_login_token(client_socket, request)
                continue

            if action == "logout_token":
                handle_logout_token(client_socket, request)
                continue

            if action == "logout":
                send_json(client_socket, make_ok("Выход выполнен"))
                break

            if not require_login(current_user):
                send_json(client_socket, make_error("Сначала выполните вход"))
                continue

            if action == "get_users":
                handle_get_users(client_socket)

            elif action == "get_recent_chats":
                handle_get_recent_chats(client_socket, current_user)

            elif action == "create_room":
                handle_create_room(client_socket, current_user, request)

            elif action == "get_room_history":
                handle_get_room_history(client_socket, current_user, request)

            elif action == "send_room_message":
                handle_send_room_message(client_socket, current_user, request)

            elif action == "edit_room_message":
                handle_edit_room_message(client_socket, current_user, request)

            elif action == "mark_room_read":
                handle_mark_room_read(client_socket, current_user, request)

            elif action == "room_typing":
                handle_room_typing(client_socket, current_user, request)

            elif action == "get_room_members":
                handle_get_room_members(client_socket, current_user, request)

            elif action == "add_room_members":
                handle_add_room_members(client_socket, current_user, request)

            elif action == "leave_room":
                handle_leave_room(client_socket, current_user, request)

            elif action == "delete_room":
                handle_delete_room(client_socket, current_user, request)

            elif action == "mark_chat_read":
                handle_mark_chat_read(client_socket, current_user, request)

            elif action == "update_profile":
                handle_update_profile(client_socket, current_user, request)

            elif action == "change_password":
                handle_change_password(client_socket, current_user, request)

            elif action == "hide_chat":
                handle_hide_chat(client_socket, current_user, request)

            elif action == "pin_chat":
                handle_pin_chat(client_socket, current_user, request)

            elif action == "send_message":
                handle_send_message(client_socket, current_user, request)

            elif action == "edit_message":
                handle_edit_message(client_socket, current_user, request)

            elif action == "typing":
                handle_typing(client_socket, current_user, request)

            elif action == "get_history":
                handle_get_history(client_socket, current_user, request)

            elif action == "search_history":
                handle_search_history(client_socket, current_user, request)

            elif action == "add_user":
                handle_add_user(client_socket, current_user, request)

            elif action == "delete_user":
                handle_delete_user(client_socket, current_user, request)

            elif action == "reset_password":
                handle_reset_password(client_socket, current_user, request)

            else:
                send_json(client_socket, make_error(f"Неизвестное действие: {action}"))

    except ConnectionResetError:
        print(f"Соединение сброшено клиентом: {client_address}")

    except Exception as error:
        print("Неожиданная ошибка при работе с клиентом:")
        print(error)

    finally:
        if current_user is not None:
            remove_online_user(current_user["id"])
            print(f"Пользователь вышел: {current_user['username']}")
            broadcast_users_status()

        try:
            client_socket.close()
        except OSError:
            pass


def start_server():
    """
    Запускает TCP-сервер CatCorp.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # Позволяет быстро перезапускать сервер после остановки
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((SERVER_HOST, SERVER_PORT))
        server_socket.listen()

        print("Сервер CatCorp запущен")
        print(f"Адрес: {SERVER_HOST}")
        print(f"Порт: {SERVER_PORT}")
        print("Ожидание подключений...")

        while True:
            client_socket, client_address = server_socket.accept()

            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address),
                daemon=True
            )

            client_thread.start()

    except OSError as error:
        print("Ошибка запуска сервера:")
        print(error)

    finally:
        server_socket.close()


if __name__ == "__main__":
    start_server()