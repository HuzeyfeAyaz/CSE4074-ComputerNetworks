import socket
import errno
import sys
import select
import threading
import time


class PeerUser:
    def __init__(self, username, ip, port, p_socket, socket_list_index):
        self.username = username
        self.ip = ip
        self.port = port
        self.p_socket = p_socket
        self.socket_list_index = socket_list_index


class Client:
    HEADER_LENGTH = 10
    IP = "127.0.0.1"
    SERVER_PORT = 1234
    CLIENT_SERVER_SOCKET = None
    SOCKETS_LIST = []
    PEERS = {}  # key = socket, value = PeerUser
    MESSAGE_TYPES_OUT = {
        "Register": "1",    # to server
        "Login": "2",       # to server
        "Search": "3",      # to server
        "KeepAlive": "4",   # to server
        "Logout": "5",      # to server
        "ChatRequest": "6",  # to other client
        "Message": "7",     # to other client
    }
    MESSAGE_TYPES_IN = {
        "RegistrationDenied": "1",  # from server
        "LoginFailed": "2",         # from server
        "LoginSuccess": "3",        # from server
        "SearchResult": "4",        # from server
        "ChatRequest": "6",         # from other client
        "Message": "7",             # from other client
    }
    new_messages = []

    username = None
    password = None

    # ------------------------- << INIT START >> -------------------------
    def __init__(self):
        self.MY_PORT = str(10000 +
                           int(input("Please enter your port number (0-9): ")))
        self.establish_connection("Server", self.IP, self.SERVER_PORT)

    def build_client_server(self):
        self.CLIENT_SERVER_SOCKET = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.CLIENT_SERVER_SOCKET.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.CLIENT_SERVER_SOCKET.bind((self.IP, int(self.MY_PORT)))
        self.CLIENT_SERVER_SOCKET.listen()
        self.SOCKETS_LIST.append(self.CLIENT_SERVER_SOCKET)
        print(f'Listening for connections on {self.IP}:{self.MY_PORT}...')
    # ------------------------- << INIT END >> -------------------------

    # ------------------------- << Message IO START >> -------------------------
    def send_message(self, user: PeerUser, msg_data_header: str, msg_data_string: str):
        message_string = f"{msg_data_header + msg_data_string}".encode("utf-8")
        message_header = f"{len(message_string):<{self.HEADER_LENGTH}}".encode(
            'utf-8')
        self.SOCKETS_LIST[user.socket_list_index].send(
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
    # ------------------------- << Message IO END >> -------------------------

    # ------------------------- << Establish Connection START >> -------------------------
    def establish_connection(self, Name, IP, PORT):  # establishes
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((IP, int(PORT)))
        client_socket.setblocking(False)
        self.SOCKETS_LIST.append(client_socket)
        self.PEERS[client_socket] = PeerUser(
            Name, IP, PORT, client_socket, len(self.SOCKETS_LIST)-1)

    def establish_peer_connection(self):
        peer_socket, peer_address = self.CLIENT_SERVER_SOCKET.accept()
        message = self.receive_message(peer_socket)

        if message is False:
            return False, None

        self.SOCKETS_LIST.append(peer_socket)
        socket_list_index = len(self.SOCKETS_LIST) - 1
        self.PEERS[peer_socket] = PeerUser(
            "", peer_address[0], peer_address[1], peer_socket, socket_list_index)
        print('Accepted new connection from {}:{}'.format(
            *peer_address))
        return True, peer_socket

    # ------------------------- << Establish Connection END >> -------------------------

    def ask_for_credentials(self):
        _username = input("Username: ")
        _password = input("Password: ")
        return _username, _password

    def logout(self):   # TODO
        pass

    # ------------------------- << Login & Register START >> -------------------------
    def login(self) -> bool:
        username, password = self.ask_for_credentials()
        # TODO

    def register(self) -> bool:
        username, password = self.ask_for_credentials()
        msg_data = username + "*" + password + "*" + self.MY_PORT
        self.send_message(
            self.PEERS[self.SOCKETS_LIST[0]], self.MESSAGE_TYPES_OUT["Register"], msg_data)

        self.SOCKETS_LIST[0].setblocking(1)
        answer = self.receive_message(self.SOCKETS_LIST[0])
        self.SOCKETS_LIST[0].setblocking(False)

        if answer:
            print(f"Message type = {answer['header']}")
            self.username, self.password = username, password
            return True
    # ------------------------- << Login & Register END >> -------------------------

    # ------------------------- << Search & Chat Request START >> -------------------------
    def search(self, users: list):
        msg_data = '*'.join(users)
        self.send_message(self.PEERS[self.SOCKETS_LIST[0]],
                          self.MESSAGE_TYPES_OUT["Search"], msg_data)

        self.SOCKETS_LIST[0].setblocking(1)
        answer = self.receive_message(self.SOCKETS_LIST[0])
        self.SOCKETS_LIST[0].setblocking(False)

        user_stats = answer['data'].split('*')
        registerd_users = []
        for ix, user_stat in enumerate(user_stats):
            if user_stat.endswith("exist"):
                print(user_stat)
            else:
                # [[username, ip, port]]
                registerd_users.append([users[ix], *(user_stat.split(' '))])
                print(
                    f"{users[ix]} is available at destination: {':'.join(user_stat.split(' '))}")

        return registerd_users

    def send_chat_request(self, users: list):
        registered_users = self.search(users)
        request_msg = f"{self.username} sent a chat request"
        if len(registered_users) == 1:  # peer to peer
            self.establish_connection(
                registered_users[0][0], registered_users[0][1], registered_users[0][2])
            self.send_message(self.PEERS[self.SOCKETS_LIST[-1]],
                              self.MESSAGE_TYPES_OUT["ChatRequest"], request_msg)
    # ------------------------- << Search & Chat Request END >> -------------------------

    # ------------------------- << Main Functionality START >> -------------------------
    def check_for_messages(self):
        while True:
            read_sockets, _, exception_sockets = select.select(
                self.SOCKETS_LIST, [], self.SOCKETS_LIST)
            for notified_socket in read_sockets:
                if notified_socket == self.CLIENT_SERVER_SOCKET:
                    is_connected, client_ = self.establish_peer_connection()  # TODO
                    self.CLIENT_SERVER_SOCKET.close()
                    break

                else:
                    message = self.receive_message(notified_socket)
                    if message != False:
                        self.new_messages.append(message['data'])
                        # print(
                        #     f"Message type: {message['header']}, message content: {message['data']}")
                        if message['header'] == self.MESSAGE_TYPES_IN["RegistrationDenied"]:
                            pass
                        elif message['header'] == self.MESSAGE_TYPES_IN["LoginFailed"]:
                            # self.remove_client(notified_socket)
                            pass
                        elif message['header'] == self.MESSAGE_TYPES_IN["LoginSuccess"]:
                            pass
                        elif message['header'] == self.MESSAGE_TYPES_IN["SearchResult"]:
                            pass
                        elif message['header'] == self.MESSAGE_TYPES_IN["ChatRequest"]:
                            pass
                        elif message['header'] == self.MESSAGE_TYPES_IN["Message"]:
                            # print(
                            #     f"{self.PEERS[notified_socket].username} > {message['data']}")
                            pass

            for notified_socket in exception_sockets:
                self.remove_client(self.CLIENTS[notified_socket])

    def main_process(self):
        logged_in = False
        quit_process = False
        while not logged_in:
            l_or_r = input("Do you wanna login (L) or register (R)?: ")
            if l_or_r.lower() == "l":
                logged_in = self.login()
            elif l_or_r.lower() == "r":
                logged_in = self.register()

        self.build_client_server()
        msg_checker_thread = threading.Thread(target=self.check_for_messages)
        msg_checker_thread.start()

        while not quit_process:
            if len(self.new_messages) > 0:
                print("You have new messages")
                for msg in self.new_messages:
                    print(msg)
            my_input = input(f'{self.username} > ')
            my_input_lower = my_input.lower()
            if my_input_lower == "quit" or my_input_lower == "logout":
                break
            if my_input.startswith("message"):
                users = my_input.strip().split(' ')[1:]
                self.send_chat_request(users)
    # ------------------------- << Main Functionality END >> -------------------------


if __name__ == '__main__':
    client = Client()
    client.main_process()
