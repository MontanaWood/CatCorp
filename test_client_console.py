# test_client_console.py
# Временный консольный клиент для проверки TCP-сервера CatCorp

import socket

from common.protocol import send_json, recv_json


SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000


def print_response(title, response):
    """
    Красиво выводит ответ сервера в консоль.
    """
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)
    print(response)


def main():
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client_socket.connect((SERVER_HOST, SERVER_PORT))
        print("Подключение к серверу успешно")

        login_request = {
            "action": "login",
            "username": "admin",
            "password": "admin123"
        }

        send_json(client_socket, login_request)
        response = recv_json(client_socket)
        print_response("Ответ на login", response)

        users_request = {
            "action": "get_users"
        }

        send_json(client_socket, users_request)
        response = recv_json(client_socket)
        print_response("Ответ на get_users", response)

        history_request = {
            "action": "get_history",
            "user_id": 2
        }

        send_json(client_socket, history_request)
        response = recv_json(client_socket)
        print_response("Ответ на get_history с ivan", response)

        message_request = {
            "action": "send_message",
            "receiver_id": 2,
            "content": "Привет, Иван! Это тестовое сообщение от admin."
        }

        send_json(client_socket, message_request)
        response = recv_json(client_socket)
        print_response("Ответ на send_message", response)

        search_request = {
            "action": "search_history",
            "user_id": 2,
            "search_text": "тестовое"
        }

        send_json(client_socket, search_request)
        response = recv_json(client_socket)
        print_response("Ответ на search_history", response)

        logout_request = {
            "action": "logout"
        }

        send_json(client_socket, logout_request)
        response = recv_json(client_socket)
        print_response("Ответ на logout", response)

    except ConnectionRefusedError:
        print("Не удалось подключиться к серверу")
        print("Проверь, что server.py запущен")

    except OSError as error:
        print("Ошибка сети:")
        print(error)

    finally:
        client_socket.close()


if __name__ == "__main__":
    main()