import socket
import errno
import sys

from our_server_new_y import User


class PeerUser:
    def __init__(self, ip, port, socket_list_index):
        self.ip = ip
        self.port = port
        self.socket_list_index = socket_list_index


class Client:
    HEADER_LENGTH = 10
    SERVER_IP = "127.0.0.1"
    SERVER_PORT = 1234
    SOCKET_LIST = []
    PEERS = {}  # key = username, value = PeerUser
    MESSAGE_TYPES_OUT = {
        "Register": 1,
        "Login": 2,
        "Search": 3,
        "KeepAlive": 4,
        "Logout": 5,
        "Message": 6,
    }
    MESSAGE_TYPES_IN = {
        "RegistrationDenied": 1,
        "LoginFailed": 2,
        "LoginSuccess": 3,
        "MessageIn": 4,
    }

    username = None
    password = None

    def __init__(self):
        self.MY_PORT = 10000 + \
            int(input("Please enter your port number (0-9): "))
        self.establish_connection("Server", self.SERVER_IP, self.SERVER_PORT)

    def send_message(self, user: PeerUser, msg_data_header: int, msg_data_string: str):
        message_string = f"{str(msg_data_header) + msg_data_string}".encode("utf-8")
        message_header = f"{len(message_string):<{self.HEADER_LENGTH}}".encode(
            'utf-8')
        self.SOCKET_LIST[user.socket_list_index].send(
            message_header + message_string)

    def receive_message(self, client_socket):
        try:
            message_header = client_socket.recv(self.HEADER_LENGTH)
            if not len(message_header):
                return False
            message_length = int(message_header.decode('utf-8').strip())
            message = client_socket.recv(message_length).decode('utf-8')
            return {'header': message[0], 'data': message[1:]}
        except:
            return False

    def establish_connection(self, Name, IP, PORT):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((IP, PORT))
        client_socket.setblocking(False)
        self.SOCKET_LIST.append(client_socket)
        self.PEERS[Name] = PeerUser(IP, PORT, len(self.SOCKET_LIST)-1)

    def ask_for_credentials(self):
        _username = input("Username: ")
        _password = input("Password: ")
        return _username, _password

    def login(self) -> bool:
        username, password = self.ask_for_credentials()

    def register(self) -> bool:
        username, password = self.ask_for_credentials()
        msg_data = username + "*" + password
        self.send_message(
            self.PEERS["Server"], self.MESSAGE_TYPES_OUT["Register"], msg_data)

    def search(self, users: list):
        msg_data = '*'.join(users)
        self.send_message(self.PEERS["Server"],
                          self.MESSAGE_TYPES_OUT["Search"], msg_data)

    def send_chat_request(self, users: list):
        self.search()

    def main_process(self):
        logged_in = False
        quit_process = False
        while not logged_in:
            l_or_r = input("Do you wanna login (L) or register (R)?: ")
            if l_or_r.lower() == "l":
                logged_in = self.login()
            elif l_or_r.lower() == "r":
                logged_in = self.register()
        while not quit_process:
            my_input = input(f'{self.username} > ')
            if my_input == "QUIT":
                break
            if my_input.startswith() == "message":
                users = my_input[6:].split(' ')
                self.send_chat_request(users)


if __name__ == '__main__':
    client = Client()
    client.main_process()
