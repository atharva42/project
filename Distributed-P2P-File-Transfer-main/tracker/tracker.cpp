// pass the new owner mesage that you are new owner
// If user do login upload files then do logout hrn do login from different port then delete files
// if any client is doing ctrl+c then log off him from tracker
// file with same name.


// show downloads,stop sharing,exit

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
#include <unordered_map>
#include <unordered_set>
#include <utility>
using namespace std;

struct PairHash {
    template <class T1, class T2>
    std::size_t operator () (const std::pair<T1, T2>& p) const {
        auto h1 = std::hash<T1>{}(p.first);
        auto h2 = std::hash<T2>{}(p.second);
        return h1 ^ h2;
    }
};

class fileInfo{
    public:
    string file_name;
    long long int no_of_chunks;
    long long int size;
    string sha;
};

class User{
    public :
    string user_id;
    string password;
    string ip_address;
    string port;
    bool is_active;
    //<{sha,group_id},name>
    unordered_map<pair<string,string>,string,PairHash> files;
    // <sha,{file name,group_id}>
    // unordered_map<string,pair<string,string>> files;

    User()
    {
        user_id = "";
        password = "";  
        ip_address = "";
        port = "";
        is_active = false;
    }
};



class Group{
    public :
    string group_id;
    string owner_user_id;
    //<user_id , count>
    unordered_map<string,int> pending_users;
    unordered_map<string,int> accepted_users;
};

// map for all groups : <gorup_id,Group class object>
unordered_map<string,Group> groups;

// map for all users : <user_id,User class object>
unordered_map<string,User> users;

// map for all files : <name,fileInfo obj>
unordered_map<string,fileInfo> files;

// Tokenize with space
vector<string> tokenize(string commandString)
{
    string temp = "";
    vector<string> command;
    int bufferLength = commandString.length();
    
    // spliting input command by spacce
    for(int i=0;i<bufferLength;i++)
    {
        // cout << commandString[i] << " ";
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

pair<bool,string> isLoggedIn(string user_id)
{
    if(users.find(user_id) == users.end())
    {
        cout << "User does not exist,please register" << endl;
        return {false,"User does not exist,please register"};
    }
    else
    {
        if(users[user_id].is_active)
        {
            cout << "Logged in" << endl;
            return {true,"Logged In"};
        }
        else
        {
            cout << "User is not logged in,please login" << endl;
            return {false,"User is not logged in,please login"};
        }
    }
}

void printUserTable()
{
    cout << endl;
    cout << "//////////////////////////////////// User //////////////////////////////////" << endl;
    for(auto x : users)
    {
        cout << x.first << " " << x.second.ip_address << " " << x.second.port << " " << x.second.password << " " << x.second.is_active<<" ";
        for( auto y : x.second.files)
        {
            cout << "{" << y.first.second << "," << y.second << "}" << " ";
        }
        cout << endl;
    }
    cout << "//////////////////////////////////// User //////////////////////////////////" << endl;
    cout << endl;

}

void printGroupTable()
{
    cout << endl;
    cout << "//////////////////////////////////// Group //////////////////////////////////" << endl;
    for(auto x : groups)
    {
        cout << x.first << " " << x.second.owner_user_id << " " << " | ";
        for(auto y : x.second.pending_users)
            cout << y.first << " ";
        cout << " | ";
        for(auto y : x.second.accepted_users)
            cout << y.first << " ";
        cout << endl;
    }
    cout << "//////////////////////////////////// Group //////////////////////////////////" << endl;
    cout << endl;
}

void printFileTable()
{
    cout << endl;
    cout << "//////////////////////////////////// File //////////////////////////////////" << endl;
    for(auto x : files)
    {
        cout << x.first << " " << x.second.no_of_chunks<< " " << x.second.size << " " << x.second.sha << endl;
    }
    cout << "//////////////////////////////////// File //////////////////////////////////" << endl;
    cout << endl;
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

    // For example, echo server
    char buffer[1024];
    int bytesReceived;
    send(clientSocket,"You are connected to tracker, I am here to serve you",52,0);
    while ((bytesReceived = read(clientSocket, buffer, sizeof(buffer))) > 0) {
        // cout  << "bytesreciveved" << bytesReceived << endl;
        // cout << buffer << endl;
        vector<string> command = tokenize(buffer);
        
        // cout << command.size() << endl;
        // cout << command[0] << endl;
        // cout << (command[0] == "update_file_table");
        //Printing incoming command tokenized
        printIncomingCommandTokenized(command);
        
        if(command.size() == 0)
        {
            cerr << "Invalid Command" << endl;
            send(clientSocket,"Invalid Command",1024,0);
            continue;
        }
        // update_file_table user_id group_id fileName no_of_chunks sha file_size
        else if(command[0] == "update_file_table")
        {
            // cout << "inside update file entry" << endl;
            string file_name = command[3];
            if(files.find(file_name)==files.end())
            {
                fileInfo f1;
                f1.file_name = file_name;
                f1.no_of_chunks = stoll(command[4]);
                f1.size = stoll(command[6]);
                f1.sha = command[5];

                files[command[3]] = f1;
            }
        
            users[command[1]].files[{command[5],command[2]}] = file_name;

        }
        else if(command[0] == "create_user")
        {
            if(users.find(command[1]) != users.end())
            {
                send(clientSocket,"User already exist,Please try to login",1024,0);
                continue;
            }
            User userObj;
            userObj.user_id = command[1];
            userObj.password = command[2];
            userObj.ip_address = command[3];
            userObj.port = command[4];
            userObj.is_active = false;

            users[command[1]] = userObj;

            send(clientSocket,"User created successfully,Please log in",1024,0);
        }
        else if(command[0] == "login")
        {
            if(users.find(command[1]) == users.end())
            {
                send(clientSocket,"User does not exist,Please register",1024,0);
                // cout << "user exist" << endl;
                continue;
            }
            if(users[command[1]].is_active)
            {
                //If user's port and ip got changed 
                // users[command[1]].ip_address = command[3];
                // users[command[1]].port = command[4];
                send(clientSocket,"Already logged in",1024,0);
                continue;
            }
            if(users[command[1]].password == command[2])
            {
                users[command[1]].is_active = true;
                //If user's port and ip got changed
                if(users[command[1]].port != command[4] || users[command[1]].ip_address != command[3])
                {
                    users[command[1]].files.clear();
                } 
                users[command[1]].ip_address = command[3];
                users[command[1]].port = command[4];
                send(clientSocket,"Logged in successfully",1024,0);
            }
            else
            {
                send(clientSocket,"Invalid Credentials",1024,0);
            }
        }
        else if(command[0] == "create_group")
        {
            //incoming request : create_group gtoup_id user_id
            if(command.size() < 3 || command[2] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[2]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[1]) != groups.end())
                    {
                        send(clientSocket,"Group already exist with given group id",1024,0);
                        // continue;
                    }
                    else
                    {
                        Group groupObj;
                        groupObj.group_id = command[1];
                        groupObj.owner_user_id = command[2];
                        groupObj.accepted_users[command[2]]++;
                        // groupObj.accepted_users["temp"]++;
                        groups[command[1]] = groupObj;

                        send(clientSocket,"Group created successfully",1024,0);
                    }
                    // continue;
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "join_group")
        {
            //incoming request : join_group <group_id> user_id
            if(command.size() < 3 || command[2] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[2]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[1]) == groups.end())
                    {
                        send(clientSocket,"Group does exist with given group id",1024,0);
                        // continue;
                    }
                    else
                    {
                        if(groups[command[1]].accepted_users.find(command[2]) != groups[command[1]].accepted_users.end())
                        {
                            send(clientSocket,"You are already part of this group",1024,0);
                        }
                        else if(groups[command[1]].pending_users.find(command[2]) != groups[command[1]].pending_users.end())
                        {
                            groups[command[1]].pending_users[command[2]]++;
                            send(clientSocket,"Your request has already sent to ownler,please wait",1024,0);
                        }
                        else
                        {
                            groups[command[1]].pending_users[command[2]]++;
                            send(clientSocket,"Your request has been sent to ownler,please wait",1024,0);
                        }
                    }
                    // continue;
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "leave_group")
        {
            //incoming request : leave_group <group_id> user_id
            if(command.size() < 3 || command[2] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[2]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[1]) == groups.end())
                    {
                        send(clientSocket,"Group does exist with given group id",1024,0);
                        // continue;
                    }
                    else
                    {
                        if(groups[command[1]].accepted_users.find(command[2]) != groups[command[1]].accepted_users.end() || groups[command[1]].pending_users.find(command[2]) != groups[command[1]].pending_users.end())
                        {
                            groups[command[1]].accepted_users.erase(command[2]);
                            groups[command[1]].pending_users.erase(command[2]);
                            // If owner is leaving the group
                            if(groups[command[1]].owner_user_id == command[2])
                            {
                                if(groups[command[1]].accepted_users.size()<=0)
                                {
                                    groups.erase(command[1]);
                                }
                                else
                                {
                                    // assign new owner of the group
                                    groups[command[1]].owner_user_id = groups[command[1]].accepted_users.begin()->first;
                                }
                            }
                            send(clientSocket,"Leaved from group successfully",1024,0);
                        }
                        else
                        {
                            send(clientSocket,"Your are not part of this group",1024,0);
                        }
                    }
                    // continue;
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "list_requests")
        {
            //incoming request : list_requests <group_id> user_id
            if(command.size() < 3 || command[2] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[2]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[1]) == groups.end())
                    {
                        send(clientSocket,"Group does exist with given group id",1024,0);
                        // continue;
                    }
                    else
                    {
                        if(groups[command[1]].owner_user_id == command[2])
                        {
                            // add success to notify client that this is valid response not any error
                            string response = "success ";
                            for(auto ele : groups[command[1]].pending_users)
                            {
                                response += ele.first + " ";
                            }
                            send(clientSocket,response.c_str(),1024,0);
                        }
                        else
                        {
                            send(clientSocket,"Your are not owner of this group",1024,0);
                        }
                    }
                    // continue;
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "accept_request")
        {
            //incoming request : accept_request <group_id> <user_id> <own_user_id>
            if(command.size() < 4 || command[3] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[3]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[1]) == groups.end())
                    {
                        send(clientSocket,"Group does exist with given group id",1024,0);
                        // continue;
                    }
                    else
                    {
                        if(groups[command[1]].owner_user_id == command[3])
                        {
                            if(groups[command[1]].pending_users.find(command[2]) != groups[command[1]].pending_users.end())
                            {
                                // Remove from pending
                                groups[command[1]].pending_users.erase(command[2]);
                                // Added to complete
                                groups[command[1]].accepted_users[command[2]]++;
                                send(clientSocket,"Given user id accepted successfully",1024,0);
                            }
                            else
                            {
                                send(clientSocket,"No user found in pending list with given id",1024,0);
                            }
                        }
                        else
                        {
                            send(clientSocket,"Your are not owner of this group",1024,0);
                        }
                    }
                    // continue;
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "list_groups")
        {
            //incoming request : list_groups user_id
            if(command.size() < 2 || command[1] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[1]);
                if(isLoggedInRes.first == true)
                {
                    // add success to notify client that this is valid response not any error
                    string response = "success ";
                    for(auto ele : groups)
                    {
                        response += ele.first + " ";
                    }
                    send(clientSocket,response.c_str(),1024,0);
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "list_files")
        {
            //incoming request : list_files <group_id> <own_user_id>
            if(command.size() < 3 || command[2] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[2]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[1]) == groups.end())
                    {
                        send(clientSocket,"Group does exist with given group id",1024,0);
                        // continue;
                    }
                    else
                    {
                        unordered_set<string> usersOfGroup;
                        unordered_set<string> responseFiles;
                        for(auto ele : groups[command[1]].accepted_users)
                        {
                            // cout << "User of Group " << ele.first << endl;
                            usersOfGroup.insert(ele.first);
                        }
                        for(auto ele : usersOfGroup)
                        {
                            if(users.find(ele) != users.end() && users[ele].is_active)
                            {
                                for(auto ele2 : users[ele].files)
                                {
                                    if(ele2.first.second == command[1])
                                        responseFiles.insert(ele2.second);
                                }
                            }
                        }
                        string response = "success ";
                        for(auto ele : responseFiles)
                        {
                            response += ele + " ";
                        }
                        // cout << "sending " << response << endl;
                        send(clientSocket,response.c_str(),1024,0);
                    }
                    // continue;
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "upload_file")
        {
            //incoming request : upload_file <file_path> <group_id> <user_id> <file_name> <sha> <no_of_chunks> <file_size>
            if(command.size() < 8 || command[3] == "" || command[4] == "" || command[5] == "")
            {
                // cout << "Sorry! unable to entertain request" << endl;
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[3]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[2]) == groups.end())
                    {
                        // cout << "Group does exist with given group id" << endl;
                        send(clientSocket,"Group does exist with given group id",1024,0);
                        // continue;
                    }
                    else
                    {
                        if(groups[command[2]].accepted_users.find(command[3]) != groups[command[2]].accepted_users.end())
                        {
                            fileInfo f1;
                            f1.file_name = command[4];
                            f1.no_of_chunks = stoll(command[6]);
                            f1.size = stoll(command[7]);
                            f1.sha = command[5];

                            files[command[4]] = f1;

                            users[command[3]].files[{command[5],command[2]}] = command[4];

                            // cout << "Here" << endl;
                            
                            send(clientSocket,"Success, File Uploaded Successfully",1024,0);
                        }
                        else
                        {
                            // cout << "Your are not part of this group or your request is in still pending mode" << endl;
                            send(clientSocket,"Your are not part of this group or your request is in still pending mode",1024,0);
                        }
                    }
                    // continue;
                }
                else
                {
                    // cout << "Login issue" << endl;
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "download_file")
        {
           //incoming request : download_file <group_id> <file_name> <destination_path> <user_id>
            if(command.size() < 5 || command[4] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",512*1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[4]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[1]) == groups.end())
                    {
                        send(clientSocket,"Group does exist with given group id",512*1024,0);
                        // continue;
                    }
                    else
                    {
                        if(groups[command[1]].accepted_users.find(command[4]) != groups[command[1]].accepted_users.end())
                        {
                            if(files.find(command[2]) != files.end())
                            {
                                unordered_set<string> usersOfGroup;
                                //ip and port of users
                                unordered_set<pair<string,string>,PairHash> responseUsers;
                                for(auto ele : groups[command[1]].accepted_users)
                                {
                                    // cout << "User of Group " << ele.first << endl;
                                    usersOfGroup.insert(ele.first);
                                }
                                cout << "Users of group" << endl;
                                for(auto x : usersOfGroup)
                                    cout << x << endl;
                                for(auto user : usersOfGroup)
                                {
                                    cout << "checking for " << user << endl;
                                    if(users.find(user) != users.end() && users[user].is_active && users[user].user_id != command[4] && users[user].files.find({files[command[2]].sha,command[1]}) != users[user].files.end())
                                    {
                                        cout << "Inside" << endl;
                                        responseUsers.insert({users[user].ip_address,users[user].port});
                                    }
                                }
                                string response = "success";
                                response += " " + files[command[2]].sha;
                                response += " " + to_string(files[command[2]].no_of_chunks);
                                response += " " + to_string(files[command[2]].size)+ " ";

                                for(auto ele : responseUsers)
                                {
                                    response += ele.first + " " + ele.second + " ";
                                }
                                cout << "response" << response << endl;
                                // response format : success sha no_of_chunks size ip port ip port
                                send(clientSocket,response.c_str(),512*1024,0);
                            }
                            else
                            {
                                send(clientSocket,"No file found with given name",512*1024,0);
                            }
                        }
                        else
                        {
                            send(clientSocket,"Your are not part of this group or your request is in still pending mode",512*1024,0);
                        }
                    }
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),512*1024,0);
                    // continue;
                }
            }
        }
        else if(command[0] == "logout")
        {
            if(command.size() < 2 || command[1] == "")
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            pair<bool,string> isLoggedInRes = isLoggedIn(command[1]);
            if(isLoggedInRes.first == true)
            {
                users[command[1]].is_active = false;
                send(clientSocket,"Logged out successfully",1024,0);
                // continue;
            }
            else
            {
                send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
            }
        }
        // else if(command[0] == "show_downloads")
        // {
        //     cout << "show_downloads" << endl;
        // }
        // stop_share <group_id> <file_name> <user_id>
        else if(command[0] == "stop_share")
        {
            //incoming request : stop_share <group_id> <file_name> <user_id>
            if(command.size() < 4)
            {
                send(clientSocket,"Sorry! unable to entertain request",1024,0);
            }
            else
            {
                pair<bool,string> isLoggedInRes = isLoggedIn(command[3]);
                if(isLoggedInRes.first == true)
                {
                    if(groups.find(command[1]) == groups.end())
                    {
                        send(clientSocket,"Group does exist with given group id",1024,0);
                        // continue;
                    }
                    else
                    {
                         if(groups[command[1]].accepted_users.find(command[3]) != groups[command[1]].accepted_users.end())
                        {
                            if(files.find(command[2]) != files.end())
                            {
                                string fileSha = files[command[2]].sha;
                                if(users[command[3]].files.find({fileSha,command[1]}) != users[command[3]].files.end())
                                {
                                    users[command[3]].files.erase({fileSha,command[1]});
                                    send(clientSocket,"Stop sharing request accepted",1024,0);
                                }
                                else
                                {
                                    send(clientSocket,"File already removed",1024,0);
                                }
                            }
                            else
                            {
                                send(clientSocket,"File already removed",1024,0);
                            }                            
                        }
                        else
                        {
                            send(clientSocket,"Your are not part of this group",1024,0);
                        }
                    }
                    // continue;
                }
                else
                {
                    send(clientSocket,isLoggedInRes.second.c_str(),1024,0);
                    // continue;
                }
            }
        }
        else
        {
            cout << "Invalid Commands" << endl;
            send(clientSocket,"Invalid Command",1024,0);
        }
        printUserTable();
        printGroupTable();
        printFileTable();
    }

    // Close the client socket
    close(clientSocket);
}

void connectToOtherServer(const char* serverIP, int serverPort) {
    string command;
    getline(cin,command);
    // cout << command << " Here" << endl;
    if(command == "connect")
    {
        // cout << "Command satisfied" << endl;
        int serverSocket = socket(AF_INET, SOCK_STREAM, 0);
        if (serverSocket == -1) {
            perror("Socket creation failed");
            return;
        }

        sockaddr_in serverAddr;
        serverAddr.sin_family = AF_INET;
        serverAddr.sin_port = htons(serverPort);

        if (inet_pton(AF_INET, serverIP, &serverAddr.sin_addr) <= 0) {
            perror("Invalid address");
            return;
        }

        if (connect(serverSocket, (struct sockaddr*)&serverAddr, sizeof(serverAddr)) == -1) {
            perror("Connection to server failed");
            close(serverSocket);
            return;
        }

        // You can send and receive data with the connected server here

        char buffer[1024];
        int bytesReceived;
        // cout << "here1" << endl;
        while ((bytesReceived = recv(serverSocket, buffer, sizeof(buffer), 0)) > 0) {
            // cout << "byte got" << bytesReceived << endl;
            cout << buffer << endl;
            for(int i=0;i<bytesReceived;i++)
            {
                cout << buffer[i] << " ";
            }
            write(1,buffer,bytesReceived);
        }
        // Close the server socket
        close(serverSocket);
    }
    
}

int main(int argc,char *argv[]) {

// Dummy Data
    User a;
    a.user_id = "abc";
    a.password = "abc";
    a.ip_address = "12";
    a.is_active = true;
    a.port = "12";
    a.files[{"123","v1"}] = "abc1.txt";
    a.files[{"223","v1"}] = "abc2.txt";
    a.files[{"323","v2"}] = "abc3.txt";
    users["abc"] = a;
    User b;
    b.user_id = "abc2";
    b.password = "abc2";
    b.ip_address = "122";
    b.is_active = true;
    b.port = "122";
    b.files[{"123","v1"}] = "abc1.txt";
    b.files[{"2232","v2"}] = "abc22.txt";
    b.files[{"323","v1"}] = "abc3.txt";
    users["abc2"] = b;
    User v;
    v.user_id = "v";
    v.password = "v";
    v.ip_address = "1221";
    v.is_active = false;
    v.port = "1221";
    users["v"] = v;

    User a1;
    a1.user_id = "a";
    a1.password = "a";
    a1.ip_address = "1222";
    a1.is_active = false;
    a1.port = "1222";
    users["a"] = a1;

    User b1;
    b1.user_id = "b";
    b1.password = "b";
    b1.ip_address = "12221";
    b1.is_active = false;
    b1.port = "12221";
    users["b"] = b1;

    Group c;
    c.accepted_users["abc"]++;
    c.accepted_users["abc2"]++;
    c.accepted_users["v"]++;
    c.accepted_users["a"]++;
    c.accepted_users["b"]++;
    c.owner_user_id = "v";
    c.group_id = "v1";
    groups["v1"] = c;

    fileInfo f1;
    f1.file_name = "abc1.txt";
    f1.no_of_chunks = 10;
    f1.sha = "123";
    f1.size = 10000;
    files["abc1.txt"] = f1;

    fileInfo f2;
    f2.file_name = "abc2.txt";
    f2.no_of_chunks = 100;
    f2.sha = "323";
    f2.size = 100001;
    files["abc3.txt"] = f2;
// Dummy data


    // cout << argc << endl;
    if(argc < 3)
    {
        cerr << "Provide tracker file name and tracker number" << endl;
        exit(1);
    }

    // Reading tracker_info file
    char* trackerInfoFileName = argv[1];
    int readTrackerInfoFileDescriptor = open(trackerInfoFileName,O_RDONLY);
    if(readTrackerInfoFileDescriptor < 0)
    {
        cerr << "Error while opening tracker_info file " << endl;
        exit(1);
    }

    // Getting track no from user argument
    int trackerNo = atoi(argv[2]);

    if(trackerNo > 2 || trackerNo < 1)
    {
        cerr << "Please select tracker no from 1 and 2" << endl;
        close(readTrackerInfoFileDescriptor);
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

    string serverIp = trackerInfo[((trackerNo-1)*2)];
    int serverPort = stoi(trackerInfo[((trackerNo-1)*2)+1]);
    
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

    if (listen(serverSocket, 50) == -1) {
        cerr << "Listening failed" << endl;
        exit(1);
    }

    cout << "Tracker " << trackerNo << " is listening on port " << serverPort << endl;

    // Create a thread to connect to another server
    thread(connectToOtherServer, "127.0.0.1", 9090).detach();

    while (true) {
        sockaddr_in clientAddr;
        socklen_t clientAddrLen = sizeof(clientAddr);
        int clientSocket = accept(serverSocket, (struct sockaddr*)&clientAddr, &clientAddrLen);

        if (clientSocket == -1) {
            cerr << "Tracker Accept failed" << endl;
            continue;
        }

        // Create a new thread to handle the client connection
        thread(inComingClientRequest, clientSocket).detach();
    }

    close(serverSocket);

    return 0;
}