import socket
import select
import threading

class Server:
    HEADER_LENGTH = 10
    IP = "127.0.0.1"
    PORT = 1234
    CLIENTS = {} # key=scoket, val=username
    SOCKETS_LIST = []
    PEERS = {} # key:username, val=list of peered users
    
    def __init__(self) -> None:
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.IP, self.PORT))
        self.SOCKETS_LIST.append(self.server_socket)
        self.server_socket.listen()
        # sockets_list = [server_socket]
        print(f'Listening for connections on {self.IP}:{self.PORT}...')

    def receive_message(self, client_socket):

        try:
            message_header = client_socket.recv(self.HEADER_LENGTH)

            if not len(message_header):
                return False

            message_length = int(message_header.decode('utf-8').strip())
            return client_socket.recv(message_length)

        except:
            return False

        # {'sender': '0.0.0.0:1234', 'receiver':'1.1.1.1', 'message':'hello'}
    def establish_connection(self):
        # Accept new connection
        # That gives us new socket - client socket, connected to this given client only, it's unique for that client
        # The other returned object is ip/port set
        client_socket, client_address = self.server_socket.accept()

        # Client should send his name right away, receive it
        user = self.receive_message(client_socket)

        # If False - client disconnected before he sent his name
        if user is False:
            return False, None

        # Add accepted socket to select.select() list
        # sockets_list.append(client_socket)

        # Also save username and username header
        self.CLIENTS[client_socket] = user
        print('Accepted new connection from {}:{}, username: {}'.format(*client_address, user['data'].decode('utf-8')))
        return True, client_socket

    def check_for_messages(self):
        read_sockets, _, exception_sockets = select.select(list(self.SOCKETS_LIST), [], list(self.SOCKETS_LIST))
        for notified_socket in read_sockets:
            if notified_socket == self.server_socket:
                if notified_socket not in self.CLIENTS:
                    is_connected, client_ = self.establish_connection()
                    self.SOCKETS_LIST.append(client_)
                    if is_connected:
                        client_.send(self.get_online_users()) # send online user list
                else:
                    message = self.receive_message(notified_socket).decode('utf-8')
                    self.PEERS[notified_socket] = self.SOCKETS_LIST[message]
                    self.PEERS[self.SOCKETS_LIST[message]] = notified_socket

            else:
                message = self.receive_message(notified_socket)
                if message is False:
                    print('Closed connection from: {}'.format(self.CLIENTS[notified_socket]['data'].decode('utf-8')))

                # Remove from list for socket.socket()
                    self.SOCKETS_LIST.remove(notified_socket)

                # Remove from our list of users
                    del self.CLIENTS[notified_socket]

                    continue
                
            # Get user by notified socket, so we will know who sent the message
                user = self.CLIENTS[notified_socket]

                print(f'Received message from {user["sender"].decode("utf-8")}: {message["message"].decode("utf-8")}')

                # Iterate over connected clients and broadcast message
                self.PEERS[notified_socket].send(user['header'] + user['data'] + message['header'] + message['data'])

    def get_online_users(self):
        if len(self.SOCKETS_LIST) == 1:
            return f"{len('False'):<{self.HEADER_LENGTH}}".encode('utf-8') + 'False'.encode('utf-8')

        online_users = 'Online Users:\n'
        for idx, socket in enumerate(self.SOCKETS_LIST[1:]):
            online_users += f'{idx+1}. {self.CLIENTS[socket]}\n'

        online_users = online_users.encode('utf-8')
        online_users_header = f"{len(online_users):<{self.HEADER_LENGTH}}".encode('utf-8')
        online_users = online_users_header + online_users

        return online_users

if __name__ == '__main__':
    server = Server()
    while True:
        server.check_for_messages()