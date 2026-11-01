#!/usr/bin/env python3
"""Build Twin Bee V9990 on top of the original game (32KB, PSG music).

Output: 256KB Konami (no SCC) MegaROM. Banks 0-3 = original game (with small
patches), bank 4 = V9990 boot + driver, banks 5.. = graphics data.
"""
import os, subprocess, sys, json, re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths
BASE = paths.ORIG
SJ = paths.SJASM
OUTROM = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'twinbee_v9990_psg.rom')


def patch(rom, addr, data, expect):
    off = addr - 0x4000
    cur = bytes(rom[off:off + len(expect)])
    assert cur == bytes(expect), 'patch @%04x expected %s got %s' % (addr, bytes(expect).hex(), cur.hex())
    rom[off:off + len(data)] = bytes(data)


def w(a):
    return [a & 255, a >> 8]


def main():
    env = dict(os.environ, TB_FIRST_BANK='5')
    subprocess.run([sys.executable, os.path.join(HERE, 'gfx.py'), os.path.join(HERE, 'out')], check=True, cwd=HERE, env=env)
    lay = json.load(open(os.path.join(HERE, 'out', 'layout.json')))
    assert lay['first'] == 5
    assert lay['first'] + lay['nbanks'] <= 32, 'graphics data does not fit in 256KB'
    args = [SJ, '--nologo', '--msg=war', '--sym=driver_psg.sym'] + [('-D' + x) for x in os.environ.get('TB_DEFS', '').split()] + ['driver.asm']
    r = subprocess.run(args, cwd=HERE, capture_output=True, text=True)
    print(r.stdout, r.stderr)
    if r.returncode:
        sys.exit(1)
    sym = {}
    for line in open(os.path.join(HERE, 'driver_psg.sym')):
        m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-Fa-f]+)', line)
        if m:
            sym[m.group(1)] = int(m.group(2), 16)
    boot = open(os.path.join(HERE, 'boot.bin'), 'rb').read()
    assert len(boot) <= 8192, len(boot)

    rom = bytearray(open(BASE, 'rb').read())
    assert len(rom) == 32768
    # 1. INIT vector -> stub at 4010h: di / ld a,4 / ld (6000h),a / jp 6000h (boot in bank 4)
    patch(rom, 0x4002, w(0x4010), expect=w(0x40B1))
    patch(rom, 0x4010, [0xF3, 0x3E, 0x04, 0x32, 0x00, 0x60, 0xC3, 0x00, 0x60],
          expect=[0x43, 0x44, 0x07, 0x40, 0x08, 0x00, 0xE0, 0x04, 0x76])
    # 2. game init, after page 2 was switched to the cartridge: banks 8000h/A000h + H.KEYI hook
    patch(rom, 0x40D1, [0xCD] + w(sym['hook_slot']) + [0] * 8,
          expect=[0x3E, 0xC3, 0x32, 0x9A, 0xFD, 0x21, 0x2E, 0x40, 0x22, 0x9B, 0xFD])
    # 3. gameplay frame: call 46CEh / call 466Eh (TMS uploads)
    patch(rom, 0x5E52, [0xCD] + w(sym['hook_satup']) + [0xCD] + w(sym['hook_nameup']),
          expect=[0xCD, 0xCE, 0x46, 0xCD, 0x6E, 0x46])
    # 4. stage start: call 46CEh / call 6D08h / jp 466Eh
    patch(rom, 0x5FEC, [0xCD] + w(sym['hook_satup']) + [0xCD, 0x08, 0x6D, 0xC3] + w(sym['hook_nameup']),
          expect=[0xCD, 0xCE, 0x46, 0xCD, 0x08, 0x6D, 0xC3, 0x6E, 0x46])
    # 5. ground object chars: 'ld c,ffh / ldi / ...' -> call hook_obj / jr +10
    patch(rom, 0xAA51, [0xCD] + w(sym['hook_obj']) + [0x18, 0x0A], expect=[0x0E, 0xFF, 0xED, 0xA0, 0xED])
    # 6. player Y limit (1P, 2P) and enemies removed below the screen (as in the SCC build)
    for a in (0x6298, 0x6364):
        patch(rom, a, [0xCD] + w(sym['hook_ycmp']), expect=[0x7C, 0xFE, 0xAF])
        patch(rom, a + 5, [0x2A] + w(sym['ymax16']), expect=[0x21, 0x00, 0xAF])
    patch(rom, 0xBB9F, [0xCD] + w(sym['hook_ykill']) + [0, 0], expect=[0x7E, 0xD6, 0xC0, 0xFE, 0x20])
    # 7. test build: infinite lives
    if os.environ.get('TB_INFINITE'):
        for a in (0x6501, 0x6565):
            patch(rom, a, [0xD6, 0x00], expect=[0xD6, 0x01])
    # 8. credits: X glyph + "COLOR   GUANTXIP" (code and record in the driver, see cred_font)
    patch(rom, 0x49B3, [0xCD] + w(sym['cred_font']), expect=[0xCD, 0x99, 0x46])
    patch(rom, 0x4945 + 16, w(sym['cred_rec']) + w(0x49A8) + w(0x499A) + w(0x49A8),
          expect=w(0x49A8) + w(0x499A) + w(0x49A8) + w(0x49A8))

    banks = open(os.path.join(HERE, 'out', 'banks.bin'), 'rb').read()
    full = rom + boot + bytes([0xFF] * (8192 - len(boot)))
    assert len(full) == 5 * 8192
    full += banks
    total = 256 * 1024
    assert len(full) <= total, len(full)
    full += bytes([0xFF] * (total - len(full)))
    open(OUTROM, 'wb').write(full)
    print('wrote', OUTROM, len(full), 'hooks', {k: hex(sym[k]) for k in ('hook_isr', 'hook_satup', 'hook_nameup', 'hook_obj')})


if __name__ == '__main__':
    main()
