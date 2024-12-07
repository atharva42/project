#include<iostream>
#include<vector>
#include "header.h"
using namespace std;

void echo(vector<string> command)
{
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
        for(int i =1;i<command.size();i++)
        {
            if(i!=command.size()-1)
            {
                cout << command[i] << " ";
            }
            else{
                cout << command[i] << endl;
            }
        }
    }
    return;
}