#include <iostream>
#include <opencv2/opencv.hpp>
using namespace std;
using namespace cv;

double energyCalculation(const Mat& inputImage, int x, int y) {
    Vec3b pixelLeft,pixelRight,pixelUp,pixelDown;
    if(x==0)
        pixelLeft=inputImage.at<Vec3b>(y,inputImage.cols-1);
    else
        pixelLeft=inputImage.at<Vec3b>(y,x-1);
    if(x==inputImage.cols - 1)
        pixelRight=inputImage.at<Vec3b>(y,0);
    else    
        pixelRight=inputImage.at<Vec3b>(y,x+1);
    long long deltaX=(pixelRight[2]-pixelLeft[2])+(pixelRight[1]-pixelLeft[1])+(pixelRight[0]-pixelLeft[0]);
    deltaX=pow(deltaX,2);
    if(y==0)
        pixelUp = inputImage.at<Vec3b>(inputImage.rows-1,x);
    else    
        pixelUp = inputImage.at<Vec3b>(y-1,x);
    if(y==inputImage.rows-1)
        pixelDown = inputImage.at<Vec3b>(0,x);
    else
        pixelDown = inputImage.at<Vec3b>(y+1,x);
    long long deltaY=(pixelDown[2]-pixelUp[2])+(pixelDown[1]-pixelUp[1])+(pixelDown[0]-pixelUp[0]);
    deltaY=pow(deltaY,2);
    double energy=sqrt(deltaX+deltaY);
    return energy;
}

int* findVericalLowestEnergySeam(const Mat& inputImage){
    Mat energyMatrix(inputImage.size(), CV_64F);

    for (int y=0;y<inputImage.rows;y++){
        for (int x=0;x<inputImage.cols;x++){
            energyMatrix.at<double>(y,x)=energyCalculation(inputImage,x,y);
        }
    }

    for (int y=1;y<inputImage.rows;y++){
        for (int x=0;x<inputImage.cols;x++){
            double minimumEnergy = energyMatrix.at<double>(y - 1, x);
            if (x > 0 && energyMatrix.at<double >(y - 1, x - 1) < minimumEnergy)
                minimumEnergy = energyMatrix.at<double>(y - 1, x - 1);
            if (x < inputImage.cols - 1 && energyMatrix.at<double>(y - 1, x + 1) < minimumEnergy)
                minimumEnergy = energyMatrix.at<double>(y - 1, x + 1);
            energyMatrix.at<double>(y, x) += minimumEnergy;
        }
    }

    double minimumEnergy = energyMatrix.at<double>(inputImage.rows - 1, 0);
    int lowestIndex = 0;
    for (int x = 1; x < inputImage.cols; x++) {
        if (energyMatrix.at<double>(inputImage.rows - 1, x) < minimumEnergy) {
            minimumEnergy = energyMatrix.at<double>(inputImage.rows - 1, x);
            lowestIndex = x;
        }
    }

    int* seam = new int[inputImage.rows];
    seam[inputImage.rows - 1] = lowestIndex;
    for (int y = inputImage.rows - 2; y >= 0; y--) {
        int prevX = seam[y + 1];
        double minimumEnergy = energyMatrix.at<double>(y, prevX);

        if (prevX > 0 && energyMatrix.at<double>(y, prevX - 1) < minimumEnergy) 
            seam[y] = prevX - 1;
        else if (prevX < inputImage.cols - 1 && energyMatrix.at<double>(y, prevX + 1) < minimumEnergy) 
            seam[y] = prevX + 1;
        else 
            seam[y] = prevX;
    }

    return seam;
}

int* findHorizontalLowestEnergySeam(const Mat& inputImage){
    Mat energyMatrix(inputImage.size(), CV_64F);

    for (int y=0;y<inputImage.rows;y++){
        for (int x=0;x<inputImage.cols;x++){
            energyMatrix.at<double>(y,x)=energyCalculation(inputImage,x,y);
        }
    }

    for (int x=1;x<inputImage.cols;x++){
        for (int y=0;y<inputImage.rows;y++){
            double minimumEnergy = energyMatrix.at<double>(y,x - 1);
            if (y > 0 && energyMatrix.at<double>(y - 1, x - 1) < minimumEnergy)
                minimumEnergy = energyMatrix.at<double>(y - 1, x - 1);
            if (y < inputImage.rows - 1 && energyMatrix.at<double>(y + 1, x - 1) < minimumEnergy)
                minimumEnergy = energyMatrix.at<double>(y + 1, x - 1);
            energyMatrix.at<double>(y, x) += minimumEnergy;
        }
    }

    double minimumEnergy = energyMatrix.at<double>(0,inputImage.cols - 1);
    int lowestIndex = 0;
    for (int y = 1; y < inputImage.rows; y++) {
        if (energyMatrix.at<double>(y,inputImage.cols - 1) < minimumEnergy) {
            minimumEnergy = energyMatrix.at<double>(y,inputImage.cols - 1);
            lowestIndex = y;
        }
    }
    
    int* seam = new int[inputImage.cols];
    seam[inputImage.cols - 1] = lowestIndex;
    for (int x = inputImage.cols - 2; x >= 0; x--) {
        int prevY = seam[x + 1];
        double minimumEnergy = energyMatrix.at<double>(prevY,x);

        if (prevY > 0 && energyMatrix.at<double>(prevY - 1,x) < minimumEnergy) 
            seam[x] = prevY - 1;
        else if (prevY < inputImage.rows - 1 && energyMatrix.at<double>( prevY + 1,x) < minimumEnergy) 
            seam[x] = prevY + 1;
        else 
            seam[x] = prevY;
    }

    return seam;
}

void removeVerticalSeam(Mat& inputImage, int* seam) {
    for (int y = 0; y < inputImage.rows; y++) {
        for (int x = seam[y]; x < inputImage.cols - 1; x++) {
            inputImage.at<Vec3b>(y, x) = inputImage.at<Vec3b>(y, x + 1);
        }
    }
    inputImage = inputImage.colRange(0, inputImage.cols - 1);
}

void removeHorizontalSeam(Mat& inputImage, int* seam) {
    for (int x = 0; x < inputImage.cols; x++) {
        for (int y = seam[x]; y < inputImage.rows - 1; y++) {
            inputImage.at<Vec3b>(y, x) = inputImage.at<Vec3b>(y+1, x);
        }
    }
     inputImage = inputImage.rowRange(0, inputImage.rows - 1);
}

int main(int argc, char* argv[]) {
    if(argc==1){
        cout<<"Please provide Image File Path\n";
        exit(1);
    }
    if(argc>2){
        cout<<"Please provide proper Input\n";
        exit(1);
    }
    string inputPath=argv[1];
    Mat inputImage=imread(inputPath);

    if (inputImage.empty()) {
        cout << "Error: Could not open or find the input image." << endl;
        return 1;
    }

    int widthReduce,heightReduce;
    cout<<"Enter the Width to be Reduced : ";
    cin>>widthReduce;
    cout<<"Enter the Height to be Reduced : ";
    cin>>heightReduce;

    if(widthReduce>=inputImage.cols || widthReduce<0){
        cout << "Error: Please Enter Width to be Reduced correctly." << endl;
        return 1;
    }

    if(heightReduce>=inputImage.rows || heightReduce<0){
        cout << "Error: Please Enter Height to be Reduced correctly." << endl;
        return 1;
    }

    // Specify the new width and height for the resized image
    int newWidth = inputImage.cols - widthReduce; 
    int newHeight = inputImage.rows - heightReduce;

    while(inputImage.cols > newWidth || inputImage.rows > newHeight){
        if (inputImage.cols > newWidth) {
            int *verticalSeam = findVericalLowestEnergySeam(inputImage);
            removeVerticalSeam(inputImage, verticalSeam);
        }
        if (inputImage.rows > newHeight) {
            int *horizontalSeam = findHorizontalLowestEnergySeam(inputImage);
            removeHorizontalSeam(inputImage, horizontalSeam);
        }
    }
    imwrite("output.jpg", inputImage);
    return 0;
}
