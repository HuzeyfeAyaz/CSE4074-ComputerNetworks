import asyncio
import select
import socket
import errno
import sys
import threading
import time
import asyncio
import logging
import random


class PeerUser:
    def __init__(self, ip, port, p_socket, socket_list_index, username):
        self.ip = ip
        self.port = port
        self.p_socket = p_socket
        self.socket_list_index = socket_list_index
        self.username = username
        self.chatting_with = False


class Client:
    HEADER_LENGTH = 10
    SERVER_IP = "127.0.0.1"
    SERVER_PORT = 9000
    SERVER_UDP_PORT = 9001
    SOCKETS_LIST = []  # 0 = server, 1 = client_server
    PEERS = {}  # key = socket, value = PeerUser
    MESSAGE_TYPES_OUT = {
        "Logout": "0",      # to server & other client
        "Register": "1",    # to server
        "Login": "2",       # to server
        "Search": "3",      # to server
        "KeepAlive": "4",   # to server
        "Message": "6",     # to other client
        "ChatRequest": "7",  # to other client
        "ChatAccept": "8",  # to other client
        "ChatReject": "9",  # to other client
    }
    MESSAGE_TYPES_IN = {
        "Logout": "0",              # from other client
        "RegistrationDenied": "1",  # from server
        "LoginFailed": "2",         # from server
        "LoginSuccess": "3",        # from server
        "SearchResult": "5",        # from server
        "Message": "6",             # from other client
        "ChatRequest": "7",         # from other client
        "ChatAccept": "8",          # from other client
        "ChatReject": "9",          # from other client
    }
    MY_PORT = None
    client_server_socket = None
    username = None
    password = None
    available = True    # status is user is currently chatting
    peers_waiting_for_chat_accept = []  # peer socket objects waiting for answer
    registered_users = []
    quit_process = False

    # -------------------------<< region INIT START >>-------------------------
    def __init__(self):
        while True:
            try:
                self.MY_PORT = str(
                    10000 + int(input("Please enter your port number (int): ")))
                break
            except:
                continue
        logging.basicConfig(filename=f"client_{self.MY_PORT}.log",
                            format="%(asctime)s — %(name)s — %(levelname)s — %(funcName)s:%(lineno)d — %(message)s",
                            filemode='w',
                            encoding="utf-8")
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.establish_connection("Server", self.SERVER_IP, self.SERVER_PORT)
        self.server_udp_socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM)

    def build_client_server(self):
        self.client_server_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.client_server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.client_server_socket.bind((self.SERVER_IP, int(self.MY_PORT)))
        self.client_server_socket.listen()
        self.SOCKETS_LIST.append(self.client_server_socket)
        self.logger.info(
            f'Listening for connections on {self.SERVER_IP}:{self.MY_PORT}...')
    # -------------------------<< region INIT END >>-------------------------

    # -------------------------<< region MessageIO START >>-------------------------
    def send_message(self, user: PeerUser, msg_data_header: str, msg_data_string=""):
        message_string = f"{msg_data_header + msg_data_string}".encode("utf-8")
        message_header = f"{len(message_string):<{self.HEADER_LENGTH}}".encode(
            'utf-8')
        user.p_socket.send(message_header + message_string)

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
    # -------------------------<< region MessageIO END >>-------------------------

    # -------------------------<< region EstablishConnection START >>-------------------------
    def establish_peer_connection(self):
        peer_socket, peer_address = self.client_server_socket.accept()
        self.logger.info(
            'Accepted new connection from {}:{}'.format(*peer_address))
        self.SOCKETS_LIST.append(peer_socket)
        socket_list_index = len(self.SOCKETS_LIST) - 1
        peer_user = PeerUser(
            peer_address[0], peer_address[1], peer_socket, socket_list_index, "")
        self.PEERS[peer_socket] = peer_user
        return True, peer_socket

    def establish_connection(self, Name, IP, PORT):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((IP, int(PORT)))
        client_socket.setblocking(False)
        self.SOCKETS_LIST.append(client_socket)
        self.PEERS[client_socket] = PeerUser(
            IP, PORT, client_socket, len(self.SOCKETS_LIST)-1, Name)
        self.logger.info(f"Established connection to {Name} on {IP}:{PORT}")
    # -------------------------<< region EstablishConnection END >>-------------------------

    # -------------------------<< region SendToServer START >>-------------------------
    def login(self) -> bool:
        username, password = self.ask_for_credentials()
        msg_data = username + "*" + password + "*" + self.MY_PORT
        self.send_message(
            self.PEERS[self.SOCKETS_LIST[0]], self.MESSAGE_TYPES_OUT["Login"], msg_data)

        self.SOCKETS_LIST[0].setblocking(1)
        answer = self.receive_message(self.SOCKETS_LIST[0])
        self.SOCKETS_LIST[0].setblocking(False)

        if answer:
            if answer['header'] == self.MESSAGE_TYPES_IN["LoginSuccess"]:
                self.username, self.password = username, password
                self.logger.info("Login was successful!")
                return True
            else:
                print("Login Failed - Username or Password is wrong!")
                self.logger.warning(
                    "Login Failed - Username or Password is wrong!")
                return False
        else:
            print("Login Failed - Error while receiving answer from server!")
            self.logger.error(
                "Login Failed - Error while receiving answer from server!")
            return False

    def register(self) -> bool:
        username, password = self.ask_for_credentials()
        msg_data = username + "*" + password + "*" + self.MY_PORT
        self.send_message(
            self.PEERS[self.SOCKETS_LIST[0]], self.MESSAGE_TYPES_OUT["Register"], msg_data)

        self.SOCKETS_LIST[0].setblocking(1)
        answer = self.receive_message(self.SOCKETS_LIST[0])
        self.SOCKETS_LIST[0].setblocking(False)

        if answer:
            if answer['header'] == self.MESSAGE_TYPES_IN["LoginSuccess"]:
                self.username, self.password = username, password
                self.logger.info("Register was successful!")
                return True
            elif answer['header'] == self.MESSAGE_TYPES_IN["RegistrationDenied"]:
                print("Registration Failed - Username already taken!")
                self.logger.warning(
                    "Registration Failed - Username already taken!")
                return False
        else:
            print("Registration Failed - Error while receiving answer from server!")
            self.logger.error(
                "Registration Failed - Error while receiving answer from server!")
            return False

    def search(self, users: list):
        msg_data = '*'.join(users)
        self.send_message(
            self.PEERS[self.SOCKETS_LIST[0]], self.MESSAGE_TYPES_OUT["Search"], msg_data)
        self.logger.info(f"Sent serach request for user/s: {' '.join(users)}")

    def send_keep_alive(self):
        while not self.quit_process:
            time.sleep(6)
            data = self.username.encode("utf-8")
            self.server_udp_socket.sendto(
                data, (self.SERVER_IP, self.SERVER_UDP_PORT))
            self.logger.info("Sent keep alive ping to server!")

    # -------------------------<< region SendToServer END >>-------------------------

    # -------------------------<< region SendToClient START >>-------------------------
    def send_chat_request(self):
        request_message = self.username
        if len(self.registered_users) == 1:  # peer to peer chat
            self.establish_connection(
                self.registered_users[0][0], self.registered_users[0][1], self.registered_users[0][2])
            for peer in self.PEERS.values():
                if peer.username == self.registered_users[0][0]:
                    self.send_message(
                        peer, self.MESSAGE_TYPES_OUT["ChatRequest"], request_message)
                    self.logger.info(f"Sent chat request to {peer.username}")

        else:  # group chat TODO
            # for user in registered_users:
            pass

    def send_chat_accept(self):
        for peer_socket in self.peers_waiting_for_chat_accept:
            self.PEERS[peer_socket].chatting_with = True
            self.send_message(
                self.PEERS[peer_socket], self.MESSAGE_TYPES_OUT["ChatAccept"])
            self.logger.info(
                f"Accepted chat request from {self.PEERS[peer_socket].username}")

    def send_chat_reject(self):
        for peer_socket in self.peers_waiting_for_chat_accept:
            self.send_message(
                self.PEERS[peer_socket], self.MESSAGE_TYPES_OUT["ChatReject"], "rejected the chat request")
            self.logger.info(
                f"Rejected chat request from {self.PEERS[peer_socket].username}")

            # self.remove_peer(peer_socket)
        self.available = True

        self.peers_waiting_for_chat_accept = []

    def send_busy(self):
        for peer_socket in self.peers_waiting_for_chat_accept:
            self.send_message(
                self.PEERS[peer_socket], self.MESSAGE_TYPES_OUT["ChatReject"], "is already in a chat!")
            self.logger.info(
                f"Automatically rejected chat request from {self.PEERS[peer_socket].username}")

    def send_chat_message(self, my_input: str):
        for peer in self.PEERS.values():
            if peer.chatting_with and peer.username != "Server":
                self.send_message(
                    peer, self.MESSAGE_TYPES_OUT["Message"], my_input)
                self.logger.info(
                    f"Sent a chat message to {peer.username}, content: {my_input}")

    def logout(self):
        self.SOCKETS_LIST[1].close()
        self.SOCKETS_LIST.pop(1)
        server_socket_obj = self.PEERS[self.SOCKETS_LIST[0]]
        for soc in self.SOCKETS_LIST:
            self.send_message(
                self.PEERS[soc], self.MESSAGE_TYPES_OUT["Logout"])
            soc.close()
        self.SOCKETS_LIST = [server_socket_obj.p_socket]
        self.PEERS = {server_socket_obj.p_socket: server_socket_obj, }
        self.logger.info("Logging out")
    # -------------------------<< region SendToClient END >>-------------------------

    # -------------------------<< region Utils START >>-------------------------
    def ask_for_credentials(self):
        _username = input("Username: ")
        _password = input("Password: ")
        return _username, _password

    def remove_peer(self, peer_socket):
        self.SOCKETS_LIST.remove(peer_socket)
        del self.PEERS[peer_socket]
        try:
            self.peers_waiting_for_chat_accept.remove(peer_socket)
        except:
            pass
        peer_socket.shutdown(socket.SHUT_RDWR)
        peer_socket.close()
    # -------------------------<< region Utils END >>-------------------------

    # -------------------------<< region CheckForMessages START >>-------------------------
    def check_for_messages(self):
        while True:
            if self.quit_process:
                break
            try:
                read_sockets, _, exception_sockets = select.select(
                    self.SOCKETS_LIST, [], self.SOCKETS_LIST)
                for notified_socket in read_sockets:
                    if notified_socket == self.client_server_socket:
                        is_connected, client_ = self.establish_peer_connection()  # TODO

                    else:
                        message = self.receive_message(notified_socket)
                        if message != False:
                            if message['header'] == self.MESSAGE_TYPES_IN["SearchResult"]:
                                user_stats = message['data'].split(
                                    '*')  # [ip port]
                                for ix, user_stat in enumerate(user_stats):
                                    if user_stat.endswith("exist") or user_stat.endswith("offline"):
                                        print(user_stat)
                                        self.logger.info(user_stat)
                                    else:
                                        user_datail = user_stat.split(
                                            ' ')  # [[username, ip, port]]
                                        self.registered_users.append(
                                            [user_datail[0], user_datail[1], user_datail[2]])
                                        print(
                                            f"{user_datail[0]} is available at destination: {user_datail[1] + ':' + user_datail[2]}")
                                        self.logger.info(
                                            f"{user_datail[0]} is available at destination: {user_datail[1] + ':' + user_datail[2]}")
                                        self.send_chat_request()
                            elif message['header'] == self.MESSAGE_TYPES_IN["Message"]:
                                print(
                                    f"-->{self.PEERS[notified_socket].username} > {message['data']}")
                                self.logger.info(
                                    f"-->{self.PEERS[notified_socket].username} > {message['data']}")

                            # the other client sent a request
                            elif message['header'] == self.MESSAGE_TYPES_IN["ChatRequest"]:
                                if not self.available:
                                    self.send_busy()
                                else:
                                    username = message["data"]
                                    self.PEERS[notified_socket].username = username
                                    self.peers_waiting_for_chat_accept.append(
                                        notified_socket)
                                    print(
                                        f"{self.PEERS[notified_socket].username} sent a chat request")
                                    self.logger.info(
                                        f"{self.PEERS[notified_socket].username} sent a chat request")

                            # the other client accepted the chat request
                            elif message['header'] == self.MESSAGE_TYPES_IN["ChatAccept"]:
                                self.available = False
                                self.peers_waiting_for_chat_accept = []
                                self.PEERS[notified_socket].chatting_with = True
                                print(
                                    f"{self.PEERS[notified_socket].username} accepted the chat request")
                                self.logger.info(
                                    f"{self.PEERS[notified_socket].username} accepted the chat request")

                            elif message['header'] == self.MESSAGE_TYPES_IN["ChatReject"]:
                                print(
                                    f"{self.PEERS[notified_socket].username} {message['data']}")
                                self.logger.info(
                                    f"{self.PEERS[notified_socket].username} {message['data']}")
                                self.remove_peer(notified_socket)
                                self.available = True
                                self.registered_users.pop()
                                # self.SOCKETS_LIST.remove(notified_socket)
                            elif message['header'] == self.MESSAGE_TYPES_IN["Logout"]:
                                print(
                                    f"{self.PEERS[notified_socket].username} logged out")
                                self.logger.info(
                                    f"{self.PEERS[notified_socket].username} logged out")
                                # TODO
                                self.remove_peer(notified_socket)
                                self.available = True
                                # self.SOCKETS_LIST.remove(notified_socket)

                        else:
                            print('Closed connection from: {}'.format(
                                self.PEERS[notified_socket].username))
                            self.logger.info('Closed connection from: {}'.format(
                                self.PEERS[notified_socket].username))

                            self.remove_peer(notified_socket)
                            self.available = True

                    continue

                for notified_socket in exception_sockets:
                    self.remove_peer(notified_socket)

            except IOError as e:
                # This is normal on non blocking connections - when there are no incoming data error is going to be raised
                # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
                # We are going to check for both - if one of them - that's expected, means no incoming data, continue as normal
                # If we got different error code - something happened
                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                    self.logger.error('Reading error: {}'.format(str(e)))
                    sys.exit()

            except Exception as e:
                # Any other exception - something happened, exit
                self.logger.error('Reading error: {}'.format(str(e)))
                sys.exit()
    # -------------------------<< region CheckForMessages END >>-------------------------

    # -------------------------<< region MAIN START >>-------------------------
    def main_process(self):

        logged_in = False
        while not logged_in:
            l_or_r = input("Do you wanna login (L) or register (R)?: ")
            if l_or_r.lower() == "l":
                logged_in = self.login()
            elif l_or_r.lower() == "r":
                logged_in = self.register()

        self.build_client_server()
        msg_checker_thread = threading.Thread(target=self.check_for_messages)
        msg_checker_thread.start()
        keep_alive_thread = threading.Thread(target=self.send_keep_alive)
        keep_alive_thread.start()
        while not self.quit_process:
            my_input = input(f'{self.username} > ')
            if (my_input.lower() == "quit") or (my_input.lower() == "logout"):
                self.quit_process = True
                self.logout()
                sys.exit(0)
            elif my_input.startswith("message"):
                users = my_input.strip().split(' ')[1:]
                self.search(users)

            if self.available and len(self.peers_waiting_for_chat_accept) > 0:
                if my_input == ("ok"):
                    self.available = False
                    self.send_chat_accept()
                elif my_input.startswith("reject"):
                    self.available = True
                    self.send_chat_reject()
            elif not self.available:
                self.send_chat_message(my_input)
    # -------------------------<< region MAIN END >>-------------------------


if __name__ == '__main__':
    client = Client()
    client.main_process()
