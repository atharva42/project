#include <iostream>
#include <string.h>
#define ll long long 
using namespace std;

int compare(string s1,string s2){
    int n=s1.length(),m=s2.length();
    if(n>m)
        return 1;
    else if(n<m)
        return -1;
    else{
        if(s1==s2)
            return 0;
        for(int i=0;i<n;i++){
            if(s1[i]>s2[i])
                return 1;
            else if(s1[i]<s2[i])
                return -1;
        }
    }
    return 0;
}

string addition(string s1,string s2){
    string s="";
    int carry=0,i,j;
    for(i=s1.length()-1,j=s2.length()-1;i>=0 && j>=0;i--,j--){
        int x=(s1[i]-'0')+(s2[j]-'0')+carry;
        s=to_string(x%10)+s;
        carry=x/10;
    }
    while(i>=0){
        int x=(s1[i]-'0')+carry;
        s=to_string(x%10)+s;
        carry=x/10;
        i--;
    }
    while(j>=0){
        int x=(s2[j]-'0')+carry;
        s=to_string(x%10)+s;
        carry=x/10;
        j--;
    }
    if(carry>0){
        s=to_string(carry)+s;
    }
    return s;
}

string subtraction(string s1,string s2){
    string s="";
    int borrow=0,i,j;
    for(i=s1.length()-1,j=s2.length()-1;i>=0 && j>=0;i--,j--){
        int x=(s1[i]-'0')-(s2[j]-'0')-borrow;
        if(x<0){
            x=x+10;
            borrow=1;
        }
        else
            borrow=0;
        s=to_string(x%10)+s;
    }
    while(i>=0){
        int x=(s1[i]-'0')-borrow;
        if(x<0){
            x=x+10;
            borrow=1;
        }
        else
            borrow=0;
        s=to_string(x%10)+s;
        i--;
    }
    while(j>=0){
        int x=(s2[j]-'0')-borrow;
        if(x<0){
            x=x+10;
            borrow=1;
        }
        else
            borrow=0;
        s=to_string(x%10)+s;
        j--;
    }
    for(int i=0;i<s.length();i++){
        if(s[i]!='0')
            return s.substr(i);
        if(i==s.length()-1)
            return "0";
    }
    return s;
}

string multiplication(string s1,string s2){
    if(compare(s1,"0")==0 || compare(s2,"0")==0)
        return "0";
    string s(s1.length()+s2.length(),'0');
    for(int j=s2.length()-1;j>=0;j--){
        for(int i=s1.length()-1;i>=0;i--){
            int r=(s1[i]-'0')*(s2[j]-'0')+(s[i + j + 1]-'0');
            s[i+j+1] =(r%10)+'0';
            s[i+j]+=r/10;
        }
    }
    for(int i = 0; i < s1.length() + s2.length(); i++)
        if(s[i] !='0')
            return s.substr(i);
    return s;
}

// Division Using Binary Search

// string division(string s1,string s2){
//     if(compare(s1,"0")==0)
//         return "0";
//     string low="1",high=s1;
//     int cmp=compare(low,high);
//     string mid;
//     while(cmp==-1 || cmp==0){
//         string newMid=multiplication(addition(low,high),"5");
//         mid=newMid.substr(0,newMid.length()-1);
//         string ans=multiplication(mid,s2);
//         int cmp1=compare(ans,s1);
//         if(cmp1==0)
//             return mid;
//         else if(cmp1==-1)
//             low=addition(mid,"1");
//         else    
//             high=subtraction(mid,"1");
//         cmp=compare(low,high);
//     }
//     cmp=compare(multiplication(mid,s2),s1);
//     while(cmp==1){
//         mid=subtraction(mid,"1");
//         cmp=compare(multiplication(s2,mid),s1);
//     }
//     return mid;
// }

string division(string s1,string s2){
    if(compare(s1,"0")==0 || compare(s1,s2)==-1)
        return "0";
    string str="";
    int i=0;
    while(i<s1.length() && compare(str,s2)==-1){
        str+=s1[i];
        i++;
    }
    string s="";
    int k=0;
    if(i==s1.length()){
        while(compare(s2,str)==-1 || compare(s2,str)==0){
            str=subtraction(str,s2);
            k++;
        }
        s+=to_string(k);
    }
    for(int j=i;j<s1.length();){
        while(compare(s2,str)==-1 || compare(s2,str)==0){
            str=subtraction(str,s2);
            k++;
        }
        s+=to_string(k);
        k=0;
        if(str=="0")
            str="";
        if(j<s1.length()){
            str+=s1[j];
            j++;
        }
        while(j<s1.length() && compare(str,s2)==-1){
            str+=s1[j];
            j++;
            s+="0";
        }
    }
    if(compare(str,s2)==1){
        while(compare(s2,str)==-1 || compare(s2,str)==0){
            str=subtraction(str,s2);
            k++;
        }
        s+=to_string(k);
    }
    return s;
}

string modulo(string s1,string s2){
    if(compare(s1,s2)==-1)
        return modulo(s2,s1);
    if(compare(s1,"0")==0 || compare(s1,s2)==-1)
        return "0";
    string str="";
    int i=0;
    while(i<s1.length() && compare(str,s2)==-1){
        str+=s1[i];
        i++;
    }
    string s="";
    int k=0;
    if(i==s1.length()){
        while(compare(s2,str)==-1 || compare(s2,str)==0){
            str=subtraction(str,s2);
            k++;
        }
        s+=to_string(k);
    }
    for(int j=i;j<s1.length();){
        while(compare(s2,str)==-1 || compare(s2,str)==0){
            str=subtraction(str,s2);
            k++;
        }
        s+=to_string(k);
        k=0;
        if(str=="0")
            str="";
        if(j<s1.length()){
            str+=s1[j];
            j++;
        }
        while(j<s1.length() && compare(str,s2)==-1){
            str+=s1[j];
            j++;
            s+="0";
        }
    }
    if(compare(str,s2)==1){
        while(compare(s2,str)==-1 || compare(s2,str)==0){
            str=subtraction(str,s2);
            k++;
        }
        s+=to_string(k);
    }
    return str;
}

string gcd(string s1,string s2){
    if(compare(s1,s2)==-1)
        return gcd(s2,s1);
    if(compare(modulo(s1,s2),"0")==0)
        return s2;
    return gcd(s2,modulo(s1,s2));
}

string exponentiation(string base,string power){
    if(compare(base,"0")==0)
        return "0";
    else if(compare(base,"1")==0 || compare(power,"0")==0)
        return "1";
    else if(compare(power,"1")==0)
        return base;
    int len=power.length();
    string str=exponentiation(base,division(power,"2"));
    if(power[len-1]=='0' || power[len-1]=='2' || power[len-1]=='4' || power[len-1]=='6' || power[len-1]=='8')
        return multiplication(str,str);
    else
        return multiplication(base,multiplication(str,str));

    // long long p=stoll(power)-1;
    // string ans=base;
    // while(p--){
    //     ans=multiplication(ans,base);
    // }
    // return ans;
}

string factorial(string s){
    string ans="1";
    ll x=stoll(s);
    for(int i=2;i<=x;i++)
        ans=multiplication(ans,to_string(i));
    return ans;
}

string infixToPostfix(string s){
    string ans="";
    char st[3000];
    int top=-1;
    for(int i=0;i<s.length();i++){
        if(s[i]=='+'){
            while(top!=-1 && (st[top]=='+' || st[top]=='-' || st[top]=='x' || st[top]=='/')){
                ans+=st[top--];
                ans+=" ";
            }
            st[++top]=s[i];
        }
        else if(s[i]=='-'){
            while(top!=-1 && (st[top]=='-' || st[top]=='x' || st[top]=='/')){
                ans+=st[top--];
                ans+=" ";
            }
            st[++top]=s[i];
        }
        else if(s[i]=='x'){
            while(top!=-1 && (st[top]=='x' || st[top]=='/')){
                ans+=st[top--];
                ans+=" ";
            }
            st[++top]=s[i];
        }
        else if(s[i]=='/'){
            while(top!=-1 && st[top]=='/'){
                ans+=st[top--];
                ans+=" ";
            }
            st[++top]=s[i];
        }
        else{
            while(i<s.length() && s[i]>='0' && s[i]<='9'){
                ans+=s[i];
                i++;
            }
            i--;
        }
        ans+=" ";
    }
    while(top!=-1){
        ans+=st[top--];
        ans+=" ";
    }
    return ans;
}

string evaluate(string s){
    string st[3000];
    int top=-1;
    string post=infixToPostfix(s);
    for(int i=0;i<post.length();i++){
        if(post[i]=='+' || post[i]=='-' || post[i]=='x' || post[i]=='/'){
            string b=st[top--];
            string a=st[top--];
            if(post[i]=='+')
                st[++top]=addition(a,b);
            else if(post[i]=='-')
                st[++top]=subtraction(a,b);
            else if(post[i]=='x')
                st[++top]=multiplication(a,b);
            else
                st[++top]=division(a,b);
            i++;
        }
        else{
            string str="";
            while(i<post.length() && post[i]!=' '){
                str+=post[i];
                i++;
            }
            if(str!="")
                st[++top]=str;
        }
    }
    return st[0];
}

int main(){
    int choice;
    cin>>choice;
    string s,p,x,s1,s2;
    switch(choice){
        case 1:
            cin>>s;
            cout<<evaluate(s)<<endl;
            break;
        case 2:
            cin>>x>>p;
            cout<<exponentiation(x,p)<<endl;
            break;
        case 3:
            cin>>s1>>s2;
            cout<<gcd(s1,s2)<<endl;
            break;
        case 4:
            cin>>s;
            cout<<factorial(s)<<endl;
            break;
        default : cout<<"Invalid Option\n";
            break;
    }
    return 0;
}
