#!/usr/bin/env python3
"""Extract the signing certificate (DER) info from an APK.

Reads the APK Signature Scheme v2/v3 blocks (the scheme FinaSU's repack
apksigner produces), prints the DER certificate size and its SHA-256 in the
exact format FinaSU's Kbuild expects for the second trusted manager slot:

    SIZE_HEX = "0x%04x" % der_size
    SHA256   = lowercase hex digest of the DER certificate

Usage:
    python3 extract_manager_cert.py <apk> [<apk> ...]

Prints one line per unique certificate:  "<size_hex> <sha256>"
Keep in sync with the inline parser in .github/workflows/get-manager.yml.
"""

import hashlib
import struct
import sys

V2_BLOCK_ID = 0x7109871A
V3_BLOCK_ID = 0xF05368C0


def u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def u64(buf, off):
    return struct.unpack_from("<Q", buf, off)[0]


def extract_certs(data):
    """Yield DER certificates from the APK signing block, if present."""
    magic_off = data.find(b"APK Sig Block 42")
    if magic_off == -1:
        return
    block_end = magic_off + 16
    block_size = u64(data, magic_off - 8)
    block_start = block_end - block_size - 8
    pairs = data[block_start + 8 : block_end - 24]
    # Pair framing uses uint64 length prefixes; everything inside the
    # v2/v3 blocks uses uint32.
    off = 0
    while off + 12 <= len(pairs):
        pair_len = u64(pairs, off)
        off += 8
        pair_id = u32(pairs, off)
        payload = pairs[off + 4 : off + pair_len]
        if pair_id in (V2_BLOCK_ID, V3_BLOCK_ID):
            q = 4
            signers_end = 4 + u32(payload, 0)
            while q < signers_end:
                signer_len = u32(payload, q)
                q += 4
                signer = payload[q : q + signer_len]
                q += signer_len
                sd_len = u32(signer, 0)
                sd = signer[4 : 4 + sd_len]
                r = 0
                digests_len = u32(sd, r)
                r += 4 + digests_len
                certs_len = u32(sd, r)
                r += 4
                cert_section = sd[r : r + certs_len]
                c = 0
                while c < certs_len:
                    cert_len = u32(cert_section, c)
                    c += 4
                    yield cert_section[c : c + cert_len]
                    c += cert_len
        off += pair_len


def main():
    if len(sys.argv) < 2:
        print("usage: extract_manager_cert.py <apk> [<apk> ...]", file=sys.stderr)
        return 2
    seen = set()
    found = False
    for path in sys.argv[1:]:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            continue
        for der in extract_certs(data):
            digest = hashlib.sha256(der).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            found = True
            print("0x%04x %s" % (len(der), digest))
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
