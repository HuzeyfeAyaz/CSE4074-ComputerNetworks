import select
import socket
import errno
import sys
import threading
import time
class PeerUser:
    def __init__(self, ip, port, p_socket, socket_list_index, username):
        self.ip = ip
        self.port = port
        self.p_socket = p_socket
        self.socket_list_index = socket_list_index
        self.username = username


class Client:
    HEADER_LENGTH = 10
    SERVER_IP = "127.0.0.1"
    SERVER_PORT = 1234
    SOCKETS_LIST = [] # 0 = server, 1 = client_server
    PEERS = {}  # key = socket, value = PeerUser
    MESSAGE_TYPES_OUT = {
        "Register": "1",
        "Login": "2",
        "Search": "3",
        "KeepAlive": "4",
        "Logout": "5",
        "Message": "6",
    }
    MESSAGE_TYPES_IN = {
        "RegistrationDenied": "1",
        "LoginFailed": "2",
        "LoginSuccess": "3",
        "MessageIn": "4",
        "SearchResult": "5",
    }
    client_server_socket = None
    username = None
    password = None
    available = True

    def __init__(self):
        self.MY_PORT = str(10000 + \
            int(input("Please enter your port number (0-9): ")))
        self.establish_connection("Server", self.SERVER_IP, self.SERVER_PORT)

    def build_client_server(self):
        self.client_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.client_server_socket.bind((self.SERVER_IP, int(self.MY_PORT)))
        self.client_server_socket.listen()
        self.SOCKETS_LIST.append(self.client_server_socket)
        print(f'Listening for connections on {self.SERVER_IP}:{self.MY_PORT}...')

    def send_message(self, user: PeerUser, msg_data_header: str, msg_data_string=""):
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

    def establish_peer_connection(self):
        peer_socket, peer_address = self.client_server_socket.accept()
        message = self.receive_message(peer_socket)

        if message is False:
            return False, None

        self.SOCKETS_LIST.append(peer_socket)
        socket_list_index = len(self.SOCKETS_LIST) - 1
        peer_user = PeerUser(peer_address[0], peer_address[1], peer_socket, socket_list_index, "")
        self.PEERS[peer_socket] = peer_user

        print('Accepted new connection from {}:{}'.format(
            *peer_address))
        # print(message, message["header"])

        return True, peer_socket

    def establish_connection(self, Name, IP, PORT):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((IP, int(PORT)))
        client_socket.setblocking(False)
        self.SOCKETS_LIST.append(client_socket)
        self.PEERS[client_socket] = PeerUser(IP, PORT, client_socket, len(self.SOCKETS_LIST)-1, Name)

    def ask_for_credentials(self):
        _username = input("Username: ")
        _password = input("Password: ")
        return _username, _password

    def logout(self):
        for peer in self.PEERS:
            self.send_message(peer,
                          self.MESSAGE_TYPES_OUT["Logout"])
    
    def peer_logout(self):
        
        pass

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
            self.build_client_server()
            return True


    def search(self, users: list):
        msg_data = '*'.join(users)
        self.send_message(self.PEERS[self.SOCKETS_LIST[0]],
                          self.MESSAGE_TYPES_OUT["Search"], msg_data)
        
        self.SOCKETS_LIST[0].setblocking(1)
        answer = self.receive_message(self.SOCKETS_LIST[0])
        self.SOCKETS_LIST[0].setblocking(False)
        user_stats =  answer['data'].split('*') # [ip port]
        registered_users = []
        for ix, user_stat in enumerate(user_stats):
            if user_stat.endswith("exist"):
                print(user_stat)
            else:
                registered_users.append([users[ix], *(user_stat.split(' '))]) # [[username, ip, port]]
                print(f"{users[ix]} is available at destination: {':'.join(user_stat.split(' '))}")

        return registered_users

    def send_chat_request(self, users: list):
        registered_users = self.search(users)
        # self.search(users)

        request_message = f"{self.client_server_socket} sent a chat request".encode('utf-8')
        request_header = f"{len(request_message):<{self.HEADER_LENGTH}}".encode('utf-8')
        if len(registered_users) == 1:  # peer to peer chat
            print(registered_users[0][0],registered_users[0][1], registered_users[0][2]) 
            self.establish_connection(registered_users[0][0],registered_users[0][1], registered_users[0][2]) 
            self.SOCKETS_LIST[-1].send(request_header + request_message)

        else: # group chat TODO
            # for user in registered_users:
            pass
        
        




    def check_for_messages(self):
        while True:
            read_sockets, _, exception_sockets = select.select(
                self.SOCKETS_LIST, [], self.SOCKETS_LIST)
            for notified_socket in read_sockets:
                if notified_socket == self.client_server_socket:
                    is_connected, client_ = self.establish_peer_connection()  # TODO
                
                else:
                    message = self.receive_message(notified_socket)
                    print(f"Message type: {message['header']}, message content: {message['data']}")
                    if message['header'] == self.MESSAGE_TYPES_IN["SearchResult"]:
                        pass
                    elif message['header'] == self.MESSAGE_TYPES_IN["Logout"]:
                        # self.remove_client(notified_socket)
                        pass
                    elif message['header'] == self.MESSAGE_TYPES_IN["MessageIn"]:
                        print(f"{self.PEERS[notified_socket].username} > {message['data']}")
                    
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

        
        msg_checker_thread = threading.Thread(target=self.check_for_messages)
        msg_checker_thread.start()
        
        while not quit_process:
            my_input = input(f'{self.username} > ')
            if (my_input.lower() == "quit") or (my_input.lower() == "logout"):
                self.logout()
                break
            elif my_input.startswith("message"):
                users = my_input.strip().split(' ')[1:]
                self.send_chat_request(users)
            elif len(self.PEERS) > 1:
                for peer in self.PEERS:
                    self.send_message(peer, self.MESSAGE_TYPES_OUT["Message"], my_input)



if __name__ == '__main__':
    client = Client()
    client.main_process()
