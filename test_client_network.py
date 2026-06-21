# test_client_network.py
# Проверка клиентского сетевого модуля CatCorp без GUI

import time

from client_network import ClientNetwork


def on_new_message(message):
    """
    Callback для проверки получения новых сообщений.
    """
    print()
    print("Получено новое сообщение:")
    print(message)


def on_users_status(users):
    """
    Callback для проверки обновления статусов пользователей.
    """
    print()
    print("Обновился список пользователей:")
    for user in users:
        status = "online" if user.get("online") else "offline"
        print(f"- {user.get('username')} [{status}]")


def on_disconnected():
    """
    Callback при отключении от сервера.
    """
    print()
    print("Соединение с сервером закрыто")


def on_error(message):
    """
    Callback для ошибок.
    """
    print()
    print("Ошибка:")
    print(message)


def print_response(title, response):
    """
    Красивый вывод ответа сервера.
    """
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print(response)


def main():
    network = ClientNetwork()

    network.on_new_message = on_new_message
    network.on_users_status = on_users_status
    network.on_disconnected = on_disconnected
    network.on_error = on_error

    connected = network.connect()

    if not connected:
        print("Не удалось подключиться к серверу")
        return

    print("Подключение к серверу успешно")

    response = network.login("admin", "admin123")
    print_response("LOGIN", response)

    response = network.get_users()
    print_response("GET_USERS", response)

    response = network.get_history(2)
    print_response("GET_HISTORY admin <-> ivan", response)

    response = network.send_message(
        receiver_id=2,
        content="Сообщение отправлено через ClientNetwork"
    )
    print_response("SEND_MESSAGE", response)

    response = network.search_history(
        user_id=2,
        search_text="ClientNetwork"
    )
    print_response("SEARCH_HISTORY", response)

    time.sleep(1)

    network.disconnect()


if __name__ == "__main__":
    main()