#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Paul Sladen, 2014-12-04, Seaward GAR PAT testing file format debug harness
# Hereby placed in the public domain in the hopes of improving
# electrical safety and interoperability.
#
# Example: gar.py <input1.gar> [input2.gar] ...
#
# This would extract the results to 'input1_TestResults.sss', and any
# other JPEG attachments to 'input1_...jpg'.  Note that the JPEGs are
# low-resolution (320x240---at least the ones I've seen); this is not
# a problem with with extraction!

# == GAR ==
# GAR files are a container format used for importing/exporting
# filesets to and from some Seaward PAT testing machines ("Apollo"
# series?).  As of 2014-12-05 I have seen three examples of '.GAR'
# files; one purporting to contain an .SSS file and a selection of
# JPEGs and two purporting to contain just an .SSS file.
#
# == File Header ==
# There is a single file-header that begins 0xcabcab (CAB CAB;
# cabinet?) for magic/identification purposes, followed by single byte
# version number.  There is no-end of file marker or overall checksum.
#
# == Archive records ==
# Each file stored within the GAR container is prefixed by:
# 1. a record header giving the overall size of the record;
# 2. a variable length human-readable string (aka the filename);
# 3. a truncated monotonically-increasing semi-timestamp;
# 4. the original pre-compression length.
#
# == Compression ==
# Compression is Deflate---as used in zipfiles and PNG images---
# wrapped with zlib headers and footers.  This reduces the largely
# fixed-field .SSS files to ~10% of their input size, while the
# already-compressed JPEG files remain ~99% of their input size.
# Each file's payload is compressed separately.
#
# == Deflate ==
# The QByteArray::qCompress() convention is used, which prepends an
# extra four-byte header containing an additional little-endian
# uncompressed stream size, then continues with the usual two-byte
# zlib header, deflate streame, and four-byte zlib footer:
# http://ehc.ac/p/ctypes/mailman/message/23484411/
#
# As the contained files are likely to be under 65k in length, the
# first 2 bytes of the original length are nulls, which proved to be a
# handy plaintext and sanity check for the next step. :-D
#
# There appear to be some people at Seaward posting patches to Qt
# so I expect the added qCompress() length prefix is probably simply
# as a result of using Qt somewhere, rather than an active choice:
# http://patchwork.openembedded.org/patch/80259/mbox/
#
# == Obfuscation ==
# The qCompress (with length prefix)-style Deflate/zlib streams 
# are perturbed additively (meaning bytewise ADD/SUB, not XOR) with
# the bottom 8-bits from Marsaglia xorshift PNR, seeded from the
# pseudo-timestamp and payload length of the corresponding file.
#
# Xorshift uses 128-bits (four * 32-bit words) for state (x,y,z,w),
# and the standard default seeds are used for initialisation for
# 'z' and 'w' while, 'x' and 'y' are seeded from truncated timestamp
# and from the original file-length.  The give-away for spotting
# xorshift is that the first round output depends solely upon the
# 'x' and 'w' inputs, enabling confirmation of 'x' (== timestamp)
# independent to confirmation of 'y' (== original file length).
# 
# 5. original length (little-endian, four octets)
# 6. compressed contents (zlib)
#
# == Integrity checking ==
# Aside from failing to decode/validate, the zlib checksum provides
# the only defacto integrity checking in the GAR file-format.

import struct
import sys
import zlib

# Marsaglia xorshift, using default parameters
# https://en.wikipedia.org/wiki/Xorshift
# http://stackoverflow.com/questions/4508043/on-xorshift-random-number-generator-algorithm
def marsaglia_xorshift_128(x = 123456789, y = 362436069, z = 521288629, w = 88675123):
    while True:
        t = (x ^ (x << 11)) & 0xffffffff
        x, y, z = y, z, w
        w = (w ^ (w >> 19) ^ (t ^ (t >> 8)))
        yield w

# The lower 8-bits from the Xorshift PNR are subtracted from byte
# values during extraction, and added to byte values on insertion.
# When calling deobfuscate_string() the whole string is processed.
def deobfuscate_string(pnr, obfuscated, operation=int.__sub__):
    return ''.join([chr((operation(ord(c), pnr.next())) & 0xff) for c in obfuscated])

# Remove spaces and directory slashes from a string (filename).
# This is useful for saving a file in the current directory, rather
# than needing to recreate the structure of the container.
def clean_filename(unsafe_filename):
    return unsafe_filename.replace('/','_').replace(' ','_').replace('\\','_')

# The main parse and extract from Seaward '.GAR' container starts here
def gar_extract(container_filename):

    # Try to read the filename we've been asked to parse
    container = open(container_filename, 'rb')

    # The GAR container's magic number is 0xcabcab
    container_header = struct.unpack('>L', container.read(4))[0]
    container_magic, container_version = container_header >> 8, container_header & 0xff
    assert container_magic == 0xcabcab and container_version == 1

    # The container has no end-of-file marker, it ends when there are no more records
    while True:
        s = container.read(4)
        if len(s) < 4:
            break

        # The record headers start with a variable length (filename) string
        filename_length, = struct.unpack('>L', s)
        filename = container.read(filename_length)

        # Followed by a file contents, variable length depending on compression
        compressed_length, = struct.unpack('>L', container.read(4))
        contents = container.read(compressed_length)
        header_length, mangling_method, truncated_timestamp, original_length = struct.unpack('>HHLL', contents[:12])
        assert header_length == 12 and mangling_method == 1

        # The file contents are obfuscated with a Marsaglia xorshift PNR
        pnr = marsaglia_xorshift_128(x = truncated_timestamp, y = original_length)

        # There is also a (second) obfuscated copy of the original file length
        # and then the (compressed) file contents.
        qcompress_prefix = deobfuscate_string(pnr, contents[12:16])
        zlib_stream = deobfuscate_string(pnr, contents[16:])

        # We can check the lengths match up, and if so try to uncompress with zlib
        expected_length, = struct.unpack(">L", qcompress_prefix)
        assert original_length == expected_length
        original = zlib.decompress(zlib_stream)

        # And try to ensure that filename can be saved to the local directory
        target_filename = filename
        if filename == 'TestResults.sss':
            if container_filename.endswith('.gar'):
                target_filename = container_filename[:-4] + '_' + filename
        safe_filename = clean_filename(target_filename)

        # Assuming it all went well we can inform the user where their file will be saved
        assert original_length == expected_length == len(original)
        print 'Saving "%s" (%2.0f%%) to "%s"' % \
            (filename,
             100.0 * float(compressed_length) / (original_length),
             safe_filename)

        # And then write out the original uncompressed file to its appropriate name
        f = open(safe_filename + '', 'wb')
        f.write(original)
        f.close()

# Step though, allowing multiple '.gar' filenames to be passed at once (handy for testing)
def main():
    for gar in sys.argv[1:]:
        print 'Trying CAB/GAR filename "%s"' % gar
        gar_extract(gar)

if __name__=='__main__':
    main()
