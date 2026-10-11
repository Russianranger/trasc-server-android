// Open Wine/Xvnc fixture: cached cursor race plus real polled and buffered
// DirectInput during v1 recenter and v2 raw look. No game code/assets.
#define DIRECTINPUT_VERSION 0x0800
#include <windows.h>
#include <dinput.h>
#include <cstdio>
#include <cstring>
#include "../native/takp_camera_recenter.h"
#define TRASC_TAKP_TRACE_IMPLEMENTATION
#include "../native/takp_camera_trace.h"
#include "../native/takp_dinput_observation.h"

static IDirectInputDevice8A* mouse;
static HWND game_window;
static volatile LONG mode=0; // free=0, v1 warp=1, v2 clip=2, exit=-1
static volatile LONG swap_buttons=0;
static volatile LONG polling=1,manual_ack=0;
static LONG totals[4],buttons;
static CRITICAL_SECTION clip_lock;
static trasc_takp_camera::LookClip clip;
static bool get_clip(trasc_takp_camera::Rect& value) {
    RECT rect;if(!GetClipCursor(&rect))return false;
    value={rect.left,rect.top,rect.right,rect.bottom};return true;
}
static bool set_clip(const trasc_takp_camera::Rect& value) {
    RECT rect={value.left,value.top,value.right,value.bottom};return ClipCursor(&rect)!=0;
}
static void release_clip(){EnterCriticalSection(&clip_lock);clip.release(get_clip,set_clip);LeaveCriticalSection(&clip_lock);}
static unsigned long clip_generation(){EnterCriticalSection(&clip_lock);auto generation=clip.generation();LeaveCriticalSection(&clip_lock);return generation;}
static void hold_clip(unsigned long generation){EnterCriticalSection(&clip_lock);
    if(GetForegroundWindow()==game_window&&!IsIconic(game_window)&&IsWindowVisible(game_window))
        clip.hold_since(generation,400,300,{0,0,800,600},get_clip,set_clip);
    else clip.release(get_clip,set_clip);
    LeaveCriticalSection(&clip_lock);}
static LRESULT CALLBACK window_proc(HWND window,UINT message,WPARAM wparam,LPARAM lparam) {
    if(message==(swap_buttons?WM_LBUTTONUP:WM_RBUTTONUP)||message==WM_KILLFOCUS||(message==WM_ACTIVATEAPP&&!wparam)||
       (message==WM_SIZE&&wparam==SIZE_MINIMIZED)||message==WM_CLOSE||message==WM_DESTROY) release_clip();
    return DefWindowProcA(window,message,wparam,lparam);
}
static DWORD WINAPI input_frame(void*) {
    while(mode>=0) {
        auto generation=clip_generation();
        if(mode==2 && (GetAsyncKeyState(swap_buttons?VK_LBUTTON:VK_RBUTTON)&0x8000))hold_clip(generation);else release_clip();
        if(!polling){InterlockedExchange(&manual_ack,1);Sleep(5);continue;}
        InterlockedExchange(&manual_ack,0);
        DIMOUSESTATE2 state={};mouse->Acquire();
        const HRESULT state_result=mouse->GetDeviceState(sizeof(state),&state);
        trasc_takp_trace::frame(mode==2);
        trasc_takp_observation::state_result(state_result,sizeof(state),&state);
        if(SUCCEEDED(state_result)) {
            InterlockedExchangeAdd(totals,state.lX);InterlockedExchangeAdd(totals+1,state.lY);
            InterlockedExchange(&buttons,state.rgbButtons[1]!=0);
        }
        DIDEVICEOBJECTDATA events[256];DWORD count=256;
        HRESULT hr=mouse->GetDeviceData(sizeof(events[0]),events,&count,0);
        trasc_takp_observation::data_result(hr,sizeof(events[0]),events,256,&count,0);
        if(hr==DIERR_NOTACQUIRED||hr==DIERR_INPUTLOST)count=0; // expected foreground loss
        else if(FAILED(hr)||hr==DI_BUFFEROVERFLOW)ExitProcess(21);
        for(DWORD i=0;i<count;i++) {
            if(events[i].dwOfs==DIMOFS_X)InterlockedExchangeAdd(totals+2,(LONG)events[i].dwData);
            if(events[i].dwOfs==DIMOFS_Y)InterlockedExchangeAdd(totals+3,(LONG)events[i].dwData);
        }
        if(mode==1 && (GetAsyncKeyState(VK_RBUTTON)&0x8000))trasc_takp_camera::legacy_center(400,300,0,800,[](int x,int y){return SetCursorPos(x,y);});
        Sleep(5);
    }
    release_clip();return 0;
}
static void result(const char *value) {
    FILE *file=std::fopen("D:\\reply.tmp","wb");if(!file)ExitProcess(12);
    std::fputs(value,file);std::fclose(file);
    if(!MoveFileExA("D:\\reply.tmp","D:\\reply.txt",MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))ExitProcess(13);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE,LPSTR arguments,int) {
    if(!std::strncmp(arguments,"trace-smoke",11)){trasc_takp_trace::write("smoke bounded private camera telemetry");return 0;}
    if(!std::strncmp(arguments,"trace-cap",9)) {
        char text[800];std::memset(text,'x',sizeof(text)-1);text[sizeof(text)-1]=0;
        for(int i=0;i<10000;i++)trasc_takp_trace::write("cap %d %s",i,text);
        return 0;
    }
    InitializeCriticalSection(&clip_lock);
    WNDCLASSA cls={};cls.lpfnWndProc=window_proc;cls.hInstance=instance;cls.lpszClassName="TrascCursorProbe";
    if(!RegisterClassA(&cls))return 10;
    HWND window=CreateWindowA(cls.lpszClassName,"TAKP relative camera fixture",WS_POPUP|WS_VISIBLE,
                             0,0,800,600,nullptr,nullptr,instance,nullptr);
    if(!window || !GetProcAddress(GetModuleHandleW(L"ntdll.dll"),"wine_get_version"))return 11;
    game_window=window;SetForegroundWindow(window);SetFocus(window);
    for(int i=0;i<30;i++){MSG message;while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessage(&message);}Sleep(10);}
    SetCursorPos(400,300);result("ready");
    bool pump=false;HANDLE worker=nullptr;
    DWORD until=GetTickCount()+240000;
    while(GetTickCount()<until) {
        if(pump){MSG message;while(PeekMessage(&message,nullptr,0,0,PM_REMOVE)){TranslateMessage(&message);DispatchMessage(&message);}}
        FILE *file=std::fopen("D:\\command.txt","rb");
        if(!file){Sleep(1);continue;}
        char command[128]={};std::fgets(command,sizeof(command),file);std::fclose(file);
        DeleteFileA("D:\\command.txt");
        if(!std::strncmp(command,"quit",4)) {
            mode=-1;if(worker)WaitForSingleObject(worker,5000);release_clip();result(command);return 0;
        }
        if(!std::strncmp(command,"legacy",6))SetCursorPos(400,300);
        else if(!std::strncmp(command,"fixed",5))
            trasc_takp_camera::legacy_center(400,300,0,800,[](int x,int y){return SetCursorPos(x,y);});
        else if(!std::strncmp(command,"input",5)) {
            IDirectInput8A* input=nullptr;
            if(FAILED(DirectInput8Create(instance,0x0800,IID_IDirectInput8A,(void**)&input,nullptr))||
               FAILED(input->CreateDevice(GUID_SysMouse,&mouse,nullptr))||FAILED(mouse->SetDataFormat(&c_dfDIMouse2))||
               FAILED(mouse->SetCooperativeLevel(window,DISCL_FOREGROUND|DISCL_NONEXCLUSIVE)))return 16;
            DIPROPDWORD size={{sizeof(DIPROPDWORD),sizeof(DIPROPHEADER),0,DIPH_DEVICE},4096};
            if(FAILED(mouse->SetProperty(DIPROP_BUFFERSIZE,&size.diph)))return 17;
            trasc_takp_observation::format_result(DI_OK,&c_dfDIMouse2);
            trasc_takp_observation::property_result(DI_OK,DIPROP_BUFFERSIZE,&size.diph);
            pump=true;worker=CreateThread(nullptr,0,input_frame,nullptr,0,nullptr);if(!worker)return 18;
        }
        else if(!std::strncmp(command,"manual",6)) {
            InterlockedExchange(&polling,0);
            DWORD start=GetTickCount();while(!manual_ack&&GetTickCount()-start<5000)Sleep(1);
            if(!manual_ack)return 22;
        }
        else if(!std::strncmp(command,"auto",4))InterlockedExchange(&polling,1);
        else if(!std::strncmp(command,"absformat",9)) {
            if(!manual_ack)return 23;
            DIDATAFORMAT format=c_dfDIMouse2;format.dwFlags=DIDF_ABSAXIS;
            mouse->Unacquire();HRESULT hr=mouse->SetDataFormat(&format);
            trasc_takp_observation::format_result(hr,&format);
            if(FAILED(hr)||FAILED(mouse->Acquire()))return 24;
        }
        else if(!std::strncmp(command,"relproperty",11)) {
            if(!manual_ack)return 25;
            mouse->Unacquire();DIPROPDWORD axis={{sizeof(DIPROPDWORD),sizeof(DIPROPHEADER),0,DIPH_DEVICE},DIPROPAXISMODE_REL};
            HRESULT hr=mouse->SetProperty(DIPROP_AXISMODE,&axis.diph);
            trasc_takp_observation::property_result(hr,DIPROP_AXISMODE,&axis.diph);
            if(FAILED(hr)||FAILED(mouse->Acquire()))return 26;
        }
        else if(!std::strncmp(command,"customformat",12)) {
            if(!manual_ack||c_dfDIMouse2.dwNumObjs>32)return 31;
            DIDATAFORMAT format=c_dfDIMouse2;DIOBJECTDATAFORMAT objects[32];
            std::memcpy(objects,format.rgodf,format.dwNumObjs*sizeof(objects[0]));format.rgodf=objects;
            for(DWORD i=0;i<format.dwNumObjs;i++) {
                if(objects[i].pguid&&IsEqualGUID(*objects[i].pguid,GUID_XAxis))objects[i].dwOfs=8;
                if(objects[i].pguid&&IsEqualGUID(*objects[i].pguid,GUID_YAxis))objects[i].dwOfs=0;
                if(objects[i].pguid&&IsEqualGUID(*objects[i].pguid,GUID_ZAxis))objects[i].dwOfs=4;
            }
            mouse->Unacquire();HRESULT hr=mouse->SetDataFormat(&format);
            trasc_takp_observation::format_result(hr,&format);
            if(FAILED(hr)||FAILED(mouse->Acquire()))return 32;
        }
        else if(!std::strncmp(command,"readstate",9)) {
            if(!manual_ack)return 27;
            DIMOUSESTATE2 state={};const HRESULT hr=mouse->GetDeviceState(sizeof(state),&state);
            trasc_takp_observation::state_result(hr,sizeof(state),&state);
            if(FAILED(hr))return 28;
            char reply[192];std::sprintf(reply,"%s %ld %ld %ld",command,state.lX,state.lY,state.lZ);result(reply);continue;
        }
        else if(!std::strncmp(command,"readbuffer",10)||!std::strncmp(command,"peekbuffer",10)) {
            if(!manual_ack)return 29;
            const DWORD requested=command[10]=='1'?1:256;
            const DWORD flags=command[0]=='p'?DIGDD_PEEK:0;
            DIDEVICEOBJECTDATA events[256];DWORD count=requested;
            const HRESULT hr=mouse->GetDeviceData(sizeof(events[0]),events,&count,flags);
            trasc_takp_observation::data_result(hr,sizeof(events[0]),events,requested,&count,flags);
            if(FAILED(hr)||hr==DI_BUFFEROVERFLOW)return 30;
            LONG sum_x=0,sum_y=0;
            for(DWORD i=0;i<count;i++){if(events[i].dwOfs==DIMOFS_X)sum_x+=(LONG)events[i].dwData;if(events[i].dwOfs==DIMOFS_Y)sum_y+=(LONG)events[i].dwData;}
            char reply[192];std::sprintf(reply,"%s %lu %ld %ld %lu %lu",command,count,sum_x,sum_y,
                count?events[0].dwSequence:0,count?events[count-1].dwSequence:0);result(reply);continue;
        }
        else if(!std::strncmp(command,"warp",4))mode=1;
        else if(!std::strncmp(command,"raw",3))mode=2;
        else if(!std::strncmp(command,"free",4)) {mode=0;release_clip();}
        else if(!std::strncmp(command,"swap",4))InterlockedExchange(&swap_buttons,1);
        else if(!std::strncmp(command,"normal",6))InterlockedExchange(&swap_buttons,0);
        else if(!std::strncmp(command,"focus",5)){SetForegroundWindow(window);SetFocus(window);}
        else if(!std::strncmp(command,"blur",4)){ShowWindow(window,SW_MINIMIZE);release_clip();}
        else if(!std::strncmp(command,"resume",6)){ShowWindow(window,SW_RESTORE);SetForegroundWindow(window);SetFocus(window);}
        else if(!std::strncmp(command,"sample",6)) {
            POINT point;RECT current;GetCursorPos(&point);GetClipCursor(&current);
            char reply[320];std::sprintf(reply,"%s %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %d %d %d",command,
                totals[0],totals[1],totals[2],totals[3],buttons,point.x,point.y,current.left,current.top,current.right,current.bottom,
                GetForegroundWindow()==window,GetFocus()==window,!IsIconic(window));
            result(reply);continue;
        }
        else return 14;
        result(command);
    }
    mode=-1;return 15;
}
