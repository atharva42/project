#include<iostream>
#include<vector>
#include<string.h>
#include <fstream>
#include <sstream>
#include<unistd.h>
#include <termios.h>
#include<fcntl.h>
#include "header.h"
using namespace std;

//Handle redirectional

string readStatusFileState(const string& filePath) {
    string output = "";
    char buffer[1024];

    string line;
    ifstream file(filePath);
    if (file.is_open()) {
        while (getline(file, line)) {
            size_t processStatus = line.find("State:");
            if (processStatus != string::npos) {
                output = output + line.substr(7,1);
            }

            if (processStatus != string::npos) {
                break;
            }
        }
        file.close();
    }
    return output;
}

string readStatusFileVM(const string& filePath) {
    string output = "";
    char buffer[1024];

    string line;
    ifstream file(filePath);
    if (file.is_open()) {
        while (getline(file, line)) {
            size_t processStatus = line.find("VmSize:");
            if (processStatus != string::npos) {
                output = output + line.substr(8);
            }

            if (processStatus != string::npos) {
                break;
            }
        }
        file.close();
    }
    return output;
}


string readFileEXE(const string& filePath) {
    char buffer[1024];

    ssize_t len = readlink(filePath.c_str(), buffer, sizeof(buffer));

    if (len != -1) {
        buffer[len] = '\0';
        return std::string(buffer);
    } else {
        return ""; // Failed to read the link
    }
}

bool isProcessForeground(pid_t pgid) {
    pid_t tcpgid = tcgetpgrp(STDIN_FILENO);
    // cout << " pgid " << pgid << " tc "  << tcpgid << endl;
    return (pgid == tcpgid);
}


void pinfo(vector<string> command)
{
    vector<string> output;
    bool pipe = false;
    bool leftRedirect = false;
    bool rightRedirect = false;
    bool rightAppend = false;
    bool leftAppend = false;
    for(int i = 0;i<command.size();i++)
    {
        if(command[i] == ">>")
        {
            rightAppend = true;
            break;
        }
        if(command[i] == "<<")
        {
            leftAppend = true;
            break;
        }
        if(command[i] == ">")
        {
            rightRedirect = true;
            break;
        }
        if(command[i] == "<")
        {
            leftRedirect = true;
            break;
        }
        if(command[i] == "|")
        {
            pipe = true;
            break;
        }
    }
    if( pipe == true || leftRedirect == true || rightRedirect == true || rightAppend == true || leftAppend == true )
    {

    }
    else{

        string procssIdentifier = "";
        procssIdentifier = (command.size()==1)?"self":command[1];
    
        string statusFilePath = "/proc/" + procssIdentifier + "/status";
        // string getIsBgPath = "/proc/" + procssIdentifier + "/stat";
        string executableFilePath = "/proc/" + procssIdentifier + "/exe";

        pid_t pid = getpid();
        if(procssIdentifier != "self")
        {
            pid = stoi(procssIdentifier);
        }

        pid_t pgid = getpgid(pid);

        char forebackProcess;
        if (isProcessForeground(pgid)) 
        {
            forebackProcess = '+';
        }

        output.push_back("pid -- " + to_string(pid));
        output.push_back("Process Status -- " + readStatusFileState(statusFilePath)+forebackProcess);
        string virtualMemory1 = readStatusFileVM(statusFilePath);
        std::string virtualMemory(virtualMemory1);
        while( virtualMemory.length() > 0 && virtualMemory[0] == ' ')
        {
            virtualMemory = virtualMemory.substr(1);
        }
        output.push_back("memory -- " + virtualMemory + " {Virtual Memory}");
        output.push_back("Executable Path -- " + readFileEXE(executableFilePath));
        
    }
    for(int i=0;i<output.size();i++)
    {
        cout << output[i] << endl;
    }
    return;
}






// R (Running): The process is currently executing or running on the CPU.

// S (Sleeping): The process is sleeping. It is not currently executing but is waiting for an event to wake it up, such as receiving a signal or waiting for I/O.

// D (Uninterruptible Sleep): The process is in an uninterruptible sleep state, typically waiting for I/O operations to complete. This state is not interruptible by signals.

// T (Stopped): The process is stopped, often as a result of receiving a stop signal (e.g., SIGSTOP or Ctrl+Z). It can be resumed later.

// t (Traced or Stopped): The process is being traced by a debugger, but it is also in a stopped state.

// Z (Zombie): The process has completed its execution, but its entry still exists in the process table because its parent process has not yet collected its exit status using the wait() system call. Zombies are eventually removed when the parent collects the status.

// X (Dead): The process is dead (terminated), and its entry is about to be removed from the process table.

// I (Idle): This state is specific to the kernel's idle process, which is a special system process that runs when the CPU has no other tasks to perform.