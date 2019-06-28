#!/usr/bin/env python3

"""
Program to interpret a .blend file
"""

import sys
from BinFileUtils import getInt, getString, check4, padUp4
from readDNA import BlenderDNA
from blockCodes import FileBlockCodes

def main():
    with open('startup.blend', 'rb') as f:
        bf = BlenderFile(f)
        bf.processFile()
        print(bf.getFileHeader())

class BlenderFile:
    def __init__(self, infile):
        self.__f = infile
        self.__fileHeader = {}
        self.__blockHeaders = []
        self.__headersByType = {}
        self.__headersByAddress = {}
    
    def processFile(self):
        self.__verifyFileHeader(self.__f)
        self.__saveBlockHeaders(self.__f, self.__blockHeaders)
        
    def getFileHeader(self):
        return self.__fileHeader
    
    def getBlockHeaders(self):
        return self.__blockHeaders
    
    def getHeadersByType(self):
        return self.__headersByType
    
    def getHeadersByAddress(self):
        return self.__headersByAddress

    def __verifyFileHeader(self,f):
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
        if pointerSizeCode == '_':
            pointerSize = 4
        else:
            pointerSize = 8
        #print(f'Pointer size is {pointerSize} bytes')
        self.__fileHeader['pointerSize'] = pointerSize
        # 9th byte must be either 'V' or 'v'
        endianCode = header[8]
        if endianCode != 'V' and endianCode != 'v':
            print(f'ERROR: Expected "V" or "v" in 8th byte of file, got "{endianCode}"')
            return
        byteorder = 'little' if endianCode == 'v' else 'big'
        if byteorder != sys.byteorder:
            print(f'ERROR: File byte order is "{byteorder}", system expects "{sys.byteorder}"')
            return 
        #print(f'Byte order is {byteorder}-endian',sep='')
        self.__fileHeader['byteOrder'] = byteorder
        # bytes 10-12 are the version number in ASCII
        versionStr = header[9:12]
        try:
            version = int(versionStr)
        except ValueError:
            print(f'ERROR: Expected valid number in bytes 10-12 of file, got "{versionStr}"')
            return
        #print(f'version is {version}')
        self.__fileHeader['version'] = version

    def __getBlockHeader(self, f):
        pointerSize = self.__fileHeader['pointerSize']
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

    """
    Saves block headers in a list. Each block header is a dictionary with these keys:
        blockCode       a string of 2 or 4 characters indicating the block type
        blockLength     length in bytes of the data following the block header
        oldPointer      memory address of block when it was saved
        structCode      index into the array of structure definitions read from the
                        structure DNA. The data in the block conforms to this structure.
        numberOfStructs the data consists of this number of consecutive structs
        filePos         not in the .blend file; generated during reading
    """
    def __saveBlockHeaders(self, f, blist):
        blist = []
        endCode = 'ENDB'
        filePos = 0
        while True:
            data = self.__getBlockHeader(f)
            if data == None: break
            if data['blockCode'] == endCode: break
            #############
            # TEMPORARY #
            #############
            if data['blockCode'] == 'TEST':
                curPos = f.tell()
                imgBlockData = f.read(data['blockLength'])
                self.__saveImageAsPNG(imgBlockData)
                f.seek(curPos)
            #################
            # END TEMPORARY #
            #################
            data['filePos'] = filePos
            # populate dictionaries
            code = data['blockCode']
            if code not in self.__headersByType:
                self.__headersByType[code] = []
            self.__headersByType[code].append(data)
            self.__headersByAddress[data['oldPointer']] = data
            filePos = f.tell() + data["blockLength"]
            f.seek(filePos)
    
            blist.append(data)
        #print(f'Found {len(blist)} header blocks (not including end block)')
        for h in blist:
            self.__dumpBlockHeader(h)
    
    def __dumpBlockHeader(self, data):
            code = data["blockCode"]
            fbcs = FileBlockCodes.fileBlockCodes
            print(f'code = {code} {fbcs[code]}')
            print(f'length = {data["blockLength"]}')
            print(f'old pointer = {data["oldPointer"]:016x}')
            print(f'struct code = {data["structCode"]}')
            print(f'number of structs = {data["numberOfStructs"]}')
            print()
    
    def __saveImageAsPNG(self, data):
        # Data starts with two integers, the width and height of the image
        width = getInt(data[0:4])
        height = getInt(data[4:8])
        from PIL import Image
        pngImg = Image.frombytes('RGBA',(width, height),data[8:])
        pngImg.save('thumbnail.png')

if __name__ == '__main__': main()
