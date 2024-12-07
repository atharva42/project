#include<iostream>
#include<vector>
#include<unistd.h>  // open,close,read
#include<fcntl.h> // used for argument of open system call
#include <sys/stat.h> //mkdir,stat ,chmod
#include <iostream>
#include <fstream>
#include <string>
#include<vector>
#include <dirent.h>         // opendir, readdir, and closedir
#include <sys/types.h>      // size_t and time_t
#include<string.h>
#include "header.h"
using namespace std;

string tabAutoComplete(string wholeInput,int tabInsertCount)
{
    string input = wholeInput;
    string atReturnTimeOutputString = "";

    vector<string> commmandList = { "cat" , "code", "cd", "ls", "pwd","mkdir","rmdir","pinfo","cp","mv","whoami","man","find","locate","exit","echo","search","history","grep","touch","sudo","rm","clear","tail","head","top","sort","more","less","sed","awk","chmod","chown","htop","ps","kill","jobs","bg","fg","uname","df","free","ssh","scp","du","lscpu","ping","ip","ss","ifconfig","netstat","nano","vim","vi","zip","unzip","tar","gzip","gunzip","apt" };
    // vector<string> spaceSaperatedInput;
    // if(wholeInput[wholeInput.length()-1] == ' ')
    // {
    //     input = "";
    // }
    // else{
    //     if(spaceSaperatedInput.size() > 0)
    //     {

    //     }
    //     else{
    //         input = "";
    //     }
    // }
    // cout << wholeInput << endl;
    vector<string> spaceSaperatedInput;
    string temp = "";
    for(int i=0;i<wholeInput.length();i++)
    {
        if(wholeInput[i] == ' ')
        {
            spaceSaperatedInput.push_back(temp);
            atReturnTimeOutputString = atReturnTimeOutputString + temp + " ";
            temp = "";
        }
        else{
            temp = temp + wholeInput[i];
        }
    }
    if(temp.length()>0)
    {
        spaceSaperatedInput.push_back(temp);
        temp = "";
    }
    // for(auto z : spaceSaperatedInput)
    // {
    //     cout << z << endl;
    // }
    if(wholeInput.length() ==0 || wholeInput[wholeInput.length()-1] == ' ')
    {
        input = "";
    }
    else{
        input = spaceSaperatedInput[spaceSaperatedInput.size()-1];
    }

    // cout << input << endl;

    // cout << "end here";

    
    string output = "";
    vector<string> searchList;
    vector<string> fileList;
    if(input.length()<=0)
    {
        return atReturnTimeOutputString+output;
    }

    // Get all files of current directory
    string currentPath = presentWorkingDirectory();
    char* dirName = new char[currentPath.size() + 1];
    strcpy(dirName, currentPath.c_str());

    DIR *directory = opendir(dirName);

    if (directory) {
        struct dirent *tupple;
        while ((tupple = readdir(directory))) {
                fileList.push_back(tupple->d_name);
        }    
    }

    closedir(directory);

    // cout << spaceSaperatedInput.size() << endl;
    // cout << endl;
    // cout << atReturnTimeOutputString << endl;
    // cout << (atReturnTimeOutputString.length()>2 && (atReturnTimeOutputString[atReturnTimeOutputString.length()-2] == '|' || atReturnTimeOutputString[atReturnTimeOutputString.length()-2] == ';')) << endl;
 

    if(spaceSaperatedInput.size() == 1 || (atReturnTimeOutputString.length()>2 && (atReturnTimeOutputString[atReturnTimeOutputString.length()-2] == '|' || atReturnTimeOutputString[atReturnTimeOutputString.length()-2] == ';')))
    {
        searchList = commmandList;
    }
    else{
        searchList = fileList;
    }

    string suggestionString = "";
    vector<string> suggestions;
    for(int i=0;i<searchList.size();i++)
    {
        if((searchList[i].find(input)) == 0)
        {
            // cout<<endl << "startsugges" <<  suggestionString << endl;
            suggestions.push_back(searchList[i]);
            if(suggestionString == "")
            {
                suggestionString = searchList[i];
            }
            else
            {
                int minLength = min(suggestionString.length(),searchList[i].length());
                string tempSuggestionString = "";
                // cout << " found fule " << searchList[i] << endl; 
                for(int j =0;j<minLength;j++)
                {
                    // cout << suggestionString[j] << " " << searchList[i][j] << endl;
                    if(suggestionString[j] == searchList[i][j])
                    {
                        tempSuggestionString = tempSuggestionString + suggestionString[j];
                    }
                    else
                    {
                        break;
                    }
                    
                }
                suggestionString = tempSuggestionString;
            }
            //  cout<<endl << "endsugges" <<  suggestionString << endl;
        }
    }

    if(suggestions.size() == 0)
    {
        return wholeInput;
    }
    else if(suggestions.size() == 1)
    {
        cout << "\r";
        int len = PROMPTLENGTH + input.length() + 30;
        for(int i=0;i<len;i++)
        {
            cout << " ";
        }
        cout << "\r";
        display();
        // cout << suggestionString;
        cout << (atReturnTimeOutputString+suggestionString);
        // return suggestionString;
        return atReturnTimeOutputString+suggestionString;
    }
    else
    {
        if(tabInsertCount >= 1 && suggestions.size()>1)
        {
            cout << endl;
            for(int i = 0;i<suggestions.size();i++)
            {
                cout << suggestions[i] << " ";
            }
            cout << endl;
            display();
            // cout << suggestionString;
            cout << (atReturnTimeOutputString+suggestionString);
            // return suggestionString;
            return atReturnTimeOutputString+suggestionString;
        }
        else{
            cout << "\r";
            int len = PROMPTLENGTH + input.length() + 30;
            for(int i=0;i<len;i++)
            {
                cout << " ";
            }
            cout << "\r";
            display();
            // cout << suggestionString;
            cout << (atReturnTimeOutputString+suggestionString);
            // return suggestionString;
            return atReturnTimeOutputString+suggestionString;
        }
    }
    
    // return suggestionString;
    return atReturnTimeOutputString+suggestionString;
}
