// Open fixture for the exact Wine cursor-cache race; no game code/assets.
#include <windows.h>
#include <cstdio>
#include <cstring>
#include "../native/takp_camera_recenter.h"

static void result(const char *value) {
    FILE *file=std::fopen("D:\\reply.tmp","wb");if(!file)ExitProcess(12);
    std::fputs(value,file);std::fclose(file);
    if(!MoveFileExA("D:\\reply.tmp","D:\\reply.txt",MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))ExitProcess(13);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE,LPSTR,int) {
    WNDCLASSA cls={};cls.lpfnWndProc=DefWindowProcA;cls.hInstance=instance;cls.lpszClassName="TrascCursorProbe";
    if(!RegisterClassA(&cls))return 10;
    HWND window=CreateWindowA(cls.lpszClassName,"TAKP cursor cache fixture",WS_POPUP|WS_VISIBLE,
                             0,0,800,600,nullptr,nullptr,instance,nullptr);
    if(!window || !GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"wine_get_version"))return 11;
    SetForegroundWindow(window);SetFocus(window);
    for(int i=0;i<30;i++){MSG message;while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessage(&message);}Sleep(10);}
    SetCursorPos(400,300);result("ready");
    // EQW's input/frame thread can recenter before its window-message thread
    // consumes MotionNotify. Keep that pump paused to reproduce the race.
    DWORD until=GetTickCount()+60000;
    while(GetTickCount()<until) {
        FILE *file=std::fopen("D:\\command.txt","rb");
        if(!file){Sleep(5);continue;}
        char command[128]={};std::fgets(command,sizeof(command),file);std::fclose(file);
        DeleteFileA("D:\\command.txt");
        if(!std::strncmp(command,"quit",4)){result(command);return 0;}
        if(!std::strncmp(command,"legacy",6))SetCursorPos(400,300);
        else if(!std::strncmp(command,"fixed",5))
            trasc_takp_camera::center(400,300,0,800,true,[](int x,int y){return SetCursorPos(x,y);});
        else return 14;
        result(command);
    }
    return 15;
}
