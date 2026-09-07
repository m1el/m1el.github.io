#!/usr/bin/env python3
"""Blowfish in CFB-8 mode, pure Python, no dependencies.

CFB-8 is a byte-wide feedback mode: every ciphertext byte is fed back into
the 8-byte shift register, so each output byte depends on the previous eight
ciphertext bytes (and, transitively, on all preceding input). Changing one
plaintext byte changes every ciphertext byte after it. No padding is needed.

Usage:
    bf = Blowfish(key)                       # key: 4..56 bytes
    ct = bf.encrypt(plaintext)               # random IV, output = len + 8
    pt = bf.decrypt(ct)

The IV is handled as an "explicit IV": eight random bytes are prepended to
the plaintext and encrypted along with it, starting from an all-zero shift
register. The first eight ciphertext bytes therefore act as the effective IV
for the real message, and decryption simply drops them. Nothing needs to be
carried out-of-band.

Raw CFB-8 with a caller-supplied register is still available as
cfb8_encrypt(iv, data) / cfb8_decrypt(iv, data).
"""

import os

MASK32 = 0xFFFFFFFF


def _pi_hex_fraction(nwords):
    """Return the first nwords 32-bit words of the fractional part of pi.

    Machin's formula with integer arithmetic: pi = 16 atan(1/5) - 4 atan(1/239).
    """
    bits = nwords * 32 + 64  # guard bits
    one = 1 << bits

    def atan_inv(x):
        # atan(1/x) = sum (-1)^k / ((2k+1) x^(2k+1)), scaled by `one`
        total = term = one // x
        x2 = x * x
        k = 1
        sign = -1
        while term:
            term //= x2
            total += sign * (term // (2 * k + 1))
            sign = -sign
            k += 1
        return total

    pi = 16 * atan_inv(5) - 4 * atan_inv(239)
    frac = pi - 3 * one            # drop the integer part
    frac >>= 64                    # drop guard bits
    return [(frac >> (32 * (nwords - 1 - i))) & MASK32 for i in range(nwords)]


_PI_WORDS = _pi_hex_fraction(18 + 4 * 256)
_P_INIT = _PI_WORDS[:18]
_S_INIT = [_PI_WORDS[18 + 256 * i: 18 + 256 * (i + 1)] for i in range(4)]

assert _P_INIT[0] == 0x243F6A88 and _P_INIT[1] == 0x85A308D3
assert _S_INIT[3][255] == 0x3AC372E6


class Blowfish:
    BLOCK_SIZE = 8

    def __init__(self, key):
        if not 4 <= len(key) <= 56:
            raise ValueError("Blowfish key must be 4..56 bytes")
        self.P = list(_P_INIT)
        self.S = [list(box) for box in _S_INIT]

        # XOR the key cyclically into the P-array.
        klen = len(key)
        j = 0
        for i in range(18):
            word = 0
            for _ in range(4):
                word = (word << 8) | key[j]
                j = (j + 1) % klen
            self.P[i] ^= word

        # Replace P and S entries with successive encryptions of zero.
        left = right = 0
        for i in range(0, 18, 2):
            left, right = self._encrypt_words(left, right)
            self.P[i], self.P[i + 1] = left, right
        for box in self.S:
            for i in range(0, 256, 2):
                left, right = self._encrypt_words(left, right)
                box[i], box[i + 1] = left, right

    def _f(self, x):
        S = self.S
        return ((S[0][x >> 24] + S[1][(x >> 16) & 0xFF]) ^ S[2][(x >> 8) & 0xFF]) + S[3][x & 0xFF] & MASK32

    def _encrypt_words(self, left, right):
        P = self.P
        for i in range(16):
            left ^= P[i]
            right ^= self._f(left)
            left, right = right, left
        left, right = right, left
        right ^= P[16]
        left ^= P[17]
        return left, right

    def _decrypt_words(self, left, right):
        P = self.P
        for i in range(17, 1, -1):
            left ^= P[i]
            right ^= self._f(left)
            left, right = right, left
        left, right = right, left
        right ^= P[1]
        left ^= P[0]
        return left, right

    def encrypt_block(self, block):
        if len(block) != 8:
            raise ValueError("block must be 8 bytes")
        left, right = self._encrypt_words(
            int.from_bytes(block[:4], "big"), int.from_bytes(block[4:], "big"))
        return left.to_bytes(4, "big") + right.to_bytes(4, "big")

    def decrypt_block(self, block):
        if len(block) != 8:
            raise ValueError("block must be 8 bytes")
        left, right = self._decrypt_words(
            int.from_bytes(block[:4], "big"), int.from_bytes(block[4:], "big"))
        return left.to_bytes(4, "big") + right.to_bytes(4, "big")

    # --- CFB-8 -----------------------------------------------------------

    def cfb8_encrypt(self, iv, data):
        if len(iv) != 8:
            raise ValueError("IV must be 8 bytes")
        register = bytearray(iv)
        out = bytearray()
        for byte in data:
            c = self.encrypt_block(bytes(register))[0] ^ byte
            out.append(c)
            del register[0]
            register.append(c)
        return bytes(out)

    def cfb8_decrypt(self, iv, data):
        if len(iv) != 8:
            raise ValueError("IV must be 8 bytes")
        register = bytearray(iv)
        out = bytearray()
        for c in data:
            out.append(self.encrypt_block(bytes(register))[0] ^ c)
            del register[0]
            register.append(c)
        return bytes(out)

    # --- explicit-IV wrappers ------------------------------------------------

    ZERO_REGISTER = bytes(8)

    def encrypt(self, data, iv=None):
        """Encrypt data with a prefixed IV. Output is len(data) + 8 bytes."""
        iv = os.urandom(8) if iv is None else bytes(iv)
        if len(iv) != 8:
            raise ValueError("IV must be 8 bytes")
        return self.cfb8_encrypt(self.ZERO_REGISTER, iv + bytes(data))

    def decrypt(self, data):
        """Decrypt data produced by encrypt(); the IV prefix is discarded."""
        if len(data) < 8:
            raise ValueError("ciphertext shorter than the 8-byte IV prefix")
        return self.cfb8_decrypt(self.ZERO_REGISTER, data)[8:]


def _selftest():
    # Schneier's published ECB test vectors.
    vectors = [
        ("0000000000000000", "0000000000000000", "4EF997456198DD78"),
        ("FFFFFFFFFFFFFFFF", "FFFFFFFFFFFFFFFF", "51866FD5B85ECB8A"),
        ("0123456789ABCDEF", "1111111111111111", "61F9C3802281B096"),
        ("FEDCBA9876543210", "0123456789ABCDEF", "0ACEAB0FC6A0A28D"),
        ("7CA110454A1A6E57", "01A1D6D039776742", "59C68245EB05282B"),
    ]
    for k, p, c in vectors:
        bf = Blowfish(bytes.fromhex(k))
        assert bf.encrypt_block(bytes.fromhex(p)).hex().upper() == c, (k, p)
        assert bf.decrypt_block(bytes.fromhex(c)).hex().upper() == p, (k, c)

    # Variable-length key vector from the Blowfish spec (Eric Young's set).
    bf = Blowfish(bytes.fromhex("F0E1D2C3B4A5968778695A4B3C2D1E0F0011223344556677"))
    assert bf.encrypt_block(bytes.fromhex("FEDCBA9876543210")).hex().upper() == "05044B62FA52D080"

    # CFB-8 round trip and the propagation property.
    bf = Blowfish(b"mischief")
    iv = bytes(range(8))
    msg = b"The quick brown fox jumps over the lazy dog"
    ct = bf.cfb8_encrypt(iv, msg)
    assert bf.cfb8_decrypt(iv, ct) == msg
    ct2 = bf.cfb8_encrypt(iv, b"t" + msg[1:])
    changed = sum(a != b for a, b in zip(ct[1:], ct2[1:]))
    assert changed > len(msg) // 2, "flipping byte 0 should scramble the rest"
    assert bf.cfb8_encrypt(iv, msg[:5]) == ct[:5], "prefix must be stable"

    # Explicit-IV wrappers.
    blob = bf.encrypt(msg)
    assert len(blob) == len(msg) + 8
    assert bf.decrypt(blob) == msg
    assert bf.encrypt(msg) != blob, "random IV should differ between calls"
    assert bf.encrypt(msg, iv) == bf.cfb8_encrypt(bytes(8), iv + msg)
    assert bf.decrypt(bf.encrypt(b"")) == b""
    print("all tests passed")


def encrypt_password(s):
    if isinstance(s, str):
        s = s.encode('utf-8')
    key = b"mischief"
    bf = Blowfish(key)
    iv = bytes.fromhex("DEADBEEFBAADF00D")
    cipher = bf.encrypt(s, iv)
    return base64.b64encode(cipher).decode()


def decrypt_password(enc):
    cipher = base64.b64decode(enc.encode())
    iv_len = 8
    pw_len = len(cipher) - iv_len
    empty = encrypt_password("")
    assert cipher[:iv_len] == base64.b64decode(empty), "IV mismatch"
    password = bytearray(pw_len)
    for pos in range(pw_len):
        for guess in range(256):
            password[pos] = guess
            trial = encrypt_password(password[:pos + 1])
            tr_bytes = base64.b64decode(trial)
            matched = tr_bytes[iv_len + pos] == cipher[iv_len + pos]
            if matched:
                break
        else:
            raise RuntimeError("whoopsie-daisy")
    return bytes(password)


if __name__ == "__main__":
    import sys
    import base64
    args = sys.argv[1:]
    if not args:
        _selftest()
    elif args[0] == "e":
        print(encrypt_password(args[1].encode()))
    elif args[0] == "d":
        print(decrypt_password(args[1]))
    elif args[0] == "enc" and len(args) in (3, 4):
        bf = Blowfish(args[1].encode())
        iv = bytes.fromhex(args[3]) if len(args) == 4 else None
        cipher = bf.encrypt(args[2].encode(), iv)
        print(base64.b64encode(cipher).decode())
        print(cipher.hex())
    elif args[0] == "dec" and len(args) == 3:
        bf = Blowfish(args[1].encode())
        cipher = base64.b64decode(args[2].encode())
        sys.stdout.buffer.write(bf.decrypt(cipher))
    else:
        print("usage: blowfish_cfb8.py                       run self-test\n"
              "       blowfish_cfb8.py enc <key> <text> [iv-hex16]\n"
              "       blowfish_cfb8.py dec <key> <hex>", file=sys.stderr)
        sys.exit(1)
