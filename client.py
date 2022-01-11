import select
import socket
import errno
import sys
import threading
import time
import logging


class PeerUser:
    def __init__(self, ip, port, p_socket, socket_list_index, username):
        self.ip = ip                                # ip of a user
        self.port = port                            # port of a user
        self.p_socket = p_socket                    # socket of a user
        self.socket_list_index = socket_list_index  # index of a socket in list for this user
        self.username = username                  
        self.chatting_with = False                  # True: if already chatting with


class Client:
    HEADER_LENGTH = 10      # heder lenght for message byte
    SERVER_IP = "127.0.0.1" # server ip for all clients
    SERVER_PORT = 9000      # server tcp port
    SERVER_UDP_PORT = 9001  # server udp port
    SOCKETS_LIST = []       # 0 = server, 1 = client_server
    PEERS = {}              # key = socket, value = PeerUser
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
    MY_PORT = None                  # port of a this client
    client_server_socket = None
    username = None
    password = None
    available = True                    # status is user is currently chatting
    peers_waiting_for_chat_accept = []  # peer socket objects waiting for answer
    registered_users = []               # available users coming from search search results
    quit_process = False                # when user wants to logout

    # -------------------------<< region INIT START >>-------------------------
    def __init__(self):
        """
        initializes the client attributes starting from
        taking the port number and establishing connection with server
        """
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
                            encoding="utf-8") # log configurations
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG)
        self.establish_connection("Server", self.SERVER_IP, self.SERVER_PORT) # establishing connection with server
        self.server_udp_socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM) # taking the udp socket of the server      

    def build_client_server(self):
        """
        This function creates a server for a client to accept connections that
        coming from other clients.
        """""""""
        self.client_server_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM) # server socket of the current client
        self.client_server_socket.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # openin the port 
        self.client_server_socket.bind((self.SERVER_IP, int(self.MY_PORT))) # binding ip and port
        self.client_server_socket.listen() # starts to listen that ip form specified port  other connections 
        self.SOCKETS_LIST.append(self.client_server_socket) # we are adding that socket to socket list to reach later
        self.logger.info(
            f'Listening for connections on {self.SERVER_IP}:{self.MY_PORT}...') # adding logger info
    # -------------------------<< region INIT END >>-------------------------

    # -------------------------<< region MessageIO START >>-------------------------
    def send_message(self, user: PeerUser, msg_data_header: str, msg_data_string=""):
        """ this function sends the message to a specified user by parameter"""
        message_string = f"{msg_data_header + msg_data_string}".encode("utf-8")
        message_header = f"{len(message_string):<{self.HEADER_LENGTH}}".encode(
            'utf-8')
        user.p_socket.send(message_header + message_string)

    def receive_message(self, client_socket):
        """ this function receives the message from given client and return the coming message data as with header and its data"""
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
        """ this funcion creates and establisher the peer connection. it is called when another peer connects to the peer server"""
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
        """ this function establishes when the current clients tries to conect to another server"""
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
        """
        login function takes input and send to related user name and 
        password to server in order to check login 
        """
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
        """ 
        takes input username and password to register user. If  registration
        accepted from server side user automatically logs in. if not ask for new input
        """
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
        """Sending search request to server based on given input from user"""
        msg_data = '*'.join(users)
        self.send_message(
            self.PEERS[self.SOCKETS_LIST[0]], self.MESSAGE_TYPES_OUT["Search"], msg_data)
        self.logger.info(f"Sent serach request for user/s: {' '.join(users)}")

    def send_keep_alive(self):
        """sending alive message to UDP socket of the server at every 6 sec"""
        while not self.quit_process:
            time.sleep(6)
            data = self.username.encode("utf-8")
            self.server_udp_socket.sendto(
                data, (self.SERVER_IP, self.SERVER_UDP_PORT))
            self.logger.info("Sent keep alive ping to server!")

    # -------------------------<< region SendToServer END >>-------------------------

    # -------------------------<< region SendToClient START >>-------------------------
    def send_chat_request(self):
        """sending chat request to users that client has their ip and port"""
        request_message = self.username
        if len(self.registered_users) == 1:  # peer to peer chat
            self.establish_connection(
                self.registered_users[0][0], self.registered_users[0][1], self.registered_users[0][2])
            for peer in self.PEERS.values():
                if peer.username == self.registered_users[0][0]:
                    self.send_message(
                        peer, self.MESSAGE_TYPES_OUT["ChatRequest"], request_message)
                    self.logger.info(f"Sent chat request to {peer.username}")
        else:  
            pass

    def send_chat_accept(self):
        """Sending chat accept message to peer client and setting usr as BUSY if the user input ok"""
        for peer_socket in self.peers_waiting_for_chat_accept:
            self.PEERS[peer_socket].chatting_with = True
            self.send_message(
                self.PEERS[peer_socket], self.MESSAGE_TYPES_OUT["ChatAccept"])
            self.logger.info(
                f"Accepted chat request from {self.PEERS[peer_socket].username}")

    def send_chat_reject(self):
        """Sending chat reject to the requester"""
        for peer_socket in self.peers_waiting_for_chat_accept:
            self.send_message(
                self.PEERS[peer_socket], self.MESSAGE_TYPES_OUT["ChatReject"], "rejected the chat request")
            self.logger.info(
                f"Rejected chat request from {self.PEERS[peer_socket].username}")

            # self.remove_peer(peer_socket)
        self.available = True

        self.peers_waiting_for_chat_accept = []

    def send_busy(self):
        """sending busy if there is chatrequest and ser is already in a chat"""
        for peer_socket in self.peers_waiting_for_chat_accept:
            self.send_message(
                self.PEERS[peer_socket], self.MESSAGE_TYPES_OUT["ChatReject"], "is already in a chat!")
            self.logger.info(
                f"Automatically rejected chat request from {self.PEERS[peer_socket].username}")

    def send_chat_message(self, my_input: str):
        """Sending user message to peered user"""
        for peer in self.PEERS.values():
            if peer.chatting_with and peer.username != "Server":
                self.send_message(
                    peer, self.MESSAGE_TYPES_OUT["Message"], my_input)
                self.logger.info(
                    f"Sent a chat message to {peer.username}, content: {my_input}")

    def logout(self):
        """Logout function logs out and remove the sockets and if its in a chat also ends the chat"""
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
        """Taking user name input and password and return them"""
        _username = input("Username: ")
        _password = input("Password: ")
        return _username, _password

    def remove_peer(self, peer_socket):
        """
        this function removes a peer from dictionary
        when s/he reject the request or logout
        """
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
        """
        this function checks incoming messages from server and other clients
        """
        while True:
            if self.quit_process:
                break
            try:
                read_sockets, _, exception_sockets = select.select(
                    self.SOCKETS_LIST, [], self.SOCKETS_LIST)  
                for notified_socket in read_sockets:        # iterating over sockets for incoming messages
                    if notified_socket == self.client_server_socket:
                        is_connected, client_ = self.establish_peer_connection()  

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
                                        user_detail = user_stat.split(
                                            ' ')  # [[username, ip, port]]
                                        self.registered_users.append(
                                            [user_detail[0], user_detail[1], user_detail[2]])
                                        print(
                                            f"{user_detail[0]} is available at destination: {user_detail[1] + ':' + user_detail[2]}")
                                        self.logger.info(
                                            f"{user_detail[0]} is available at destination: {user_detail[1] + ':' + user_detail[2]}")
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
                            elif message['header'] == self.MESSAGE_TYPES_IN["Logout"]:
                                print(
                                    f"{self.PEERS[notified_socket].username} logged out")
                                self.logger.info(
                                    f"{self.PEERS[notified_socket].username} logged out")
                                
                                self.remove_peer(notified_socket)
                                self.available = True

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
                if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                    self.logger.error('Reading error: {}'.format(str(e)))
                    sys.exit()

            except Exception as e:
                self.logger.error('Reading error: {}'.format(str(e)))
                sys.exit()
    # -------------------------<< region CheckForMessages END >>-------------------------

    # -------------------------<< region MAIN START >>-------------------------
    def main_process(self):
        """
        Main process starts the main processes for logging, building the client server,
        sending and receiving messages
        """
        logged_in = False  # Not logged in default
        while not logged_in:  # Looping untill user logged in
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