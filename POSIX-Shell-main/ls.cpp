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

void ls(vector<string> command)
{
    bool pipe = false;
    bool leftRedirect = false;
    bool rightRedirect = false;
    bool rightAppend = false;
    bool leftAppend = false;

    vector<string> output;
    vector<string> errorsOfCommand;

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
        bool aFlag = false;
        bool lFlag = false;
        // for(int i =0;i<command.size();i++)
        // {
        //     cout << command[i] << " ";
        // }

        for(int i = 1;i<command.size();i++)
        {
            if(command[i] == "-l")
            {
                lFlag = true;
            }
            if(command[i] == "-a")
            {
                aFlag = true;
            }
            if(command[i] == "-la")
            {
                lFlag = true;
                aFlag = true;
            }
            if(command[i] == "-al")
            {
                lFlag = true;
                aFlag = true;
            }
        }

        vector<string> listOfDir;

        for(int i = 1;i<command.size();i++)
        {
            if(command[i] == "<<" || command[i] == ">>" || command[i] == ">" || command[i] == "<" || command[i] == "|")
            {
                break;
            }
            if(command[i] == "-l" || command[i] == "-a" || command[i] == "-la" || command[i] == "-al")
            {
                continue;
            }
            if(command[i] == "~")
            {
                listOfDir.push_back(HOME);
            }
            else{
                listOfDir.push_back(command[i]);
            }
        }

        if(listOfDir.size() == 0)
        {
            listOfDir.push_back(".");
        }


        // cout << endl << endl << "directories" << endl;

        // for(auto x : listOfDir)
        // {
        //     cout << x << endl;
        // }

        // cout << endl<<endl;

        // cout << "flags" << endl << endl;

        // cout << aFlag << " " << lFlag << endl << endl;


        for(int i=0;i<listOfDir.size();i++)
        {
            if(lFlag == true && aFlag == true)
            {
                // cout << "inside" << endl;
                char* dirName = new char[listOfDir[i].size() + 1];
                strcpy(dirName, listOfDir[i].c_str());

                DIR *directory = opendir(dirName);

                if (!directory) {
                    // cout << "Error opening directory " << dirName << endl;
                    errorsOfCommand.push_back("ls: cannot access '" + listOfDir[i] +"': No such file or directory");
                    continue;
                }

                if(listOfDir.size()!=1)
                {
                    output.push_back(listOfDir[i]+":");
                }

                int total_blocks = 0;
                int totalEntryInOneDir=0;

                struct dirent *tupple;
                while ((tupple = readdir(directory))) {
                    
                    // output.push_back(tupple->d_name);
                    // cout << tupple -> d_name << endl;
                    // if((tupple->d_name)[0] == '.')
                    // {
                    //     continue;
                    // }
                    
                    struct stat fileStat;

                    string currentFileString = listOfDir[i]+"/"+(tupple->d_name);
                    char* currentFile = new char[currentFileString.size() + 1];
                    strcpy(currentFile, currentFileString.c_str());
                    if (stat(currentFile, &fileStat) == -1) {
                        perror("stat");
                    }

                    string allInfo = "";
                    // Get file permissions
                    allInfo += S_ISDIR(fileStat.st_mode) ? 'd' : '-';
                    allInfo += (fileStat.st_mode & S_IRUSR) ? 'r' : '-';
                    allInfo += (fileStat.st_mode & S_IWUSR) ? 'w' : '-';
                    allInfo += (fileStat.st_mode & S_IXUSR) ? 'x' : '-';
                    allInfo += (fileStat.st_mode & S_IRGRP) ? 'r' : '-';
                    allInfo += (fileStat.st_mode & S_IWGRP) ? 'w' : '-';
                    allInfo += (fileStat.st_mode & S_IXGRP) ? 'x' : '-';
                    allInfo += (fileStat.st_mode & S_IROTH) ? 'r' : '-';
                    allInfo += (fileStat.st_mode & S_IWOTH) ? 'w' : '-';
                    allInfo += (fileStat.st_mode & S_IXOTH) ? 'x' : '-';
                    allInfo += ' ';

                    allInfo = allInfo + to_string(fileStat.st_nlink) + " ";
                    
                    // Get username and group name
                    struct passwd *pw = getpwuid(fileStat.st_uid);
                    allInfo = allInfo + (pw ? pw->pw_name : "unknown") + " ";

                    struct group *gr = getgrgid(fileStat.st_gid);
                    allInfo = allInfo + (gr ? gr->gr_name : "unknown") + " ";

                    string currentFileSize = to_string(fileStat.st_size);
                    int cnt = currentFileSize.length();
                    cnt = 9-cnt;
                    while(cnt>0)
                    {
                        currentFileSize = " " + currentFileSize;
                        cnt--;
                    }

                    allInfo = allInfo + currentFileSize + " ";

                    // Get modification time
                    char timeString[80];
                    std::strftime(timeString, sizeof(timeString), "%b %d %H:%M", localtime(&fileStat.st_mtime));
                    
                    
                    // "%b %d %H:%M": This is a format string that specifies how the time should be formatted. It consists of the following components:
                    // %b: Abbreviated month name (e.g., "Jan" for January).
                    // %d: Day of the month (e.g., "01" for the 1st day).
                    // %H: Hour in 24-hour format (e.g., "14" for 2 PM).
                    // %M: Minute (e.g., "05").
                    
                    
                    allInfo = allInfo + timeString + " ";

                    
                    allInfo = allInfo + tupple->d_name + " ";

                    output.push_back(allInfo);
                    // cout << " end" << endl;

                    totalEntryInOneDir++;
                    total_blocks = total_blocks + (fileStat.st_blocks / 2);
                }
                closedir(directory);
                string totalBlockCount = "total "+to_string(total_blocks);
                output.insert(output.begin()+(output.size()-totalEntryInOneDir), totalBlockCount);

            }
            else if(aFlag == true)
            {
                char* dirName = new char[listOfDir[i].size() + 1];
                strcpy(dirName, listOfDir[i].c_str());

                DIR *directory = opendir(dirName);

                if (!directory) {
                    // cout << "Error opening directory " << dirName << endl;
                    errorsOfCommand.push_back("ls: cannot access '" + listOfDir[i] +"': No such file or directory");
                    continue;
                }

                if(listOfDir.size()!=1)
                {
                    output.push_back(listOfDir[i]+":");
                }

                struct dirent *tupple;
                while ((tupple = readdir(directory))) {
                        output.push_back(tupple->d_name);
                }

                closedir(directory);
            }
            else if( lFlag == true)
            {
                // cout << "inside" << endl;
                char* dirName = new char[listOfDir[i].size() + 1];
                strcpy(dirName, listOfDir[i].c_str());

                DIR *directory = opendir(dirName);

                if (!directory) {
                    // cout << "Error opening directory " << dirName << endl;
                    errorsOfCommand.push_back("ls: cannot access '" + listOfDir[i] +"': No such file or directory");
                    continue;
                }

                if(listOfDir.size()!=1)
                {
                    output.push_back(listOfDir[i]+":");
                }

                int total_blocks = 0;
                int totalEntryInOneDir=0;
                
                struct dirent *tupple;
                while ((tupple = readdir(directory))) {
                   
                    // output.push_back(tupple->d_name);
                    // cout << tupple -> d_name << endl;
                    if((tupple->d_name)[0] == '.')
                    {
                        continue;
                    }
                     
                    struct stat fileStat;

                    string currentFileString = listOfDir[i]+"/"+(tupple->d_name);
                    char* currentFile = new char[currentFileString.size() + 1];
                    strcpy(currentFile, currentFileString.c_str());
                    if (stat(currentFile, &fileStat) == -1) {
                        perror("stat");
                    }

                    string allInfo = "";
                    // Get file permissions
                    allInfo += S_ISDIR(fileStat.st_mode) ? 'd' : '-';
                    allInfo += (fileStat.st_mode & S_IRUSR) ? 'r' : '-';
                    allInfo += (fileStat.st_mode & S_IWUSR) ? 'w' : '-';
                    allInfo += (fileStat.st_mode & S_IXUSR) ? 'x' : '-';
                    allInfo += (fileStat.st_mode & S_IRGRP) ? 'r' : '-';
                    allInfo += (fileStat.st_mode & S_IWGRP) ? 'w' : '-';
                    allInfo += (fileStat.st_mode & S_IXGRP) ? 'x' : '-';
                    allInfo += (fileStat.st_mode & S_IROTH) ? 'r' : '-';
                    allInfo += (fileStat.st_mode & S_IWOTH) ? 'w' : '-';
                    allInfo += (fileStat.st_mode & S_IXOTH) ? 'x' : '-';
                    allInfo += ' ';

                    allInfo = allInfo + to_string(fileStat.st_nlink) + " ";
                    
                    // Get username and group name
                    struct passwd *pw = getpwuid(fileStat.st_uid);
                    allInfo = allInfo + (pw ? pw->pw_name : "unknown") + " ";

                    struct group *gr = getgrgid(fileStat.st_gid);
                    allInfo = allInfo + (gr ? gr->gr_name : "unknown") + " ";

                    string currentFileSize = to_string(fileStat.st_size);
                    int cnt = currentFileSize.length();
                    cnt = 9-cnt;
                    while(cnt>0)
                    {
                        currentFileSize = " " + currentFileSize;
                        cnt--;
                    }

                    allInfo = allInfo + currentFileSize + " ";

                    // Get modification time
                    char timeString[80];
                    std::strftime(timeString, sizeof(timeString), "%b %d %H:%M", localtime(&fileStat.st_mtime));
                    allInfo = allInfo + timeString + " ";

                    
                    allInfo = allInfo + tupple->d_name + " ";

                    output.push_back(allInfo);
                    // cout << " end" << endl;
                    totalEntryInOneDir++;
                    total_blocks = total_blocks + (fileStat.st_blocks / 2);

                }
                closedir(directory);

                // cout << "totalEntryInOneDir " << totalEntryInOneDir << " output.size() " << output.size()<< endl; 

                string totalBlockCount = "total "+to_string(total_blocks);
                output.insert(output.begin()+(output.size()-totalEntryInOneDir), totalBlockCount);
                // output.push_back(totalBlockCount);
            }
            else
            {
                char* dirName = new char[listOfDir[i].size() + 1];
                strcpy(dirName, listOfDir[i].c_str());

                DIR *directory = opendir(dirName);

                if (!directory) {
                    // cout << "Error opening directory " << dirName << endl;
                    errorsOfCommand.push_back("ls: cannot access '" + listOfDir[i] +"': No such file or directory");
                    continue;
                }

                if(listOfDir.size()!=1)
                {
                    output.push_back(listOfDir[i]+":");
                }

                struct dirent *tupple;
                while ((tupple = readdir(directory))) {
                    if((tupple->d_name)[0] != '.')
                    {
                        output.push_back(tupple->d_name);
                    }
                }

                closedir(directory);
            }

            if(i != listOfDir.size()-1)
            {
                output.push_back("");
            }
            
        }
        for(int i=0;i<errorsOfCommand.size();i++)
        {
            cout << errorsOfCommand[i] << endl;
        }
        for(int i=0;i<output.size();i++)
        {
            cout << output[i] << endl;
        }
    }
    return;
}


// d_ino: This is an inode number, which is a unique identifier for the file or directory.
// d_off: This is the offset of the next dirent structure in the directory stream. It's typically not used by applications.
// d_reclen: This is the length of the dirent structure.
// d_type: This member indicates the type of the directory entry. Possible values include DT_REG for regular files, DT_DIR for directories, DT_LNK for symbolic links, and so on.
// d_name: This member is a character array that contains the name of the directory entry.
