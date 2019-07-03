#!/usr/bin/env python3

"""
    Module definining some binary file convenience methods
"""
import sys

def getInt(bytes):
   """
   Converts an array of bytes to a signed integer
   """
   return int.from_bytes(bytes, byteorder=sys.byteorder, signed=True)
 
def getString(f):
   """
   Gets a null-terminated string from the input file
   """
   achar = f.read(1).decode()
   straccum = ''
   while achar != '\0':
       straccum += achar
       achar = f.read(1).decode()
   return straccum

def check4(f, theString):
   """
   Reads 4 bytes and checks to see if they match the input string
   """
   astring = (f.read(4)).decode()
   if astring != theString:
       return None
   else:
       return theString

def padUp4(f):
   """
   Moves file position to next multiple of 4
   """
   newp = ((f.tell() + 3)//4) * 4
   f.seek(newp)
