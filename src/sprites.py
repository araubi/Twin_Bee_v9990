#!/usr/bin/env python3
"""MSX sprite (pattern,colour) -> V9990 sprite art mapping and data generation.

Sprite contexts (ebb8, ebf2!=0):
  n0..n4 : normal stage play, MSX pattern set of stage ebb8  -> art of fase ebb8+1
  b1..b4,b0 : boss fight (ebf2 != 0) with boss set loaded   -> art of fase ebb8 (b0 -> fase 5)

Art references: ('3', cell) / ('4', cell) = cells of 'fase N - paleta 3/4.png' of the context's fase.
              ('X', fase, sheet, cell) = cell of another fase, colour-remapped into this fase's palette.
"""
from PIL import Image

import paths
SRC = paths.ART
MAG = (255, 0, 216)

CTX_FASE = {'n0': 1, 'b1': 1, 'n1': 2, 'b2': 2, 'n2': 3, 'b3': 3, 'n3': 4, 'b4': 4, 'n4': 5, 'b0': 5}
CTX_ORDER = ['n0', 'b0', 'n1', 'b1', 'n2', 'b2', 'n3', 'b3', 'n4', 'b4']   # index = ebb8*2 + boss

# colour groups of the TMS palette
YEL = (10, 11)
BLU = (4, 5, 7)
WHT = (14, 15)
RED = (6, 8, 9, 13)
GRN = (2, 3, 12)
BLK = (1,)         # black bell (deadly)

# ---------------------------------------------------------------- common patterns
# references are cells of FASE 1 sheets; they get translated to identical cells
# of the other fases (or imported when missing)
BEE = 'BEE'   # marker: bee overlay frame (WinBee variant = cell+16)
COMMON = {
    0x00: {WHT: [('S', 0)], None: None},   # bee body (drawn by the overlay); white = crash flash: white silhouette
    # TwinBee overlays (body 00h) / WinBee overlays (body 0Ch)
    0x04: [('3', 0)], 0x08: [('3', 16)], 0x44: [('3', 0)], 0x48: [('3', 16)],
    0x10: [('3', 1)], 0x14: [('3', 17)], 0x54: [('3', 1)], 0x58: [('3', 17)],
    0x0c: {WHT: [('S', 1)], None: None},
    0x18: [('4', 18)],
    0x1c: [('4', 18)],               # outline of the crashed bee (with 20h)
    0x20: [('3', 54)],
    0x24: [('3', 58)],
    0x28: [('3', 53)],
    0x2c: {YEL: [('3', 34)], BLU: [('3', 35)], WHT: [('3', 39)], RED: [('4', 27)], GRN: [('G', 0)], BLK: [('K', 0)], None: [('3', 34)]},
    0x64: {YEL: [('3', 55)], BLU: [('3', 57)], WHT: [('3', 41)], RED: [('4', 29)], GRN: [('G', 2)], BLK: [('K', 2)], None: [('3', 55)]},
    0x68: {YEL: [('3', 38)], BLU: [('3', 56)], WHT: [('3', 40)], RED: [('4', 28)], GRN: [('G', 1)], BLK: [('K', 1)], None: [('3', 38)]},
    0x30: {RED: [('3', 37)], None: [('3', 36)]},
    0x34: [('3', 51)],
    0x38: [('3', 52)],
    0x3c: [('4', 35)],
    0x40: [('4', 34)],
    0x4c: [('3', 4)], 0x50: [('3', 5)], 0x5c: [('3', 4)], 0x60: [('3', 5)],
    0x6c: {YEL: [('3', 20)], None: [('3', 42)]},
    0x70: {YEL: [('3', 21)], None: [('3', 43)]},
    0x74: [('3', 22)],
    0x78: [('3', 48)], 0x7c: [('3', 49)], 0x80: [('3', 32)], 0x84: [('3', 33)],
    0x88: [('4', 23)], 0x8c: [('4', 24)], 0x90: [('4', 25)], 0x94: [('4', 26)],
    0x98: [('4', 30)], 0x9c: [('4', 31)],
    0xa0: [('4', 13)], 0xa4: [('4', 14)], 0xa8: [('4', 11)], 0xac: [('4', 12)],
}

# explosion of a boss (patterns b0..cc of every boss set)
BOSS_EXPL = {0xb0: [('3', 10)], 0xb4: [('3', 11)], 0xb8: [('3', 26)], 0xbc: [('3', 27)],
             0xc0: [('3', 12)], 0xc4: [('3', 13)], 0xc8: [('3', 28)], 0xcc: [('3', 29)]}

# stage specific patterns (b0..fc), references into the context's own fase sheets
SPECIFIC = {
    'n0': {0xb0: [('3', 50), ('4', 36)], 0xb4: [('4', 17)], 0xb8: [('4', 16)], 0xbc: [('3', 9)],
           0xc0: [('4', 32)], 0xc4: [('4', 33)], 0xc8: [('4', 19)]},
    'b1': {**BOSS_EXPL, **{0xd0: [('4', 21)], 0xd4: [('4', 22)], 0xd8: [('4', 37)], 0xdc: [('4', 38)],
                             0xe0: [('3', 8)]}},
    'n1': {0xb0: [('4', 16)], 0xb4: [('4', 17)], 0xb8: [('4', 18)], 0xbc: [('3', 45)], 0xc0: [('4', 20)],
           0xc4: [('4', 30)], 0xc8: [('4', 31)], 0xcc: [('3', 9), ('4', 39)], 0xd0: [('4', 32)], 0xd4: [('4', 33)],
           0xd8: [('4', 21)], 0xdc: [('4', 22)], 0xe0: [('3', 8)]},
    'b2': {**BOSS_EXPL, **{0xd0: 'AUTO', 0xd4: 'AUTO', 0xd8: 'AUTO', 0xdc: 'AUTO',
                             0xe0: [('3', 59)], 0xe4: [('3', 60)], 0xe8: [('3', 61)]}},
    'n2': {0xb0: [('4', 16)], 0xb4: 'AUTO', 0xb8: 'AUTO', 0xbc: [('4', 39)], 0xc0: [('4', 40)],
           0xc4: 'AUTO', 0xc8: 'AUTO', 0xcc: 'AUTO', 0xd0: 'AUTO', 0xd4: [('4', 43)], 0xd8: [('4', 17)],
           0xdc: [('4', 36)], 0xe0: [('3', 59)], 0xe4: [('3', 60)], 0xe8: [('3', 61)]},
    'b3': {**BOSS_EXPL, **{0xd0: [('4', 21)], 0xd4: [('4', 22)], 0xd8: [('4', 37)], 0xdc: [('4', 38)],
                             0xe0: [('4', 42)], 0xe4: [('4', 41)], 0xe8: [('3', 61)]}},
    'n3': {0xb0: [('3', 66)], 0xb4: [('3', 67)], 0xb8: [('4', 42)], 0xbc: [('4', 43)], 0xc0: 'AUTO',
           0xc4: 'AUTO', 0xc8: 'AUTO', 0xcc: 'AUTO', 0xd0: 'AUTO', 0xd4: 'AUTO', 0xd8: [('3', 68)],
           0xdc: [('3', 68)], 0xe0: [('4', 41)], 0xe4: [('4', 46)], 0xe8: [('3', 61)]},
    'b4': {**BOSS_EXPL, **{0xd0: 'AUTO', 0xd4: 'AUTO', 0xd8: 'AUTO', 0xdc: 'AUTO', 0xe0: 'AUTO',
                             0xe4: [('4', 46)], 0xe8: [('3', 61)]}},
    'n4': {0xb0: [('4', 40)], 0xb4: [('4', 41)], 0xb8: [('4', 46)], 0xbc: [('4', 47)], 0xc0: [('4', 48)],
           0xc4: [('4', 49)], 0xc8: 'AUTO', 0xcc: 'AUTO', 0xd0: 'AUTO', 0xd4: 'AUTO', 0xd8: [('4', 56)],
           0xdc: [('4', 39)], 0xe0: [('4', 37)], 0xe4: [('4', 38)], 0xe8: [('4', 45)], 0xec: 'AUTO',
           0xf0: 'AUTO', 0xf4: 'AUTO'},
    'b0': {**BOSS_EXPL, **{0xd0: [('3', 14)], 0xd4: [('3', 15)], 0xd8: [('3', 30)], 0xdc: [('3', 31)],
                             0xe0: 'AUTO', 0xe4: 'AUTO', 0xe8: 'AUTO'}},
}


# ---------------------------------------------------------------- helpers
def sheet(f, k):
    return Image.open(SRC + 'fase %d/fase %d - paleta %d.png' % (f, f, k))


def sheet_pal(f, k):
    p = sheet(f, k).getpalette()[:48]
    return [tuple(p[i * 3:i * 3 + 3]) for i in range(16)]


def cell_rgb(f, k, idx):
    im = sheet(f, k).convert('RGB')
    x, y = (idx % 16) * 16, (idx // 16) * 16
    return [im.getpixel((x + i % 16, y + i // 16)) for i in range(256)]


def cell_idx(f, k, idx):
    im = sheet(f, k)
    assert im.mode == 'P'
    x, y = (idx % 16) * 16, (idx // 16) * 16
    return [im.getpixel((x + i % 16, y + i // 16)) for i in range(256)]


def ncells(f, k):
    return (sheet(f, k).height // 16 - 1) * 16


def remap(rgb, pal):
    out = []
    for c in rgb:
        if c == MAG:
            out.append(0)
        else:
            best = min(range(1, 16), key=lambda i: sum((a - b) ** 2 for a, b in zip(pal[i], c)))
            out.append(best)
    return out


_GB = {}


def find_green_bells(f, k=1, xs=(0, 16, 32)):
    """bells of fase 1 sheet k at bottom row x positions xs (green: k=1, black: k=2),
    searched in the bottom rows of both 'paleta 1' and 'paleta 2' of fase f, with
    the same shape and a similar colour.  Returns [(pixels, palette 0/1)]."""
    key = (f, k, tuple(xs))
    if key in _GB:
        return _GB[key]
    import os, json
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'bells2_%d_%d_%d.json' % (f, k, xs[0]))
    if os.path.exists(cache):
        _GB[key] = [tuple(x) for x in json.load(open(cache))]
        return _GB[key]
    res = _find_green_bells(f, k, xs)
    json.dump(res, open(cache, 'w'))
    _GB[key] = res
    return res


def _mean(cs):
    cs = [c for c in cs if c != MAG]
    return tuple(sum(c[i] for c in cs) / max(1, len(cs)) for i in range(3))


def _find_green_bells(f, k, xs):
    ref = sheet(1, k).convert('RGB')
    h = ref.height
    refcells = []
    for x0 in xs:
        refcells.append([ref.getpixel((x0 + x, h - 32 + y)) for y in range(16) for x in range(16)])
    res = []
    for rc in refcells:
        mask = [c != MAG for c in rc]
        rmean = _mean(rc)
        best = None
        for kk in (1, 2):
            im = sheet(f, kk).convert('RGB')
            W, H = im.size
            px = im.load()
            for yy in range(max(0, H - 64), H - 16 + 1):
                for xx in range(0, W - 15):
                    sc = 0
                    cs = []
                    for i in range(256):
                        c = px[xx + i % 16, yy + i // 16]
                        cs.append(c)
                        if (c != MAG) == mask[i]:
                            sc += 1
                    if sc < 240:
                        continue
                    m = _mean(cs)
                    dist = sum((a - b) ** 2 for a, b in zip(m, rmean)) ** 0.5
                    if dist > 60:
                        continue
                    cand = (sc - dist / 10, kk, cs)
                    if best is None or cand[0] > best[0]:
                        best = cand
        if best is None:      # not in this fase: import the fase 1 art
            res.append((remap(rc, sheet_pal(f, k)), k - 1))
        else:
            res.append((remap(best[2], sheet_pal(f, best[1])), best[1] - 1))
    return res


class FaseArt:
    """sprite pattern set for one fase: pattern numbers 0..255"""

    def __init__(self, f):
        self.f = f
        self.pals = [sheet_pal(f, 1), sheet_pal(f, 2), sheet_pal(f, 3), sheet_pal(f, 4)]
        self.patterns = {}     # number -> 256 indices
        self.n3 = ncells(f, 3)
        self.n4 = ncells(f, 4)
        for i in range(self.n3):
            self.patterns[i] = cell_idx(f, 3, i)
        for i in range(self.n4):
            self.patterns[80 + i] = cell_idx(f, 4, i)
        self.next_free = 144
        self.imports = {}
        import objects as OB
        v = open(paths.REF + 'stage%d.vram' % (f - 1), 'rb').read()
        self.objects = []
        for pn, pix, how in OB.object_art(f, v):
            self.objects.append((self.alloc(pix), pn))
        self.black = [(self.alloc(b), p) for b, p in find_green_bells(f, 2, (64, 80, 96))]
        self.green = [(self.alloc(g), p) for g, p in find_green_bells(f, 1, (0, 16, 32))]

    def alloc(self, pix):
        n = self.next_free
        assert n < 0xF0   # pattern rows 15 overlap the sprite attribute table
        self.patterns[n] = pix
        self.next_free += 1
        return n

    def ref(self, r):
        """returns (pattern number, palette number)"""
        if r[0] == '3':
            return r[1], 2
        if r[0] == '4':
            return 80 + r[1], 3
        if r[0] == 'G':
            return self.green[r[1]]
        if r[0] == 'K':
            return self.black[r[1]]
        if r[0] == 'S':
            # white silhouette of a sheet 3 cell (the MSX shows the bee all white when hit)
            key = ('S', r[1])
            if key not in self.imports:
                pal = self.pals[2]
                white = min(range(1, 16), key=lambda i: sum((255 - c) ** 2 for c in pal[i][:3]))
                self.imports[key] = self.alloc([white if v else 0 for v in self.patterns[r[1]]])
            return self.imports[key], 2
        raise ValueError(r)

    def common_ref(self, r):
        """translate a fase-1 reference to this fase (identical cell or import)"""
        if r[0] in 'GKS' or self.f == 1:
            return self.ref(r)
        k = int(r[0])
        rgb = cell_rgb(1, k, r[1])
        # same cell repainted for this fase (same place in the sheet, same shape)?
        if r[1] < ncells(self.f, k):
            own = cell_rgb(self.f, k, r[1])
            m1 = [c != MAG for c in rgb]
            m2 = [c != MAG for c in own]
            best = 0
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    inter = union = 0
                    for i in range(256):
                        x, y = i % 16 + dx, i // 16 + dy
                        b = m2[y * 16 + x] if 0 <= x < 16 and 0 <= y < 16 else False
                        inter += m1[i] and b
                        union += m1[i] or b
                    if union:
                        best = max(best, inter / union)
            if best >= 0.8:
                return self.ref(r)
        # identical cell (in RGB) in same sheet of this fase?
        for i in range(ncells(self.f, k)):
            if cell_rgb(self.f, k, i) == rgb:
                return self.ref((r[0], i))
        key = (k, r[1])
        if key not in self.imports:
            self.imports[key] = self.alloc(remap(rgb, self.pals[k - 1]))
        return self.imports[key], k - 1

    def area_image(self):
        """V9990 P1 sprite pattern area (16 sprites per 2KB row)"""
        nrows = (max(self.patterns) // 16) + 1
        data = bytearray(nrows * 2048)
        for n, pix in self.patterns.items():
            base = 128 * (n & 0xF0) + 8 * (n & 15)
            for y in range(16):
                for x in range(0, 16, 2):
                    data[base + y * 128 + x // 2] = (pix[y * 16 + x] << 4) | pix[y * 16 + x + 1]
        return bytes(data)


def auto_ref(ctx, p, vram):
    import json
    m = json.load(open(paths.AUTOMAP))
    e = m.get(ctx, {})
    for k, v in e.items():
        if int(k[:2], 16) == p:
            return [tuple(x[:2]) for x in v['ents']], [tuple(x[2:]) for x in v['ents']]
    return None, None


def build_context(ctx, art):
    """returns table[64*16] -> entry index, and entries list (each: flags, [(pat, attr, dx, dy)...])"""
    import json
    am = json.load(open(paths.AUTOMAP))
    entries = [None]        # index 0 = hide
    ekey = {}

    def add(flags, subs):
        key = (flags, tuple(subs))
        if key not in ekey:
            ekey[key] = len(entries)
            entries.append(key)
        return ekey[key]

    table = bytearray(64 * 16)
    spec = SPECIFIC.get(ctx, {})
    for p in range(0, 256, 4):
        if p in spec:
            v = spec[p]
            common = False
        elif p in COMMON:
            v = COMMON[p]
            common = True
        elif p >= 0xb0:
            v = 'AUTO'          # anything else stage specific: best automatic match
            common = False
        else:
            continue
        if v == 'AUTO':
            a = am.get(ctx, {})
            ks = [k for k in a if int(k[:2], 16) == p]
            if not ks:
                continue
            v = [tuple(x[:2]) for x in a[ks[0]]['ents']]
            shifts = [tuple(x[2:]) for x in a[ks[0]]['ents']]
        else:
            shifts = None
        for c in range(16):
            if v is None:
                idx = 0
            elif isinstance(v, tuple) and v[0] == BEE:
                pat, pal = art.common_ref(('3', v[1]))
                idx = add(1, [(pat, pal, 0, 0)])
            else:
                lst = v
                if isinstance(v, dict):
                    lst = None
                    found = False
                    for grp, l in v.items():
                        if grp is not None and c in grp:
                            lst = l
                            found = True
                    if not found:
                        lst = v[None]
                if lst is None:
                    table[(p >> 2) * 16 + c] = 0
                    continue
                subs = []
                for j, r in enumerate(lst):
                    dx, dy = (0, 0)
                    if len(r) == 4:          # (sheet, cell, dx, dy): art drawn at -dx,-dy
                        dx, dy = r[2], r[3]
                        r = r[:2]
                    pat, pal = art.common_ref(r) if common else art.ref(r)
                    if shifts:
                        dx, dy = shifts[j]
                    subs.append((pat, pal, dx, dy))
                idx = add(0, subs)
            table[(p >> 2) * 16 + c] = idx
    assert len(entries) <= 256
    return table, entries


def entries_blob(entries):
    """13 byte records: flags|count, then 3x (dy, pattern, dx+64, attr), stored as
    13 pages of 256 bytes (byte k of entry n at k*256 + n: the driver steps with inc h)"""
    recs = []
    for e in entries:
        if e is None:
            recs.append(bytes(13))
            continue
        flags, subs = e
        rec = bytearray([len(subs) | (0x80 if flags & 1 else 0)])
        for pat, pal, dx, dy in subs:
            # MSX shape is at (dx,dy) inside the art cell -> art must be drawn at -dx,-dy
            # (driver order: dy, pattern, dx + 64, attr)
            assert -64 <= -dx <= 191, dx
            rec += bytes([(-dy) & 255, pat, (-dx + 64) & 255, (pal << 6)])
        assert len(subs) <= 3, subs
        rec += bytes(13 - len(rec))
        recs.append(bytes(rec))
    assert len(recs) <= 256
    recs += [bytes(13)] * (256 - len(recs))
    return bytes(recs[n][k] for k in range(13) for n in range(256))