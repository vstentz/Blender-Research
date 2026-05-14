import struct
import sys
import os
import compression.zstd as zstd
from collections import namedtuple

#####################
# container classes #
#####################
FileHeader = namedtuple('FileHeader', ['pointerSize', 'endianType',\
                        'blenderVersion', 'headerSize', 'blenderFileVersion'])
BlockHeader = namedtuple('BlockHeader',['code', 'len', 'oldp', 'SDNAnr',\
                                         'number', 'foffset'])
####################
# Global variables #
####################
BlendFileHeader = None
AllBlocks = []
AllBlocksByType = {}
AllBlocksByOldp = {}

########################################
# Custom exceptions for error handling #
########################################
class BadMagicStringError(Exception):
    """Raise this error when the file starts with anything but BLENDER"""
    def __init__(self, magic, message='ERROR: File must start with BLENDER'):
        self.magic = magic
        self.message = message
        super().__init__(self.message)
    
    def __str__(self):
        return f'{self.message}: found {self.magic}'

class BadVersionNumberError(Exception):
    """Raise this error when a version field is not as expected"""
    def __init__(self, numStr, expectedNumStr,\
                  message='ERROR: Invalid version number'):
        self.numStr = numStr
        self.message = message
        self.expextecNumStr = expectedNumStr
        super().__init__(self.message)
    
    def __str__(self):
        return f'{self.message}: expected {self.expectedNumStr}, found {self.numStr}'

class InvalidNumberError(Exception):
    """Raise this error when a field is not a number"""
    def __init__(self, numStr, message='ERROR: Invalid numeric field'):
        self.numStr = numStr
        self.message = message
        super().__init__(self.message)
    
    def __str__(self):
        return f'{self.message}: expected a number, found "{self.numStr}"'

class BadEndianCodeError(Exception):
    """Raise this error when the header endian type is invalid"""
    def __init__(self, endian, expectedEndian,\
                 message='ERROR: Bad endian type'):
        self.endian = endian
        self.expectedEndian = expectedEndian
        self.message = message
        super().__init__(self.message)
    
    def __str__(self):
        return f'{self.message}: expected {self.expectedEndian},\
              found "{self.endian}"'
    
class InvalidHeaderSizeError(Exception):
    """Raise this error when the file header size is invalid"""
    def __init__(self, size, message='ERROR: Invalid file header size'):
        self.size = size
        self.message = message
        super().__init__(self.message)
    
    def __str__(self):
        return f'{self.message}: expected 17, found {self.size}'
    
class InvalidPointerSizeError(Exception):
    """Raise this error when the pointer size code is invalid"""
    def __init__(self, size, message='ERROR: Invalid pointer size code'):
        self.size = size
        self.message = message
        super().__init__(self.message)
    
    def __str__(self):
        return f'{self.message}: expected "-", found "{self.size}"'

####################
# Helper functions #
####################    
def isFileCompressed(fname):
    """See if this file is compressed with ZSTD by reading the first four bytes
    and looking for a magic number. There are two possible values.
    Reference: BLI_file_magic_is_zstd in blenloader/intern/readfile.cc
    """
    with open(fname, 'rb') as f:
        data = f.read(4)
        # unpack() always returns a tuple. In this case the tuple has only one
        # element, an integer.
        magic = struct.unpack('=I', data)[0]
        if magic == 0xFD2FB528 or magic == 0x0184D2A5:
            return True
        else:
            return False

def updateGlobals(header):
    AllBlocks.append(header)
    code = header.code
    if code not in AllBlocksByType:
        AllBlocksByType[code] = []
    AllBlocksByType[code].append(header)
    oldp = header.oldp
    AllBlocksByOldp[oldp] = header

def traverseBlocks(f, hdr):
    # block layout varies with ptr size, new vs. legacy
    if hdr.pointerSize == 4:
        # headers are 20 bytes long
        while True:
            data = f.read(4)
            if not data:
                break
            code = struct.unpack('=4s', data)[0].decode('utf-8')
            data = f.read(20-4)
            (len,oldp,SDNAnr,number) = struct.unpack('=iIii', data)
            header = BlockHeader(code,len,oldp,SDNAnr,number,f.tell())
            updateGlobals(header)
            f.seek(len, 1)
    else:
        if hdr.blenderFileVersion:
            # headers are 32 bytes long
            while True:
                data = f.read(4)
                if not data:
                    break
                code = struct.unpack('=4s', data)[0].decode('utf-8')
                data = f.read(32-4)
                (SDNAnr,oldp,len,number) = struct.unpack('=iQqq', data)
                header = BlockHeader(code,len,oldp,SDNAnr,number,f.tell())
                updateGlobals(header)
                f.seek(len, 1)
        else:
            # headers are 24 bytes long
            while True:
                data = f.read(4)
                if not data:
                    break
                code = struct.unpack('=4s', data)[0].decode('utf-8')
                data = f.read(24-4)
                (len,oldp,SDNAnr,number) = struct.unpack('=iQii', data)
                header = BlockHeader(code,len,oldp,SDNAnr,number,f.tell())
                updateGlobals(header)
                f.seek(len, 1)

def printFileHeader(hdr):
    print(f"""
Pointer size = {hdr.pointerSize}
Endian type = {hdr.endianType}
Blender version = {hdr.blenderVersion}
Header size = {hdr.headerSize}""")
    if hdr.blenderFileVersion:
        print(f'Blender file version = {hdr.blenderFileVersion}')


def parseSDNA(f):
    # find the file offset for the SDNA bock
    sdnaHdr = AllBlocksByType['DNA1'][0]
    if not sdnaHdr:
        raise Exception('No DNA found, aborting')
    f.seek(sdnaHdr.foffset, 0)
    # check for 'SDNA'
    data = f.read(4)
    sdnaStr = struct.unpack('=4s', data)[0].decode('utf-8')
    if sdnaStr != 'SDNA':
        raise Exception(f'ERROR: Expected "SDNA", found "{sdnaStr}"')
    # check for 'NAME'
    data = f.read(4)
    sdnaStr = struct.unpack('=4s', data)[0].decode('utf-8')
    if sdnaStr != 'NAME':
        raise Exception(f'ERROR: Expected "NAME", found "{sdnaStr}"')
    # get the number of name strings
    data = f.read(4)
    numNames = struct.unpack('=i', data)[0]
    print(f'Found {numNames} name strings')
    # read the name strings
    namesArray = []
    for j in range(numNames):
        tname = bytearray()
        for i in range(256): # safety factor
            data = f.read(1)
            if not data:
                raise Exception('Premature end of file while reading names')
            if data[0] == 0:
                break
            tname.append(data[0])
        namesArray.append(tname.decode())
    
    # skip characters until we find a 'T'
    while True:
        data = f.read(1)
        if not data:
            raise Exception('Premature end of file while looking for TYPE')
        if data[0] == 84:
            break

    # see if the next 3 chars are 'YPE'
    data = f.read(3)
    sdnaStr = struct.unpack('=3s', data)[0].decode('utf-8')
    if sdnaStr != 'YPE':
        raise Exception(f'Looking for TYPE, found T{sdnaStr}')
    
    # get the number of type strings
    data = f.read(4)
    numTypes = struct.unpack('=i', data)[0]
    print(f'Found {numTypes} type strings')
    # read the type strings
    typesArray = []
    for j in range(numTypes):
        tname = bytearray()
        for i in range(256): # safety factor
            data = f.read(1)
            if not data:
                raise Exception('Premature end of file while reading types')
            if data[0] == 0:
                break
            tname.append(data[0])
        typesArray.append(tname.decode())

    # skip characters until we find a 'T'
    while True:
        data = f.read(1)
        if not data:
            raise Exception('Premature end of file while looking for TLEN')
        if data[0] == 84:
            break

    # see if the next 3 chars are 'LEN'
    data = f.read(3)
    sdnaStr = struct.unpack('=3s', data)[0].decode('utf-8')
    if sdnaStr != 'LEN':
        raise Exception(f'Looking for TLEN, found T{sdnaStr}')
    
    # read the type lengths. they are short integers, one
    # for each type
    typeLengths = []
    for j in range(numTypes):
        data = f.read(2)
        if not data:
            raise Exception('Premature end of file while reading type lengths')
        tlen = struct.unpack('=h', data)[0]
        typeLengths.append(tlen)

def parseBlendFile(f):
    try:
        verifyFileHeader(f)
        printFileHeader(BlendFileHeader)   
        traverseBlocks(f, BlendFileHeader)
        print('Block type counts')
        for type, blist in AllBlocksByType.items():
            print(f'{type} {len(blist)}')
        print('');
        parseSDNA(f)
    except Exception as err:
        print(err)

def verifyFileHeader(f):
    global BlendFileHeader
    # read magic string
    data = f.read(7)
    magic = struct.unpack('=7s', data)[0].decode('utf-8')
    if magic != 'BLENDER':
        raise BadMagicStringError(magic)
    # check for legacy format - next character would be '-' or '_'
    data = f.read(1)
    pointerSizeCode = struct.unpack('=1s', data)[0].decode('utf-8')
    if pointerSizeCode == '-' or pointerSizeCode == '_':
        print('File header is legacy format')
        pointerSize = 8 if pointerSizeCode == '-' else 4
        # next char should be 'v' for little endian or 'V' for big
        data = f.read(1)
        endianCode = struct.unpack('=1s', data)[0].decode('utf-8')
        if endianCode == 'v' or endianCode == 'V':
            endianStr = 'little' if endianCode == 'v' else 'big'
        else:
            # invalid endian code
            raise BadEndianCodeError(endianStr, '"V" or "v"')
        # next three bytes are the blender version number
        data = f.read(3)
        versionStr = struct.unpack('=3s', data)[0].decode('utf-8')
        if not versionStr.isdigit():
            raise InvalidNumberError(versionStr,\
                             'ERROR: Invalid Blender version number')
        BlendFileHeader = FileHeader(pointerSize, endianStr, versionStr, 12, '')
    else:
        # could be new format
        # last byte and next byte are the header size
        data = f.read(1)
        sizeDigit2 = struct.unpack('=1s', data)[0].decode('utf-8')
        sizeDigits = pointerSizeCode + sizeDigit2
        if sizeDigits != '17':
            raise InvalidHeaderSizeError(sizeDigits)       
        print('File header is new format')
        # next char is pointer size, but only '-' (8) is allowed
        data = f.read(1)
        pointerSizeCode = struct.unpack('=1s', data)[0].decode('utf-8')
        if (pointerSizeCode != '-'):
            raise InvalidPointerSizeError(pointerSizeCode)
        # next two chars are the Blender file version number
        data = f.read(2)
        fileVersionStr = struct.unpack('=2s', data)[0].decode('utf-8')
        if not fileVersionStr.isdigit():
            raise InvalidNumberError(fileVersionStr,\
                             'Invalid Blender file version number')
        if fileVersionStr != '01':
            raise BadVersionNumberError(fileVersionStr, '01',\
                         'ERROR: Bad Blender file version number')
        # next char is the endian code: must have 'v' (little)
        data = f.read(1)
        endianCode = struct.unpack('=1s', data)[0].decode('utf-8')
        if endianCode == 'v':
            endianStr = 'little'
        else:
            # invalid endian code
            raise BadEndianCodeError(endianStr, '"v"')
        # finally, we have 4 characters for the Blender version
        data = f.read(4)
        versionStr = struct.unpack('=4s', data)[0].decode('utf-8')
        if not versionStr.isdigit():
            raise InvalidNumberError(versionStr,\
                             'ERROR: Invalid Blender version number')
        BlendFileHeader = FileHeader(8, endianStr, versionStr, 17, fileVersionStr)

################
# Main program #
################
# Dumps a .blend file, which may be compressed by ZSTD
def main():
    if len(sys.argv) > 1:
        fileName = sys.argv[1]
    else:
        print("ERROR: No file name provided")
        exit()
    # generate output file name
    (baseName, _) = os.path.splitext(fileName)
    outFname = baseName + ".txt"

    isComp = isFileCompressed(fileName)
    if isComp:
        print(f'file "{fileName}" is compressed with ZSTD')
        with zstd.open(fileName) as fobj:
            parseBlendFile(fobj)
    else:
        print(f'file "{fileName}" is not compressed')
        with open(fileName, 'rb') as fobj:
            parseBlendFile(fobj)

    exit()

if __name__ == "__main__":    main()