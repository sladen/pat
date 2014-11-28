#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Paul Sladen, 2014-11-25, Seaward SSS PAT testing file format debug harness
# Hereby placed in the public domain in the hopes of improving
# electrical safety and interoperability
# Usage: ./portableappliancetester.py <input.sss>
#
# = PAT Testing =
# Portable Appliance Testing (PAT Inspections) are tests undertaken on
# electrical equipment before they can be used in a workplace.  A
# significant part of the test process is visual, followed by an
# electrical sanity test.  This part can be performed with a
# multi-meter, but over time dedicated test machines were created to
# automate the electrical part of the test, and to record the results
# of the visual part, plus automatically recording data and time.
#
# == Seaward ==
# Seaward appear to be one UK-based manufacturer of such devices, with
# output being in a binary format normally given the extension '.sss'.
# To date (2014-11-28) I (Paul Sladen) have only seen a single '.sss'
# file, containing 12 results, of out of which 10 contain visual
# inspection only, 2 of the results have (some) of the electrical
# tests, and 1 is a visual fail.
#
# == Stream structure ==
# The structure of the file/stream is big-endian and simple in nature.
# There is no file-header, only a stream of concatenated test records.
# Each record has a six-byte header with its payload length and
# checksum, and a number of fields/sub-records prefixed by a one-byte
# type code.  The checksum is a 16-bit summation of the payload byte
# values.  The null (zeros) values may be a protocol version number.
#
# === Visual test header ===
# The visual inspection sub-record contains several fixed-length ASCII
# string fields, date-and-time (rounded down to the minute, and with no
# timezone), and configuration/parameter "testcodes".
#
# ==== Testcodes ====
# The two 10-digit testcode appear to cover the configuration of the
# testing machine (port, voltage, current limits, enabled tests).
# The test strings are ultimately configured by the user, either by
# menus or barcode-scanning a pre-made test-code sheet, or label on
# the appliance to be tested.  Testcodes are not covered here.
#
# === Electrical test results ===
# Most test results in 16-bit fields are formed of both a one-bit
# boolean field (individual test pass/fail), while the remaining
# lower 15 bits hold a resistance value (0.01 MOhm).  Current
# measurement appears to be possibly be scaled by 0.1/16 Amps.
#
# === Free form text ===
# There is space for four 21-character free-form text strings, these
# appear to normally be used for documenting any failure reason.
# The fields are fixed-length and zero padding, leaving it unclear
# whether the final byte in each string is required to be zero.
#
# = Version 2 =
# There appears to be newer version of the format with much the same
# structure, but with the possibility of multiple results per sub-record,
# with the count being iuncluded as an additional byte between the
# result code type (F0-FE) and the 16-bit result values.
#
# = Further work =
# Currently this utility is intended as a debug class to assistant
# with understanding the format in order to allow interoperability,
# and in particular allow use of the meters on non-MS Windows
# operating systems such as Debian and Ubuntu.
#
# Suggested work for those interested, could be to:
# Add option support for newer multi-sample protocol version.
# Add option to output ASCII is same format as meter (requires example)
# Add option to output .csv

import struct, sys
import string
import collections

# Code is in the main() function at the bottom.  Above are helper
# classes, and then classes for parsing the 'SSS' format itself.

# Not-invented-here Structured Database Helper class
class sdb(object):
    """Structured database class, not related to 'SSS' specifically.  It is
    a helper class for describing binary databases and gets used later
    below; variants of 'sdb' have been re-used over the years on various
    file-format parsers."""

    field_pack_format = {int: 'I'}
    def __init__(self, endian='<'):
        self.data = collections.OrderedDict()
        self.build_format_string(endian = endian)

    def build_format_string(self, endian):
        self.endian = endian
        s = ''
        for name, type, size in self.fields:
            if type == int and size == 1: s += 'B'
            elif type == int and size == 2: s += 'H'
            elif type == int and size == 4: s += 'L'
            elif type == str:
                s += str(size) + 's'
            else:
                s += self.field_pack_format[type]
        self.format_string = self.endian + s
        self.required_length = struct.calcsize(self.format_string)
        
    def unpack(self, s):
        u = list(struct.unpack(self.format_string, s))
        for name, type, size in self.fields:
            if type == str:
                u[0] = u[0].replace('\x00', '').rstrip()
            self.data[name] = type(u.pop(0))
        return self

    def headings(self):
        return [name for name, type, size in self.fields]

    def values(self):
        return self.data.values()

    def items_dict(self):
        s = '{'
        s += ', '.join(['%s:%s' % (k, `v`) for k, v in self.data.items()])
        s += '}'
        return s

    def __len__(self):
        return self.required_length

    def __str__(self):
        return str(self.data)

# This sub-class for the SSS stream-format, most 
class SSS(sdb):
    def __init__(self):
        super(SSS, self).__init__(endian='>')
        
    def fixup(self):
        pass
    def unpack(self, s):
        r = super(SSS, self).unpack(s)
        r.fixup()
        return self

class SSSRecordHeader(SSS):
    fields = [('payload_length', int, 2),
              ('nulls', int, 2),
              ('checksum_header', int, 2)]
    def checksum(self, payload):
        # checksum is the sum value of all the bytes in the payload portion
        self.data['checksum_payload'] = sum(map(ord,payload)) & 0xffff
        match = bool(self.data['checksum_header'] == self.data['checksum_header'])
        self.data['checksum_match'] = match
        return match

class SSSVisualTest(SSS):
    fields = [('id', str, 16),
              ('hour', int, 1),
              ('minute', int, 1),
              ('day', int, 1),
              ('month', int, 1),
              ('year', int, 2),
              ('site', str, 16),
              ('location', str, 16),
              ('tester', str, 11),
              ('testcode1', str, 10),
              ('testcode2', str, 11)
              ]

class SSSNoDataTest(SSS):
    fields = []

class SSSEarthResistanceTest(SSS):
    fields = [('resistance', int, 2),
              ]
    def fixup(self):
        self.data['pass'] = bool(self.data['resistance'] >> 15)
        self.data['resistance'] = 0.01 * (self.data['resistance'] & 0x7fff)

class SSSEarthInsulationTest(SSS):
    fields = [('resistance', int, 2),
              ]
    def fixup(self):
        self.data['pass'] = not bool(self.data['resistance'] >> 15)
        self.data['actual_resistance'] = 0.01 * self.data['resistance'] 
        # Note: the displayed resistance for the Earth Insulation test
        # is capped at 19.99 MOhms or 99.99 MOhms depending upon the
        # model of meter.  Internally the meters appears to treat
        # infinity as somewhere around 185 MOhms and stores the actual
        # value measured (this is needed for calibration situations).
        # For simple result reporting, the value is capped to 99.99
        # MOhms, inline which what other software (and the meter's
        # display) does.
        self.data['resistance'] = min(99.99, 0.01 * (self.data['resistance'] & 0x7fff))

class SSSPowerLeakTest(SSS):
    fields = [('leakage', int, 2),
              ('load', int, 2),
              ]
    def fixup(self):
        self.data['pass'] = bool(self.data['leakage'] >> 15)
        # Note: The 10/16ths current (load) scaling factor was
        # obtained from a sample size of two results only, both of
        # which were the same... Caveat emptor!
        self.data['load'] = 0.1/16.0 * self.data['load']
        self.data['leakage'] = 0.01 * (self.data['leakage'] & 0x7fff)

class SSSContinuityTest(SSS):
    fields = [('resistance', int, 2),
              ]
    def fixup(self):
        self.data['pass'] = bool(self.data['resistance'] >> 15)
        # Zero appears to correspond to infinity (no connection).
        # Which at least one other output software apparently shows as
        # "(no result)", instead of a numerical value.  This reported
        # behaviour is copied here.
        if self.data['resistance'] & 0x7fff == 0:
            self.data['resistance'] = '(no result)'
        else:
            self.data['resistance'] = 0.01 * (self.data['resistance'] & 0x7fff)

class SSSUserDataTest(SSS):
    fields = [('line1', str, 21),
              ('line2', str, 21),
              ('line3', str, 21),
              ('line4', str, 21),
              ]

# Field types:
# 0x01 86x Main record (Asset, Datetime, Site, Location, Tester, Testcode 1, Testcode 2)
# 0xf0 Pass
# 0xf1 Fail
# 0xf2 1H (Ohm) Earth resistance test (top-bit pass/fail flag?)
# 0xf3 1H (kOhm) Insulation
# 0xf6 2H Two values (Ohm or mA?)
# 0xf8 1H mA?
# 0xfb Freeform text/failure description (4*21 characters)
# 0xff End of record

Tests = {
    0x01: ('Visual Pass (01)', SSSVisualTest),
    0x02: ('Visual Fail (02)', SSSVisualTest),
    0xf0: ('Overall Pass (F0)', SSSNoDataTest),
    0xf1: ('Overall Fail (F1)', SSSNoDataTest),
    0xf2: ('Earth Resistance (F2)', SSSEarthResistanceTest),
    0xf3: ('Earth Insulation (F3)', SSSEarthInsulationTest),
    0xf6: ('Load/Leakage (F6)', SSSPowerLeakTest),
    0xf8: ('Continuity (F8)', SSSContinuityTest),
    0xfb: ('User data (FB)', SSSUserDataTest),
    0xff: ('End of Record (FF)', SSSNoDataTest),
    }
    

import struct
import functools
from functools import partial

def main(filename = 'SSS'):
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    f = open(filename, 'r')
    r = SSSRecordHeader()
    for header in iter(lambda: f.read(len(r)), ''):
        r.unpack(header)
        payload = f.read(r.data['payload_length'])
        r.checksum(payload)
        #print 'Checksum {pass: %s}' % bool(checksum == r.data['checksum'])
        print 'New Record', r.items_dict()
        test_type = None
        while len(payload) and test_type != 0xff:
            test_type = ord(payload[0])
            payload = payload[1:]
            t = Tests[test_type][1]()
            # Unpack the current sub-field
            t.unpack(payload[:len(t)])
            print Tests[test_type][0], t.items_dict()

            # Seek past to start of next sub-field
            payload = payload[len(t):]

        # Line-break between records.
        print
        

if __name__=='__main__':
    main()
