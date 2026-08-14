#include "checker.hpp"
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>
extern "C" void checker_scan(const uint16_t*,int,int,int,uint16_t,int,int,int,int*,int*,int*);
static std::vector<std::string> sp(const std::string&s){std::vector<std::string>v;std::stringstream z(s);std::string x;while(std::getline(z,x,','))v.push_back(x);return v;}
int main(int ac,char**av){if(ac!=3)return 2;std::ifstream mf(av[1]);std::ofstream o(av[2]);if(!mf||!o)return 2;std::string l;std::getline(mf,l);auto h=sp(l);int ip=-1,iw=-1,ih=-1,is=-1,ic=-1;for(int i=0;i<(int)h.size();++i){if(h[i]=="raw_path")ip=i;if(h[i]=="width")iw=i;if(h[i]=="height")ih=i;if(h[i]=="stem")is=i;if(h[i]=="source")ic=i;}o<<"source,stem,width,height,dark_count,hyst_flags,selected_mode\n";int cnt=0;while(std::getline(mf,l)){auto c=sp(l);int w=std::stoi(c[iw]),hh=std::stoi(c[ih]);std::vector<uint16_t>a((size_t)w*hh);std::ifstream f(c[ip],std::ios::binary);f.read((char*)a.data(),a.size()*2);if(f.gcount()!=(std::streamsize)a.size()*2){std::cerr<<"bad raw "<<c[ip]<<"\n";return 3;}int m=-1,fl=-1,d=-1;checker_scan(a.data(),w,hh,DFXISP_MODE_AUTO,4096,62,64,60,&m,&fl,&d);o<<c[ic]<<','<<c[is]<<','<<w<<','<<hh<<','<<d<<','<<fl<<','<<m<<'\n';++cnt;}std::cout<<"HLS_TB_COMPLETE frames="<<cnt<<" output="<<av[2]<<"\n";return cnt?0:4;}
