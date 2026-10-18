"""Exact, reversible RoF2 720-to-1440 spellbook compatibility patch.

Algorithm and patch table ported from thezerodivide/SpellbookSizeUpdate,
commit 38a153d273f448ad1953d0b89497470443fd590e (tools/patcher/).
Only the byte-exact supported executable (or its LAA-bit-only variant) is
modified. No game executable or other client assets are distributed.

MIT License

Copyright (c) 2026 thezerodivide

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""
import hashlib
import json
import os
from pathlib import Path
import stat
import struct
import threading
import types

import client_connection as connection

SOURCE_COMMIT = '38a153d273f448ad1953d0b89497470443fd590e'
SOURCE_URL = 'https://github.com/thezerodivide/SpellbookSizeUpdate/tree/' + SOURCE_COMMIT
BASE_SHA256 = '4a456734af62b465660610794780e48ac3b0161f7b96e13aee86267c45ea49a3'
BASE_SIZE = 8774656
PATCHED_SIZE = BASE_SIZE + 512
RECOVERY = connection.RECOVERY
KIND = 'spellbook'
GUEST_CLIENT = Path('/client')
GUEST_WORK = Path('/work')
TABLE_SHA256 = 'a5eb88a400bde346610093cb904ebafc1965d9f745139e4ff1631dbb79c6f004'
_LOCK = threading.RLock()
_EXPECTED_HASHES = {}

# The complete 115-entry table, including explanatory upstream annotations.
TABLE = json.loads(r'''[
 {
  "va": "449cf2",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 449cd0)"
 },
 {
  "va": "449cfb",
  "expect": "399cb020250000",
  "replace": "399cb050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: cmp dword ptr [eax + esi*4 + 0x2520], ebx"
 },
 {
  "va": "449d05",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 449cd0)"
 },
 {
  "va": "449d42",
  "expect": "0520250000",
  "replace": "0550990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: add eax, 0x2520"
 },
 {
  "va": "449d47",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 449cd0)"
 },
 {
  "va": "449d56",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 449cd0)"
 },
 {
  "va": "4605dc",
  "expect": "81f9d0020000",
  "replace": "81f9a0050000",
  "why": "slot bound 720 -> 1440: cmp ecx, 0x2d0 (fn 4605d0)"
 },
 {
  "va": "4605e5",
  "expect": "8b848820250000",
  "replace": "8b848850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + ecx*4 + 0x2520]"
 },
 {
  "va": "4bea0b",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 4be9d0)"
 },
 {
  "va": "4bea14",
  "expect": "89bcb020250000",
  "replace": "89bcb050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [eax + esi*4 + 0x2520], edi"
 },
 {
  "va": "4bea1c",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 4be9d0)"
 },
 {
  "va": "578fe9",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 5789b0)"
 },
 {
  "va": "578ff2",
  "expect": "89bcb020250000",
  "replace": "89bcb050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [eax + esi*4 + 0x2520], edi"
 },
 {
  "va": "578ffa",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 5789b0)"
 },
 {
  "va": "648229",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 648200)"
 },
 {
  "va": "648232",
  "expect": "8bac9820250000",
  "replace": "8bac9850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov ebp, dword ptr [eax + ebx*4 + 0x2520]"
 },
 {
  "va": "648261",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 648200)"
 },
 {
  "va": "64826a",
  "expect": "8b849820250000",
  "replace": "8b849850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + ebx*4 + 0x2520]"
 },
 {
  "va": "6482e7",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 648200)"
 },
 {
  "va": "75b885",
  "expect": "81ffcf020000",
  "replace": "81ff9f050000",
  "why": "slot bound 719 -> 1439: cmp edi, 0x2cf (fn 75b880)"
 },
 {
  "va": "75bc37",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75bc00)"
 },
 {
  "va": "75bc40",
  "expect": "39bcb020250000",
  "replace": "39bcb050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: cmp dword ptr [eax + esi*4 + 0x2520], edi"
 },
 {
  "va": "75bc4a",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75bc00)"
 },
 {
  "va": "75bd9f",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75bd40)"
 },
 {
  "va": "75bda8",
  "expect": "8b84b820250000",
  "replace": "8b84b850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "75bdfe",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75bd40)"
 },
 {
  "va": "75be07",
  "expect": "3bacb820250000",
  "replace": "3bacb850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: cmp ebp, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "75be4e",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75bd40)"
 },
 {
  "va": "75be57",
  "expect": "8b84b820250000",
  "replace": "8b84b850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "75bfb7",
  "expect": "0520250000",
  "replace": "0550990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: add eax, 0x2520"
 },
 {
  "va": "75bfbc",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75bf30)"
 },
 {
  "va": "75c03c",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75bf30)"
 },
 {
  "va": "75c045",
  "expect": "3b9cb020250000",
  "replace": "3b9cb050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: cmp ebx, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75c06f",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75bf30)"
 },
 {
  "va": "75c078",
  "expect": "8b84b020250000",
  "replace": "8b84b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75c0ef",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75bf30)"
 },
 {
  "va": "75c0f8",
  "expect": "8b84b020250000",
  "replace": "8b84b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75c29e",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75c290)"
 },
 {
  "va": "75c2d7",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75c290)"
 },
 {
  "va": "75c2e0",
  "expect": "8b84b020250000",
  "replace": "8b84b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75c449",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 75c340)"
 },
 {
  "va": "75c46c",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 75c340)"
 },
 {
  "va": "75c475",
  "expect": "8b849820250000",
  "replace": "8b849850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + ebx*4 + 0x2520]"
 },
 {
  "va": "75c4a4",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 75c340)"
 },
 {
  "va": "75c4ad",
  "expect": "8b849820250000",
  "replace": "8b849850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + ebx*4 + 0x2520]"
 },
 {
  "va": "75c631",
  "expect": "81fecf020000",
  "replace": "81fe9f050000",
  "why": "slot bound 719 -> 1439: cmp esi, 0x2cf (fn 75c620)"
 },
 {
  "va": "75c654",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75c620)"
 },
 {
  "va": "75c65d",
  "expect": "8b84b020250000",
  "replace": "8b84b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75c68c",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75c620)"
 },
 {
  "va": "75c695",
  "expect": "8b84b020250000",
  "replace": "8b84b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75c773",
  "expect": "81ffcf020000",
  "replace": "81ff9f050000",
  "why": "slot bound 719 -> 1439: cmp edi, 0x2cf (fn 75c760)"
 },
 {
  "va": "75c792",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75c760)"
 },
 {
  "va": "75c79d",
  "expect": "c784b820250000ffffffff",
  "replace": "c784b850990000ffffffff",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [eax + edi*4 + 0x2520], 0xffffffff"
 },
 {
  "va": "75c887",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75c820)"
 },
 {
  "va": "75c890",
  "expect": "8b84b020250000",
  "replace": "8b84b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75c8bb",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75c820)"
 },
 {
  "va": "75c8c4",
  "expect": "8b84b020250000",
  "replace": "8b84b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75c90e",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75c820)"
 },
 {
  "va": "75cf52",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 75ceb0)"
 },
 {
  "va": "75d0aa",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75d080)"
 },
 {
  "va": "75d0b3",
  "expect": "8b84b820250000",
  "replace": "8b84b850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "75d0e2",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75d080)"
 },
 {
  "va": "75d0eb",
  "expect": "8b84b820250000",
  "replace": "8b84b850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "75d180",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75d080)"
 },
 {
  "va": "75d189",
  "expect": "3b9cb820250000",
  "replace": "3b9cb850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: cmp ebx, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "75d267",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75d080)"
 },
 {
  "va": "75d272",
  "expect": "3b8cb820250000",
  "replace": "3b8cb850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: cmp ecx, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "75d2d3",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75d080)"
 },
 {
  "va": "75d2e8",
  "expect": "89acb820250000",
  "replace": "89acb850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [eax + edi*4 + 0x2520], ebp"
 },
 {
  "va": "75d3b6",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75d380)"
 },
 {
  "va": "75d3c6",
  "expect": "8bacb020250000",
  "replace": "8bacb050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov ebp, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75d402",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75d380)"
 },
 {
  "va": "75d40c",
  "expect": "8b9cb820250000",
  "replace": "8b9cb850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov ebx, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "75d42a",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75d380)"
 },
 {
  "va": "75d433",
  "expect": "899cb020250000",
  "replace": "899cb050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [eax + esi*4 + 0x2520], ebx"
 },
 {
  "va": "75d452",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 75d380)"
 },
 {
  "va": "75d45f",
  "expect": "89acb820250000",
  "replace": "89acb850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [eax + edi*4 + 0x2520], ebp"
 },
 {
  "va": "75d4aa",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75d480)"
 },
 {
  "va": "75d4ef",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75d480)"
 },
 {
  "va": "75d4f8",
  "expect": "8b84b020250000",
  "replace": "8b84b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75d533",
  "expect": "81fed0020000",
  "replace": "81fea0050000",
  "why": "slot bound 720 -> 1440: cmp esi, 0x2d0 (fn 75d480)"
 },
 {
  "va": "75d546",
  "expect": "8b94b020250000",
  "replace": "8b94b050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov edx, dword ptr [eax + esi*4 + 0x2520]"
 },
 {
  "va": "75e2ca",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 75ddf0)"
 },
 {
  "va": "7d42ab",
  "expect": "8b84b820250000",
  "replace": "8b84b850990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [eax + edi*4 + 0x2520]"
 },
 {
  "va": "7eb420",
  "expect": "3dcf020000",
  "replace": "3d9f050000",
  "why": "slot bound 719 -> 1439: cmp eax, 0x2cf (fn 7eac20)"
 },
 {
  "va": "7eb427",
  "expect": "8b8f5c300000",
  "replace": "8b8fccaf0000",
  "why": "last spellbook slot: mov ecx, dword ptr [edi + 0x305c]"
 },
 {
  "va": "7eb445",
  "expect": "8b948f20250000",
  "replace": "8b948f50990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov edx, dword ptr [edi + ecx*4 + 0x2520]"
 },
 {
  "va": "7eb477",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 7eac20)"
 },
 {
  "va": "7ed6c3",
  "expect": "8984be20250000",
  "replace": "8984be50990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [esi + edi*4 + 0x2520], eax"
 },
 {
  "va": "7ed6cc",
  "expect": "c784be2025000000000000",
  "replace": "c784be5099000000000000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [esi + edi*4 + 0x2520], 0"
 },
 {
  "va": "7ed6d8",
  "expect": "81ffd0020000",
  "replace": "81ffa0050000",
  "why": "slot bound 720 -> 1440: cmp edi, 0x2d0 (fn 7ebb70)"
 },
 {
  "va": "7ed6e2",
  "expect": "b9d0020000",
  "replace": "b9a0050000",
  "why": "slot bound 720 -> 1440: mov ecx, 0x2d0 (fn 7ebb70)"
 },
 {
  "va": "7ed6e9",
  "expect": "8dbe20250000",
  "replace": "8dbe50990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: lea edi, [esi + 0x2520]"
 },
 {
  "va": "7ed6f3",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 7ebb70)"
 },
 {
  "va": "7ed6fb",
  "expect": "83bc862025000000",
  "replace": "83bc865099000000",
  "why": "spellbook base 0x2520 -> tail 0x9950: cmp dword ptr [esi + eax*4 + 0x2520], 0"
 },
 {
  "va": "7ed705",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 7ebb70)"
 },
 {
  "va": "7ed70d",
  "expect": "c7848620250000ffffffff",
  "replace": "c7848650990000ffffffff",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [esi + eax*4 + 0x2520], 0xffffffff"
 },
 {
  "va": "7ed719",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 7ebb70)"
 },
 {
  "va": "7edae7",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 7edaa0)"
 },
 {
  "va": "7edaff",
  "expect": "898c8720250000",
  "replace": "898c8750990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [edi + eax*4 + 0x2520], ecx"
 },
 {
  "va": "7edb0a",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 7edaa0)"
 },
 {
  "va": "7ee79f",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 7ee560)"
 },
 {
  "va": "7ee7a7",
  "expect": "c7848620250000ffffffff",
  "replace": "c7848650990000ffffffff",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov dword ptr [esi + eax*4 + 0x2520], 0xffffffff"
 },
 {
  "va": "7ee7b3",
  "expect": "3dd0020000",
  "replace": "3da0050000",
  "why": "slot bound 720 -> 1440: cmp eax, 0x2d0 (fn 7ee560)"
 },
 {
  "va": "7ee8c4",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 7ee880)"
 },
 {
  "va": "7ee8cd",
  "expect": "8b849f20250000",
  "replace": "8b849f50990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: mov eax, dword ptr [edi + ebx*4 + 0x2520]"
 },
 {
  "va": "7ee8e5",
  "expect": "81fbd0020000",
  "replace": "81fba0050000",
  "why": "slot bound 720 -> 1440: cmp ebx, 0x2d0 (fn 7ee880)"
 },
 {
  "va": "7ef4ad",
  "expect": "8db020250000",
  "replace": "8db050990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: lea esi, [eax + 0x2520]"
 },
 {
  "va": "7ef4b3",
  "expect": "8d8b20250000",
  "replace": "8d8b50990000",
  "why": "spellbook base 0x2520 -> tail 0x9950: lea ecx, [ebx + 0x2520]"
 },
 {
  "va": "7ef4bd",
  "expect": "81fad0020000",
  "replace": "81faa0050000",
  "why": "slot bound 720 -> 1440: cmp edx, 0x2d0 (fn 7ef330)"
 },
 {
  "va": "7ef4cf",
  "expect": "81fad0020000",
  "replace": "81faa0050000",
  "why": "slot bound 720 -> 1440: cmp edx, 0x2d0 (fn 7ef330)"
 },
 {
  "va": "7bec13",
  "expect": "6850990000",
  "replace": "68d0af0000",
  "why": "allocate 0xafd0 bytes (was 0x9950) so the 1440-slot spellbook fits after the object"
 },
 {
  "va": "7cd1e5",
  "expect": "6850990000",
  "replace": "68d0af0000",
  "why": "allocate 0xafd0 bytes (was 0x9950) so the 1440-slot spellbook fits after the object"
 },
 {
  "va": "460876",
  "expect": "6888340000",
  "replace": "68d0af0000",
  "why": "allocate 0xafd0 bytes (was 0x3488) so the 1440-slot spellbook fits after the object"
 },
 {
  "va": "75d599",
  "expect": "83f8587e158bcec7862c02000058000000e891edffff5ec20400",
  "replace": "3db20000007e13b8b2000000eb0c909090909090909090909090",
  "why": "page limit: left page max 0x58 (90 pages) -> 0xB2 (180 pages)"
 }
]''')


class Refusal(ValueError):
    pass


def _u16(raw, offset):
    if offset < 0 or offset + 2 > len(raw):
        raise Refusal('Truncated client PE header')
    return struct.unpack_from('<H', raw, offset)[0]


def _u32(raw, offset):
    if offset < 0 or offset + 4 > len(raw):
        raise Refusal('Truncated client PE header')
    return struct.unpack_from('<I', raw, offset)[0]


def _put16(raw, offset, value):
    struct.pack_into('<H', raw, offset, value & 0xffff)


def _put32(raw, offset, value):
    struct.pack_into('<I', raw, offset, value & 0xffffffff)


def parse_pe(raw):
    # Shared ordinary-PE checks also reject DLLs, 64-bit programs and truncated
    # sections. The upstream spellbook algorithm then checks its exact layout.
    connection.pe_info(raw)
    pe = _u32(raw, 0x3c)
    if len(raw) < 0x400 or raw[pe:pe+4] != b'PE\0\0':
        raise Refusal('This is not the supported RoF2 executable')
    count = _u16(raw, pe + 6)
    opt = pe + 24
    tab = opt + _u16(raw, pe + 20)
    if not 1 <= count <= 32 or tab + count * 40 > len(raw):
        raise Refusal('Invalid client section table')
    sections = []
    for index in range(count):
        offset = tab + index * 40
        name = raw[offset:offset+8].replace(b'\0', b'').decode('latin1')
        sections.append(dict(offset=offset, name=name, vs=_u32(raw, offset+8),
                             va=_u32(raw, offset+12), rs=_u32(raw, offset+16),
                             raw=_u32(raw, offset+20)))
    text = next((s for s in sections if s['name'] == '.text'), None)
    reloc = next((s for s in sections if s['name'] == '.reloc'), None)
    if text is None or reloc is None or _u32(raw, opt+28) != 0x400000:
        raise Refusal('The supported RoF2 code and relocation sections were not found')
    return dict(pe=pe, opt=opt, tab=tab, count=count, sections=sections, text=text, reloc=reloc)


def build(raw, set_laa=True):
    """Pure, bounded port of upstream build(); every byte guard precedes edits."""
    pe = parse_pe(raw)
    if any(s['name'] == '.sbook' for s in pe['sections']):
        raise Refusal('This executable already has a .sbook section')
    if hashlib.sha256(json.dumps(TABLE, sort_keys=True, separators=(',', ':')).encode()).hexdigest() != TABLE_SHA256:
        raise Refusal('The bundled spellbook patch table failed its integrity check')
    text, reloc = pe['text'], pe['reloc']

    def offset(va):
        rva = va - 0x400000
        if not text['va'] <= rva < text['va'] + text['rs']:
            raise Refusal('Spellbook patch address is outside the code section')
        result = rva - text['va'] + text['raw']
        if not 0 <= result < len(raw):
            raise Refusal('Spellbook patch address is outside the executable')
        return result

    def rel32(source, target):
        return struct.pack('<I', (target-source) & 0xffffffff)

    checked = []
    for entry in TABLE:
        before, after = bytes.fromhex(entry['expect']), bytes.fromhex(entry['replace'])
        pos = offset(int(entry['va'], 16))
        if len(before) != len(after) or raw[pos:pos+len(before)] != before:
            raise Refusal('The client does not match the spellbook patch at 0x' + entry['va'] + '; no files were changed')
        checked.append((pos, after))
    site1, site2, original_read = 0x57cbd1, 0x578fd6, 0x57b600
    hook1 = bytes.fromhex('68d00200008d97bc1a0000528bcee8') + rel32(0x57cbe4, original_read)
    hook2 = bytes.fromhex('8bbcb3bc1a0000')
    if raw[offset(site1):offset(site1)+len(hook1)] != hook1:
        raise Refusal('The client profile-reading hook does not match; no files were changed')
    if raw[offset(site2):offset(site2)+len(hook2)] != hook2:
        raise Refusal('The client spellbook-copy hook does not match; no files were changed')
    hdr = pe['tab'] + pe['count'] * 40
    if hdr + 40 > min(s['raw'] for s in pe['sections']) or raw[hdr:hdr+40] != b'\0' * 40:
        raise Refusal('The client has no empty section-header slot')
    opt = pe['opt']
    size_of_image = _u32(raw, opt+56)
    if not size_of_image or size_of_image > 0xffffdfff:
        raise Refusal('Invalid client SizeOfImage')
    dd5 = opt + 96 + 5 * 8
    directory_size = _u32(raw, dd5+4)
    if _u32(raw, dd5) != reloc['va']:
        raise Refusal('The client relocation directory does not match')
    cave = bytearray(b'\xcc' * 512)
    fixups = []
    base = 0x400000 + size_of_image
    bg, flag = base + 0x200, base + 0x200 + 1440 * 4

    def emit(position, parts):
        for part in parts:
            if isinstance(part, str):
                value = bytes.fromhex(part)
            elif 'abs' in part:
                value = struct.pack('<I', part['abs'])
                fixups.append(position)
            else:
                value = rel32(base+position+4, part.get('call', part.get('jmp')))
            if position+len(value) > len(cave):
                raise Refusal('Internal spellbook cave overflow')
            cave[position:position+len(value)] = value
            position += len(value)

    emit(0, ['50', '51', '57', 'bf', {'abs': bg}, 'b9a0050000', '83c8ff', 'fc',
             'f3ab', '5f', '59', '58', '68a0050000', '68', {'abs': bg}, '8bce',
             'e8', {'call': original_read}, 'c705', {'abs': flag}, '01000000',
             '56', '57', 'be', {'abs': bg}, '8dbfbc1a0000', 'b9d0020000',
             'fc', 'f3a5', '5f', '5e', 'c3'])
    emit(0x80, ['81fed0020000', '730c', '8bbcb3bc1a0000', 'e9', {'jmp': 0x578fdd},
                '833d', {'abs': flag}, '00', 'bfffffffff', '7407', '8b3cb5',
                {'abs': bg}, 'e9', {'jmp': 0x578fdd}])
    if any(r >= 0x1000 for r in fixups):
        raise Refusal('Internal spellbook relocation overflow')
    entries = [0x3000 | r for r in fixups]
    if len(entries) % 2:
        entries.append(0)
    block = struct.pack('<II', size_of_image, 8+len(entries)*2) + struct.pack('<'+'H'*len(entries), *entries)
    if directory_size > reloc['rs'] or reloc['rs'] - directory_size < len(block):
        raise Refusal('Insufficient relocation-section space')
    reloc_end = reloc['raw'] + directory_size
    if reloc_end + len(block) > len(raw):
        raise Refusal('Truncated relocation section')

    out = bytearray(raw)
    for pos, replacement in checked:
        out[pos:pos+len(replacement)] = replacement
    out[offset(site1):offset(site1)+19] = b'\xe8' + rel32(site1+5, base) + b'\x90' * 14
    out[offset(site2):offset(site2)+7] = b'\xe9' + rel32(site2+5, base+0x80) + b'\x90' * 2
    out[reloc_end:reloc_end+len(block)] = block
    _put32(out, dd5+4, directory_size+len(block))
    if reloc['vs'] < directory_size+len(block):
        _put32(out, reloc['offset']+8, directory_size+len(block))
    out += cave
    out[hdr:hdr+8] = b'.sbook\0\0'
    _put32(out, hdr+8, 0x2000)
    _put32(out, hdr+12, size_of_image)
    _put32(out, hdr+16, 512)
    _put32(out, hdr+20, len(raw))
    _put32(out, hdr+36, 0xe0000060)
    _put16(out, pe['pe']+6, pe['count']+1)
    _put32(out, opt+56, size_of_image+0x2000)
    if set_laa:
        _put16(out, pe['pe']+22, _u16(out, pe['pe']+22) | 0x20)
    _put32(out, opt+64, 0)
    # PE checksum: bounded generator, no per-word Python list allocation.
    total = sum(item[0] for item in struct.iter_unpack('<H', memoryview(out)[:len(out)//2*2]))
    if len(out) % 2:
        total += out[-1]
    while total >> 16:
        total = (total & 0xffff) + (total >> 16)
    _put32(out, opt+64, (total & 0xffff)+len(out))
    return bytes(out)


def _base_supported(raw):
    if len(raw) != BASE_SIZE:
        return False
    if connection.sha(raw) == BASE_SHA256:
        return True
    # The existing launcher changes only this bit. Recognize exactly that
    # reversible variant, with every other original byte held to SHA-256.
    try:
        pos, _ = connection.pe_info(raw)
    except ValueError:
        return False
    alternate = bytearray(raw)
    alternate[pos] ^= 0x20
    return connection.sha(alternate) == BASE_SHA256


def require_stopped(engine):
    if engine.profile != 'custom':
        raise Refusal('The 1,440-slot patch belongs to TRASC Custom')
    if getattr(engine, 'server_running', lambda: False)():
        raise Refusal('Stop the server before changing spellbook compatibility')
    connection.require_stopped(engine)


def _cancel(engine):
    event = getattr(engine, 'cancel', None)
    if event is not None and event.is_set():
        raise Refusal('Spellbook patch cancelled; the executable is unchanged')


def _fsync_directory(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0) | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _original(engine, path, identity):
    return connection.recovery(engine, KIND, path, identity)


def _retain_base_variant(engine, path, identity, raw, record):
    """Admit only the pinned LAA-bit variant without replacing our original.

    The separate legacy 4 GB restore can change that bit after spellbook
    restoration. Its known SHA-256 variant is safe to repatch, but must not
    become a new recovery baseline or relax the arbitrary-edit check.
    """
    current = connection.sha(raw)
    if record is None or current in record['accepted'] + [record['original_sha256']]:
        return
    original = connection.read(connection.confined(engine, record['backup']), BASE_SIZE)
    if not _base_supported(raw) or not _base_supported(original):
        raise Refusal('The client changed outside the supported LAA-bit variant; the protected original is unchanged')
    pos, _ = connection.pe_info(original)
    alternate = bytearray(original)
    alternate[pos] ^= 0x20
    if raw != alternate:
        raise Refusal('The client changed beyond the supported LAA flag; the protected original is unchanged')
    record = dict(record, accepted=record['accepted'] + [current])
    marker = connection.confined(engine, RECOVERY + '/' + KIND + '-' + identity + '.json')
    connection.atomic(marker, json.dumps(record, indent=2).encode(), 0o600)


def _inspect(engine):
    root, executable, identity = connection.local(engine)
    path = connection.lookup(root, executable)
    raw = connection.read(path, PATCHED_SIZE)
    record = _original(engine, path, identity)
    if _base_supported(raw):
        # Full guarded build ensures the fingerprint and this reviewed patch
        # table are compatible before offering Apply.
        key = connection.sha(raw)
        if key not in _EXPECTED_HASHES:
            _EXPECTED_HASHES[key] = connection.sha(build(raw))
        return root, path, identity, raw, record, False
    if record and len(raw) == PATCHED_SIZE:
        original = connection.read(connection.confined(engine, record['backup']), BASE_SIZE)
        if _base_supported(original):
            key = connection.sha(original)
            if key not in _EXPECTED_HASHES:
                _EXPECTED_HASHES[key] = connection.sha(build(original))
            if connection.sha(raw) == _EXPECTED_HASHES[key]:
                return root, path, identity, raw, record, True
    raise Refusal('This eqgame.exe is not the verified RoF2 client or its exact TRASC 1,440-slot patch; no bytes were changed')


def recognizes_supported_executable(path):
    """Recognize the pinned base or a byte-exact patch with protected original."""
    path = Path(path)
    try:
        # The client runner reads the /client bind; protected originals and
        # import identity remain in the same world's /work mount. Accept that
        # alias only when it is the very same file as the canonical client.
        if path.parent == GUEST_CLIENT:
            canonical = GUEST_WORK / 'client/current' / path.name
            if not path.samefile(canonical):
                return False
            path = canonical
        if path.name.casefold() != 'eqgame.exe' or path.parent.name != 'current' or path.parent.parent.name != 'client':
            return False
        engine = types.SimpleNamespace(work=path.parents[2], profile='custom')
        _, checked, _, _, _, _ = _inspect(engine)
        return checked == path
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
        return False


def status(engine, args=None):
    result = dict(profile=engine.profile, revision='', sha256='', path='client/current/eqgame.exe',
                  patched=False, supported=False, can_apply=False, can_restore=False,
                  backup_exists=False, backup_path='', warning='', expected_slots=1440,
                  source_commit=SOURCE_COMMIT, source_url=SOURCE_URL, message='',
                  base_sha256=BASE_SHA256, expected_patched_sha256='')
    if engine.profile != 'custom':
        result['warning'] = 'The 1,440-slot patch belongs to TRASC Custom'
        return result
    try:
        _, path, _, raw, record, patched = _inspect(engine)
        revision = connection.sha(raw)
        result.update(revision=revision, sha256=revision, path=str(path.relative_to(engine.work)),
                      patched=patched, supported=True, can_apply=True,
                      expected_patched_sha256=revision if patched else _EXPECTED_HASHES[revision],
                      message='Verified 1,440-slot client executable.' if patched else '720-slot client: apply the matching 1,440-slot executable patch before entering this Custom server.')
        if record:
            result.update(backup_exists=True, backup_path=record['backup'],
                          can_restore=patched and revision in record['accepted'])
        require_stopped(engine)
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        result.update(warning=str(error), can_apply=False, can_restore=False)
    return result


def mutate(engine, operation, args):
    with _LOCK:
        require_stopped(engine)
        _cancel(engine)
        if operation not in ('client_spellbook_apply', 'client_spellbook_restore'):
            raise Refusal('Unknown spellbook compatibility operation')
        _, path, identity, raw, record, patched = _inspect(engine)
        revision = connection.sha(raw)
        if args.get('revision') != revision:
            raise Refusal('The client executable changed. Refresh compatibility before continuing.')
        if operation == 'client_spellbook_apply':
            if args.get('confirm_apply') is not True:
                raise Refusal('Confirm the 1,440-slot client compatibility patch before applying it')
            if patched:
                return dict(status(engine), message='The 1,440-slot executable patch is already verified; no files or backups changed.')
            updated = build(raw)
            _retain_base_variant(engine, path, identity, raw, record)
            retained = connection.checked_backup(engine, KIND, path, identity, raw, updated)
            # Commit recovery directory entries before publishing the exe. A
            # power loss must not leave a new executable without its original.
            saved = connection.confined(engine, retained['backup'])
            for directory in (saved.parent, saved.parent.parent, saved.parent.parent.parent):
                _fsync_directory(directory)
            message = '1,440-slot spellbook and 4 GB address flag applied. Protected original retained. Rebuild and deploy the matching Custom dinput8.dll before entering world.'
        else:
            if args.get('confirm_restore') is not True:
                raise Refusal('Restoring a 720-slot executable is incompatible with a 1,440-slot server. Confirm restoration explicitly.')
            if record is None:
                raise Refusal('No protected pre-spellbook executable is available')
            if revision == record['original_sha256']:
                return dict(status(engine), message='The protected original executable is already restored.')
            if revision not in record['accepted']:
                raise Refusal('The executable changed outside the launcher; restoration was refused')
            updated = connection.read(connection.confined(engine, record['backup']), BASE_SIZE)
            if not _base_supported(updated):
                raise Refusal('The protected executable does not match the verified original')
            message = 'Protected pre-spellbook executable restored. It cannot enter a 1,440-slot Custom server; reapply compatibility before playing there.'
        # Recheck identity, exact bytes and all process leases after building and
        # journaling, immediately before an atomic replacement.
        current_root, executable, current_identity = connection.local(engine)
        current_path = connection.lookup(current_root, executable)
        if current_identity != identity or current_path != path or connection.sha(connection.read(current_path, PATCHED_SIZE)) != revision:
            raise Refusal('The client changed during patch preparation; no executable was replaced')
        require_stopped(engine)
        _cancel(engine)
        mode = stat.S_IMODE(path.stat().st_mode)
        connection.atomic(path, updated, mode)
        _fsync_directory(path.parent)
        if connection.sha(connection.read(path, PATCHED_SIZE)) != connection.sha(updated):
            raise Refusal('Executable verification failed after atomic replacement; the protected original remains available')
        return dict(status(engine), message=message)
