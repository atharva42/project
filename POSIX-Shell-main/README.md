# Assignment 2

## Question 1

### Overview (Approach) 
- make file will compile all needed file all togather.
- Header file is the center of every file, It will handle all global variable and functions.
- main.cpp : This file will handle all inputs and also handle command handler. It will tokenize the input with semicolon,space,pipeline and input output redirector.
- display.cpp : It will create the prompt for shell.
- pwd.cpp : This file will give present working directory.
- echo.cpp : This file works same as echo command of terminal. 
- cd.cpp : This file's function work for changing curent directory, it will also handle cases for ~,-,.,.. 
- ls.cpp : To list all the files, also handles -a,-l flag and multiple directory input
- bgfg.cpp : Create background or foreground process according to the input. It also handles commands which are not coded.
- pinfo.cpp : It will give the process info like pid,virtual memory, status, executable path.
- search.cpp : It will search given file/directory recursively inside current directory.
- signal.cpp : This will handle all signals like ctrl+c,ctrl+d,ctrl+z
- history.cpp : Give past history of commands which are executed. Handling this history in saperate file.It will also handle up and down arraow key functionality
- userinput.cpp : This file will take user input character by character and act upon tab,enter,up,down arrow key..
- testingpipe : This file contain logiv of autosuggestion on pressing tab.

### Execution (To run this file)
```c++
1. make
2. ./a.out
```

### Asumptions 
- Everything is space saperated.
- Program will be executed from the path where a.out/program file exists.
***
