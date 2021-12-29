import socket
import select


class Server:
    HEADER_LENGTH = 10
    IP = "127.0.0.1"
    PORT = 1234
    CLIENTS = {} # key=scoket, val=username
    PEERS = {} # key:username, val=list of peered users
    
    def __init__(self) -> None:
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.IP, self.PORT))
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
        return True, user

    def check_for_messages(self):
        read_sockets, _, exception_sockets = select.select(list(self.CLIENTS.keys()), [], list(self.CLIENTS.keys()))
        for notified_socket in read_sockets:
            if notified_socket == self.server_socket:
                is_connected, user_name = self.establish_connection()
                if is_connected:
                    self.send_message() # send online user list
                    

            else:
                message = self.receive_message(notified_socket)
                if message is False:
                    print('Closed connection from: {}'.format(self.CLIENTS[notified_socket]['data'].decode('utf-8')))

                # Remove from list for socket.socket()
                # sockets_list.remove(notified_socket)

                # Remove from our list of users
                    del self.CLIENTS[notified_socket]

                    continue
                
            # Get user by notified socket, so we will know who sent the message
                user = self.CLIENTS[notified_socket]

                print(f'Received message from {user["sender"].decode("utf-8")}: {message["message"].decode("utf-8")}')

                # Iterate over connected clients and broadcast message
                for client_socket in self.CLIENTS:

                    # But don't sent it to sender
                    if client_socket != notified_socket:

                        # Send user and message (both with their headers)
                        # We are reusing here message header sent by sender, and saved username header send by user when he connected
                        client_socket.send(user['header'] + user['data'] + message['header'] + message['data'])


    def send_message(self):
        
        pass