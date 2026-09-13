#include <windows.h>
__declspec(dllexport) int TrascProbe(void){return 0x54524153;}
BOOL WINAPI DllMain(HINSTANCE instance,DWORD reason,LPVOID reserved){return TRUE;}
