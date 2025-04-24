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

def create_piece_message(self, piece_index, piece_data):
    """Create a piece message containing actual file data
    Format: <length prefix><message ID><piece index><block data>
    Piece message ID is 7
    """
    # Calculate message length: 4 bytes for index + len(piece_data)
    msg_length = 4 + len(piece_data)
    
    # Pack the message
    message = struct.pack('>IBI', msg_length, 7, piece_index)
    
    # Append the actual piece data
    message += piece_data
    
    return message

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

def select_piece_to_request(self, peer_id):
    """Select a random piece that the peer has but we don't"""
    if peer_id not in self.peers_bitfield_dict:
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
    
    if not pieces_we_need:
        return None  # No pieces to request
        
    # Select a random piece from the ones we need
    piece_index = random.choice(pieces_we_need)
    
    # Mark this piece as requested
    self.requested_pieces.add(piece_index)
    
    return piece_index

def handle_unchoking(self, peer_id):
    """Handle being unchoked by a peer - start requesting pieces"""
    print(f"Starting to request pieces from peer {peer_id}")
    
    # Create a new thread to handle piece requests
    # This ensures we don't block other operations
    threading.Thread(
        target=self._request_pieces_from_peer,
        args=(peer_id,),
        daemon=True
    ).start()

def request_pieces_from_peer(self, peer_id):
    """Request pieces from a specific peer - runs in a separate thread"""
    # Get the socket for this peer
    if peer_id not in self.peer_connections:
        print(f"Cannot request pieces: peer {peer_id} not connected")
        return
        
    client_socket = self.peer_connections[peer_id].client_socket
    
    # Track if we're still interested in this peer's pieces
    still_interested = True
    
    while still_interested:
        # Check if we're still unchoked by this peer
        if peer_id not in self.peer_connections or self.peer_connections[peer_id].choked:
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
                    self.peer_connections[peer_id].interested = False
                    print(f"Sent NOT_INTERESTED to peer {peer_id}")
                except:
                    print(f"Error sending NOT_INTERESTED to peer {peer_id}")
            break
            
        # Send request for the selected piece
        request_msg = self.create_request_message(piece_index)
        try:
            client_socket.sendall(request_msg)
            print(f"Requested piece {piece_index} from peer {peer_id}")
        except:
            print(f"Error requesting piece {piece_index} from peer {peer_id}")
            break
            
        # Wait for the piece response
        piece_received = False
        start_time = time.time()
        
        while not piece_received:
            # Add a timeout to prevent waiting forever
            if time.time() - start_time > 30:  # 30 seconds timeout
                print(f"Timeout waiting for piece {piece_index} from peer {peer_id}")
                # Remove the piece from our requested set
                self.requested_pieces.remove(piece_index)
                break
                
            # Check if we've been choked while waiting
            if peer_id not in self.peer_connections or self.peer_connections[peer_id].choked:
                print(f"Choked while waiting for piece {piece_index} from peer {peer_id}")
                # Remove the piece from our requested set
                self.requested_pieces.remove(piece_index)
                return
                
            try:
                # Non-blocking receive to check for data
                client_socket.setblocking(False)
                response = client_socket.recv(1024000)  # Large buffer for piece data
                client_socket.setblocking(True)
                
                if not response:
                    # Socket closed or error
                    time.sleep(0.1)  # Small delay before retry
                    continue
                    
                # Process the response
                piece_index_rcv, piece_data = self.process_piece_message(response)
                
                if piece_index_rcv is not None:
                    print(f"Received piece {piece_index_rcv} from peer {peer_id}")
                    
                    # Verify this is the piece we requested
                    if piece_index_rcv == piece_index:
                        # Save the piece
                        self.save_piece(piece_index, piece_data)
                        
                        # Update our bitfield
                        self.peers_bitfield_dict[self.peer_id][piece_index] = True
                        
                        # Update download statistics IMPLEMENT LATER...
                        #self.peer_connections[peer_id].update_download_rate(len(piece_data))
                        
                        # Mark that we've received this piece
                        piece_received = True
                        
                        # Check if we have the complete file
                        if all(self.peers_bitfield_dict[self.peer_id]):
                            self.has_complete_file = True
                            print("We now have the complete file!")
                    else:
                        print(f"Received unexpected piece {piece_index_rcv}, expected {piece_index}")
            except BlockingIOError:
                # No data available yet
                time.sleep(0.1)
            except Exception as e:
                print(f"Error receiving piece: {e}")
                break

def handle_request_message(self, peer_id, message):
    """Handle a piece request from another peer"""
    piece_index = self.process_request_message(message)
    
    if piece_index is None:
        return
        
    # Only send piece if this peer is unchoked
    if peer_id not in self.peer_connections:
        print(f"Cannot handle request: peer {peer_id} not connected")
        return
        
    if self.peer_connections[peer_id].choked:
        print(f"Ignoring request from choked peer {peer_id}")
        return
        
    # Check if we have this piece
    if not self.peers_bitfield_dict[self.peer_id][piece_index]:
        print(f"We don't have requested piece {piece_index}")
        return
        
    # Retrieve the piece data
    piece_data = self.read_piece(piece_index)
    
    if piece_data:
        # Create and send the piece message
        piece_msg = self.create_piece_message(piece_index, piece_data)
        try:
            self.peer_connections[peer_id].client_socket.sendall(piece_msg)
            print(f"Sent piece {piece_index} to peer {peer_id}")
        except Exception as e:
            print(f"Error sending piece {piece_index} to peer {peer_id}: {e}")

def read_piece(self, piece_index):
    """Read a piece from disk"""
    # This is a placeholder - you'll need to implement this based on your file storage
    # It should return the raw bytes of the requested piece
    try:
        filename = f"peer_{self.peer_id}/piece_{piece_index}"
        with open(filename, 'rb') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading piece {piece_index}: {e}")
        return None

def save_piece(self, piece_index, piece_data):
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

# Additional initialization code for PeerProcess class
def __init__(self, peer_id, config_file, num_preferred_neighbors=4, unchoking_interval=30, 
             optimistic_unchoking_interval=15):
    # Add to existing initialization
    self.peer_id = peer_id
    # ... other existing initialization ...
    
    # Add these new attributes
    self.requested_pieces = set()  # Keep track of pieces we have requested
    self.has_complete_file = False

# Update the process_choke_unchoke_message function to trigger piece requests
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

# Update the message handling code in connect_to_previous_peers
# Note: Only showing the part that needs to be added
def handle_incoming_message(self, message, peer_id):
    """Process any incoming message and take appropriate action"""
    if len(message) < 5:
        return
        
    # Get message type
    msg_type = message[4]
    
    if msg_type == 0:  # CHOKE
        print(f"Got CHOKE from peer {peer_id}")
        # Update our records
        if peer_id in self.peer_connections:
            self.peer_connections[peer_id].choked = True
    
    elif msg_type == 1:  # UNCHOKE
        print(f"Got UNCHOKE from peer {peer_id}")
        # Update our records
        if peer_id in self.peer_connections:
            self.peer_connections[peer_id].choked = False
            # Start requesting pieces
            self.handle_unchoking(peer_id)
    
    elif msg_type == 6:  # REQUEST
        print(f"Got REQUEST from peer {peer_id}")
        self.handle_request_message(peer_id, message)
    
    elif msg_type == 7:  # PIECE
        # Processing of piece messages is handled in _request_pieces_from_peer
        pass
    
    # Add handlers for other message types as needed