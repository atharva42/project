#include<iostream>
#include<termios.h>
#include<unistd.h>
#include<string.h>
#include<string>
#include "header.h"
using namespace std;

string userInput()
{
    int tabInsertCount = 0;
    string previousTabString = "";
    string output = "";
    string orginalInputWithoutUpAndDown = output;

    char input;
    char arrowKeys[3];

    struct termios oldt, newt;
    tcgetattr(STDIN_FILENO, &oldt);
    newt = oldt;
    newt.c_lflag &= ~(ICANON | ECHO);
    tcsetattr(STDIN_FILENO, TCSANOW, &newt);

     while (true) {
        input = getchar();

        if (input == '\t') {
            if(strcmp(output.c_str(),previousTabString.c_str()) != 0)
            {
                tabInsertCount = 0;
            } 
            output = tabAutoComplete(output,tabInsertCount); 
            previousTabString = output;
            tabInsertCount++;
            orginalInputWithoutUpAndDown = output;
        }
        else if((int)input == 4)
        {
            if(output.length()==0)
            {
                cout << endl;
                tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
                signalQuitHandler();
            }
        }
        else if (input == 27) 
        {
            arrowKeys[0] = getchar();
            arrowKeys[1] = getchar();
            arrowKeys[2] = '\0';

            // Check for Up and Down arrow keys
            if (strcmp(arrowKeys, "[A") == 0) {
                output = upKeyHistory(output);
            }
            else if (strcmp(arrowKeys, "[B") == 0) {
                output = downKeyHistory(output,orginalInputWithoutUpAndDown);
            }
            continue;
        }
        else if (input == '\b' || input == '\x7F') {
            if (output.length()>0) {
                output = output.substr(0,output.length()-1);
                cout << "\r";
                int len = PROMPTLENGTH + output.length() + 1 + 30;
                for(int i=0;i<len;i++)
                {
                    cout << " ";
                }
                cout << "\r";
                display();
                cout << output;
                orginalInputWithoutUpAndDown = output;
            }
        }
        else if (input == '\n') {
            cout << endl;
            break;
        }
        else {
            output = output + input;
            orginalInputWithoutUpAndDown = output;
            cout << input;
        }
    }
    tcsetattr(STDIN_FILENO, TCSANOW, &oldt);
    return output;
}