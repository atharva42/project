#include <iostream>
#include <string.h>
using namespace std;

template <typename T>
class Deque{
private:
    T* deque;
    int Front; 
    int Rear;  
    int totalCapacity;

public:
    Deque(){
        deque = new T[0];
        Front=-1;
        Rear=-1;
        totalCapacity=0;
    }
    
    Deque(int n){
        totalCapacity=n;
        deque = new T[totalCapacity];
        for(int i=0;i<n;++i) 
            deque[i] = T();
        Front=0;
        Rear=n-1;
    }
    
    Deque(int n, T x){
        totalCapacity=n;
        deque = new T[totalCapacity];
        for(int i=0;i<n;++i)
            deque[i]=x;
        Front=0;
        Rear=n-1;
    }
    
    bool push_back(T x) {
        if (Front==-1 || size()==totalCapacity) {
            int newCapacity=(totalCapacity==0)?1:totalCapacity*2;
            try{
                int temp=size()-1;
                resize(newCapacity);
                Rear=temp;
            }
            catch(bad_alloc& ex){
                cout<<newCapacity<<" bytes: Out of memory!";
                return false;
            }
        }
        if(Rear==-1)
            Front=0;
        Rear=(Rear+1)%totalCapacity;
        deque[Rear] = x;
        return true;
    }
    
    bool pop_back() {
        if (Front!=-1) {
            Rear=(Rear-1+totalCapacity)%totalCapacity;
            if(Front==(Rear+1)%totalCapacity){
                Front=-1;
                Rear=-1;
            }
            return true;
        }
        return false;
    }
    
    bool push_front(T x) {
        if(Front==-1)
            return push_back(x);
        if (size()==totalCapacity) {
            int newCapacity=(totalCapacity==0)?1:totalCapacity*2;
            try{
                int temp=size()-1;
                resize(newCapacity);
                Rear=temp;
            }
            catch(bad_alloc& ex){
                cout<<newCapacity<<" bytes: Out of memory!";
                return false;
            }
        }
        Front=(Front-1+totalCapacity)%totalCapacity;
        deque[Front]=x;
        return true;
    }
    
    bool pop_front() {
        if (Front!=-1) {
            Front=(Front+1)%totalCapacity;
            if(Front==(Rear+1)%totalCapacity){
                Front=-1;
                Rear=-1;
            }
            return true;
        }
        return false;
    }
    
    T front() {
        if (Front!=-1) {
            return deque[Front];
        }
        return T();
    }
    
    T back() {
        if (Rear!=-1) {
            return deque[Rear];
        }
        return T();
    }
    
    T operator[](int n) {
        if(n<0)
            n=n+size();
        if(n>=0 && n<size())
            return deque[(n+Front)%totalCapacity];
        return T();
    }
    
    bool empty() {
        return Front==-1;
    }
    
    int size() {
        return Front>Rear?(totalCapacity-Front+Rear+1):(Rear-Front+1);
    }
    
    void resize(int n) {
        T* newDeque = new T[n];
        if(Front==-1){
            deque = newDeque;
            for(int i=0;i<n;i++)
                deque[i]=T();
            totalCapacity = n;
            Front=0;
            Rear=n-1;
            return;
        }
        int j=0,i=Front;
        do{
            newDeque[j] = deque[i];
            if(i==size()-1)
                i=-1;
            i++;
            j++;
        }while(i!=(Rear+1)%totalCapacity && j<n);
        delete[] deque;
        deque = newDeque;
        for(int i=size();i<n;i++)
            deque[i]=T();
        totalCapacity = n;
        Rear=n-1;
        Front=0;
    }
    
    void resize(int n, T value) {
        T* newDeque = new T[n];
        if(Front==-1){
            totalCapacity = n;
            for (int i = 0; i < n; ++i) 
                newDeque[i] = value;
            deque = newDeque;
            Front=0;
            Rear=n-1;
            return;
        }
        int j=0,i=Front;
        do{
            newDeque[j] = deque[i];
            if(i==size()-1)
                i=-1;
            i++;
            j++;
        }while(i!=(Rear+1)%totalCapacity && j<n);
        for (i = size(); i < n; ++i) {
            newDeque[i] = value;
        }
        delete[] deque;
        deque=newDeque;
        totalCapacity = n;
        Rear=n-1;
        Front=0;
    }
    
    void reserve(int n) {
        if (n > totalCapacity) {
            T* newDeque = new T[n];
            if(Front==-1){
                deque = newDeque;
                for(int i=0;i<n;i++)
                    deque[i]=T();
                totalCapacity = n;
                Front=0;
                Rear=n-1;
                return;
            }
            int j=0,i=Front;
            do{
                newDeque[j] = deque[i];
                if(i==size()-1)
                    i=-1;
                i++;
                j++;
            }while(i!=(Rear+1)%totalCapacity && j<n);
            delete[] deque;
            deque = newDeque;
            totalCapacity = n;
            Rear=n-1;
            Front=0;
        }
    }
    
    void shrink_to_fit() {
        resize(size());
    }
    
    void clear() {
        Front=-1;
        Rear=-1;
    }
    
    int capacity() {
        return totalCapacity;
    }

};

int main(){
    int choice,n;
    int x;
    Deque<int> deque;
    // string x;
    // Deque<string> deque;

    while (true) {
        cin>>choice;
        if(choice==0) 
            break;
        switch(choice){
            case 1:
                // deque=Deque<string>();
                deque=Deque<int>();
                break;

            case 2: 
                cin>>n;
                // deque=Deque<string>(n);
                deque=Deque<int>(n);
                break;

            case 3: 
                cin>>n>>x;
                // deque=Deque<string>(n,x);
                deque=Deque<int>(n,x);
                break;

            case 4: 
                cin>>x;
                cout<<boolalpha<<deque.push_back(x)<<endl;
                break;

            case 5: 
                cout<<boolalpha<<deque.pop_back()<<endl;
                break;

            case 6: 
                cin>>x;
                cout<<boolalpha<<deque.push_front(x)<<endl;
                break;

            case 7: 
                cout<<boolalpha<<deque.pop_front()<<endl;
                break;

            case 8: 
                x=deque.front();
                cout<<x<<endl;
                break;

            case 9: 
                x=deque.back();
                cout<<x<<endl;
                break;

            case 10: 
                cin>>n;
                x=deque[n];
                cout<<x<<endl;
                break;

            case 11: 
                cout<<boolalpha<<deque.empty()<<endl;
                break;

            case 12: 
                cout<<deque.size()<<endl;
                break;

            case 13: 
                cin>>n;
                deque.resize(n);
                break;

            case 14: 
                cin>>n>>x;
                deque.resize(n, x);
                break;

            case 15: 
                cin>>n;
                deque.reserve(n);
                break;

            case 16: 
                deque.shrink_to_fit();
                break;

            case 17: 
                deque.clear();
                break;

            case 18: 
                cout<<deque.capacity()<<endl;
                break;
        }
    }
    return 0;
}