#define COBJMACROS
#include <windows.h>
#include <d3d9.h>
#include <stdio.h>
#include <string.h>

// ROF2 is a sizeable legacy PE32 image; exercise its low-address allocation class.
static volatile unsigned char legacy_image[20*1024*1024];
static BOOL pause_render,alternate_color,relative_test;
static LONG relative_total,buffered_total;
static BOOL chat=TRUE,unclipped,camera_look;
static char chat_text[128]="unsent draft";

static void marker(const char *name,const char *value) {
    // Readers use existence as readiness; never expose an empty/partial result.
    char temporary[MAX_PATH];
    if(snprintf(temporary,sizeof(temporary),"%s.tmp",name)>=(int)sizeof(temporary))ExitProcess(90);
    FILE *out=fopen(temporary,"w");
    if(!out||fputs(value,out)==EOF||fclose(out)!=0)ExitProcess(90);
    if(!MoveFileExA(temporary,name,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))ExitProcess(91);
}
static LRESULT CALLBACK window_proc(HWND window,UINT message,WPARAM key,LPARAM data) {
    if(message==WM_KEYDOWN&&key==VK_ESCAPE){chat=FALSE;chat_text[0]=0;}
    if(message==WM_CHAR){
        if(key=='/'&&!chat){chat=TRUE;chat_text[0]=0;}
        if(chat){
            size_t n=strlen(chat_text);
            if(key==13){marker("D:\\probe-command.txt",chat_text);chat=FALSE;}
            else if(key==8){if(n)chat_text[n-1]=0;}
            else if(key>=32&&key<127&&n+1<sizeof(chat_text)){chat_text[n]=(char)key;chat_text[n+1]=0;}
        }
    }
    if(message==WM_KEYDOWN&&key=='U'){ClipCursor(NULL);unclipped=TRUE;camera_look=TRUE;while(ShowCursor(FALSE)>=0){}}
    if(message==WM_KEYDOWN&&key=='N'){ClipCursor(NULL);unclipped=TRUE;camera_look=FALSE;while(ShowCursor(TRUE)<0){}}
    if(message==WM_KEYDOWN&&key=='M'){camera_look=FALSE;while(ShowCursor(TRUE)<0){};}
    if(message==WM_KEYDOWN&&key=='T')marker("D:\\probe-key.txt","T");
    if(message==WM_LBUTTONDOWN)marker("D:\\probe-mouse.txt","left");
    if(message==WM_KEYDOWN&&key=='P'){pause_render=!pause_render;marker("D:\\probe-paused.txt",pause_render?"yes":"no");}
    if(message==WM_KEYDOWN&&key=='V')alternate_color=!alternate_color;
    if(message==WM_KEYDOWN&&key=='R'){
        RECT area;GetWindowRect(window,&area);int x=(area.left+area.right)/2,y=(area.top+area.bottom)/2;
        SetCursorPos(x,y);RECT clip={x,y,x+1,y+1};ClipCursor(&clip);relative_total=buffered_total=0;relative_test=TRUE;unclipped=FALSE;
    }
    if(message==WM_KEYDOWN&&key=='E'){relative_test=FALSE;camera_look=FALSE;ClipCursor(NULL);while(ShowCursor(TRUE)<0){}}
    if(message==WM_DESTROY){PostQuitMessage(0);return 0;}
    return DefWindowProc(window,message,key,data);
}
int WINAPI WinMain(HINSTANCE instance,HINSTANCE previous,LPSTR command,int show) {
    legacy_image[sizeof(legacy_image)-1]=1;
    HMODULE dll=LoadLibraryA("dinput8.dll");
    int (*probe)(void)=dll?(void*)GetProcAddress(dll,"TrascProbe"):NULL;
    BOOL input_ready=probe&&probe()==0x54524153;
    if(strstr(command,"--check-directinput"))return input_ready?0:23;
    if(!input_ready){marker("D:\\probe-error.txt","Native proxy could not create keyboard/mouse through system DirectInput8");return 1;}
    // Match the routine debug-string exceptions dominating the Thor's trace.
    // This is an open workload, not a ROF2 frame-rate benchmark.
    if(strstr(command,"--check-debug-output")) {
        for(int i=0;i<512;i++)OutputDebugStringA("[TRASC probe] routine asset-loading diagnostic");
        return 0;
    }
    /* Reproduce ROF2's observed single-core process restriction. The native
       supervisor must free our real Linux threads without editing game files. */
    DWORD_PTR process_mask=0,system_mask=0;
    if(!GetProcessAffinityMask(GetCurrentProcess(),&process_mask,&system_mask)||!process_mask||
       !SetProcessAffinityMask(GetCurrentProcess(),process_mask&(~process_mask+1))) {
        marker("D:\\probe-error.txt","Could not reproduce game CPU restriction");return 3;
    }
    LoadLibraryA("d3dx9_30.dll");LoadLibraryA("d3dx9_35.dll");
    int (*held_key)(HWND,int)=(void*)GetProcAddress(dll,"TrascHeldKey");
    int (*mouse_delta)(HWND,LONG*,LONG*)=(void*)GetProcAddress(dll,"TrascMouseDelta");
    int (*camera_recenter)(HWND,int)=(void*)GetProcAddress(dll,"TrascCameraRecenter");
    BOOL saw_hold=FALSE;int previous_held=-99;
    WNDCLASSA cls={0};cls.lpfnWndProc=window_proc;cls.hInstance=instance;cls.lpszClassName="TrascProbe";
    RegisterClassA(&cls);
    char windowed[16];GetPrivateProfileStringA("Defaults","WindowedMode","TRUE",windowed,sizeof(windowed),"D:\\eqclient.ini");
    BOOL fullscreen=!lstrcmpiA(windowed,"FALSE");
    UINT width=GetPrivateProfileIntA("VideoMode","Width",800,"D:\\eqclient.ini");
    UINT height=GetPrivateProfileIntA("VideoMode","Height",600,"D:\\eqclient.ini");
    HWND window=CreateWindowA(cls.lpszClassName,"TRASC 32-bit Direct3D/input probe",(fullscreen?WS_POPUP:WS_OVERLAPPEDWINDOW)|WS_VISIBLE,
                             0,0,fullscreen?width:600,fullscreen?height:400,NULL,NULL,instance,NULL);
    SetForegroundWindow(window);SetFocus(window);
    IDirect3D9 *d3d=Direct3DCreate9(D3D_SDK_VERSION);
    D3DPRESENT_PARAMETERS params={0};params.Windowed=!fullscreen;params.SwapEffect=D3DSWAPEFFECT_DISCARD;params.hDeviceWindow=window;
    if(fullscreen){params.BackBufferWidth=width;params.BackBufferHeight=height;params.BackBufferFormat=D3DFMT_X8R8G8B8;params.PresentationInterval=D3DPRESENT_INTERVAL_IMMEDIATE;}
    IDirect3DDevice9 *device=NULL;
    if(!d3d||FAILED(IDirect3D9_CreateDevice(d3d,0,D3DDEVTYPE_HAL,window,D3DCREATE_SOFTWARE_VERTEXPROCESSING,&params,&device))) {
        marker("D:\\probe-error.txt","Direct3D9 device creation failed");return 2;
    }
    BOOL ready=FALSE;
    DWORD until=GetTickCount()+120000;
    while(GetTickCount()<until) {
        MSG msg;
        while(PeekMessage(&msg,NULL,0,0,PM_REMOVE)){if(msg.message==WM_QUIT)goto done;TranslateMessage(&msg);DispatchMessage(&msg);}
        HRESULT cleared=pause_render?S_OK:IDirect3DDevice9_Clear(device,0,NULL,D3DCLEAR_TARGET,alternate_color?D3DCOLOR_XRGB(96,72,24):D3DCOLOR_XRGB(24,72,96),1,0);
        HRESULT presented=pause_render?S_OK:IDirect3DDevice9_Present(device,NULL,NULL,NULL,NULL);
        if(!ready&&SUCCEEDED(cleared)&&SUCCEEDED(presented)) {
            IDirect3DSwapChain9 *chain=NULL;D3DPRESENT_PARAMETERS actual={0};RECT area={0};
            if(FAILED(IDirect3DDevice9_GetSwapChain(device,0,&chain))||FAILED(IDirect3DSwapChain9_GetPresentParameters(chain,&actual))||!GetClientRect(window,&area))return 4;
            char report[256];snprintf(report,sizeof(report),"{\"windowed\":%s,\"backbuffer_width\":%u,\"backbuffer_height\":%u,\"client_width\":%ld,\"client_height\":%ld}",actual.Windowed?"true":"false",actual.BackBufferWidth,actual.BackBufferHeight,area.right-area.left,area.bottom-area.top);
            marker("D:\\probe-display.json",report);IDirect3DSwapChain9_Release(chain);
            marker("D:\\probe-result.json","{\"pe32\":true,\"native_dinput8\":true,\"system_directinput\":true,\"direct3d9\":true}");
            ready=TRUE;
        }
        if(held_key) {
            int held=held_key(window,0x11); // DIK_W, polled like game movement.
            if(held!=previous_held){printf("DirectInput W state: %d\n",held);fflush(stdout);previous_held=held;}
            if(held==1){saw_hold=TRUE;marker("D:\\probe-held-key.txt","W held");}
            if(saw_hold&&held==0)marker("D:\\probe-released-key.txt","W released");
        }
        if(relative_test&&mouse_delta){
            LONG dx=0,buffered=0;int result=mouse_delta(window,&dx,&buffered);
            if(result==0){marker("D:\\probe-relative-ready.txt","ready");relative_total+=dx;buffered_total+=buffered;}
            if(buffered_total>=4096){char total[64];snprintf(total,sizeof(total),"%ld",buffered_total);marker("D:\\probe-buffered.txt",total);}
            if(unclipped){if(!camera_recenter)return 7;camera_recenter(window,camera_look);POINT pos,center;RECT rect;GetCursorPos(&pos);GetClientRect(window,&rect);center.x=(rect.left+rect.right)/2;center.y=(rect.top+rect.bottom)/2;ClientToScreen(window,&center);
                char value[128];snprintf(value,sizeof(value),"%ld %ld %ld %ld",pos.x,pos.y,center.x,center.y);marker(camera_look?"D:\\probe-warp.txt":"D:\\probe-menu.txt",value);}
            if(relative_total>=4096){char total[64];snprintf(total,sizeof(total),"%ld",relative_total);marker("D:\\probe-relative.txt",total);}
        }
        Sleep(30);
    }
done:
    ClipCursor(NULL);
    IDirect3DDevice9_Release(device);IDirect3D9_Release(d3d);return 0;
}
