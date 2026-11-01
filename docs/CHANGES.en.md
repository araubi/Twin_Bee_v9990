[Español](CAMBIOS.md) · **English** · [日本語](CHANGES.ja.md)

# Twin Bee V9990: changes and technical details

## How it is put together

### SCC version (base: Twin Bee SCC Enhanced, 128 KB → 256 KB, Konami SCC mapper)

| 8 KB banks | Contents |
| --- | --- |
| 0 | Boot code of the SCC version, with an added jump to the V9990 loader. |
| 1-3 | SCC sound driver and music. |
| 4 | V9990 loader and driver, with `sndfast` (fast PSG/SCC output) at the end. The driver is copied to RAM from D520h upwards and its variables live at C000h, areas the SCC version does not use (it uses C800h-C9FFh, D000h-D2FFh, D506h-D507h and D514h). |
| 5-8 | The game, with small patches: interrupt hook, writes to the TMS9918, ground-object registration, lower limit of the ship (1P and 2P), the point where enemies and bullets are removed when leaving at the bottom, font loader (for the X) and credits table. |
| 9-31 | V9990 graphics (tiles, maps, sprites and palettes), compressed. |

### PSG version (base: original Twin Bee, 32 KB → 256 KB, Konami mapper)

| 8 KB banks | Contents |
| --- | --- |
| 0-3 | The original game with the same small patches. INIT jumps to a stub at 4010h that maps bank 4. |
| 4 | V9990 loader and driver. The driver is copied to RAM at C800h and its variables live at C000h. `slotfix` (40D1h) sets the banks and the H.KEYI hook. |
| 5-31 | V9990 graphics, all RLE (there is plenty of room and loading is faster). |

### V9990 driver

- P1 mode, 256x212, two layers: B = "mapa N - paleta 1" and A = "mapa N - paleta 2". 64x64-tile maps in a 64-row ring buffer (A at 7C000h, B at 7E000h).
- **Line interrupt (line 191):** writes the high part of the next frame's scroll.
- **Vertical interrupt:**
  1. Writes the low part of the scroll first, before the picture starts (vital on real machines such as the Sony HB-F900).
  2. SCC music tick (SCC version only).
  3. Map and sprites.
  4. Jumps to the game's interrupt handler.
- The TMS9918 interrupt is acknowledged too, so the BIOS does not run its keyboard and clock routine.
- **Sprites:** each MSX sprite (pattern and colour) is translated into one or more 16-colour sprites, with per-context tables (stage and boss) in `src/sprites.py` (`COMMON` and `SPECIFIC`). Entries are stored in 256-byte pages, in the order they are sent to the V9990.
- **MSX screen:** during play it shows the pause window (stage, high score, scores and lives), updated about 7 times per second. It stays black during the demo.

## Changes made during testing

### Graphics and sprites

- Bells: the black one (the deadly one) had no drawing and looked yellow; it now has its own. In stage 3 the green bells used the black bell's drawing; fixed.
- Objects shown in white: the candy, the stage-3 star and the stage-4 hands now have drawings. The pot uses the one from the sprite sheet.
- Ship death (checked against the original ROM): the MSX alternates an all-white ship with the crashed ship. The white frames used to show the shielded ship; they now show the white silhouette of the ship itself (WinBee too).
- Ship hit: the splash and the small bee, both white in the new art, overlapped. Now the splash comes first and then the bee (`SPL_HALF` in `driver.asm`).
- Sprites repainted for a specific stage (for example the red bells of stage 2) were taken from stage 1. Each stage now always uses its own drawing.
- The ship no longer disappears when dropping bombs, when hit or with the siren (the tilted-ship drawings were missing).
- Enemy bullets on top of everything: they use entries 25-31 of the game's sprite table, and the driver now sends them first to the V9990, which draws the first sprites in front. They no longer hide behind clouds or enemies, nor get lost to the 16-sprites-per-line limit.
- Credits: new line **COLOR GUANTXIP**. The game had no letter X, so it was added to the font, on rows 1-7 of the character like the rest.

### Screen and scrolling

- **Full-screen flicker.** There were two causes:
  - The cut at line 192 was done by blanking the screen (R#8), and that bit is only read at the start of each frame: if the interrupt came late, a whole frame was lost. There is no cut now: the bottom 20 lines are part of the game (ship limit at C300h; enemies and bullets are removed from Y = D4h).
  - The TMS9918 interrupt made the BIOS run its routine, delaying the V9990 interrupt by up to 1.5 ms. The driver now cancels it.
- When a stage starts, on leaving pause or on changing stage, the map is redrawn in the hidden half of the ring over 4 frames, and switched in one go when finished.
- Stopped scroll (bosses): the fine offset kept counting while the game did not advance, and the background went back and forth ("moonwalker"). It is now computed from the last real scroll step. A background jolt every ~4 s with the scroll stopped was fixed too.
- **Shaking screen on the HB-F900:** in one test build the music ran before the scroll, and the low part of the scroll was written about 3 ms after the interrupt, with the picture already started. It is now written at about 0.3 ms, with the music right after.
- Logo and menu: the driver copied the whole MSX screen every frame. It now copies at most 64 characters per frame, and they run at the same speed as the SCC version.

### Bosses

- The map switched to the next stage's when the boss appeared (for boss 5, to a non-existent map). The boss is now fought over the end of its own stage's map.
- Each boss's island screen is drawn twice in the art (at the end of one map and the start of the next), with differences and different palettes, and beating the boss showed tiles or colours changing (reports by DTensoMSX). The converter now puts the same picture in both places, using colours both stages share, and picks for each boss the drawing that loses fewest colours (boss 2's lighthouse, boss 1's brown rocks).
- The coast strip of the map is kept under the island screen, in the next map too (it used to turn into sea, which looked like a flicker before the boss; report by Xavi Sorinas).
- Row above the boss screen: the converter appends to each map, after its last row, the row above the island screen in the next map. The same is shown during the boss and after it (double waves of boss 5, cliff at the top right).
- Bosses entering from the top start at Y = D1h, and when they die the game parks their sprites at Y = D0h; the MSX does not show them, but the V9990 has 20 more lines. Sprites with Y between D0h and DFh are no longer drawn.
- End of boss 5: the game sets the scroll back from position 1760 to 26, and the background dropped 5 lines (a little "dance"). Such a jump no longer moves the background.
- Stage 4 art: in "mapa - paleta 2" the cliffs of the last island screen were one row higher than in "paleta 1"; the converter fixes it.
- Music after dying at a boss: the stage music plays. This comes from the original game (the SCC version without GFX9000 does the same).

### SCC music

- Channels dropping when a tune started (report by Xavi Sorinas): the SCC player runs with interrupts enabled and its banks mapped; if the V9990 interrupt came at that point, the driver restored the game's banks. Now:
  - the music tick runs at the start of each frame, right after the scroll write;
  - if the interrupt arrives inside the player, the driver leaves everything alone;
  - redraws are spread over several frames so they do not delay the music.
  In 30 s of play the music performs 1798 ticks, the same as the SCC version without GFX9000.
- Sound during pause: the original SCC version makes exactly the same PSG and SCC writes during pause.

### Performance (SCC version)

Full playthrough in openMSX, in game-logic frames per second:

| | Before | Now | SCC without GFX9000 | Original (PSG) |
| --- | --- | --- | --- | --- |
| Stages 1-5 | 25.6-27.0 | 28.9-30.0 | 26.2-27.2 | 29.9-30.7 |
| Bosses 1 and 4 | 20.5-21.3 | 24.7-25.9 | 21.4-21.7 | 30.0 |
| Bosses 2, 3 and 5 | 24.9-26.5 | 28.8-29.5 | 23.8-25.6 | 30.0 |
| **Total** | **25.0** | **28.6** | **25.3** | **30.0** |

- **SCC player:** from 3.1 ms to 2.0 ms per tick. The PSG and SCC output was rewritten (`src/sndfast.asm`): it writes straight to the PSG ports instead of calling the BIOS (WRTPSG) and opens the SCC window only once. It writes exactly the same as before, checked register by register.
- **Sprites:** from 5.3 ms to 3.9 ms per logic frame: empty entries are skipped earlier and the data are already in sending order.
- The PSG version runs at 30.0, like the original.

### Compression

- Graphics are RLE, which unpacks fast, except for the blocks that need stronger compression (LZ) to fit in the SCC version (12 of 42). Initial loading takes about 2.2 s.
