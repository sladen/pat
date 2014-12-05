#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Paul Sladen, 2014-12-04, Seaward GAR PAT testing file format debug harness
# Hereby placed in the public domain in the hopes of improving
# electrical safety and interoperability.

# == GAR ==
# GAR files are a container format used for importing/exporting
# filesets to and from some Seaward PAT testing machines ("Apollo"
# series?).  As of 2014-12-05 I have seen three examples of '.GAR'
# files; one purporting to contain an .SSS file and a selection of
# JPEGs and two purporting to contain just an .SSS file.
#
# == File Header ==
# There is a single file-header that begins 0xcabcab (CAB CAB;
# cabinet?) for identification purposes, followed by single byte
# version number.  There is no-end of file marker or overall checksum.
#
# == Archive records ==
# Each file stored within the container is prefixed by a record header
# giving the overall size of the record, a variable length
# human-readable string that is the filename, a monotonically
# increasingly truncated semi-timestamp, plus uncompressed (before
# Deflate) length.
#
# == Compression ==
# Compression is straight Deflate (aka zlib)---as is used in zipfiles
# and PNG images.  This reduces the largely fixed-field .SSS files to
# ~10% of their input size, while the already-compressed JPEG files
# remain ~99% of their input size.  Each file's payload is compressed
# separately.
# 
# == Obfuscation ==
# The compressed Deflate streams are additively perturbed using the
# bottom 8-bits from Marsaglia xorshift PNR, seeded from the
# pseudo-timestamp and payload length of the corresponding file.
#
# == Integrity checking ==
# The Deflate checksum provides the only defacto integrity checking in
# the GAR file-format.

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
