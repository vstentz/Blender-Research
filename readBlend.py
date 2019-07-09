#!/usr/bin/env python3

"""
Program to interpret a .blend file
"""

import sys
from BinFileUtils import getInt, getUint, getFloat, getDouble, getString
from readDNA import BlenderDNA
from blockCodes import FileBlockCodes
from PIL import Image
from os.path import basename, splitext
import re

def main(bfile = 'startup.blend'):
    with open(bfile, 'rb') as f:
        bf = BlenderFile(f)
        bf.processFile()
        # d = bf.getDNA()
        # names = d.getNames()
        # types = d.getTypes()
        # structs = d.getStructs()
        # print(f'Found {len(names)} names, {len(types)} types, {len(structs)} structs')
        # for idx in range(0, len(structs)):
        #     print(f'Struct number {idx}')
        #     d.dumpStruct(names, types, structs[idx])
        bhs = bf.getBlockHeaders()
        print(bf.getFileHeader())
        print(f'Found {len(bhs)} header blocks (not including end block)')
        timg = bf.getThumbnail()
        if timg:
            (bname, fext) = splitext(basename(bfile))
            fname = bname + '.png'
            timg.save(fname)
            print(f'Found thumbnail image, width = {timg.width}, height = {timg.height}, saved as "{fname}"')
        rds = bf.getRenderData()
        print("Render data:")
        for rd in rds:
            print(f'\tstart frame {rd.startFrame} end frame {rd.endFrame} scene "{rd.sceneName}"')
            for h in bhs:
                bf.dumpBlockHeader(h)

class Pointer(int):
    # convenience class to format a pointer for printing
    def __str__(self):
        return f'0x{self:016x}'
    def __repr__(self):
        return f'0x{self:016x}'

class RenderData:
    """
    Container class for render data. Render data consists of:
    startFrame: start frame number
    endFrame: an end frame number
    sceneName: scene name string, up to 64 chars
    """
    pass

class StructMember:
    """
    Holds the description and data for one structure member.
    Attributes:
        type: a type name, e.g. "char" or "IDProperty"
        name: a variable name, e.g. "*curl", "drw_corners[2][4][2]"
        dimensions: a tuple of array dimensions, e.g. (2,4,2) for the
            drw_corners example above. Could be empty.
        isSimpleType: True if type is not a structure, e.g. "char" or "int"
        isPointer: True if the member is a pointer
        value: either a single integer, floating point or string value, a
            Struct, or a list. Interpretation depends on type and dimensions.
    """
    def __init__(self, type, name, dimensions, isSimpleType, isPointer, value):
        self.type = type
        self.name = name
        self.dimensions = dimensions
        self.isSimpleType = isSimpleType
        self.isPointer = isPointer
        self.value = value

class Struct:
    """
    Contents of a structure found in a .blend file.
    The public members of aStruct are:
    name - the C name of the struct type
    members - a list of StructMember objects.
    """
    basicTypes = frozenset([ # simple types found in Blender files
            'char',
            'uchar',
            'short',
            'ushort',
            'int',
            'long',
            'ulong',
            'float',
            'double',
            'int64_t',
            'uint64_t',
            'void'
        ]
    )
    # pat parses a typical member name, e.g. "*array[2][3]"
    pat = re.compile(r"(?P<ptr>[*]*)(?P<cname>\w+)(?P<cdim>(?:\[\d+\])+)?")
    # pat2 parses a function pointer, e.g. "(*func)()"
    pat2 = re.compile(r"(?P<fptr>\(\*\w+\))\(\)")

    def __getSingleValue(self, type, name, isSimpleType, dimensions, isPointer, bf, f):
        """
        Creates a simple value from raw data
        """
        if isPointer:
            # make a pointer
            hdr = bf.getFileHeader()
            psize = hdr['pointerSize']
            return Pointer(getUint(f.read(psize)))
        if not isSimpleType:
            return Struct(f, bf, type, name) # value is another struct
        if type == 'char':
            numDim = len(dimensions)
            if numDim == 0:
                return getInt(f.read(1))
            else:
                maxlen = dimensions[0]
                raw = f.read(maxlen)
                rs = raw
                nulidx = raw.find(b'\x00')
                if nulidx >= 0:
                    rs = raw[0:nulidx]
                try:
                    tstring = rs.decode()
                except UnicodeDecodeError:
                    return raw
                return tstring
        elif type == 'uchar':
            return getUint(f.read(1))
        elif type == 'short':
            return getInt(f.read(2))
        elif type == 'ushort':
            return getUint(f.read(2))
        elif type == 'int' or type == 'long':
            return getInt(f.read(4))
        elif type == 'ulong':
            return getUint(f.read(4))
        elif type == 'int64_t':
            return getInt(f.read(8))
        elif type == 'uint64_t':
            return getInt(f.read(8))
        elif type == 'float':
            return getFloat(f.read(4))
        elif type == 'double':
            return getDouble(f.read(8))
        else:
            return None

    def __getArrayValue(self, type, name, isSimpleType, dimensions, isPointer, bf, f):
        """
        Creates a (possibly nested) list of single values
        """
        vlist = []
        for idx in range(0, dimensions[0]):
            if len(dimensions) == 1:
                # get single values
                value = self.__getSingleValue(type, name, isSimpleType, dimensions, isPointer, bf, f)
            else:
                value = self.__getArrayValue(type, name, isSimpleType, dimensions[1:], isPointer, bf, f)
            vlist.append(value)
        return vlist

    def __init__(self, f, bf, type, name = ''):
        # f - File object pointing to block's raw data
        # bf - BlenderFile obect
        # type - struct type string
        # name - member name if inside another struct (top-level structs don't have one)
        dna = bf.getDNA()
        names = dna.getNames() # get the SDNA info
        types = dna.getTypes()
        sstructs = dna.getStructs()
        structCodesByType = dna.getStructCodesByType()
        daStruct = sstructs[structCodesByType[type]]
        self.type = type # really the C name of the struct
        self.name = name
        memCodes = daStruct[1] # list of structure member type/name codes
        members = [] # list of StructMember
        self.members = members
        for t_n in memCodes:
            type = types[t_n[0]]
            isSimpleType = (type in self.basicTypes)
            name = names[t_n[1]]
           # parse the member name and type
            damatch = self.pat.match(name)
            dimensions = []
            pointer = ''
            value = None
            if damatch:
                # check for a pointer
                pointer = damatch.group('ptr')
                isPointer = True if pointer else False

                # see if we have an array, possibly multi-dimensional
                cdim = damatch.group('cdim')
                if cdim:
                    # get the array dimensions as a list of integers
                    cdim = cdim[1:-1] # strip opening "[" and closing "]"
                    dims = cdim.split('][')
                    dimensions = [int(x) for x in dims]

                if len(dimensions) == 0 or (len(dimensions) == 1 and type == 'char'):
                    # we have a single value
                    value = self.__getSingleValue(type, name, isSimpleType, dimensions, isPointer, bf, f)
                else:
                    # we have an array:
                    value = self.__getArrayValue(type, name, isSimpleType, dimensions, isPointer, bf, f)
                members.append(StructMember(type, name, dimensions, isSimpleType, isPointer, value))
            else:
                damatch2 = self.pat2.match(name)
                if damatch2:
                    # we have a pointer to a function - its value is a 4 or 8-byte integer
                    value = self.__getSingleValue(type, name, isSimpleType, dimensions, True, bf, f)
                    members.append(StructMember(type, name, dimensions, isSimpleType, True, value))
                else:
                    print(f'WARNING: "{name} {type}" was not parsed')
               
class BlenderFile:
    def __init__(self, infile):
        self.__f = infile
        self.__fileHeader = {}
        self.__blockHeaders = []
        self.__headersByType = {}
        self.__headersByAddress = {}
        self.__thumbnailImage = None
        self.__renderData = []
    
    def processFile(self):
        self.__verifyFileHeader(self.__f)
        self.__saveBlockHeaders(self.__f)
        self.__processBlockData(self.__f)
        
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
    
    def getRenderData(self):
        return self.__renderData
    
    def getDNA(self):
        return self.__dna
    
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
        """
        Parses block headers and saves data to a dictionary. Dictionary keys:
            blockCode       a string of 2 or 4 characters indicating the block type
            blockLength     length in bytes of the data following the block header
            oldPointer      memory address of block when it was saved
            structCode      index into the array of structure definitions read from the
                            structure DNA. The data in the block conforms to this structure.
            numberOfStructs the data consists of this number of consecutive structs
            filePos         file offset to block's data
            structData      list of Struct objects that comprise the block's data
        """
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
        oldPointer = getUint(raw)
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
        Saves the block headers in a list. The SDNA data is processed in this
        loop, but the data in the other blocks is skipped over.
        """
        while True:
            data = self.__getBlockHeader(f)
            if data == None: break
            code = data["blockCode"]
            if code == 'ENDB': break
            data['processed'] = False # Data not yet parsed
            filePos = f.tell()
            data['filePos'] = filePos
            if code == 'DNA1':
                # parse and save the structure DNA
                self.__dna = BlenderDNA(f)
                self.__dna.processDNA()
                data['processed'] = True
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
            
    def __processBlockData(self, f):
        """
        Iterates over the list of block headers and parses the data for each block.
        """
        for block in self.__blockHeaders:
            if block['processed']:
                continue # already processed
            code = block['blockCode']
            dataLength = block['blockLength']
            f.seek(block['filePos'])
            if code == 'REND':
                # process the abbreviated render data
                for idx in range(0, block['numberOfStructs']):
                    sframe = getInt(f.read(4)) # start frame number
                    eframe = getInt(f.read(4)) # end frame number
                    scene = (f.read(64)).decode().rstrip('\0')
                    rd = RenderData()
                    rd.startFrame = sframe
                    rd.endFrame = eframe
                    rd.sceneName = scene
                    self.__renderData.append(rd)
                block['processed'] = True
            elif code == 'TEST':
                # The block data is a thumbnail image in RGBA format
                # Data starts with two integers, the width and height of the image
                width = getInt(f.read(4))
                height = getInt(f.read(4))
                self.__thumbnailImage = Image.frombytes('RGBA',(width, height),f.read(dataLength - 8))
                block['processed'] = True
            else:
                scode = block['structCode']
                dna = self.__dna
                if scode == 0 or not dna:
                    continue # can't process
                else:
                    types = dna.getTypes()
                    structs = dna.getStructs()
                    dastruct = structs[scode]
                    type = types[dastruct[0]]
                    slist = []
                    for idx in range(0, block['numberOfStructs']):
                        slist.append(Struct(f, self, type))
                    block['structData'] = slist
                    block['processed'] = True
    
    def dumpBlockHeader(self, data):
            code = data["blockCode"]
            fbcs = FileBlockCodes.fileBlockCodes
            print(f'code = {code} {fbcs[code]}')
            print(f'length = {data["blockLength"]}')
            print(f'old pointer = 0x{data["oldPointer"]:016x}')
            print(f'struct code = {data["structCode"]}')
            print(f'number of structs = {data["numberOfStructs"]}')
            if 'structData' in data:
                self.dumpBlockData(data['structData'])
            print()
    
    def dumpBlockData(self, structList, tabLevel = ''):
        # StructMember(type, name, dimensions, isSimpleType, isPointer, value)
        for s in structList:
            if isinstance(s, list):
                self.dumpBlockData(s, tabLevel)
                continue
            spec = s.type
            if s.name:
                spec = spec + ' ' + s.name
            print(tabLevel + f'Struct {spec} ' + '{')
            for m in s.members:
                if m.isPointer or m.isSimpleType:
                    print(tabLevel + '\t' + m.type, m.name, '=', m.value)
                else:
                    self.dumpBlockData([m.value], tabLevel + '\t')
            print(tabLevel + '}')
        print()

if __name__ == '__main__':
    if len(sys.argv) >= 2:
        main(sys.argv[1])
    else:
        main()
