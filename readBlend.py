#!/usr/bin/env python3

"""
Program to interpret a .blend file
"""

import sys
from BinFileUtils import getInt, getUint, getFloat, getDouble
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
        if len(bf.otherImages) > 0:
            for (nm,img) in bf.otherImages:
                print(f'Found image, width = {img.width}, height = {img.height}, saved as "{nm}.png"')
                img.save(nm + ".png")
        rds = bf.getRenderData()
        print("Render data:")
        for rd in rds:
            print(f'\tstart frame {rd.startFrame} end frame {rd.endFrame} scene "{rd.sceneName}"')
        unprocessed = 0
        for h in bhs:
            if not h['processed']:
                unprocessed += 1
                print(f'unprocessed block oldPointer = 0x{h["oldPointer"]:016x}')
        if unprocessed > 0: print(f'{unprocessed} unprocessed blocks')
        for h in bhs:
            bf.dumpBlockHeader(h)

class Pointer(int):
    # convenience class to format a pointer for printing
    def __str__(self):
        return f'0x{self:016x}'
    def __repr__(self):
        return f'0x{self:016x}'
    def pointsTo(self, ref):
        self.pointedTo = ref

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
        mtype: a type name, e.g. "char" or "IDProperty"
        name: a variable name, e.g. "*curl", "drw_corners[2][4][2]"
        dimensions: a tuple of array dimensions, e.g. (2,4,2) for the
            drw_corners example above. Could be empty.
        isSimpleType: True if type is not a structure, e.g. "char" or "int"
        isPointer: True if the member is a pointer
        value: either a single integer, floating point or string value, a
            Struct, or a list. Interpretation depends on type and dimensions.
        parentStruct: link to containing struct
    """
    def __init__(self, mtype, name, dimensions, isSimpleType, isPointer, pstruct):
        self.mtype = mtype
        self.name = name
        self.dimensions = dimensions
        self.isSimpleType = isSimpleType
        self.isPointer = isPointer
        self.value = None
        self.parentStruct = pstruct

class Struct:
    """
    Contents of a structure found in a .blend file.
    The public members of a Struct are:
    stype - the C name of the struct type
    name - the variable name of this struct, if it is inside another struct
    block - the containing block for this struct
    members - a list of StructMember objects.
    parentMemeber - for structs that are nested in other structs as the value
       of a StructMember
    """
    def __init__(self, block, stype, name = '', parentMember = None):
        self.block = block
        self.stype = stype
        self.name = name
        self.members = []
        self.parentMember = parentMember

class BlenderFile:
    """
    This class reads and decodes a .blend file and saves the contents.
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
    
    def __init__(self, infile):
        self.__f = infile
        self.__fileHeader = {}
        self.__blockHeaders = []
        self.__headersByType = {}
        self.__headersByAddress = {}
        self.__thumbnailImage = None
        self.__renderData = []
        self.otherImages = [] # each list element is a (name, Image) tuple
    
    def processFile(self):
        self.__verifyFileHeader(self.__f)
        self.__saveBlockHeaders(self.__f)
        self.__processBlockData(self.__f)
        self.__fixupBlocks()
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
            references      pointers that point to this block
            memberSpecs     for ad-hoc structures (i.e. not in the structure DNA), a list
                            of (type, name) tuples for the structure members
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
        # quickrefs are strings consisting of the struct name, a "|" char, and the
        # member type and member name separated by a space.
        # referringMembers is a list of StructureMember objects.
        emptyrefs = {'quickRefs' : set(), 'referringMembers' : []}
        return {'blockCode' : code, 'blockLength' : length, 'oldPointer' : oldPointer,
            'structCode' : structCode, 'numberOfStructs' : numStructs, 'references' : emptyrefs,
            'memberSpecs' : []}

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

    def __getSingleValue(self, mtype, name, isSimpleType, dimensions, isPointer, smember):
        """
        Creates a simple value from raw data
        """
        f = self.__f # file object
        if isPointer:
            # make a pointer
            hdr = self.getFileHeader()
            psize = hdr['pointerSize']
            ptr = Pointer(getUint(f.read(psize)))
            # check for blocks referred to by this pointer
            hdrs = self.getHeadersByAddress()
            b = hdrs.get(ptr)
            if b:
                stype = smember.parentStruct.stype
                ptr.pointsTo(b)
                # add a reference to this pointer to the destination block
                b['references']['quickRefs'].add(stype + '|' + mtype + ' ' + name)
                b['references']['referringMembers'].append(smember)
            return ptr
            
        if not isSimpleType:
            # find enclosing block
            parent = smember.parentStruct
            while parent:
                if parent.block:
                    break
                parent = parent.parentStruct
            return self.__buildStruct(mtype, parent.block, name, parentMember = smember) # value is another struct
        if mtype == 'char':
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
        elif mtype == 'uchar':
            return getUint(f.read(1))
        elif mtype == 'short':
            return getInt(f.read(2))
        elif mtype == 'ushort':
            return getUint(f.read(2))
        elif mtype == 'int' or type == 'long':
            return getInt(f.read(4))
        elif mtype == 'ulong':
            return getUint(f.read(4))
        elif mtype == 'int64_t':
            return getInt(f.read(8))
        elif mtype == 'uint64_t':
            return getInt(f.read(8))
        elif mtype == 'float':
            return getFloat(f.read(4))
        elif mtype == 'double':
            return getDouble(f.read(8))
        else:
            return None

    def __getArrayValue(self, mtype, name, isSimpleType, dimensions, isPointer, smember):
        """
        Creates a (possibly nested) list of single values
        """
        f = self.__f # file object
        vlist = []
        for idx in range(0, dimensions[0]):
            if len(dimensions) == 1:
                # get single values
                value = self.__getSingleValue(mtype, name, isSimpleType, dimensions, isPointer, smember)
            else:
                value = self.__getArrayValue(mtype, name, isSimpleType, dimensions[1:], isPointer, smember)
            vlist.append(value)
        return vlist
    
    def __buildStruct(self, stype, block, mname = '', mspecs = [], parentMember = None):
        # stype - struct type string, really the C name of the struct
        # block - containing block
        # mname - member name if inside another struct (top-level structs don't have one)
        # mspecs - a list of (type, name) tuples that describe the structure when
        #           a valid structure type is not available
        # parentMemeber - for structs that are nested in other structs as the value
        #   of a StructMember
        outStruct = Struct(block, stype, mname)
        f = self.__f
        daspecs = []
        if len(mspecs) == 0:
            dna = self.getDNA()
            names = dna.getNames() # get the SDNA info
            types = dna.getTypes()
            sstructs = dna.getStructs()
            structCodesByType = dna.getStructCodesByType()
            daStruct = sstructs[structCodesByType[stype]]
            for spec in daStruct[1]:
                daspecs.append((types[spec[0]], names[spec[1]]))
        else:
                outStruct.stype = '(generated)'
                daspecs = mspecs
        for (mtype, name) in daspecs:
            isSimpleType = (mtype in self.basicTypes)
           # parse the member name
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

                outMember = StructMember(mtype, name, dimensions, isSimpleType, isPointer, outStruct)

                if len(dimensions) == 0 or (len(dimensions) == 1 and mtype == 'char'):
                    # we have a single value
                    value = self.__getSingleValue(mtype, name, isSimpleType, dimensions, isPointer, outMember)
                else:
                    # we have an array:
                    value = self.__getArrayValue(mtype, name, isSimpleType, dimensions, isPointer, outMember)
                
                outMember.value = value
                outStruct.members.append(outMember)
            else:
                damatch2 = self.pat2.match(name)
                if damatch2:
                    # we have a pointer to a function - its value is a 4 or 8-byte integer
                    value = self.__getSingleValue(mtype, name, isSimpleType, dimensions, True, outMember)
                    outMember.value = value
                    outMember.isPointer = True
                    outStruct.members.append(outMember)
                else:
                    print(f'WARNING: "{name} {type}" was not parsed')

        if parentMember:
            outStruct.parentMember = parentMember
        return outStruct
            
    def __processBlockData(self, f):
        """
        Iterates over the list of block headers and parses the data for each block.
        """
        dna = self.__dna
        types = dna.getTypes() if dna else None
        structs = dna.getStructs() if dna else None
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
                daspecs = block['memberSpecs']
                if (scode == 0 and len(daspecs) == 0) or not dna:
                    continue # can't process
                else:
                    dastruct = structs[scode]
                    stype = types[dastruct[0]]
                    slist = []
                    for idx in range(0, block['numberOfStructs']):
                        slist.append(self.__buildStruct(stype, block, mspecs=daspecs))
                    block['structData'] = slist
                    block['processed'] = True

    def __fixupBlocks(self):
        """
        Looks for blocks that haven't been processed and tries to guess their data format
        based on how they are referenced by other blocks
        """
        pts = self.getFileHeader()['pointerSize']
        for hdr in self.getBlockHeaders():
            if hdr['processed'] or len(hdr['references']) == 0:
                continue
            blockLength = hdr['blockLength']
            refs = hdr['references']['quickRefs']
            if 'Paint|PaintToolSlot *tool_slots' in refs:
                # see how many pointers we have
                numptr = blockLength//pts
                hdr['memberSpecs'] = [('PaintToolSlot','*tool_slots[' + str(numptr) + ']')]
            elif 'Object|Material **mat' in refs:
                if blockLength == pts:
                    hdr['memberSpecs'] = [('Material','**mat')]
            elif 'Mesh|Material **mat' in refs:
                if blockLength == pts:
                    hdr['memberSpecs'] = [('Material','**mat')]
            elif 'Object|char *matbits' in refs:
                # this is a boolean byte field
                hdr['memberSpecs'] = [('uchar','matbits[' + str(blockLength) + ']')]
            elif 'ConsoleLine|char *line' in refs:
                hdr['memberSpecs'] = [('char',f'line[{blockLength}]')]
            elif 'CustomDataLayer|void *data' in refs:
                # get the type field from the CustomDataLayer parent struct
                smembers = hdr['references']['referringMembers']
                cdtype = 1000
                for mem in smembers:
                    ps = mem.parentStruct
                    if ps.stype == 'CustomDataLayer':
                        for pm in ps.members:
                            if pm.mtype != 'int':
                                continue
                            if pm.name == 'type':
                                cdtype = pm.value
                                break
                        break
                if cdtype == 34:
                    # CD_PAINT_MASK, an array of floats: see DNA_customdata_types.h
                    numfloats = blockLength//4
                    hdr['memberSpecs'] = [('float','paintMask[' + str(numfloats) + ']')]
            elif 'PreviewImage|int *rect[2]' in refs:
                # get the w[2], h[2], and rect[2] values from PreviewImage
                imWidth = []
                imHeight = []
                imData = []
                smembers = hdr['references']['referringMembers']
                for mem in smembers:
                    ps = mem.parentStruct
                    if ps.stype != 'PreviewImage':
                        continue
                    for pm in ps.members:
                        if pm.mtype != 'int':
                            continue
                        if pm.name == 'w[2]':
                            imWidth.append(pm.value[0])
                            imWidth.append(pm.value[1])
                        elif pm.name == 'h[2]':
                            imHeight.append(pm.value[0])
                            imHeight.append(pm.value[1])
                        elif pm.name == '*rect[2]':
                            imData.append(pm.value[0])
                            imData.append(pm.value[1])
                    break
                # identify which of the two images we are referring to
                if len(imData) > 0:
                    index = -1
                    if hdr['oldPointer'] == imData[0]:
                        index = 0
                    elif hdr['oldPointer'] == imData[1]:
                        index = 1
                    if index >= 0:
                        # Make an image and name it with the pointer
                        width = imWidth[index]
                        height = imHeight[index]
                        f = self.__f
                        f.seek(hdr['filePos'])
                        ourImage = Image.frombytes('RGBA',(width, height),f.read(blockLength))
                        ourName = f'0x{hdr["oldPointer"]:016x}'
                        self.otherImages.append((ourName, ourImage))
                        # make a Struct to describe the image we made
                        myStruct = Struct(hdr, 'rgbaImage')
                        sm = StructMember('int', 'width', [], True, False, myStruct)
                        sm.value = width
                        myStruct.members.append(sm)
                        sm = StructMember('int', 'height', [], True, False, myStruct)
                        sm.value = height
                        myStruct.members.append(sm)
                        nameLen = len(ourName)
                        sm = StructMember('char', f'name[{nameLen}]', [nameLen], True, False, myStruct)
                        sm.value = ourName
                        myStruct.members.append(sm)
                        hdr['structData'] = [myStruct]
                hdr['processed'] = True # nothing more to do
            elif 'IDPropertyData|void *pointer' in refs:
                # get the type and subtype from the top-level struct
                smembers = hdr['references']['referringMembers']
                for mem in smembers:
                    ps = mem.parentStruct
                    if ps.stype == 'IDPropertyData':
                        topblock = ps.block
                        break
                if topblock: #and tops.stype == 'IDProperty':
                    tops = topblock['structData'][0]
                    if tops.stype == 'IDProperty':
                        idttype = idsubtype = -1
                        for mbr in tops.members:
                            if mbr.mtype != 'char':
                                continue
                            if mbr.name == 'type':
                                idtype = mbr.value
                            if mbr.name == 'subtype':
                                idsubtype = mbr.value
                        if idtype == 0 and idsubtype == 0:
                            # data is a string
                            hdr['memberSpecs'] = [('char',f'stringData[{blockLength}]')]
            elif 'bNodeSocket|void *default_value' in refs:
                # we need the type of the bNodeSocket to interpret the data
                smembers = hdr['references']['referringMembers']
                for mem in smembers:
                    ps = mem.parentStruct
                    if ps.stype == 'bNodeSocket':
                        # look for the type
                        for pm in ps.members:
                            if pm.mtype == 'short' and pm.name == 'type':
                                scByType = self.getDNA().getStructCodesByType()
                                bntype = pm.value
                                if bntype == 0: # SOCK_FLOAT
                                    hdr['structCode'] = scByType['bNodeSocketValueFloat']
                                elif bntype == 1: # SOCK_VECTOR
                                    hdr['structCode'] = scByType['bNodeSocketValueVector']
                                elif bntype == 2: # SOCK_RGBA
                                   hdr['structCode'] = scByType['bNodeSocketValueRGBA']
                                elif bntype == 3: # SOCK_SHADER
                                    pass # don't know how to interpret
                                elif bntype == 4: # SOCK_BOOLEAN
                                    hdr['structCode'] = scByType['bNodeSocketValueBoolean']
                                # type 5, SOCK_MESH, is deprecated
                                elif bntype == 6: # SOCK_INT
                                    hdr['structCode'] = scByType['bNodeSocketValueInt']
                                elif bntype == 7: # SOCK_STRING
                                    hdr['structCode'] = scByType['bNodeSocketValueString']
                                break
    
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
            refs = data['references']['quickRefs']
            if len(refs) > 0:
                print('References to this block:')
                for sm in refs:
                    print(sm)
            print()
    
    def dumpBlockData(self, structList, tabLevel = ''):
        # StructMember(mtype, name, dimensions, isSimpleType, isPointer, value)
        for s in structList:
            if isinstance(s, list):
                self.dumpBlockData(s, tabLevel)
                continue
            spec = s.stype
            if s.name:
                spec = spec + ' ' + s.name
            print(tabLevel + f'Struct {spec} ' + '{')
            for m in s.members:
                if m.isPointer or m.isSimpleType:
                    print(tabLevel + '\t' + m.mtype, m.name, '=', m.value)
                else:
                    self.dumpBlockData([m.value], tabLevel + '\t')
            print(tabLevel + '}')
        print()

if __name__ == '__main__':
    if len(sys.argv) >= 2:
        main(sys.argv[1])
    else:
        main()
