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
# giving the overall size of the record,
# a variable length human-readable string (the filename),
# a monotonically increasingly truncated semi-timestamp,
# plus the original pre-compression length.
#
# == Compression ==
# Compression is straight Deflate (aka zlib)---as is used in zipfiles
# and PNG images.  This reduces the largely fixed-field .SSS files to
# ~10% of their input size, while the already-compressed JPEG files
# remain ~99% of their input size.  Each file's payload is compressed
# separately.
#
# == Deflate ==
# The QByteArray::qCompress() convention is used, this prepends an
# extra four-byte header containing the little-endian uncompressed
# size, followed by the two-byte zlib header, deflate
# streamed, and four-byte zlib footer:
# http://ehc.ac/p/ctypes/mailman/message/23484411/
#
# Note that as the contained files are likely to be well-under 65k in
# length, the first 2 bytes are be nulls, which is a handy way to
# sanity test the next step.  :-D
# 
# == Obfuscation ==
# The qCompress-style compressed Deflate streams (with length prefix)
# are additively perturbed (bytewise ADD/SUB, not XOR) using the
# bottom 8-bits from Marsaglia xorshift PNR, seeded from the
# pseudo-timestamp and payload length of the corresponding file.
#
# == Integrity checking ==
# The Zlib checksum provides the only defacto integrity checking in
# the GAR file-format; however the presence of the duplicate
# (obfuscated) file length is a useful double-check.

import struct
import sys
import numpy
import zlib

# Marsaglia xorshift
# https://en.wikipedia.org/wiki/Xorshift
# http://stackoverflow.com/questions/4508043/on-xorshift-random-number-generator-algorithm
def marsaglia_xorshift_128(x = 123456789, y = 362436069, z = 521288629, w = 88675123):
    while True:
        t = (x ^ (x << 11)) & 0xffffffff
        x, y, z = y, z, w
        w = (w ^ (w >> 19) ^ (t ^ (t >> 8)))
        yield w

# The lower 8-bits from the Xorshift PNR are subtracted from byte values
def deobfuscate_string(pnr, obfuscated):
    return ''.join([chr((ord(c) - pnr.next()) & 0xff) for c in obfuscated])

# Remove spaces and directory slashes
def clean_filename(unsafe_filename):
    return unsafe_filename.replace('/','_').replace(' ','_').replace('\\','_')

def gar_extract(container_filename):
    # Try to read the filename we've been asked to parse
    container = open(container_filename, 'rb')

    # The GAR container's magic number is 0xcabcab
    container_header = struct.unpack('>L', container.read(4))[0]
    cabcab, container_version = container_header >> 8, container_header & 0xff
    assert cabcab == 0xcabcab and container_version == 1

    # The container has no end-of-file marker, it ends when there are no more records
    while True:
        s = container.read(4)
        if len(s) < 4:
            break

        # The record headers start with a variable length filename string
        filename_length, = struct.unpack('>L', s)
        filename = container.read(filename_length)

        # Followed by variable length compressed + obfuscated file contents
        compressed_length, = struct.unpack('>L', container.read(4))
        contents = container.read(compressed_length)
        header_length, mangling_method, truncated_timestamp, original_length = struct.unpack('>HHLL', contents[:12])
        assert header_length == 12 and mangling_method == 1

        # The remainder of the contents is obfuscated with a Marsaglia xorshift PNR
        pnr = marsaglia_xorshift_128(x = truncated_timestamp, y = original_length)
        qcompress_prefix = deobfuscate_string(pnr, contents[12:16])
        zlib_stream = deobfuscate_string(pnr, contents[16:])

        # We can check the prefixed length matches up, and if so try to uncompress with zlib
        expected_length, = struct.unpack(">L", qcompress_prefix)
        assert original_length == expected_length
        original = zlib.decompress(zlib_stream)

        # And try to ensure that filename can be saved to the local directory
        target_filename = filename
        if filename == 'TestResults.sss':
            if container_filename.endswith('.gar'):
                target_filename = container_filename[:-4] + '_' + filename
        safe_filename = clean_filename(target_filename)

        # Assuming it all went well we can inform the user where it will be saved
        assert original_length == expected_length == len(original)
        print 'Saving "%s" (%2.0f%%) to "%s"' % \
            (filename,
             100.0 * float(compressed_length) / (original_length),
             safe_filename)

        # And tne write out the original uncompressed file to its appropriate name
        f = open(safe_filename + '', 'wb')
        f.write(original)
        f.close()

# Step though multiple '.gar' files being passed in one go
def main():
    for gar in sys.argv[1:]:
        print 'Trying CAB/GAR filename "%s"' % gar
        gar_extract(gar)

if __name__=='__main__':
    main()
