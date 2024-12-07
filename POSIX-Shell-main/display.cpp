#include<iostream>
#include "header.h"
#include <unistd.h>         // for getuid()
#include <sys/types.h>      // for getpwuid()
#include <pwd.h>            // for getpwuid()
#include <sys/utsname.h>    // utsname
using namespace std;

// It will print hr prompt
void display()
{

    // cout << "inside display : " << HOME;

    // USER INFO

    // It will give you user id
    uid_t userId = getuid();
    //It will gice you user information
    struct passwd *userInfo = getpwuid(userId);
    
    //All the information provided by passwd
    // struct passwd {
        // char *pw_name;     // User's login name
        // char *pw_passwd;   // Encrypted password (often not used)
        // uid_t pw_uid;      // User ID
        // gid_t pw_gid;      // Group ID
        // char *pw_gecos;    // Real name and other user information
        // char *pw_dir;      // Home directory
        // char *pw_shell;    // Default shell
    // };


    // SYSTEM INFO

    // It will give ypu  system information
    //  The uname system call retrieves system information and stores it in a structure called struct utsname. 
    struct utsname systemInfo;
    string nodeName = "";
    if (uname(&systemInfo) != 0) {
        perror("Error getting system information");
        // return;
    }
    else{
        nodeName = systemInfo.nodename;
    }

    // struct utsname {
    //     char sysname[_UTSNAME_SYSNAME_LENGTH];     // Operating system name (e.g., "Linux")
    //     char nodename[_UTSNAME_NODENAME_LENGTH];   // Network node hostname
    //     char release[_UTSNAME_RELEASE_LENGTH];     // Operating system release version
    //     char version[_UTSNAME_VERSION_LENGTH];     // Operating system version
    //     char machine[_UTSNAME_MACHINE_LENGTH];     // Hardware identifier (e.g., "x86_64")
    //     char domainname[_UTSNAME_DOMAIN_LENGTH];   // NIS or YP domain name
    // };

    string directoryPath = presentWorkingDirectory();

    if(directoryPath == HOME)
    {
        directoryPath = "~";
    }
    else
    {
        if(directoryPath.find(HOME)!=string::npos)
        {
            directoryPath = "~"+directoryPath.substr(HOME.length());
        }
    }

    string prompt = string(userInfo->pw_name) + "@" + systemInfo.nodename + ":" + directoryPath + ">";

    PROMPTLENGTH = prompt.length();

    cout << prompt;


}