import sys
import socket
import threading
import argparse
import struct
import time
import math
import os

# Add the parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger_config import setup_logger  



class P2P:
    def __init__(self,peer_id,logger):
        self.logger = logger

        self.peer_id=peer_id

        self.HANDSHAKE_HEADER = b'P2PFILESHARINGPROJ'  # 18-byte header

        self.ZERO_BITS = b'\x00' * 10  # 10 zero bytes
        
        self.peers_bitfield_dict=dict() 

    def create_handshake_message(self, peer_id):
        """Creates a 32-byte handshake message."""
        return self.HANDSHAKE_HEADER + self.ZERO_BITS + struct.pack('!I', peer_id)  # 4-byte peer ID

    def read_common_cfg(self):
        """Reads Common.cfg and extracts global configurations."""
        common_cfg = {}

        with open("../Common.cfg", "r") as file:
            for line in file:
                logger.info("Going through each line of Common.cfg")

                key, value = line.strip().split(" ")
                common_cfg[key.strip()] = value.strip()

        return common_cfg

    def read_peer_info(self):
        """Reads Peerinfo.cfg and stores peer information in a dictionary."""
        peers = {}

        with open("Peerinfo.cfg", "r") as file:
            for line in file:
                logger.info("Going through each line of Peerinfo.cfg")

                parts = line.strip().split(" ")
                peer_id = int(parts[0])

                hostname = parts[1]
                port = int(parts[2])

                has_file = int(parts[3])
                peers[peer_id] = {"hostname": hostname, "port": port, "has_file": has_file}

        return peers
    

    def handle_client_connection(self,client_socket,addr):
        """Handles communication with a connected peer. Basically what to do after receing connection inside the server_socket from another 
        peer, when the another peer comminicates with all previous peers to it.."""
        print(f"Connected by {addr}")

        ack_sent=False

        while ack_sent is not True:
            data = client_socket.recv(1024)
            print('receiving data from client_socket object')

            if not data:
                # if data not found 
                break
            print(f"Received from {addr}:{data}")

            # Send acknowledgement
            client_socket.sendall(b"ACK")
            print("sent ACK msg as acknowledgement!")

            ack_sent=True
        
        while ack_sent:
            # Creating handshake msg.
            handshake_msg = self.create_handshake_message(peer_id=self.peer_id)
            print("Created handshake_msg::"+str(handshake_msg))

            client_socket.sendall(handshake_msg)
            print("Sending handshake_msg to client peer which was connected to our server_socket using client_socket object that we received " \
            "after connecting with client..")

            print("handshake msg sent as first handshake ===",handshake_msg)

            while True:
                # Receive data from peer as response handshake msg
                data = client_socket.recv(100000)
                print("Here, to send data to client peer we use something like client_socket.sendall('message') and to receive data from client " \
                "we again use the client_socket. It basically acts like a token. In this way we can connect with multiple clients, just " \
                "need to use that particular client_socket for that peer to send and receive messages from it. Once initial connection established" \
                "using server_socket and client_socket created, whole transactions with client done using respective client_socket and addr returned")

                # break if data not present.
                if not data:
                    break

                print(f"Received from {addr} handshake message: {data}")

                # Calling function to verify the handshake message format and content.
                result = self.verify_handshake(data)
                print("verify handshake msg called!")

                if result==True:
                    handshake_ack="HANDSHAKE_VERIFIED"

                    print("Sending handshake msg acknowledgement..")
                    client_socket.sendall(handshake_ack.encode())

                    print("handshake msg which was received from peer has been verified by server")

                    # NOW SENDING BITFIELD MESSAGE
                    print("SENDING BITFIELD MSG NOW FROM SERVER")
                    peer_info = self.read_peer_info()

                    bitfield_msg = self.creating_pieces(peer_info)
                    print('bitfield_msg',bitfield_msg)

                    client_socket.sendall(bitfield_msg)
                    print("bitfield msg sent.")

                    ack_sent=False

        bitfield_msg_response=False    
        while bitfield_msg_response is False:
            print("waiting for response for bitfield msg sent previously")

            response = client_socket.recv(1024)
            print(f"Response from bitfield expected: {response}")

            peer_id_sent,bitfield_payload =self.process_bitfield_msg(response)

            print('peer_id from where bitfield was sent =',peer_id_sent)
            print('bitfield_payload of bitfield_msg=',bitfield_payload)
            bitfield_msg_response=True

    

    def process_bitfield_msg(self,response):
        """ Function to process the bitfield message and 
            find out its constituents like message lenght and type
        """
        data = response  # Read message

        if len(data) < 9:  # Minimum expected size (4 + 1 + 4)
            print("Invalid bitfield message received")
            logger.info("Found invalid bitfield message..!")

            return None, None
        
        # Extract: length (4 bytes), type (1 byte), peer ID (4 bytes)
        logger.info("extracting message_length,message_type and peer_Id from bitfield message")

        message_length, message_type, peer_id = struct.unpack("!IBI", data[:9])

        bitfield_payload = data[9:]
        
        print('message_length ',message_length)
        logger.info('message_length:'+str(message_length))

        print('message_type',message_type)
        logger.info('message_type:'+str(message_type))

        print(f"Received bitfield message from Peer {peer_id}: {bitfield_payload.hex()}")
        logger.info('Recieved bitfield message:'+str(bitfield_payload.hex()))

        return peer_id, bitfield_payload

    
    def verify_handshake(self,data):
        """ Function to verify if the handshake message is the correct format.."""

        #handshake_header = data[:18].decode()  # Convert bytes to string
        handshake_header = data[:18]
        logger.info("handshake header extracted:: "+str(handshake_header))

        # Extracting the 10-byte zero bits (not used for processing)
        zero_bits = data[18:28]  # Just to verify it's correct
        logger.info("zero_bits extracted "+str(zero_bits))

        # Extracting the 4-byte Peer ID (big-endian integer)
        peer_id = int.from_bytes(data[28:32], byteorder='big')  # Convert bytes to integer
        logger.info("extracting the peer_id from bytes")

        logger.info("extracted peer id from handshake msg :: "+str(peer_id))

        # Printing results
        print(f"Handshake Header: {handshake_header}")  # Should be 'P2PFILESHARINGPROJ'

        print(f"Zero Bits: {zero_bits}")  # Should be b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'

        print(f"Peer ID: {peer_id}")  # Should be 1001 (0x03E9)
        
        peers=self.read_peer_info()

        verified=False

        if handshake_header==self.HANDSHAKE_HEADER:
            verified=True
        else:
            verified=False

        if zero_bits==b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
            verified=True
        else:
            verified=False

        if peer_id in peers.keys():
            verified=True
        else:
            verified=False
            
        # returning verified or not verified for handshake
        return verified


    def create_bitfield_message(self, has_pieces, num_pieces):
        """Creates a 'bitfield' message for a given set of available pieces."""
        
        num_bytes = math.ceil(num_pieces / 8)
        bitfield = bytearray(num_bytes)

        for i in range(num_pieces):
            if has_pieces[i]:  # Set bit if peer has the piece
                byte_index = i // 8
                bit_position = 7 - (i % 8)  # High bit to low bit order
                bitfield[byte_index] |= (1 << bit_position)
        
        message_length = 1 + 4 + len(bitfield)  # Type (1 byte) + bitfield
        message = (
            message_length.to_bytes(4, byteorder='big') +  # 4-byte message length
            bytes([5]) +  # Message type (5 for bitfield)
            struct.pack("!I", self.peer_id) + #converting peer_id to bytes
            bitfield  # Bitfield payload
        )
        return message
    

    def creating_pieces_before(self,peer_info):
        """Creating pieces used in bitfield messages and calling 
           create bitfield message function
        """
        print('peer_info',peer_info)
        has_piece_val=peer_info[self.peer_id]['has_file']
        num_pieces = 23
        logger.info("Number of pieces: "+str(num_pieces))

        has_pieces = [has_piece_val] * num_pieces  # All pieces are available
        logger.info("has_pieces list :"+str(has_pieces))

        # calling the function to create bitfield message
        bitfield_msg = self.create_bitfield_message(has_pieces, num_pieces)
        logger.info("bitfield msg created: "+str(bitfield_msg))

        return bitfield_msg
    
    def creating_pieces(self, peer_info):
        """Creating pieces used in bitfield messages by reading from the actual file
        and calling create bitfield message function
        """
        print('peer_info', peer_info)
        file_path = "TheFile.dat"
        piece_size = 200
        num_pieces = 23  # This is still hardcoded, but could be calculated: math.ceil(4409/200)
        
        logger.info("Number of pieces: " + str(num_pieces))
        
        # Initialize has_pieces with all 0s
        has_pieces = [0] * num_pieces
        
        try:
            # Check if file exists and read it
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                with open(file_path, 'rb') as file:
                    # For each piece index, check if we can read data for that piece
                    for i in range(num_pieces):
                        file.seek(i * piece_size)
                        data = file.read(piece_size)
                        
                        # If we read some data, mark this piece as available (1)
                        if data:
                            has_pieces[i] = 1
                            
                logger.info(f"File size: {file_size}, Pieces available: {sum(has_pieces)}/{num_pieces}")
            else:
                logger.warning(f"File {file_path} not found. All pieces marked as unavailable.")
        except Exception as e:
            logger.error(f"Error reading file: {e}")
            
        logger.info("has_pieces list: " + str(has_pieces))
        
        # calling the function to create bitfield message
        bitfield_msg = self.create_bitfield_message(has_pieces, num_pieces)
        logger.info("bitfield msg created: " + str(bitfield_msg))
        
        return bitfield_msg
    
    


    def connect_to_previous_peers(self,peer_id, peers):
        """Connects to all previously started peers.
           Its making connection with other peers which are previously started
        """
        for pid, peer in peers.items():
            if pid>=peer_id:
                break
            try:
                client_socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print('Client socket created')

                client_socket.connect((peer["hostname"],peer["port"]))

                print(f"Connected to peer {pid} at {peer['hostname']}:{peer['port']}")

                client_socket.sendall(f"Hello from {peer_id}".encode())

                ack_for_first_msg=False
                
                while ack_for_first_msg is False:
                    response = client_socket.recv(1024)
                    print("listening for response from server side, waiting for first ACK from server side..")
                    print(f"Response from {pid}:{response}")
                    if response is not None:
                        ack_for_first_msg=True


                while True:
                    response = client_socket.recv(1024)
                    print("listening for response from server side")
                    print(f"Response from {pid}:{response}")

                    # Calling verify_handshake function
                    result = self.verify_handshake(response)
                    print("add verify handshake function above and change this print message")

                    if result == True:
                        print("HANDSHAKE MSG verified...")

                        handshake_ack="HANDSHAKE_VERIFIED"
                        client_socket.sendall(handshake_ack.encode())

                        print('handshake message received verified')

                        break
                handshake_msg_sent=False
                while handshake_msg_sent is False:
                    handshake_msg = self.create_handshake_message(peer_id=self.peer_id)
                    #print("called class function - create_handshake_message..")

                    client_socket.sendall(handshake_msg)
                    print("Sent handshake msg from client_socket")

                    print('handshake message sent as response after verification ===',handshake_msg)
                    
                    handshake_msg_sent=True 
                
                handshake_ack_from_server=False

                while handshake_ack_from_server is False:
                    response = client_socket.recv(1024)
                    print("listening for response from server side for handshake_ack_from_server.Response below..")
                    print(f"Response from {pid}:{response}")
                    if response is not None:
                        print('ACK received for the handshake msg sent from client side. Received the ACK sent from server after Verification')
                        handshake_ack_from_server=True
               
                
                bitfield_msg_received_from_server=False
                while bitfield_msg_received_from_server is False:
                    response = client_socket.recv(1024)
                    print(f"bitfield msg received from server -- {pid}:{response}")
                    if response is not None:
                        
                        print("Now we need to figure out how to process this bitfield message received from SERVER!")
                        peer_id_sent,bitfield_payload =self.process_bitfield_msg(response)

                        print('peer_id from where bitfield was sent =',peer_id_sent)
                        print('bitfield_payload of bitfield_msg=',bitfield_payload)

                        has_pieces=self.extract_has_pieces(bitfield_payload)
                        self.peers_bitfield_dict[peer_id_sent]=has_pieces
                        print("self.peers_bitfield_dict11111",self.peers_bitfield_dict)
                        
                        """
                        # sending interested or not intereseted message
                        interested=self.interested_not_interested(peer_id_sent)
                        print("11111 result of interested_not_intereseted ",interested)
                        if interested==True:
                            msg=self.create_interested_message()
                            print("1111 msg variable before sending ",msg)
                            client_socket.sendall(msg)
                        else:
                            print("I REACHED HERE ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                            msg=self.create_notinterested_message()
                            print("1111 msg variable before sending ",msg)
                            client_socket.sendall(msg)

                        #self.peers_bitfield_dict[peer_id_sent]=bitfield_payload
                        """
                        #print("*************")
                        bitfield_msg_received_from_server=True
                # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
               

                # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

                bitfield_msg_sent=False
                while bitfield_msg_sent is False:
                    # reading peer_info from class variable earlier created.
                    peer_info=self.read_peer_info()
                    # calling creating_pieces function to be used in bitfield message.
                    bitfield_msg = self.creating_pieces(peer_info)
                    print("Created the bitfield_msg object")

                    print('bitfield_msg ',bitfield_msg)
                    print('NO ACK, Just sending client side bitfield message as response to bitfield message received above!!')
                    
                    peer_id, bitfield_payload =self.process_bitfield_msg(bitfield_msg)

                    has_pieces=self.extract_has_pieces(bitfield_payload)
                    self.peers_bitfield_dict[peer_id]=has_pieces

                    client_socket.sendall(bitfield_msg)

                    bitfield_msg_sent=True
                print("****************")
                print(f"PRINTING OUT self.peers_bitfield_dict for {self.peer_id}",self.peers_bitfield_dict)
                
                # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                # sending interested or not intereseted message
                interested=self.interested_not_interested(peer_id_sent)
                print("11111 result of interested_not_intereseted ",interested)
                if interested==True:
                    msg=self.create_interested_message()
                    print("1111 msg variable before sending ",msg)
                    client_socket.sendall(msg)
                else:
                    print("I REACHED HERE ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                    msg=self.create_notinterested_message()
                    print("1111 msg variable before sending ",msg)
                    client_socket.sendall(msg)

                #self.peers_bitfield_dict[peer_id_sent]=bitfield_payload
                # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                interested_status_flag=False
                while interested_status_flag is False:
                    response = client_socket.recv(100000)
                    print(f'interested or not intereseted msg received from client after bitfield msg was sent from server.')
                    print("THIS IS THE RESONSE MESSAGE THAT GOES INTO PROCESS INTERSTER ",response)
                    message_length, message_type, peer_id = self.process_intereseted_message(response)
                    #message_length, message_type, peer_id = self.process_intereseted_message(response)
                    print("message_length and message_type of interested/notinterested received",message_length,message_type)
                    if int(message_type)==2:
                        print(f"{peer_id} is INTERESTED")
                    elif int(message_type)==3:
                        print(f"{peer_id} is NOT INTERESTED")
                    break 
                
                """
                interested_status=False
                while interested_status is False:
                    response = client_socket.recv(100000)
                    print(f'interested or not intereseted msg received from client after bitfield msg was sent from server.')
                    print("THIS IS THE RESONSE MESSAGE THAT GOES INTO PROCESS INTERSTER ",response)
                    message_length, message_type, peer_id = self.process_intereseted_message(response)
                    print("message_length and message_type of interested/notinterested received",message_length,message_type)
                    if int(message_type)==2:
                        print(f"{peer_id} is INTERESTED")
                    elif int(message_type)==3:
                        print(f"{peer_id} is NOT INTERESTED")
                    break 
                """
                '''
                bitfield_msg_ack=False
                while bitfield_msg_ack is False:
                    response = client_socket.recv(1024)
                    print(f"Response from {pid}: {response}")
                    
                    print("Response as ack for bitfield_msg sent Previously below")
                    print("Response from "+str(pid)+":"+str(response))
                '''
            except Exception as e:
                print(f"Failed to connect to peer {pid}: {e}") 
    def process_intereseted_message(self,message):
        # Extract: length (4 bytes), type (1 byte), peer ID (4 bytes)
        message_length = int.from_bytes(message[0:4], byteorder='big')
        message_type = message[4]
        peer_id = struct.unpack("!I", message[5:9])[0]

        return message_length, message_type, peer_id

    def extract_has_pieces(self, bitfield_payload, num_pieces=23):
        """
        Extracts the has_pieces list from a bitfield payload.
        
        Args:
            bitfield_payload (bytes): The bitfield payload from a bitfield message
            num_pieces (int): The total number of pieces in the torrent
            
        Returns:
            list: A boolean list indicating which pieces the peer has
        """
        has_pieces = []
        
        for i in range(num_pieces):
            byte_index = i // 8
            bit_position = 7 - (i % 8)  # High bit to low bit order
            
            # Check if the byte_index is within the bitfield payload
            if byte_index < len(bitfield_payload):
                # Check if the bit at bit_position is set
                has_piece = bool((bitfield_payload[byte_index] >> bit_position) & 1)
                if has_piece==True:
                    has_piece=1
                else:
                    has_piece=0
                has_pieces.append(has_piece)
            else:
                has_pieces.append(False)
        
        return has_pieces
    
    def interested_not_interested(self,other_peerid):
        interested=False
        peer_id=self.peer_id
        print(f"peer_id and other peer_id are {peer_id} & {other_peerid}")
        self_has_pieces=self.peers_bitfield_dict[peer_id]

        other_has_pieces=self.peers_bitfield_dict.get(other_peerid)
        if other_has_pieces==None:
            return False

        for i in range(len(other_has_pieces)):
            if other_has_pieces[i]==True and self_has_pieces[i]==False:
                interested=True
                break
        return interested
    
    def create_notinterested_message(self):
        """Creates a 'notinterested' message for a given set of available pieces."""
        
        message_length = 1 + 4  # Type (1 byte) + peer_id (4 bytes)
        message = (
            message_length.to_bytes(4, byteorder='big') +  # 4-byte message length
            bytes([3]) +  # Message type (2 for interested)
            struct.pack("!I", self.peer_id)  # 4-byte peer_id
        )
        return message
    
    
    def create_interested_message(self):
        """Creates a 'interested' message for a given set of available pieces."""
        
        message_length = 1 + 4  # Type (1 byte) + peer_id (4 bytes)
        message = (
            message_length.to_bytes(4, byteorder='big') +  # 4-byte message length
            bytes([2]) +  # Message type (2 for interested)
            struct.pack("!I", self.peer_id)  # 4-byte peer_id
        )
        return message


    def process_bitfield_msg(self,response):
        """ Function to process the bitfield message and 
            find out its constituents like message lenght and type
        """
        data = response  # Read message

        if len(data) < 9:  # Minimum expected size (4 + 1 + 4)
            print("Invalid bitfield message received")
            logger.info("Found invalid bitfield message..!")

            return None, None
        
        # Extract: length (4 bytes), type (1 byte), peer ID (4 bytes)
        logger.info("extracting message_length,message_type and peer_Id from bitfield message")

        message_length, message_type, peer_id = struct.unpack("!IBI", data[:9])

        bitfield_payload = data[9:]
        
        print('message_length ',message_length)
        logger.info('message_length:'+str(message_length))

        print('message_type',message_type)
        logger.info('message_type:'+str(message_type))

        print(f"Received bitfield message from Peer {peer_id}: {bitfield_payload.hex()}")
        logger.info('Recieved bitfield message:'+str(bitfield_payload.hex()))

        return peer_id, bitfield_payload


    def handshake_method(self,client_socket,addr):
        """Handles handshaking with a connected peer."""

        print(f"Connected by {addr}")

        # TCP connection established, now can send handshake message
        handshake_msg = self.create_handshake_message(peer_id=self.peer_id)

        client_socket.sendall(handshake_msg)

        print('handshake message sent as first handshake ===',handshake_msg)

        while True:
            # Receive data from peer
            data = client_socket.recv(100000) 
            if not data:
                break
            
            print(f"Received from {addr} handshake message: {data}")

    

    def start_server(self,port,peer_id):
        """Starts a TCP server that listens for incoming connections."""
        
        self.logger.info("running start_server function..")
        # create a TCP socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.info("Started server_socket to listen to incoming connections")
    

        SERVER = socket.gethostbyname(socket.gethostname())
        self.logger.info("getting SERVER object using gethostname function.")

        print('SERVER IP ',SERVER)
        self.logger.info("Got the server IP "+str(SERVER))

        # bind to given port
        server_socket.bind((SERVER,port))
        self.logger.info("Binding the SERVER and port="+str(port))

    
        # Start listening to incoming connections
        server_socket.listen(50)
        print(f"Peer {peer_id} listening on port {port}...")

        self.logger.debug(f"Peer {peer_id} listening on port {port}...")
        
        try:
            while True: 
                self.logger.debug("Peer 1 now waiting for incoming traffic...")

                client_socket, addr = server_socket.accept()

                self.logger.debug("client_socket object and addr created using .accept()")

                self.client_socket=client_socket

                print('client_socket,addr values printed -',client_socket,addr)

                self.logger.info("client_socket,addr values printed -"+str(client_socket)+","+str(addr))

                thread=threading.Thread(target=self.handle_client_connection, args=(client_socket, addr)).start()

                self.logger.info("New thread started for handle_client_connection function..")

                print("ACTIVE CONNECTIONS",str(threading.active_count()-1))
                
                self.logger.debug("Number of active threads minus main thread -"+str(threading.active_count()-1))

        except ConnectionResetError:
            print(f"Client {addr} forcibly closed the connection.")
            logger.error("Cleint forcibly closed the connection")

        except Exception as e:
            print(f"Error with {addr}: {e}")
            logger.error(str(e))

        finally:

            print(f"Closing connection with {addr}")
            print(f"Server on port {port} shut down.")
            logger.info("closing connection")
            logger.info("shutting down server!.")

            client_socket.close()
        


def main(peer_id, logger):
    """ Main function to create Object of Class P2P.
        Creating logger object, getting config information from :
        a) Common_cfg
        b) Peer config
    """
    print('just testing out peer id', peer_id)

    ClassObj=P2P(peer_id, logger)
    logger.info("created Object of class P2P...")

    # read configurations
    common_cfg = ClassObj.read_common_cfg()
    print('read common_cfg',common_cfg)

    logger.debug("read from common_cfg common configs")

    peer_info = ClassObj.read_peer_info()
    print('read peer info',peer_info.get(peer_id))

    logger.debug("read from peer info config file")


    # Start server in a separate thread
    threading.Thread(target=ClassObj.start_server, args=(peer_info[peer_id]["port"],peer_info[peer_id],)).start()

    logger.info("Thread started for start_server function, separate thread for server")

    # Connect to previous peers
    threading.Thread(target=ClassObj.connect_to_previous_peers, args=(peer_id, peer_info,)).start()

    logger.info("Thread started for connect to previous peers to connect to peers started before..")

    

    


if __name__=="__main__":
    # create parser object 
    parser = argparse.ArgumentParser()

    # added argument
    parser.add_argument('peer_id', type=int)

    args = parser.parse_args()
    
    # Setup logger file
    logfile='log_peer_'+ str(args.peer_id)
    logger = setup_logger(logfile)

    main(args.peer_id, logger)

