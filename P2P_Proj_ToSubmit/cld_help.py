class PeerConnection:
    def __init__(self, peer_id, client_socket, addr=None, interested=False, choked=True):
        """Represents a connection to another peer"""
        self.peer_id = peer_id
        self.client_socket = client_socket
        self.addr = addr
        self.interested = interested  # Whether the remote peer is interested in our pieces
        self.choked = True  # Whether we are choking the remote peer (initially all peers are choked)
        self.download_rate = 0  # Bytes/second downloaded from this peer
        self.bytes_downloaded = 0  # Total bytes downloaded in current interval
        self.last_measurement_time = time.time()
        
    def update_download_rate(self, bytes_received):
        """Update download rate statistics when receiving data"""
        current_time = time.time()
        self.bytes_downloaded += bytes_received
        time_diff = current_time - self.last_measurement_time
        if time_diff > 0:
            self.download_rate = self.bytes_downloaded / time_diff
        
    def reset_download_stats(self):
        """Reset download statistics for a new measurement interval"""
        self.bytes_downloaded = 0
        self.last_measurement_time = time.time()


class PeerProcess:
    def __init__(self, peer_id, config_file, num_preferred_neighbors=4, unchoking_interval=30, 
                 optimistic_unchoking_interval=15):
        """Initialize the peer process with configuration options"""
        self.peer_id = peer_id
        self.config_file = config_file
        self.num_preferred_neighbors = num_preferred_neighbors  # k value
        self.unchoking_interval = unchoking_interval  # p seconds
        self.optimistic_unchoking_interval = optimistic_unchoking_interval  # m seconds
        
        self.peers_info = {}  # Dictionary to store peer information
        self.peer_connections = {}  # Dictionary to store active peer connections
        self.preferred_neighbors = set()  # Set of peer_ids that are preferred neighbors
        self.optimistically_unchoked_neighbor = None  # Peer_id of optimistically unchoked neighbor
        
        self.has_complete_file = False  # Whether this peer has the complete file
        
        # Initialize timers for unchoking intervals
        self.last_preferred_neighbors_update = time.time()
        self.last_optimistic_unchoking = time.time()
    
    def create_choke_unchoke_messages(self):
        """Create message formats for choke and unchoke messages"""
        # Message format: <length prefix><message ID>
        # Choke: ID 0, Unchoke: ID 1
        
        # Choke message - 5 bytes total
        # 1 byte for message length (4) + 1 byte for message ID (0)
        choke_msg = struct.pack('>IB', 1, 0)
        
        # Unchoke message - 5 bytes total
        # 1 byte for message length (4) + 1 byte for message ID (1)
        unchoke_msg = struct.pack('>IB', 1, 1)
        
        return choke_msg, unchoke_msg
    
    def process_choke_unchoke_message(self, message):
        """Process incoming choke or unchoke messages"""
        if len(message) < 5:  # Basic validation
            return None
            
        # Unpack the message to get length and message type
        msg_length = struct.unpack('>I', message[0:4])[0]
        msg_type = message[4]
        
        if msg_type == 0:  # Choke message
            return "CHOKE"
        elif msg_type == 1:  # Unchoke message
            return "UNCHOKE"
        else:
            return None
    
    def update_preferred_neighbors(self):
        """Select k preferred neighbors based on download rates"""
        current_time = time.time()
        
        # Only update if the unchoking interval has passed
        if current_time - self.last_preferred_neighbors_update < self.unchoking_interval:
            return
            
        self.last_preferred_neighbors_update = current_time
        
        # Find interested peers
        interested_peers = {
            pid: conn for pid, conn in self.peer_connections.items() 
            if conn.interested
        }
        
        # If we have the complete file, select randomly
        if self.has_complete_file:
            if len(interested_peers) <= self.num_preferred_neighbors:
                new_preferred = set(interested_peers.keys())
            else:
                new_preferred = set(random.sample(
                    list(interested_peers.keys()), 
                    self.num_preferred_neighbors
                ))
        else:
            # Sort peers by download rate (highest first)
            sorted_peers = sorted(
                interested_peers.items(), 
                key=lambda x: x[1].download_rate, 
                reverse=True
            )
            
            # Select top k peers
            new_preferred = set()
            for i, (pid, _) in enumerate(sorted_peers):
                if i < self.num_preferred_neighbors:
                    new_preferred.add(pid)
                else:
                    break
        
        # Process peers that need to be choked/unchoked
        choke_msg, unchoke_msg = self.create_choke_unchoke_messages()
        
        # Choke peers that are no longer preferred (except optimistically unchoked)
        for pid in self.preferred_neighbors - new_preferred:
            if pid != self.optimistically_unchoked_neighbor:
                if not self.peer_connections[pid].choked:
                    self.peer_connections[pid].choked = True
                    self.peer_connections[pid].client_socket.sendall(choke_msg)
                    print(f"Choking peer {pid}")
        
        # Unchoke new preferred peers
        for pid in new_preferred:
            if self.peer_connections[pid].choked:
                self.peer_connections[pid].choked = False
                self.peer_connections[pid].client_socket.sendall(unchoke_msg)
                print(f"Unchoking peer {pid} as preferred neighbor")
        
        # Update our preferred neighbors set
        self.preferred_neighbors = new_preferred
        
        # Reset download statistics for the next interval
        for conn in self.peer_connections.values():
            conn.reset_download_stats()
            
        print(f"Updated preferred neighbors: {self.preferred_neighbors}")
    
    def update_optimistically_unchoked_neighbor(self):
        """Randomly select one peer to be optimistically unchoked"""
        current_time = time.time()
        
        # Only update if the optimistic unchoking interval has passed
        if current_time - self.last_optimistic_unchoking < self.optimistic_unchoking_interval:
            return
            
        self.last_optimistic_unchoking = current_time
        
        # Find interested but choked peers
        candidates = [
            pid for pid, conn in self.peer_connections.items()
            if conn.interested and conn.choked and pid not in self.preferred_neighbors
        ]
        
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
            self.peer_connections[old_opt].client_socket.sendall(choke_msg)
            print(f"Choking previous optimistically unchoked peer {old_opt}")
        
        # Unchoke the new optimistically unchoked neighbor
        self.optimistically_unchoked_neighbor = new_optimistic
        self.peer_connections[new_optimistic].choked = False
        _, unchoke_msg = self.create_choke_unchoke_messages()
        self.peer_connections[new_optimistic].client_socket.sendall(unchoke_msg)
        print(f"Optimistically unchoking peer {new_optimistic}")
    
    def process_intereseted_message(self, message):
        """Process interested or not interested messages"""
        if len(message) < 5:
            return None, None, None
            
        # Unpack to get message length and type
        message_length = struct.unpack('>I', message[0:4])[0]
        message_type = message[4]
        
        # Extract peer_id from the message if available
        peer_id = None
        if len(message) > 5:
            # Assuming peer_id is encoded in the rest of the message
            peer_id = message[5:].decode()
        
        return message_length, message_type, peer_id
        
    def handle_client_connection(self, client_socket, addr):
        """Modified handler for client connections with choke/unchoke support"""
        print(f"Connected by {addr}")
        
        ack_sent = False
        
        # Initial communication remains the same...
        while ack_sent is not True:
            data = client_socket.recv(1024)
            print('receiving data from client_socket object')
            
            if not data:
                break
                
            print(f"Received from {addr}: {data}")
            
            # Send acknowledgement
            client_socket.sendall(b"ACK")
            print("sent ACK msg as acknowledgement!")
            
            ack_sent = True
        
        # Handshake and bitfield exchange remains the same...
        while ack_sent is True:
            handshake_msg = self.create_handshake_message(peer_id=self.peer_id)
            print("Created handshake_msg::" + str(handshake_msg))
            
            client_socket.sendall(handshake_msg)
            print("Sending handshake_msg to client peer...")
            
            handshake_ack_received = False
            while handshake_ack_received is False:
                data = client_socket.recv(100000)
                if data is not None:
                    print("HANDSHAKE ACK received from client side...")
                    handshake_ack_received = True
                    break
            
            # Handle handshake response
            data = client_socket.recv(100000)
            if not data:
                break
                
            print(f"Received from {addr} handshake message: {data}")
            
            result = self.verify_handshake(data)
            print("verify handshake msg called!")
            
            if result is not None:
                handshake_ack = "HANDSHAKE_VERIFIED"
                client_socket.sendall(handshake_ack.encode())
                print("handshake msg verified by server")
                
                # Send bitfield message
                print("SENDING BITFIELD MSG NOW FROM SERVER")
                peer_info = self.read_peer_info()
                
                bitfield_msg = self.creating_pieces(peer_info)
                print('bitfield_msg', bitfield_msg)
                
                peer_id, bitfield_payload = self.process_bitfield_msg(bitfield_msg)
                has_pieces = self.extract_has_pieces(bitfield_payload)
                self.peers_bitfield_dict[peer_id] = has_pieces
                
                client_socket.sendall(bitfield_msg)
                print("bitfield msg sent.")
                break
                
            ack_sent = False
            break
        
        # Wait for bitfield message from client
        bitfield_msg_response = False    
        while bitfield_msg_response is False:
            print("waiting for bitfield msg from client...")
            
            response = client_socket.recv(100000)
            print(f"bitfield msg received from client side -- {addr}: {response}")
            
            peer_id_sent, bitfield_payload = self.process_bitfield_msg(response)
            print('peer_id from where bitfield was sent =', peer_id_sent)
            print('bitfield_payload of bitfield_msg=', bitfield_payload)
            
            has_pieces = self.extract_has_pieces(bitfield_payload)
            self.peers_bitfield_dict[peer_id_sent] = has_pieces
            
            # Create a peer connection object for this peer
            self.peer_connections[peer_id_sent] = PeerConnection(
                peer_id=peer_id_sent,
                client_socket=client_socket,
                addr=addr,
                interested=False,
                choked=True
            )
            
            bitfield_msg_response = True
            
        print("**************")
        print(f"PRINTING OUT self.peers_bitfield_dict for {self.peer_id}", self.peers_bitfield_dict)
        
        # Handle interested/not interested messages
        interested_status_flag = False
        while interested_status_flag is False:
            response = client_socket.recv(100000)
            print(f'interested or not interested msg received from client...')
            
            message_length, message_type, peer_id = self.process_intereseted_message(response)
            print("message_length and message_type received:", message_length, message_type)
            
            if int(message_type) == 2:
                print(f"{peer_id} is INTERESTED")
                # Update the peer's interest status
                if peer_id_sent in self.peer_connections:
                    self.peer_connections[peer_id_sent].interested = True
            elif int(message_type) == 3:
                print(f"{peer_id} is NOT INTERESTED")
                if peer_id_sent in self.peer_connections:
                    self.peer_connections[peer_id_sent].interested = False
                    
            # After receiving interest status, we can check if we should update our preferred neighbors
            self.update_preferred_neighbors()
            self.update_optimistically_unchoked_neighbor()
            
            interested_status_flag = True
            break
        
        # Send our own interested status
        interested = self.interested_not_interested(peer_id_sent)
        print("Result of interested_not_interested:", interested)
        
        if interested:
            msg = self.create_interested_message()
            client_socket.sendall(msg)
        else:
            msg = self.create_notinterested_message()
            client_socket.sendall(msg)
            
        # Start a thread to periodically check and update choking status
        threading.Thread(target=self._periodic_unchoking_updates, daemon=True).start()
        
        # Continue with piece requests and transfers...
        # This would handle the actual file transfers after choking decisions are made
        
    def _periodic_unchoking_updates(self):
        """Periodically update preferred neighbors and optimistically unchoked neighbor"""
        while True:
            self.update_preferred_neighbors()
            self.update_optimistically_unchoked_neighbor()
            # Sleep for a shorter time than the intervals to ensure we don't miss deadlines
            time.sleep(min(self.unchoking_interval, self.optimistic_unchoking_interval) / 2)
            
    def connect_to_previous_peers(self, peer_id, peers):
        """Modified function to connect to previous peers with choke/unchoke support"""
        for pid, peer in peers.items():
            if pid >= peer_id:
                break
                
            try:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                print('Client socket created')
                
                client_socket.connect((peer["hostname"], peer["port"]))
                print(f"Connected to peer {pid} at {peer['hostname']}:{peer['port']}")
                
                # Create a peer connection object for this peer
                self.peer_connections[pid] = PeerConnection(
                    peer_id=pid,
                    client_socket=client_socket,
                    addr=(peer["hostname"], peer["port"]),
                    interested=False,
                    choked=True
                )
                
                # Initial handshake remains the same
                client_socket.sendall(f"Hello from {peer_id}".encode())
                
                ack_for_first_msg = False
                while ack_for_first_msg is False:
                    response = client_socket.recv(1024)
                    print("waiting for first ACK from server side...")
                    print(f"Response from {pid}: {response}")
                    if response is not None:
                        ack_for_first_msg = True
                
                # Handle handshake
                while True:
                    response = client_socket.recv(1024)
                    print(f"Response from {pid}: {response}")
                    
                    result = self.verify_handshake(response)
                    
                    if result == True:
                        print("HANDSHAKE MSG verified...")
                        handshake_ack = "HANDSHAKE_VERIFIED"
                        client_socket.sendall(handshake_ack.encode())
                        print('handshake message received verified')
                        break
                        
                # Send our handshake
                handshake_msg_sent = False
                while handshake_msg_sent is False:
                    handshake_msg = self.create_handshake_message(peer_id=self.peer_id)
                    client_socket.sendall(handshake_msg)
                    print("Sent handshake msg from client_socket")
                    handshake_msg_sent = True
                
                # Wait for handshake acknowledgement
                handshake_ack_from_server = False
                while handshake_ack_from_server is False:
                    response = client_socket.recv(1024)
                    print(f"Response from {pid}: {response}")
                    if response is not None:
                        print('ACK received for handshake msg')
                        handshake_ack_from_server = True
                
                # Process bitfield message from server
                bitfield_msg_received_from_server = False
                while bitfield_msg_received_from_server is False:
                    response = client_socket.recv(1024)
                    print(f"bitfield msg received from server -- {pid}: {response}")
                    
                    if response is not None:
                        peer_id_sent, bitfield_payload = self.process_bitfield_msg(response)
                        print('peer_id from where bitfield was sent =', peer_id_sent)
                        print('bitfield_payload of bitfield_msg=', bitfield_payload)
                        
                        has_pieces = self.extract_has_pieces(bitfield_payload)
                        self.peers_bitfield_dict[peer_id_sent] = has_pieces
                        print("self.peers_bitfield_dict:", self.peers_bitfield_dict)
                        
                        bitfield_msg_received_from_server = True
                
                # Send our bitfield
                bitfield_msg_sent = False
                while bitfield_msg_sent is False:
                    peer_info = self.read_peer_info()
                    bitfield_msg = self.creating_pieces(peer_info)
                    
                    print('bitfield_msg ', bitfield_msg)
                    peer_id, bitfield_payload = self.process_bitfield_msg(bitfield_msg)
                    
                    has_pieces = self.extract_has_pieces(bitfield_payload)
                    self.peers_bitfield_dict[peer_id] = has_pieces
                    
                    client_socket.sendall(bitfield_msg)
                    bitfield_msg_sent = True
                    
                print("****************")
                print(f"PRINTING OUT self.peers_bitfield_dict for {self.peer_id}", self.peers_bitfield_dict)
                
                # Send interested/not interested message
                interested = self.interested_not_interested(peer_id_sent)
                
                if interested:
                    msg = self.create_interested_message()
                    client_socket.sendall(msg)
                    # Update our interest status for this peer
                    self.peer_connections[pid].interested = True
                else:
                    msg = self.create_notinterested_message()
                    client_socket.sendall(msg)
                
                # Process incoming interested/not interested message
                interested_status_flag = False
                while interested_status_flag is False:
                    response = client_socket.recv(100000)
                    print(f'interested/not interested msg received')
                    
                    message_length, message_type, peer_id = self.process_intereseted_message(response)
                    print("message type:", message_type)
                    
                    if int(message_type) == 2:
                        print(f"{peer_id} is INTERESTED")
                        # Update the peer's interest status in our records
                        self.peer_connections[pid].interested = True
                    elif int(message_type) == 3:
                        print(f"{peer_id} is NOT INTERESTED")
                        self.peer_connections[pid].interested = False
                        
                    interested_status_flag = True
                    break
                    
                # After establishing connections with all peers, we can start choking/unchoking process
                self.update_preferred_neighbors()
                self.update_optimistically_unchoked_neighbor()
                
                # Now we can start handling requests for pieces, but we need to check if we're choked or not
                
            except Exception as e:
                print(f"Error connecting to peer {pid}: {e}")
                
    def handle_download_from_peer(self, peer_id, piece_data):
        """Update download statistics when receiving pieces from a peer"""
        if peer_id in self.peer_connections:
            bytes_received = len(piece_data)
            self.peer_connections[peer_id].update_download_rate(bytes_received)
            
    def create_request_message(self, piece_index):
        """Create a request message for a specific piece"""
        # Message format: <length prefix><message ID><piece index>
        # Request message ID is 6
        message = struct.pack('>IBI', 5, 6, piece_index)
        return message
        
    def process_request_message(self, message):
        """Process a request message for a piece"""
        if len(message) < 8:  # Basic validation
            return None
            
        # Unpack to get message details
        msg_length = struct.unpack('>I', message[0:4])[0]
        msg_type = message[4]
        
        if msg_type != 6:  # Not a request message
            return None
            
        # Extract the requested piece index
        piece_index = struct.unpack('>I', message[5:9])[0]
        return piece_index
        
    def handle_request_message(self, peer_id, message):
        """Handle request messages from peers"""
        piece_index = self.process_request_message(message)
        
        if piece_index is None:
            return
            
        # Check if this peer is unchoked before sending data
        if peer_id in self.peer_connections and (
            peer_id in self.preferred_neighbors or 
            peer_id == self.optimistically_unchoked_neighbor
        ):
            if not self.peer_connections[peer_id].choked:
                # Only send pieces if the peer is unchoked
                piece_data = self.read_piece(piece_index)
                if piece_data:
                    piece_msg = self.create_piece_message(piece_index, piece_data)
                    self.peer_connections[peer_id].client_socket.sendall(piece_msg)
                    print(f"Sent piece {piece_index} to peer {peer_id}")
        else:
            print(f"Ignoring request from choked peer {peer_id}")