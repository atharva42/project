#include<iostream>
#include <unistd.h>
#include "header.h"
using namespace std;

// extern string HOME;

string presentWorkingDirectory()
{
    // string HOME;
    // Get the current working directory absolute path
    char pwd[1024];
    if (getcwd(pwd, sizeof(pwd)) == nullptr) {
        perror("Error getting current working directory");
        return "";
    }
    // cout << pwd << endl;
    // cout << HOME << endl;
    return pwd;
}