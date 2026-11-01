#!/usr/bin/env python3
"""Build Twin Bee V9990 on top of the 'SCC Enhanced' version (Konami SCC mapper, 256KB).

SCC hack layout (128KB): bank 0 = init + SCC driver loader, banks 1-3 = SCC sound driver/music,
banks 5-8 = game (re-assembled), the rest is empty.
We add: bank 4 = V9990 boot + driver, banks 9-31 = graphics data.
"""
import os, subprocess, sys, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths
BASE = paths.BASE
SJ = paths.SJASM
OUTROM = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'twinbee_v9990_scc.rom')
GAME = 0xA000          # file offset of the game (banks 5-8, address 4000h)


def patch_file(rom, off, data, expect):
    cur = bytes(rom[off:off + len(expect)])
    assert cur == bytes(expect), 'patch @%05x expected %s got %s' % (off, bytes(expect).hex(), cur.hex())
    rom[off:off + len(data)] = bytes(data)


def g(addr):
    return GAME + addr - 0x4000


def w(a):
    return [a & 255, a >> 8]


def main():
    env = dict(os.environ, TB_FIRST_BANK='9')
    subprocess.run([sys.executable, os.path.join(HERE, 'gfx.py'), os.path.join(HERE, 'out')], check=True, cwd=HERE, env=env)
    lay = json.load(open(os.path.join(HERE, 'out', 'layout.json')))
    assert lay['first'] == 9
    assert lay['first'] + lay['nbanks'] <= 32, 'graphics data does not fit in 256KB'
    args = [SJ, '--nologo', '--msg=war', '--sym=driver_scc.sym', '-DSCC'] + (['-DKEEP_TMS'] if os.environ.get('KEEP_TMS') else []) + [('-D' + x) for x in os.environ.get('TB_DEFS', '').split()] + ['driver.asm']
    r = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    print(r.stdout, r.stderr)
    if r.returncode:
        sys.exit(1)
    sym = {}
    for line in open(os.path.join(HERE, 'driver_scc.sym')):
        m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-Fa-f]+)', line)
        if m:
            sym[m.group(1)] = int(m.group(2), 16)
    boot = open(os.path.join(HERE, 'boot.bin'), 'rb').read()
    assert len(boot) <= 8192, len(boot)

    rom = bytearray(open(BASE, 'rb').read())
    assert len(rom) == 131072
    rom += bytes(131072)          # extend to 256KB (zero filled like the empty banks)

    # 1. hack init: 'jp 0C940h' (start game) -> stub at 40B5h (bank 0)
    patch_file(rom, 0x0091, [0xC3, 0xB5, 0x40], expect=[0xC3, 0x40, 0xC9])
    # 2. stub: ld a,4 / ld (7000h),a / jp 6000h   (V9990 loader in bank 4)
    patch_file(rom, 0x00B5, [0x3E, 0x04, 0x32, 0x00, 0x70, 0xC3, 0x00, 0x60], expect=[0] * 8)
    # 3. game init: H.KEYI -> our interrupt handler (which chains to the hack's handler at C800h)
    patch_file(rom, g(0x4082), [0x21] + w(sym['hook_isr']), expect=[0x21, 0x00, 0xC8])
    # 4. gameplay frame: call 460Bh / call 45ABh (TMS uploads)
    patch_file(rom, g(0x5D92), [0xCD] + w(sym['hook_satup']) + [0xCD] + w(sym['hook_nameup']),
               expect=[0xCD, 0x0B, 0x46, 0xCD, 0xAB, 0x45])
    # 5. stage start: call 460Bh / call 6C48h / jp 45ABh
    patch_file(rom, g(0x5F2C), [0xCD] + w(sym['hook_satup']) + [0xCD, 0x48, 0x6C, 0xC3] + w(sym['hook_nameup']),
               expect=[0xCD, 0x0B, 0x46, 0xCD, 0x48, 0x6C, 0xC3, 0xAB, 0x45])
    # 6. ground object chars: 'ld c,ffh / ldi / ...' -> call hook_obj / jr +10
    patch_file(rom, g(0xA991), [0xCD] + w(sym['hook_obj']) + [0x18, 0x0A],
               expect=[0x0E, 0xFF, 0xED, 0xA0, 0xED, 0xA0, 0x3E, 0x1E, 0xCD, 0x1D, 0x40, 0xED, 0xA0, 0xED, 0xA0, 0xD1])
    # 6b. player Y limit: 'ld a,h / cp 0AFh' -> call hook_ycmp, 'ld hl,0AF00h' -> ld hl,(ymax16)
    for a in (0x61D8, 0x62A4):
        patch_file(rom, g(a), [0xCD] + w(sym['hook_ycmp']), expect=[0x7C, 0xFE, 0xAF])
        patch_file(rom, g(a + 5), [0x2A] + w(sym['ymax16']), expect=[0x21, 0x00, 0xAF])
    # 6a2. music tick of the game ISR (C80Ch, copied from 020Ch): through the driver
    patch_file(rom, 0x020C, [0xCD] + w(sym['hook_tick']), expect=[0xCD, 0xC3, 0xC8])
    # 6b2. enemy objects removed below the screen: 'ld a,(hl) / sub 0C0h / cp 20h' -> call hook_ykill / nop / nop
    patch_file(rom, g(0xBADF), [0xCD] + w(sym['hook_ykill']) + [0, 0], expect=[0x7E, 0xD6, 0xC0, 0xFE, 0x20])
    # 6c. test build: infinite lives ('sub 1' of the 1P/2P rest counters -> 'sub 0')
    if os.environ.get('TB_INFINITE'):
        for a in (0x6441, 0x64A5):
            patch_file(rom, g(a), [0xD6, 0x00], expect=[0xD6, 0x01])
    # 7. credits: 'X' glyph (font char 35h) + "COLOR   GUANTXIP" line in the staff roll
    #    font loader 'call 45D6h' -> BF40h: call 45D6h, then the X glyph into the 3 PG thirds
    patch_file(rom, g(0x48F3), [0xCD, 0x40, 0xBF], expect=[0xCD, 0xD6, 0x45])
    xr = [0xCD, 0xD6, 0x45,                   # call 45D6h
          0x11, 0xA8, 0x21, 0xCD, 0x52, 0xBF,  # ld de,21A8h / call .one
          0x11, 0xA8, 0x29, 0xCD, 0x52, 0xBF,  # ld de,29A8h / call .one
          0x11, 0xA8, 0x31,                    # ld de,31A8h
          0x21, 0x5B, 0xBF, 0x01, 0x08, 0x00, 0xC3, 0x5C, 0x00,   # .one: ld hl,XG / ld bc,8 / jp LDIRVM
          0x00, 0x63, 0x63, 0x36, 0x1C, 0x36, 0x63, 0x63]         # XG (rows 1-7, as the font)
    assert len(xr) == 0x1B + 8
    patch_file(rom, g(0xBF40), xr, expect=[0] * len(xr))
    #    C O L O R . . . G U A N T X I P  (font codes)
    rec = [0x08, 0x1D, 0x2E, 0x23, 0x2E, 0x34, 0, 0, 0, 0x2D, 0x28, 0x2F, 0x24, 0x27, 0x35, 0x21, 0x25, 0xFF]
    patch_file(rom, g(0xBF68), rec, expect=[0] * len(rec))
    #    staff table (4885h, 12 lines): ... ISAO, -, COLOR, -, (c)KONAMI, -
    patch_file(rom, g(0x4885 + 16), w(0xBF68) + w(0x48E8) + w(0x48DA) + w(0x48E8),
               expect=w(0x48E8) + w(0x48DA) + w(0x48E8) + w(0x48E8))
    # 8. bank 4: boot + driver
    assert rom[0x8000:0xA000] == bytes(8192)
    rom[0x8000:0x8000 + len(boot)] = boot
    # 8b. SCC sound driver: its PSG writes go through the BIOS (call 0093h, WRTPSG),
    #     about 14 calls per frame. They call a direct port write instead, placed at
    #     the end of bank 4, which the sound driver maps at A000h-BFFFh (banks 1-4).
    #     (WRTPSG also enables the interrupts: the music tick now runs with them off.)
    WR = 0xBFF0
    assert len(boot) <= 0x1FF0
    rom[0x8000 + 0x1FF0:0x8000 + 0x1FF8] = bytes([0xD3, 0xA0,   # out (0A0h),a
                                                  0xF5,         # push af
                                                  0x7B,         # ld a,e
                                                  0xD3, 0xA1,   # out (0A1h),a
                                                  0xF1,         # pop af
                                                  0xC9])        # ret
    for a in (0x5160, 0x5167, 0x5173, 0x518D, 0x51A1, 0x51B3, 0x51C1, 0x51CF, 0x51FC):
        patch_file(rom, 0x2000 + a - 0x4000, [0xCD] + w(WR), expect=[0xCD, 0x93, 0x00])
    # 8c. faster SCC register output (sndfast.asm, at BE00h of the same bank 4 mapping)
    if not os.environ.get('TB_OLDSND'):
        r = subprocess.run([SJ, '--nologo', '--msg=war', '--sym=sndfast.sym', 'sndfast.asm'], cwd=HERE, capture_output=True, text=True)
        print(r.stdout, r.stderr)
        if r.returncode:
            sys.exit(1)
        sf = open(os.path.join(HERE, 'sndfast.bin'), 'rb').read()
        assert len(boot) <= 0x1E00 and len(sf) <= 0x1F0
        rom[0x8000 + 0x1E00:0x8000 + 0x1E00 + len(sf)] = sf
        ssym = {}
        for line in open(os.path.join(HERE, 'sndfast.sym')):
            m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-Fa-f]+)', line)
            if m:
                ssym[m.group(1)] = int(m.group(2), 16)
        patch_file(rom, 0x2000 + 0x5133 - 0x4000, [0xCD] + w(ssym['psg_out']) + [0xCD] + w(ssym['scc_out']),
                   expect=[0xCD, 0x3A, 0x51, 0xCD, 0x13, 0x52])
    # 9. data banks 9..
    banks = open(os.path.join(HERE, 'out', 'banks.bin'), 'rb').read()
    for i in range(9, 16):
        assert rom[i * 8192:(i + 1) * 8192] == bytes(8192), 'bank %d of the SCC rom is not empty' % i
    rom[9 * 8192:9 * 8192 + len(banks)] = banks
    assert len(rom) == 262144
    open(OUTROM, 'wb').write(rom)
    print('wrote', OUTROM, len(rom), 'hooks', {k: hex(sym[k]) for k in ('hook_isr', 'hook_satup', 'hook_nameup', 'hook_obj')})


if __name__ == '__main__':
    main()
