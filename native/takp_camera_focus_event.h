// Bounded, session-scoped native-focus notification. Parsing this record never
// changes input or capture; the caller applies it only to an owned held clip.
#pragma once
#include <cstddef>
#include <cstring>
#include <limits>
#ifdef _WIN32
#include <windows.h>
#endif

namespace trasc_takp_focus_event {
using Sequence = unsigned long long;
static constexpr std::size_t max_bytes = 96;
static constexpr std::size_t token_bytes = 32;
static constexpr char prefix[] = "TRASCFOCUS1 ";

inline bool token_valid(const char* token) {
    if (!token) return false;
    for (std::size_t i=0;i<token_bytes;++i) {
        const unsigned char ch=static_cast<unsigned char>(token[i]);
        if (!ch || !((ch>='0'&&ch<='9')||(ch>='a'&&ch<='f'))) return false;
    }
    return token[token_bytes]=='\0';
}

inline bool parse(const char* data,std::size_t bytes,const char* launch_token,Sequence& sequence) {
    constexpr std::size_t prefix_bytes=sizeof(prefix)-1;
    constexpr std::size_t digits_offset=prefix_bytes+token_bytes+1;
    if (!data || bytes<digits_offset+2 || bytes>max_bytes || !token_valid(launch_token) ||
        std::memcmp(data,prefix,prefix_bytes) ||
        std::memcmp(data+prefix_bytes,launch_token,token_bytes) ||
        data[digits_offset-1]!=' ' || data[bytes-1]!='\n' || data[digits_offset]=='0') return false;
    Sequence value=0;
    for (std::size_t i=digits_offset;i<bytes-1;++i) {
        const unsigned char ch=static_cast<unsigned char>(data[i]);
        if (ch<'0'||ch>'9') return false;
        const Sequence digit=ch-'0';
        if (value>((std::numeric_limits<Sequence>::max)()-digit)/10) return false;
        value=value*10+digit;
    }
    if (!value) return false;
    sequence=value;
    return true;
}

class SequenceReader {
    Sequence sequence_=0;
public:
    Sequence sequence() const { return sequence_; }
    // Consume new valid records when the hook runs, including Look-off frames.
    // A paused hook can receive an older same-launch sequence later; the caller
    // may then refresh only its already-owned clip once. No event-age binding.
    bool accept(const char* data,std::size_t bytes,const char* launch_token,Sequence& sequence) {
        Sequence next=0;
        if (!parse(data,bytes,launch_token,next) || next<=sequence_) return false;
        sequence_=next;
        sequence=next;
        return true;
    }
};
#ifdef _WIN32
// Each game input hook owns one reader and serializes access to it. The file
// producer atomically replaces a regular one-link file in the private session.
class Win32Reader {
    SequenceReader reader_;
    char path_[1024]={},token_[token_bytes+1]={};
    bool initialized_=false,enabled_=false,clock_started_=false;
    unsigned long last_poll_=0;
    void initialize() {
        initialized_=true;
        const DWORD path_bytes=GetEnvironmentVariableA("TRASC_TAKP_FOCUS_EVENT",path_,sizeof(path_));
        const DWORD token_length=GetEnvironmentVariableA("TRASC_CLIENT_LAUNCH",token_,sizeof(token_));
        enabled_=path_bytes>0&&path_bytes<sizeof(path_)&&token_length==token_bytes&&token_valid(token_);
    }
public:
    Sequence sequence() const { return reader_.sequence(); }
    bool poll(unsigned long now,Sequence& sequence) {
        if (!initialized_) initialize();
        if (!enabled_ || (clock_started_&&static_cast<unsigned int>(now-last_poll_)<20U)) return false;
        clock_started_=true;last_poll_=now;
        HANDLE file=CreateFileA(path_,GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
            nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,nullptr);
        if (file==INVALID_HANDLE_VALUE) return false;
        BY_HANDLE_FILE_INFORMATION info={};LARGE_INTEGER size={};DWORD read=0;
        char bytes[max_bytes+1];
        const bool valid=GetFileType(file)==FILE_TYPE_DISK&&GetFileInformationByHandle(file,&info)&&
            !(info.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))&&
            info.nNumberOfLinks==1&&GetFileSizeEx(file,&size)&&size.QuadPart>0&&
            size.QuadPart<=static_cast<LONGLONG>(max_bytes)&&
            ReadFile(file,bytes,sizeof(bytes),&read,nullptr)&&static_cast<LONGLONG>(read)==size.QuadPart;
        CloseHandle(file);
        return valid&&reader_.accept(bytes,read,token_,sequence);
    }
};
#endif
}
