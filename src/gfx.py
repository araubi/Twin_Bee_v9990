#!/usr/bin/env python3
"""Twin Bee V9990: convert artwork into V9990 P1 data and pack into ROM banks.

Produces in OUT dir:
  banks.bin   : concatenated 8KB banks starting at bank FIRST_BANK
  data.inc    : sjasmplus include with symbols (bank numbers/offsets, tables)
"""
import os, sys, json
from PIL import Image

import paths
SRC = paths.ART
OUT = sys.argv[1] if len(sys.argv) > 1 else paths.OUT
os.makedirs(OUT, exist_ok=True)
FIRST_BANK = int(os.environ.get('TB_FIRST_BANK', '5'))   # first data bank (Konami: 5, SCC: 9)
NUM_BANKS = 32          # 256KB Konami

MAGENTA = (0xff, 0x00, 0xd8)
STAGES = {
    1: ('fase 1', 'mapa 1 - paleta 1.png', 'mapa 1 - paleta 2.png'),
    2: ('fase 2', 'mapa 2 - paleta 1.png', 'mapa 2 - paleta 2.png'),
    3: ('fase 3', 'mapa 3 - paleta 1.png', 'mapa 3 - paleta 2.png'),
    4: ('fase 4', 'mapa - paleta 1.png', 'mapa - paleta 2.png'),
    5: ('fase 5', 'mapa 5 - paleta 1.png', 'mapa 5 - paleta 2.png'),
}
# stage end thresholds of ebf0 (ROM table at 6132)
THRESH = [261, 585, 945, 1272, 1760]
REF = paths.REF
TMSPAL = [(0, 0, 0), (0, 0, 0), (33, 200, 66), (94, 220, 120), (84, 85, 237), (125, 118, 252), (212, 82, 77),
          (66, 235, 245), (252, 85, 84), (255, 121, 120), (212, 193, 84), (230, 206, 128), (33, 176, 59),
          (201, 91, 186), (204, 204, 204), (255, 255, 255)]


# ---------------------------------------------------------------- helpers
def sheet_palette(path):
    im = Image.open(path)
    p = im.getpalette()[:48]
    return [tuple(p[i * 3:i * 3 + 3]) for i in range(16)]


def nearest(pal, c, start=1):
    best = None
    for i in range(start, len(pal)):
        d = sum((a - b) ** 2 for a, b in zip(pal[i], c))
        if best is None or d < best[0]:
            best = (d, i)
    return best[1]


def index_image(im, pal):
    im = im.convert('RGBA')
    w, h = im.size
    px = im.load()
    exact = {}
    for i in range(15, 0, -1):
        exact[tuple(pal[i])] = i
    out = []
    cache = {}
    for y in range(h):
        row = []
        for x in range(w):
            r, g, b, a = px[x, y]
            c = (r, g, b)
            if a < 128 or c == MAGENTA:
                row.append(0)
            elif c in exact:
                row.append(exact[c])
            else:
                if c not in cache:
                    cache[c] = nearest(pal, c)
                row.append(cache[c])
        out.append(row)
    return out, w, h


def cut_tiles(idx, w, h, tiles, tmap):
    """returns map (list of rows of tile ids) adding unique tiles to tiles/tmap"""
    m = []
    for ty in range(h // 8):
        row = []
        for tx in range(w // 8):
            t = tuple(idx[ty * 8 + y][tx * 8 + x] for y in range(8) for x in range(8))
            if t not in tmap:
                tmap[t] = len(tiles)
                tiles.append(t)
            row.append(tmap[t])
        m.append(row)
    return m


def pal5(pal):
    b = bytearray()
    for i, c in enumerate(pal):
        if i % 16 == 0:
            c = (0, 0, 0)   # colour 0 of every palette: backdrop/black
        for v in c:
            b.append((v * 31 + 127) // 255)
    return bytes(b)


def rle(data):
    """n<128: n+1 literals follow ; n>=128: byte repeated n-125 times (3..130)"""
    out = bytearray()
    i = 0
    lit = bytearray()

    def flush():
        while lit:
            chunk = lit[:128]
            out.append(len(chunk) - 1)
            out.extend(chunk)
            del lit[:128]
    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i] and j - i < 130:
            j += 1
        if j - i >= 3:
            flush()
            out.append(j - i + 125)
            out.append(data[i])
            i = j
        else:
            lit.append(data[i])
            i += 1
    flush()
    return bytes(out)


def lz(data):
    """byte LZ: c<128: c+1 literals follow ; c>=128: copy (c&127)+3 bytes from
    distance d (2 bytes, 1..4096) back in the output.  Greedy with hash chains."""
    out = bytearray()
    lit = bytearray()
    n = len(data)
    heads = {}
    prev = [-1] * n

    def flush():
        while lit:
            chunk = lit[:128]
            out.append(len(chunk) - 1)
            out.extend(chunk)
            del lit[:128]

    def insert(p):
        if p + 2 < n:
            k = data[p:p + 3]
            prev[p] = heads.get(k, -1)
            heads[k] = p
    i = 0
    while i < n:
        best_l, best_d = 0, 0
        if i + 2 < n:
            cand = heads.get(data[i:i + 3], -1)
            tries = 0
            while cand >= 0 and tries < 256:
                d = i - cand
                if d > 4096:
                    break
                l = 0
                while i + l < n and l < 130 and data[cand + l] == data[i + l]:
                    l += 1
                if l > best_l:
                    best_l, best_d = l, d
                    if l == 130:
                        break
                cand = prev[cand]
                tries += 1
        if best_l >= 3:
            flush()
            out.append(0x80 | (best_l - 3))
            out.append(best_d & 255)
            out.append(best_d >> 8)
            for k in range(best_l):
                insert(i + k)
            i += best_l
        else:
            lit.append(data[i])
            insert(i)
            i += 1
    flush()
    return bytes(out)


def unlz(comp):
    out = bytearray()
    i = 0
    while i < len(comp):
        c = comp[i]
        i += 1
        if c < 128:
            out += comp[i:i + c + 1]
            i += c + 1
        else:
            l = (c & 127) + 3
            d = comp[i] | comp[i + 1] << 8
            i += 2
            for k in range(l):
                out.append(out[-d])
    return bytes(out)


class PatternArea:
    """V9990 P1 pattern area image: 32 tiles per 'tile row', 128 bytes per pixel line."""

    def __init__(self, ntiles_max):
        self.data = bytearray(((ntiles_max + 31) // 32) * 1024)
        self.n = 0

    def put_tile(self, num, t):
        base = (num >> 5) * 1024 + (num & 31) * 4
        for y in range(8):
            for x in range(0, 8, 2):
                self.data[base + y * 128 + x // 2] = (t[y * 8 + x] << 4) | t[y * 8 + x + 1]

    def used(self, ntiles):
        return bytes(self.data[:((ntiles + 31) // 32) * 1024])


# ---------------------------------------------------------------- ROM packer
class Packer:
    def __init__(self):
        self.banks = []
        self.cur = None
        self.syms = []

    def new_bank(self):
        self.banks.append(bytearray())
        return FIRST_BANK + len(self.banks) - 1

    def place(self, data, name=None, align_bank=False, align=1):
        """place blob entirely inside one bank (first fit); returns (bank, addr in window 6000)"""
        assert len(data) <= 8192, (name, len(data))
        pad = lambda n: (-n) % align
        bi = None
        if not align_bank:
            for i, b in enumerate(self.banks):
                if len(b) + pad(len(b)) + len(data) <= 8192:
                    bi = i
                    break
        if bi is None:
            self.new_bank()
            bi = len(self.banks) - 1
        b = self.banks[bi]
        b += bytes(pad(len(b)))
        off = len(b)
        b += data
        bank = FIRST_BANK + bi
        if name:
            self.syms.append((name + '_BANK', bank))
            self.syms.append((name + '_ADDR', 0x6000 + off))
            self.syms.append((name + '_LEN', len(data)))
        return bank, 0x6000 + off

    def place_split(self, data):
        """place data possibly across banks, return list of (bank, addr, len)"""
        res = []
        pos = 0
        while pos < len(data):
            if not self.banks or len(self.banks[-1]) >= 8192:
                self.new_bank()
            free = 8192 - len(self.banks[-1])
            chunk = data[pos:pos + free]
            bank, addr = self.place(chunk)
            res.append((bank, addr, len(chunk)))
            pos += len(chunk)
        return res


def main():
    pk = Packer()
    uploads = []  # (vram addr, bank, addr, len)

    pending = []   # (vram addr, raw chunk); compressed and placed at the end

    def upload(vaddr, data):
        # chunks of <= 4KB that never cross a bank; RLE (fast to decode) or LZ (smaller)
        CH = 4096
        for pos in range(0, len(data), CH):
            pending.append((vaddr + pos, data[pos:pos + CH]))

    def place_uploads():
        maxb = int(os.environ.get('TB_MAX_BANKS', 32 - FIRST_BANK))
        forms = []
        for va, raw in pending:
            r = rle(raw)
            z = lz(raw)
            assert unlz(z) == raw
            forms.append((r, z))
        other = sum(len(b) for b in pk.banks)
        order = sorted(range(len(forms)), key=lambda i: len(forms[i][1]) - len(forms[i][0]))
        slack = 2048
        while True:
            use_lz = set()
            total = other + sum(len(f[0]) for f in forms)
            for i in order:
                if total <= maxb * 8192 - slack:
                    break
                use_lz.add(i)
                total += len(forms[i][1]) - len(forms[i][0])
            trial = Packer()
            trial.banks = [bytearray(b) for b in pk.banks]
            ok = True
            res = []
            for i, (va, raw) in enumerate(pending):
                c = forms[i][1] if i in use_lz else forms[i][0]
                bank, addr = trial.place(c)
                res.append((va | (0x800000 if i in use_lz else 0), bank, addr, len(c)))
            if len(trial.banks) <= maxb or slack > 60000:
                break
            slack += 2048
        pk.banks = trial.banks
        uploads.extend(res)
        print('uploads: %d chunks, %d LZ, %d RLE' % (len(res), len(use_lz), len(res) - len(use_lz)))

    # ---- global tile numbering
    A_tiles = []   # list of 64-px tuples (layer A, pattern space 0x00000)
    B_tiles = []
    A_tiles.append(tuple([0] * 64))   # tile 0 = blank
    B_tiles.append(tuple([0] * 64))
    stage_info = {}
    raw = {}
    for s, (d, mb, ma) in STAGES.items():
        base = os.path.join(SRC, d)
        imB = Image.open(os.path.join(base, mb)).convert('RGBA')
        imA = Image.open(os.path.join(base, ma)).convert('RGBA')
        if s == 4:
            # art fix: in 'mapa - paleta 2' of fase 4 the cliffs of the last island
            # screen (lines 2648-2703) are one tile row higher than in 'paleta 1'
            imA.paste(imA.crop((0, 2648, 256, 2704)), (0, 2656))
            imA.paste(imA.crop((0, 2600, 256, 2608)), (0, 2648))   # (empty water line)
        raw[s] = (imB, imA)
    # the boss of stage s is fought over the top screen of map s (rows 0-23); after
    # it the game goes on with map s+1, whose bottom shows the same island screen,
    # drawn a little differently and with other palettes. Both copies are replaced
    # by one picture made only of colours that both stages have, so that nothing
    # changes when the map (and the palette) is switched.
    spals = {}
    for s, (d, mb, ma) in STAGES.items():
        base = os.path.join(SRC, d)
        spals[s] = [sheet_palette(os.path.join(base, 'fase %d - paleta %d.png' % (s, k))) for k in (1, 2)]

    def common_screen(img, y0, nrows, pa, pb):
        # colours of stage s with a close one in stage n (each map indexes the
        # picture with its own palette: e.g. the lighthouse's white is 222 grey
        # in one stage and 255 white in the other)
        cols = [c[:3] for c in pa[1:16] if min(sum((x - y) ** 2 for x, y in zip(c[:3], d[:3])) for d in pb[1:16]) < 4000]
        out = img.crop((0, y0 * 8, 256, (y0 + nrows) * 8)).copy()
        px = out.load()
        cache = {}
        for yy in range(out.height):
            for xx in range(256):
                p = px[xx, yy]
                if p[3] < 128 or (abs(p[0] - 255) + abs(p[1]) + abs(p[2] - 216)) < 60:
                    continue
                k = p[:3]
                if k not in cache:
                    cache[k] = min(cols, key=lambda c: sum((x - y) ** 2 for x, y in zip(c, k)))
                px[xx, yy] = cache[k] + (255,)
        return out
    def missing(img, y0, nrows, pal):
        # pixels of the picture whose colour has no close one in the palette
        c = 0
        for p in img.crop((0, y0 * 8, 256, (y0 + nrows) * 8)).getdata():
            if p[3] < 128 or (abs(p[0] - 255) + abs(p[1]) + abs(p[2] - 216)) < 60:
                continue
            if min(sum((x - y) ** 2 for x, y in zip(p[:3], q)) for q in pal[1:16]) >= 4000:
                c += 1
        return c
    for s in range(1, 6):
        n = s % 5 + 1
        off = (THRESH[n - 1] - THRESH[s - 1]) if n > 1 else THRESH[0] - 26
        # the island screen is taken from the copy that loses fewer colours: the
        # one of map n (e.g. the white lighthouse of stage 3) or the one of map s
        # (e.g. stage 1: in map 2 the cliffs are drawn in layer B, which has no
        # brown in the stage 1 palette, and would turn grey)
        rows_n = min(24, raw[n][0].height // 8 - off)
        from_s = sum(missing(raw[s][k], 0, 24, spals[n][k]) for k in range(2)) < \
            sum(missing(raw[n][k], off, rows_n, spals[s][k]) for k in range(2))
        print('island screen %d->%d from map %d' % (s, n, s if from_s else n))
        for k in range(2):
            src = raw[n][k]
            hn = src.height // 8
            rows = min(24, hn - off)
            if from_s:
                scr = common_screen(raw[s][k], 0, 24, spals[s][k], spals[n][k])
                rows = 24
            else:
                scr = common_screen(src, off, rows, spals[s][k], spals[n][k])
            # the 3 rows below the island screen (shown below the MSX screen
            # area during the boss) are the end of stage s: the same in map n,
            # so nothing changes there when the boss is beaten
            strip = common_screen(raw[s][k], 24, 3, spals[s][k], spals[n][k])
            if raw[n][k].height < (off + 27) * 8:
                big = Image.new(raw[n][k].mode, (256, (off + 27) * 8))
                big.paste(raw[n][k], (0, 0))
                lst = list(raw[n])
                lst[k] = big
                raw[n] = type(raw[n])(lst)
            raw[n][k].paste(scr, (0, off * 8))
            raw[n][k].paste(strip, (0, (off + 24) * 8))
            raw[s][k].paste(scr, (0, 0))
            raw[s][k].paste(strip, (0, 24 * 8))
            for r in range(rows, 24):      # (map n ends before: repeat its last row)
                raw[s][k].paste(scr.crop((0, (rows - 1) * 8, 256, rows * 8)), (0, r * 8))
                raw[n][k].paste(scr.crop((0, (rows - 1) * 8, 256, rows * 8)), (0, (off + r) * 8))
    # row above the top of map s (partly visible above the boss screen): the
    # row above the island screen in map n, the same in both maps (common
    # colours). It is added below the bottom of map s, out of the rows the
    # scroll can reach (the driver reads it for the rows above the map top).
    above = {}
    for s in range(1, 6):
        n = s % 5 + 1
        off = (THRESH[n - 1] - THRESH[s - 1]) if n > 1 else THRESH[0] - 26
        rws = []
        for k in range(2):
            row = common_screen(raw[n][k], off - 1, 1, spals[s][k], spals[n][k])
            raw[n][k].paste(row, (0, (off - 1) * 8))
            rws.append(row)
        above[s] = rws
    h_orig = {}
    for s in range(1, 6):
        lst = list(raw[s])
        h_orig[s] = lst[0].height // 8
        for k in range(2):
            big = Image.new(lst[k].mode, (256, lst[k].height + 8))
            big.paste(lst[k], (0, 0))
            big.paste(above[s][k], (0, lst[k].height))
            lst[k] = big
        raw[s] = type(raw[s])(lst)
    if os.environ.get('TB_DUMP'):
        for s in range(1, 6):
            raw[s][0].save(os.path.join(OUT, 'dumpB%d.png' % s)); raw[s][1].save(os.path.join(OUT, 'dumpA%d.png' % s))
    for s, (d, mb, ma) in STAGES.items():
        base = os.path.join(SRC, d)
        pals = [sheet_palette(os.path.join(base, 'fase %d - paleta %d.png' % (s, k))) for k in (1, 2, 3, 4)]
        iB, w, h = index_image(raw[s][0], pals[0])
        iA, w2, h2 = index_image(raw[s][1], pals[1])
        assert (w, h) == (w2, h2) and w == 256
        # per-stage local tile sets (local 0 = blank)
        tB, tmB = [tuple([0] * 64)], {tuple([0] * 64): 0}
        tA, tmA = [tuple([0] * 64)], {tuple([0] * 64): 0}
        mB = cut_tiles(iB, w, h, tB, tmB)
        mA = cut_tiles(iA, w, h, tA, tmA)
        baseB = len(B_tiles)
        baseA = len(A_tiles)
        B_tiles += tB
        A_tiles += tA
        stage_info[s] = dict(pals=pals, mA=mA, mB=mB, baseA=baseA, baseB=baseB, H=h // 8)
        print('stage', s, 'rows', h // 8, 'tilesA', len(tA), 'tilesB', len(tB), 'baseA', baseA, 'baseB', baseB)

    # ---- mirror (TMS screen copy) tilesets: logo, title, stage PGs (TMS colours)
    #      and pause-window tilesets (stage PG converted into the layer A palette)
    mir_tabs = []
    tm = {}

    def tile_id(t):
        if t not in tm:
            tm[t] = len(A_tiles)
            A_tiles.append(t)
        return tm[t]

    def conv_table(v, cmap, keep=None):
        tab = bytearray()
        for th in range(3):
            for c in range(256):
                if keep is not None and not keep(c):
                    tab += bytes([0, 0])
                    continue
                t = []
                for y in range(8):
                    p = v[0x2000 + th * 0x800 + c * 8 + y]
                    co = v[th * 0x800 + c * 8 + y]
                    for x in range(8):
                        t.append(cmap[(co >> 4) if p & (0x80 >> x) else (co & 15)])
                n = tile_id(tuple(t))
                tab += bytes([n & 255, n >> 8])
        return bytes(tab)
    ident = list(range(16))
    XGLYPH = bytes([0x00, 0x63, 0x63, 0x36, 0x1C, 0x36, 0x63, 0x63])   # 'X' added at char 35h (credits)

    def add_x(v):
        v = bytearray(v)
        for th in range(3):
            v[0x2000 + th * 0x800 + 0x35 * 8:0x2000 + th * 0x800 + 0x36 * 8] = XGLYPH
            v[th * 0x800 + 0x35 * 8:th * 0x800 + 0x36 * 8] = v[th * 0x800 + 0x34 * 8:th * 0x800 + 0x35 * 8]
        return bytes(v)
    for snap in ('logoB', 'title'):
        v = open(os.path.join(REF, snap + '.vram'), 'rb').read()
        mir_tabs.append(conv_table(v, ident))
    # game over / ending screens: font + the bush border chars (ending PG)
    v = add_x(open(os.path.join(REF, 'ending.vram'), 'rb').read())
    mir_tabs.append(conv_table(v, ident, lambda c: c < 0x3C or 0x70 <= c < 0x78))
    for k in range(5):
        v = open(os.path.join(REF, 'stage%d.vram' % k), 'rb').read()
        p1 = stage_info[k + 1]['pals'][1]
        dark = min(range(1, 16), key=lambda i: sum(p1[i]))
        cmap = [dark] + [nearest(p1, TMSPAL[c]) for c in range(1, 16)]
        cmap[1] = dark
        mir_tabs.append(conv_table(v, cmap, lambda c: c < 0x3C))
    print('mirror+pause tiles', len(tm))

    # ---- pattern area images
    assert len(A_tiles) <= 2048, len(A_tiles)
    paA = PatternArea(2048)
    for i, t in enumerate(A_tiles):
        paA.put_tile(i, t)
    paB = PatternArea(len(B_tiles))
    for i, t in enumerate(B_tiles):
        paB.put_tile(i, t)
    upload(0x00000, paA.used(len(A_tiles)))
    upload(0x40000, paB.used(len(B_tiles)))

    # ---- sprites: one pattern area per fase at 0x10000 + (f-1)*0x8000
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import sprites as SP
    arts = {}
    for f in range(1, 6):
        arts[f] = SP.FaseArt(f)
    ctx_info = []
    # the entries of 3 contexts share one set of 13 pages of 256 bytes (byte k of
    # entry n at page k + n: the driver steps with inc h); entry numbers of the
    # 2nd and 3rd context are offset. Each group goes in one bank with the
    # pattern/colour tables and ground object tables of its contexts.
    built = []
    for ctx in SP.CTX_ORDER:
        f = SP.CTX_FASE[ctx]
        table, entries = SP.build_context(ctx, arts[f])
        objtab = b''.join(bytes([pat, pal << 6]) for pat, pal in arts[f].objects)
        assert len(objtab) == 34
        built.append((ctx, f, table, entries, objtab))
        print('sprite ctx', ctx, 'fase', f, 'entries', len(entries) - 1)
    for g in range(0, len(built), 3):
        grp = built[g:g + 3]
        allent = [None]
        tabs = []
        for ctx, f, table, entries, objtab in grp:
            off = len(allent) - 1
            allent += entries[1:]
            tabs.append((bytes((v + off) if v else 0 for v in table) + objtab, f))
        assert len(allent) <= 256, len(allent)
        blob = SP.entries_blob(allent)
        tpos = []
        for t, f in tabs:
            tpos.append(len(blob))
            blob += t
        bank, addr = pk.place(blob, align_bank=False, align=256)
        for (t, f), tp in zip(tabs, tpos):
            ctx_info.append((bank, addr + tp, addr, f))
    for f in range(1, 6):
        img = arts[f].area_image()
        print('fase', f, 'sprite patterns used', len(arts[f].patterns), 'imports', len(arts[f].imports), 'bytes', len(img))
        upload(0x10000 + (f - 1) * 0x8000, img)

    # ---- per stage maps: rowlist + dict rows (64 bytes = 32 name entries)
    stage_tab = []
    for s in range(1, 6):
        si = stage_info[s]
        for L, m, tb in (('A', si['mA'], si['baseA']), ('B', si['mB'], si['baseB'])):
            rows = []
            rmap = {}
            rl = bytearray()
            for r in m:
                key = tuple(r)
                if key not in rmap:
                    rmap[key] = len(rows)
                    rows.append(key)
                rl.append(rmap[key])
            assert len(rows) <= 256
            dic = bytearray()
            for r in rows:
                for t in r:
                    n = tb + t
                    dic += bytes([n & 255, n >> 8])
            blob = bytes(rl) + bytes(dic)
            bank, addr = pk.place(blob, 'MAP%d%s' % (s, L))
            si['map' + L] = (bank, addr, addr + len(rl))
        # palette blob
        pb = b''.join(pal5(p) for p in si['pals'])
        si['pal'] = pb

    # palettes: put all 5 together in one bank, plus mirror palette and tables
    palblob = b''.join(stage_info[s]['pal'] for s in range(1, 6))
    pk.place(palblob, 'PALS')
    mp = [(0, 0, 0)] * 16 + [(0, 0, 0)] + TMSPAL[1:] + [(0, 0, 0)] * 32
    pk.place(pal5(mp), 'MIRPAL')
    mir_dir = [pk.place(t) for t in mir_tabs]
    place_uploads()

    # ---- generate include
    syms = list(pk.syms)
    lines = ['; generated by gfx.py']
    for n, v in syms:
        lines.append('%s EQU 0x%X' % (n, v))
    # stage table: for each stage: K(T_s) word, H word, mapA bank, rowlistA addr, dictA addr, mapB bank, rowlistB, dictB
    open(os.path.join(OUT, 'data_sym.inc'), 'w').write('\n'.join(lines) + '\n')
    lines = ['; generated tables']
    lines.append('STAGE_TAB:')
    for s in range(1, 6):
        si = stage_info[s]
        K = THRESH[s - 1]
        H = si['H']
        bA, rlA, dA = si['mapA']
        bB, rlB, dB = si['mapB']
        lines.append('    DW %d, %d' % (K, h_orig[s] - 1))
        lines.append('    DB %d' % bA)
        lines.append('    DW 0x%04X, 0x%04X' % (rlA, dA))
        lines.append('    DB %d' % bB)
        lines.append('    DW 0x%04X, 0x%04X' % (rlB, dB))
        # row shown above the top of the map: the extra row below the map (see above)
        lines.append('    DW %d' % h_orig[s])
    lines.append('STAGE_TAB_SIZE = 16')
    lines.append('MIR_DIR:   ; bank, addr : logo, title, ending (TMS colours), pause1-5')
    for bank, addr in mir_dir:
        lines.append('    DB %d : DW 0x%04X' % (bank, addr))
    import objects as OB
    lines.append('OBJ_QUADS:   ; TL,TR chars of the ground object quads')
    for q in OB.quads():
        lines.append('    DB 0x%02X, 0x%02X' % (q[0], q[1]))
    lines.append('OBJ_NQUADS = %d' % len(OB.quads()))
    lines.append('CTX_TAB:   ; bank, table addr, entries addr, fase-1')
    for bank, ta, ea, f in ctx_info:
        lines.append('    DB %d : DW 0x%04X, 0x%04X : DB %d' % (bank, ta, ea, f - 1))
    up = ['; generated upload table', 'UPLOAD_COUNT = %d' % len(uploads), 'UPLOAD_TAB:']
    for vaddr, bank, addr, ln in uploads:
        up.append('    DB %d, %d, %d : DB %d : DW 0x%04X, %d' % (vaddr & 255, (vaddr >> 8) & 255, vaddr >> 16, bank, addr, ln))
    open(os.path.join(OUT, 'data_upl.inc'), 'w').write('\n'.join(up) + '\n')
    open(os.path.join(OUT, 'data_tab.inc'), 'w').write('\n'.join(lines) + '\n')

    # ---- banks
    allb = bytearray()
    for b in pk.banks:
        allb += b + bytes([0xFF] * (8192 - len(b)))
    open(os.path.join(OUT, 'banks.bin'), 'wb').write(allb)
    print('data banks used:', len(pk.banks), 'last bank', FIRST_BANK + len(pk.banks) - 1)
    json.dump({'nbanks': len(pk.banks), 'first': FIRST_BANK}, open(os.path.join(OUT, 'layout.json'), 'w'))


if __name__ == '__main__':
    main()
