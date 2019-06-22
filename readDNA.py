#!/usr/bin/env python3

"""
    This program reads a Blender binary "struct DNA" file
"""
import sys

def main():
    with open('sdna', 'rb') as f:
        processDNA(f)
    
def processDNA(f):
    # first 4 bytes must be string "SDNA"
    if check4(f, 'SDNA') == None:
        return

    # get the NAME strings
    allNames = getStringBlock(f, 'NAME')
    if allNames == None or len(allNames) == 0: return
    
    # seek to next 4-byte aligned position
    padUp4(f)
    
    # get the TYPE strings
    allTypes = getStringBlock(f, 'TYPE',
                    DNA_struct_rename_legacy_hack_static_from_alias)
    if allTypes == None or len(allTypes) == 0: return
    padUp4(f)
    
    # next 4 bytes must be "TLEN"
    if check4(f,'TLEN') == None:
        return

    # following data is a sequence of 2-byte integers representing the
    # length (in bytes) of each type in allTypes, in the same order.
    allTypeLengths = []
    for idx in range(0, len(allTypes)):
        theLen = getint(f.read(2))
        allTypeLengths.append(theLen)
    padUp4(f)

    # get the structure definitions
    allStructs = getStructs(f)
    for s in allStructs:
        dumpStruct(names=allNames, types=allTypes, struct=s)

"""
Converts an array of bytes to a signed integer
"""
def getint(bytes):
    return int.from_bytes(bytes, byteorder=sys.byteorder, signed=True)
 

"""
Gets a null-terminated string from the input file
"""
def getString(f):
    achar = f.read(1).decode()
    straccum = ''
    while achar != '\0':
        straccum += achar
        achar = f.read(1).decode()
    return straccum

"""
Reads 4 bytes and checks to see if they match the input string
"""
def check4(f, theString):
    astring = (f.read(4)).decode()
    if astring != theString:
        print(f'Expected "{theString}" saw {astring}')
        return None
    else:
        return theString

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
def getStringBlock(f, type, postProc=None):
    # first 4 bytes must be the type
    if check4(f, type) == None:
        return None
    
    # next 4 bytes are an integer representing the total number of strings
    # of the given type
    typesLen = getint(f.read(4))

    # fetch all the name strings and save
    allTypes = []
    for runningLen in range(0,typesLen):
        theString = getString(f)
        if postProc != None:
            theString = postProc(theString)
        allTypes.append(theString)
    
    return allTypes

"""
DNA Compatibility Hack
======================
Only keep this for compatibility: **NEVER ADD NEW STRINGS HERE**.
The renaming here isn't complete, references to the old struct names
are still included in DNA, now fixing these struct names properly
breaks forward compatibility. Leave these as-is, but don't add to them!
See D4342#98780
"""
def DNA_struct_rename_legacy_hack_static_from_alias(name):
    if name == 'bScreen':
        return 'Screen'
    elif name == 'Collection':
        return 'Group'
    elif name == 'CollectionObject':
        return 'GroupObject'
    else:
        return name

"""
Moves file position to next multiple of 4
"""
def padUp4(f):
    newp = ((f.tell() + 3)//4) * 4
    f.seek(newp)

"""
getStructs fetches all the structure arrays and returns them as
a list of lists, where each element list is an encoded structure
definition.

Input structure definition format:
Each structure definition is a variable length array of 2-byte
integers.
index  meaning
-----  -------
   0    struct type number, i.e. index into allTypes array
   1    number of members in the structure
   2    type number of first member
   3    name number of first member, i.e. index into allnames array
... repeats for each member

We will save these as a list where the first element is the structure
type code, and the second element is a list of tuples, where each tuple
is a type/name code pair.
"""
def getStructs(f):
    # first 4 bytes of structs section must be "STRC"
    if check4(f, 'STRC') == None:
        return None
    # read the number of structure definitions
    numStructs = getint(f.read(4))
    theStructs = []
    for structIdx in range(0, numStructs):
        curStruct = []
        structType = getint(f.read(2))
        curStruct.append(structType)
        numMembers = getint(f.read(2))
        curMembers = []
        for memberIdx in range(0, numMembers):
            typeCode = getint(f.read(2))
            nameCode = getint(f.read(2))
            curMembers.append((typeCode, nameCode))
        curStruct.append(curMembers)
        if len(curStruct) > 0:
            theStructs.append(curStruct)
    
    if len(theStructs) > 0:
        return theStructs
    else:
        return None
            
def dumpStruct(names,types,struct):
    print('struct ', types[struct[0]], ' {', sep='')
    for t in struct[1]:
        print('\t', types[t[0]], ' ', names[t[1]], ';', sep='')
    print('};')
    
if __name__ == '__main__': main()
