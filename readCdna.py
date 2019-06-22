#!/usr/bin/env python3

"""
    This program converts the Blender source file dna.c created by program makesdna
    into a binary file.
"""

def main():
    dnaFile = '/Users/vstentz/blender-build/cmake/source/blender/makesdna/intern/dna.c'
    f = open(dnaFile)
    # output goes to a binary file in the current directory
    of = open("sdna","wb")

    # Skip the first two lines as they have no data; they set up an array definition.
    # The lines are:
    #   extern const unsigned char DNAstr[];
    #   const unsigned char DNAstr[] = {
    line = f.readline()
    line = f.readline()
    # Succeeding lines supply data for a C unsigned char array. The lines
    # consist of up to 20 comma-separated decimal numbers, e.g.
    # 83, 68, 78, 65, ... 122, 75,
    # The last data line ends in ", };" to close the array definition.
    for line in f:
        line = line.rstrip()
        if line.endswith('};'):
            break
        # remove trailing comma, then split out the numbers
        byteStrings = line[:-1].split(', ')
        byteInts = [int(x) for x in byteStrings] # convert ASCII numbers to integers
        of.write(bytes(byteInts))
    
    # Strip off ", };", convert line to bytes, and write
    byteStrings = line[:-4].split(', ')
    byteInts = [int(x) for x in byteStrings]
    of.write(bytes(byteInts))
    
    f.close()
    of.close()

if __name__ == '__main__': main()
