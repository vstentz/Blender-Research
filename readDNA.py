#!/usr/bin/env python3

"""
    This program reads a Blender binary "struct DNA" file
    Note: the basic types (i.e., not structures) and their lengths are
    char        1
    uchar       1
    short       2
    ushort      2
    int         4
    long        4
    ulong       4
    float       4
    double      8
    int64_t     8
    uint64_t    8
    void        0
"""
from BinFileUtils import getInt, getString, check4, padUp4 

def main():
        with open('sdna', 'rb') as f:
            d = BlenderDNA(f)
            d.processDNA()
            names = d.getNames()
            types = d.getTypes()
            for s in d.getStructs():
                d.dumpStruct(names, types, s)
            
class BlenderDNA:
    def __init__(self, infile):
        self.__allNames = []
        self.__allTypes = []
        self.__allTypeLengths = []
        self.__allStructs = []
        self.__f = infile
        
    def getNames(self):
        return self.__allNames
    
    def getTypes(self):
        return self.__allTypes
    
    def getTypeLengths(self):
        return self.__allTypeLengths
    
    def getStructs(self):
        return self.__allStructs
        
    def processDNA(self):
        # first 4 bytes must be string "SDNA"
        if check4(self.__f, 'SDNA') == None:
            return
    
        # get the NAME strings
        self.__allNames = self.__getStringBlock(self.__f, 'NAME')
        if self.__allNames == None or len(self.__allNames) == 0: return
        
        # seek to next 4-byte aligned position
        padUp4(self.__f)
        
        # get the TYPE strings
        self.__allTypes = self.__getStringBlock(self.__f, 'TYPE',
                        self.__DNA_struct_rename_legacy_hack_static_from_alias)
        if self.__allTypes == None or len(self.__allTypes) == 0: return
        padUp4(self.__f)
        
        # next 4 bytes must be "TLEN"
        if check4(self.__f,'TLEN') == None:
            return
    
        # following data is a sequence of 2-byte integers representing the
        # length (in bytes) of each type in __allTypes, in the same order.
        for idx in range(0, len(self.__allTypes)):
            theLen = getInt(self.__f.read(2))
            self.__allTypeLengths.append(theLen)
        padUp4(self.__f)
    
        # get the structure definitions
        self.__allStructs = self.__getStructures(self.__f)
        
    def __getStringBlock(self, f, type, postProc=None):
        """
        Loads a block of null-terminated strings into an array
        The block consists of a 4-character type string, e.g. NAME,
        followed by a 4-byte integer representing the count of strings,
        followed by the strings themselves.
        
        Arguments are the file stream and the type string. The function
        returns the strings in a list, or None if there was a problem.
        There is also an optional postProc function argument. This is a
        function which takes a string and returns an altered string.
        """
        # first 4 bytes must be the type
        if check4(f, type) == None:
            return None
        
        # next 4 bytes are an integer representing the total number of strings
        # of the given type
        typesLen = getInt(f.read(4))
    
        # fetch all the name strings and save
        allTypes = []
        for runningLen in range(0,typesLen):
            theString = getString(f)
            if postProc != None:
                theString = postProc(theString)
            allTypes.append(theString)
        
        return allTypes
    
    def __DNA_struct_rename_legacy_hack_static_from_alias(self, name):
        """
        DNA Compatibility Hack
        ======================
        Only keep this for compatibility: **NEVER ADD NEW STRINGS HERE**.
        The renaming here isn't complete, references to the old struct names
        are still included in DNA, now fixing these struct names properly
        breaks forward compatibility. Leave these as-is, but don't add to them!
        See D4342#98780
        """
        if name == 'bScreen':
            return 'Screen'
        elif name == 'Collection':
            return 'Group'
        elif name == 'CollectionObject':
            return 'GroupObject'
        else:
            return name
        
    def __getStructures(self, f):
        """
        getStructures fetches all the structure arrays and returns them as
        a list of lists, where each element list is an encoded structure
        definition.
        
        Input structure definition format:
        Each structure definition is a variable length array of 2-byte
        integers.
        index  meaning
        -----  -------
           0    struct type number, i.e. index into __allTypes array
           1    number of members in the structure
           2    type number of first member
           3    name number of first member, i.e. index into allnames array
        ... repeats for each member
        
        We will save these as a list where the first element is the structure
        type code, and the second element is a list of tuples, where each tuple
        is a type/name code pair.
        """
        # first 4 bytes of structs section must be "STRC"
        if check4(f, 'STRC') == None:
            return None
        # read the number of structure definitions
        numStructs = getInt(f.read(4))
        theStructs = []
        for structIdx in range(0, numStructs):
            curStruct = []
            structType = getInt(f.read(2))
            curStruct.append(structType)
            numMembers = getInt(f.read(2))
            curMembers = []
            for memberIdx in range(0, numMembers):
                typeCode = getInt(f.read(2))
                nameCode = getInt(f.read(2))
                curMembers.append((typeCode, nameCode))
            curStruct.append(curMembers)
            if len(curStruct) > 0:
                theStructs.append(curStruct)
        
        if len(theStructs) > 0:
            return theStructs
        else:
            return None
                
    def dumpStruct(self,names,types,struct):
        print('struct ', types[struct[0]], ' {', sep='')
        for t in struct[1]:
            print('\t', types[t[0]], ' ', names[t[1]], ';', sep='')
        print('};')
    
if __name__ == '__main__': main()
