#include<iostream>
#include<stdio.h>
#include<string.h>
#include<vector>
#include<unistd.h>  // open,close,read
#include<fcntl.h> // used for argument of open system call
#include <sys/stat.h> //mkdir,stat ,chmod
#include <sys/wait.h>
#include <cstdlib>
#include <signal.h>
#include <termios.h>
#include "header.h"
#define commandDelim ";"
#define withinCommandDelim " "
#define quoteDelim "\""
#define quoteDelim1 "\'"
using namespace std;

string HOME = presentWorkingDirectory();
string OLDPWD = "";
int CURRENTFOREGROUND = getpid();
int MAINPROCESSPID = getpid();
string HISTORYFILENAME = HOME+"/.historylist.txt";
int PROMPTLENGTH = 0;
vector<string> HISTORYDATAINVECTOR;
int HISTORYVECTORCOUNT = -1;

void commandSelection(vector<string> command)
{
    if(command[0] == "pwd")
    {
        string pwd = presentWorkingDirectory();
        cout << pwd << endl;
    }
    else if(command[0] == "echo")
    {
        echo(command);
    }
    else if(command[0] == "cd")
    {
        cd(command);
    }
    else if(command[0] == "ls")
    {
        ls(command);
    }
    else if(command[0] == "pinfo")
    {
        pinfo(command);
    }
    else if(command[0] == "search")
    {
        search(command);
    }
    else if(command[0] == "history")
    {
        showHistory(command);
    }
    else if(command[0] == "exit")
    {
        exit(0);
    }
    else{
        // cout << command[0] << endl;
        if(!bgfg(command))
        {
            cout << "Invalid Command" << endl;
        }
    }
}

int main()
{    
    createHistoryFile();
    getHistoryFileDataIntoVector();

    while(true)
    {
        signal(SIGINT, signalInputHandler);
        // signal(SIGQUIT, signalQuitHandler);
        signal(SIGTSTP, signalBGHandler);
        // cout << getpid() << endl;
        // cout << quoteDelim[0];
        // return 0;

        // string HOME = presentWorkingDirectory();
          
        display();

        HISTORYVECTORCOUNT = -1;

        string input;
        // getline(cin,input);
        input = userInput();

        if(input.length()<1)
        {
            continue;
        }

        //write into history file
        writeHistory(input);

        char* charInput = new char[input.size() + 1];
        strcpy(charInput, input.c_str());

        char* commandToken = strtok(charInput,commandDelim);

        vector<string> command_temp;

        while(commandToken != NULL)
        {
            // cout << commandToken << endl;

            command_temp.push_back(commandToken);            

            commandToken = strtok(NULL, commandDelim);
        }

        vector<vector<string>> command;

        for(int i=0;i<command_temp.size();i++)
        {
            int ptr =0;
            char* charCommandToken = new char[command_temp[i].size() + 1];
            strcpy(charCommandToken, command_temp[i].c_str());

            char* argumentToken = strtok(charCommandToken, withinCommandDelim);
            vector<string> argument;
            while (argumentToken != NULL) {
                
                
                if (argumentToken[0] == quoteDelim[0]) {
                    string quoted = "";
                    int m;
                    int start =0;
                    int end = 0;
                    for(m=ptr;m<command_temp[i].size();m++)
                    {
                        if(command_temp[i][m] == quoteDelim[0] && start == 0)
                        {
                            start = m;
                        }
                        else if(command_temp[i][m] == quoteDelim[0])
                        {
                            end = m;
                            break;
                        }
                    }
                    quoted = command_temp[i].substr(start+1,end-start-1);
                    // cout << "quoted " << quoted << endl;
                    ptr = end+1;
                    
                    // while (argumentToken[strlen(argumentToken) - 1] != quoteDelim[0] && argumentToken!=NULL) {
                    //     quoted = quoted + argumentToken + " ";
                    //     argumentToken = strtok(nullptr, withinCommandDelim);
                    //     cout << "argument1 " << argumentToken << endl;
                    //     if( argumentToken == NULL)
                    //     {
                    //         cout << "break" << endl;
                    //         break;
                    //     }
                    // }
                    while (argumentToken[strlen(argumentToken) - 1] != quoteDelim[0] && (argumentToken = strtok(nullptr, withinCommandDelim)) != nullptr) {
                    }
                    
                    argument.push_back(quoted);
                } 
                // else if (argumentToken[0] == quoteDelim1[0]) {
                //     string quoted = "";
                //     int m;
                //     int start =0;
                //     int end = 0;
                //     for(m=ptr;m<command_temp[i].size();m++)
                //     {
                //         if(command_temp[i][m] == quoteDelim1[0] && start == 0)
                //         {
                //             start = m;
                //         }
                //         else if(command_temp[i][m] == quoteDelim1[0])
                //         {
                //             end = m;
                //             break;
                //         }
                //     }
                //     quoted = command_temp[i].substr(start+1,end-start-1);
                //     // cout << "quoted " << quoted << endl;
                //     ptr = end+1;
                    
                //     // while (argumentToken[strlen(argumentToken) - 1] != quoteDelim[0] && argumentToken!=NULL) {
                //     //     quoted = quoted + argumentToken + " ";
                //     //     argumentToken = strtok(nullptr, withinCommandDelim);
                //     //     cout << "argument1 " << argumentToken << endl;
                //     //     if( argumentToken == NULL)
                //     //     {
                //     //         cout << "break" << endl;
                //     //         break;
                //     //     }
                //     // }
                //     while (argumentToken[strlen(argumentToken) - 1] != quoteDelim1[0] && (argumentToken = strtok(nullptr, withinCommandDelim)) != nullptr) {
                //     }
                    
                //     argument.push_back(quoted);
                // } 
                else {
                    argument.push_back(argumentToken);
                }

                argumentToken = strtok(NULL, withinCommandDelim);
            }
            command.push_back(argument);
            argument.clear();

            delete[] charCommandToken;
        }

        command_temp.clear();
        delete[] charInput;

        // for(int i=0;i<command.size();i++)
        // {
        //     cout << command[i].size() << endl;
        //     for(auto x : command[i])
        //     {
        //         cout << x.size() << " ";
        //         cout << x << " ";
        //     }
        //     cout << endl;
        // }

        int inputFileStdInDescriptor = dup(0);
        int outpueFileStdOutDescriptor = dup(1);

        for(int i=0;i<command.size();i++)
        {
            vector<vector<string>> pipeCommands;
            vector<string> pipeTempCommand;
            int noOfPipes = 0;
            bool pipeErrorFlag = false;
            for(int j=0;j<command[i].size();j++)
            {
                if(command[i][j] == "|")
                {
                    noOfPipes++;
                    pipeCommands.push_back(pipeTempCommand);
                    pipeTempCommand.clear();
                }
                else{
                    pipeTempCommand.push_back(command[i][j]);
                }
            }
            if(pipeTempCommand.size()>0)
            {
                pipeCommands.push_back(pipeTempCommand);
                pipeTempCommand.clear();
            }

            // cout << noOfPipes;

            if(noOfPipes > 0)
            {
                vector<int *> pipeFds(noOfPipes);

                for (int m = 0; m < noOfPipes; m++) {
                    int* pipeFd = new int[2];
                    if (pipe(pipeFd) == -1) {
                        perror("Pipe creation failed");
                        return 1;
                    }
                    pipeFds[m] = pipeFd;
                }

                // for(int z=0;z<pipeFds.size();z++)
                // {
                //     cout << pipeFds[z][0] << " " << pipeFds[z][1];
                // }

                vector<int> childs;

                for(int curcmd =0;curcmd<noOfPipes+1;curcmd++)
                {
                    // cout << curcmd << endl;
                    // cout << "Inside child" << endl;
                    int childFork = fork();
                    if(childFork == -1)
                    {
                        perror("Pipe creation failed");
                        pipeErrorFlag = true;
                        break;
                    }

                    if(childFork == 0)
                    {
                        // cout << "main child" << endl;
                        if(curcmd == 0)
                        {
                            // cout << "0th child" << endl;
                            for(int curpipe=0;curpipe<noOfPipes;curpipe++)
                            {
                                if(curpipe!=0)
                                {
                                    close(pipeFds[curpipe][0]);
                                    close(pipeFds[curpipe][1]);
                                }
                                else{
                                    close(pipeFds[curpipe][0]);
                                }
                            }
                                
                            dup2(pipeFds[0][1],1);
                            dup2(inputFileStdInDescriptor,0);


                            ////////////////////////////////add input out put redirection /////////////////////////

                            int count = 0;
                            vector<string> subCommands1;
                            vector<string> subCommands2;
                            string inputFileName = "";
                            string outputFileName = "";
                            bool directionArrived = false;
                            bool errorCaught = false;
                            while(count < pipeCommands[curcmd].size())
                            {
                                if(pipeCommands[curcmd][count] == ">")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    outputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int writeFileDescriptor = open(outputFileName.c_str(), O_WRONLY | O_CREAT | O_TRUNC,0644 ); 
                                    if(writeFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening destination file ");
                                        break;
                                    }
                                    
                                    //set sstdout
                                    if (dup2(writeFileDescriptor, 1) == -1) {                       //===============
                                        errorCaught = true;
                                        close(writeFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(writeFileDescriptor);

                                }
                                else if(pipeCommands[curcmd][count] == ">>")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    outputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int writeFileDescriptor = open(outputFileName.c_str(), O_WRONLY | O_CREAT | O_APPEND , 0644 ); 
                                    mode_t outputFileNameMode = 0644;
                                    if(writeFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening destination file ");
                                        break;
                                    }

                                    //set sstdout
                                    if (dup2(writeFileDescriptor, 1) == -1) {             //========================
                                        errorCaught = true;
                                        close(writeFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(writeFileDescriptor);
                                }
                                else if(pipeCommands[curcmd][count] == "<")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    inputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int readFileDescriptor = open(inputFileName.c_str(), O_RDONLY); 
                                    
                                    if(readFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening input file ");
                                        break;
                                    }

                                    //set sstdout
                                    if (dup2(readFileDescriptor, 0) == -1) {               ////==================
                                        errorCaught = true;
                                        close(readFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(readFileDescriptor);
                                }
                                else{
                                    if(!directionArrived){
                                        subCommands1.push_back(pipeCommands[curcmd][count]);
                                    }
                                }

                                count++;
                            }

                            //call commandSelection

                            if(!errorCaught)
                            {
                                commandSelection(subCommands1);
                            }

                            subCommands1.clear();
                            subCommands2.clear();


                            dup2(pipeFds[0][1],1);
                            dup2(inputFileStdInDescriptor,0);


                            ////////////////////////////////end input out put redirection /////////////////////////

                            // commandSelection(pipeCommands[curcmd]);

                            close(pipeFds[0][1]);
                            exit(1);
                        }
                        else if(curcmd == noOfPipes)
                        {
                            // cout << "end child" << endl;
                            for(int curpipe=0;curpipe<noOfPipes;curpipe++)
                            {
                                if(curpipe!=noOfPipes-1)
                                {
                                    close(pipeFds[curpipe][0]);
                                    close(pipeFds[curpipe][1]);
                                }
                            }
                            close(pipeFds[curcmd-1][1]);
                                
                            dup2(pipeFds[curcmd-1][0],0);
                            dup2(outpueFileStdOutDescriptor,1);

                            ////////////////////////////////add input out put redirection /////////////////////////

                            int count = 0;
                            vector<string> subCommands1;
                            vector<string> subCommands2;
                            string inputFileName = "";
                            string outputFileName = "";
                            bool directionArrived = false;
                            bool errorCaught = false;
                            while(count < pipeCommands[curcmd].size())
                            {
                                if(pipeCommands[curcmd][count] == ">")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    outputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int writeFileDescriptor = open(outputFileName.c_str(), O_WRONLY | O_CREAT | O_TRUNC,0644 ); 
                                    if(writeFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening destination file ");
                                        break;
                                    }
                                    
                                    //set sstdout
                                    if (dup2(writeFileDescriptor, 1) == -1) {                       //===============
                                        errorCaught = true;
                                        close(writeFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(writeFileDescriptor);

                                }
                                else if(pipeCommands[curcmd][count] == ">>")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    outputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int writeFileDescriptor = open(outputFileName.c_str(), O_WRONLY | O_CREAT | O_APPEND , 0644 ); 
                                    mode_t outputFileNameMode = 0644;
                                    if(writeFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening destination file ");
                                        break;
                                    }

                                    //set sstdout
                                    if (dup2(writeFileDescriptor, 1) == -1) {             //========================
                                        errorCaught = true;
                                        close(writeFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(writeFileDescriptor);
                                }
                                else if(pipeCommands[curcmd][count] == "<")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    inputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int readFileDescriptor = open(inputFileName.c_str(), O_RDONLY); 
                                    
                                    if(readFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening input file ");
                                        break;
                                    }

                                    //set sstdout
                                    if (dup2(readFileDescriptor, 0) == -1) {               ////==================
                                        errorCaught = true;
                                        close(readFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(readFileDescriptor);
                                }
                                else{
                                    if(!directionArrived){
                                        subCommands1.push_back(pipeCommands[curcmd][count]);
                                    }
                                }

                                count++;
                            }

                            //call commandSelection

                            if(!errorCaught)
                            {
                                commandSelection(subCommands1);
                            }

                            subCommands1.clear();
                            subCommands2.clear();


                            dup2(pipeFds[curcmd-1][0],0);
                            dup2(outpueFileStdOutDescriptor,1);

                            ////////////////////////////////end input out put redirection /////////////////////////

                            // commandSelection(pipeCommands[curcmd]);

                            close(pipeFds[curcmd-1][0]);
                            exit(1);
                        }
                        else{
                            // cout << "else child" << endl;
                            for(int curpipe=0;curpipe<noOfPipes;curpipe++)
                            {
                                if(curpipe!=curcmd-1 && curpipe!=curcmd)
                                {
                                    close(pipeFds[curpipe][0]);
                                    close(pipeFds[curpipe][1]);
                                }
                            }
                            close(pipeFds[curcmd-1][1]);
                            close(pipeFds[curcmd][0]);
                                
                            dup2(pipeFds[curcmd-1][0],0);
                            dup2(pipeFds[curcmd][1],1);

                            ////////////////////////////////add input out put redirection /////////////////////////

                            int count = 0;
                            vector<string> subCommands1;
                            vector<string> subCommands2;
                            string inputFileName = "";
                            string outputFileName = "";
                            bool directionArrived = false;
                            bool errorCaught = false;
                            while(count < pipeCommands[curcmd].size())
                            {
                                if(pipeCommands[curcmd][count] == ">")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    outputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int writeFileDescriptor = open(outputFileName.c_str(), O_WRONLY | O_CREAT | O_TRUNC,0644 ); 
                                    if(writeFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening destination file ");
                                        break;
                                    }
                                    
                                    //set sstdout
                                    if (dup2(writeFileDescriptor, 1) == -1) {                       //===============
                                        errorCaught = true;
                                        close(writeFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(writeFileDescriptor);

                                }
                                else if(pipeCommands[curcmd][count] == ">>")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    outputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int writeFileDescriptor = open(outputFileName.c_str(), O_WRONLY | O_CREAT | O_APPEND , 0644 ); 
                                    mode_t outputFileNameMode = 0644;
                                    if(writeFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening destination file ");
                                        break;
                                    }

                                    //set sstdout
                                    if (dup2(writeFileDescriptor, 1) == -1) {             //========================
                                        errorCaught = true;
                                        close(writeFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(writeFileDescriptor);
                                }
                                else if(pipeCommands[curcmd][count] == "<")
                                {
                                    count++;
                                    if(count>=pipeCommands[curcmd].size())
                                    {
                                        errorCaught = true;
                                        break;
                                    }
                                    inputFileName = pipeCommands[curcmd][count];

                                    //open file
                                    int readFileDescriptor = open(inputFileName.c_str(), O_RDONLY); 
                                    
                                    if(readFileDescriptor < 0)
                                    {
                                        errorCaught = true;
                                        perror("Error while opening input file ");
                                        break;
                                    }

                                    //set sstdout
                                    if (dup2(readFileDescriptor, 0) == -1) {               ////==================
                                        errorCaught = true;
                                        close(readFileDescriptor);
                                        perror("Error duplicating file descriptor");
                                        break;
                                    }

                                    //close file
                                    close(readFileDescriptor);
                                }
                                else{
                                    if(!directionArrived){
                                        subCommands1.push_back(pipeCommands[curcmd][count]);
                                    }
                                }

                                count++;
                            }

                            //call commandSelection

                            if(!errorCaught)
                            {
                                commandSelection(subCommands1);
                            }

                            subCommands1.clear();
                            subCommands2.clear();


                            dup2(pipeFds[curcmd-1][0],0);
                            dup2(pipeFds[curcmd][1],1);


                            ////////////////////////////////end input out put redirection /////////////////////////

                            // commandSelection(pipeCommands[curcmd]);

                            close(pipeFds[curcmd-1][0]);
                            close(pipeFds[curcmd][1]);
                            exit(1);
                        }   

                    }
                    else{
                        //parent
                        childs.push_back(childFork);
                        // wait(NULL);
                    }
                }
                
                if(pipeErrorFlag == true)
                {
                    continue;
                }

                // //Parent
                
                for (int m = 0; m < noOfPipes; m++) {
                    close(pipeFds[m][0]);
                    close(pipeFds[m][1]);
                }

                // wait(NULL);
                // Wait for all child processes to finish
                // for (int m = 0; m < childs.size(); m++) {
                //     waitpid(childs[m], NULL, 0);
                // }
                dup2(outpueFileStdOutDescriptor,1);
                dup2(inputFileStdInDescriptor,0);
                sleep(1.5);
            }
            else
            {
                // cout << "Inside Normal";
                int count = 0;
                vector<string> subCommands1;
                vector<string> subCommands2;
                string inputFileName = "";
                string outputFileName = "";
                bool directionArrived = false;
                bool errorCaught = false;
                while(count < command[i].size())
                {
                    if(command[i][count] == ">")
                    {
                        count++;
                        if(count>=command[i].size())
                        {
                            errorCaught = true;
                            break;
                        }
                        outputFileName = command[i][count];

                        //open file
                        int writeFileDescriptor = open(outputFileName.c_str(), O_WRONLY | O_CREAT | O_TRUNC,0644 ); 
                        if(writeFileDescriptor < 0)
                        {
                            errorCaught = true;
                            perror("Error while opening destination file ");
                            break;
                        }
                        
                        //set sstdout
                        if (dup2(writeFileDescriptor, 1) == -1) {
                            errorCaught = true;
                            close(writeFileDescriptor);
                            perror("Error duplicating file descriptor");
                            break;
                        }

                        //close file
                        close(writeFileDescriptor);

                    }
                    else if(command[i][count] == ">>")
                    {
                        count++;
                        if(count>=command[i].size())
                        {
                            errorCaught = true;
                            break;
                        }
                        outputFileName = command[i][count];

                        //open file
                        int writeFileDescriptor = open(outputFileName.c_str(), O_WRONLY | O_CREAT | O_APPEND , 0644 ); 
                        mode_t outputFileNameMode = 0644;
                        if(writeFileDescriptor < 0)
                        {
                            errorCaught = true;
                            perror("Error while opening destination file ");
                            break;
                        }

                        //set sstdout
                        if (dup2(writeFileDescriptor, 1) == -1) {
                            errorCaught = true;
                            close(writeFileDescriptor);
                            perror("Error duplicating file descriptor");
                            break;
                        }

                        //close file
                        close(writeFileDescriptor);
                    }
                    else if(command[i][count] == "<")
                    {
                        count++;
                        if(count>=command[i].size())
                        {
                            errorCaught = true;
                            break;
                        }
                        inputFileName = command[i][count];

                        //open file
                        int readFileDescriptor = open(inputFileName.c_str(), O_RDONLY); 
                        
                        if(readFileDescriptor < 0)
                        {
                            errorCaught = true;
                            perror("Error while opening input file ");
                            break;
                        }

                        //set sstdout
                        if (dup2(readFileDescriptor, 0) == -1) {
                            errorCaught = true;
                            close(readFileDescriptor);
                            perror("Error duplicating file descriptor");
                            break;
                        }

                        //close file
                        close(readFileDescriptor);
                    }
                    else{
                        if(!directionArrived){
                            subCommands1.push_back(command[i][count]);
                        }
                    }

                    count++;
                }

                //call commandSelection

                if(!errorCaught)
                {
                    commandSelection(subCommands1);
                }

                subCommands1.clear();
                subCommands2.clear();


                //set stdout to original
                dup2(inputFileStdInDescriptor, 0);

                //set stdout to original
                dup2(outpueFileStdOutDescriptor, 1);
            }
            

            noOfPipes = 0;
            pipeErrorFlag = false;
            pipeTempCommand.clear();
            for(auto ele : pipeCommands)
            {
                ele.clear();
            }
            pipeCommands.clear();
            // cout << "at end of while" << endl;

                // if(command[i][0] == "pwd")
                // {
                //     string pwd = presentWorkingDirectory();
                //     cout << pwd << endl;
                // }
                // else if(command[i][0] == "echo")
                // {
                //     echo(command[i]);
                // }
                // else if(command[i][0] == "cd")
                // {
                //     cd(command[i]);
                // }
                // else if(command[i][0] == "ls")
                // {
                //     ls(command[i]);
                // }
                // else if(command[i][0] == "pinfo")
                // {
                //     pinfo(command[i]);
                // }
                // else if(command[i][0] == "search")
                // {
                //     search(command[i]);
                // }
                // else if(command[i][0] == "exit")
                // {
                //     exit(0);
                // }
                // else{

                //     if(!bgfg(command[i]))
                //     {
                //         cout << "Invalid Command" << endl;
                //     }
                // }
            
        }

    }
    return 0 ;
}

