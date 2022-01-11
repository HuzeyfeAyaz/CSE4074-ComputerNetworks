import socket
import select
from datetime import datetime
import threading
import time
import asyncio
import errno
import sys
import logging

class User:
    name = None
    contact_port = None

    def __init__(self, client_socket, client_ip, client_port, socket_list_index) -> None:
        self.client_socket = client_socket
        self.client_ip = client_ip
        self.client_port = client_port
        self.logged_in = False
        self.last_seen = datetime.now()
        self.socket_list_index = socket_list_index


class Server:
    HEADER_LENGTH = 10
    IP = "127.0.0.1"
    PORT = 9000
    UDP_PORT = 9001
    CLIENTS = {}  # key = socket, val = User object
    SOCKETS_LIST = []
    USER_REGISTRY = {}  # key = username, value = password
    MESSAGE_TYPES_IN = {
        "Register": "1",
        "Login": "2",
        "Search": "3",
        "KeepAlive": "4",
        "Logout": "0",
    }
    MESSAGE_TYPES_OUT = {
        "RegistrationDenied": "1",
        "LoginFailed": "2",
        "LoginSuccess": "3",
        "SearchResult": "5",
    }

    def __init__(self) -> None:
        logging.basicConfig(filename="server.log",
                            format="%(asctime)s — %(name)s — %(levelname)s — %(funcName)s:%(lineno)d — %(message)s",
                            filemode='w',
                            encoding="utf-8")
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.IP, self.PORT))
        self.server_socket.listen()
        self.SOCKETS_LIST.append(self.server_socket)
        print(f'Listening for connections on {self.IP}:{self.PORT}...')
        self.logger.info(f'Listening for connections on {self.IP}:{self.PORT}...')

        self.server_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_udp_socket.bind((self.IP, self.UDP_PORT))
        print(f'Checking for keep alive signals on {self.IP}:{self.UDP_PORT}...')
        self.logger.info(f'Checking for keep alive signals on {self.IP}:{self.UDP_PORT}...')


    def send_message(self, user: User, msg_data_header: str, msg_data_string=''):
        message_string = f"{msg_data_header + msg_data_string}".encode("utf-8")
        message_header = f"{len(message_string):<{self.HEADER_LENGTH}}".encode(
            'utf-8')
        user.client_socket.send(message_header + message_string)
        print(f"{msg_data_header + ' - ' + msg_data_string}")

    def receive_message(self, client_socket):
        try:
            message_header = client_socket.recv(self.HEADER_LENGTH)
            if not len(message_header):
                return False
            message_length = int(message_header.decode('utf-8').strip())
            message = client_socket.recv(message_length).decode('utf-8')
            print("Message type: {}, message content: {}".format(
                message[0], message[1:]))
            return {'header': message[0], 'data': message[1:]}
        except:
            return False

    def createUserObject(self, client_socket, client_ip, client_port, client_socket_list_index):
        user = User(client_socket, client_ip,
                    client_port, client_socket_list_index)
        self.logger.info(f"Created user IP:{client_ip}, PORT:{client_port}.")
        return user

    def registerUser(self, user: User, username, password, port: str) -> None:
        try:
            # if user doesn't exist throws an error
            _ = self.USER_REGISTRY[username]
            # if user already exists, send message to notify client
            self.send_message(
                user, self.MESSAGE_TYPES_OUT["RegistrationDenied"])
            self.logger.info(f"User {user.name}  registeration denied.")
            
        except:
            self.USER_REGISTRY[username] = password  # add user to registry
            self.send_message(
                user, self.MESSAGE_TYPES_OUT["LoginSuccess"])

            user.last_seen = datetime.now()
            user.name = username
            user.logged_in = True
            user.contact_port = port
            print(f"Registered user: {user.name}")
            self.logger.info(f"User {user.name} successfully registered.")


    def loginUser(self, user: User, username, password, port: str) -> None:
        try:
            # if user doesn't exist throws an error
            pw_of_user = self.USER_REGISTRY[username]
            if pw_of_user != password:
                self.send_message(user, self.MESSAGE_TYPES_OUT["LoginFailed"])
                self.logger.info(f"Login failed. Wrong password {username}.")

            else:
                self.send_message(user, self.MESSAGE_TYPES_OUT["LoginSuccess"])
                self.logger.info(f"Succesfull login. User:{username}.")
                user.last_seen = datetime.now()
                user.name = username
                user.logged_in = True
                user.contact_port = port
        except:
            self.send_message(user, self.MESSAGE_TYPES_OUT["LoginFailed"])
            self.logger.warning(f"Login failed {username}.")


    def establish_connection(self):
        client_socket, client_address = self.server_socket.accept()
        message = self.receive_message(client_socket)

        if message is False:
            return False, None

        self.SOCKETS_LIST.append(client_socket)
        socket_list_index = len(self.SOCKETS_LIST) - 1
        user = self.createUserObject(
            client_socket, client_address[0], client_address[1], socket_list_index)
        self.CLIENTS[client_socket] = user
        print('Accepted new connection from {}:{}'.format(*client_address))
        self.logger.info('Accepted new connection from {}:{}'.format(*client_address))

        # print(message, message["header"])
        if message['header'] == self.MESSAGE_TYPES_IN["Register"]:
            username, password, port = message['data'].split('*')
            print(f"Trying to register user: {username}")
            self.logger.info(f"Registration attempt. Username:{username}. Creting new thread to handle user requests.")
            t = threading.Thread(target=self.registerUser,
                                 args=[user, username, password, port])
            t.start()

        elif message['header'] == self.MESSAGE_TYPES_IN["Login"]:
            username, password, port = message['data'].split('*')
            t = threading.Thread(target=self.loginUser,
                                 args=[user, username, password, port])
            t.start()
        return True, client_socket

    def search(self, user: User, msg_data: str):
        searched_users = msg_data.split('*')
        searched_users_results = []
        for su in searched_users:
            if self.USER_REGISTRY.get(su, False):
                found = False
                for us_obj in self.CLIENTS.values():
                    if us_obj.name == su and us_obj.logged_in:
                        searched_users_results.append(f"{us_obj.name} {us_obj.client_ip} {us_obj.contact_port}")
                        found = True
                if not found:
                    searched_users_results.append(f"{su} is offline")
            else:
                searched_users_results.append(f"{su} does not exist")
        msg_data = "*".join(searched_users_results)
        self.send_message(
            user, self.MESSAGE_TYPES_OUT["SearchResult"], msg_data)   # TODO

    def remove_client(self, client_socket: socket):
        self.logger.info(f"Removing client {self.CLIENTS[client_socket].name}.")
        self.SOCKETS_LIST.remove(client_socket)
        del self.CLIENTS[client_socket]
        client_socket.close()

    def update_last_seen(self, username):
        for client in self.CLIENTS.values():
            if username == client.name:
                client.last_seen = datetime.now()
    
    def check_for_keep_alive(self):
        while True:
            data, _addr = self.server_udp_socket.recvfrom(1024)
            data = data.decode("utf-8")
            # print(data)
            self.logger.info(f"Received HELLO from {data} from UDP Port.")
            updater_thread = threading.Thread(target=self.update_last_seen, args=[data])
            updater_thread.start()
    
    def find_dead_clients(self, interval: int, max_wait: int):
        while True:
            current_time = datetime.now()
            found = False
            for client in self.CLIENTS.copy().values():
                if (current_time - client.last_seen).seconds > max_wait:
                    self.remove_client(client.client_socket)
                    found = True
            if found:
                print("Removed dead client")
            else:
                print("No dead clients found")
            
            time.sleep(interval)

    def check_for_messages(self):
        try: 
            read_sockets, _, exception_sockets = select.select(
                self.SOCKETS_LIST, [], self.SOCKETS_LIST)
            for notified_socket in read_sockets:
                if notified_socket == self.server_socket:
                    is_connected, client_ = self.establish_connection()  # TODO

                else:
                    message = self.receive_message(notified_socket)
                    print(
                        f"Message type: {message['header']}, message content: {message['data']}")
                    if message['header'] == self.MESSAGE_TYPES_IN["Search"]:
                        self.search(self.CLIENTS[notified_socket], message['data'])
                    elif message['header'] == self.MESSAGE_TYPES_IN["Logout"]:
                        self.remove_client(notified_socket)

            for notified_socket in exception_sockets:
                self.remove_client(notified_socket)
                
        except IOError as e:
                # This is normal on non blocking connections - when there are no incoming data error is going to be raised
                # Some operating systems will indicate that using AGAIN, and some using WOULDBLOCK error code
                # We are going to check for both - if one of them - that's expected, means no incoming data, continue as normal
                # If we got different error code - something happened
                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                    print('Reading error: {}'.format(str(e)))
                    sys.exit()

        except Exception as e:
            # Any other exception - something happened, exit
            print('Reading error: {}'.format(str(e)))
            sys.exit()
            


if __name__ == '__main__':
    server = Server()
    find_dead_client_thread = threading.Thread(target=server.find_dead_clients, args=[5, 10])
    find_dead_client_thread.start()
    keep_alive_checker_thread = threading.Thread(target=server.check_for_keep_alive)
    keep_alive_checker_thread.start()
    while True:
        server.check_for_messages()
