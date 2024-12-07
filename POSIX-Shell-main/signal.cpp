#include <iostream>
#include <cstdlib>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
#include "header.h"

using namespace std;

void signalInputHandler(int signum) {
    if(CURRENTFOREGROUND != MAINPROCESSPID)
    {
        kill(CURRENTFOREGROUND,SIGINT);
        CURRENTFOREGROUND = MAINPROCESSPID;
    }
    else{
        cout << endl;
    }
}

void signalQuitHandler() {
    exit(0);
}

void signalBGHandler(int signum) {
    if(CURRENTFOREGROUND != MAINPROCESSPID)
    {
        kill(CURRENTFOREGROUND,SIGINT);
        CURRENTFOREGROUND = MAINPROCESSPID;
    }
    else{
        cout << endl;
    }
}
