#!/usr/bin/env python3

"""
Program to interpret a .blend file
"""

import sys
from BinFileUtils import getInt, getString, check4, padUp4

pointerSize = 0

def main():
    with open('startup.blend', 'rb') as f:
        verifyFileHeader(f)
        dumpBlockHeaders(f)

def verifyFileHeader(f):
    # Read 12-byte header
    header = f.read(12).decode()
    magic = header[:7]
    if magic != 'BLENDER':
        print(f'ERROR: Expected "BLENDER" at start of file, got "{magic}"')
        return
    # 8th byte must be either '_' or '-'
    pointerSizeCode = header[7]
    if pointerSizeCode != '-' and pointerSizeCode != '_':
        print(f'ERROR: Expected "_" or "-" in 8th byte of file, got "{pointerSizeCode}"')
        return
    global pointerSize
    if pointerSizeCode == '_':
        pointerSize = 4
    else:
        pointerSize = 8
    print(f'Pointer size is {pointerSize} bytes')
    # 9th byte must be either 'V' or 'v'
    endianCode = header[8]
    if endianCode != 'V' and endianCode != 'v':
        print(f'ERROR: Expected "V" or "v" in 8th byte of file, got "{endianCode}"')
        return
    byteorder = 'little' if endianCode == 'v' else 'big'
    if byteorder != sys.byteorder:
        print(f'ERROR: File byte order is "{byteorder}", system expects "{sys.byteorder}"')
        return 
    print(f'Byte order is {byteorder}-endian',sep='')
    # bytes 10-12 are the version number in ASCII
    versionStr = header[9:12]
    try:
        version = int(versionStr)
    except ValueError:
        print(f'ERROR: Expected valid number in bytes 10-12 of file, got "{versionStr}"')
        return
    print(f'version is {version}')

def getBlockHeader(f):
    # first 4 bytes are a block type code
    raw = f.read(4)
    if len(raw) != 4: return None
    code = raw.decode().rstrip('\0')
    # next 4 bytes are the length of data after the block
    raw = f.read(4)
    if len(raw) != 4: return None
    length = getInt(raw)
    # next 4 or 8 bytes are a pointer
    raw = f.read(pointerSize)
    if len(raw) != pointerSize: return None
    oldPointer = getInt(raw)
    # next 4 bytes are a structure code - need structure DNA to interpret
    raw = f.read(4)
    if len(raw) != 4: return None
    structCode = getInt(raw)
    # next 4 bytes are the number of structures in this block
    raw = f.read(4)
    if len(raw) != 4: return None
    numStructs = getInt(raw)
    return {'blockCode' : code, 'blockLength' : length, 'oldPointer' : oldPointer,
            'structCode' : structCode, 'numberOfStructs' : numStructs}

def dumpBlockHeaders(f):
    code = ''
    endCode = 'ENDB'
    while code != endCode:
        data = getBlockHeader(f)
        if data == None: break
        code = data['blockCode']
        print(f'code = {code}')
        print(f'length = {data["blockLength"]}')
        print(f'old pointer = {data["oldPointer"]:016x}')
        print(f'struct code = {data["structCode"]}')
        print(f'number of structs = {data["numberOfStructs"]}')
        print()
        f.seek(f.tell() + data["blockLength"])
        
    

if __name__ == '__main__': main()
