#include<iostream>
#include<vector>
#include<unistd.h>  // open,close,read
#include<fcntl.h> // used for argument of open system call
#include <sys/stat.h> //mkdir,stat ,chmod
#include <iostream>
#include <fstream>
#include <string>
#include<vector>
#include "header.h"
using namespace std;

//issue is in storing it in file

void createHistoryFile()
{
    int writeFileDescriptor = open(HISTORYFILENAME.c_str(), O_WRONLY | O_CREAT,0644); 
    if(writeFileDescriptor >= 0)
    {
        close(writeFileDescriptor);
    }
}

void showHistory(vector<string> command)
{
    int limit = 10;
    if(command.size() > 1)
    {
        limit = stoi(command[1]);
        if(limit>20)
        {
            cout << "Only 20 commands available in history" << endl; 
            return;
        }
    }
    ifstream inputFile(HISTORYFILENAME.c_str());
    vector<string> output;

    if (inputFile.is_open()) {
        string line;
        int lineCount = 0;

        while (lineCount < limit && getline(inputFile, line)) {
            output.push_back(line);
            lineCount++;
        }
        inputFile.close();
    }
    
    for(int i=output.size()-1;i>=0;i--)
    {
        cout << output[i] << endl;
    }   
}

void writeHistory(string input)
{
    ifstream fileW(HISTORYFILENAME.c_str(), std::ios::in | std::ios::out);
    vector<string> linesOfFiles;
    if (fileW.is_open()) {
        int totalNoOfLines = 0;
        string line;
        
        while (getline(fileW, line)) {
            linesOfFiles.push_back(line);
        }

        if(linesOfFiles.size() > 0 && linesOfFiles[0] == input)
        {
            // cout << "Already exist" << endl;
            fileW.close();
            return;
        }
    }

    ofstream writefile(HISTORYFILENAME.c_str(), ofstream::out | ofstream::trunc);

     if (writefile.is_open()) 
     {
        HISTORYDATAINVECTOR.clear();
        HISTORYDATAINVECTOR.push_back(input);

        input = input + "\n";

        writefile << input;

        int writeBack = linesOfFiles.size();
        // cout << "file size " << writeBack << endl;
        if(writeBack >= 20)
        {
            writeBack = 19;
        }

        // cout << "new write back " << writeBack << endl;

        for(int i=0;i<writeBack;i++)
        {
            writefile << (linesOfFiles[i]+"\n");
            HISTORYDATAINVECTOR.push_back(linesOfFiles[i]);
        }
        writefile.close();
    }
}

void getHistoryFileDataIntoVector()
{
    ifstream inputFile(HISTORYFILENAME.c_str());
    if (inputFile.is_open()) {
        string line;
        int lineCount = 0;

        while (getline(inputFile, line)) {
            HISTORYDATAINVECTOR.push_back(line);
        }
        inputFile.close();
    }
}

string upKeyHistory(string input)
{
    string output = "";
    int historyVectorSize = (HISTORYDATAINVECTOR.size()-1);
    if(HISTORYVECTORCOUNT >= historyVectorSize || HISTORYVECTORCOUNT >= 19)
    {
        HISTORYVECTORCOUNT = HISTORYDATAINVECTOR.size()-1;
    }
    else
    {
        HISTORYVECTORCOUNT++;
    }
    if(HISTORYDATAINVECTOR.size() > 0)
    {
        cout << "\r";
        int len = PROMPTLENGTH + input.length() + 1 + 10;
        for(int i=0;i<len;i++)
        {
            cout << " ";
        }
        cout << "\r";
        display();
        cout << HISTORYDATAINVECTOR[HISTORYVECTORCOUNT];
        output = HISTORYDATAINVECTOR[HISTORYVECTORCOUNT];
    }
    else{
        HISTORYVECTORCOUNT = -1;
    }
    return output;
}

string downKeyHistory(string input,string orginalInputWithoutUpAndDown)
{
    string output = "";
    if(HISTORYVECTORCOUNT <= 0)
    {
        HISTORYVECTORCOUNT = -1;
    }
    else
    {
        HISTORYVECTORCOUNT--;
    }
    if(HISTORYDATAINVECTOR.size() > 0 && HISTORYVECTORCOUNT >= 0)
    {
        cout << "\r";
        int len = PROMPTLENGTH + input.length() + 1 + 10;
        for(int i=0;i<len;i++)
        {
            cout << " ";
        }
        cout << "\r";
        display();
        cout << HISTORYDATAINVECTOR[HISTORYVECTORCOUNT];
        output = HISTORYDATAINVECTOR[HISTORYVECTORCOUNT];
    }
    else
    {
        cout << "\r";
        int len = PROMPTLENGTH + input.length() + 10;
        for(int i=0;i<len;i++)
        {
            cout << " ";
        }
        cout << "\r";
        display();
        cout << orginalInputWithoutUpAndDown;
        output = orginalInputWithoutUpAndDown;
    }
    return output;
}
