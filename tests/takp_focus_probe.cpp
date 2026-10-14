// Reuse the qualified open PE32 consumer unchanged. Its process is launched
// as eqgame.exe; only this fixture's window title matches the real EQW window.
#include <windows.h>
static HWND WINAPI focus_probe_window(LPCSTR klass,LPCSTR,DWORD style,
    int x,int y,int width,int height,HWND parent,HMENU menu,HINSTANCE instance,LPVOID argument) {
    return CreateWindowExA(0,klass,"EqW-TAKP",style,x,y,width,height,parent,menu,instance,argument);
}
#undef CreateWindowA
#define CreateWindowA focus_probe_window
#include "takp_cursor_probe.cpp"
