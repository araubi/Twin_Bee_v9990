; ===========================================================================
;  Twin Bee (Konami RC-740) - V9990 / GFX9000 graphics driver
;  Boot code runs from ROM bank 4 mapped at 6000h, the driver itself is
;  copied to RAM at C000h and hooks into the original game.
; ===========================================================================

        OUTPUT  "boot.bin"

; ---- V9990 ports
V9_VRAM equ 60h
V9_PAL  equ 61h
V9_CMD  equ 62h
V9_REGD equ 63h
V9_REGS equ 64h
V9_STAT equ 65h
V9_INTF equ 66h
V9_SYS  equ 67h

    IFDEF SCC
; ---- Konami SCC mapper, game = "SCC Enhanced" re-assembly (banks 5-8)
BANKSEL equ 7000h       ; writes select the bank seen at 6000h-7FFFh
BOOTSEL equ 9000h       ; boot loader reads data through the 8000h window
BOOTOFS equ 2000h
GAMEBANK1 equ 6
G_ISR     equ 0C800h    ; interrupt handler of the SCC hack (in RAM)
G_SATUP   equ 460Bh
G_NAMEUP  equ 45ABh
DRV_ORG   equ 0D520h    ; (D000h-D2FFh, D506h-D507h and D514h are used by the SCC version)
VARS_ORG  equ 0C000h
G_2P      equ 4011h     ; Z = 1 player
G_STR     equ 4569h     ; draw string records DE into the name buffer
G_WINCLR  equ 4578h     ; clear window rows 4..19 from column 6, D = width
G_WNUM1   equ 4507h     ; window numbers: rest / scores / stage
G_WNUM2   equ 450Fh
G_WNUM3   equ 44EAh
T_1P      equ 4864h     ; window text records
T_2P      equ 485Dh
T_HI      equ 486Bh
T_R1      equ 4847h
T_R2      equ 483Ch
    ELSE
; ---- Konami mapper (no SCC), original 32KB game in banks 0-3
BANKSEL equ 6000h       ; writes select the bank seen at 6000h-7FFFh
BOOTSEL equ BANKSEL     ; boot loader (run from RAM) reads data through the 6000h window
BOOTOFS equ 0
GAMEBANK1 equ 1
G_ISR     equ 402Eh
G_INIT    equ 40B1h
G_SATUP   equ 46CEh     ; TMS sprite attribute upload
G_NAMEUP  equ 466Eh     ; TMS name table upload
DRV_ORG   equ 0C800h
VARS_ORG  equ 0C000h
G_2P      equ 4063h
G_STR     equ 462Ch
G_WINCLR  equ 463Bh
G_WNUM1   equ 45CAh
G_WNUM2   equ 45D2h
G_WNUM3   equ 45ADh
T_1P      equ 4924h
T_2P      equ 491Dh
T_HI      equ 492Bh
T_R1      equ 4907h
T_R2      equ 48FCh
    ENDIF
G_MODE    equ 0E000h
G_SUB     equ 0E001h
G_FRAME   equ 0E003h
G_BUSY    equ 0E005h
G_PAUSE   equ 0E079h
G_SCRPOS  equ 0EBF0h    ; map row at top of screen (16 bit)
G_SCRSTOP equ 0EBF2h    ; non-zero: scrolling halted (boss)
G_STAGE   equ 0EBB8h    ; stage 0..4
G_NAMEBUF equ 0EC40h
G_SATBUF  equ 0EF80h
RG7SAV    equ 0F3E6h

LZBUF    equ 0E000h     ; 4KB decompression buffer at boot (game RAM, cleared after)
CUT_LINE equ 191        ; display is switched off from this line (MSX screen = 192 lines)
SPR_R25_DEFAULT equ 4

        include "out/data_sym.inc"

; ===========================================================================
        ORG     6000h
boot:
        di
        ld      hl,drv_image
        ld      de,DRV_ORG
        ld      bc,drv_end-DRV_ORG
        ldir
        ld      hl,vars_image
        ld      de,VARS_ORG
        ld      bc,vars_end-VARS_ORG
        ldir
    IFDEF SCC
        call    v9_boot
        ; entered from the SCC hack init instead of 'jp 0C940h' (A = (F342h), 4000h on stack)
        ld      a,(0F342h)
        jp      0C940h          ; map the game banks and start it (ret -> 4000h)

        include "boot_v9.inc"
    ELSE
        ; entered from the INIT vector, with page 2 not on the cartridge yet:
        ; the loader runs from RAM and reads the data through the 6000h window
        jp      drv_start
    ENDIF

drv_image:
        DISP    DRV_ORG
; ===========================================================================
;  RAM resident part
; ===========================================================================

; ---------------------------------------------------------------- hooks
; (fixed entry points used by the patches in the game ROM)
hook_isr:       jp isr                  ; C000  H.KEYI handler
    IFDEF SCC
; (the patches call the routines directly)
hook_satup      equ satup               ; replaces call 46CEh in game frame
hook_nameup     equ nameup              ; replaces call/jp 466Eh in game frame
hook_obj        equ objdraw             ; object char drawing (aa51)
hook_ycmp       equ ycmp                ; player Y limit (61D8h, 62A4h)
hook_ykill      equ ykill               ; enemies/bullets leaving the screen (BADFh)
hook_tick       equ tick_gate           ; music tick call of the game ISR (C80Ch)
    ELSE
hook_satup      equ satup               ; replaces call 46CEh in game frame
hook_nameup     equ nameup              ; replaces call/jp 466Eh in game frame
hook_obj        equ objdraw             ; object char drawing (aa51)
hook_ycmp       equ ycmp
hook_ykill      equ ykill
hook_slot       equ slotfix             ; after ENASLT in game init (40d1)
    ENDIF

; called from game init right after page 2 was switched to the cartridge:
; set the Konami banks of 8000h/A000h (the BIOS RAM scan may have changed them)
; and install the H.KEYI hook (replaces the original 11 bytes at 40d1)
    IFNDEF SCC
slotfix:
        ld      a,2
        ld      (8000h),a
        ld      a,3
        ld      (0A000h),a
        ld      a,0C3h
        ld      (0FD9Ah),a
        ld      hl,hook_isr
        ld      (0FD9Bh),hl
        ret
    ENDIF

    IFNDEF SCC
; credits: the font loader (call 4699h at 49B3h) also loads an 'X' (char 35h,
; the game has none) into the 3 pattern generator thirds; staff record "COLOR
; GUANTXIP" (the SCC build has these in the free space at BF40h of the game)
cred_font:
        call    4699h
        ld      de,21A8h
        call    .one
        ld      de,29A8h
        call    .one
        ld      de,31A8h
.one:   ld      hl,.xg
        ld      bc,8
        jp      005Ch           ; LDIRVM
.xg:    db      00h,63h,63h,36h,1Ch,36h,63h,63h
cred_rec:
        db      08h,1Dh,2Eh,23h,2Eh,34h,0,0,0,2Dh,28h,2Fh,24h,27h,35h,21h,25h,0FFh

drv_start:
        call    v9_boot
        ld      a,GAMEBANK1
        ld      (BANKSEL),a
        jp      G_INIT

        include "boot_v9.inc"
    ENDIF

; ---- write register A with value E
wreg:
        out     (V9_REGS),a
        ld      a,e
        out     (V9_REGD),a
        ret

; ---- set VRAM write address  A:HL (A = bits 16-18)
setwr:
        push    af
        xor     a
        out     (V9_REGS),a
        ld      a,l
        out     (V9_REGD),a
        ld      a,h
        out     (V9_REGD),a
        pop     af
        out     (V9_REGD),a
        ret


; ---- hide all 125 V9990 sprites
sat_clear:
        ld      hl,0FE00h
        ld      a,3
        call    setwr
        ld      b,125
.l:     ld      a,216
        out     (V9_VRAM),a
        xor     a
        out     (V9_VRAM),a
        out     (V9_VRAM),a
        ld      a,10h           ; disabled
        out     (V9_VRAM),a
        djnz    .l
        xor     a
        ld      (spr_used),a
        ret

; ---- load palette set: HL = 192 bytes source (in bank A)
load_palette:
        ld      (BANKSEL),a
        ld      a,14
        ld      e,0
        call    wreg
        ld      bc,192*256+V9_PAL
        otir
        ld      a,GAMEBANK1
        ld      (BANKSEL),a
        ret

; ===========================================================================
;  game frame hooks
; ===========================================================================
satup:
    IFDEF KEEP_TMS
        jp      G_SATUP
    ENDIF
        ld      a,(v9ok)
        or      a
        jp      z,G_SATUP
        call    is_gp
        jp      nz,G_SATUP
        ret
nameup:
    IFDEF KEEP_TMS
        jp      G_NAMEUP
    ENDIF
        ld      a,(v9ok)
        or      a
        jp      z,G_NAMEUP
        call    is_gp
        jr      z,.gp
        xor     a
        ld      (tms_clean),a
        jp      G_NAMEUP
.gp:
        ; the MSX screen shows the information of the pause window (score, rest...)
        ld      a,(G_PAUSE)
        or      a
        jr      z,.np
        xor     a               ; the game draws its pause screen itself
        ld      (tms_clean),a
        ret
.np:    ld      a,(tms_clean)
        or      a
        jr      nz,.upd
        call    tms_clear
        ld      a,(G_MODE)
        cp      2               ; demo: MSX screen stays black
        ret     z
        jp      tms_info        ; whole window once
.upd:   ld      a,(G_MODE)
        cp      2
        ret     z
        ld      hl,info_tick
        inc     (hl)
        ld      a,(hl)
        and     3
        ret     nz
        jp      tms_nums        ; then only the numbers

WIN_BUF   equ G_NAMEBUF+4*32+6

; ---- numbers of the window (stage, rest, scores): drawn by the game routines into
; the name buffer, sent to the TMS, and the play field restored. Much cheaper than tms_info.
NUM_N   equ 6
num_tab:
        dw      0ECF2h : db 2   ; stage
        dw      0EDF1h : db 2   ; rest 1P
        dw      0ED51h : db 8   ; hi score
        dw      0EDB1h : db 8   ; 1P score
        dw      0EE91h : db 2   ; rest 2P   (only in 2 player mode)
        dw      0EE51h : db 8   ; 2P score
tms_nums:
        ld      ix,num_tab
        ld      de,num_save
        ld      b,NUM_N
.s:     ld      l,(ix+0)
        ld      h,(ix+1)
        ld      c,(ix+2)
        push    bc
        ld      b,0
        ldir
        pop     bc
        inc     ix
        inc     ix
        inc     ix
        djnz    .s
        call    G_WNUM1
        call    G_WNUM2
        call    G_WNUM3
        ld      ix,num_tab
        ld      b,NUM_N
        call    G_2P
        jr      nz,.u
        ld      b,4
.u:     push    bc
        ld      l,(ix+0)
        ld      h,(ix+1)
        push    hl
        ld      de,3800h-G_NAMEBUF
        add     hl,de
        call    0053h           ; SETWRT
        ld      a,(0007h)
        ld      c,a
        pop     hl
        ld      b,(ix+2)
.o:     outi
        nop
        jr      nz,.o
        inc     ix
        inc     ix
        inc     ix
        pop     bc
        djnz    .u
        ld      ix,num_tab
        ld      hl,num_save
        ld      b,NUM_N
.r:     ld      e,(ix+0)
        ld      d,(ix+1)
        ld      c,(ix+2)
        push    bc
        ld      b,0
        ldir
        pop     bc
        inc     ix
        inc     ix
        inc     ix
        djnz    .r
        ret

; clear the TMS name table and hide the TMS sprites
tms_clear:
        ld      a,1
        ld      (tms_clean),a
        ld      hl,3800h
        ld      bc,768
        xor     a
        call    0056h           ; FILVRM
        ld      a,0D0h
        ld      hl,3B00h
        jp      004Dh           ; WRTVRM

; draw the pause window texts (as the game does at 418Ah) and send the window
; to the TMS name table; the window area of the name buffer is restored after.
tms_info:
        ld      hl,WIN_BUF
        ld      de,info_save
        call    .copy
        ld      d,14h
        call    G_WINCLR
        call    G_2P
        ld      de,T_1P
        jr      z,.p1
        ld      de,T_2P
.p1:    call    G_STR
        call    G_WNUM2
        ld      de,T_HI
        call    G_STR
        call    G_WNUM1
        call    G_2P
        ld      de,T_R1
        jr      z,.p2
        ld      de,T_R2
.p2:    call    G_STR
        call    G_WNUM3
        ; window -> VRAM 3800h + 4*32 + 6
        ld      hl,WIN_BUF
        ld      de,3800h+4*32+6
        ld      b,16
.up:    push    bc
        push    hl
        push    de
        ex      de,hl
        call    0053h           ; SETWRT
        ld      a,(0007h)
        ld      c,a
        pop     de
        pop     hl
        push    hl
        ld      b,20
.o:     outi                    ; >= 29 T per byte for the TMS9918
        nop
        jr      nz,.o
        pop     hl
        ld      bc,32
        add     hl,bc
        ex      de,hl
        add     hl,bc
        ex      de,hl
        pop     bc
        djnz    .up
        ; restore the play field
        ld      hl,info_save
        ld      de,WIN_BUF
        ld      b,16
.r:     push    bc
        ld      bc,20
        ldir
        ex      de,hl
        ld      bc,12
        add     hl,bc
        ex      de,hl
        pop     bc
        djnz    .r
        ret
.copy:  ld      b,16
.c:     push    bc
        ld      bc,20
        ldir
        ld      bc,12
        add     hl,bc
        pop     bc
        djnz    .c
        ret
; Z if the game is in a gameplay mode (demo, stage start, playing)
is_gp:
        ld      a,(G_MODE)
        cp      2
        ret     z
        cp      4
        ret     z
        cp      5
        ret

; replaces 'ld a,h / cp 0AFh' of the player movement: with the GFX9000 the
; player can go down to the bottom of the 212 line screen
ycmp:   push    hl
        ld      a,(ymax16+1)
        ld      l,a
        ld      a,h
        cp      l
        pop     hl
        ret

; replaces 'ld a,(hl) / sub 0C0h / cp 20h' (enemy objects removed when Y is in
; C0h..DFh): with the GFX9000 they are removed from D4h, below the 212 lines
ykill:  ld      a,(hl)
        push    hl
        ld      hl,ykmin
        sub     (hl)
        inc     hl
        cp      (hl)
        pop     hl
        ret

; objdraw: replaces at aa51:  ld c,ffh / ldi / ldi / ld a,1eh / call 406fh / ldi / ldi
; HL = source chars, DE = destination in name buffer, B must be preserved
objdraw:
        push    de
        push    hl
        push    bc
        ld      a,(obj_cnt)
        cp      OBJ_MAX
        jr      nc,.skip
        inc     a
        ld      (obj_cnt),a
        dec     a
        ld      c,a
        add     a,a
        add     a,c
        add     a,a
        ld      c,a
        ld      b,0
        ld      hl,obj_list
        add     hl,bc
        ld      (hl),e
        inc     hl
        ld      (hl),d
        inc     hl
        ex      de,hl
        pop     bc
        pop     hl
        push    hl
        push    bc
        ld      bc,4
        ldir
.skip:
        pop     bc
        pop     hl
        pop     de
        ld      c,0FFh
        ldi
        ldi
        ld      a,1Eh
        add     a,e
        ld      e,a
        jr      nc,.n
        inc     d
.n:     ldi
        ldi
        ret

; ===========================================================================
;  interrupt handler (H.KEYI)
; ===========================================================================
isr:
        ld      a,(v9ok)
        or      a
        jp      z,G_ISR
        ld      a,(irq_on)
        or      a
        call    z,irq_enable    ; V9990 interrupts start once our handler is installed
        ; acknowledge the TMS9918 too, so the BIOS skips its (long) timer
        ; interrupt code: the game does not use it, and it used to delay the
        ; V9990 interrupts by up to 1.5 ms
        ld      a,(0006h)
        ld      c,a
        inc     c
        in      a,(c)
        in      a,(V9_INTF)
        ld      b,a
        bit     1,b
        jr      z,.nohi
        ld      a,2
        out     (V9_INTF),a     ; ack line interrupt (end of the MSX screen area)
        bit     0,b
        jr      nz,.nohi
        call    snd_busy
        ret     nz
        jp      hi_pre          ; scroll registers for the next frame, well before it starts
.nohi:
        bit     0,b
        ret     z
        ld      a,1
        out     (V9_INTF),a
        call    display_on      ; first thing: the next frame must not start blanked
        ; interrupted inside a sound request of the SCC version (it maps the
        ; sound banks over the game with interrupts enabled): the mapper must not
        ; be touched, so nothing is updated in this frame
        call    snd_busy
        jp      nz,G_ISR
        call    vblank
        call    do_tick         ; (if the V9990 update did not do it already)
        ld      a,GAMEBANK1
        ld      (BANKSEL),a
        jp      G_ISR

; NZ while the SCC version is inside a sound request (D507h = 1)
; NZ while the interrupt landed inside the SCC music tick (D506h, it runs with
; interrupts enabled and is skipped while flagged) or a sound request (D507h):
; keep the interrupt short so the music never loses a tick
snd_busy:
    IFDEF SCC
        ld      hl,(0D506h)         ; (HL is free in the interrupt handler)
        ld      a,l
        or      h
    ELSE
        xor     a
    ENDIF
        ret

; ---- SCC music tick, once per frame, as early as possible: right after the
; scroll registers (which must be written before the frame starts), so it never
; runs late and overlaps the next interrupt (which would skip its tick)
do_tick:
    IFDEF NOTICK
        ret
    ENDIF
    IFDEF SCC
        ld      a,(tick_done)
        or      a
        ret     nz
        ld      hl,0D506h
        inc     (hl)
        call    0C8C3h
        xor     a
        ld      (0D506h),a
        inc     a
        ld      (tick_done),a
    ENDIF
        ret

    IFDEF SCC
; the game ISR's tick call: skipped when the V9990 handler already did it
tick_gate:
        ld      a,(tick_done)
        or      a
        jp      z,0C8C3h
        xor     a
        ld      (tick_done),a
        ret
    ENDIF

irq_enable:
        ld      a,1
        ld      (irq_on),a
        ld      a,0FFh
        out     (V9_INTF),a     ; clear pending flags
        ld      a,9
        out     (V9_REGS),a
        ld      a,03h           ; vertical + line interrupt
        out     (V9_REGD),a
        ret

; line interrupt (end of the MSX screen area): if the game logic is idle, the
; state shown in the next frame is already final, write the scroll now
hi_pre:
        ld      a,(dmode)
        cp      DM_GAME
        ret     nz
        call    is_gp
        ret     nz
        ld      a,(G_BUSY)
        rrca
        ret     c
        ld      a,(G_PAUSE)
        ld      hl,paused
        or      (hl)
        ret     nz
        ld      a,(rows_valid)
        or      a
        ret     z
        call    map_stage
        ld      hl,cur_stage
        cp      (hl)
        ret     nz
        call    calc_scroll
        call    write_scroll_hi ; the high bits are taken at the start of the frame;
        call    stream_rows     ; the low bits act at once: they wait for the vblank
        ld      a,1
        ld      (scr_pre),a
        ld      a,GAMEBANK1
        ld      (BANKSEL),a
        ret

; back to the normal horizontal scroll for the next frame
display_on:
        ld      a,8
        out     (V9_REGS),a
        ld      a,(mir_clr)
        or      a
        ld      a,82h           ; display on, sprites on
        jr      z,.on
        ld      a,02h           ; blank while the layers are cleared
.on:    out     (V9_REGD),a
        ret

vblank:
        call    is_gp
        jp      z,game_frame
        jp      mirror_frame

; ===========================================================================
;  gameplay display
; ===========================================================================
game_frame:
        ld      a,(dmode)
        cp      DM_GAME
        jr      z,.ingame
        ; entering gameplay
        ld      a,DM_GAME
        ld      (dmode),a
        ld      a,15
        ld      e,0             ; backdrop: colour 0 (black)
        call    wreg
        ld      a,0FFh
        ld      (cur_stage),a
        xor     a
        ld      (mir_clr),a
.ingame:
        ld      a,(scr_pre)
        ld      (scr_did),a
        xor     a
        ld      (scr_pre),a
        ld      a,(G_BUSY)
        rrca
        jp      c,display_on    ; game logic still running: nothing consistent to show
        ; --- pause: keep the picture, hide sprites, show the text window
        ld      a,(G_PAUSE)
        or      a
        jr      z,.nopause
        ld      a,(G_MODE)
        cp      5
        jr      nz,.nopause
        call    display_on
        ld      a,(paused)
        or      a
        jr      nz,.pz
        inc     a
        ld      (paused),a
        xor     a
        ld      (mir_tick),a
        call    sat_clear
.pz:    ld      hl,mir_tick     ; the window is drawn twice (the text is static)
        ld      a,(hl)
        cp      17
        ret     nc
        inc     (hl)
        and     7
        ret     nz
        ld      a,(hl)
        cp      2
        ret     c
        jp      draw_pause
.nopause:
        ld      a,(paused)
        or      a
        jr      z,.np2
        xor     a
        ld      (paused),a
        ld      (rows_valid),a  ; window area must be redrawn from the map
        ld      (rb_left),a
.np2:
        ; --- stage change? (palette is switched together with the new map)
        call    map_stage
        ld      hl,cur_stage
        cp      (hl)
        call    nz,stage_switch
        ; --- whole map window to redraw? (stage start, life lost, end of pause)
        ; drawn into the other half of the ring, RB_ROWS rows per frame, while
        ; the old picture stays on screen; the scroll (and palette) flip happens
        ; at the interrupt after the last row (short interrupts: the SCC music
        ; tick is never delayed)
        ld      a,(rb_left)
        or      a
        jr      nz,.rb
        call    need_full
        jr      z,.inc
        call    rb_start
.rb:    call    do_tick
        call    rb_step
        jr      .spr
.inc:
        ; --- scroll registers (unless already written at the line interrupt)
        ld      a,(scr_did)
        or      a
        jr      nz,.lo
        call    calc_scroll
        call    write_scroll
        jr      .done
.lo:    call    write_scroll_lo
.done:  call    do_tick
        call    stream_rows
.spr:   call    spr_update
        xor     a
        ld      (obj_cnt),a
        ret

; ---- stage whose map is shown: the game already counts the next stage while
; the boss is fought (scroll stopped), but the boss is fought over the map of
; the stage that ends (after boss 5 the next stage is stage 1 again)
map_stage:
        ld      a,(G_SCRSTOP)
        or      a
        ld      a,(G_STAGE)
        jr      z,.run
        dec     a
        ret     p
        ; boss 5 (the counter is already back to stage 1): map 5 while the
        ; scroll is still at 1760, map 1 once the game moves it back to 26 (the
        ; island screen is the same picture in both)
.five:  ld      a,(G_SCRPOS+1)
        cp      4
        ld      a,0
        ret     c
        ld      a,4
        ret
.run:   or      a
        ret     nz
        jr      .five

; scroll value: Y = ((ring_base-pos)&63)*8 - phase
calc_scroll:
        xor     a
        ld      (phase),a
        ld      hl,(G_SCRPOS)
        ld      a,(ring_base)
        sub     l
        and     63
        ld      l,a
        ld      h,0
        add     hl,hl
        add     hl,hl
        add     hl,hl
        ; phase: the game moves one row every 16 frames (when frame&15 = 0); the
        ; picture moves 1 line every 2 frames since the last step, and stops at 7
        ; when the game stops scrolling (boss, after the last boss...)
        push    hl
        ld      hl,(G_SCRPOS)
        ld      de,(last_pos)
        or      a
        sbc     hl,de
        jr      z,.same
        dec     hl
        ld      a,h
        or      l               ; Z: a normal one-row step
        ld      hl,(G_SCRPOS)
        ld      (last_pos),hl
        jr      nz,.same        ; a jump (after boss 5: 1760 -> 26): the phase stays
        ld      a,(G_FRAME)
        and     0F0h
        ld      (step_t),a
        xor     a
        ld      (ph_sat),a
.same:  ld      a,(ph_sat)
        or      a
        jr      nz,.sat
        ld      a,(step_t)
        ld      e,a
        ld      a,(G_FRAME)
        sub     e
        cp      16
        jr      c,.ph
        ld      a,1             ; stopped: stays at the end of the step until the
        ld      (ph_sat),a      ; game moves again (the frame counter wraps)
.sat:   ld      a,15
.ph:    pop     hl
        srl     a
        ld      (phase),a
        ld      e,a
        ld      d,0
        or      a
        sbc     hl,de
        ld      a,h
        and     1
        ld      h,a
        ld      (scrolly),hl
        ret

write_scroll:
        call    write_scroll_hi
write_scroll_lo:
        ld      a,(pal_pend)
        or      a
        jr      z,.np
        xor     a
        ld      (pal_pend),a
        ld      hl,(pal_src)
        ld      a,PALS_BANK
        ld      bc,96*256+0
        call    load_pal_part
.np:    ld      hl,(scrolly)
        ld      a,17
        ld      e,l
        call    wreg
        ld      a,21
        ld      e,l
        jp      wreg
write_scroll_hi:
        ld      hl,(scrolly)
        ld      a,18
        ld      e,h
        call    wreg
        ld      a,22
        ld      e,h
        jp      wreg

; ---- switch to stage (G_STAGE): palette, sprite base, map, full redraw
stage_switch:
        ld      (cur_stage),a
        ; stage table entry
        ld      l,a
        ld      h,0
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl           ; *16
        ld      de,STAGE_TAB
        add     hl,de
        ld      de,st_K
        ld      bc,STAGE_TAB_SIZE
        ldir
        ; palette
        ld      a,(cur_stage)
        ld      l,a
        ld      h,0
        ld      e,l
        ld      d,h
        add     hl,hl
        add     hl,de           ; *3
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl           ; *192
        ld      de,PALS_ADDR
        add     hl,de
        ld      (pal_src),hl
        ld      a,1
        ld      (pal_pend),a
        xor     a
        ld      (rows_valid),a
        ld      (rb_left),a
        ld      a,0FFh
        ld      (cur_ctx),a
        ret

; ---- load B bytes of palette data from HL (bank A) starting at palette byte pointer C
load_pal_part:
        ld      (BANKSEL),a
        ld      a,14
        out     (V9_REGS),a
        ld      a,c
        out     (V9_REGD),a
        ld      c,V9_PAL
        otir
        ld      a,GAMEBANK1
        ld      (BANKSEL),a
        ret

; ===========================================================================
;  sprites
; ===========================================================================
; switch sprite context A (= stage*2 + boss)
ctx_switch:
        ld      (cur_ctx),a
        ld      l,a
        ld      h,0
        ld      e,l
        ld      d,h
        add     hl,hl
        add     hl,de
        add     hl,hl           ; *6
        ld      de,CTX_TAB
        add     hl,de
        ld      de,ctx_bank
        ld      bc,6
        ldir
        ; sprite palettes (entries 32..63) of the art fase
        ld      a,(ctx_fase)
        ld      l,a
        ld      h,0
        ld      e,l
        ld      d,h
        add     hl,hl
        add     hl,de           ; *3
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl           ; *192
        ld      de,PALS_ADDR+96
        add     hl,de
        ld      a,PALS_BANK
        ld      bc,96*256+128
        call    load_pal_part
        ; sprite pattern area of the fase: R25 = 4 + 2*fase
        ld      a,(ctx_fase)
        add     a,a
        add     a,4
        ld      e,a
        ld      a,25
        jp      wreg

spr_update:
        ld      a,(G_STAGE)
        add     a,a
        ld      b,a
        ld      a,(G_SCRSTOP)
        or      a
        jr      z,.nb
        inc     b
.nb:    ld      a,(cur_ctx)
        cp      b
        ld      a,b
        call    nz,ctx_switch
        ld      a,(ctx_bank)
        ld      (BANKSEL),a
        ld      hl,0FE00h
        ld      a,3
        call    setwr
        xor     a
        ld      (spl_seen),a
        ; entries 25-31 first (the enemy bullets): the V9990 draws the first
        ; sprites in front, so the bullets are not hidden by clouds and enemies
        ld      ix,G_SATBUF+25*4
        xor     a
        ld      (spr_n),a
        ld      (prev_pc),a     ; previous MSX entry: pattern 00 with colour != 7 -> WinBee
.loop:
        ld      a,(ix+0)
        cp      0E0h            ; unused entry (Y=E0h, colour 0): nothing to do
        jr      nz,.used
        ld      a,(ix+3)
        and     15
        jp      z,.next0
        ld      a,0E0h
        ; Y D0h-DFh: below the MSX screen, in the last lines of the V9990 one.
        ; The game parks sprites there (a dead boss) and a boss entering from
        ; the top starts there: hidden, as on the MSX. (Objects leaving the
        ; screen downwards lose only their last 3 lines.)
.used:  cp      0D0h
        jr      c,.yv
        cp      0E0h
        jp      c,.next0
.yv:    ld      c,a             ; C = Y
        ld      a,(ix+2)
        and     0FCh
        ld      b,a             ; B = pattern
        ; crash animation: the MSX shows the splash (24h) and the small bee (28h)
        ; together; here the splash comes first and the small bee after it
        cp      24h
        jr      nz,.n24
        ld      (spl_seen),a
        ld      a,(spl_cnt)
        cp      SPL_HALF+1
        jp      nc,.next0       ; second half: only the small bee
        jr      .sok
.n24:   cp      28h
        jr      nz,.sok
        ld      a,(spl_cnt)
        cp      SPL_HALF+1
        jp      c,.next0        ; first half: only the splash
.sok:
        ld      a,(ix+3)
        and     15
        jp      z,.next0
        ; table[pattern*4 + colour] = entry number
        ld      l,b
        ld      h,0
        add     hl,hl
        add     hl,hl
        or      l
        ld      l,a
        ld      de,(ctx_tab)
        add     hl,de
        ld      a,(hl)
        or      a
        jp      z,.next
        ; entry A: byte k at (entries page + k)*256 + A
        ld      l,a
        ld      a,(ctx_ent+1)
        ld      h,a
        ; DE = X - 64 (the dx of the entries are biased by +64), -32 with early clock
        ld      a,(ix+1)
        sub     64
        ld      e,a
        sbc     a,a
        ld      d,a
        bit     7,(ix+3)
        jr      z,.xok
        ld      a,e
        sub     32
        ld      e,a
        jr      nc,.xok
        dec     d
.xok:   ld      a,(hl)          ; flags|count
        inc     h
        add     a,a             ; Cy: WinBee/TwinBee entry
        push    af
        rrca
        and     7
        ld      b,a
        ld      a,(spr_n)
        add     a,b
        ld      (spr_n),a
        pop     af
        jr      nc,.s
        ld      a,(prev_pc)
        or      a
        jr      nz,.sb
        ; sub-sprites: dy, pattern, dx+64, attr -> V9990 Y, pattern, X, X high|attr
.s:     ld      a,(hl)
        add     a,c
        out     (V9_VRAM),a
        inc     h
        ld      a,(hl)
        out     (V9_VRAM),a
        inc     h
        ld      a,(hl)
        inc     h
        add     a,e
        out     (V9_VRAM),a
        ld      a,d
        adc     a,0
        and     3
        or      (hl)
        inc     h
        out     (V9_VRAM),a
        djnz    .s
        jr      .next
.sb:    ld      a,(hl)          ; (WinBee: patterns + 16)
        add     a,c
        out     (V9_VRAM),a
        inc     h
        ld      a,(hl)
        add     a,16
        out     (V9_VRAM),a
        inc     h
        ld      a,(hl)
        inc     h
        add     a,e
        out     (V9_VRAM),a
        ld      a,d
        adc     a,0
        and     3
        or      (hl)
        inc     h
        out     (V9_VRAM),a
        djnz    .sb
.next:
        ; remember for WinBee detection (WinBee body = pattern 0Ch)
        ld      c,0
        ld      a,(ix+2)
        and     0FCh
        cp      0Ch
        jr      nz,.np
        dec     c
.np:    ld      a,c
        ld      (prev_pc),a
.next0:
        ld      de,4
        add     ix,de
        ld      a,ixh           ; 32 entries: EFE4h..EFFFh, then EF80h..EFE3h
        cp      HIGH (G_SATBUF+128)
        jr      nz,.nw
        ld      ix,G_SATBUF
.nw:    ld      a,ixl
        cp      LOW (G_SATBUF+25*4)
        jp      nz,.loop
.done:
        ld      a,(spl_seen)
        or      a
        jr      z,.spz
        ld      a,(spl_cnt)
        inc     a
        jr      z,.sp1
        ld      (spl_cnt),a
        jr      .sp1
.spz:   ld      (spl_cnt),a
.sp1:
        ; ---- ground objects (2x2 chars in the name buffer) as sprites
        ld      a,(obj_cnt)
        or      a
        jp      z,.noobj
        ld      b,a
        ld      hl,obj_list
.ol:    push    bc
        push    hl
        ld      e,(hl)
        inc     hl
        ld      d,(hl)
        inc     hl
        ld      c,(hl)
        inc     hl
        ld      a,(hl)
        ld      (tmp_tr),a
        push    de
        ld      hl,OBJ_QUADS
        ld      b,OBJ_NQUADS
        ld      e,0
.fq:    ld      a,(hl)
        cp      c
        jr      nz,.fn
        inc     hl
        ld      a,(tmp_tr)
        cp      (hl)
        dec     hl
        jr      z,.ff
.fn:    inc     hl
        inc     hl
        inc     e
        djnz    .fq
        pop     de
        jr      .onext
.ff:    ld      a,e
        ld      (tmp_q),a
        pop     de
        ld      hl,-G_NAMEBUF
        add     hl,de
        ld      a,l
        and     31
        add     a,a
        add     a,a
        add     a,a
        ld      (tmp_x),a
        ld      a,l
        and     0E0h
        ld      l,a
        sra     h
        rr      l
        sra     h
        rr      l
        ld      a,(phase)
        ld      e,a
        ld      d,0
        add     hl,de
        ld      de,15           ; -1 (sprite Y) +16 (clip bias)
        add     hl,de
        ld      a,h
        or      a
        jr      nz,.onext
        ld      a,l
        cp      207
        jr      nc,.onext
        sub     16
        ld      (tmp_oy),a
        ld      a,(tmp_q)
        add     a,a
        ld      e,a
        ld      d,0
        ld      hl,(ctx_tab)
        add     hl,de
        ld      de,1024
        add     hl,de
        ld      a,(tmp_oy)
        out     (V9_VRAM),a
        ld      a,(hl)
        out     (V9_VRAM),a
        inc     hl
        ld      a,(tmp_x)
        out     (V9_VRAM),a
        ld      a,(hl)
        out     (V9_VRAM),a
        ld      a,(spr_n)
        inc     a
        ld      (spr_n),a
.onext: pop     hl
        ld      de,6
        add     hl,de
        pop     bc
        dec     b
        jp      nz,.ol
.noobj:
        ; hide sprites that were used last frame but not now
        ld      a,(spr_used)
        ld      b,a
        ld      a,(spr_n)
        ld      (spr_used),a
        sub     b
        jr      nc,.fin
        neg
        ld      b,a
.hide:  ld      a,216
        out     (V9_VRAM),a
        xor     a
        out     (V9_VRAM),a
        out     (V9_VRAM),a
        ld      a,10h
        out     (V9_VRAM),a
        djnz    .hide
.fin:   ld      a,GAMEBANK1
        ld      (BANKSEL),a
        ret

; ---- NZ if the whole window of map rows has to be rebuilt
need_full:
        ld      a,(rows_valid)
        or      a
        jr      z,.yes
        ld      hl,(G_SCRPOS)
        inc     hl
        ld      de,(top_written)
        or      a
        sbc     hl,de
        jr      c,.yes          ; went backwards
        ld      a,h
        or      a
        jr      nz,.yes
        ld      a,l
        cp      9
        jr      nc,.yes
        xor     a
        ret
.yes:   or      1
        ret

; ---- make sure map rows up to pos+1 are present in the ring (small steps only)
stream_rows:
        call    need_full
        ret     nz
        ld      hl,(G_SCRPOS)
        inc     hl
        ld      de,(top_written)
        or      a
        sbc     hl,de
        ld      a,l
        or      a
        ret     z
        ld      b,a
.inc:   push    bc
        ld      hl,(top_written)
        inc     hl
        ld      (top_written),hl
        call    write_row
        pop     bc
        djnz    .inc
        ret

; ---- rows pos-26 .. pos+1 into the half of the ring that is not on screen
RB_ROWS equ 7
rb_start:
        ; ring row of the top row = (shown top ring row + 31) & 63
        ld      hl,(scrolly)
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl           ; h = (Y >> 3) & 63 (bits 3..8 of Y)
        ld      a,h
        and     63
        add     a,31
        ld      hl,(G_SCRPOS)
        inc     hl
        add     a,l             ; new ring_base = top ring row + (pos+1)
        and     63
        ld      (rb_base),a
        ld      de,-28
        add     hl,de
        ld      (rb_top),hl
        ld      a,28            ; rows pos-26..pos+1 (the V9990 shows 26.5 rows)
        ld      (rb_left),a
        xor     a
        ld      (rows_valid),a
        ret

rb_step:
        ld      a,(ring_base)
        push    af
        ld      a,(rb_base)
        ld      (ring_base),a
        ld      a,(rb_left)
        ld      b,RB_ROWS
        cp      b
        jr      nc,.n
        ld      b,a
.n:     sub     b
        ld      (rb_left),a
.l:     push    bc
        ld      hl,(rb_top)
        inc     hl
        ld      (rb_top),hl
        call    write_row
        pop     bc
        djnz    .l
        pop     bc              ; b = shown ring_base
        ld      a,(rb_left)
        or      a
        jr      nz,.keep
        ld      hl,(rb_top)     ; done: the new ring_base stays
        ld      (top_written),hl
        inc     a
        ld      (rows_valid),a
        ret
.keep:  ld      a,b
        ld      (ring_base),a
        ret

; ---- write map row L (HL) of current stage to both layers
write_row:
        ; ring row RR = (-L) & 63 ; vram offset = RR*128
        ld      a,(ring_base)
        sub     l
        and     63
        ld      (tmp_rr),a
        ; image row y = K - L, clamped to 0..Hm1
        ex      de,hl
        ld      hl,(st_K)
        or      a
        sbc     hl,de
        jr      nc,.notneg
        ld      hl,(st_top)     ; above the top of the map: the extra row after the last one
        jr      .inrange
.notneg:
        ld      de,(st_Hm1)
        push    hl
        or      a
        sbc     hl,de
        pop     hl
        jr      c,.inrange
        jr      z,.inrange
        ex      de,hl
.inrange:
        ld      (tmp_y),hl
        ; layer A
        ld      a,(st_bankA)
        ld      de,(st_rlA)
        ld      bc,(st_dA)
        ld      ix,0C000h       ; low 16 bits of 7C000h
        call    .layer
        ; layer B
        ld      a,(st_bankB)
        ld      de,(st_rlB)
        ld      bc,(st_dB)
        ld      ix,0E000h       ; low 16 bits of 7E000h
        call    .layer
        ld      a,GAMEBANK1
        ld      (BANKSEL),a
        ret
.layer:
        ld      (BANKSEL),a
        ld      hl,(tmp_y)
        add     hl,de
        ld      l,(hl)          ; dict index
        ld      h,0
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl           ; *64
        add     hl,bc
        push    hl
        ; vram address = 70000h + ix + RR*128
        ld      a,(tmp_rr)
        ld      l,0
        srl     a
        rr      l
        ld      h,a             ; hl = RR*128
        push    ix
        pop     de
        add     hl,de
        ld      a,7
        call    setwr
        pop     hl
        ld      bc,64*256+V9_VRAM
        otir
        ret

; ===========================================================================
;  non gameplay screens: mirror the TMS9918 name table
; ===========================================================================
mirror_frame:
        call    display_on
        xor     a
        ld      (tms_clean),a
        ld      a,(dmode)
        cp      DM_MIRROR
        jr      z,.in
        ld      a,DM_MIRROR
        ld      (dmode),a
        call    mirror_enter
.in:
        call    do_tick         ; nothing time-critical here: the music first
        ld      a,(mir_clr)
        or      a
        jp      nz,mir_clear_step
        ld      a,(G_BUSY)
        rrca
        ret     c
        ; backdrop colour from TMS R7
        ld      a,(RG7SAV)
        and     15
        add     a,16
        ld      e,a
        ld      a,15
        call    wreg
        ; which mapping table: 0 logo, 1 title (modes 1,3), 2+stage otherwise
        ld      a,(G_MODE)
        or      a
        jr      z,.t
        ld      b,1
        cp      1
        jr      z,.t1
        cp      3
        jr      z,.t1
        ld      a,2
        jr      .t
.t1:    ld      a,b
.t:     call    mir_select
        ; compare the TMS name table with the copy, 256 cells per interrupt and
        ; at most MIR_MAX changed cells (each costs ~150 us): the interrupt
        ; stays well inside one frame, so the music tick and the game logic are
        ; never delayed; a whole new screen is drawn in a few frames
        ld      de,(mir_pos)
        ld      hl,mir_copy
        add     hl,de
        ld      a,(0007h)       ; VDP read port
        ld      c,a
        inc     c
        out     (c),e
        ld      a,38h
        add     a,d
        out     (c),a
        dec     c
        ld      a,MIR_MAX
        ld      (mir_left),a
        ld      b,0
.loop:
        in      a,(c)
        cp      (hl)
        jr      z,.nx
        call    mir_cell
        ld      a,(mir_left)
        dec     a
        ld      (mir_left),a
        jr      nz,.nx
        ld      b,1             ; budget spent: stop after this cell
.nx:    inc     hl
        inc     de
        ld      a,d
        cp      3
        jr      nc,.wrap
        djnz    .loop
        jr      .sv
.wrap:  ld      de,0
.sv:    ld      (mir_pos),de
        ld      a,GAMEBANK1
        ld      (BANKSEL),a
        ret

MIR_MAX equ 64

; cell DE changed to char A: (HL = copy ptr)
mir_cell:
        ld      (hl),a
        push    hl
        push    bc
        push    de
        ; tile = mir_tab[(third*256 + char)] (word), third = DE>>8
        ld      l,a
        ld      h,d
        add     hl,hl
        ld      bc,(mir_tab)
        add     hl,bc
        ld      a,(mir_bank)
        ld      (BANKSEL),a
        ld      c,(hl)
        inc     hl
        ld      b,(hl)
        ; vram address 7C000h + row*128 + col*2  (row = DE>>5, col = DE&31)
        ld      a,e
        and     31
        add     a,a
        ld      l,a             ; col*2
        ; row = DE >> 5 (0..23) -> row*128 = DE>>5<<7 = (DE&~31)<<2
        ld      a,e
        and     0E0h
        ld      h,d
        add     a,a
        rl      h
        add     a,a
        rl      h               ; h:a = (DE&~31)*4
        or      l
        ld      l,a
        ld      a,h
        add     a,0C0h
        ld      h,a
        ld      a,7
        call    setwr
        ld      a,c
        out     (V9_VRAM),a
        ld      a,b
        out     (V9_VRAM),a
        pop     de
        pop     bc
        pop     hl
        ret

; select mirror table A (index into MIR_DIR); a change forces a full redraw
mir_select:
        ld      hl,mir_id
        cp      (hl)
        jr      z,.same
        ld      (hl),a
        push    af
        ld      hl,mir_copy
        ld      de,mir_copy+1
        ld      bc,767
        ld      (hl),0FFh
        ldir
        pop     af
.same:
        ld      l,a
        ld      h,0
        ld      e,l
        ld      d,h
        add     hl,hl
        add     hl,de
        ld      de,MIR_DIR
        add     hl,de
        ld      a,(hl)
        ld      (mir_bank),a
        inc     hl
        ld      e,(hl)
        inc     hl
        ld      d,(hl)
        ld      (mir_tab),de
        ret

; ---- pause window: rows 4..19, columns 6..25 of the name buffer onto layer A
draw_pause:
        call    map_stage
        add     a,3
        ld      (mir_id),a      ; (mirror copy is invalid anyway after a pause)
        ld      l,a
        ld      h,0
        ld      e,l
        ld      d,h
        add     hl,hl
        add     hl,de
        ld      de,MIR_DIR
        add     hl,de
        ld      a,(hl)
        ld      (BANKSEL),a
        inc     hl
        ld      e,(hl)
        inc     hl
        ld      d,(hl)
        ld      (mir_tab),de
        ld      b,4             ; screen row
.row:   push    bc
        ; ring row of map row (pos - screen row)
        ld      hl,(G_SCRPOS)
        ld      a,(ring_base)
        sub     l
        add     a,b
        and     63
        ld      l,0
        srl     a
        rr      l
        ld      h,a             ; RR*128
        ld      de,0C000h+12    ; layer A + column 6
        add     hl,de
        ld      a,7
        call    setwr
        pop     bc
        push    bc
        ; source = namebuf + row*32 + 6
        ld      l,b
        ld      h,0
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        add     hl,hl
        ld      de,G_NAMEBUF+6
        add     hl,de
        ld      a,b
        rrca
        rrca
        rrca
        and     3
        ld      d,a             ; third
        ld      c,20
.col:   ld      e,(hl)
        push    hl
        ex      de,hl
        add     hl,hl
        ld      de,(mir_tab)
        add     hl,de
        ld      a,(hl)
        out     (V9_VRAM),a
        inc     hl
        ld      a,(hl)
        out     (V9_VRAM),a
        pop     hl
        ld      a,b             ; keep d = third
        rrca
        rrca
        rrca
        and     3
        ld      d,a
        inc     hl
        dec     c
        jr      nz,.col
        pop     bc
        inc     b
        ld      a,b
        cp      20
        jr      nz,.row
        ld      a,GAMEBANK1
        ld      (BANKSEL),a
        ret

mirror_enter:
        ; palette (TMS colours) + clear visible window of both layers
        ld      hl,MIRPAL_ADDR
        ld      a,MIRPAL_BANK
        call    load_palette
        xor     a
        ld      (pal_pend),a
        ld      hl,0
        ld      (scrolly),hl
        call    write_scroll
        call    sat_clear
        ; rows 0..26 cols 0..31 of A and B are cleared in the next interrupts
        ; (MIR_CLR rows each), with the display blanked
        ld      a,27
        ld      (mir_clr),a
        call    display_on
        ld      a,0FFh
        ld      (mir_id),a
        ld      a,0FFh
        ld      (cur_stage),a
        xor     a
        ld      (rows_valid),a
        ld      (rb_left),a
        ret
MIR_CLR equ 7
mir_clear_step:
        ld      a,(mir_clr)
        ld      b,MIR_CLR
        cp      b
        jr      nc,.n
        ld      b,a
.n:     sub     b
        ld      (mir_clr),a
        ; first row = 27 - (rows left before this step) ; HL = row*128
        add     a,b
        neg
        add     a,27
        ld      l,0
        srl     a
        rr      l
        ld      h,a
        push    bc
        push    hl
        ld      ix,0C000h
        call    .clr
        pop     hl
        pop     bc
        ld      ix,0E000h
.clr:
.r:     push    bc
        push    hl
        push    ix
        pop     de
        add     hl,de
        ld      a,7
        call    setwr
        ld      b,64
        xor     a
.c:     out     (V9_VRAM),a
        djnz    .c
        pop     hl
        ld      de,128
        add     hl,de
        pop     bc
        djnz    .r
        ret

        include "out/data_tab.inc"

drv_end:
        ENT
vars_image:
        DISP    VARS_ORG
; ===========================================================================
;  variables
; ===========================================================================
DM_NONE   equ 0
DM_GAME   equ 1
DM_MIRROR equ 2
OBJ_MAX   equ 8
SPL_HALF  equ 2          ; sprite updates showing the splash before the small bee

v9ok:           db 0
irq_on:         db 0
dmode:          db 0
cur_stage:      db 0FFh
cur_ctx:        db 0FFh
ctx_bank:       db 0
ctx_tab:        dw 0
ctx_ent:        dw 0
ctx_fase:       db 0
spr_n:          db 0
prev_pc:        db 0
sp_y:           db 0
sp_x:           dw 0
sp_flags:       db 0
phase:          db 0
tmp_tr:         db 0
tmp_q:          db 0
tmp_x:          db 0
tmp_oy:         db 0
rows_valid:     db 0
rb_left:        db 0
tick_done:      db 0
rb_base:        db 0
rb_top:         dw 0
spr_used:       db 0
mir_tick:       db 0
scrolly:        dw 0
top_written:    dw 0
tmp_target:     dw 0
tmp_y:          dw 0
tmp_rr:         db 0
mir_tab:        dw 0
mir_bank:       db 0
mir_id:         db 0FFh
paused:         db 0
obj_cnt:        db 0
; current stage parameters (copy of STAGE_TAB entry)
st_K:           dw 0
st_Hm1:         dw 0
st_bankA:       db 0
st_rlA:         dw 0
st_dA:          dw 0
st_bankB:       db 0
st_rlB:         dw 0
st_dB:          dw 0
st_top:         dw 0
lz_end:         dw 0
ykmin:          db 0C0h, 20h ; enemy objects removed when Y-ykmin < ykmin+1
ymax16:         dw 0AF00h  ; lowest player Y (8.8): AF00h = MSX screen, C300h = 212 lines
scr_pre:        db 0
ring_base:      db 0
last_pos:       dw 0FFFFh
step_t:         db 0
ph_sat:         db 0
prev_stop:      db 0
pal_pend:       db 0
pal_src:        dw 0
mir_pos:        dw 0
mir_left:       db 0
mir_clr:        db 0
spl_cnt:        db 0
spl_seen:       db 0
scr_did:        db 0
tms_clean:      db 0
info_tick:      db 0
info_save:      ds 320
num_save:       ds 30
obj_list:       ds OBJ_MAX*6
mir_copy:       ds 768

vars_end:
        ENT
        ASSERT  drv_end <= 0E000h
        ASSERT  vars_end <= 0C800h
        ASSERT  (G_SATBUF & 255) == 80h
boot_end:
        ASSERT  boot_end - 6000h <= 8192
