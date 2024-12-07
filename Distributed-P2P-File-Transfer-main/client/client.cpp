// client try to connect to tracker or peer what happen on connectipon refuse
// if tracker goes down what happened with client thread and all thread s
//  If user has  try to login with other ip port then updating it, and along with file info storing that info ias well
// what is user is already logged in and user do create_user -> vheck in whole user table that with same ip is someone already logged in 

// check before upload and download that user has part of group or not and part of accepted user list otherwise restrict it

// for list files it is possible that it can not fit into 1024 size, so may be need to share multiple files

// no need of storing sha of every chunk - optimize it
// when first piece got downloaded initilize chunks_I have vector with "" -> and fill that chunk info

// Is send and recv allowed ??

// At all places we are sending more bytes though message is small

// It is not coming from 3rd peer


//  send exit at every socket close

// g++ -o client client.cpp  -lssl -lcrypto

#include <iostream>
#include <thread>
#include <arpa/inet.h>
#include <sys/types.h>   //header file contains definition of a number of data types used in system call and helper file for sys/socket.h and netinet/in.h
#include <sys/socket.h>     // Includes a number of definition of structure needed for socket e.g. defines the socketaddr structur(this structure contains port family ...)
#include <netinet/in.h>     // Constants and structure needed for internet domain address e.g. socketaddr_in()
#include <stdlib.h>         // defines four variable types,saveral macros and various functions for performing general functions e.g. int atoi(const char *str)-> convert string to int 
#include <netdb.h>
#include <ctype.h>
#include <unistd.h>  // open,close,read
#include <fcntl.h> // used for argument of open system call
#include <sys/stat.h> //mkdir,stat ,chmod
#include <vector>
#include <cstring> // to convert string to char *
#include <unordered_map>
#include <openssl/sha.h> // For calculating sha hash value
#include <queue>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <sys/select.h> 
#include <stdlib.h>
#include <unordered_set>
#define CHUNK_SIZE_TCP 32768
using namespace std;

class ThreadPool {
public:
    ThreadPool(size_t numThreads) {
        for (size_t i = 0; i < numThreads; ++i) {
            workers.emplace_back([this] {
                while (true) {
                    std::function<void()> task;

                    {
                        std::unique_lock<std::mutex> lock(queueMutex);
                        condition.wait(lock, [this] {
                            return !tasks.empty() || stop;
                        });

                        if (stop && tasks.empty()) {
                            return;
                        }

                        task = std::move(tasks.front());
                        tasks.pop();
                    }

                    task();
                }
            });
        }
    }

    // Add a task to the thread pool
    template <class F>
    void AddTask(F&& task) {
        {
            std::unique_lock<std::mutex> lock(queueMutex);
            tasks.emplace(std::forward<F>(task));
        }
        condition.notify_one();
    }

    // Wait for all tasks to complete and stop the thread pool
    void WaitAndStop() {
        {
            std::unique_lock<std::mutex> lock(queueMutex);
            stop = true;
        }
        condition.notify_all();

        for (std::thread& worker : workers) {
            worker.join();
        }
    }

private:
    std::vector<std::thread> workers;
    std::queue<std::function<void()>> tasks;
    std::mutex queueMutex;
    std::condition_variable condition;
    bool stop = false;
};

class FilesStructure{
    public :
    string file_name;
    string file_path;
    string sha;
    long long int total_chunks;
    long long int total_size;
    vector<string> chunks_I_have;
    long long int no_of_chunks_I_have;

    FilesStructure()
    {
        file_name = "";
        file_path = "";  
        sha = "";
        total_chunks = 0;
        total_size = 0;
        file_path = "";
    }
};

// <sha,obj of filestructur>
unordered_map<string,FilesStructure> filesIHave;

// When file start downloading
// <sha,{group_id,file_name}>
unordered_map<string,pair<string,string>> downloadStart;
// When any one of the chunk got downloaded
// <sha,{group_id,file_name}>
unordered_map<string,pair<string,string>> downloadPending;
// When ffike fully downloaded
// <sha,{group_id,file_name}>
vector<pair<string,string>> downloadComplete;

// class currentFileProcess{
//     public:
//     vector<pair<string,string>>    
// };

struct PairHash {
    template <class T1, class T2>
    std::size_t operator () (const std::pair<T1, T2>& p) const {
        auto h1 = std::hash<T1>{}(p.first);
        auto h2 = std::hash<T2>{}(p.second);
        return h1 ^ h2;
    }
};

void printFileTable()
{
    cout << endl;
    cout << "//////////////////////////////////// File //////////////////////////////////" << endl;
    for(auto x : filesIHave)
    {
        cout << x.first << " " << x.second.file_name<< " " << x.second.file_path << " " << x.second.no_of_chunks_I_have << " " << x.second.total_chunks << " " << x.second.total_size << endl;
    }
    cout << "//////////////////////////////////// File //////////////////////////////////" << endl;
    cout << endl;
}

void printShowDownloads()
{
    unordered_set<pair<string,string>,PairHash> pending;
    // unordered_set<pair<string,string>,PairHash> completed;
    //Taking download start and download pending and putting it in pending result
    for(auto x : downloadStart)
    {
        pending.insert({x.second.first,x.second.second});
    }
    for(auto x : downloadPending)
    {
        pending.insert({x.second.first,x.second.second});
    }
    
    // for download complete we can directly take it form downloadComplete vector

    cout << endl;
    cout << "//////////////////////////////////// Downloads //////////////////////////////////" << endl;
    for(auto x : pending)
    {
        cout << "[D] : " << "[ " << x.first << " ] " << x.second << endl; 
    }
    for(auto x : downloadComplete)
    {
        cout << "[C] : " << "[ " << x.first << " ] " << x.second << endl; 
    }
    cout << "//////////////////////////////////// Downloads //////////////////////////////////" << endl;
    cout << endl;
}

vector<string> tokenize(string commandString)
{
    string temp = "";
    vector<string> command;
    int bufferLength = commandString.length();
    
    // spliting input command by spacce
    for(int i=0;i<bufferLength;i++)
    {
        if(commandString[i] == ' ')
        {
            command.push_back(temp);
            temp = "";
        }
        else
        {
            temp += commandString[i];
        }
    }
    if(temp != "")
        command.push_back(temp);

    return command;

}

string calculateShaofFile(string filePath)
{
    string sha = "";
    int fileDescriptor = open(filePath.c_str(), O_RDONLY);

    if (fileDescriptor < 0) {
        std::cerr << "Error opening file" << std::endl;
        return sha;
    }

    SHA_CTX shaContext;
    SHA1_Init(&shaContext);

    unsigned char buffer[512*1024];
    ssize_t bytesRead;

    while ((bytesRead = read(fileDescriptor, buffer, sizeof(buffer)) > 0)) {
        SHA1_Update(&shaContext, buffer, bytesRead);
    }

    close(fileDescriptor);

    unsigned char sha1Result[SHA_DIGEST_LENGTH];
    SHA1_Final(sha1Result, &shaContext);

    for (int i = 0; i < SHA_DIGEST_LENGTH; ++i) {
        char hex[3];
        sprintf(hex, "%02x", sha1Result[i]);
        sha += hex;
    }
    return sha;
}

string calculateShaofChunk(string buffer)
{
    // cout << "calculating sha of chunl : "  << buffer << endl;
    string sha = "";
    SHA_CTX shaContext;
    SHA1_Init(&shaContext);

    SHA1_Update(&shaContext, buffer.c_str(), buffer.length());

    unsigned char sha1Result[SHA_DIGEST_LENGTH];
    SHA1_Final(sha1Result, &shaContext);

    for (int i = 0; i < SHA_DIGEST_LENGTH; ++i) {
        char hex[3];
        sprintf(hex, "%02x", sha1Result[i]);
        sha += hex;
    }
    return sha;
}

void printIncomingCommandTokenized(vector<string> &command)
{
    cout << endl;
    cout << "/////////////// Incoming command tokenized /////////////////////" << endl;
    for(auto x : command)
    {
        cout << x << " ";
    }
    cout << endl;
    cout << "/////////////// Incoming command tokenized /////////////////////" << endl;
    cout << endl;
}

void inComingClientRequest(int clientSocket) {

    char buffer[512*1024];
    int bytesReceived;
    send(clientSocket,"You are connected to tracker, I am here to serve you",52,0);

    while ((bytesReceived = read(clientSocket, buffer, sizeof(buffer))) > 0) {
        
        vector<string> command = tokenize(buffer);
        
        //Printing incoming command tokenized
        printIncomingCommandTokenized(command);
        
        if(command.size() == 0)
        {
            cerr << "Invalid Command" << endl;
            send(clientSocket,"Invalid Command",1024,0);
            continue;
        }
        // Give how much chunks I have
        else if(command[0] == "give_file_chunks_info")
        {
            // Incoming request give_file_chunks_info sha
            if(command.size() < 2 || command[1] == "")
            {
                cout << "Sorry! unable to entertain request" << endl;
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                if(filesIHave.find(command[1]) != filesIHave.end())
                {
                    string response = "success ";
                    int len = filesIHave[command[1]].no_of_chunks_I_have;
                    cout << "len " << len << endl;
                    for(int i=0;i<len;i++)
                    {
                        if(filesIHave[command[1]].chunks_I_have[i]!="")
                            response += to_string(i) + " ";
                    }
                    cout << "response sending to : " <<response << endl; 
                    send(clientSocket,response.c_str(),512*1024,0);
                }
                else
                {
                    cout << "Sorry! I don't have this file" << endl;
                    send(clientSocket,"Sorry! I don't have this file",1024,0);
                }
            }
        }
        // incoming request : give_chunk sha chunkNo
        else if(command[0] == "give_chunk")
        {
            if(command.size() < 3)
            {
                cout << "Sorry! unable to entertain request" << endl;
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                if(filesIHave.find(command[1]) != filesIHave.end())
                {
                    char buffer1[512*1024];
                    long int CHUNK_SIZE = 512*1024;
                    int bReceived = 0;
                    string res1 = "";
                    int readFileDescriptor = open(filesIHave[command[1]].file_path.c_str(),O_RDONLY);
                    if(readFileDescriptor < 0)
                    {
                        cerr << "at peer Error while opening input file " << endl;
                    }
                    else
                    {
                        // lseek(readFileDescriptor, stoi(command[2]) * CHUNK_SIZE, SEEK_SET);
                        // bzero(buffer1,sizeof(buffer1));
                        // int readFileCount = read(readFileDescriptor,buffer1,CHUNK_SIZE);
                        // // cout << "chunk " << buffer1 << endl;
                        // cout << "Sending chunk to ........." << endl;
                        // string res(buffer1);
                        // send(clientSocket,(to_string(readFileCount)).c_str(),1024,0);
                        // int a = send(clientSocket,buffer1,readFileCount,0);
                        // cout << "sent " << a << endl;


                        lseek(readFileDescriptor, stoi(command[2]) * CHUNK_SIZE, SEEK_SET);
                        bzero(buffer1,sizeof(buffer1));
                        int readFileCount = read(readFileDescriptor,buffer1,CHUNK_SIZE);
                        // cout <<"read from file : " <<  readFileCount << endl;
                        int smallChunks = (readFileCount-1/CHUNK_SIZE_TCP)+1;
                        string res(buffer1,readFileCount);
                        res1 = res;
                        // cout << "//////file from sender//////////" << endl;
                        // cout << res << endl;
                        // cout << "//////file from sender//////////" << endl;
                        // cout << "After whole chunk " << res.length() << endl;
                        // How many small chunks I will send
                        send(clientSocket,(to_string(readFileCount)).c_str(),1024,0);

                        int totalLength = readFileCount;
                        int alreadyRead = 0;

                        // for(int i=0;i<smallChunks;i++)
                        // {
                        //     int needToRead = (totalLength-alreadyRead) < CHUNK_SIZE_TCP ? totalLength-alreadyRead : CHUNK_SIZE_TCP;
                        //     cout << (totalLength-alreadyRead) << " "<<needToRead << endl;
                        //     cout << "Sending chunk to ........." << endl;
                        //     string data = res.substr(i*CHUNK_SIZE_TCP,needToRead);
                        //     int a = send(clientSocket,data.c_str(),data.length(),0);
                        //     cout << "sent " << a << endl;
                        //     alreadyRead += data.length();
                        // }
                        int readAtOnce = CHUNK_SIZE_TCP;
                        int leftToRead = readFileCount;
                        int i=0;
                        while(leftToRead > 0)
                        {
                            // cout << "AT START " << readAtOnce << " " << "left to read " << leftToRead << endl; 
                            readAtOnce = (readAtOnce < leftToRead) ? readAtOnce : leftToRead;
                            // cout << (totalLength-alreadyRead) << " "<<needToRead << endl;
                            // cout << i << " readAtOnce : " << readAtOnce << " " << endl;
                            // cout << "Sending chunk to ........." << (res.substr(i*CHUNK_SIZE_TCP,readAtOnce)).length() << endl;

                            string data = res.substr(i*CHUNK_SIZE_TCP,readAtOnce);
                            // cout << "after substring : " <<data.length();
                            int a = send(clientSocket,data.c_str(),data.length(),0);
                            // cout << "sent " << a << endl;
                            leftToRead -= data.length();
                            i++;
                        }
                        // cout << "Sent i tims " << i << endl;
                        
                    }


                    bzero(buffer1,sizeof(buffer1));
                    bReceived = recv(clientSocket, buffer1, sizeof(buffer1), 0);
                    // cout << "buffer 1 " << buffer1 << endl;
                    bzero(buffer1,sizeof(buffer1));

                    // string response = filesIHave[command[1]].chunks_I_have[stoi(command[2])];
                    string response = calculateShaofChunk(res1);
                    // cout << "response sending to : " <<response << endl; 
                    // sending chunk
                    int a = send(clientSocket,response.c_str(),response.length(),0);
                    // cout << "sha sent " << a << endl;

                    // reciving ok message;
                    // char buffer1[512*1024];
                    // int bReceived = 0;
                    
                    // long int CHUNK_SIZE = 512*1024;

                    // int readFileDescriptor = open(filesIHave[command[1]].file_path.c_str(),O_RDONLY);
                    // if(readFileDescriptor < 0)
                    // {
                    //     cerr << "at peer Error while opening input file " << endl;
                    // }
                    // else
                    // {
                    //     lseek(readFileDescriptor, stoi(command[2]) * CHUNK_SIZE, SEEK_SET);
                    //     bzero(buffer1,sizeof(buffer1));
                    //     int readFileCount = read(readFileDescriptor,buffer1,CHUNK_SIZE);
                    //     cout << "chunk " << buffer1 << endl;
                    //     cout << "Sending chunk to ........." << endl;
                    //     string res(buffer1);
                    //     int a = send(clientSocket,buffer1,readFileCount,0);
                    //     cout << "sent " << a << endl;
                    // }

                }
                
                else
                {
                    cout << "Sorry! I don't have this file" << endl;
                    send(clientSocket,"Sorry! I don't have this file",1024,0);
                }
            }
        }
        else if(command[0] == "exit")
        {
            // cout << "EXIT" << endl;
            break;
        }
        else
        {
            cout << "Invalid Commands" << endl;
            send(clientSocket,"Invalid Command",1024,0);
        }
    }

    // Close the client socket
    close(clientSocket);
}

bool isUserIdSet(string userId)
{
    if(userId == "")
        return false;
    return true;
}

string extractFileNameFromPath(string filePath)
{
    // cout << "get file path : " << filePath << endl;
    string fileName = "";
    int len = filePath.length();
    for(int i=len-1;i>=0;i--)
    {
        if(filePath[i] == '/')
            break;
        fileName = filePath[i] + fileName;
    }
    // cout << "filename" << fileName << endl;
    return fileName;
}

vector<pair<int,pair<string,string>>> connectWithClientAndGetChunkInfo(int i,string ip,string port,string sha)
{
    // cout << i << " " << ip << " " << port << endl;
    cout << "To get chunk data contacting client : IP : " << ip << " PORT : " << port << endl;
    
    //<{chunkno,{ip,port}}>
    vector<pair<int,pair<string,string>>> response;

    int peerServerSocket = socket(AF_INET, SOCK_STREAM, 0);
    if (peerServerSocket == -1) {
        perror("Socket creation failed with peer");
        return response;
    }

    int peerPort = stoi(port);

    sockaddr_in serverAddr;
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(peerPort);

    if (inet_pton(AF_INET, ip.c_str(), &serverAddr.sin_addr) <= 0) {
        perror("Invalid address");
        close(peerServerSocket);
        return response;
    }

    if (connect(peerServerSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) == -1) {
        perror("Connection to peer failed");
        close(peerServerSocket);
        return response;
    }

    int bytesReceived = 0;
    char buffer[512*1024];
    bytesReceived = recv(peerServerSocket, buffer, sizeof(buffer), 0);
    // cout << buffer << endl;

    string arguments = "";
    arguments += "give_file_chunks_info";
    arguments += " " + sha;

    send(peerServerSocket,arguments.c_str(),1024,0);

    bzero(buffer, sizeof(buffer));
   
    bytesReceived = recv(peerServerSocket, buffer, sizeof(buffer), 0);
    
    
    // cout << "response got from peer" <<  buffer << endl;

   
    
    vector<string> res1 = tokenize(buffer);
    if(res1.size()>0 && res1[0] == "success")
    {
        string temp = "";
        int bufferLength = bytesReceived;
        
        // spliting buffer command by spacce
        for(int i=1;i<res1.size();i++)
        {
            response.push_back({stoi(res1[i]),{ip,port}});
        }
    }
    else
    {
        cout << buffer << endl;
    }

    // format <{chunkno,{ip,port}}>
    // cout << " response for loop " << endl;
    // for(auto x : response)
    // {
    //     cout << x.first << " " << x.second.first << " " << x.second.first << endl;
    // }
    close(peerServerSocket);
    return response;
}

// Download saperate chunk from another peer                                                                                                  //full path with file name
string downloadWholeChunkFromPeer(int i,vector<pair<int,vector<pair<string,string>>>>& chunkInfoTable,string sha,string fileName,string destination_path,long long int no_of_chunks,long long int file_size,std::mutex &queueAndFileTableMutex,char* trackerServerIp, int trackerServerPort,string user_id,string group_id)
{
    // char resultBuffer[512*1024];
    bool flagSuccess = false;
    string resultBuffer = "";
    int itr = 0;

    while(!flagSuccess)
    {
        itr++;
        if(itr>5)
            break;
        
        int noOfPeers = chunkInfoTable[i].second.size();
        // If no peer has this chunk then just break the loop
        if(noOfPeers == 0)
        {
            flagSuccess = true;
            break;
        }
        
        int peerSelectionIndex = rand() % chunkInfoTable[i].second.size();                         // Select peer index
        string peerIp = chunkInfoTable[i].second[peerSelectionIndex].first;
        int peerPort = stoi(chunkInfoTable[i].second[peerSelectionIndex].second);

        cout << "Asking to peer : " << peerIp << " PORT : " << peerPort << "Chunk no : " << chunkInfoTable[i].first << endl;

        int peerServerSocket = socket(AF_INET, SOCK_STREAM, 0);
        if (peerServerSocket == -1) {
            cerr << "Socket connection failed Asking to peer : " << peerIp << " PORT : " << peerPort << "Chunk no : " << chunkInfoTable[i].first << endl;
            continue;
        }

        sockaddr_in serverAddr;
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_port = htons(peerPort);

        if (inet_pton(AF_INET, peerIp.c_str(), &serverAddr.sin_addr) <= 0) {
            close(peerServerSocket);
            cerr << "Invalid address Asking to peer : " << peerIp << " PORT : " << peerPort << "Chunk no : " << chunkInfoTable[i].first << endl;
            continue;
        }

        if (connect(peerServerSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) == -1) {
            close(peerServerSocket);
            cerr << "Connection failled Asking to peer : " << peerIp << " PORT : " << peerPort << "Chunk no : " << chunkInfoTable[i].first << endl;
            continue;
        }

        int bytesReceived = 0;
        char resultBufferbuffer[1024];
        char buffer[512*1024];
        // connection message
        bytesReceived = recv(peerServerSocket, buffer, sizeof(buffer), 0);
        // cout << "1st message" << endl;
        // cout << buffer << endl;

        // bzero(buffer, sizeof(buffer));
        // sent argumnet : give_chunk sha chunkNo
        string arguments = "";
        arguments += "give_chunk";
        arguments += " " + sha;
        arguments += " " + to_string(chunkInfoTable[i].first);

        send(peerServerSocket,arguments.c_str(),arguments.length(),0);

        // bzero(buffer, sizeof(buffer));
        // cout << "Buffer size " << sizeof(buffer) << endl;
        memset(buffer, 0, sizeof(buffer));
    
        bytesReceived = recv(peerServerSocket, buffer, sizeof(buffer), 0);
        string lengthOfChunk(buffer);
        long long int expectedSize = stoi(lengthOfChunk);
        long long int totalReceived = 0;

        // cout << expectedSize << " length of chunk "<<endl;
        // if(expectedSize == 475712)
        // {
        //     sleep(3);
        // }
        resultBuffer = "";
        char newBuffer[CHUNK_SIZE_TCP];

        // for(int i=0;i<expectedSize;i++)
        // {
        //     bzero(newBuffer,sizeof(newBuffer));
        //     bytesReceived = recv(peerServerSocket, newBuffer, sizeof(newBuffer), 0);
        //     string result(newBuffer);
        //     resultBuffer += result;
        // }
        
/////////////////////////////////////////final////////////////////////////////////
        // int readAtOnce = CHUNK_SIZE_TCP;
        // int leftToRead = expectedSize;
        // int k=0;
        // resultBuffer = "";
        // while(leftToRead > 0)
        // {
        //     bzero(newBuffer,sizeof(newBuffer));
            
        //     readAtOnce = (readAtOnce < leftToRead) ? readAtOnce : leftToRead;
        //     bytesReceived = recv(peerServerSocket, newBuffer, sizeof(newBuffer), 0);
        //     // cout << "sizeof new buffer" << sizeof(newBuffer) << endl;
        //     string result(newBuffer, bytesReceived);
        //     // cout << "Incoming result length : "<<  result.length()<< endl; 
        //     resultBuffer += result;
        //     leftToRead -= bytesReceived;
        //     k++;
        //     // cout << "Got : " << bytesReceived  << "New result bufferlength " << resultBuffer.length() << endl;
        // }
/////////////////////////////////////////final////////////////////////////////////

        int readAtOnce = CHUNK_SIZE_TCP;
        int leftToRead = expectedSize;
        int k=0;
        resultBuffer = "";
        while(true)
        {
            if(leftToRead <=0)
            {
                break;
            }
            fd_set readfds;
            struct timeval timeout;

            FD_ZERO(&readfds);
            FD_SET(peerServerSocket, &readfds);

            timeout.tv_sec = 6; // Set a 6-second timeout
            timeout.tv_usec = 0;

            int selectResult = select(peerServerSocket + 1, &readfds, NULL, NULL, &timeout);

            if (selectResult < 0) {
                // Handle select error
                break;
            } else if (selectResult == 0) {
                // Timeout reached, no data received within the timeout
                break;
            }
            bzero(newBuffer,sizeof(newBuffer));
            
            readAtOnce = (readAtOnce < leftToRead) ? readAtOnce : leftToRead;
            bytesReceived = recv(peerServerSocket, newBuffer, sizeof(newBuffer), 0);
            // cout << "sizeof new buffer" << sizeof(newBuffer) << endl;
            string result(newBuffer, bytesReceived);
            // cout << "Incoming result length : "<<  result.length()<< endl; 
            resultBuffer += result;
            leftToRead -= bytesReceived;
            k++;
            // cout << "Got : " << bytesReceived  << "New result bufferlength " << resultBuffer.length() << endl;

            if (bytesReceived <= 0) {
                // Handle errors or end of data
                break;
            }

        }



        // cout << "//////file from rec//////////" << endl;
        // cout << resultBuffer << endl;
        // cout << "//////file from rec//////////" << endl;
        









        // cout << k << " RECIVED " << resultBuffer.length() << endl;
        // if(resultBuffer.length() > expectedSize )
        //     resultBuffer = resultBuffer.substr(0,expectedSize);

        // int i= 0;
        // while (totalReceived < expectedSize) {
        //     cout << " i " << i << " " <<totalReceived << endl;
        //     bzero(buffer,sizeof(buffer));
        //     cout <<"here1"<<endl;
        //     if(resultBuffer.length()>=expectedSize)
        //     {
        //         break;
        //     }
        //     cout<<"here2"<<endl;
        //     bytesReceived = recv(peerServerSocket, buffer, sizeof(buffer), 0);
        //     totalReceived += bytesReceived;
        //     string result(buffer);
        //     resultBuffer += result;
        //     cout <<"here3"<<endl;
        //     if(resultBuffer.length()>=expectedSize)
        //     {
        //         break;
        //     }
        //     if(bytesReceived <=0)
        //     {
        //         break;
        //     }
        //     cout << "total " << totalReceived <<endl;
        //     i++;
        // }




        // while (true) {
        //     fd_set readfds;
        //     struct timeval timeout;

        //     FD_ZERO(&readfds);
        //     FD_SET(peerServerSocket, &readfds);

        //     timeout.tv_sec = 5; // Set a 5-second timeout
        //     timeout.tv_usec = 0;

        //     int selectResult = select(peerServerSocket + 1, &readfds, NULL, NULL, &timeout);

        //     if (selectResult < 0) {
        //         // Handle select error
        //         break;
        //     } else if (selectResult == 0) {
        //         // Timeout reached, no data received within the timeout
        //         break;
        //     }

        //     bytesReceived = recv(peerServerSocket, buffer, sizeof(buffer), 0);
            
        //     if (bytesReceived <= 0) {
        //         // Handle errors or end of data
        //         break;
        //     }

        //     string result(buffer);
        //     resultBuffer += result;
        //     totalReceived += bytesReceived;
        // }




        // cout << expectedSize << "   Inside4" << endl;
        // cout << "after while loop I have recieved : " << totalReceived << endl;

        // // Reciving sha of chunk
        // bytesReceived = recv(peerServerSocket, buffer, sizeof(buffer), 0);
        // // cout << "file" << buffer << endl;
        // string result(buffer);
        // resultBuffer = result;
        // cout << "got result buffer " << bytesReceived << endl;
        // cout << "Got result " << resultBuffer.length() << endl;

        string shaChunk =calculateShaofChunk(resultBuffer);
        // cout << "sha : "<<shaChunk << endl;
        // cout << "Sha chunk " << shaChunk.length() << endl;
        // cout << "2nd message file" << endl; 
        // cout << buffer << endl;

        // Got sha message ack
        send(peerServerSocket,"got file",1024,0);
        // bzero(buffer, sizeof(buffer));
        memset(buffer, 0, sizeof(buffer));


        // cout << "3rd messahe" << endl;
        // cout << "previous buffer" << buffer << endl;
        
        bytesReceived = recv(peerServerSocket, buffer, 40, 0);

    //     for (int i = 0; i < bytesReceived; i++) {
    //     printf("%02X ", static_cast<unsigned char>(buffer[i]));
    // }
        
        // cout <<  "sha "<< endl;
        // cout << bytesReceived << endl;
        // cout << "sha " << buffer<< endl;

        string shaSentByPeer(buffer);
        // cout << "sha got by peer"  << shaSentByPeer.length();

        send(peerServerSocket,"exit",1024,0);
        close(peerServerSocket);

        //comparing sha
        // cout << "at compare time : " << endl;
        // cout << shaChunk << endl;
        // cout << shaSentByPeer << endl;;
        // cout << "CHUNK NO : " << chunkInfoTable[i].first << endl;
        if(shaChunk == shaSentByPeer)
        {
            std::lock_guard<std::mutex> lock(queueAndFileTableMutex);
            // cout << "Sha Got matched" << endl;
            flagSuccess = true;
            // start to inprogress queue
            if(downloadStart.find(sha)!=downloadStart.end())
            {
                // Put lock here
                downloadStart.erase(sha);
                downloadPending[sha] = {group_id,fileName};

                // do entry in fileIhave table
                if(filesIHave.find(sha) != filesIHave.end())
                {
                    filesIHave[sha].no_of_chunks_I_have++;
                    filesIHave[sha].chunks_I_have[chunkInfoTable[i].first] = shaChunk;
                }
                else
                {
                    vector<string> shaEveryChunk(no_of_chunks,"");
                    shaEveryChunk[chunkInfoTable[i].first] = shaChunk;
                    FilesStructure fs;
                    fs.file_path = destination_path;
                    fs.file_name = fileName;
                    fs.sha = sha;
                    fs.total_chunks = no_of_chunks;
                    fs.total_size = file_size;
                    fs.chunks_I_have = shaEveryChunk;
                    fs.no_of_chunks_I_have = 1;

                    // cout<<fs.no_of_chunks_I_have << "no of chunk stored" << endl;

                    filesIHave[fs.sha] = fs;
                }

                //  informing tracker that I have this file
                int trackerServerSocket = socket(AF_INET, SOCK_STREAM, 0);
                if (trackerServerSocket == -1) {
                    perror("Socket creation failed with peer");
                    // return;
                }
                else
                {
                    sockaddr_in serverAddr;
                    serverAddr.sin_family = AF_INET;
                    serverAddr.sin_port = htons(trackerServerPort);

                    if (inet_pton(AF_INET, trackerServerIp, &serverAddr.sin_addr) <= 0) {
                        perror("Invalid address");
                        close(trackerServerSocket);
                        // return;
                    }
                    else
                    {
                        if (connect(trackerServerSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) == -1) {
                            perror("Connection to peer failed");
                            close(trackerServerSocket);
                            // return;
                        }
                        else
                        {
                            // update_file_table user_id group_id fileName no_of_chunks sha file_size
                            string arguments = "";
                            arguments += "update_file_table " + user_id + " " + group_id + " " + fileName + " " + to_string(no_of_chunks) + " " + sha + " " + to_string(file_size) ;

                            bytesReceived = recv(trackerServerSocket, buffer, sizeof(buffer), 0);
                            bzero(buffer,sizeof(buffer));


                            send(trackerServerSocket,arguments.c_str(),1024,0);

                            close(trackerServerSocket);
                        }
                    }
                }
                

            }
            else
            {
                filesIHave[sha].no_of_chunks_I_have++;
                filesIHave[sha].chunks_I_have[chunkInfoTable[i].first] = shaChunk;
            }
            break;
        }
        else
        {
            // cout << "Sha did not match for chunk no : " << chunkInfoTable[i].first << " asking again" << endl;
            // break;              /////////////////////////////////////////// REMOVE THIS BREAK /////////////////////////////////////////////
        }
    }


    return resultBuffer;
}

bool comparator(pair<int,vector<pair<string,string>>> a,pair<int,vector<pair<string,string>>> b)
{
    return b.second.size() > a.second.size();
}


void downloadRequestHandler(string user_id,string commandInput, vector<string> command,char* trackerServerIp, int trackerServerPort)
{
    // command vector contain -> download_file <group_id> <file_name> <destination_path>

    string fileName = command[2];
    if(fileName == "")
    {
        cerr << "Please give filename " << endl;
        return;
    }

    string destination_path = command[3];
    if(destination_path == "")
    {
        cerr << "Please enter destination path" << endl;
        return;
    }
    else
    {
        struct stat folder;
        if (stat(destination_path.c_str(), &folder) == 0) {
        } else {
            cerr << "Destination path is not valid" << endl;
            return;
        }
    }

    // append file name at the end of destiantion 
    if(destination_path[destination_path.length()-1] == '/')
    {
        destination_path+=fileName;
    }
    else
    {
        destination_path += "/"+fileName;
    }

    int trackerServerSocket = socket(AF_INET, SOCK_STREAM, 0);
    if (trackerServerSocket == -1) {
        perror("Socket creation failed with peer");
        return;
    }

    // int peerPort = trackerServerPort;

    sockaddr_in serverAddr;
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(trackerServerPort);

    if (inet_pton(AF_INET, trackerServerIp, &serverAddr.sin_addr) <= 0) {
        perror("Invalid address");
        close(trackerServerSocket);
        return;
    }

    if (connect(trackerServerSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) == -1) {
        perror("Connection to peer failed");
        close(trackerServerSocket);
        return;
    }

    
    string fileSha = "";
    long long int total_no_of_chunks = 0;
    long long int file_size = 0;
    long long int bytesReceived = 0;
    char buffer[512*1024];
    if(!isUserIdSet(user_id))
    {
        cerr << "Please do login first" << endl;
        return;
    }
    if(command.size() != 4)
    {
        cerr << "Please pass download_file <group_id> <file_name> <destination_path>" << endl;
        return;
    }

    string arguments = "";
    arguments += commandInput;
    arguments += " " + user_id;

    bytesReceived = recv(trackerServerSocket, buffer, sizeof(buffer), 0);
    bzero(buffer,sizeof(buffer));


    send(trackerServerSocket,arguments.c_str(),1024,0);

    
    // response format : success sha no_of_chunks size ip port ip port
    bytesReceived = recv(trackerServerSocket, buffer, sizeof(buffer), 0);

    close(trackerServerSocket);

    vector<string> res1 = tokenize(buffer);
    if(res1.size()>0 && res1[0] == "success")
    {
        if(res1.size()<=4)
            cerr << "No peer has requested file" << endl;
        else
        {
            fileSha = res1[1];
            total_no_of_chunks = stoi(res1[2]);
            file_size = stoi(res1[3]);

            // Creating 10 threads;
            ThreadPool pool(10);
            
            // who have which chunk info table
            // {chunk_no,vecorofclients{ip,port}}
            vector<pair<int,vector<pair<string,string>>>> chunkInfoTable(total_no_of_chunks); 
            std::mutex chunkInfoTableMutex;

            std::vector<std::vector<std::string>> allResults;

            for(int i=4;i<res1.size();i = i+2)
            {
                //request clients for file chunk information
                pool.AddTask([i,res1,fileSha,&chunkInfoTableMutex,&chunkInfoTable] {
                    // Use lambda to capture and pass arguments
                    vector<pair<int,pair<string,string>>> result = connectWithClientAndGetChunkInfo(i, res1[i],res1[i+1],fileSha);
                    std::lock_guard<std::mutex> lock(chunkInfoTableMutex);
                    for(auto ele : result)
                    {
                        chunkInfoTable[ele.first].first = ele.first;
                        chunkInfoTable[ele.first].second.push_back({ele.second.first,ele.second.second});
                    }
                });
            }

            pool.WaitAndStop();
            cout << "All thread work is completed" << endl;

            // cout << "Chunk list : " << endl;
            // for(int i=0;i<chunkInfoTable.size();i++)
            // {
            //     cout << "chunk no : " << chunkInfoTable[i].first << " : "; 
            //     for(int j=0;j<chunkInfoTable[i].second.size();j++)
            //     {
            //         cout << "{" << chunkInfoTable[i].second[j].first << "," << chunkInfoTable[i].second[j].second << "} ";
            //     }
            //     cout << endl;
            // }

            /////////////////////Recieved who has which chunk/////////////////////

            ///////////////////// Downloading process starts////////////////////

            // At start of downloading stroing file name in start download map
            downloadStart[fileSha] = {command[1],fileName};

            // To do rarest first
            sort(chunkInfoTable.begin(),chunkInfoTable.end(),comparator);

            // cout << "Sorting " << endl;

            cout << "Chunk list : " << endl;
            for(int i=0;i<chunkInfoTable.size();i++)
            {
                cout << "chunk no : " << chunkInfoTable[i].first << " : "; 
                for(int j=0;j<chunkInfoTable[i].second.size();j++)
                {
                    cout << "{" << chunkInfoTable[i].second[j].first << "," << chunkInfoTable[i].second[j].second << "} ";
                }
                cout << endl;
            }


            // Ask for pieces

            ThreadPool pool1(15);

            // Creating one file :
            long int CHUNK_SIZE = 512*1024;
        
            int writeFileDescriptor = open(destination_path.c_str(), O_WRONLY | O_CREAT | O_TRUNC ); 

            if(writeFileDescriptor < 0)
            {
                    cerr << "Error while opening destination file " << endl;
                    return;
            }
            if (chmod(destination_path.c_str(), S_IRUSR | S_IWUSR ) != 0) {
                perror("Error changing file permissions");
                return;
            }
            
            std::mutex writeFileDescriptorMutex;
            std::mutex queueAndFileTableMutex;

            // cout << "1111" << endl;
            string group_id = command[1];

            for(int i=0;i<chunkInfoTable.size();i++)
            {
                // cout << "for i : " << i << endl;
                //request clients for file chunk information
                pool1.AddTask([i,fileSha,&chunkInfoTable,&writeFileDescriptorMutex,writeFileDescriptor,CHUNK_SIZE,fileName,&queueAndFileTableMutex,destination_path,total_no_of_chunks,file_size,trackerServerIp,trackerServerPort,user_id,group_id] {
                    // Use lambda to capture and pass arguments
                    // cout << "haha" << endl;
                    string resultBuffer;
                    resultBuffer = downloadWholeChunkFromPeer(i,chunkInfoTable,fileSha,fileName,destination_path,total_no_of_chunks,file_size,queueAndFileTableMutex,trackerServerIp,trackerServerPort,user_id,group_id);
                    // cout << resultBuffer << "     This is I got back" << endl;
                    std::lock_guard<std::mutex> lock(writeFileDescriptorMutex);
                    lseek(writeFileDescriptor, chunkInfoTable[i].first * CHUNK_SIZE, SEEK_SET);
                    // cout << "Size iof result buffer at time of file writing " << resultBuffer.length() << endl; 
                    write(writeFileDescriptor, resultBuffer.c_str(), resultBuffer.length());
                });
            }
            // sleep(10);
            pool1.WaitAndStop();
            cout << "All thread work is completed" << endl;

            // Check final sha : 
            if(downloadPending.find(fileSha)!=downloadPending.end())
            {
                downloadPending.erase(fileSha);
            }
            string mySha = calculateShaofFile(destination_path);
            if(mySha == fileSha)
            {
                cout << "File Downloaded Successfully : " <<  destination_path << endl;
                 // Putting in complete queue :
                downloadComplete.push_back({group_id,fileName});
                std::lock_guard<std::mutex> lock(queueAndFileTableMutex);

                if(filesIHave.find(mySha) != filesIHave.end())
                {
                    filesIHave[fileSha].no_of_chunks_I_have = filesIHave[fileSha].total_chunks;
                
                    vector<string> shaEveryChunk(total_no_of_chunks);
                    int index = 0;
                    char chunkOfFile[512*1024]; // Read 512 Kbytes at a time
                    ssize_t bytesRead;

                    int fileDescriptor = open(destination_path.c_str(), O_RDONLY);

                    if (fileDescriptor < 0) {
                        // std::cerr << "Error opening file" << std::endl;
                        // continue;
                    }
                    else
                    {
                        bzero(chunkOfFile, sizeof(chunkOfFile));
                    
                        while ((bytesRead = read(fileDescriptor, chunkOfFile, sizeof(chunkOfFile)) > 0)) {
                            shaEveryChunk[index] = calculateShaofChunk(chunkOfFile);
                            index++;
                            bzero(chunkOfFile, sizeof(chunkOfFile));
                        }
                        filesIHave[fileSha].chunks_I_have = shaEveryChunk;
                    }

                    close(fileDescriptor);
                }
                else
                {
                    FilesStructure fs;
                    fs.file_path = destination_path;
                    fs.file_name = fileName;
                    fs.sha = fileSha;
                    fs.total_chunks = total_no_of_chunks;
                    fs.total_size = file_size;
                    fs.no_of_chunks_I_have = 1;

                    // cout<<fs.no_of_chunks_I_have << "no of chunk stored" << endl;

                    filesIHave[fileSha] = fs;

                    filesIHave[fileSha].no_of_chunks_I_have = total_no_of_chunks;
                
                    vector<string> shaEveryChunk(total_no_of_chunks,"");
                    int index = 0;
                    char chunkOfFile[512*1024]; // Read 512 Kbytes at a time
                    ssize_t bytesRead;

                    int fileDescriptor = open(destination_path.c_str(), O_RDONLY);

                    if (fileDescriptor < 0) {
                        // std::cerr << "Error opening file" << std::endl;
                        // continue;
                    }
                    else
                    {
                        bzero(chunkOfFile, sizeof(chunkOfFile));
                    
                        while ((bytesRead = read(fileDescriptor, chunkOfFile, sizeof(chunkOfFile)) > 0)) {
                            shaEveryChunk[index] = calculateShaofChunk(chunkOfFile);
                            index++;
                            bzero(chunkOfFile, sizeof(chunkOfFile));
                        }
                        filesIHave[fileSha].chunks_I_have = shaEveryChunk;
                    }

                    close(fileDescriptor);
                }

                //  informing tracker that I have this file
                int trackerServerSocket = socket(AF_INET, SOCK_STREAM, 0);
                if (trackerServerSocket == -1) {
                    perror("Socket creation failed with peer");
                    // return;
                }
                else
                {
                    sockaddr_in serverAddr;
                    serverAddr.sin_family = AF_INET;
                    serverAddr.sin_port = htons(trackerServerPort);

                    if (inet_pton(AF_INET, trackerServerIp, &serverAddr.sin_addr) <= 0) {
                        perror("Invalid address");
                        close(trackerServerSocket);
                        // return;
                    }
                    else
                    {
                        if (connect(trackerServerSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) == -1) {
                            perror("Connection to peer failed");
                            close(trackerServerSocket);
                            // return;
                        }
                        else
                        {
                            // update_file_table user_id group_id fileName no_of_chunks sha file_size
                            string arguments = "";
                            arguments += "update_file_table " + user_id + " " + group_id + " " + fileName + " " + to_string(total_no_of_chunks) + " " + fileSha + " " + to_string(file_size) ;

                            bytesReceived = recv(trackerServerSocket, buffer, sizeof(buffer), 0);
                            bzero(buffer,sizeof(buffer));


                            send(trackerServerSocket,arguments.c_str(),1024,0);

                            close(trackerServerSocket);
                        }
                    }
                }

                

            
            }
            else
            {
                cout << "File" << endl;
                // cout << "File Downloading Failed,please try again : " <<  destination_path << endl;
                 // Putting in complete queue :
                downloadComplete.push_back({group_id,fileName + "-failed"});
                // downloadStart[fileSha] = fileName + "-failed";
                // remove file entry from files table

                // if(filesIHave.find(fileSha)!=filesIHave.end())
                // {
                //     filesIHave.erase(fileSha);
                // }
            }

           printFileTable();




        }   


    }
    // error in res1
    else
    {
        cout << buffer << endl;
    }
    return;
}

void connectToOtherServer(char* connectToOtherServerIp, int connectToOtherServerPort, string ownServerIp, int ownServerPort) 
{
    // Store user_id so it can be used in further processes
    string user_id = "";

    int serverSocket = socket(AF_INET, SOCK_STREAM, 0);
    if (serverSocket == -1) {
        perror("Socket creation failed");
        return;
    }

    sockaddr_in serverAddr;
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(connectToOtherServerPort);

    if (inet_pton(AF_INET, connectToOtherServerIp, &serverAddr.sin_addr) <= 0) {
        perror("Invalid address");
        return;
    }

    if (connect(serverSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) == -1) {
        perror("Connection to tracker failed");
        close(serverSocket);
        return;
    }

    // You can send and receive data with the connected server here

    char buffer[1024];
    int bytesReceived;
    bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
    cout << buffer << endl;

    while(true)
    {
        string commandInput;
        getline(cin,commandInput);
        string temp = "";
        vector<string> command = tokenize(commandInput);

        if(command.size() == 0)
        {
            cerr << "Invalid Command" << endl;
            continue;
        }
        else if(command[0] == "create_user")
        {
            if(command.size() != 3)
            {
                cerr << "Please pass create_user <user_id> <passwd>" << endl;
                continue;
            }
            user_id = "";
            string arguments = "";
            arguments += commandInput;
            arguments += " " + ownServerIp;
            arguments += " " + to_string(ownServerPort);
            
            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            cout << buffer << endl;
        }
        else if(command[0] == "login")
        {
            if(user_id != "")
            {
                cerr << "Please try to login for some other device,some user is already logged in log out first" << endl;
                continue;
            }
            if(command.size() != 3)
            {
                cerr << "Please pass create_user <user_id> <passwd>" << endl;
                continue;
            }
            
            string arguments = "";
            arguments += commandInput;
            arguments += " " + ownServerIp;
            arguments += " " + to_string(ownServerPort);

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            cout << buffer << endl;
            if(strcmp(buffer,"Logged in successfully") == 0)
            {
                user_id = command[1];
            }
            else
            {
                user_id = "";
            }
        }
        else if(command[0] == "create_group")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 2)
            {
                cerr << "Please pass create_group <group_id>" << endl;
                continue;
            }

            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            cout << buffer << endl;
        }
        else if(command[0] == "join_group")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 2)
            {
                cerr << "Please pass join_group <group_id>" << endl;
                continue;
            }

            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            cout << buffer << endl;
        }
        else if(command[0] == "leave_group")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 2)
            {
                cerr << "Please pass leave_group <group_id>" << endl;
                continue;
            }

            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            cout << buffer << endl;
        }
        // List pending join: list_requests <group_id>
        else if(command[0] == "list_requests")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 2)
            {
                cerr << "Please pass list_requests <group_id>" << endl;
                continue;
            }

            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            // print vector of list requests
            // cout << buffer << endl;
            vector<string> response = tokenize(buffer);
            if(response.size()>0 && response[0] == "success")
            {
                cout << "Users of pending requests : "<<endl;
                int len = response.size();
                for(int i=1;i<len;i++)
                    cout << response[i] << endl;
            }
            else
            {
                cout << buffer << endl;
            }
        }
        // Accept Group Joining Request: accept_request <group_id> <user_id>
        else if(command[0] == "accept_request")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 3)
            {
                cerr << "Please pass accept_request <group_id> <user_id>" << endl;
                continue;
            }

            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            cout << buffer << endl;
        }
        // List All Group In Network: list_groups
        else if(command[0] == "list_groups")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 1)
            {
                cerr << "Please pass list_groups" << endl;
                continue;
            }

            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            // cout << buffer << endl;
            vector<string> response = tokenize(buffer);
            if(response.size()>0 && response[0] == "success")
            {
                cout << "Group id of groups : "<<endl;
                int len = response.size();
                for(int i=1;i<len;i++)
                    cout << response[i] << endl;
            }
            else
            {
                cout << buffer << endl;
            }
        }
        // List All sharable Files In Group: list_files <group_id>
        else if(command[0] == "list_files")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 2)
            {
                cerr << "Please pass list_files <group_id>" << endl;
                continue;
            }

            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            send(serverSocket,arguments.c_str(),1024,0);

            cout << "I am here 1" << endl;
            // bzero(buffer, sizeof(buffer));
            memset(buffer, 0, sizeof(buffer));

            int flags = fcntl(serverSocket, F_GETFL, 0);
            // if (flags & O_NONBLOCK) {
            //     // The socket is in non-blocking mode
            //     cout << "Non blocking" << endl;
            // } else {
            //     // The socket is in blocking mode
            //     cout << "blocking" << endl;
            // }
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            // cout << "bytes" <<  bytesReceived << endl;
            // cout << "testing" <<  buffer <<"testing"<< endl;
            vector<string> response = tokenize(buffer);
            if(response.size()>0 && response[0] == "success")
            {
                cout << "List of files : "<<endl;
                int len = response.size();
                for(int i=1;i<len;i++)
                    cout << response[i] << endl;
            }
            else
            {
                cout << buffer << endl;
            }
        }
        // Upload File: upload_file <file_path> <group_id>
        else if(command[0] == "upload_file")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 3)
            {
                cerr << "Please pass upload_file <file_path> <group_id>" << endl;
                continue;
            }

            if (access(command[1].c_str(), F_OK) != 0) {
                cerr << "Given file does not exist" << endl;
                continue;
            }

            struct stat fileStat;
            string sha = calculateShaofFile(command[1]);
            if(sha == "")
            {
                cerr << "Error while calculating sha value, please try again" << endl;
                continue;
            }
            string fileName = extractFileNameFromPath(command[1]);
            long long int no_of_chunks = 0;
            off_t fileSize = 0;
            if (stat(command[1].c_str(), &fileStat) == 0)
                fileSize = fileStat.st_size;

            if(fileSize > 0)
                no_of_chunks = ((fileSize-1)/(512*1024))+1;

            vector<string> shaEveryChunk(no_of_chunks);
            int index = 0;
            char chunkOfFile[512*1024]; // Read 512 Kbytes at a time
            ssize_t bytesRead;

            int fileDescriptor = open(command[1].c_str(), O_RDONLY);

            if (fileDescriptor < 0) {
                std::cerr << "Error opening file" << std::endl;
                continue;
            }

            bzero(chunkOfFile, sizeof(chunkOfFile));
            
            while ((bytesRead = read(fileDescriptor, chunkOfFile, sizeof(chunkOfFile)) > 0)) {
                shaEveryChunk[index] = calculateShaofChunk(chunkOfFile);
                index++;
                bzero(chunkOfFile, sizeof(chunkOfFile));
            }

            // for(auto x : shaEveryChunk)
            // {
            //     cout << "every chunk : " << x <<endl;
            // }

            close(fileDescriptor);

            // Passing : upload_file <file_path> <group_id> <user_id> <file_name> <sha> <no_of_chunks> <file_size>
            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;
            arguments += " " + fileName;
            arguments += " " + sha;
            arguments += " " + to_string(no_of_chunks);
            arguments += " " + to_string(fileSize);

            // cout << arguments;

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            string res = buffer;
            // // cout << buffer << endl;
            
            // // comapre if success -> storing in user's storage
            if(res.substr(0,7) == "Success")
            {
                FilesStructure fs;
                fs.file_path = command[1];
                fs.file_name = fileName;
                fs.sha = sha;
                fs.total_chunks = no_of_chunks;
                fs.total_size = fileSize;
                fs.chunks_I_have = shaEveryChunk;
                fs.no_of_chunks_I_have = no_of_chunks;

                // cout<<fs.no_of_chunks_I_have << "no of chunk stored" << endl;

                filesIHave[fs.sha] = fs;

                printFileTable();
            }
            cout << buffer << endl;
        }
        else if(command[0] == "download_file")
        {
            thread(downloadRequestHandler, user_id, commandInput, command,connectToOtherServerIp,connectToOtherServerPort).detach();
            // downloadRequestHandler(serverSocket, user_id, commandInput, command);
        }
        else if(command[0] == "logout")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            
            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            user_id = "";

            send(serverSocket,arguments.c_str(),1024,0);
            
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            cout << buffer << endl;
        }
        else if(command[0] == "show_downloads")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            printShowDownloads();
        }
        // stop_share <group_id> <file_name>
        else if(command[0] == "stop_share")
        {
            if(!isUserIdSet(user_id))
            {
                cerr << "Please do login first" << endl;
                continue;
            }
            if(command.size() != 3)
            {
                cerr << "Please pass stop_share <group_id> <file_name>" << endl;
                continue;
            }
            bool fileExist = false;
            string fileSha = "";
            for( auto x : filesIHave)
            {
                if(x.second.file_name == command[2])
                {
                    fileExist = true;
                    fileSha = x.second.sha;
                    break;
                }
            }
            if(fileExist = false)
            {
                cerr << "You are already not sharing this file" << endl;
                continue;
            }

            string arguments = "";
            arguments += commandInput;
            arguments += " " + user_id;

            send(serverSocket,arguments.c_str(),1024,0);
            bzero(buffer,sizeof(buffer));
            bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0);
            cout << buffer << endl;
            if(filesIHave.find(fileSha) != filesIHave.end())
            {
                filesIHave.erase(fileSha);
            }
            printFileTable();
        }
        else
        {
            cout << "Invalid Commands" << endl;
        }
        

    }

    close(serverSocket);
    
}

int main(int argc,char *argv[]) {

    // cout << argc << endl;
    if(argc < 3)
    {
        cerr << "Please pass input argument in this format : ./client <IP>:<PORT> tracker_info.txt" << endl;
        exit(1);
    }
    
    // Reading tracker_info file
    char* trackerInfoFileName = argv[2];
    int readTrackerInfoFileDescriptor = open(trackerInfoFileName,O_RDONLY);
    if(readTrackerInfoFileDescriptor < 0)
    {
        cerr << "Error while opening tracker_info file " << endl;
        exit(1);
    }

    char buffer[1024];
    int dataRead = 0;
    
    string temp = "";
    vector<string> trackerInfo;

    // Reading first 4 lines
    dataRead = read(readTrackerInfoFileDescriptor, buffer, sizeof(buffer));
    for (int i = 0; i < dataRead; i++) {
        if (buffer[i] == '\n') {
            trackerInfo.push_back(temp);
            temp = "";
        }
        else
        {
            temp += buffer[i];
        }
    }

    // close tracker_info file
    close(readTrackerInfoFileDescriptor);

    if(trackerInfo.size() < 4)
    {
        cerr << "Tracker_info file does not have corrct data" << endl;
        exit(1);
    }

    string connectToOtherServerIp = trackerInfo[0];
    int connectToOtherServerPort = stoi(trackerInfo[1]);
    char* connectToOtherServerIp_charArray = new char[connectToOtherServerIp.length() + 1];
    strcpy(connectToOtherServerIp_charArray, connectToOtherServerIp.c_str()); 

    string ipPort = argv[1];
    string serverIp = "";
    int serverPort;
    temp = "";

    for(int i=0;i<ipPort.length();i++)
    {
        if(ipPort[i] == ':')
        {
            serverIp = temp;
            temp = "";
        }
        else
        {
            temp += ipPort[i];
        }
    }
    serverPort = stoi(temp);
    // cout << "My port : " << serverPort << endl;

    // char* serverIp_charArray = new char[serverIp.length() + 1];
    // strcpy(serverIp_charArray, serverIp.c_str());

    
    // Create server
    int serverSocket = socket(AF_INET, SOCK_STREAM, 0);
    if (serverSocket == -1) {
        cerr << "Socket creation failed" << endl;
        exit(1);
    }

    sockaddr_in serverAddr;
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(serverPort);
    serverAddr.sin_addr.s_addr = INADDR_ANY;

    int opt = 1;

    if (setsockopt(serverSocket, SOL_SOCKET, SO_REUSEADDR | SO_REUSEPORT, &opt, sizeof(opt))) { 
        cerr << "setsockopt" << endl; 
        exit(1); 
    } 

    if (bind(serverSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) == -1) {
        cerr << "Binding failed" << endl;
        exit(1);
    }

    if (listen(serverSocket, 100) == -1) {
        cerr << "Listening failed" << endl;
        exit(1);
    }

    cout << "Listening on port " << serverPort << endl;

    // user_ip = serverIp;
    // user_port = serverPort;
    // Create a thread to connect to another server
    thread(connectToOtherServer, connectToOtherServerIp_charArray, connectToOtherServerPort,serverIp,serverPort).detach();

    while (true) {
        sockaddr_in clientAddr;
        socklen_t clientAddrLen = sizeof(clientAddr);
        int clientSocket = accept(serverSocket, (struct sockaddr*)&clientAddr, &clientAddrLen);

        if (clientSocket == -1) {
            cerr << "Peer Accept failed" << endl;
            continue;
        }

        // Create a new thread to handle the client connection
        thread(inComingClientRequest, clientSocket).detach();
    }

    close(serverSocket);

    return 0;
}