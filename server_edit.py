import socket
import select
from datetime import datetime
import threading
import time


class User:
    name = ""

    def __init__(self, client_socket, socket_list_index) -> None:
        self.client_socket = client_socket
        self.logged_in = False
        self.last_seen = datetime.now()
        self.socket_list_index = socket_list_index


class Server:
    HEADER_LENGTH = 10
    IP = "127.0.0.1"
    PORT = 1234
    CLIENTS = {}  # key = socket, val = User object
    SOCKETS_LIST = []
    USER_REGISTRY = {}  # key = username, value = password
    PEERS = {}
    MESSAGE_TYPES_IN = {
        "Register": 1,
        "Login": 2,
        "Search": 3,
        "KeepAlive": 4,
        "Logout": 5,
    }
    MESSAGE_TYPES_OUT = {
        "RegistrationDenied": 1,
        "LoginFailed": 2,
        "LoginSuccess": 3,
    }

    def __init__(self) -> None:
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.IP, self.PORT))
        self.server_socket.listen()
        self.SOCKETS_LIST.append(self.server_socket)
        print(f'Listening for connections on {self.IP}:{self.PORT}...')

    def send_message(self, user: User, msg_data_header: str, msg_data: str):
        msg_header = f"{len(msg_data):<{self.HEADER_LENGTH}}".encode('utf-8')
        total_msg = msg_header + msg_data_header.encode("utf-8") + msg_data.encode("utf-8")
        user.client_socket.send(total_msg)

    def receive_message(self, client_socket):
        try:
            message_header = client_socket.recv(self.HEADER_LENGTH)
            if not len(message_header):
                return False
            message_length = int(message_header.decode('utf-8').strip())
            message = client_socket.recv(message_length).decode('utf-8')
            return {'header': message_length, 'data': message}
        except:
            return False

    def createUserObject(self, client_socket, socket_list_index):
        user = User(client_socket, socket_list_index)
        return user

    def registerUser(self, user: User, username, password) -> None:
        try:
            # if user doesn't exist throws an error
            _ = self.USER_REGISTRY[username]
            # if user already exists, send message to notify client
            self.send_message(
                user, "RegistrationDenied")
        except:
            self.USER_REGISTRY[username] = password  # add user to registry
            # self.send_message(
            #     user, self.MESSAGE_TYPES_OUT["LoginSuccess"], None)
            user.last_seen = datetime.now()
            user.name = username
            user.logged_in = True

    def loginUser(self, user: User, username, password) -> None:
        try:
            # if user doesn't exist throws an error
            pw_of_user = self.USER_REGISTRY[username]
            if pw_of_user != password:
                self.send_message(user, self.MESSAGE_TYPES_OUT["LoginFailed"])
            else:
                self.send_message(user, self.MESSAGE_TYPES_OUT["LoginSuccess"])
                user.last_seen = datetime.now()
                user.name = username
                user.logged_in = True
        except:
            self.send_message(
                user, self.MESSAGE_TYPES_OUT["LoginFailed"])

    def establish_connection(self):
        client_socket, client_address = self.server_socket.accept()
        message = self.receive_message(client_socket)

        if message is False:
            return False, None

        self.SOCKETS_LIST.append(client_socket)
        socket_list_index = len(self.SOCKETS_LIST) - 1
        user = self.createUserObject(client_socket, socket_list_index)
        self.CLIENTS[client_socket] = user
        print('Accepted new connection from {}:{}'.format(
            *client_address))

        # if message['header'] == self.MESSAGE_TYPES_IN["Register"]:
        username, password = message['data'].split('*')
        if username not in self.USER_REGISTRY:
            t = threading.Thread(target=self.registerUser,
                                    args=[user, username, password])
            t.start()

            # elif message['header'] == self.MESSAGE_TYPES_IN["Login"]:
            #     username, password = message['data'].split('*')
            #     t = threading.Thread(target=self.loginUser,
            #                          args=[user, username, password])
            #     t.start()

            # t.join()
            # server_message = "SERVER".encode('utf-8')
            # server_message_header = f"{len(server_message):<{self.HEADER_LENGTH}}".encode('utf-8')
            # client_socket.send(server_message_header + server_message)      
            server_message = "Login Succesfull".encode('utf-8')
            server_message_header =  f"{len(server_message):<{self.HEADER_LENGTH}}".encode('utf-8')
            client_socket.send(server_message_header + server_message)
            print(f"{username} succesfully logged in!")
        else:
            server_message = "Choose different username".encode('utf-8')
            server_message_header =  f"{len(server_message):<{self.HEADER_LENGTH}}".encode('utf-8')
            client_socket.send(server_message_header + server_message)
            print(f"{username} unsuccesfull attempt!")
            return False, client_socket
        return True, client_socket

    def search(self, user: User, msg_data: str):
        user.client_socket.send()   # TODO

    def remove_client(self, user: User):
        user.client_socket.close()
        self.SOCKETS_LIST.remove(user.socket_list_index)
        del self.CLIENTS[user.client_socket]

    def find_dead_clients(self, interval: int, max_wait: int):
        # Need to check with UDP Socket TODO
        while True:
            current_time = datetime.now()
            for client in self.CLIENTS:
                if (current_time - self.CLIENTS[client].last_seen).total_seconds > max_wait:
                    self.remove_client(client)
            time.sleep(interval)

    def check_for_messages(self):
        read_sockets, _, exception_sockets = select.select(
            self.SOCKETS_LIST, [], self.SOCKETS_LIST)
        for notified_socket in read_sockets:
            if notified_socket == self.server_socket:
                is_connected, client_ = self.establish_connection()  # TODO
                if is_connected:continue
            else:
                message = self.receive_message(notified_socket)
                message = message['data'].split()
                if message[0] == 'search':
                    for k, v in self.CLIENTS.items():
                        if v.name == message[1]:
                            if k not in self.PEERS:
                                server_message = "SERVER".encode('utf-8')
                                server_message_header = f"{len(server_message):<{self.HEADER_LENGTH}}".encode('utf-8')
                                notified_socket.send(server_message_header + server_message)                

                                message = f"{v.name} is online and available.".encode('utf-8')
                                message_header =  f"{len(message):<{self.HEADER_LENGTH}}".encode('utf-8')
                                notified_socket.send(message_header + message)    
                            else:
                                server_message = "SERVER".encode('utf-8')
                                server_message_header = f"{len(server_message):<{self.HEADER_LENGTH}}".encode('utf-8')
                                notified_socket.send(server_message_header + server_message)                

                                message = f"{v.name} is busy.".encode('utf-8')
                                message_header =  f"{len(message):<{self.HEADER_LENGTH}}".encode('utf-8')
                                notified_socket.send(message_header + message)   
                elif  message[0] == 'chat_request':
                    for k, v in self.CLIENTS.items():
                        if v.name == message[1]:
                            server_message = "SERVER".encode('utf-8')
                            server_message_header = f"{len(server_message):<{self.HEADER_LENGTH}}".encode('utf-8')
                            k.send(server_message_header + server_message)

                            message = f"{self.CLIENTS[notified_socket].name} send you chat request.".encode('utf-8')
                            message_header =  f"{len(message):<{self.HEADER_LENGTH}}".encode('utf-8')
                            k.send(message_header + message)  
                elif message[0] == 'ok':
                    for k, v in self.CLIENTS.items():
                        if v.name == message[1]:
                            server_message = "SERVER".encode('utf-8')
                            server_message_header = f"{len(server_message):<{self.HEADER_LENGTH}}".encode('utf-8')
                            notified_socket.send(server_message_header + server_message)

                            message = f"{self.CLIENTS[notified_socket].name} accepted your chat request.".encode('utf-8')
                            message_header =  f"{len(message):<{self.HEADER_LENGTH}}".encode('utf-8')
                            notified_socket.send(message_header + message)    
                            self.PEERS[k] = notified_socket
                            self.PEERS[notified_socket] = k                

        for notified_socket in exception_sockets:
            self.remove_client(self.CLIENTS[notified_socket])


if __name__ == '__main__':
    server = Server()
    find_dead_client_thread = threading.Thread(
        target=server.find_dead_clients, args=[30, 200])
    find_dead_client_thread.start()
    while True:
        server.check_for_messages()
