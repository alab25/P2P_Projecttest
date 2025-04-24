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
    def __init__(self, peer_id,logger):
        self.logger = logger
        self.peer_id = peer_id
        self.HANDSHAKE_HEADER = b'P2PFILESHARINGPROJ' # 18-byte header
        self.ZERO_BITS = b'\x00' * 10 # 10 zero bytes

        print('self.peer_id from constructor of class P2P ',self.peer_id)
        print('self.HANDSHAKE_HEADER from constructor of class P2P ',self.HANDSHAKE_HEADER)
        print('self.ZERO_BITS from constructor of class P2P ',self.ZERO_BITS)

    def create_handshake_message(self, peer_id):
        """Creates a 32-byte handshake message."""
        return self.HANDSHAKE_HEADER + self.ZERO_BITS + struct.pack('!I', peer_id)  # 4-byte peer ID


    def read_common_cfg(self):
        """Reads Common.cfg and extracts global configurations."""
        common_cfg = {}

        with open("../Common.cfg","r") as file:
            for line in file:
                logger.info("Going through each line of Common.cfg")

                key, value = line.strip().split(" ")
                common_cfg[key.strip()] = value.strip()
        print("Printing out common_cfg below..")
        print(common_cfg)
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

                peers[peer_id] = {"hostname": hostname, "port":port, "has_file": has_file}
            print("Printing contents of peer_info.cfg file below")
            print(peers)
        
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
    

    def creating_pieces(self,peer_info):
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
           
    
    def start_server(self,port,peer_id):
        """ Starts a TCP server that listens for incoming connections."""
        
        # Create a TCP socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("Starter server socket to listen to incoming connections")

        SERVER = socket.gethostbyname(socket.gethostname())
        print("getting server oject using gethostname funciton.Could have also copied from ipconfig i think, but this is safer")
        print("SERVER IP ",SERVER)
        print('SERVER IP above')

        # bind to given port
        server_socket.bind((SERVER,port))
        print("Binding the SERVER and port="+str(port))

        # Start listening to incoming connections
        server_socket.listen(50)
        print(f"Peer {peer_id} listening on port {port}...")

        try:
            while True:
                print("Peer 1 waiting for incoming traffic...")
                client_socket, addr = server_socket.accept()
                # this client_socket object is like a key for us to access the client peer which has connected to our open server_socket
                # to send any message to this client peer we have to use this client_socket object like we do in handle_client_connection.

                print("client_socket object and addr created using .accept()")
                self.client_socket=client_socket

                print('client_socket,addr values printed -',client_socket,addr)

                thread=threading.Thread(target=self.handle_client_connection, args=(client_socket,addr)).start()

                print("ACTIVE CONNECTIONS",str(threading.active_count()-1))
        
        except ConnectionResetError:
            print(f"Client {addr} forcibly closed the connection.")
        except Exception as e:
            print(f"Error with {addr}:{e}")
        finally:
            print(f"closing connection with {addr}")
            client_socket.close()
    
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
            except Exception as e:
                print(f"Failed to connect to peer {pid}:{e}")


        
                

def main(peer_id, logger):
    """ Main function to create object of class P2P"""
    ClassObj = P2P(peer_id, logger)
    logger.info("created Object of class P2P...")

    # read configurations
    common_cfg = ClassObj.read_common_cfg()
    print('read common_cfg, main function print-out',common_cfg)

    logger.debug("read from common_cfg common configs")

    peer_info = ClassObj.read_peer_info()
    print('read peer info',peer_info.get(peer_id))

    # Start server in a separate thread
    threading.Thread(target=ClassObj.start_server, args=(peer_info[peer_id]["port"],peer_info[peer_id],)).start()

    print("Thread Started for start_server function in PeerProcessCopy, its separate thread for server")

    #threading.Thread(target=ClassObj.connect_to_previous_peers, args=(peer_id,peer_info,)).start() 

    #print("Thread started for connect to previous peers to connect to peers started before..")



if __name__=="__main__":
    # create parser object
    parser = argparse.ArgumentParser()

    # added argument
    parser.add_argument('peer_id', type=int)

    args = parser.parse_args()

    # setup logger file
    logfile = 'log_peer_' + str(args.peer_id)
    logger = setup_logger(logfile)

    main(args.peer_id, logger)
