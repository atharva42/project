#ifndef HEADER_H
#define HEADER_H
#include<string>
#include<vector>
using namespace std;

extern string HOME;
extern string OLDPWD;
extern int CURRENTFOREGROUND;
extern int MAINPROCESSPID;
extern string HISTORYFILENAME;
extern int PROMPTLENGTH;
extern vector<string> HISTORYDATAINVECTOR;
extern int HISTORYVECTORCOUNT; 

void display();
string userInput();
string presentWorkingDirectory();
void echo(vector<string> command);
void cd(vector<string> command);
void ls(vector<string> command);
bool bgfg(vector<string> command);
void pinfo(vector<string> command);
void search(vector<string> command);
void signalInputHandler(int);
void signalQuitHandler();
void signalBGHandler(int);
void createHistoryFile();
void showHistory(vector<string> command);
void writeHistory(string);
void getHistoryFileDataIntoVector();
string upKeyHistory(string);
string downKeyHistory(string,string);
string tabAutoComplete(string,int);

#endif