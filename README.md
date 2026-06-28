# Distributed Peer-to-Peer (P2P) File Sharing Network

This repository contains a robust, Python-based peer-to-peer (P2P) network designed for decentralized file sharing and high-concurrency node communication. Built to demonstrate core concepts in distributed systems, the project allows multiple autonomous peers to connect, handshake, and efficiently exchange file pieces without relying on a central server. 

This architecture serves as a foundational model for distributed data pipelines, fault-tolerant networks, and decentralized communication protocols.

---

## 🏗️ System Architecture & Repository Structure

The project is structured to simulate a multi-node distributed network. The codebase is organized into shared configurations, global logging components, and isolated peer directories[cite: 1].

### Global Network Components
*   **`Common.cfg`**: Contains the global configuration variables shared across the entire network, dictating parameters like file size and piece size[cite: 1].
*   **`logger_config.py`**: Centralized logging infrastructure to track connection states, data requests, and piece transfers across all participating nodes[cite: 1].
*   **Helper Scripts**: Includes utility scripts such as `cld_help.py` and `cld_help_2.py` to facilitate network operations[cite: 1].
*   **`ScreenshotsWorking/`**: A directory containing visual proof of successful network execution, handshakes, and data transfers, including `peer1-working.png` and `peer2-working.png`[cite: 1].

### Peer Nodes
The network simulates at least four distinct peers, housed in directories `peer_1001` through `peer_1004`[cite: 1]. Each directory acts as an independent, isolated node containing its own specific execution environment:

*   **`Peerprocess.py`**: The main executable Python script that drives the node's network connections, protocol logic, and concurrency management[cite: 1].
*   **`PeerProcessCopy.py`**: A secondary or backup operational script for the peer process[cite: 1].
*   **`Peerinfo.cfg`**: Node-specific configuration detailing the peer's ID, hostname, port, and whether it initially possesses the complete file[cite: 1].
*   **`TheFile.dat` & `TheFile.txt`**: The target data files being fragmented, requested, and shared across the network[cite: 1].
*   **Log Files**: Localized execution logs, such as `log_peer_1001.log`, detailing the granular runtime events and network state changes of that specific peer[cite: 1].

---

## 🚀 Setup & Execution

### Prerequisites
*   Python 3.x
*   A terminal environment capable of running multiple processes concurrently, or access to distinct remote machines (e.g., SSH connections to university lab servers).

### Running the Network
To properly initialize the P2P network, each peer must be started in its own process environment. 

1.  **Configure the Network:** Ensure `Common.cfg` is properly set with your desired file size and payload parameters[cite: 1]. Update `Peerinfo.cfg` in each peer directory with the correct IP addresses/hostnames and ports[cite: 1].
2.  **Initialize the Nodes:** Open a separate terminal window for each peer (1001 to 1004)[cite: 1].
3.  **Start the Processes:** Navigate into each peer's specific directory and execute the main process script. 
    ```bash
    cd peer_1001
    python Peerprocess.py 1001
    ```
    *Repeat this step for each subsequent peer, replacing the peer ID accordingly.*
4.  **Monitor the Logs:** As the nodes connect and begin transferring file pieces, you can monitor the network traffic and concurrency handling via the generated log files (e.g., `log_peer_1002.log`)[cite: 1].

---

## 🛠️ Technical Focus
*   **High-Concurrency:** Utilizes multi-threading/asynchronous I/O to handle simultaneous incoming and outgoing connections across multiple peers.
*   **Protocol Design:** Implements a custom application-layer protocol for handshaking, bitfield exchanges, and piece requests.
*   **State Management:** Dynamically tracks which peers hold which file pieces to optimize download speeds and ensure complete file reconstruction.
