#!/usr/bin/env python3
"""Small independent sanity checks for the original synthetic fixture builder."""
import struct
import tempfile
import unittest
from pathlib import Path

import synthetic_check as check


class SyntheticFixtureTests(unittest.TestCase):
    def result(self, name, a, b=0, t=0):
        state = list(range(22))
        state[4], state[5], state[16], state[21] = a, b, 0x3F2 | t, check.RETURN
        before = state.copy()
        output = check.mathematical_result(name, state)
        self.assertEqual(state, before)
        for index in set(range(22)) - {0, 16, 20}:
            self.assertEqual(output[index], state[index])
        return output

    def test_addition_carry_boundaries(self):
        result = self.result('addc', 0xFFFFFFFF, 0, 1)
        self.assertEqual((result[0], result[16]), (0, 0x3F3))
        result = self.result('addc', 5, 6, 0)
        self.assertEqual((result[0], result[16]), (11, 0x3F2))
        self.assertEqual(self.result('add', 0xFFFFFFFF, 1)[0], 0)

    def test_subtraction_borrow_boundaries(self):
        result = self.result('subc', 0, 0, 1)
        self.assertEqual((result[0], result[16]), (0xFFFFFFFF, 0x3F3))
        result = self.result('subc', 7, 6, 1)
        self.assertEqual((result[0], result[16]), (0, 0x3F2))

    def test_signed_overflow_boundaries(self):
        add = self.result('addv', 0x7FFFFFFF, 1)
        sub = self.result('subv', 0x80000000, 1)
        self.assertEqual((add[0], add[16]), (0x80000000, 0x3F3))
        self.assertEqual((sub[0], sub[16]), (0x7FFFFFFF, 0x3F3))
        self.assertEqual(self.result('addv', 0xFFFFFFFF, 1, 1)[16], 0x3F2)

    def test_signed_and_unsigned_comparisons_differ(self):
        self.assertEqual(self.result('signed_lt', 0xFFFFFFFF, 0)[0], 1)
        self.assertEqual(self.result('unsigned_lt', 0xFFFFFFFF, 0)[0], 0)
        self.assertEqual(self.result('signed_lt', 7, 7)[0], 0)

    def test_rotations_preserve_shifted_out_bits(self):
        left = self.result('rotl', 0x80000001)
        right = self.result('rotr', 0x80000001)
        self.assertEqual((left[0], left[16]), (3, 0x3F3))
        self.assertEqual((right[0], right[16]), (0xC0000000, 0x3F3))

    def test_multiplication_low_word(self):
        result = self.result('mul_low', 0xFFFFFFFF, 0xFFFFFFFF)
        self.assertEqual((result[0], result[20]), (1, 1))
        self.assertEqual(self.result('mul_low', 0x10000, 0x10000)[0], 0)

    def test_boot_literal_and_instruction_layout(self):
        body = check.boot_program()
        self.assertEqual(len(body), 76)
        first = struct.unpack_from('>H', body)[0]
        self.assertEqual(first >> 8, 0xD1)  # mov.l @(disp,PC),r1
        offset = 4 + 4 * (first & 0xFF)
        self.assertEqual(struct.unpack_from('>I', body, offset)[0], 0x06030000)
        self.assertEqual(struct.unpack_from('>H', body, 4)[0], 0x2102)
        self.assertEqual(body[30:34], bytes.fromhex('AFFE0009'))

    def test_iso_directory_and_payload_are_original(self):
        with tempfile.TemporaryDirectory(prefix='pal-synthetic-test-') as temp:
            cue = check.synthetic_disc(Path(temp) / 'disc', b'original-test-only', check.BOOT_BASE)
            image = (cue.parent / 'synthetic.iso').read_bytes()
        self.assertEqual(image[:16], b'SEGA SEGASATURN ')
        self.assertEqual(image[16 * 2048:16 * 2048 + 7], b'\x01CD001\x01')
        self.assertEqual(struct.unpack_from('>I', image, 0xF0)[0], check.BOOT_BASE)
        self.assertEqual(struct.unpack_from('<I', image, 16 * 2048 + 80)[0], len(image) // 2048)
        self.assertEqual(struct.unpack_from('>I', image, 16 * 2048 + 84)[0], len(image) // 2048)
        self.assertEqual(image[21 * 2048:21 * 2048 + 18], b'original-test-only')


if __name__ == '__main__':
    unittest.main(verbosity=2)
