#define DIRECTINPUT_VERSION 0x0800
#include "../backend/eq_camera_mouse.h"

static BYTE *fixtureImage() {
    static BYTE *image = static_cast<BYTE *>(VirtualAlloc(NULL, 0x12c3000, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE));
    if (!image) ExitProcess(92);
    *reinterpret_cast<DWORD *>(image + 0xa67ccc) = reinterpret_cast<DWORD>(image + 0x1000);
    return image;
}

// Supply only synthetic game state. Every DirectInput poll now goes through
// processRead, including its actual Wine capabilities query and buffer gate.
extern "C" __declspec(dllexport) int TrascCameraRecenter(HWND window, int camera) {
    (void)window;
    BYTE *image = fixtureImage();
    *reinterpret_cast<DWORD *>(image + 0x1000 + 0x5c8) = camera ? 5 : 2;
    image[0x9df702] = camera != 0;
    return 0;
}

extern "C" void TrascCameraRead(void *device, HRESULT result, void *state) {
    BYTE *image = fixtureImage();
    void *buffer = image + 0xa67884;
    memcpy(buffer, state, sizeof(DIMOUSESTATE2));
    trasc_camera::processRead(static_cast<IDirectInputDevice8A *>(device), result,
        sizeof(DIMOUSESTATE2), buffer, image);
    if (memcmp(buffer, state, sizeof(DIMOUSESTATE2))) ExitProcess(93);
}
