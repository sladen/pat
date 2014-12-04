#!/usr/bin/env python

import struct
import sys
import numpy

def parse(filename):
    f = open(filename, 'rb')
    header = struct.unpack('>L', f.read(4))[0]
    cabcab = header >> 8
    version = header & 0xff
    assert cabcab == 0xcabcab and version == 1
    files = 1
    while True:
        s = f.read(4)
        # There is no End-of-file marker, just no more packets
        if len(s) < 4: break
        sub_filename_length, = struct.unpack('>L', s)
        sub_filename = f.read(sub_filename_length)
        compressed_length, = struct.unpack('>L', f.read(4))
        contents = f.read(compressed_length)
        header_length, compression_method, checksum, payload_length = struct.unpack('>HHLL', contents[:12])
        assert header_length == 0x0c and compression_method == 0x01
        print '"%s" (%d characters): %d bytes, %d uncompressed (%+d bytes %2.2f%%), checksum/timestamp?: %#10x' % \
            (sub_filename,
             sub_filename_length,
             compressed_length,
             payload_length,
             payload_length - compressed_length - header_length,
             100.0 * float(compressed_length) / (payload_length),
             checksum)

        # histogram shows even spread, which means either compressed
        # input (probably zlib) or input XOR'ed with a pseudo-random stream
        a, b = numpy.histogram(map(ord,contents), bins=xrange(257))
        #print dict(zip(b,a))
        #print sorted(a, reverse=True)[0]

        # test for simple XORing (now disproved)
        #for i in 0x00,:
        #    new = ''.join([chr(ord(c) ^ i) for c in contents ])
        #    g = open('output/' + str(files) + "." + str(i) + '.test', 'wb')
        #    g.write(new)
        #    g.close()

        files += 1

def main():
    for f in sys.argv[1:]:
        print 'CAB/GAR filename "%s"' % f
        parse(f)

if __name__=='__main__':
    main()
