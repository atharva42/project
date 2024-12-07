#include<iostream>
#include<vector>
#include <string>
#include <cstdlib>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include "header.h"
using namespace std;


bool bgfg(vector<string> command)
{
    bool returnValue = true;

    bool backgroundProcess = false;

    if(command.size()!=0 && command[command.size()-1] == "&")
    {
        backgroundProcess = true;
        command.pop_back();
    }

    pid_t pid = fork();
    // cout << pid << endl;

    if(pid == -1)
    {
        perror("fork");
        returnValue = false;
    }
    else if(pid ==0)
    {
        if (backgroundProcess) 
        {
            // Detach from the terminal
            setsid();
        }

        // Execute the command - by rewriting parent code
        string commandString;
        for(auto ele : command)
        {
            commandString = commandString + ele + " ";
        }
        if(commandString.length()>0)
        {
            commandString = commandString.substr(0,commandString.length()-1);
        }
        
        // const char* cmd = commandString.c_str();
        // if (execl("/bin/sh", "/bin/sh", "-c", cmd, nullptr) == -1) {
        //     // cout << "Inside wrong command" << endl;
        //     perror("execl");
        //     returnValue = false;
        // }

        char* charInputArgs[command.size()+1];
        for(int i = 0;i<command.size();i++)
        {
            charInputArgs[i] = const_cast<char*>(command[i].c_str());
        }
        charInputArgs[command.size()] = NULL;
        if (execvp(charInputArgs[0], charInputArgs) == -1) {
            perror("Command Not Found");
            exit(1);
        }

    }
    else
    {
        if(!backgroundProcess) 
        {
            int status;
            // cout << "at time of creatiopn "  << pid << endl;
            CURRENTFOREGROUND = pid;
            waitpid(pid, &status, 0);
        }
        else{
            cout << pid << endl;
            // setpgid(pid, pid);

            // // Install a signal handler for Ctrl+C (SIGINT)
            // signal(SIGINT, [](int signal) {
            //     // Terminate the child process
            //     kill(-pid, SIGINT);
            //     exit(0);
            // });
        }
    }



    return returnValue;
}
