; ---- V9990 detection and graphics upload (boot)
v9_boot:
        call    v9_detect
        ret     nz
        ld      a,1
        ld      (v9ok),a
        ld      hl,0C300h
        ld      (ymax16),hl
        ld      hl,0CD4h        ; remove enemy objects from Y = D4h (below the screen)
        ld      (ykmin),hl
        call    v9_init
        call    upload_all
        call    sat_clear
        jp      v9_enable

; ---- detect: Z if present
v9_detect:
        ld      a,15
        out     (V9_REGS),a
        ld      a,15h
        out     (V9_REGD),a
        ld      a,15
        out     (V9_REGS),a
        in      a,(V9_REGD)
        cp      15h
        ret     nz
        ld      a,15
        out     (V9_REGS),a
        ld      a,2Ah
        out     (V9_REGD),a
        ld      a,15
        out     (V9_REGS),a
        in      a,(V9_REGD)
        cp      2Ah
        ret

v9_init:
        ld      a,2             ; software reset
        out     (V9_SYS),a
        xor     a
        out     (V9_SYS),a      ; MCS=0 (XTAL)
        ld      hl,init_regs
.l:     ld      a,(hl)
        cp      0FFh
        ret     z
        inc     hl
        ld      e,(hl)
        inc     hl
        call    wreg
        jr      .l

init_regs:
        db      6,05h           ; P1 mode, 512 dot image, 4bpp
        db      7,00h           ; NTSC, non interlaced
        db      8,02h           ; display off, 512KB
        db      9,00h           ; no interrupts
        db      13,01h          ; layer A palette 1, layer B palette 0
        db      15,00h          ; backdrop colour 0
        db      16,00h
        db      17,0,18,0,19,0,20,0
        db      21,0,22,0,23,0,24,0
        db      25,SPR_R25_DEFAULT
        db      26,0
        db      27,0
        db      0FFh

; ---- upload all graphics blobs listed in UPLOAD_TAB
upload_all:
        ; clear both name tables (7C000h-7FFFFh): the unused columns 32-63 are
        ; shown below line 192
        ld      hl,0C000h
        ld      a,7
        call    setwr
        ld      d,64
        xor     a
.clr:   ld      b,0
.clr2:  out     (V9_VRAM),a
        djnz    .clr2
        dec     d
        jr      nz,.clr
        ld      ix,UPLOAD_TAB
        ld      b,UPLOAD_COUNT
.next:
        push    bc
        ld      l,(ix+0)
        ld      h,(ix+1)
        ld      a,(ix+2)
        and     7
        call    setwr
        ld      a,(ix+3)
        ld      (BOOTSEL),a
        ld      l,(ix+4)
        ld      h,(ix+5)
    IFDEF SCC
        ld      de,BOOTOFS
        add     hl,de
    ENDIF
        ld      e,(ix+6)
        ld      d,(ix+7)
        ex      de,hl
        add     hl,de
        ex      de,hl           ; de = end of the compressed blob
        bit     7,(ix+2)
        jr      nz,.lz
        ; ---- RLE chunk, straight to VRAM (fast)
.rle:   ld      a,l
        cp      e
        jr      nz,.rg
        ld      a,h
        cp      d
        jr      z,.done
.rg:    ld      a,(hl)
        inc     hl
        cp      128
        jr      nc,.run
        inc     a
        ld      b,a
        ld      c,V9_VRAM
        otir
        jr      .rle
.run:   sub     125
        ld      b,a
        ld      a,(hl)
        inc     hl
.rl:    out     (V9_VRAM),a
        djnz    .rl
        jr      .rle
        ; ---- LZ chunk (smaller, slower): decoded in RAM, then sent
.lz:    ld      (lz_end),de
        ld      de,LZBUF
.dec:   ld      a,(lz_end)
        cp      l
        jr      nz,.go
        ld      a,(lz_end+1)
        cp      h
        jr      z,.out
.go:    ld      a,(hl)
        inc     hl
        ld      b,0
        cp      128
        jr      nc,.match
        inc     a
        ld      c,a
        ldir
        jr      .dec
.match: and     7Fh
        add     a,3
        ld      c,a
        ld      a,(hl)
        inc     hl
        push    hl
        ld      h,(hl)
        ld      l,a             ; hl = distance
        push    de
        ex      de,hl
        or      a
        sbc     hl,de           ; hl = dest - distance
        pop     de
        ldir
        pop     hl
        inc     hl
        jr      .dec
        ; decoded chunk LZBUF..DE -> VRAM
.out:   ex      de,hl
        ld      de,LZBUF
        or      a
        sbc     hl,de
        ld      a,h
        ld      e,l
        ld      hl,LZBUF
        ld      c,V9_VRAM
        or      a
        jr      z,.rest
.blk:   ld      b,0
        otir
        dec     a
        jr      nz,.blk
.rest:  ld      a,e
        or      a
        jr      z,.done
        ld      b,a
        otir
.done:
        ld      de,8
        add     ix,de
        pop     bc
        dec     b
        jp      nz,.next
        ld      a,GAMEBANK1
        ld      (BOOTSEL),a
        ; leave the buffer (game RAM) clean
        ld      hl,LZBUF
        ld      de,LZBUF+1
        ld      bc,4095
        ld      (hl),0
        ldir
        ret

; ---- display on, line + vertical interrupts
v9_enable:
        ld      a,8
        ld      e,082h          ; display on
        call    wreg
        ld      a,10
        ld      e,CUT_LINE
        call    wreg
        ld      a,11
        ld      e,0
        call    wreg
        ld      a,12
        ld      e,0
        jp      wreg            ; (interrupts are enabled by the handler itself)

        include "out/data_upl.inc"

