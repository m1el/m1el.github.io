#!/usr/bin/env python3
"""Recover a Blowfish-CFB-8 plaintext by brute-forcing one byte at a time.

The attacker is given the key and the ciphertext but only ever *encrypts*.
Because CFB-8 encrypts a prefix identically no matter what follows, the
ciphertext byte at position i depends only on plaintext bytes 0..i. So the
attacker can guess byte i, encrypt IV + known_prefix + guess, and check
whether ciphertext byte i matches. At most 256 encryptions per byte.

The IV is fixed to DEADBEEFBAADF00D, so the first eight ciphertext bytes are
already known and the search starts at the ninth.

Usage:
    brute_cfb8.py <key> <text>          encrypt <text>, then animate recovery
    brute_cfb8.py <key> hex:<cipher>    animate recovery of an existing blob
    --delay SEC                          pause per attempt (default 0.002)
"""

import sys
import time
import base64

from blowfish_cfb8 import Blowfish

IV = bytes.fromhex("DEADBEEFBAADF00D")


def brute_decrypt(bf, ciphertext, iv=IV, on_attempt=None):
    """Recover plaintext from ciphertext using only bf.encrypt().

    on_attempt(pos, guess, recovered, matched) is called for every trial.
    Returns the recovered plaintext (without the IV prefix).
    """
    recovered = bytearray()
    for pos in range(len(iv), len(ciphertext)):
        for guess in range(256):
            trial = bf.encrypt(bytes(recovered) + bytes([guess]), iv)
            matched = trial[pos] == ciphertext[pos]
            if on_attempt:
                on_attempt(pos, guess, bytes(recovered), matched)
            if matched:
                recovered.append(guess)
                break
        else:
            raise RuntimeError(f"no byte matched at position {pos}; wrong key or IV?")
    return bytes(recovered)


# --- terminal animation ------------------------------------------------------

GREEN, YELLOW, DIM, RESET = "\x1b[32m", "\x1b[33m", "\x1b[2m", "\x1b[0m"


def _glyph(b):
    return chr(b) if 0x20 <= b < 0x7F else "·"


def animate(bf, ciphertext, delay=0.002, out=sys.stdout):
    total = len(ciphertext) - len(IV)
    attempts = [0]
    start = time.monotonic()
    tty = out.isatty()

    def on_attempt(pos, guess, recovered, matched):
        attempts[0] += 1
        if not tty:
            return
        done = "".join(_glyph(b) for b in recovered)
        rest = "." * (total - len(recovered) - 1)
        chars = f"{GREEN}{done}{YELLOW}{_glyph(guess)}{DIM}{rest}{RESET}"
        hexline = f"{GREEN}{recovered.hex()}{YELLOW}{guess:02x}{DIM}{'..' * len(rest)}{RESET}"
        elapsed = time.monotonic() - start
        out.write(
            f"\x1b[2K\r"
            f"byte {len(recovered) + 1:>3}/{total}  "
            f"guess 0x{guess:02x}  "
            f"attempts {attempts[0]:>6}  \n"
            # f"{elapsed:6.2f}s\n"
            f"\x1b[2K\r  {chars}\n"
            f"\x1b[2K\r  {hexline}"
            f"\x1b[2A"
        )
        out.flush()
        if delay:
            time.sleep(delay)

    plaintext = brute_decrypt(bf, ciphertext, on_attempt=on_attempt)
    if tty:
        out.write("\n\n\n")
    elapsed = time.monotonic() - start
    out.write(
        f"recovered {len(plaintext)} bytes in {attempts[0]} attempts\n"
        # , {elapsed:.2f}s
        f"  {plaintext!r}\n"
    )
    out.flush()
    return plaintext


if __name__ == "__main__":
    args = sys.argv[1:]
    delay = 0.002
    if "--delay" in args:
        i = args.index("--delay")
        delay = float(args[i + 1])
        del args[i:i + 2]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    key, payload = args
    bf = Blowfish(key.encode())
    if payload.startswith("hex:"):
        ct = bytes.fromhex(payload[4:])
    else:
        ct = bf.encrypt(payload.encode(), IV)
        ctb = base64.b64encode(ct).decode()
        print(f"ciphertext: {ctb}\n")
    result = animate(bf, ct, delay=delay)
    if not payload.startswith("hex:"):
        assert result == payload.encode()
