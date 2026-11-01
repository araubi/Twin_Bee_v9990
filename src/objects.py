#!/usr/bin/env python3
"""Ground objects (2x2 chars drawn by the game into the name buffer) -> V9990 sprites."""
import numpy as np
from PIL import Image

import paths
SRC = paths.ART
REF = paths.REF
MAG = (255, 0, 216)
THRESH = 232
TMSPAL = [(0, 0, 0), (0, 0, 0), (33, 200, 66), (94, 220, 120), (84, 85, 237), (125, 118, 252), (212, 82, 77),
          (66, 235, 245), (252, 85, 84), (255, 121, 120), (212, 193, 84), (230, 206, 128), (33, 176, 59),
          (201, 91, 186), (204, 204, 204), (255, 255, 255)]


QUADS = [(74, 75, 76, 77), (70, 71, 72, 73), (82, 83, 84, 81), (78, 79, 80, 81), (64, 68, 66, 69), (64, 65, 66, 67),
         (114, 115, 116, 117), (112, 113, 116, 117), (60, 61, 62, 63), (104, 105, 106, 107), (108, 109, 110, 111),
         (85, 86, 87, 88), (89, 90, 91, 92), (93, 94, 95, 96), (97, 98, 99, 100), (101, 102, 97, 97), (103, 102, 97, 97)]


def quads():
    """2x2 character sets of the ground objects (game table at ACE1h of the original ROM)"""
    return list(QUADS)


def tms_quad(vram, q, third=1):
    """16x16 rgb list + mask (bg colour of the chars removed)"""
    pix = [[None] * 16 for _ in range(16)]
    bgs = {}
    for j, c in enumerate(q):
        for y in range(8):
            p = vram[0x2000 + third * 0x800 + c * 8 + y]
            co = vram[third * 0x800 + c * 8 + y]
            for x in range(8):
                fg = bool(p & (0x80 >> x))
                cc = (co >> 4) if fg else (co & 15)
                pix[(j // 2) * 8 + y][(j % 2) * 8 + x] = cc
                if not fg:
                    bgs[cc] = bgs.get(cc, 0) + 1
    # ground colour = most common background colour
    ground = max(bgs, key=bgs.get) if bgs else 0
    rgb = [[None if (pix[y][x] == ground or pix[y][x] == 0) else TMSPAL[pix[y][x]] for x in range(16)] for y in range(16)]
    return rgb


def sheet_region(f, k):
    im = Image.open(SRC + 'fase %d/fase %d - paleta %d.png' % (f, f, k))
    pal = im.getpalette()[:48]
    pal = [tuple(pal[i * 3:i * 3 + 3]) for i in range(16)]
    idx = np.array(im)                       # palette indices
    rgb = np.array(im.convert('RGB'))
    h = im.height
    bot = (h // 16) * 16 - 16                 # above the colour swatches
    top = 0 if k >= 3 else max(0, bot - 48)   # sprite sheets: everything, tile sheets: 3 bottom rows
    return idx[top:bot], rgb[top:bot], pal


def find_art(f, mask, sheets=(2, 1, 3, 4)):
    best = None
    m = np.array(mask, dtype=bool)
    if m.sum() == 0:
        return None
    for k in sheets:
        idx, rgb, pal = sheet_region(f, k)
        opaque = ~((rgb[:, :, 0] == 255) & (rgb[:, :, 1] == 0) & (rgb[:, :, 2] == 216))
        H, W = opaque.shape
        for yy in range(0, H - 15):
            for xx in range(0, W - 15):
                win = opaque[yy:yy + 16, xx:xx + 16]
                agree = (win == m).sum()
                if best is None or agree > best[0]:
                    best = (agree, k, yy, xx)
    agree, k, yy, xx = best
    if agree < THRESH:
        return None
    idx, rgb, pal = sheet_region(f, k)
    cell = idx[yy:yy + 16, xx:xx + 16]
    return k, [int(v) for v in cell.flatten()], agree


def nearest(pal, c):
    return min(range(1, 16), key=lambda i: sum((a - b) ** 2 for a, b in zip(pal[i], c)))


_ART_CACHE = {}


# where the artist may have drawn each ground object: tile sheets (bottom rows) or sprite sheets
QUAD_SHEETS = {12: (3, 4), 13: (3, 4), 14: (3, 4)}


def find_art_cached(f, qi, mask):
    key = (f, qi)
    if key not in _ART_CACHE:
        _ART_CACHE[key] = find_art(f, mask, QUAD_SHEETS.get(qi, (2, 1)))
    return _ART_CACHE[key]


def object_art(f, stage_vram):
    """returns list per quad: (palette number 0..3, 256 pixel indices, how)"""
    res = []
    pals = []
    for k in (1, 2, 3, 4):
        im = Image.open(SRC + 'fase %d/fase %d - paleta %d.png' % (f, f, k))
        p = im.getpalette()[:48]
        pals.append([tuple(p[i * 3:i * 3 + 3]) for i in range(16)])

    def best_palette(rgb):
        best = None
        for pn in range(4):
            err = 0
            pix = []
            for y in range(16):
                for x in range(16):
                    c = rgb[y][x]
                    if c is None:
                        pix.append(0)
                    else:
                        n = nearest(pals[pn], c)
                        err += sum((a - b) ** 2 for a, b in zip(pals[pn][n], c))
                        pix.append(n)
            if best is None or err < best[0]:
                best = (err, pn, pix)
        return best[1], best[2]

    for qi, q in enumerate(quads()):
        rgb = tms_quad(stage_vram, q)
        mask = [[rgb[y][x] is not None for x in range(16)] for y in range(16)]
        if qi in (4, 5, 15, 16):          # moai heads / score numbers: no art, converted
            pn, pix = best_palette(rgb)
            res.append((pn, pix, 'conv'))
            continue
        a = find_art_cached(f, qi, mask)
        if a:
            k, pix, agree = a
            res.append((k - 1, pix, 'art'))
            continue
        # art drawn for another fase? import it with this fase's colours
        found = None
        for f2 in sorted(range(1, 6), key=lambda x: abs(x - f)):
            if f2 == f:
                continue
            a = find_art_cached(f2, qi, mask)
            if a:
                found = (f2, a)
                break
        if found:
            f2, (k, pix, agree) = found
            im = Image.open(SRC + 'fase %d/fase %d - paleta %d.png' % (f2, f2, k))
            p = im.getpalette()[:48]
            p = [tuple(p[i * 3:i * 3 + 3]) for i in range(16)]
            rgb2 = [[None if pix[y * 16 + x] == 0 else p[pix[y * 16 + x]] for x in range(16)] for y in range(16)]
            pn, pix2 = best_palette(rgb2)
            res.append((pn, pix2, 'import%d' % f2))
            continue
        pn, pix = best_palette(rgb)
        res.append((pn, pix, 'conv'))
    return res


if __name__ == '__main__':
    W = Image.new('RGB', (17 * 40, 5 * 40), (60, 60, 60))
    for f in range(1, 6):
        v = open(REF + 'stage%d.vram' % (f - 1), 'rb').read()
        r = object_art(f, v)
        pals = []
        for k in (1, 2, 3, 4):
            im = Image.open(SRC + 'fase %d/fase %d - paleta %d.png' % (f, f, k))
            p = im.getpalette()[:48]
            pals.append([tuple(p[i * 3:i * 3 + 3]) for i in range(16)])
        for qi, q in enumerate(quads()):
            rgb = tms_quad(v, q)
            for y in range(16):
                for x in range(16):
                    if rgb[y][x]:
                        W.putpixel((qi * 40 + x, (f - 1) * 40 + y), rgb[y][x])
            pn, pix, how = r[qi]
            for i, c in enumerate(pix):
                if c:
                    W.putpixel((qi * 40 + 18 + i % 16, (f - 1) * 40 + i // 16), pals[pn][c])
            if how != 'conv':
                W.putpixel((qi * 40 + 18, (f - 1) * 40 + 18), (255, 255, 0))
        print(f, [(x[0], x[2]) for x in r])
    W.resize((W.width * 2, W.height * 2), Image.NEAREST).save(paths.OUT + 'objart.png')
