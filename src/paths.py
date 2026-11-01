"""Paths used by the build scripts (relative to this folder unless overridden)."""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
# folder with the artwork ('fase 1' ... 'fase 5'); default: '../art'
ART = os.environ.get('TB_ART', os.path.join(HERE, '..', 'art')) + '/'
REF = os.path.join(HERE, 'ref') + '/'              # TMS VRAM snapshots of the original game (not published)
BASE = os.path.join(HERE, 'twinbee_scc_base.rom')  # Twin Bee SCC Enhanced (128KB, Konami SCC) - not published
ORIG = os.path.join(HERE, 'twinbee_orig_base.rom') # Twin Bee original (32KB, RC-740, PSG) - not published
OUT = os.path.join(HERE, 'out') + '/'
AUTOMAP = os.path.join(HERE, 'automap.json')
SJASM = os.environ.get('SJASMPLUS', 'sjasmplus')
