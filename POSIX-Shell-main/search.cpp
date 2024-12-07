#include<iostream>
#include<vector>
#include <dirent.h>         // opendir, readdir, and closedir
#include <sys/types.h>      // size_t and time_t
#include<string.h>
#include <sys/stat.h>       // struct stat
#include <pwd.h>            // struct passwd, getpwuid
#include <grp.h>            // struct group , getgrgid
#include <ctime>            // strftime
#include <iomanip>
#include "header.h"
using namespace std;

bool fileFoundInDirectory(string diriectoryName,string searchFileName)
{
    char* dirName = new char[diriectoryName.length()+1];
    strcpy(dirName,diriectoryName.c_str());

    DIR *directory = opendir(dirName);

    string currentPath = diriectoryName + "/";

    if(directory)
    {
        struct dirent *tupple;
        while ((tupple = readdir(directory))) {
            // cout << tupple->d_name << endl;
            if(strcmp((tupple->d_name) ,".") == 0 || strcmp((tupple->d_name) ,"..") == 0)
            {
                continue;
            }
            if(strcmp((tupple->d_name),searchFileName.c_str()) ==0)
            {
                closedir(directory);
                return true;
            }
            if((tupple->d_type) == DT_DIR)
            {
                if(fileFoundInDirectory(currentPath+(tupple->d_name),searchFileName))
                {
                    closedir(directory);
                    return true;
                }
            }
        }
    }
    closedir(directory);
    return false;
}

void search(vector<string> command)
{
    bool output = false;
    if(command.size()>1)
    {
        string searchFileName = command[1];
        string currentDir = ".";
        if(fileFoundInDirectory(currentDir,searchFileName))
        {
            output = true;
        }
    }
    if(output)
    {
        cout << "True" << endl;
    }
    else
    {
        cout << "False" << endl;
    }
    return;
}