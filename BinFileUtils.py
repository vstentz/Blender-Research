#!/usr/bin/env python3

"""
    Module definining some binary file convenience methods
"""
import sys

"""
Converts an array of bytes to a signed integer
"""
def getInt(bytes):
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
       return None
   else:
       return theString

"""
Moves file position to next multiple of 4
"""
def padUp4(f):
    newp = ((f.tell() + 3)//4) * 4
    f.seek(newp)
