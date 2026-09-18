#define DIRECTINPUT_VERSION 0x0800
#include "../backend/eq_camera_mouse.h"

// Open fixture drives the production recenter function through menu/look/focus
// transitions. No proprietary game or fake game offsets enter the DLL build.
extern "C" __declspec(dllexport) int TrascCameraRecenter(HWND window, int camera) {
    return trasc_camera::recenter(window, camera != 0);
}
