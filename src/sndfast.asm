; ===========================================================================
;  Faster output of the SCC registers for the sound driver of the SCC version.
;  Runs from the end of ROM bank 4, which the sound driver maps at A000h-BFFFh.
;  Replaces 'call 5213h' at 5136h: same writes as 5220h+5325h+5377h (compare
;  each channel's frequency and volume with the driver's copies at D2A3h-D2B2h,
;  write the ones that changed), then the waveforms as before (543Ch).
;  The SCC registers are mapped once instead of once per register.
; ===========================================================================
        OUTPUT  "sndfast.bin"
        ORG     0BE00h

   MACRO SCCV src, copy, reg
        ld      a,(src)
        cp      (hl)            ; HL = copy
        jr      z,.same
        ld      (hl),a
        ld      (reg),a
.same:  inc     hl
   ENDM

scc_out:
        ld      a,3Fh
        ld      (9000h),a
        ld      hl,0D2A3h       ; frequencies, 2 per channel
        SCCV    0D0CBh,0,9880h
        SCCV    0D0CCh,0,9881h
        SCCV    0D10Bh,0,9882h
        SCCV    0D10Ch,0,9883h
        SCCV    0D14Bh,0,9884h
        SCCV    0D14Ch,0,9885h
        SCCV    0D18Bh,0,9886h
        SCCV    0D18Ch,0,9887h
        SCCV    0D1CBh,0,9888h
        SCCV    0D1CCh,0,9889h
        ; (HL = D2ADh) volumes
        SCCV    0D0CDh,0,988Ah
        SCCV    0D10Dh,0,988Bh
        SCCV    0D14Dh,0,988Ch
        SCCV    0D18Dh,0,988Dh
        SCCV    0D1CDh,0,988Eh
        ; channel enable: a channel plays while its byte at D0CEh+40h*n is not 0
        ld      e,0
        ld      a,(0D0CEh)
        or      a
        jr      z,.e0
        set     0,e
.e0:    ld      a,(0D10Eh)
        or      a
        jr      z,.e1
        set     1,e
.e1:    ld      a,(0D14Eh)
        or      a
        jr      z,.e2
        set     2,e
.e2:    ld      a,(0D18Eh)
        or      a
        jr      z,.e3
        set     3,e
.e3:    ld      a,(0D1CEh)
        or      a
        jr      z,.e4
        set     4,e
.e4:    ld      a,e             ; (HL = D2B2h)
        cp      (hl)
        jr      z,.ee
        ld      (hl),a
        ld      (988Fh),a
.ee:    ld      a,2
        ld      (9000h),a
        jp      543Ch           ; waveforms
; ---------------------------------------------------------------------------
; PSG output (replaces 'call 513Ah' at 5133h): the same writes as 5147h-51FFh,
; with direct port writes instead of a call per register
   MACRO PSGW reg, src
        ld      a,reg
        out     (0A0h),a
        ld      a,(src)
        out     (0A1h),a
   ENDM
   MACRO PSGCH n, base
        PSGW    2*n, base
        PSGW    2*n+1, base+1
        ld      hl,base+3
        bit     3,(hl)
        jr      nz,.skip
        PSGW    8+n, base+2
        bit     2,(hl)
        jr      z,.skip
        set     3,(hl)
.skip:
   ENDM
psg_out:
        PSGCH   0,0D00Bh
        PSGCH   1,0D04Bh
        PSGCH   2,0D08Bh
        call    517Ch           ; noise
        call    51A5h           ; envelope
        ; mixer: tables 5207h, 520Bh, 520Fh indexed by bits 0-1 of D00Eh, D04Eh, D08Eh
        ld      a,(0D00Eh)
        and     3
        add     a,07h
        ld      l,a
        ld      h,52h
        ld      b,(hl)
        ld      a,(0D04Eh)
        and     3
        add     a,0Bh
        ld      l,a
        ld      c,(hl)
        ld      a,(0D08Eh)
        and     3
        add     a,0Fh
        ld      l,a
        ld      a,(hl)
        or      b
        or      c
        ld      (0D299h),a
        ld      e,a
        ld      a,7
        out     (0A0h),a
        ld      a,e
        out     (0A1h),a
        ret
scc_out_end:
        ASSERT  scc_out_end <= 0BFF0h
