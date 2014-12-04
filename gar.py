#!/usr/bin/env python

import struct
import sys

def parse(filename):
    f = open(filename, 'rb')
    header = struct.unpack('>L', f.read(4))[0]
    cabcab = header >> 8
    version = header & 0xff
    assert cabcab == 0xcabcab and version == 1
    while True:
        s = f.read(4)
        # There is no End-of-file marker, just no more packets
        if len(s) < 4: break
        sub_filename_length, = struct.unpack('>L', s)
        sub_filename = f.read(sub_filename_length)
        compressed_length, = struct.unpack('>L', f.read(4))
        f.read(compressed_length)
        print '"%s" (%d characters): %d bytes' % (sub_filename, sub_filename_length, compressed_length)

def main():
    for f in sys.argv[1:]:
        print 'CAB/GAR filename "%s"' % f
        parse(f)

if __name__=='__main__':
    main()
