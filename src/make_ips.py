#!/usr/bin/env python3
"""Make an IPS patch from a base ROM and a patched ROM (the patched one may be longer).

usage: make_ips.py base.rom patched.rom out.ips
       make_ips.py --apply base.rom patch.ips out.rom     (check)

Every byte of the patched ROM that differs from the base, and every byte past the
end of the base, is written (runs of one value as RLE records), so the result
does not depend on how a patcher fills the extended part.
"""
import sys


def make(base, new):
    out = bytearray(b'PATCH')
    n = len(new)
    i = 0

    def changed(k):
        return k >= len(base) or base[k] != new[k]

    while i < n:
        if not changed(i):
            i += 1
            continue
        j = i
        while j < n and (changed(j) or (j + 1 < n and changed(j + 1) and j + 1 - i < 0xFFFF)) and j - i < 0xFFFF:
            j += 1
        chunk = new[i:j]
        # split into RLE runs (>= 8 equal bytes) and literal parts
        p = 0
        while p < len(chunk):
            r = p
            while r < len(chunk) and chunk[r] == chunk[p] and r - p < 0xFFFF:
                r += 1
            if r - p >= 8:
                off = i + p
                assert off < 0x1000000 and off != 0x454F46
                out += off.to_bytes(3, 'big') + b'\0\0' + (r - p).to_bytes(2, 'big') + bytes([chunk[p]])
                p = r
                continue
            q = p
            while q < len(chunk) and q - p < 0xFFFF:
                r = q
                while r < len(chunk) and chunk[r] == chunk[q]:
                    r += 1
                if r - q >= 8:
                    break
                q = r if r > q else q + 1
            off = i + p
            assert off < 0x1000000 and off != 0x454F46
            out += off.to_bytes(3, 'big') + (q - p).to_bytes(2, 'big') + chunk[p:q]
            p = q
        i = j
    out += b'EOF'
    return bytes(out)


def apply(base, ips):
    assert ips[:5] == b'PATCH'
    data = bytearray(base)
    p = 5
    while ips[p:p + 3] != b'EOF':
        off = int.from_bytes(ips[p:p + 3], 'big')
        size = int.from_bytes(ips[p + 3:p + 5], 'big')
        p += 5
        if size == 0:
            size = int.from_bytes(ips[p:p + 2], 'big')
            chunk = bytes([ips[p + 2]]) * size
            p += 3
        else:
            chunk = ips[p:p + size]
            p += size
        if len(data) < off + size:
            data += bytes(off + size - len(data))
        data[off:off + size] = chunk
    return bytes(data)


if __name__ == '__main__':
    if sys.argv[1] == '--apply':
        base, ips, out = sys.argv[2:5]
        open(out, 'wb').write(apply(open(base, 'rb').read(), open(ips, 'rb').read()))
    else:
        base, new, out = sys.argv[1:4]
        b = open(base, 'rb').read()
        n = open(new, 'rb').read()
        ips = make(b, n)
        assert apply(b, ips) == n
        open(out, 'wb').write(ips)
        print(out, len(ips), 'bytes')
