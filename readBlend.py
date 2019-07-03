#!/usr/bin/env python3

"""
Program to interpret a .blend file
"""

import sys
from BinFileUtils import getInt, getString, check4, padUp4
from readDNA import BlenderDNA
from blockCodes import FileBlockCodes
from PIL import Image

def main():
    with open('startup.blend', 'rb') as f:
        bf = BlenderFile(f)
        bf.processFile()
        bhs = bf.getBlockHeaders()
        print(bf.getFileHeader())
        print(f'Found {len(bhs)} header blocks (not including end block)')
        for h in bhs:
            bf.dumpBlockHeader(h)
        timg = bf.getThumbnail()
        if timg:
            timg.save('startup.png')

class BlenderFile:
    def __init__(self, infile):
        self.__f = infile
        self.__fileHeader = {}
        self.__blockHeaders = []
        self.__headersByType = {}
        self.__headersByAddress = {}
        self.__thumbnailImage = None
    
    def processFile(self):
        self.__verifyFileHeader(self.__f)
        self.__saveBlockHeaders(self.__f)
        
    def getFileHeader(self):
        return self.__fileHeader
    
    def getBlockHeaders(self):
        return self.__blockHeaders
    
    def getHeadersByType(self):
        return self.__headersByType
    
    def getHeadersByAddress(self):
        return self.__headersByAddress
    
    def getThumbnail(self):
        return self.__thumbnailImage
    
    def __verifyFileHeader(self,f):
        """
        This function checks the .blend file header for proper formatting snd
        saves its data in a dictionary.
        
        Dictionary key      value
        --------------      -----
        pointerSize         4 or 8 (bytes)
        byteOrder           "little" or "big" (-endian)
        version             Blender version as integer, e.g. 280 = 2.80
        """
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

    def __saveBlockHeaders(self, f):
        """
        Saves block headers in a list. Each block header is a dictionary with these keys:
            blockCode       a string of 2 or 4 characters indicating the block type
            blockLength     length in bytes of the data following the block header
            oldPointer      memory address of block when it was saved
            structCode      index into the array of structure definitions read from the
                            structure DNA. The data in the block conforms to this structure.
            numberOfStructs the data consists of this number of consecutive structs
            filePos         file offset to block's data
        """
        while True:
            data = self.__getBlockHeader(f)
            if data == None: break
            code = data["blockCode"]
            if code == 'ENDB': break
            filePos = f.tell()
            data['filePos'] = filePos
            if code == 'DNA1':
                # parse and save the structure DNA
                self.__dna = BlenderDNA(f)
                self.__dna.processDNA()
            else:
                # skip over the block data
                f.seek(filePos + data['blockLength'])
            # populate dictionaries
            if code not in self.__headersByType:
                self.__headersByType[code] = []
            self.__headersByType[code].append(data)
            self.__headersByAddress[data['oldPointer']] = data
            self.__blockHeaders.append(data)
            filePos = f.tell()
    
    def dumpBlockHeader(self, data):
            code = data["blockCode"]
            fbcs = FileBlockCodes.fileBlockCodes
            print(f'code = {code} {fbcs[code]}')
            print(f'length = {data["blockLength"]}')
            print(f'old pointer = {data["oldPointer"]:016x}')
            print(f'struct code = {data["structCode"]}')
            print(f'number of structs = {data["numberOfStructs"]}')
            print()

if __name__ == '__main__': main()
