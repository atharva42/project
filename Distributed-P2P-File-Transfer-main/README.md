# Distributed P2P File Transfer System

A robust peer-to-peer file sharing system implementing BitTorrent-like protocols with advanced chunk management, integrity verification, and multi-threaded architecture.

## 🚀 Key Technical Highlights

### **System Architecture**
- **Hybrid P2P Model**: Central tracker for peer discovery with decentralized file transfers
- **Multi-threaded Design**: Concurrent handling of client-server operations using custom thread pool
- **Group-based File Sharing**: Organized file distribution with role-based access control
- **Chunk-level Parallelization**: Simultaneous downloads from multiple peers for optimal throughput

### **Advanced Algorithms & Techniques**
- **Rarest-First Algorithm**: Prioritizes downloading least available chunks to improve network resilience
- **SHA-1 Integrity Verification**: File and chunk-level hash validation ensures data consistency
- **Thread Pool Implementation**: Custom thread pool manages concurrent connections efficiently
- **Socket Programming**: Low-level TCP socket implementation for reliable data transmission

### **Core Features**
- ✅ **User Management**: Secure registration, authentication, and session handling
- ✅ **Group Administration**: Create/join groups with admin controls and permission management
- ✅ **Parallel Downloads**: Multi-source chunk downloading with automatic retry mechanisms
- ✅ **Real-time Tracking**: Live download progress monitoring and peer availability status
- ✅ **Data Integrity**: Cryptographic hashing ensures file authenticity and completeness

## 🏗️ System Components

### **Tracker Server**
Centralized coordinator managing:
```cpp
// Core data structures for scalable peer management
unordered_map<string, User> users;          // O(1) user lookup
unordered_map<string, Group> groups;        // Group management
unordered_map<string, fileInfo> files;      // File metadata registry
```

### **Peer Client**
Dual-role nodes (client + server) with:
```cpp
// Efficient chunk management and progress tracking
unordered_map<string, FilesStructure> filesIHave;     // Local file registry
ThreadPool downloadThreads;                           // Concurrent download management
```

## 🔧 Technical Implementation

### **Multi-threaded Architecture**
- **Server Thread**: Handles incoming peer requests for file chunks
- **Client Thread**: Manages tracker communication and file downloads
- **Thread Pool**: Optimizes resource utilization with configurable worker threads

### **Chunk Management System**
- **512KB Chunks**: Optimal size for network efficiency and parallel processing
- **32KB TCP Segments**: Reliable transmission with timeout handling
- **Integrity Checks**: Per-chunk SHA validation with automatic retry on corruption

### **Network Protocol**
```
Download Protocol:
1. Tracker Query → Get peer list + file metadata
2. Peer Discovery → Query chunk availability from all peers
3. Rarest-First Selection → Download strategy optimization
4. Parallel Retrieval → Multi-peer simultaneous downloads
5. Integrity Verification → SHA validation + retry on failure
```

## 🚀 Quick Start

### **Build & Run**

**Tracker:**
```bash
cd tracker/
g++ tracker.cpp -o tracker
./tracker tracker_info.txt 1
```

**Peer:**
```bash
cd client/
g++ -o client client.cpp -lssl -lcrypto
./client <peer_ip:port> tracker_info.txt
```

### **Sample Commands**
```bash
create_user <user_id> <password>
login <user_id> <password>
create_group <group_id>
upload_file <file_path> <group_id>
download_file <group_id> <file_name> <dest_path>
```

## 📊 Performance Features

- **Concurrent Connections**: Multiple simultaneous peer connections
- **Bandwidth Optimization**: Intelligent peer selection and load balancing
- **Fault Tolerance**: Automatic retry mechanisms and peer failover
- **Scalable Design**: Hash-map based O(1) lookups for large-scale deployments

## 🛡️ Security & Reliability

- **Data Integrity**: SHA-1 cryptographic verification
- **Session Management**: Secure login/logout with state tracking
- **Error Handling**: Comprehensive timeout and connection failure recovery
- **Resource Management**: Proper socket cleanup and memory management

---

**Technologies**: C++, Socket Programming, Multi-threading, Cryptography (OpenSSL), TCP/IP  
**Algorithms**: Rarest-First, Thread Pooling, Hash-based Data Structures  
**Architecture**: Client-Server, Peer-to-Peer, Distributed Systems
