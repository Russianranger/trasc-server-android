/*****************************************************************************
MQ2Main.dll: MacroQuest2's extension DLL for EverQuest
Copyright (C) 2002-2003 Plazmic, 2003-2005 Lax

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License, version 2, as published by
the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
******************************************************************************/

// Unmodified function excerpts from Triptych-Triumvirate 4c653ca.
#include "MQ2Main.h"
int __cdecl memcheck0(unsigned char *buffer, int count)
{
    unsigned int x, i;
    unsigned int eax = 0xffffffff;

    if (!extern_array0) {
        if (!EQADDR_ENCRYPTPAD0) {
            //_asm int 3
        } else {
            extern_array0 = (unsigned int *)EQADDR_ENCRYPTPAD0;
        }
    }

#ifdef ISXEQ
    unsigned char *realbuffer=(unsigned char *)malloc(count);
    pExtension->Memcpy_Clean((unsigned int)buffer,realbuffer,count);
#endif

    for (i=0;i<(unsigned int)count;i++) {
        unsigned char tmp;
#ifdef ISXEQ
        tmp=realbuffer[i];
#else
        unsigned int b=(int) &buffer[i];
        OurDetours *detour = ourdetours;
        while(detour)
        {
            if (detour->count && (b >= detour->addr) &&
                (b < detour->addr+detour->count) ) {
                    tmp = detour->array[b - detour->addr];
                    break;
            }
            detour=detour->pNext;
        }
        if (!detour) tmp = buffer[i];
#endif
        x = (int)tmp ^ (eax & 0xff);
        eax = ((int)eax >> 8) & 0xffffff;
        x = extern_array0[x];
        eax ^= x;
    }

#ifdef ISXEQ
    free(realbuffer);
#endif
    return eax;
}


int __cdecl memcheck1(unsigned char *buffer, int count, struct mckey key) 
{
    unsigned int i;
    unsigned int ebx, eax, edx;

    if (!extern_array1) {
        if (!EQADDR_ENCRYPTPAD1) {
            //_asm int 3
        } else {
            extern_array1 = (unsigned int *)EQADDR_ENCRYPTPAD1;
        }
    }
//                push    ebp
//                mov     ebp, esp
//                push    esi
//                push    edi
//                or      edi, 0FFFFFFFFh
//                cmp     [ebp+arg_8], 0
    if (key.x != 0) {
//                mov     esi, 0FFh
//                mov     ecx, 0FFFFFFh
//                jz      short loc_4C3978
//                xor     eax, eax
//                mov     al, byte ptr [ebp+arg_8]
//                xor     edx, edx
//                mov     dl, byte ptr [ebp+arg_8+1]
        edx = key.a[1];
//                not     eax
//                and     eax, esi
        eax = ~key.a[0] & 0xff;
//                mov     eax, encryptpad1[eax*4]
        eax = extern_array1[eax];
//                xor     eax, ecx
        eax ^= 0xffffff;
//                xor     edx, eax
//                and     edx, esi
        edx = (edx ^ eax) & 0xff;
//                sar     eax, 8
//                and     eax, ecx
        eax = ((int)eax >> 8) & 0xffffff;
//                xor     eax, encryptpad1[edx*4]
        eax ^= extern_array1[edx];
//                xor     edx, edx
//                mov     dl, byte ptr [ebp+arg_8+2]
        edx = key.a[2];
//                xor     edx, eax
//                sar     eax, 8
//                and     edx, esi
        edx = (edx ^ eax) & 0xff;
//                and     eax, ecx
        eax = ((int)eax >> 8) & 0xffffff;
//                xor     eax, encryptpad1[edx*4]
        eax ^= extern_array1[edx];
//                xor     edx, edx
//                mov     dl, byte ptr [ebp+arg_8+3]
        edx = key.a[3];
//                xor     edx, eax
//                sar     eax, 8
//                and     edx, esi
        edx = (edx ^ eax) & 0xff;
//                and     eax, ecx
        eax = ((int)eax >> 8) & 0xffffff;
//                xor     eax, encryptpad1[edx*4]
        eax ^= extern_array1[edx];
//                mov     edi, eax
//
    } else { // key.x != 0
        eax = 0xffffffff;
    }
//loc_4C3978:                             ; CODE XREF: new_memcheck1+16j
//                mov     edx, [ebp+arg_0]
//                mov     eax, [ebp+arg_4]
//                add     eax, edx
//                cmp     edx, eax
//                jnb     short loc_4C399F
//                push    ebx
//
//loc_4C3985:                             ; CODE XREF: new_memcheck1+8Fj
//                xor     ebx, ebx
//                mov     bl, [edx]
//                xor     ebx, edi
//                sar     edi, 8
//                and     ebx, esi
//                and     edi, ecx
//                xor     edi, encryptpad1[ebx*4]
//                inc     edx
//                cmp     edx, eax
//                jb      short loc_4C3985
//                pop     ebx
//
//loc_4C399F:                             ; CODE XREF: new_memcheck1+75j
//                mov     eax, edi
//                pop     edi
//                not     eax
//                pop     esi
//                pop     ebp
//                retn
//

#ifdef ISXEQ
    unsigned char *realbuffer=(unsigned char *)malloc(count);
    pExtension->Memcpy_Clean((unsigned int)buffer,realbuffer,count);
#endif

    for (i=0;i<(unsigned int)count;i++) {
        unsigned char tmp;
#ifdef ISXEQ
        tmp=realbuffer[i];
#else
        unsigned int b=(int) &buffer[i];
        OurDetours *detour = ourdetours;
        while(detour) {
            if (detour->count && (b >= detour->addr) &&
                (b < detour->addr+detour->count) ) {
                    tmp = detour->array[b - detour->addr];
                    break;
            }
            detour=detour->pNext;
        }
        if (!detour) tmp = buffer[i];
#endif
        ebx = ((int)tmp ^ eax) & 0xff;
        eax = ((int)eax >> 8) & 0xffffff;
        eax ^= extern_array1[ebx];
    }
#ifdef ISXEQ
    free(realbuffer);
#endif
    return ~eax;
}



int __cdecl memcheck2(unsigned char *, int, struct mckey) { return 0; }
