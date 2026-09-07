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

    on_attempt(pos, guess, recovered, matched, trial_byte) is called for every
    trial; trial_byte is the ciphertext byte the guess produced at position pos.
    Returns the recovered plaintext (without the IV prefix).
    """
    recovered = bytearray()
    for pos in range(len(iv), len(ciphertext)):
        for guess in range(256):
            trial = bf.encrypt(bytes(recovered) + bytes([guess]), iv)
            matched = trial[pos] == ciphertext[pos]
            if on_attempt:
                on_attempt(pos, guess, bytes(recovered), matched, trial[pos])
            if matched:
                recovered.append(guess)
                break
        else:
            raise RuntimeError(f"no byte matched at position {pos}; wrong key or IV?")
    return bytes(recovered)


# --- terminal animation ------------------------------------------------------

GREEN, YELLOW, RED, DIM, RESET = "\x1b[32m", "\x1b[33m", "\x1b[31m", "\x1b[2m", "\x1b[0m"


def _hex_groups(data):
    return " ".join(f"{b:02x}" for b in data)


def _glyph(b):
    if b == 0x20:
        return "␣"
    return chr(b) if 0x20 < b < 0x7F else "·"


def animate(bf, ciphertext, delay=0.002, out=sys.stdout):
    """Show the target ciphertext and the trial ciphertext being matched byte by byte.

    Three lines: the target ciphertext we're trying to reproduce, the ciphertext
    of IV + recovered_prefix + guess, and the password recovered so far with each
    character aligned under its ciphertext byte.  The IV prefix is dim (already
    known), bytes matched so far are green, the byte under attack is yellow on the
    target and password lines and red/green on the trial line depending on
    whether the guess hit.
    """
    iv_len = len(IV)
    total = len(ciphertext) - iv_len
    attempts = [0]
    ciphertext_pw = bytearray()  # plaintext recovered so far, for the password line
    start = time.monotonic()
    tty = out.isatty()

    def render(pos, guess, trial_byte, matched, done_n):
        # pos is the absolute index into the ciphertext; done_n = matched bytes so far
        iv_hex = _hex_groups(ciphertext[:iv_len])
        done_hex = _hex_groups(ciphertext[iv_len:iv_len + done_n])
        cur_hex = f"{ciphertext[pos]:02x}"
        rest_hex = _hex_groups(ciphertext[pos + 1:])
        sep = " " if done_n else ""
        colour = GREEN if matched else RED
        target = (f"{DIM}{iv_hex}{RESET} {GREEN}{done_hex}{RESET}{sep}"
                  f"{GREEN if matched else YELLOW}{cur_hex}{RESET} {DIM}{rest_hex}{RESET}")
        trial_hex = f"{trial_byte:02x}"
        trial = (f"{DIM}{iv_hex}{RESET} {GREEN}{done_hex}{RESET}{sep}"
                 f"{colour}{trial_hex}{RESET}")
        # one glyph per byte, padded to the 3-column hex cells above
        pad = " " * (len(iv_hex) + 1)
        done_pw = "".join(f"{_glyph(b)}  " for b in ciphertext_pw[:done_n])
        rest_pw = "  ".join("." for _ in range(total - done_n - 1))
        password = (f"{pad}{GREEN}{done_pw}{RESET}"
                    f"{GREEN if matched else YELLOW}{_glyph(guess)}{RESET}  {DIM}{rest_pw}{RESET}")
        out.write(
            f"\x1b[2K\r"
            f"byte {min(done_n + 1, total):>3}/{total}  "
            f"guess 0x{guess:02x}  "
            f"attempts {attempts[0]:>6}  \n"
            f"\x1b[2K\r  target {target}\n"
            f"\x1b[2K\r  trial  {trial}\n"
            f"\x1b[2K\r  passwd {password}"
            f"\x1b[3A"
        )
        out.flush()

    def on_attempt(pos, guess, recovered, matched, trial_byte):
        attempts[0] += 1
        if not tty:
            return
        ciphertext_pw[:] = recovered
        render(pos, guess, trial_byte, matched, len(recovered))
        if delay:
            time.sleep(delay)

    plaintext = brute_decrypt(bf, ciphertext, on_attempt=on_attempt)
    if tty:
        out.write("\n\n\n\n")
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
