#include<iostream>
#include<stdio.h>
#include<unistd.h>
#include<vector>
#include<string.h>
#include "header.h"
using namespace std;

void cd(vector<string> command)
{
    string curentDirectory = presentWorkingDirectory();
    if(command.size() > 2)
    {
        cerr << "Invalid arguments" << endl;
        return;
    }
    else if(command.size() == 1)
    {
        char* path = new char[HOME.length()+1];
        strcpy(path,HOME.c_str());
        if (chdir(path) == 0) {
            OLDPWD = curentDirectory;
        } 
        else {
            perror("Failed to change directory");
            return;
        }
        delete[] path;
    }
    else
    {
        if(command[1] == "~")
        {
            char* path = new char[HOME.length()+1];
            strcpy(path,HOME.c_str());
            if (chdir(path) == 0) {
                OLDPWD = curentDirectory;
            } 
            else {
                perror("Failed to change directory");
                return;
            }
            delete[] path;
        }
        else if(command[1] == "-")
        {
            if(OLDPWD == "")
            {
                cerr << "cd: OLDPWD not set" << endl;
            }
            else{
                char* path = new char[OLDPWD.length()+1];
                strcpy(path,OLDPWD.c_str());
                if (chdir(path) == 0) {
                    cout << presentWorkingDirectory() << endl;
                    OLDPWD = curentDirectory;
                } 
                else {
                    perror("Failed to change directory");
                    return;
                }
                delete[] path;
            }
        }
        else
        {
            char* path = new char[command[1].size()+1];
            strcpy(path,command[1].c_str());
            if (chdir(path) == 0) {
                OLDPWD = curentDirectory;
            } 
            else 
            {
                perror("Failed to change directory");
                return;
            }
            delete[] path;
        }
    }

    return;
}