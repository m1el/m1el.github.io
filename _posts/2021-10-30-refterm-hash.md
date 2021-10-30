---
layout: post
permalink: /refterm-hash/
title: How (Not) to Design a Hash Function
date: 2021-10-30T20:13:11Z
---

Recently, Casey Muratori has implemented a [proof-of-concept terminal][refterm-git],
which is designed around fast input processing and rendering.  This is an important
and commendable effort, since the vast majority of software performs tens to
thouthands of times slower than it can.<sup>\[citation needed\]</sup>

One of the design choices of refterm is to use a hash table to cache glyph rendering.
The key in this table is the UTF-8 string of a single glyph.  To avoid string
allocations, the hash value of the glyph bytes is used as a key instead.

When Casey got asked about the possibility of hash collisions on stream,
he responded with a claim that the hash function used in refterm is "cryptographically
secure", and the complexity to find collision is about 2^64 operations.
After analyzing the code for the hash function used in refterm, a few flaws
were found in the hash function, and O(1) attacks were discovered.

<!-- more -->

All the source code presented here was the most recent refterm code at the moment
of writing this post, commit 20a063f3700ac4c2913076864cb560301e76b2dc.
The hash function `ComputeGlyphHash` is loacted in [refterm\_example\_source\_buffer.c:166][refterm-hash].

## Operation of the hash

- The hash value is initialized to input length
- The hash value is `xor`ed with the provided seed value, which is always equal to `DefaultSeed`
- For each full 16 bytes chunk, the following bit mixing method is used:
    - the hash value is `xor`ed with the input chunk
    - the hash value is fed four times through `_mm_aesdec_si128` with zero key
- For the last chunk, it is zero padded to 16 bytes
- And fed through the same bit mixing method as described above

In FP terms, this could be described as:

```Rust
ComputeHash(Input) = ZeroPad(Input, 16).chunks_exact(16)
    .fold(Length ^ DefaultSeed, |Hash, Chunk| AesDec4Times(Hash ^ Chunk, Zero))
```

## Flaw 1: Padding weakness

The [input padding][padding-src] is done by zero-padding.  This means that
inputs that if the last block ends with zeros, the result of processing this
block is going to be the same as if that block was right-trimmed of nul bytes.

```
char Temp[16];
__movsb((unsigned char *)Temp, At, Overhang);
__m128i In = _mm_loadu_si128((__m128i *)Temp);
In = _mm_and_si128(In, _mm_loadu_si128((__m128i *)(OverhangMask + 16 - Overhang)));
```

Since the hash value of input is initialized with the input length, which is then
`xor`ed with the first block, the attack is a little bit more complex.
The first byte (in little-endian systems) needs to be `xor`ed with the `xor` of input lengths.
For example, if the input is `""` (empty string), and we append a nul byte `"\x00"`,
since the length is 1, the first byte will be `xor`ed to `"\x01"`.
If we use the value `0x01` for the first byte, the produced hash of the string
`"\x01"` will be the same as the hash of the string `""`.

Example of collisions:

```
message: "",      hash: [41148b628ab49fce6d55977058831078]
message: "\x01",  hash: [41148b628ab49fce6d55977058831078]
message: "A",     hash: [86dd41d6a69d8f979dc9c5ca6fc27cce]
message: "B\x00", hash: [86dd41d6a69d8f979dc9c5ca6fc27cce]
message: "BAAAAAAAAAAAAAAA",     hash: [32b05cfcaa74f585fc6c4fd7cef4a99]
message: "CAAAAAAAAAAAAAAA\x00", hash: [32b05cfcaa74f585fc6c4fd7cef4a99]
```

## Mitigating Padding Attack

One of the mitigations for the padding attack is to initialize padding to some
value dependending on overhang length.  If done correctly, no inputs
of different length will produce the same padded block.  A computationally
inexpensive solution would be to set padding bytes to overhang length.
This only works if the overhang chunk is always calculated.

Example code:

```C
    // Read the last block
    char Temp[16];
    __movsb((unsigned char *)Temp, At, Overhang);
    __m128i In = _mm_loadu_si128((__m128i *)Temp);
    // Compute padding depending on overhang length to prevent padding attacks
    __m128i Mask = _mm_loadu_si128((__m128i *)(OverhangMask + 16 - Overhang));
    // _mm_blendv_epi8 requires SSE4, so we use `andnot` + `and` instead
    // In = _mm_blendv_epi8(Mask, In, _mm_set1_epi8((char)Overhang));
    __m128i Padding = _mm_andnot_si128(Mask, _mm_set1_epi8((char)Overhang));
    In = _mm_or_si128(_mm_and_si128(Mask, In), Padding);
    // At this point, In has been padded securely.
```

```
Before:
Input: []   -> Padded [00 00 00 00...]
Input: [00] -> Padded [00 00 00 00...]
After:
Input: []   -> Padded [00 00 00 00...]
Input: [00] -> Padded [00 01 01 01...]
```

## Flaw 2: Invertible hashing operations

AES encryption is symmetric encryption.  Which means that encryption and decryption
functions are invertible, given that you know the encryption key.
Since the key used for bit mixing operations is constant (all zeros),
the bit mixing operations are easily invertible.

- `NextHash = AesDec4Times(PreviousHash ^ Chunk, 0)`

Given `AesDec4Times` is invertible,
- `InvAesDec4Times(NextHash, 0) = PreviousHash ^ Chunk`.
- `Chunk = PreviousHash ^ InvAesDec4Times(NextHash, 0)`.
- `PreviousHash = Chunk ^ InvAesDec4Times(NextHash, 0)`.

This equation allows us to choose two out of three variables arbitrarily.
Given fixed `PreviousHash` and `NextHash`, we can calculate a `Chunk` that will
produce `NextHash` after running one round of `ComputeGlyphHash`.
Also, given `NextHash` and `Chunk`, we can calculate the `PreviousHash` value.

This is pretty bad news for this hash function, since it allows us to:
- Invert a round of hashing, thus calculating the exact value for one input hashes.
Given `Hash`, for one chunk we know that `InputLength ^ DefaultSeed ^ Chunk = InvAesDec4Times(Hash)`,
thus `InputLength ^ Chunk = InvAesDec4Times(Hash) ^ DefaultSeed`.
- Prepend a block to change the hash to an arbitrary value.
- Insert a block to change the hash to an arbitrary value.
- Append a block to change the hash to an arbitrary value.

## Actually Inverting `_mm_aesdec_si128(Hash, Zero)`

The has function is using AES primitives in a non-standard way, so some work
is required to invert the operation.

Let's look at the operation of four AES-NI intrinsics:
[\_mm\_aesdec\_si128][intel-aesdec], [\_mm\_aesdeclast\_si128][intel-aesdeclast],
[\_mm\_aesenc\_si128][intel-aesenc], [\_mm\_aesenclast\_si128][intel-aesenclast]:

```
_mm_aesdec_si128
a[127:0] := InvShiftRows(a[127:0])
a[127:0] := InvSubBytes(a[127:0])
a[127:0] := InvMixColumns(a[127:0])
dst[127:0] := a[127:0] XOR RoundKey[127:0]

_mm_aesdeclast_si128
a[127:0] := InvShiftRows(a[127:0])
a[127:0] := InvSubBytes(a[127:0])
dst[127:0] := a[127:0] XOR RoundKey[127:0]

_mm_aesenc_si128
a[127:0] := ShiftRows(a[127:0])
a[127:0] := SubBytes(a[127:0])
a[127:0] := MixColumns(a[127:0])
dst[127:0] := a[127:0] XOR RoundKey[127:0]

_mm_aesenclast_si128
a[127:0] := ShiftRows(a[127:0])
a[127:0] := SubBytes(a[127:0])
dst[127:0] := a[127:0] XOR RoundKey[127:0]
```

Since `RoundKey` is always zero in our case, the `xor` operations may be omitted below.

To invert `_mm_aesdec_si128`, we need to run it in reverse, with the opposite operations.
`InvShiftRows -> InvSubBytes -> InvMixColumns` is inverted to: `MixColumns -> SubBytes -> ShiftRows`.

Initially, `InvAesDec` was implemented using primitives from [Tiny AES in C][tinyaes],

```C
__m128i InvAesDec(__m128i data, __m128i key) {
    // Implemented in terms of aes primitives, using tiny-aes
    data = _mm_xor_si128(data, key);
    MixColumns((state_t*)&data);
    SubBytes((state_t*)&data);
    ShiftRows((state_t*)&data);
    return data;
}
```

Furthermore, Discord user `@davee` has helpfully pointed out that the same operation
can be implemented using AES-NI intrinsics the following way:

```C
__m128i InvAesDec(__m128i data, __m128i key) {
    // Implemented using AES-NI intrinsics, credit to @davee
    data = _mm_xor_si128(data, key);
    __m128i zero = _mm_setzero_si128();
    data = _mm_aesenc_si128(_mm_aesdeclast_si128(data, zero), zero);
    return _mm_aesenclast_si128(data, zero);
}
```

Why does this work?  Let's write out the operations:

```
// aesdec(data, key)
// the operation we would like to invert
InvShiftRows, InvSubBytes, InvMixColumns, XOR Key,
// xor key
XOR Key,
// aesdeclast(data, zero)
InvShiftRows, InvSubBytes, XOR zero,
// aesenc(data, zero)
ShiftRows, SubBytes, MixColumns, XOR zero,
// aesenclast(daat)
ShiftRows, SubBytes, XOR zero,
```

All `XOR zero` operations are no-ops, and can be omitted.
Two `XOR Key` operations are next to each other, so they cancel each other.
So we are left with these ten:

```
InvShiftRows, InvSubBytes, InvMixColumns,
InvShiftRows, InvSubBytes,
ShiftRows, SubBytes, MixColumns,
ShiftRows, SubBytes,
```

Now, we need to delve a little bit about the inner workings of AES.
We don't need to know much, but these few things:
1. `InvX` operations invert `X` operations.
2. `ShiftRows` and `InvShiftRows` operations swap bytes around.
3. `SubBytes` and `InvSubBytes` substitute bytes.
4. For the current purpose, `MixColumns` is viewed as a black box that doesn't commute with anything else.

Because of what `(Inf)ShiftRows`. and `(Inv)SubBytes` do, they commute.
Byte substitution is position-independent, and byte swapping is independent of contents.

Let's rewrite the operations by swapping consecutive `InvShiftRows` and `InvSubBytes`:

```
InvSubBytes(5), InvShiftRows(4), InvMixColumns(3),
InvSubBytes(2), InvShiftRows(1),
ShiftRows(1), SubBytes(2), MixColumns(3),
ShiftRows(4), SubBytes(5),
```

Now we can see that the inverse operations are paired up, so they all cancel out.
Therefore, `InvAesDec(AesDec(data, key), key)` is a no-oop. QED

Since we're interested in inverting four rounds of `AesEnc`, rather than
calling `InvAesDec` four times, we can optimize this operation.
Note: the `xor` operations can be omitted in this case since the key is zero.

```C
__m128i InvAesDecX4(__m128i data, __m128i key) {
    __m128i zero = _mm_setzero_si128();
    data = _mm_xor_si128(data, key);
    data = _mm_aesdeclast_si128(data, zero);
    data = _mm_aesenc_si128(data, zero);
    data = _mm_xor_si128(data, key);
    data = _mm_aesenc_si128(data, zero);
    data = _mm_xor_si128(data, key);
    data = _mm_aesenc_si128(data, zero);
    data = _mm_xor_si128(data, key);
    data = _mm_aesenc_si128(data, zero);
    return _mm_aesenclast_si128(data, zero);
}
```

This function allows us to perform all of the attacks mentioned before.

## Demonstrating these attacks

```
Demonstrating invert attack, invert a hash up to 15 bytes
Note: due to padding attack, there are actually more messages
plaintext: [51, 77, 65, 72, 74, 79, 31, 32, 33]
hash:      [8, 6e, c4, db, 1f, d1, 5b, b7, 95, d5, 44, ea, 5, 2c, bd, 4b]
recovered: [51, 77, 65, 72, 74, 79, 31, 32, 33]
hash:      [8, 6e, c4, db, 1f, d1, 5b, b7, 95, d5, 44, ea, 5, 2c, bd, 4b]

Demonstrating prefix attack, prepend a block and avoid affecting the hash
message: [68, 65, 6c, 6c, 6f]
hash:    [c1, 1e, 0, 16, 4a, f5, 67, 27, e, c1, 1c, ea, 39, 74, e6, 4b]
prefix:  [1d, a4, 56, e6, e9, c3, 64, 70, 5c, e2, 8e, 11, ab, 23, a7, 9c]
forgery: [1d, a4, 56, e6, e9, c3, 64, 70, 5c, e2, 8e, 11, ab, 23, a7, 9c, 68, 65, 6c, 6c, 6f]
hash:    [c1, 1e, 0, 16, 4a, f5, 67, 27, e, c1, 1c, ea, 39, 74, e6, 4b]

Demonstrating chosen prefix attack, append a block and produce arbitrary hash
prefix:  [68, 65, 6c, 6c, 6f]
forgery: [68, 65, 6c, 6c, 6f, 41, 41, 41, 41, 41, 41, 41, 41, 41, 41, 41, be, c2, 21, f0, 83, 9d, a6, 0, 61, 58, 2c, ac, f7, 33, 74, b2]
hash:    [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

Demonstrating preimage attack, prepend a block and produce arbitrary hash
suffix:    [68, 65, 6c, 6c, 6f]
goal hash: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
prefix:    [f4, 47, d8, c8, 25, 21, 17, 41, 91, 82, 83, 31, ca, 60, 37, 4b]
message:   [f4, 47, d8, c8, 25, 21, 17, 41, 91, 82, 83, 31, ca, 60, 37, 4b, 68, 65, 6c, 6c, 6f]
hash:      [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
```

The code for these attacks is available at [github.com/m1el/refterm-hash-break][refterm-hash-break].

## Mitigating invertible hash operations

To mitigate these attacks, we take a look at publicly available construction of one-way functions.
The hash function in refterm is most similar to [Davies-Meyer][wiki-davies-meyer] compression method,
given a cryptographically secure symmetrical encryption function `Encrypt`, produces a secure one-way function.
It can be expressed in FP terms the following way:

```Rust
ComputeHash(Input) = SecurePad(Input, 16).chunks_exact(16)
    .fold(Zero, |Hash, Chunk| Hash ^ Encrypt(Hash, Chunk))
```

The implementation of this construction for refterm bit mixing operation would look like this:

```C
__m128i PreviousHash = HashValue;
HashValue = _mm_aesdec_si128(HashValue, In);
HashValue = _mm_aesdec_si128(HashValue, In);
HashValue = _mm_aesdec_si128(HashValue, In);
HashValue = _mm_aesdec_si128(HashValue, In);
HashValue = _mm_xor_si128(HashValue, PreviousHash);
```

Please note that this is using `AesDec4Times` as `Encrypt`, and it is __NOT__ cryptographically secure.
This is not a proper use of AES primitives, I suspect there may exist attacks on this hash function which I'm currently not aware of.
However, this provides significantly more security than previously existing hash function in refterm.

## Conclusions

Multiple weaknesses were found in refterm's `ComputeGlyphHash`, with practical demonstration of attacks.
This demonstrates that `ComputeGlyphHash` is not a cryptographically secure function.

Well known mitigations (proper padding, Davies-Meyer construction) were implemented and published.
The mitigations produced negligible performance losses.

These attacks and mitigations could have been found and implemented by anyone with cursory understanding of cryptography.

Do not roll your own crypto if you don't know what you're doing.

Do not claim that you have built a cryptographically secure hash function if you didn't pass it through nine circles of peer review hell.

The attack code is available here: [github.com/m1el/refterm-hash-break][refterm-hash-break].

The mitigations are available here: [github.com/cmuratori/refterm/pull/33][refterm-pr].

[refterm-git]: https://github.com/cmuratori/refterm/ "Refterm v2, a reference terminal renderer"
[refterm-hash]: https://github.com/cmuratori/refterm/blob/20a063f3700ac4c2913076864cb560301e76b2dc/refterm_example_source_buffer.c#L166-L227
[refterm-commit]: https://github.com/cmuratori/refterm/blob/20a063f3700ac4c2913076864cb560301e76b2dc/refterm_example_source_buffer.c#L213-L217
[padding-src]: https://github.com/cmuratori/refterm/blob/20a063f3700ac4c2913076864cb560301e76b2dc/refterm_example_source_buffer.c#L213-L217
[intel-aesdec]: https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html#text=aesdec_si128&ig_expand=262
[intel-aesdeclast]: https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html#text=aesdeclast_si128&ig_expand=267
[intel-aesenc]: https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html#text=aesenc_si128&ig_expand=272
[intel-aesenclast]: https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html#text=aesenclast_si128&ig_expand=277
[tinyaes]: https://github.com/kokke/tiny-AES-c "Tiny AES in C"
[refterm-hash-break]: https://github.com/m1el/refterm-hash-break "A POC for breaking refterm hash"
[wiki-davies-meyer]: https://en.wikipedia.org/wiki/One-way_compression_function#Davies%E2%80%93Meyer "One-way compression function: Davies–Meyer"
[refterm-pr]: https://github.com/cmuratori/refterm/pull/32
