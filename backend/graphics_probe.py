"""Verify a mapped GLX drawable, its real driver and a rendered pixel.

Mesa's virpipe front-buffer read can raise X_GetImage BadMatch on glxinfo's
unmapped window. Use the same mapped-window path as Wine instead.
"""
import ctypes as C


def main():
    ptr=C.c_void_p; integer=C.c_int; ulong=C.c_ulong
    class VisualInfo(C.Structure):
        _fields_=[('visual',ptr),('visualid',ulong),('screen',integer),('depth',integer),
                  ('visual_class',integer),('red_mask',ulong),('green_mask',ulong),
                  ('blue_mask',ulong),('colormap_size',integer),('bits_per_rgb',integer)]
    class Attributes(C.Structure):
        _fields_=[('background_pixmap',ulong),('background_pixel',ulong),('border_pixmap',ulong),
                  ('border_pixel',ulong),('bit_gravity',integer),('win_gravity',integer),
                  ('backing_store',integer),('backing_planes',ulong),('backing_pixel',ulong),
                  ('save_under',integer),('event_mask',C.c_long),('do_not_propagate_mask',C.c_long),
                  ('override_redirect',integer),('colormap',ulong),('cursor',ulong)]
    x=C.CDLL('libX11.so.6'); gl=C.CDLL('libGL.so.1')
    def bind(lib,name,result,args):
        f=getattr(lib,name);f.restype=result;f.argtypes=args;return f
    open_display=bind(x,'XOpenDisplay',ptr,[C.c_char_p])
    root_window=bind(x,'XRootWindow',ulong,[ptr,integer])
    choose=bind(gl,'glXChooseVisual',C.POINTER(VisualInfo),[ptr,integer,C.POINTER(integer)])
    create_map=bind(x,'XCreateColormap',ulong,[ptr,ulong,ptr,integer])
    create_window=bind(x,'XCreateWindow',ulong,[ptr,ulong,integer,integer,C.c_uint,C.c_uint,C.c_uint,integer,C.c_uint,ptr,ulong,C.POINTER(Attributes)])
    map_window=bind(x,'XMapWindow',integer,[ptr,ulong])
    sync=bind(x,'XSync',integer,[ptr,integer])
    create_context=bind(gl,'glXCreateContext',ptr,[ptr,C.POINTER(VisualInfo),ptr,integer])
    make_current=bind(gl,'glXMakeCurrent',integer,[ptr,ulong,ptr])
    get_string=bind(gl,'glGetString',C.c_char_p,[C.c_uint])
    clear_color=bind(gl,'glClearColor',None,[C.c_float]*4)
    clear=bind(gl,'glClear',None,[C.c_uint])
    read=bind(gl,'glReadPixels',None,[integer,integer,integer,integer,C.c_uint,C.c_uint,ptr])
    error=bind(gl,'glGetError',C.c_uint,[])
    swap=bind(gl,'glXSwapBuffers',None,[ptr,ulong])
    display=open_display(None)
    if not display: raise RuntimeError('Cannot open private X display')
    # A double-buffered RGB drawable, matching the WineD3D window path.
    visual=choose(display,0,(integer*10)(4,5,8,8,9,8,10,8,0,0))
    if not visual: raise RuntimeError('No RGB GLX visual')
    root=root_window(display,visual.contents.screen)
    attributes=Attributes();attributes.colormap=create_map(display,root,visual.contents.visual,0)
    attributes.override_redirect=1
    window=create_window(display,root,0,0,32,32,0,visual.contents.depth,1,visual.contents.visual,
                         (1<<13)|(1<<9),C.byref(attributes))
    map_window(display,window);sync(display,0)
    context=create_context(display,visual,None,1)
    if not context or not make_current(display,window,context): raise RuntimeError('GLX context creation failed')
    for label,key in [('vendor',0x1F00),('renderer',0x1F01),('version',0x1F02)]:
        value=get_string(key)
        if not value: raise RuntimeError('Missing OpenGL '+label)
        print('OpenGL '+label+' string: '+value.decode(errors='replace'),flush=True)
    clear_color(1,0,0,1);clear(0x4000)
    pixel=(C.c_ubyte*4)();read(0,0,1,1,0x1908,0x1401,pixel)
    gl_error=error()
    if gl_error or list(pixel)[:3]!=[255,0,0]:
        raise RuntimeError(f'GLX render/readback failed: error={gl_error}, pixel={list(pixel)}')
    swap(display,window);sync(display,0)
    print('PASS: mapped GLX drawable rendered and read back the expected pixel',flush=True)
    make_current(display,0,None)
    bind(gl,'glXDestroyContext',None,[ptr,ptr])(display,context)
    bind(x,'XDestroyWindow',integer,[ptr,ulong])(display,window)
    bind(x,'XFreeColormap',integer,[ptr,ulong])(display,attributes.colormap)
    bind(x,'XFree',integer,[ptr])(visual)
    bind(x,'XCloseDisplay',integer,[ptr])(display)


if __name__=='__main__': main()
