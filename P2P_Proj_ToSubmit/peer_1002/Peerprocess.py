import sys
import socket
import threading
import argparse
import struct
import time
import math
import os
import random

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
        

        common_cfg=self.read_common_cfg()
        self.number_of_preferred_neighbours=common_cfg["NumberOfPreferredNeighbors"]
        self.unchoking_interval=common_cfg["UnchokingInterval"]
        self.optimistic_unchoking_interval=common_cfg["OptimisticUnchokingInterval"]

        # Added from CLD, need to fix and update

        self.peer_connections = {}  # Dictionary to store active peer connections
        self.preferred_neighbors = set()  # Set of peer_ids that are preferred neighbors
        self.optimistically_unchoked_neighbor = None  # Peer_id of optimistically unchoked neighbor
        
        pieces_list=self.return_pieces_list()
        if 0 in pieces_list:
            self.has_complete_file=False
        else:
            self.has_complete_file = True  # Whether this peer has the complete file
        
        # Initialize timers for unchoking intervals
        self.last_preferred_neighbors_update = time.time()
        self.last_optimistic_unchoking = time.time()

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
        
        while ack_sent is True:
            # Creating handshake msg.
            handshake_msg = self.create_handshake_message(peer_id=self.peer_id)
            print("Created handshake_msg::"+str(handshake_msg))

            client_socket.sendall(handshake_msg)
            print("Sending handshake_msg to client peer which was connected to our server_socket using client_socket object that we received " \
            "after connecting with client..")

            print("handshake msg sent as first handshake ===",handshake_msg)

            handshake_ack_received=False
            while handshake_ack_received is False:
                data = client_socket.recv(100000)
                if data is not None:
                    print("HANDSHAKE ACK received from client side for the handshake msg sent earlier..")
                    break

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

                if result is not None:
                    handshake_ack="HANDSHAKE_VERIFIED"

                    print("Sending handshake msg acknowledgement..")
                    client_socket.sendall(handshake_ack.encode())
                    

                    print("handshake msg which was received from peer has been verified by server")

                    # NOW SENDING BITFIELD MESSAGE
                    print("SENDING BITFIELD MSG NOW FROM SERVER")
                    peer_info = self.read_peer_info()

                    bitfield_msg = self.creating_pieces(peer_info)
                    print('bitfield_msg',bitfield_msg)
                    
                    peer_id, bitfield_payload =self.process_bitfield_msg(bitfield_msg)

                    has_pieces=self.extract_has_pieces(bitfield_payload)

                    self.peers_bitfield_dict[peer_id]=has_pieces

                    client_socket.sendall(bitfield_msg)
                    print("bitfield msg sent.")
                    break
            ack_sent=False
            break
        # ^^^^^^^^^^^^^^^^^^^^
        """
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
        # ^^^^^^^^^^^^^^^^^^^^^^^^


        print("**************")


        bitfield_msg_response=False    
        while bitfield_msg_response is False:
            print("waiting for response for bitfield msg sent previously. EXPECTING bitfield msg of Client here " \
            "as response to server side sent earlier")

            response = client_socket.recv(100000)
            print(f"bitfield msg received from client side -- {addr}:{response}")
            #print(f"Response from bitfield from client side - : {response}")

            peer_id_sent,bitfield_payload =self.process_bitfield_msg(response)

            print('peer_id from where bitfield was sent =',peer_id_sent)
            print('bitfield_payload of bitfield_msg=',bitfield_payload)
            has_pieces=self.extract_has_pieces(bitfield_payload)
            self.peers_bitfield_dict[peer_id_sent]=has_pieces

            # sending interested or not intereseted message
            """
            interested=self.interested_not_interested(peer_id_sent)
            if interested==True:
                msg=self.create_interested_message()
                client_socket.sendall(msg)
            else:
                msg=self.create_notinterested_message()
                client_socket.sendall(msg)

            """
            bitfield_msg_response=True
        # Added cld need to fix and check
        
        # After successful handshake and bitfield exchange
        self.peer_connections[peer_id_sent]=dict(
            peer_id=peer_id_sent,
            client_socket=client_socket,  # This is the socket passed to handle_client_connection
            addr=addr,
            interested=False,
            choked=True,  # All peers start choked
            download_rate = 0,  # Bytes/second downloaded from this peer
            bytes_downloaded = 0,  # Total bytes downloaded in current interval
            last_measurement_time = time.time()
        )

        print("**************")
        print(f"PRINTING OUT self.peers_bitfield_dict for {self.peer_id}",self.peers_bitfield_dict)

        # ^^^^^^^^^^^^^^^^^^^^
        
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
                # Added cld need to fix and check
                self.peer_connections[peer_id]['interested']=True
            elif int(message_type)==3:
                print(f"{peer_id} is NOT INTERESTED")
            break 
        
        # ^^^^^^^^^^^^^^^^^^^^^^^^
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

        # Start a thread to periodically check and update choking status
        # Added CLD Need to fix and check
        threading.Thread(target=self.periodic_unchoking_updates, daemon=True).start()

        #@@@@@@@@@@@@@@@@@@@@
        print("REACHED HERE NOW 444444444444444444 PM ....")

        request_msg_flag=False

        while request_msg_flag is False:

            request_msg = client_socket.recv(100000)

            print(" 44444444 GOT THIS MSG from client requesting pieces",request_msg)

            print("check if recieved not interested msg, if yes exit while")

            message_id = struct.unpack('>B', request_msg[4:5])[0]

            if message_id==3:

                print('RECEIVED NOT INTERESTED FROM Peer, breaking loop')

                request_msg_flag=True

                peer_id_not = struct.unpack("!I", request_msg[5:9])[0]

                # changing peer to not interested.

                self.peer_connections[peer_id_not]['interested']=False

                break



            piece_msg = self.handle_request_msg(request_msg)

            client_socket.sendall(piece_msg)

            print('PIECE MSG CREATED AND SENT AS REQUESTED')

            #request_msg_flag=True



    # Added for request msg handling

    def handle_request_msg(self,request_msg):

        """ Handling request msg

        The request message format is:

        - 4 bytes: message length

        - 1 byte: message type (6 = request)

        - 4 bytes: piece index

        """

        #Unpack the message

        length, msg_type, piece_index = struct.unpack('>IBI', request_msg)



        if msg_type != 6:  # 6 is the message type for 'request'

            print(f"Error: Received message type {msg_type}, expected request (6)")

            return None

        print(f"Received request for piece {piece_index}")



        # Fetch the piece data

        piece_data = self.get_piece(piece_index)

        

        if piece_data is None:

            print(f"Error: Could not retrieve piece {piece_index}")

            return None

        

        message_id = 7  # 7 is the message type for 'piece'

        msg_length = 1 + 4 + len(piece_data)  # message ID + piece index + data length

        

        # Pack the message

        piece_message = struct.pack('>IBI', msg_length, message_id, piece_index) + piece_data

        

        print(f"Sending piece {piece_index}, size: {len(piece_data)} bytes")

        

        return piece_message

    

    def get_piece(self, piece_index):

        """

        Get the data for a specific piece

        """

        self.num_pieces=23

        self.file_path="TheFile.txt"

        self.file_size=4518

        self.piece_size=200

        if piece_index < 0 or piece_index >= self.num_pieces:

            print(f"Error: Invalid piece index {piece_index}")

            return None

            

        try:

            with open(self.file_path, 'rb') as f:

                # Calculate offset and how much to read

                offset = piece_index * self.piece_size

                f.seek(offset)

                

                # For the last piece, we might need to read less than piece_size

                if piece_index == self.num_pieces - 1:

                    bytes_to_read = self.file_size - offset

                else:

                    bytes_to_read = self.piece_size

                    

                return f.read(bytes_to_read)

        except Exception as e:

            print(f"Error reading piece {piece_index}: {e}")

            return None

    

    # Added CLD Need to fix and check
    def periodic_unchoking_updates(self):
        """Periodically update preferred neighbors and optimistically unchoked neighbor"""
        while True:
            self.update_preferred_neighbors()
            self.update_optimistically_unchoked_neighbor()
            # Sleep for a shorter time than the intervals to ensure we don't miss deadlines
            time.sleep(int(min(self.unchoking_interval, self.optimistic_unchoking_interval)) / int(2))
    
    # Added CLD Need to fix and check
    def update_preferred_neighbors(self):
        """Select k preferred neighbors based on download rates"""
        current_time = time.time()
        
        # Only update if the unchoking interval has passed
        if current_time - self.last_preferred_neighbors_update < float(self.unchoking_interval):
            return
            
        self.last_preferred_neighbors_update = current_time
        
        # Find interested peers
        interested_peers={}
        for each_dict in self.peer_connections.values():
            if each_dict['interested']==True:
                interested_peers[each_dict['peer_id']]=each_dict

        """
        interested_peers = {
            pid: conn for pid, conn, interested in self.peer_connections.items() 
            if interested==True
        }
        """

        print("FIND BELOW THE interested_peers dictionary..")
        print(interested_peers)
        print("FIND ABOVE the interested_peers dictionary..")

        # If we have the complete file, select randomly
        if self.has_complete_file:
            if len(interested_peers) <= int(self.number_of_preferred_neighbours):
                new_preferred = set(interested_peers.keys())
            else:
                new_preferred = set(random.sample(
                    list(interested_peers.keys()), 
                    self.number_of_preferred_neighbours
                ))
        else:
            # Sort peers by download rate (highest first)
            sorted_peers = sorted(
                interested_peers.items(), 
                key=lambda x: x[1]["download_rate"], 
                reverse=True
            )
            
            # Select top k peers
            new_preferred = set()
            for i, (pid, _) in enumerate(sorted_peers):
                if int(i) < int(self.number_of_preferred_neighbours):
                    new_preferred.add(pid)
                else:
                    break
        print("222222222222222222222 WORKS TILL HERE....")
        
        # Process peers that need to be choked/unchoked
        choke_msg, unchoke_msg = self.create_choke_unchoke_messages()
        
        # Choke peers that are no longer preferred (except optimistically unchoked)
        for pid in self.preferred_neighbors - new_preferred:
            if pid != self.optimistically_unchoked_neighbor:
                if not self.peer_connections[pid]['choked']:
                    self.peer_connections[pid]['choked'] = True
                    self.peer_connections[pid]['client_socket'].sendall(choke_msg)
                    print(f"Choking peer {pid}")
        
        # Unchoke new preferred peers
        for pid in new_preferred:
            if self.peer_connections[pid]['choked']:
                self.peer_connections[pid]['choked'] = False
                self.peer_connections[pid]['client_socket'].sendall(unchoke_msg)
                print(f"Unchoking peer {pid} as preferred neighbor")
        
        # Update our preferred neighbors set
        self.preferred_neighbors = new_preferred
        
        print("WORKS TILL HERE 33333333333333333")
        # Reset download statistics for the next interval
        for conn in self.peer_connections.values():
            # this one kind of sus, check later..
            self.reset_download_stats(conn)
            
        print(f"Updated preferred neighbors: {self.preferred_neighbors}")
    
    # kind of sus, check later.. 
    def reset_download_stats(self,conn):
        """Reset download statistics for a new measurement interval"""
        conn['bytes_downloaded'] = 0
        conn['last_measurement_time'] = time.time()
    
    def create_choke_unchoke_messages(self):
        """Create message formats for choke and unchoke messages"""
        # Message format: <length prefix><message ID>
        # Choke: ID 0, Unchoke: ID 1
        
        # Assuming peer_id is an integer
        peer_id_bytes = struct.pack('>I', self.peer_id)

        # Choke message - 5 bytes total
        # 1 byte for message length (4) + 1 byte for message ID (0)
        choke_msg = struct.pack('>IB', 1, 0) + peer_id_bytes
        
        # Unchoke message - 5 bytes total
        # 1 byte for message length (4) + 1 byte for message ID (1)
        unchoke_msg = struct.pack('>IB', 1, 1) + peer_id_bytes
        
        return choke_msg, unchoke_msg

    # Added CLD Need to fix and check
    def update_optimistically_unchoked_neighbor(self):
        """Randomly select one peer to be optimistically unchoked"""
        current_time = time.time()
        
        # Only update if the optimistic unchoking interval has passed
        if current_time - self.last_optimistic_unchoking < float(self.optimistic_unchoking_interval):
            return
            
        self.last_optimistic_unchoking = current_time
        
        # Find interested but choked peers
        candidates = [
            pid for pid, conn in self.peer_connections.items()
            if conn['interested'] and conn['choked'] and pid not in self.preferred_neighbors
        ]
        print("444444444 works till here")
        print('printing self.peer_connections dictionary here',self.peer_connections)
        print('find candidates below')
        print(candidates)
        
        # If no candidates, keep the current one
        if not candidates:
            return
        
        # Select a random peer
        new_optimistic = random.choice(candidates)
        
        # If we already have an optimistically unchoked neighbor that is not a preferred neighbor,
        # choke them unless they became a preferred neighbor
        if (self.optimistically_unchoked_neighbor and 
            self.optimistically_unchoked_neighbor not in self.preferred_neighbors):
            old_opt = self.optimistically_unchoked_neighbor
            self.peer_connections[old_opt].choked = True
            choke_msg, _ = self.create_choke_unchoke_messages()
            self.peer_connections[old_opt]['client_socket'].sendall(choke_msg)
            print(f"Choking previous optimistically unchoked peer {old_opt}")
        
        # Unchoke the new optimistically unchoked neighbor
        self.optimistically_unchoked_neighbor = new_optimistic
        self.peer_connections[new_optimistic].choked = False
        _, unchoke_msg = self.create_choke_unchoke_messages()
        self.peer_connections[new_optimistic]['client_socket'].sendall(unchoke_msg)
        print(f"Optimistically unchoking peer {new_optimistic}")

    def process_intereseted_message(self,message):
        # Extract: length (4 bytes), type (1 byte), peer ID (4 bytes)
        message_length = int.from_bytes(message[0:4], byteorder='big')
        message_type = message[4]
        peer_id = struct.unpack("!I", message[5:9])[0]

        return message_length, message_type, peer_id
    
    def interested_not_interested(self,other_peerid):
        interested=False
        peer_id=self.peer_id
        self_has_pieces=self.peers_bitfield_dict[peer_id]

        other_has_pieces=self.peers_bitfield_dict[other_peerid]

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
    
    def return_pieces_list(self):
        file_path = "TheFile.txt"
        piece_size = 200
        num_pieces = 23  # This is still hardcoded, but could be calculated: math.ceil(4409/200)
        
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
        return has_pieces
    
    def creating_pieces(self, peer_info):
        """Creating pieces used in bitfield messages by reading from the actual file
        and calling create bitfield message function
        """
        print('peer_info', peer_info)
        file_path = "TheFile.txt"
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

                # After successful handshake and bitfield exchange
                self.peer_connections[peer_id_sent]=dict(
                    peer_id=peer_id_sent,
                    client_socket=client_socket,  # This is the socket passed to handle_client_connection
                    interested=False,
                    choked=True,  # All peers start choked
                    download_rate = 0,  # Bytes/second downloaded from this peer
                    bytes_downloaded = 0,  # Total bytes downloaded in current interval
                    last_measurement_time = time.time()
                )
                
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
                choke_unchoke_flag=False
                while choke_unchoke_flag is False:
                    message = client_socket.recv(100000)
                    print("unchoked/choked msg sent from server,received here..")
                    
                    message_id = struct.unpack('>B', message[4:5])[0]
                    # Extract peer_id (4 bytes after the message ID)
                    peer_id_choke = struct.unpack('>I', message[5:9])[0]

                    if message_id==0:
                        print("choke msg received!")
                        self.peer_connections[peer_id_choke]['choked']=True
                    elif message_id==1:
                        print("unchoke msg received.")
                        self.peer_connections[peer_id_choke]['choked']=False
                        self.requested_pieces=[]
                        self.handle_unchoking(peer_id)

                    

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
    
    # CLDHELP2 %%%%%%%%%%%%%%%%%%%%%%%%
    def handle_unchoking(self, peer_id):
        """Handle being unchoked by a peer - start requesting pieces"""
        print(f"Starting to request pieces from peer {peer_id}")
        
        # Create a new thread to handle piece requests
        # This ensures we don't block other operations
        """
        threading.Thread(
            target=self.request_pieces_from_peer,
            args=(peer_id,),
            daemon=True
        ).start()
        """
        self.request_pieces_from_peer(peer_id)
        
    def request_pieces_from_peer(self, peer_id):
        """Request pieces from a specific peer - runs in a separate thread"""
        # Get the socket for this peer
        if peer_id not in self.peer_connections:
            print(f"Cannot request pieces: peer {peer_id} not connected")
            return
            
        client_socket = self.peer_connections[peer_id]['client_socket']
        
        # Track if we're still interested in this peer's pieces
        still_interested = True
        
        while still_interested:
            # Check if we're still unchoked by this peer
            if peer_id not in self.peer_connections or self.peer_connections[peer_id]['choked']:
                print(f"We are choked by peer {peer_id}, stopping piece requests")
                break
                
            # Select a piece to request
            piece_index = self.select_piece_to_request(peer_id)
            
            if piece_index is None:
                # No more pieces to request from this peer
                print(f"No more pieces to request from peer {peer_id}")
                still_interested = False
                
                # If we're no longer interested, send a NOT_INTERESTED message
                if peer_id in self.peer_connections:
                    not_interested_msg = self.create_notinterested_message()
                    try:
                        client_socket.sendall(not_interested_msg)
                        self.peer_connections[peer_id]['interested'] = False
                        print(f"Sent NOT_INTERESTED to peer {peer_id}")
                    except:
                        print(f"Error sending NOT_INTERESTED to peer {peer_id}")
                break
                
            # Send request for the selected piece
            request_msg = self.create_request_message(piece_index)
            try:
                print("1111111111111111 WORKED TILL HERE PEER 1003..")
                client_socket.sendall(request_msg)
                print(f"Requested piece {piece_index} from peer {peer_id}")
            except:
                print(f"Error requesting piece {piece_index} from peer {peer_id}")
                break
                
            # Wait for the piece response
            piece_received = False
            start_time = time.time()
            
            while not piece_received:
                '''
                # Add a timeout to prevent waiting forever
                if time.time() - start_time > 30:  # 30 seconds timeout
                    print(f"Timeout waiting for piece {piece_index} from peer {peer_id}")
                    # Remove the piece from our requested set
                    self.requested_pieces.remove(piece_index)
                    break
                    
                # Check if we've been choked while waiting
                if peer_id not in self.peer_connections or self.peer_connections[peer_id]['choked']:
                    print(f"Choked while waiting for piece {piece_index} from peer {peer_id}")
                    # Remove the piece from our requested set
                    self.requested_pieces.remove(piece_index)
                    return
                '''
                try:
                    # Non-blocking receive to check for data
                    #client_socket.setblocking(False)
                    print("STUCK HERE WAITING FOR PACKET..........4.511111")
                    response = client_socket.recv(1024000)  # Large buffer for piece data
                    #client_socket.setblocking(True)
                    print("THIS IS THE RESPONSE MSG OF PIECE REQUEST RECIEVED..",response)
                    """
                    if not response:
                        # Socket closed or error
                        time.sleep(0.1)  # Small delay before retry
                        continue
                    """
                    # Process the response
                    print("4.45 REACHED HERE !!!!!!!!!!!!!!")
                    piece_index_rcv, piece_data = self.process_piece_message(response)
                    
                    if piece_index_rcv is not None:
                        print(f"Received piece {piece_index_rcv} from peer {peer_id}")
                        
                        # Verify this is the piece we requested
                        if piece_index_rcv == piece_index:
                            # Save the piece
                            self.save_piece(piece_index, piece_data)
                            
                            # Update our bitfield
                            self.peers_bitfield_dict[self.peer_id][piece_index] = True
                            
                            # Update download statistics UPDATE LATER DOWNLOAD RATE..
                            end_time=time.time()
                            self.update_download_rate(peer_id,len(piece_data),start_time,end_time)
                            
                            # Mark that we've received this piece
                            piece_received = True
                            
                            # Check if we have the complete file
                            if all(self.peers_bitfield_dict[self.peer_id]):
                                self.has_complete_file = True
                                print("We now have the complete file!")
                        else:
                            print(f"Received unexpected piece {piece_index_rcv}, expected {piece_index}")
                            print("444444444444444444 Finally reached 1031 Line")
                    

                except BlockingIOError:
                    # No data available yet
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Error receiving piece: {e}")
                    break
    def update_download_rate(self,peer_id,len_piece_data,start_time,end_time):
        duration = end_time - start_time
        if duration == 0:
            print("Warning: Download time is zero, cannot calculate rate.")
            return 0.0

        rate = len_piece_data / duration  # bytes per second
        
        self.peer_connections[peer_id]['download_rate']=rate
        self.peer_connections[peer_id]['bytes_downloaded']=self.peer_connections[peer_id]['bytes_downloaded']+len_piece_data
        self.peer_connections[peer_id]['last_measurement_time']=time.time()
        
        print("&&&&&&&&&&&&&&&&&&&&&&&")
        print("find self.peer_connections after rate update here ",self.peer_connections)
        print("I THINK WE SHOULD SEND THIS INFO TO THE SERVER SIDE BECAUSE NEIGHBOR DECISIONS NEED THIS ONE I FEEL.. LETS SEE")
        print("&&&&&&&&&&&&&&&&&&&&&&&&&&")
        return 
    
    def process_piece_message(self, message):
        """Process a received piece message
        Returns (piece_index, piece_data)
        """
        if len(message) < 9:  # Basic validation
            return None, None
            
        # Unpack to get message details
        msg_length = struct.unpack('>I', message[0:4])[0]
        msg_type = message[4]
        
        if msg_type != 7:  # Not a piece message
            return None, None
            
        # Extract the piece index
        piece_index = struct.unpack('>I', message[5:9])[0]
        
        # Extract the piece data (everything after the first 9 bytes)
        piece_data = message[9:]
        
        return piece_index, piece_data
    
    
    def save_piece_missing(self, piece_index, piece_data):
        """Save a text piece to the file at the correct offset"""
        try:
            piece_size = 200  # PieceSize from your configuration
            
            # Calculate the offset where this piece should be written
            offset = piece_index * piece_size
            
            # If dealing with text data, ensure we're working with bytes
            if isinstance(piece_data, str):
                piece_data = piece_data.encode('utf-8')
            
            # Make sure we're not writing past the piece boundary
            if len(piece_data) > piece_size:
                print(f"Warning: Piece {piece_index} exceeds piece size, truncating.")
                piece_data = piece_data[:piece_size]
            
            # Open the file in read+write binary mode
            with open("TheFile.txt", 'r+b') as f:
                # Get file size
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                
                # Ensure the file is large enough for this piece
                if offset + piece_size > file_size:
                    f.seek(0, 2)  # Go to the end
                    bytes_needed = offset + piece_size - file_size
                    f.write(b' ' * bytes_needed)  # Extend file with spaces instead of nulls
                
                # Seek to the correct position
                f.seek(offset)
                
                # If this is not the last piece, ensure we don't break text at an awkward place
                if offset + len(piece_data) < file_size:
                    # Look for a good breaking point (newline, period, etc.)
                    for i in range(len(piece_data) - 1, len(piece_data) - 20, -1):
                        if i < 0:
                            break
                        # Good breaking characters for text
                        if piece_data[i:i+1] in [b'\n', b'.', b'!', b'?', b' ']:
                            piece_data = piece_data[:i+1]
                            break
                
                # Write the piece data
                f.seek(offset)
                f.write(piece_data)
            
            print(f"Saved piece {piece_index} to TheFile.txt at offset {offset}")
            return True
        except Exception as e:
            print(f"Error saving piece {piece_index}: {e}")
            return False

    def save_piece(self, piece_index, piece_data):
        """Save a piece to the file at the correct offset, preserving boundaries"""
        try:
            piece_size = 200  # PieceSize from your configuration
            file_size = 4518  # FileSize from your configuration
            
            # Calculate the offset where this piece should be written
            offset = piece_index * piece_size
            
            # Make sure the piece data is exactly the right length
            if len(piece_data) < piece_size:
                # Pad if too short (should not normally happen)
                print(f"Warning: Piece {piece_index} is shorter than expected, padding.")
                piece_data = piece_data + b'\x00' * (piece_size - len(piece_data))
            elif len(piece_data) > piece_size:
                # Truncate if too long
                print(f"Warning: Piece {piece_index} is longer than expected, truncating.")
                piece_data = piece_data[:piece_size]
            
            # Open the file in read+write binary mode
            with open("TheFile.txt", 'r+b') as f:
                # Seek to the correct position
                f.seek(offset)
                
                # Write the piece data
                f.write(piece_data)
                
                # Verify the write was successful by reading back
                f.seek(offset)
                verification = f.read(len(piece_data))
                if verification != piece_data:
                    print(f"Warning: Verification failed for piece {piece_index}")
            
            print(f"Saved piece {piece_index} to TheFile.txt at offset {offset}")
            self.fix_file_newlines()
            return True
        except Exception as e:
            print(f"Error saving piece {piece_index}: {e}")
            return False
    
    def fix_file_newlines_remove_it(self):
        """Fix newline issues in the file"""
        with open("TheFile.txt", 'rb') as f:
            content = f.read()
        
        # Replace null bytes with newlines or appropriate characters
        fixed_content = content.replace(b'\x00\x00\x00', b'\n')
        
        # Clean up any remaining null bytes
        fixed_content = fixed_content.replace(b'\x00', b' ')
        
        # Write the cleaned content back
        with open("TheFile_fixed.dat", 'wb') as f:
            f.write(fixed_content)
        
        print("Created fixed file: TheFile_fixed.dat")

    def save_piece_to_remove2(self, piece_index, piece_data):
        """Save a piece to the complete file at the correct offset"""
        try:
            piece_size = 200  # PieceSize from your configuration
            file_size = 4409  # FileSize from your configuration
            
            # Calculate the offset where this piece should be written
            offset = piece_index * piece_size
            
            # Make sure we're not trying to write past the end of the file
            if offset + len(piece_data) > file_size:
                print(f"Warning: Piece {piece_index} would exceed file size, truncating.")
                piece_data = piece_data[:file_size - offset]
            
            # Open the file in read+write binary mode
            with open("TheFile.txt", 'r+b') as f:
                # Check if the piece already exists
                f.seek(offset)
                existing_data = f.read(piece_size)
                
                # If the piece position contains non-zero data, it might already be there
                if existing_data and not all(b == 0 for b in existing_data):
                    # Optional: Add validation to check if it's the same piece
                    print(f"Piece {piece_index} appears to already exist. Skipping.")
                    return True
                
                # Seek back to the correct position
                f.seek(offset)
                
                # Write the piece data
                f.write(piece_data)
            
            print(f"Saved piece {piece_index} to TheFile.txt at offset {offset}")
            return True
        except Exception as e:
            print(f"Error saving piece {piece_index}: {e}")
            return False

    def save_piece_to_remove(self, piece_index, piece_data):
        """Save a piece to disk"""
        # This is a placeholder - you'll need to implement this based on your file storage
        try:
            # Ensure directory exists
            os.makedirs(f"peer_{self.peer_id}", exist_ok=True)
            
            # Write the piece to a file
            filename = f"peer_{self.peer_id}/piece_{piece_index}"
            with open(filename, 'wb') as f:
                f.write(piece_data)
                
            print(f"Saved piece {piece_index} to {filename}")
            return True
        except Exception as e:
            print(f"Error saving piece {piece_index}: {e}")
            return False

    def create_request_message(self, piece_index):
        """Create a request message for a specific piece
        Format: <length prefix><message ID><piece index>
        Request message ID is 6
        """
        message = struct.pack('>IBI', 5, 6, piece_index)
        return message

    def process_request_message(self, message):
        """Process a received request message
        Returns the requested piece index
        """
        if len(message) < 9:  # Basic validation (4-byte length + 1-byte type + 4-byte index)
            return None
            
        # Unpack to get message details
        msg_length = struct.unpack('>I', message[0:4])[0]
        msg_type = message[4]
        
        if msg_type != 6:  # Not a request message
            return None
            
        # Extract the requested piece index
        piece_index = struct.unpack('>I', message[5:9])[0]
        return piece_index

    def select_piece_to_request(self, peer_id):
        """Select a random piece that the peer has but we don't"""
        if peer_id not in self.peers_bitfield_dict.keys():
            return None
            
        # Get the pieces that this peer has
        peer_has_pieces = self.peers_bitfield_dict[peer_id]
        
        # Get the pieces that we have
        our_has_pieces = self.peers_bitfield_dict[self.peer_id]
        
        # Find pieces that the peer has but we don't
        pieces_we_need = []
        for i in range(len(peer_has_pieces)):
            if peer_has_pieces[i] and not our_has_pieces[i]:
                # Check if we haven't requested this piece yet
                if i not in self.requested_pieces:
                    pieces_we_need.append(i)
                    #self.requested_pieces.append(i)
        
        if not pieces_we_need:
            return None  # No pieces to request
            
        # Select a random piece from the ones we need
        piece_index = random.choice(pieces_we_need)
        
        # Mark this piece as requested
        self.requested_pieces.append(piece_index)
        
        return piece_index
    
    # CLDHELP2 %%%%%%%%%%%%%%%%%%%%%%%%%%%%%

    def connect_to_previous_peers_toberemoved(self,peer_id, peers):
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
                
                bitfield_msg_sent=False
                while bitfield_msg_sent is False:

                    # reading peer_info from class variable earlier created.
                    peer_info=self.read_peer_info()
                    # calling creating_pieces function to be used in bitfield message.
                    bitfield_msg = self.creating_pieces(peer_info)
                    print("Created the bitfield_msg object")

                    print('bitfield_msg ',bitfield_msg)

                    client_socket.sendall(bitfield_msg)

                    bitfield_msg_sent=True
                bitfield_msg_ack=False
                while bitfield_msg_ack is False:
                    response = client_socket.recv(1024)
                    print(f"Response from {pid}: {response}")
                    
                    print("Response as ack for bitfield_msg sent Previously below")
                    print("Response from "+str(pid)+":"+str(response))

            except Exception as e:
                print(f"Failed to connect to peer {pid}: {e}") 

    

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

