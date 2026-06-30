"""
mof_renderer.py

Draws two MOF topology diagrams side by side:
  1. Square SBU  — 4 metal corners, 4 linker ball-and-stick edges
  2. 2D cube projection — 8 metal corners, 12 linker edges (cabinet projection)

Geometry is pore-driven:
  - MOF_PORE_DIAMETER_ANG sets the pore size in Angstroms
  - Everything else (square size, linker scale, metal placement) is derived
    from that one number via PX_PER_ANG

Public API (all on MOFRenderer):
  draw()                     — square (no guest) + cube (guest in cube only)
  draw_with_guest()          — guest in both panels
  draw_without_guest()       — no guest anywhere
  draw_simple()              — plain lines, guest in cube only
  draw_simple_with_guest()   — plain lines, guest in both
  draw_simple_without_guest()— plain lines, no guest
"""

import math

from smiles_parser import SmilesParser
from layout_engine import LayoutEngine
from turtle_renderer import (
    ATOM_COLORS, BASE_RADII, DEFAULT_ATOM_COLOR,
    LABEL_Y_FRACTION, LABEL_FONT_SCALE, LABEL_MIN_RADIUS
)

# ─────────────────────────────────────────────────────────────────────────────
# ION RADII TABLE
# Format: symbol -> (ionic_radius_A, hydrated_radius_A, verification)
# ─────────────────────────────────────────────────────────────────────────────
ION_RADII = {
    "Li+":  (0.76,  3.40, "Experimentally Verified"),
    "Na+":  (1.02,  3.58, "Experimentally Verified"),
    "K+":   (1.38,  3.31, "Experimentally Verified"),
    "Rb+":  (1.52,  3.29, "Experimentally Verified"),
    "Cs+":  (1.67,  3.29, "Experimentally Verified"),
    "Be2+": (0.45,  4.59, "Estimated / Unverified"),
    "Mg2+": (0.72,  4.28, "Experimentally Verified"),
    "Ca2+": (1.00,  4.12, "Experimentally Verified"),
    "Sr2+": (1.18,  4.12, "Experimentally Verified"),
    "Ba2+": (1.35,  4.04, "Experimentally Verified"),
    "Cu+":  (0.77,  3.20, "Estimated / Unverified"),
    "V2+":  (0.79,  4.30, "Estimated / Unverified"),
    "Cr2+": (0.73,  4.25, "Estimated / Unverified"),
    "Mn2+": (0.67,  4.38, "Experimentally Verified"),
    "Fe2+": (0.61,  4.28, "Experimentally Verified"),
    "Co2+": (0.65,  4.23, "Experimentally Verified"),
    "Ni2+": (0.69,  4.04, "Experimentally Verified"),
    "Cu2+": (0.73,  4.19, "Experimentally Verified"),
    "Zn2+": (0.74,  4.30, "Experimentally Verified"),
    "Ti2+": (0.86,  4.35, "Estimated / Unverified"),
    "Sn2+": (1.12,  3.95, "Estimated / Unverified"),
    "Pb2+": (1.19,  4.01, "Estimated / Unverified"),
    "Ti3+": (0.67,  4.65, "Estimated / Unverified"),
    "V3+":  (0.64,  4.60, "Estimated / Unverified"),
    "Cr3+": (0.62,  4.61, "Estimated / Unverified"),
    "Mn3+": (0.58,  4.60, "Estimated / Unverified"),
    "Fe3+": (0.55,  4.57, "Experimentally Verified"),
    "Co3+": (0.55,  4.55, "Estimated / Unverified"),
    "Ti4+": (0.61,  4.70, "Estimated / Unverified"),
    "V4+":  (0.58,  4.70, "Estimated / Unverified"),
    "Mn4+": (0.53,  4.75, "Estimated / Unverified"),
    "V5+":  (0.54,  4.80, "Estimated / Unverified"),
    "Cr6+": (0.44,  4.90, "Estimated / Unverified"),
    "Mn7+": (0.46,  4.90, "Estimated / Unverified"),
    "Al3+": (0.54,  4.75, "Experimentally Verified"),
    "Ga3+": (0.62,  4.65, "Estimated / Unverified"),
    "In3+": (0.80,  4.63, "Estimated / Unverified"),
    "Sn4+": (0.69,  4.65, "Estimated / Unverified"),
    "Pb4+": (0.78,  4.60, "Estimated / Unverified"),
    "Sc3+": (0.75,  4.50, "Experimentally Verified"),
    "Y3+":  (0.90,  4.40, "Experimentally Verified"),
    "La3+": (1.03,  4.52, "Experimentally Verified"),
    "Ce3+": (1.01,  4.51, "Estimated / Unverified"),
    "Ce4+": (0.87,  4.65, "Estimated / Unverified"),
    "Nd3+": (0.98,  4.48, "Estimated / Unverified"),
    "Gd3+": (0.94,  4.45, "Estimated / Unverified"),
    "Lu3+": (0.86,  4.39, "Estimated / Unverified"),
    "U3+":  (1.03,  4.73, "Estimated / Unverified"),
    "U4+":  (0.89,  4.83, "Estimated / Unverified"),
    "U6+":  (0.73,  4.85, "Estimated / Unverified"),
    "Np3+": (1.01,  4.72, "Estimated / Unverified"),
    "Np4+": (0.87,  4.84, "Estimated / Unverified"),
    "Pu3+": (1.00,  4.71, "Estimated / Unverified"),
    "Pu4+": (0.86,  4.82, "Estimated / Unverified"),
    "Am3+": (0.98,  4.70, "Estimated / Unverified"),
    "Am4+": (0.85,  4.80, "Estimated / Unverified"),
    "Ac3+": (1.12,  4.75, "Estimated / Unverified"),
    "Th4+": (0.94,  4.87, "Estimated / Unverified"),
    "Pa4+": (0.90,  4.85, "Estimated / Unverified"),
    "Pa5+": (0.78,  4.90, "Estimated / Unverified"),
}

# ─────────────────────────────────────────────────────────────────────────────
# TUNING CONSTANTS  — adjust these to change the look
# ─────────────────────────────────────────────────────────────────────────────

# Fallback pore diameter (Å) used when the MOF is not found in MOF_DB.
MOF_PORE_DIAMETER_FALLBACK = 10.0

# Pixels per Angstrom — controls the overall physical size on screen.
# Increase to zoom in; decrease to zoom out.
PX_PER_ANG = 28.0

# ── MOF database: identifier -> (LCD_Å, PLD_Å, metal_types) ──────────────
# LCD = Largest Cavity Diameter  (how big a sphere fits inside the pore)
# PLD = Pore Limiting Diameter   (bottleneck — what a guest must squeeze past)
# Source: MOF_data.csv
MOF_DB = {
    "[Ag].[In].[O-]C(=O)c1cccnc1": (5.12243, 4.35883, "In,Ag"),
    "[Ag].c1ncn(c1)c1cc(n2cncc2)c(cc1n1cncc1)n1cncc1": (5.14616, 3.58328, "Ag"),
    "[Ag].c1ncn(c1)c1ccc(cc1)C(c1ccc(cc1)n1cncc1)(c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1": (4.58322, 3.5471, "Ag"),
    "[Ag][Ag].[O-]C(=O)c1ccc(cc1)C(=C(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (10.66855, 9.77424, "Ag"),
    "[Ag][Ag].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (12.32183, 11.43403, "Ag"),
    "[Ag][Ag].[O-]C(=O)CN1[CH]C=C(C=C1)C(=O)[O-].[O]N(=O)=O": (3.08728, 2.55648, "Ag"),
    "[Ag][Ag][Ag]12[Ag]([Ag]2([Ag]1[Ag])[Ag][Ag])[Ag].n1ccc(cc1)c1ccncc1": (6.86104, 5.63926, "Ag"),
    "[Ag][Ag]1[Ag]234[Ag]1([Ag]4[Ag])([Ag][Ag]3)[Ag][Ag]2.n1ccc(cc1)c1ccncc1": (6.76574, 5.53782, "Ag"),
    "[Al].[Al][O]([Al])[Al].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[O]": (8.34433, 6.53426, "Al"),
    "[Al].[Fe].[O-]C(=O)C1=[C][C]=[C][C]1.[O]": (4.02816, 3.39035, "Al,Fe"),
    "[Al].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[OH]": (7.02998, 6.83304, "Al"),
    "[Al].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[OH]": (7.04136, 6.93763, "Al"),
    "[Al].[O-]C(=O)c1ccc(o1)C(=O)[O-].[OH]": (5.59563, 4.29059, "Al"),
    "[Al][O]([Al])[Al].[O-]C(=O)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (14.37984, 5.64079, "Al"),
    "[Al]1[OH][Al][OH][Al][OH][Al][OH][Al][OH][Al][OH][Al][OH][Al][OH]1.[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (9.97158, 8.15381, "Al"),
    "[Al]1[OH][Al][OH][Al][OH][Al][OH][Al][OH][Al][OH][Al][OH][Al][OH]1.[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (10.15927, 6.3821, "Al"),
    "[Au].[C]#N.[Fe].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (4.68635, 3.59952, "Fe,Au"),
    "[Bi].[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (6.49014, 5.45081, "Bi"),
    "[Bi].[O-]C(=O)c1sc2c(c1)sc1c2sc(c1)C(=O)[O-]": (5.81023, 4.28246, "Bi"),
    "[C]#N.[Fe].[Pd]": (4.29368, 3.13998, "Pd,Fe"),
    "[Cd].[N]1C=C[C](C=C1)c1ccc(cc1)C(=C(c1ccc(cc1)c1ccncc1)c1ccc(cc1)[C]1C=C[N]C=C1)c1ccc(cc1)c1ccncc1.[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].n1ccc(cc1)c1ccc(cc1)C(=C(c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1": (11.83106, 10.92247, "Cd"),
    "[Cd].[O-]C(=O)C1=CC=CN([CH]1)Cc1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (4.21366, 3.19293, "Cd"),
    "[Cd].[O-]C(=O)C1=NN=C([CH]1)C(=O)[O-].[O-]C(=O)c1[n-][nH]c(c1)C(=O)O.[O-]C(=O)c1[nH][n-]c(c1)C(=O)[O-].[OH2][Cd]": (4.73489, 3.16265, "Cd"),
    "[Cd].[O-]C(=O)c1c(cccc1C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (4.68668, 3.8035, "Cd"),
    "[Cd].[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-]": (12.35673, 11.5506, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])[Si](c1cc(cc(c1)C(=O)[O-])C(=O)[O-])(c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C": (5.70001, 4.0069, "Cd,Si"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.58089, 5.84984, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1ccc(c(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (6.66442, 4.36546, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (7.67731, 6.18207, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (5.64538, 3.43129, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(=O)O)[C]1N[N]C(=N1)c1cc(cc(c1)C(=O)O)C(=O)[O-].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])[C]1N[N]C(=N1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (5.10831, 3.00785, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(=O)O)C(=O)[O-].c1ccc2c(c1)c([C](c1ccncc1)c1ccncc1)c1c(c2[C](c2ccncc2)c2ccncc2)cccc1": (5.67885, 4.2365, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(C)(C)C)C(=O)[O-].n1cc(cc(c1)n1cnc2c1cccc2)n1cnc2c1cccc2": (4.32418, 2.47686, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)C(C)(C)C)C(=O)[O-].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (7.76829, 2.84838, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)c1ccc(cc1)C(=O)O)c1ccc(cc1)C(=O)[O-]": (3.94811, 3.22222, "Cd"),
    "[Cd].[O-]C(=O)c1cc(cc(c1)c1ccc(cc1C(=O)[O-])C(=O)[O-])c1ccc(cc1C(=O)[O-])C(=O)[O-].c1ncn(c1)Cc1ccc(cc1)Cn1cncc1": (4.80079, 3.30608, "Cd"),
    "[Cd].[O-]C(=O)c1cc(NC2=NN=N[N]2)cc(c1)C(=O)[O-]": (6.66243, 5.97827, "Cd"),
    "[Cd].[O-]C(=O)c1cc(Oc2ccc(cc2)c2cc(nc(c2)c2ccncc2)c2ccncc2)cc(c1)C(=O)[O-]": (5.10322, 2.6955, "Cd"),
    "[Cd].[O-]C(=O)c1cc(OCc2ccccc2C(=O)[O-])cc(c1)C(=O)[O-].[O][Cd]": (5.18297, 4.1737, "Cd"),
    "[Cd].[O-]C(=O)c1cc(OCc2ccncc2)cc(c1)C(=O)[O-]": (4.62065, 3.00983, "Cd"),
    "[Cd].[O-]C(=O)c1cc2ccccc2c(c1O)Cc1c(O)c(cc2c1cccc2)C(=O)[O-].n1ccc(cc1)c1ccncc1": (5.71543, 3.55888, "Cd"),
    "[Cd].[O-]C(=O)c1cc2n(cnc2cc1C(=O)[O-])Cc1ccc(cc1)Cn1cnc2c1cc(C(=O)[O-])c(c2)C(=O)[O-]": (5.32034, 4.43488, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-].n1ccc(cc1)c1ccc(cc1)C(=C(c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1": (13.19619, 10.16926, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (4.01416, 2.8117, "Cd"),
    "[Cd].[O-]C(=O)C1CCC(CC1)C(=O)[O-].c1ccc2c(c1)c(c1ccncc1)c1c(c2c2ccncc2)cccc1": (4.12612, 2.89726, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)C(=O)[O-].n1ccc(cc1)c1nnc(nn1)c1ccncc1": (8.038, 6.46124, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)C(c1ccc(cc1)C(=O)[O-])N1[N]C=N[CH]1.c1ncn(c1)c1ccc(cc1)n1cncc1": (9.03531, 8.71363, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)C(c1ccc(cc1)C(=O)O)N1[CH]N=C[N]1.[O-]C(=O)c1ccc(cc1)C(n1cncn1)c1ccc(cc1)C(=O)O": (5.31056, 4.33584, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)C=Nc1ccc(cc1)n1cncc1": (4.13995, 2.95076, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)C1=C(N[C](N1)c1ccc(cc1)[C]1NC(=C(N1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (6.15209, 5.43901, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)C1=C(SC(=C2SC(=C(S2)c2ccc(cc2)C(=O)[O-])c2ccc(cc2)C(=O)[O-])S1)c1ccc(cc1)C(=O)[O-].[O][Cd]": (5.67149, 4.60011, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)c1c2ccccc2c(c2c1cccc2)c1ccc(cc1)C(=O)[O-]": (5.73766, 4.86718, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].n1ccc(cc1)C=Cc1ccncc1": (6.89108, 4.58076, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].n1ccc(cc1)Sc1ccncc1": (6.0594, 4.09029, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].n1ccc(cc1)SSc1ccncc1": (6.26064, 4.91879, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)c1cc(cc(n1)c1ccc(cc1)C(=O)[O-])c1ccccc1.c1cc(nc(c1)n1cncc1)n1cncc1": (4.73171, 2.7922, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].c1ccc2c(c1)c(C=Cc1ccncc1)c1c(c2C=Cc2ccncc2)cccc1": (7.47477, 4.74925, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].n1ncn(c1)c1ccc(cc1)c1ccc(cc1)n1cnnc1": (5.15336, 2.94521, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)CN(Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)CN(Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)C(=O)[O-]": (8.1647, 6.44559, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (6.44246, 4.33842, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (10.7636, 6.46187, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)n1ccnc1C": (6.42829, 6.05724, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)Oc1cc(cc(c1)Oc1ccc(cc1)C(=O)[O-])Oc1ccc(cc1)C(=O)[O-]": (8.81733, 7.87055, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccncc1": (7.73712, 5.42002, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)OCC(COc1ccc(cc1)C(=O)[O-])(COc1ccc(cc1)C(=O)[O-])COCC(COc1ccc(cc1)C(=O)[O-])(COc1ccc(cc1)C(=O)[O-])COc1ccc(cc1)C(=O)[O-].c1ccc2c(c1)n(cn2)c1ccc(cc1)n1cnc2c1cccc2": (7.74783, 5.36023, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)OCc1cc(COc2ccc(cc2)C(=O)[O-])c(cc1COc1ccc(cc1)C(=O)[O-])COc1ccc(cc1)C(=O)[O-]": (7.45467, 6.49944, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(cc1)OCCOc1ccc(cc1)C(=O)[O-].n1ccc(cc1)c1ccncc1": (6.77072, 6.40962, "Cd"),
    "[Cd].[O-]C(=O)c1ccc(o1)C(=O)[O-]": (4.4852, 3.28413, "Cd"),
    "[Cd].[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].c1ncn(c1)c1cc(cc(c1)n1cncc1)n1cncc1": (7.69675, 5.41267, "Cd"),
    "[Cd].[O-]C(=O)c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(=O)[O-].n1ccc(cc1)OCC(COc1ccncc1)(COc1ccncc1)COc1ccncc1": (8.07622, 7.49538, "Cd"),
    "[Cd].[O-]C(=O)c1cccc(c1)c1ccncc1": (7.78375, 6.60456, "Cd"),
    "[Cd].[O-]C(=O)c1cccc(c1c1c(cccc1C(=O)[O-])C(=O)[O-])C(=O)[O-].c1ccc(cn1)C1=NC(=[N]=C([N]1)c1cccnc1)c1cccnc1": (8.32557, 5.01245, "Cd"),
    "[Cd].[O-]C(=O)c1cncc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (7.05077, 6.2187, "Cd"),
    "[Cd].[O-]C(=O)CC(=O)[O-]": (5.28781, 3.77959, "Cd"),
    "[Cd].[O-]C(=O)Cc1ccc(cc1)CC(=O)[O-].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (4.39877, 3.53847, "Cd"),
    "[Cd].[O-]C(=O)CCN1C(=O)c2c(C1=O)cncc2": (4.96397, 3.87939, "Cd"),
    "[Cd].[O-]C(=O)CN1[CH]C=C(C=C1)c1ccncc1.[O-]C(=O)c1cccc(c1)C(=O)[O-]": (4.80312, 3.02916, "Cd"),
    "[Cd].[O]C1=C[CH]N(C=C1)Cc1c2ccccc2c(c2c1cccc2)Cn1ccc(=O)cc1.[O]S(c1cccc2c1cccc2S([O])([O])[O])([O])[O]": (7.21275, 3.56763, "Cd"),
    "[Cd].[O]S(c1cccc2c1cccc2S([O])([O])[O])([O])[O].c1ccc2c(c1)c(Cn1cncc1)c1c(c2Cn2cncc2)cccc1": (5.82411, 3.99559, "Cd"),
    "[Cd].c1ccc2c(c1)N=C[N]2": (5.75722, 3.39104, "Cd"),
    "[Cd][Cd].[O-]C(=O)c1cc(cc(c1)n1cnc2c1cccc2)C(=O)[O-]": (4.37729, 2.47979, "Cd"),
    "[Cd][Cd].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (9.96128, 8.95998, "Cd"),
    "[Cd][Cd].[O-]C(=O)c1ccc(cc1)S(=O)(=O)c1ccc(cc1)C(=O)[O-]": (5.77161, 3.83429, "Cd"),
    "[Cd][O]([Cd][OH2]1[Cd][OH2]([Cd]1)[Cd][O]([Cd])[Cd])[Cd].[O-]C(=O)CN(C1=NC(=[N]=C([N]1)N(CC(=O)[O-])CC(=O)[O-])N(CC(=O)[O-])CC(=O)[O-])CC(=O)[O-]": (4.06616, 2.66688, "Cd"),
    "[Cd][OH2][Cd].[O-]C(=O)c1ccc(cc1)C(=C(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (5.24921, 4.0351, "Cd"),
    "[Cd]I.[O-]C(=O)c1ccc(cc1)C(=O)[O-].n1ccc(cc1)C1=C[CH]N(C=C1)Cc1ccc(cc1)CN1[CH]C=C(C=C1)c1ccncc1": (6.25875, 4.356, "Cd"),
    "[Ce].[Co].[O-]C(=O)c1ccnc(c1)c1nccc(c1)C(=O)[O-]": (7.40912, 5.15618, "Ce,Co"),
    "[Ce].[O-]C(=O)c1c(F)c(F)c(c(c1F)F)C(=O)[O-].[O]": (3.71483, 2.61345, "Ce"),
    "[Ce].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.50772, 5.08568, "Ce"),
    "[Ce].[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-]": (5.47859, 5.00035, "Ce"),
    "[Ce].[O-]C(=O)c1ccc(cc1)C(c1ccc(cc1)C(=O)[O-])(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (8.48415, 4.23162, "Ce"),
    "[Ce].[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)O)c(nc1c1ccc(cc1)C(=O)O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)[O-])c(nc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (4.76524, 3.42014, "Ce"),
    "[Ce].[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.00337, 4.76533, "Ce"),
    "[Ce].[O-]C(=O)c1ccc(o1)C(=O)[O-]": (5.96486, 4.52282, "Ce"),
    "[Ce].[O-]C(=O)CN(CC(=O)[O-])CCCN(CC(=O)[O-])CC(=O)[O-]": (4.27692, 3.02408, "Ce"),
    "[Ce].[O-]C(=O)COc1ccc(cc1)N(CC(=O)[O-])CC(=O)[O-]": (4.67196, 3.86449, "Ce"),
    "[CH]1C=NN=N1.[Cu].[Cu][OH]([Cu][OH]([Cu])[Cu])[Cu].[N]1C=CN=N1.[O-]C(=O)c1cc(cc(c1)S([O])([O])[O])C(=O)[O-]": (5.3892, 3.85349, "Cu"),
    "[CH]1C=NN=N1.[N]1C=CN=N1.[O-]C(=O)c1cc(cc(c1)C(=O)[O-])[C]1N[N]C(=N1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[O-]C(=O)c1cc(cc(c1)c1[nH]nc(n1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-].[Zn]": (7.88337, 5.26114, "Zn"),
    "[CH]1C=NN=N1.[N]1C=CN=N1.[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cccc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (6.90169, 4.11736, "Zn"),
    "[Co].[Co][Co].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (7.27861, 5.1706, "Co"),
    "[Co].[Co][O]([Co])[Co].[O-]C(=O)c1ccc(cn1)C(=O)[O-].n1ccc(cc1)c1cc(nc(c1)c1ccncc1)c1ccncc1": (10.68617, 9.69952, "Co"),
    "[Co].[Co]O[Co].[O-]C(=O)c1ccncc1": (7.17077, 4.84194, "Co"),
    "[Co].[Er].[O-]C(=O)c1ncccc1C(=O)[O-]": (7.20181, 5.92665, "Er,Co"),
    "[Co].[Fe].[O-]C(=O)C1=CC=C[CH]1.[O-]C(=O)C1=C[CH]C=C1.[O-]C(=O)[C]1C=CC=C1.n1ccc(cc1)c1ccncc1": (4.61119, 3.38932, "Co,Fe"),
    "[Co].[Ho].[O-]C(=O)c1ncccc1C(=O)[O-]": (7.17949, 5.90683, "Ho,Co"),
    "[Co].[Mg].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (6.57785, 4.83765, "Co,Mg"),
    "[Co].[nH]1[n-]cc(c1)C1=C2C=CC3=[N]2[Co]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2c[n-][nH]c2)cc1)c1c[n-][nH]c1)c1c[n-][nH]c1": (9.0054, 8.27549, "Co"),
    "[Co].[nH]1[n-]cc(c1)C1=C2C=CC3=[N]2[Mn]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2c[n-][nH]c2)cc1)c1c[n-][nH]c1)c1c[n-][nH]c1": (9.05169, 8.30105, "Co,Mn"),
    "[Co].[O-]C(=O)[C]1C=C(C(=O)[O-])C(=O)[CH]C1=O": (11.22991, 10.00387, "Co"),
    "[Co].[O-]C(=O)C1=CC2=NN=NC2=C[CH]1.[O-]C(=O)C1=C[CH]C2=NN=NC2=C1.[O-]C(=O)c1ccc2c(c1)[N]N=N2.[O]": (5.8318, 4.99145, "Co"),
    "[Co].[O-]C(=O)C1=CC2=NN=NC2=C[CH]1.[O-]C(=O)C1=CC=C2C(=NN=N2)[CH]1.[O-]C(=O)c1ccc2c(c1)N=N[N]2.[OH]": (5.78961, 4.85187, "Co"),
    "[Co].[O-]C(=O)C1=CC2=NN=NC2=C[CH]1.[O-]C(=O)c1ccc2c(c1)[N]N=N2.[O]": (6.76674, 5.73723, "Co"),
    "[Co].[O-]C(=O)c1c2ccccc2c(c2c1cccc2)C(=O)[O-].c1ncn(c1)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1": (8.43697, 7.72021, "Co"),
    "[Co].[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-]": (11.42442, 10.86245, "Co"),
    "[Co].[O-]C(=O)c1cc(C(=O)[O-])c(cc1[O])[O]": (11.08197, 9.89273, "Co"),
    "[Co].[O-]C(=O)c1cc(c(cc1C(=O)[O-])C(=O)[O-])P(=O)([O])[O].c1ccc(c(c1)Cn1cncc1)Cn1cncc1": (4.23185, 3.46185, "Co"),
    "[Co].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (7.10963, 5.99315, "Co"),
    "[Co].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].c1ncn(c1)c1ccc(cc1)n1cncc1": (4.62849, 4.01864, "Co"),
    "[Co].[O-]C(=O)c1cc(cc(c1)c1cccnc1)C(=O)[O-]": (6.02491, 4.73803, "Co"),
    "[Co].[O-]C(=O)c1cc(cc(c1)n1ccnc1C)C(=O)[O-].c1ncn(c1)c1ccc(cc1)Oc1ccc(cc1)n1cncc1": (4.59762, 3.43271, "Co"),
    "[Co].[O-]C(=O)c1cc(cc(c1)n1cnnc1)n1cnnc1.[OH]": (4.4232, 4.15363, "Co"),
    "[Co].[O-]C(=O)c1cc(CN2[N]C(=N[C]2c2ccncc2)c2ccncc2)cc(c1)C(=O)[O-]": (4.22907, 2.83701, "Co"),
    "[Co].[O-]C(=O)c1cc(COc2cccc(c2)C(=O)O)cc(c1)C(=O)[O-].n1ccc(cc1)CCc1ccncc1": (4.64806, 4.22285, "Co"),
    "[Co].[O-]C(=O)c1cc(O)c(c(c1)O)[O]": (3.38529, 2.62935, "Co"),
    "[Co].[O-]C(=O)c1cc(OCc2ccncc2)cc(c1)C(=O)[O-].n1ccc(cc1)OCC(COc1ccncc1)(COc1ccncc1)COc1ccncc1": (9.68124, 5.2532, "Co"),
    "[Co].[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-].c1ncn(c1)c1cc(cc(c1)n1cncc1)n1cncc1": (5.57112, 2.41312, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (4.52917, 3.15863, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (10.30033, 8.55202, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-].c1nc(cc(n1)n1cncc1)n1cncc1": (6.91333, 5.90513, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-].n1ccc(cc1)SSc1ccncc1": (6.07664, 5.29283, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)C(C(F)(F)F)(C(F)(F)F)c1ccc(cc1)C(=O)[O-]": (5.48015, 4.51833, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)C1=C(SC(=C2SC(=C(S2)c2ccc(cc2)C(=O)[O-])c2ccc(cc2)C(=O)[O-])S1)c1ccc(cc1)C(=O)[O-]": (5.6621, 4.62841, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)C1=C2C=CC(=C(c3ccncc3)C3=NC(=C(C4=CC=C(C(=C5N=C1C=C5)c1ccncc1)[N]4)c1ccc(cc1)C(=O)[O-])C=C3)[N]2": (5.76378, 2.59733, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccc(cc1)C(=O)O)c1ccc(cc1)C(=O)[O-].c1ncn(c1)c1ccc(cc1)c1ccc(cc1)n1cncc1": (5.03577, 3.52134, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)c1cc(cc(n1)c1ccc(cc1)C(=O)[O-])c1ccccc1.c1cc(nc(c1)n1cncc1)n1cncc1": (4.4792, 2.75315, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (6.70333, 5.01996, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (8.58796, 4.10545, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)c1ccc(cn1)C(=O)[O-].n1ccc(cc1)c1ccc(cc1)c1ccncc1": (5.13193, 3.35545, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)CN(Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)C(=O)[O-].c1ncn(c1)Cc1ccc(cc1)Cn1cncc1": (5.58733, 4.22769, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (9.5622, 8.33335, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)n1cncc1.[O].n1ccn(c1)c1ccc(cc1)C1=NN=N[N]1": (9.66687, 9.25347, "Co"),
    "[Co].[O-]C(=O)c1ccc(cc1)Nc1ccc(cc1)C(=O)[O-].c1ncn(c1)c1ccc2c(c1)c1cc(ccc1o2)n1cncc1": (7.28209, 5.9399, "Co"),
    "[Co].[O-]C(=O)c1ccc(nc1)c1ccc(cn1)C(=O)[O-].[O-]C=O": (7.03754, 5.53828, "Co"),
    "[Co].[O-]C(=O)c1ccc2c(c1)[nH]cn2": (4.6055, 4.07898, "Co"),
    "[Co].[O-]C(=O)c1cccc(c1)c1ccncc1": (7.61466, 6.26784, "Co"),
    "[Co].[O-]C(=O)c1ccnc(c1)C(=O)[O-].[OH]": (3.7377, 3.51969, "Co"),
    "[Co].[O-]C(=O)c1ccnc(c1)c1nccc(c1)C(=O)[O-].[Pr]": (7.305, 5.12042, "Pr,Co"),
    "[Co].[O-]C(=O)c1ccncc1.[O]NC(=O)c1ccc(cc1)C(=O)N[O]": (6.17036, 4.44152, "Co"),
    "[Co].[O-]C(=O)c1ncccc1C(=O)[O-].[Tm]": (7.17717, 5.88475, "Co,Tm"),
    "[Co].[O-]C(=O)COCC(=O)[O-].n1ccc(cc1)c1ccncc1": (5.53082, 4.05182, "Co"),
    "[Co].[O]P(=O)(c1ccc(cc1)C(c1ccc(cc1)P(=O)(O)[O])(c1ccc(cc1)P(=O)(O)[O])c1ccc(cc1)P(=O)(O)[O])O.[O]P(=O)(c1ccc(cc1)C(c1ccc(cc1)P(=O)([O])O)(c1ccc(cc1)P(=O)([O])O)c1ccc(cc1)P(=O)([O])O)O": (5.67015, 4.23977, "Co"),
    "[Co].c1ccc(cc1)C1=C2C=CC(=C(c3ccncc3)C3=NC(=C(C4=CC=C(C(=C5N=C1C=C5)c1ccncc1)[N]4)c1ccccc1)C=C3)[N]2": (6.56429, 5.06226, "Co"),
    "[Co].c1ccc2-c(cc1)c(cc2c1ccncc1)c1ccncc1.n1ccc(cc1)c1ccncc1": (5.78409, 4.97221, "Co"),
    "[Co].n1cc([nH]c1)c1ccc(cc1)c1[nH]cnc1": (4.26728, 3.40774, "Co"),
    "[Co].n1ccc(cc1)C#Cc1ccc(cc1)C#Cc1ccncc1": (8.18028, 7.92646, "Co"),
    "[Co].n1ccc(cc1)C1=C2C=CC(=C(c3ccncc3)C3=NC(=C(C4=CC=C(C(=C5N=C1C=C5)c1ccncc1)[N]4)c1ccncc1)C=C3)[N]2": (4.88768, 3.8223, "Co"),
    "[Co].n1n[nH]c(n1)c1ccc(cc1)C1=C2C=CC(=C(c3ccc(cc3)c3[nH]nnn3)C3=NC(=C(C4=CC=C(C(=C5N=C1C=C5)c1ccc(cc1)c1[nH]nnn1)[N]4)c1ccc(cc1)c1[nH]nnn1)C=C3)[N]2": (5.24103, 3.51737, "Co"),
    "[Co][Co].[Co][OH]([Co])[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1cccnc1": (13.94738, 6.83886, "Co"),
    "[Co][Co].[O-]C(=O)c1cc(cc(c1)c1cccnc1)C(=O)[O-]": (4.41275, 2.67575, "Co"),
    "[Co][Co].[O-]C(=O)c1cc(cc(c1)n1ccnc1C)C(=O)[O-]": (4.97073, 3.79815, "Co"),
    "[Co][Co].[O-]C(=O)c1ccc(cc1)C(C(F)(F)F)(C(F)(F)F)c1ccc(cc1)C(=O)[O-]": (4.93014, 2.47697, "Co"),
    "[Co][Co].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].n1ccc(cc1)CN1CCN(CC1)Cc1ccncc1": (5.72885, 3.8313, "Co"),
    "[Co][Co].[O-]C(=O)c1ccc(cc1)S(=O)(=O)c1ccc(cc1)C(=O)[O-].c1ncn(c1)Cc1ccc(cc1)Cn1cncc1": (4.94127, 3.17045, "Co"),
    "[Co][Co].[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2c1ccc(cc1)c1ccc(cc1)n1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (22.51791, 11.98939, "Co"),
    "[Co][O]([Co])[Co].[O-]C(=O)c1cc(OCc2c3ccccc3c(c3c2cccc3)COc2cc(cc(c2)C(=O)[O-])C(=O)[O-])cc(c1)C(=O)[O-]": (8.39026, 5.74342, "Co"),
    "[Co][O]([Co])[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (8.93138, 4.66988, "Co"),
    "[Co][OH]1[Co][OH]([Co]1)[Co].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].c1ncn(c1)c1ccc(cc1)n1cncc1": (7.86791, 7.10373, "Co"),
    "[Co][OH]1[Co][OH]([Co]1)[Co].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].c1cc(cc(c1)c1[nH]cnc1)c1[nH]cnc1": (5.34521, 4.18072, "Co"),
    "[Co][OH]1[Co][OH]([Co]1)[Co].[O-]C(=O)c1ccncc1": (6.50079, 4.27513, "Co"),
    "[Co][OH]1[Co][OH2][Co]21[OH2][Co][OH]2[Co].[O-]C(=O)c1ccc(cc1)c1ccccc1C(=O)[O-].c1ncn(c1)c1ccc(cc1)n1cncc1": (5.20441, 4.15942, "Co"),
    "[Co][OH]1[Co][OH2][Co]21[OH2][Co][OH]2[Co].[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2Cc1ccc(cc1)Cn1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (5.35519, 4.50996, "Co"),
    "[Co][OH2][Co].[O-]C(=O)c1cc(c2ccc(cc2)C(=O)[O-])c(cc1C(=O)[O-])c1ccc(cc1)C(=O)[O-].n1ccc(cc1)CCc1ccncc1": (5.35697, 2.97763, "Co"),
    "[Co][OH2][Co].[O-]C(=O)c1ccc(cc1)CN(Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)CN(Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)C(=O)[O-]": (6.81117, 3.35123, "Co"),
    "[Co][OH2][Co].[O-]C(=O)c1ccc(s1)C(=O)[O-]": (7.49401, 5.22841, "Co"),
    "[Co][OH2][Co][OH2][Co].[O-]C(=O)c1ccc(cc1)c1ccc(cc1C(=O)[O-])C(=O)[O-]": (5.4668, 3.66161, "Co"),
    "[Co]1[Co][O]21[Co][O]1([Co]2)[Co][Co]1.[Co][O]([Co])[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1cc(nc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccncc1": (10.80481, 4.78739, "Co"),
    "[Co]12[OH]3[Co]4[OH]2[Co]2[OH]4[Co]4[OH]5[Co]3[OH]1[Co]5[OH]24.[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].n1ccc(cc1)c1ccncc1": (9.53481, 8.88161, "Co"),
    "[Co]O[Co].[O-]C(=O)c1ccc(cc1)C(c1ccc(cc1)C(=O)[O-])N1[N]C=N[CH]1.n1ccc(cc1)c1ccncc1": (9.90886, 6.495, "Co"),
    "[Cr].[Mn].[O-]C(=O)C(=O)[O-]": (6.2194, 5.33977, "Cr,Mn"),
    "[Cr].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O]": (7.50679, 7.09493, "Cr"),
    "[Cr][O]([Cr])[Cr].[O-]C(=O)C1=C[C]=CC(=C1)C(=O)[O-].[O-]C(=O)c1ccncc1.[Zn][Zn]": (11.82924, 9.14708, "Zn,Cr"),
    "[Cr][O]([Cr])[Cr].[O-]C(=O)c1cc(cc(c1)N(=O)=O)C(=O)[O-].[O-]C(=O)c1ccncc1.[Zn][Zn]": (11.05144, 8.49257, "Zn,Cr"),
    "[Cr][O]([Cr])[Cr].[O-]C(=O)c1ccc(cc1)c1cc2c(cc1c1ccc(cc1)C(=O)[O-])C1c3c(C2c2c1cc(c(c2)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])cc(c(c3)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (14.55008, 13.60266, "Cr"),
    "[Cr][O]([Cr])[Cr].[O-]C(=O)c1ccc(o1)C(=O)[O-].[O-]C(=O)c1ccncc1.[Zn][Zn]": (14.29207, 10.12824, "Zn,Cr"),
    "[Cu].[Cu][Cu].[O-]C(=O)c1cc(ccc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (8.61757, 7.37936, "Cu"),
    "[Cu].[Cu][OH]1[Cu][OH]([Cu]1)[Cu].[O-]C(=O)c1cc(cc(c1)C(=O)O)C(=O)[O-].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].c1ncn(c1)CCCn1cnnc1": (3.71447, 2.8097, "Cu"),
    "[Cu].[Eu].[O-]C(=O)c1ccccc1C(=O)[O-].[O-]C(=O)c1ccncc1": (4.65185, 4.20696, "Cu,Eu"),
    "[Cu].[In].[O-]C(=O)c1ccc(nc1)c1ccc(cn1)C(=O)[O-]": (4.60859, 4.02814, "In,Cu"),
    "[Cu].[Mo].[O].[O][As]([O])[O].c1ncn(c1)c1ccc(cc1)n1cncc1": (5.0989, 3.72099, "Cu,As,Mo"),
    "[Cu].[N][N][N].n1ccc(cc1)C1=NN=N[N]1.n1ccc(cc1)C1=N[N]N=N1": (5.94852, 4.82606, "Cu"),
    "[Cu].[Nd].[O-]C(=O)c1cccnc1c1ncccc1C(=O)[O-]": (6.32079, 5.6922, "Cu,Nd"),
    "[Cu].[O-]C(=O)C(n1cnnc1)Cc1cnc[nH]1": (8.44171, 5.79866, "Cu"),
    "[Cu].[O-]C(=O)C.[O-]C(=O)c1ccc(cc1)n1cncc1.[OH]": (5.63644, 5.13832, "Cu"),
    "[Cu].[O-]C(=O)C1=C([N]N=C1C(=O)[O-])C(=O)[O-].[O-]C(=O)[C]1C(=NN=C1C(=O)[O-])C(=O)[O-].[O-]C(=O)c1c(Cl)c(Cl)c(c(c1Cl)Cl)C(=O)[O-].[OH2][Ce]": (6.2867, 5.20836, "Ce,Cu"),
    "[Cu].[O-]C(=O)C1=CC=CN([CH]1)Cc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[O-]C(=O)C1=CN([CH]C=C1)Cc1cc(cc(c1)C(=O)[O-])C(=O)[O-].n1ccc(cc1)CCc1ccncc1": (4.4637, 3.78813, "Cu"),
    "[Cu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(c2cc(cc(c2)C(=O)[O-])C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (8.20724, 6.59788, "Cu"),
    "[Cu].[O-]C(=O)c1cc(CN2[CH]C=C(C=C2)c2ccncc2)cc(c1)C(=O)[O-].n1ccc(cc1)c1ccncc1": (5.99609, 3.11493, "Cu"),
    "[Cu].[O-]C(=O)c1cc(nc(c1)c1ccncc1)c1ccncc1": (3.88407, 2.62017, "Cu"),
    "[Cu].[O-]C(=O)c1ccc(cc1)c1c(C)[n-][nH]c1C": (5.64455, 3.80324, "Cu"),
    "[Cu].[O-]C(=O)c1ccc(cc1)n1ccnc1c1nccn1c1ccc(cc1)C(=O)[O-]": (5.43377, 4.85694, "Cu"),
    "[Cu].[O-]C(=O)c1ccc(cc1)n1ncnc1": (4.6846, 4.2919, "Cu"),
    "[Cu].[O-]C(=O)c1cccc(c1)C(=O)[O-]": (4.60586, 3.24756, "Cu"),
    "[Cu].[O-]C(=O)c1csc(n1)c1ccncc1": (5.40296, 2.98188, "Cu"),
    "[Cu].[O-]C(=O)CC(CC(=O)[O-])CC(=O)[O-].c1ccc(nc1)c1nc(c2ccccn2)c(nc1c1ccccn1)c1ccccn1": (9.58251, 8.45898, "Cu"),
    "[Cu].[O-]C(=O)CN1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)CC(=O)[O-].n1ccc(cc1)C=Cc1ccncc1": (4.92734, 3.30383, "Cu"),
    "[Cu].[O-]C(=O)CNCC(=O)[O-].[Yb]": (6.99405, 4.9448, "Cu,Yb"),
    "[Cu].[O]S(=O)(=O)[O].c1nc2c([nH]1)cc1c(c2)[nH]cn1": (4.5322, 3.65669, "Cu"),
    "[Cu].[O]S(=O)(=O)[O].n1ccc(cc1)c1nnc(s1)c1ccncc1": (4.13577, 3.75215, "Cu"),
    "[Cu].c1ncn(c1)c1ccc(cc1)n1cncc1": (3.81204, 3.00466, "Cu,Si"),
    "[Cu].n1ccc(cc1)C#CC#Cc1ccncc1": (7.92582, 6.11938, "Cu"),
    "[Cu].n1ccc(cc1)C#Cc1ccc(cc1)C#Cc1ccncc1": (10.72504, 10.39704, "Cu,Si"),
    "[Cu].n1ccc(cc1)C#Cc1ccncc1": (6.17681, 4.19394, "Cu"),
    "[Cu].n1ccc(cc1)c1ccc(cc1)c1ccncc1": (6.95106, 6.36902, "Cu,Ti"),
    "[Cu].n1ccc(cc1)c1ccncc1": (6.9917, 3.97103, "Cu"),
    "[Cu][Cu].[Cu][O]1([Cu])[Cu][O]([Cu]1)([Cu])[Cu].[O-]C(=O)c1ccc(cc1)c1cncc(c1)c1ccc(cc1)C(=O)[O-]": (11.55212, 8.55341, "Cu"),
    "[Cu][Cu].[Ga][O]([Ga])[Ga].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (13.89369, 9.71033, "Ga,Cu"),
    "[Cu][Cu].[O-][n+]1cc(ccc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (9.20584, 4.05224, "Cu"),
    "[Cu][Cu].[O-]C(=O)C=Cc1ccnc2c1cccc2": (4.5981, 3.70181, "Cu"),
    "[Cu][Cu].[O-]C(=O)C12CCC(CC1)(CC2)C(=O)[O-].n1ccc(cc1)c1ccncc1": (3.55755, 2.78705, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc(c[n+](c1)[O-])C(=O)[O-]": (7.85306, 5.37338, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc(c2ccc(cc2)C(=O)[O-])c(c(c1)c1ccc(cc1)C(=O)[O-])F.n1ccncc1": (12.39799, 11.34076, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (13.26988, 6.68271, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C1=CS[C]2[C]1SC=C2c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])[C]1[CH]S[C]2[C]1S[CH][C]2c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1csc2c1scc2c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (10.89818, 6.83827, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (10.48635, 6.7463, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc(cc(c1)c1cccc2c1cccc2c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (11.60438, 5.76316, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc(cc(c1)n1ccnc1C)C(=O)[O-]": (4.78705, 3.66848, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc(cc(c1)n1cncc1)C(=O)[O-]": (4.3583, 3.52183, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cc2c(s1)c1cc(sc1c1c2sc(c1)C(=O)[O-])C(=O)[O-]": (20.3716, 9.94685, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc(cc1)C#Cc1cc(C#Cc2ccc(cc2)C(=O)[O-])c(cc1C#Cc1ccc(cc1)C(=O)[O-])C#Cc1ccc(cc1)C(=O)[O-]": (9.31744, 7.45975, "Cu"),
    "[Cu][Cu].[O-]C(=O)C1CCC(CC1)C(=O)[O-].n1ccc(cc1)c1ccncc1": (5.55616, 3.55155, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc(cc1)c1c(c2ccc(cc2)C(=O)O)c(c(n1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (6.68517, 4.60955, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (15.78565, 8.73155, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc(cc1)CN(Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)CN(Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)C(=O)[O-]": (7.91934, 5.67788, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc(cc1)OCC(COc1ccc(cc1)C(=O)[O-])(COc1ccc(cc1)C(=O)[O-])COc1ccc(cc1)C(=O)[O-]": (7.25479, 4.50685, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc(cc1)SSc1ccc(cc1)C(=O)[O-]": (6.62833, 5.49766, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc(cc1)SSc1ccc(cc1)C(=O)[O-].n1ccc(cc1)c1ccncc1": (6.26196, 4.61074, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc(s1)c1ccc(cc1)N(c1ccc(cc1)c1ccc(s1)C(=O)[O-])c1ccc(cc1)c1ccc(s1)C(=O)[O-]": (6.142, 4.96141, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2c1ccc(cc1)c1ccc(cc1)n1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (22.78188, 12.52223, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1ccc2c(c1)ccc(c2)OCC(COc1ccc2c(c1)ccc(c2)C(=O)[O-])(COc1ccc2c(c1)ccc(c2)C(=O)[O-])COc1ccc2c(c1)ccc(c2)C(=O)[O-]": (9.09784, 5.96592, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cccc(c1)CN(Cc1cccc(c1)C(=O)[O-])Cc1ccc(cc1)CN(Cc1cccc(c1)C(=O)[O-])Cc1cccc(c1)C(=O)[O-]": (5.89219, 4.68009, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1cncc(c1)Oc1ccc(c(c1)C(=O)[O-])C(=O)O": (5.49534, 3.34203, "Cu"),
    "[Cu][Cu].[O-]C(=O)c1sc2c(c1)sc1c2sc(c1)C(=O)[O-]": (10.10848, 6.63048, "Cu"),
    "[Cu][Cu].[O-]C(=O)CCc1ccc(cc1)C[N]12CCC[N]3([Cu]42(Cl)[N](CC1)(CCC[N]4(CC3)Cc1ccc(cc1)CCC(=O)[O-])Cc1ccc(cc1)CCC(=O)[O-])Cc1ccc(cc1)CCC(=O)[O-]": (17.17781, 11.88721, "Cu"),
    "[Cu][Cu].[O-]C(=O)CCCC(=O)[O-].n1ccc(cc1)c1ccncc1": (4.7834, 3.74703, "Cu"),
    "[Cu][Cu].[O-]C(=O)CCCC(=O)[O-].n1ccc(cc1)CCc1ccncc1": (4.79113, 4.11066, "Cu"),
    "[Cu][Cu].n1ccc(cc1)C1=C2C=CC3=[N]2[Cu]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2ccncc2)cc1)c1ccncc1)c1ccncc1": (6.09567, 3.24003, "Cu"),
    "[Cu][O]1[Cu][O]([Cu]1)[Cu].[O-]C(=O)c1cc(NCc2ccccc2)cc(c1)C(=O)[O-]": (8.52958, 6.20939, "Cu"),
    "[Cu][O]1[Cu][O]([Cu]1)[Cu].[O-]C(=O)Cc1ccc(cc1)n1cnnc1": (7.28525, 5.71966, "Cu"),
    "[Cu][OH]([Cu])[Cu].[O-]C(=O)c1ccc(cc1)n1cnnc1": (6.49783, 5.01262, "Cu"),
    "[Cu][OH][Cu].[O-]C(=O)C.n1ccc(cc1)c1ccncc1": (3.78171, 3.0048, "Cu"),
    "[Cu][OH]1[Cu][OH]([Cu]1)[Cu].[O-]C(=O)c1ccccc1C(=O)[O-]": (4.92491, 3.90947, "Cu"),
    "[Cu]O[Cu]Br.[O-]C(=O)c1cc(nc(c1)c1ccncc1)c1ccncc1": (6.57016, 6.08023, "Cu"),
    "[Dy].[O-][n+]1ccc(cc1)C(=O)[O-]": (4.38092, 3.53647, "Dy"),
    "[Dy].[O-]C(=O)c1cc(NCc2ccncc2)cc(c1)C(=O)[O-]": (3.73369, 2.82471, "Dy"),
    "[Dy].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)O.[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-]": (6.16695, 4.19416, "Dy"),
    "[Er].[Er][Er].[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)[CH][CH]c1ccc(cc1)C(=O)[O-]": (10.06968, 8.83185, "Er"),
    "[Er].[O-]C(=O)[CH][CH]C(=O)[O-]": (4.96885, 4.05562, "Er"),
    "[Er].[O-]C(=O)c1cc(NCc2ccncc2)cc(c1)C(=O)[O-]": (3.76328, 3.01033, "Er"),
    "[Er].[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)[O-]": (5.45464, 3.41317, "Er"),
    "[Er].[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.36827, 4.93975, "La"),
    "[Er]12[OH]3[Er]4[OH]2[Er]2[OH]1[Er]3[OH]42.[O-]C(=O)c1ccc(cc1)c1cncc(c1)c1ccc(cc1)C(=O)[O-]": (12.70758, 7.22422, "Er"),
    "[Eu].[O-]C(=O)C1=C[C](NC=C1)c1cc(cc(c1)C(=O)O)C(=O)[O-].[O-]C(=O)C1=C[C](NC=C1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (4.79775, 3.32692, "Eu"),
    "[Eu].[O-]C(=O)c1cc(c2ccc(cc2)C(=O)[O-])c(c(c1)c1ccc(cc1)C(=O)[O-])F": (4.45966, 2.88859, "Eu"),
    "[Eu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (7.19973, 6.38685, "Eu"),
    "[Eu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)O)C(=O)[O-].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (7.10272, 5.92088, "Eu"),
    "[Eu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.5852, 5.36564, "Eu"),
    "[Eu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (8.26934, 5.41817, "Eu"),
    "[Eu].[O-]C(=O)c1cc(cc(c1)c1ccc(c2c1cccc2)C(=O)[O-])C(=O)[O-]": (7.1887, 5.05319, "Eu"),
    "[Eu].[O-]C(=O)c1cc(cc(c1)NC(=O)c1ccc(cc1)C(=O)[O-])NC(=O)c1ccc(cc1)C(=O)[O-]": (7.19015, 5.9208, "Eu"),
    "[Eu].[O-]C(=O)c1cc(ccc1C(=O)[O-])Oc1c(cccc1C(=O)[O-])C(=O)[O-]": (6.02576, 5.18239, "Eu"),
    "[Eu].[O-]C(=O)c1cc(CN2C=CC=C([CH]2)[O])cc(c1)C(=O)[O-].[O-]C(=O)c1cc(CN2[CH]C=CC(=C2)[O])cc(c1)C(=O)[O-].[O-]C=O": (3.18745, 2.54225, "Eu"),
    "[Eu].[O-]C(=O)c1cc(NCc2c3ccccc3cc3c2cccc3)cc(c1)C(=O)[O-]": (5.5734, 3.54569, "Eu"),
    "[Eu].[O-]C(=O)c1cc(NCc2ccncc2)cc(c1)C(=O)[O-]": (3.68928, 2.98786, "Eu"),
    "[Eu].[O-]C(=O)c1cc(O)c(cc1O)C(=O)[O-]": (6.47697, 4.51275, "Eu"),
    "[Eu].[O-]C(=O)c1ccc(c2c1nsn2)C(=O)[O-].[O-]C=O": (5.5303, 3.77942, "Eu"),
    "[Eu].[O-]C(=O)c1ccc(cc1)[C]1N[C](N[C](N1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (6.28049, 4.64312, "Eu"),
    "[Eu].[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (6.75856, 5.03361, "Eu"),
    "[Eu].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (5.36977, 4.23592, "Eu"),
    "[Eu].[O-]C(=O)c1ccc(cc1)N[C]1NC(=NC(=N1)Nc1ccc(cc1)C(=O)[O-])Nc1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)N[C]1N[C](Nc2ccc(cc2)C(=O)[O-])N=[C](=N1)[N]c1ccc(cc1)C(=O)[O-]": (9.93484, 8.5685, "Eu"),
    "[Eu].[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.24436, 4.87463, "Eu"),
    "[Eu].[O-]C(=O)c1ccc(o1)C(=O)[O-]": (5.86311, 4.43195, "Eu"),
    "[Eu].[O-]C(=O)c1ccc2c(c1)c1ccc(cc1c1c2cc(cc1)C(=O)[O-])C(=O)[O-]": (10.42322, 6.14247, "Eu"),
    "[Eu].[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-]": (5.20483, 2.81365, "Eu"),
    "[Eu].[O-]C(=O)CCCC(=O)[O-]": (4.89419, 4.25089, "Eu"),
    "[Eu].[O-]C(=O)CN(C1=NC(=[N]=C([N]1)N(CC(=O)[O-])CC(=O)[O-])N(CC(=O)[O-])CC(=O)[O-])CC(=O)[O-]": (4.67431, 4.24797, "Eu"),
    "[Eu][Eu].[O-]C(=O)c1c(F)c(F)c(c(c1F)F)C(=O)[O-]": (3.56221, 2.92578, "Eu"),
    "[Eu][Eu].[O-]C(=O)c1cc(c2ccc(cc2)c2ccccc2C(=O)O)c(cc1c1ccc(cc1)c1ccccc1C(=O)O)C(=O)[O-].[O-]C(=O)c1cc(c2ccc(cc2)c2ccccc2C(=O)[O-])c(cc1c1ccc(cc1)c1ccccc1C(=O)[O-])C(=O)[O-]": (5.80341, 4.80398, "Eu"),
    "[Eu][OH]1[Eu][OH]2[Eu]1[OH]1[Eu]2[OH]([Eu]1)[Eu].[O-]C(=O)c1ccc(cc1)c1cc(cc(n1)c1ccc(cc1)C(=O)[O-])c1ccncc1.[O-]C=O": (6.21597, 3.42309, "Eu"),
    "[Eu]12[O]3[Eu]4[O]2[Eu]2[O]1[Eu]3[O]42.[O-]C(=O)c1ccc(cc1)c1ccc(nc1)C(=O)[O-]": (7.66896, 7.55167, "Eu"),
    "[Fe].[NH]c1cc2c(cc1[NH])c1cc([NH])c(cc1c1c2cc([NH])c(c1)[NH])[NH]": (22.94791, 15.58314, "Fe"),
    "[Fe].[O-]C(=O)C(=O)[O-]": (5.27197, 4.09919, "Fe"),
    "[Fe].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O]": (3.00773, 2.78045, "Fe"),
    "[Fe].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[OH]": (5.68425, 5.34475, "Fe"),
    "[Fe].[O-]C(=O)c1ccc(cc1)C(=O)[O-].n1ccncc1": (15.13602, 13.61044, "Fe"),
    "[Fe].[O]NC(=O)c1cc(cc(c1)C(=O)N[O])c1cc(cc(c1)C(=O)N[O])C(=O)N[O]": (20.78792, 8.92032, "Fe"),
    "[Fe][Fe].[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2c1ccc(cc1)c1ccc(cc1)n1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (22.61205, 12.09156, "Fe"),
    "[Fe][O]([Fe])[Fe].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (8.56951, 7.78371, "Fe"),
    "[Fe][O]([Fe])[Fe].[O-]C(=O)c1ccc(cc1)C(C(F)(F)F)(C(F)(F)F)c1ccc(cc1)C(=O)[O-]": (6.86695, 4.28377, "Fe"),
    "[Fe][O]([Fe])[Fe].[O-]C(=O)c1ccc(cc1)c1cc2c(cc1c1ccc(cc1)C(=O)[O-])C1c3c(C2c2c1cc(c(c2)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])cc(c(c3)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (14.74444, 13.5624, "Fe"),
    "[Fe][O]([Fe])[Fe].[O-]C(=O)c1ccc(cc1)NC1=NC(=[N]=C([N]1)Nc1ccc(cc1)C(=O)[O-])Nc1ccc(cc1)C(=O)[O-]": (14.64676, 8.34983, "Fe"),
    "[Ga].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[OH]": (7.194, 7.0599, "Ga"),
    "[Gd].[O-]C(=O)c1cc(NCc2ccncc2)cc(c1)C(=O)[O-]": (3.70895, 3.01422, "Gd"),
    "[Gd].[O-]C(=O)c1cc(O)c(cc1O)C(=O)[O-]": (6.46354, 4.51401, "Gd"),
    "[Gd].[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)[O-]": (5.50421, 3.43728, "Gd"),
    "[Gd].[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.52949, 4.89625, "Pr"),
    "[Gd].[O-]C(=O)c1cccc(c1)C1=C2C=CC(=C(c3ccc(cc3)C(=O)[O-])C3=NC(=C(C4=CC=C(C(=C5N=C1C=C5)c1ccc(cc1)C(=O)[O-])[N]4)c1cccc(c1)C(=O)[O-])C=C3)[N]2.[O-]C=O.[Zn]": (7.12981, 4.09174, "Zn,Gd"),
    "[Gd].[O-]C(=O)CCCC(=O)[O-]": (4.93824, 4.26323, "Gd"),
    "[Gd].[O]P(=O)(C[NH](CP(=O)(O)[O])CP(=O)([O])[O])O.[O]P(=O)(C[NH](CP(=O)([O])O)CP(=O)([O])[O])O": (3.01528, 2.44659, "Gd"),
    "[Ho].[O-]C(=O)c1cc(NCc2ccncc2)cc(c1)C(=O)[O-]": (3.73924, 3.02928, "Ho"),
    "[Ho].[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)[O-]": (5.47874, 3.67921, "Ho"),
    "[Ho].[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)O.[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)[O-]": (5.77347, 3.75877, "Ho"),
    "[Ho].[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.37123, 4.90916, "Gd"),
    "[In].[O-]C(=O)C#CC(=O)[O-].[OH]": (6.98806, 6.49312, "In"),
    "[In].[O-]C(=O)C(=O)[O-].[O-]C(=O)c1ccc(cc1)[C]1N[C](N[C](N1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (7.1167, 5.06411, "In"),
    "[In].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.25511, 5.54572, "In"),
    "[In].[O-]C(=O)c1cc(ccc1[C]1NC(=CC(=C1)c1ccc(cc1C(=O)[O-])C(=O)[O-])c1ccc(cc1C(=O)[O-])C(=O)[O-])C(=O)[O-].[Tb]": (8.61603, 6.66351, "In,Tb"),
    "[In].[O-]C(=O)c1ccc(cc1)C#Cc1c2ccccc2c(c2c1cccc2)C#Cc1ccc(cc1)C(=O)[O-].[O]": (6.12588, 5.63641, "In"),
    "[In].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)S(=O)(=O)c1ccc(cc1)C(=O)[O-]": (6.45976, 4.16361, "In"),
    "[In].[O-]C(=O)c1ccc(cc1)C1=C2C=CC(=N2)C(=c2ccc(=C(C3=NC(=C(c4[nH]c1cc4)c1ccc(cc1)C(=O)[O-])C=C3)c1ccc(cc1)C(=O)[O-])[nH]2)c1ccc(cc1)C(=O)[O-].[OH]": (7.89324, 5.37061, "In"),
    "[In].[O-]C(=O)c1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O-]C=O": (5.11087, 4.28919, "In"),
    "[In].[O-]C(=O)c1ccc(cc1)c1cc(cc(n1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1cc(nc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (11.44889, 9.53551, "In"),
    "[In].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (7.94208, 4.72487, "In"),
    "[In].[O-]C(=O)c1ccc(cc1)N(c1c(C)cc(cc1C)c1cc(C)c(c(c1)C)N(c1ccc(cc1)C(=O)O)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (9.69778, 7.05768, "In"),
    "[In].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (6.66333, 6.44658, "In"),
    "[In].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (8.37885, 6.95387, "In"),
    "[In].[O-]C(=O)c1ccc(cn1)C(=O)[O-]": (8.735, 3.2117, "In"),
    "[In].[O]c1c(Cl)c([O])c(c(c1[O])Cl)[O]": (8.43082, 7.16561, "In"),
    "[La].[O-][n+]1ccc(cc1)C(=O)[O-]": (4.5927, 3.82984, "La"),
    "[La].[O-]C(=O)c1cc(ccc1C(=O)[O-])Oc1c(cccc1C(=O)[O-])C(=O)[O-]": (6.06892, 5.17463, "La"),
    "[La].[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)O)c(nc1c1ccc(cc1)C(=O)O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)[O-])c(nc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (4.77475, 3.38214, "La"),
    "[La].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (5.4596, 4.30696, "La"),
    "[La].[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (5.92518, 4.70219, "Ho"),
    "[La].[O-]C(=O)c1ccnc(c1)c1nccc(c1)C(=O)[O-]": (6.57233, 5.02454, "La"),
    "[La].[O]N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)[O]": (8.46935, 7.71035, "La"),
    "[La].[O]P(=O)(C[NH]1CCC(CC1)C1CC[NH](CC1)CP(=O)([O])[O])[O]": (6.13677, 4.62909, "La"),
    "[La].[O]P(=O)(Cc1cc(CP(=O)([O])[O])c(cc1CP(=O)([O])[O])CP(=O)([O])[O])[O]": (6.01098, 4.02105, "La"),
    "[La][OH2][La].[O-]C(=O)c1ccc(cc1)C1=C(SC(=C2SC(=C(S2)c2ccc(cc2)C(=O)[O-])c2ccc(cc2)C(=O)[O-])S1)c1ccc(cc1)C(=O)[O-]": (7.64053, 4.52668, "La"),
    "[Lu].[O-][n+]1ccc(cc1)C(=O)[O-]": (4.77627, 3.78793, "Lu"),
    "[Mg].[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-]": (11.62878, 10.82918, "Mg"),
    "[Mg].[O-]C(=O)c1ccc(cc1)c1ccnc(c1)C(=O)[O-].[OH]": (9.93189, 8.79006, "Mg"),
    "[Mg].[O-]C(=O)c1ccc(cc1)NC1=NC(=[N]=C([N]1)Nc1ccc(cc1)C(=O)[O-])Nc1ccc(cc1)C(=O)[O-].[O-]C=O": (11.09168, 5.45555, "Mg"),
    "[Mg].[O-]C(=O)c1ccc(cc1)OCC(COc1ccc(cc1)C(=O)[O-])(COc1ccc(cc1)C(=O)[O-])COc1ccc(cc1)C(=O)[O-]": (5.47287, 4.32297, "Mg"),
    "[Mg].[O-]C(=O)c1ccncc1": (4.44189, 2.40889, "Mg"),
    "[Mg][O]([Mg])[Mg].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (8.55676, 4.36478, "Mg"),
    "[Mg]O[Mg]O[Mg].[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (6.07838, 5.2775, "Mg"),
    "[Mn].[Mn]Br.[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (5.61168, 3.75163, "Mn"),
    "[Mn].[O-]C(=O)C1=CC(=S)C(=CC1=S)C(=O)[O-]": (12.00526, 10.79373, "Mn"),
    "[Mn].[O-]C(=O)c1cc(C(=O)[O-])c(cc1C1=NN=N[N]1)C1=NN=N[N]1": (12.62081, 12.40227, "Mn"),
    "[Mn].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (4.86776, 4.0167, "Mn"),
    "[Mn].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].c1ncn(c1)c1ccc(cc1)n1cncc1": (4.55427, 3.42113, "Mn"),
    "[Mn].[O-]C(=O)c1cc(cc(c1)c1cc(nc(c1)c1ccccn1)c1ccccn1)C(=O)[O-]": (5.4427, 4.33077, "Mn"),
    "[Mn].[O-]C(=O)c1cc(CN2[N]C(=N[C]2c2ccncc2)c2ccncc2)cc(c1)C(=O)[O-].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])Cn1nc(nc1c1ccncc1)c1ccncc1": (5.32496, 3.69453, "Mn"),
    "[Mn].[O-]C(=O)c1ccc(c(c1)C(=O)[O-])c1cc(cc(n1)c1ccc(cc1C(=O)[O-])C(=O)[O-])c1ccncc1": (6.03834, 5.58255, "Mn"),
    "[Mn].[O-]C(=O)c1ccc(cc1)[Si](c1ccc(cc1)C(=O)[O-])(c1ccc(cc1)C(=O)[O-])O": (6.32579, 3.74393, "Si,Mn"),
    "[Mn].[O-]C(=O)c1ccc(cc1)C(C(F)(F)F)(C(F)(F)F)c1ccc(cc1)C(=O)[O-]": (4.55831, 2.84168, "Mn"),
    "[Mn].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)c1nc2c([nH]1)c1cccnc1c1c2cccn1": (10.29679, 5.47834, "Mn"),
    "[Mn].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)N(c1ccc(cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (16.00425, 14.45637, "Mn"),
    "[Mn].[O-]C(=O)c1ccc(cc1c1cccc(n1)c1cc(ccc1C(=O)[O-])C(=O)[O-])C(=O)[O-]": (7.45612, 4.57929, "Mn"),
    "[Mn].[O-]C=O": (4.37093, 2.54585, "Mn"),
    "[Mn][Mn].[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2c1ccc(cc1)c1ccc(cc1)n1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (22.45958, 11.94743, "Mn"),
    "[Mn][OH2][Mn].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (6.59676, 5.16721, "Mn"),
    "[Mn][OH2][Mn][OH2][Mn].[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (5.9032, 5.31291, "Mn"),
    "[Mn]O[Mn].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (6.72323, 5.2222, "Mn"),
    "[N]1[CH]C=C(C=C1)c1ccc(cc1)C(=C(c1ccc(cc1)C1=C[CH][N]C=C1)c1ccc(cc1)C1=C[CH][N]C=C1)c1ccc(cc1)C1=C[CH][N]C=C1.[O-]C(=O)c1cccc(c1)C(=O)[O-].[Zn]": (7.98999, 5.66524, "Zn"),
    "[Nd].[O-][n+]1ccc(cc1)C(=O)[O-]": (4.77313, 3.82049, "Nd"),
    "[Nd].[O-]C(=O)c1c(F)c(F)c(c(c1F)F)C(=O)[O-]": (4.57962, 3.51168, "Nd"),
    "[Nd].[O-]C(=O)c1cc(ccc1C(=O)[O-])Oc1c(cccc1C(=O)[O-])C(=O)[O-]": (6.02071, 5.15652, "Nd"),
    "[Nd].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-]": (5.64911, 4.27538, "Nd"),
    "[Nd].[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.42297, 4.95585, "Nd"),
    "[Nd].[O-]C(=O)CN(CC(=O)[O-])CCCN(CC(=O)[O-])CC(=O)[O-]": (4.27264, 3.02027, "Nd"),
    "[Nd].[O-]C(=O)COc1ccc(cc1)N(CC(=O)[O-])CC(=O)[O-]": (4.66818, 3.88136, "Nd"),
    "[Ni].[O-]C(=O)C(=O)[O-].c1ncn(c1)c1ccc(cc1)C(c1ccc(cc1)n1cncc1)(c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1": (8.68471, 5.22052, "Ni"),
    "[Ni].[O-]C(=O)C=CC=CC(=O)[O-].n1ccc(cc1)C=Cc1ccncc1": (6.66867, 5.80296, "Ni"),
    "[Ni].[O-]C(=O)C=CC=CC(=O)[O-].n1ccc(cc1)CCc1ccncc1": (6.29164, 5.43914, "Ni"),
    "[Ni].[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-]": (11.61966, 10.85724, "Ni"),
    "[Ni].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].n1ccc(cc1)c1ccncc1": (3.11102, 2.44478, "Ni"),
    "[Ni].[O-]C(=O)c1cc(ccc1C(=O)O)c1ccc(nc1)C(=O)[O-].n1ccc(cc1)c1ccncc1": (5.99567, 4.91511, "Ni"),
    "[Ni].[O-]C(=O)c1cc(ccc1c1cc(nc(c1)c1ccncc1)c1ccncc1)C(=O)[O-]": (6.2418, 3.78915, "Ni"),
    "[Ni].[O-]C(=O)c1cc(Oc2ccc(cc2)c2cc(nc(c2)c2ccncc2)c2ccncc2)cc(c1)C(=O)[O-]": (4.85428, 3.67505, "Ni"),
    "[Ni].[O-]C(=O)c1ccc(cc1)C(=O)[O-].c1ncn(c1)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1": (5.00576, 3.06121, "Ni"),
    "[Ni].[O-]C(=O)c1ccc(cc1)n1ccnc1c1nccn1c1ccc(cc1)C(=O)[O-]": (5.90426, 4.22577, "Ni"),
    "[Ni].[O-]C(=O)c1cccc(c1)C(=O)[O-].c1ncn(c1)Cc1ccc(cc1)c1ccc(cc1)Cn1cncc1": (3.56425, 3.03344, "Ni"),
    "[Ni].[O-]C(=O)c1cccc(c1)C1=[N]=C(N=N1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].n1ccc(cc1)c1ccncc1": (5.33173, 4.44846, "Ni"),
    "[Ni].[O-]C(=O)c1cccc(c1)c1ccncc1": (7.55291, 6.22098, "Ni"),
    "[Ni].[O-]C(=O)c1ccncc1": (5.21863, 3.66829, "Ni"),
    "[Ni].[O-]C(=O)c1ccncc1N": (5.38628, 3.79465, "Ni"),
    "[Ni].n1ccc(cc1)C=Cc1ccncc1": (11.14925, 6.60182, "Ni"),
    "[Ni].n1ccncc1": (4.08645, 3.31052, "Ni,Ge"),
    "[Ni][Ni].[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2c1ccc(cc1)c1ccc(cc1)n1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (22.80759, 12.55712, "Ni"),
    "[Ni][O]([Ni])[Ni].[O-]C(=O)c1cc(c2ccc(cc2)C(=O)[O-])c(c(c1)c1ccc(cc1)C(=O)[O-])F": (14.03896, 5.74243, "Ni"),
    "[Ni][O]([Ni])[Ni].[O-]C(=O)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (11.37857, 5.62966, "Ni"),
    "[Ni][OH2][Ni].[O-]C(=O)c1cc(ccc1c1ccc(c(c1)N(=O)=O)C(=O)[O-])C(=O)[O-].[OH2][Ni].n1ccc(cc1)c1ccncc1": (5.84904, 4.05574, "Ni"),
    "[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43.[O]c1c(c2ccc(cc2)C(=O)[O-])c2ccc3c4c2c(c1c1ccc(cc1)C(=O)[O-])ccc4c(c(c3c1ccc(cc1)C(=O)[O-])[O])c1ccc(cc1)C(=O)[O-]": (30.57858, 29.28279, "Zr"),
    "[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43.[O]c1c(cc(cc1c1ccc(cc1)C(=O)[O-])c1cc(c2ccc(cc2)C(=O)[O-])c(c(c1)c1ccc(cc1)C(=O)[O-])[O])c1ccc(cc1)C(=O)[O-]": (30.8785, 29.56547, "Zr"),
    "[O-]C(=O)[C]1C=CC2=NN=NC2=C1.[O-]C(=O)c1ccc2c(c1)[N]N=N2.[OH].[Zn]": (4.72948, 4.20723, "Zn"),
    "[O-]C(=O)C#CC(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (4.57421, 2.50359, "Zr"),
    "[O-]C(=O)C(=O)[O-].[Sc]": (3.36985, 2.94067, "Sc"),
    "[O-]C(=O)C(=O)[O-].[U]": (5.53669, 4.08743, "U"),
    "[O-]C(=O)C(NC(=O)C1=CN=N[CH]1)C.[Zn]": (8.61383, 5.8044, "Zn"),
    "[O-]C(=O)C.[O-]C(=O)c1ccc(cc1)P(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (6.81859, 3.42446, "Zr"),
    "[O-]C(=O)C=CC(=O)[O-].[Sm]": (5.24348, 4.37673, "Sm"),
    "[O-]C(=O)C=CC(=O)[O-].[Tb]": (5.32073, 4.35505, "Tb"),
    "[O-]C(=O)C=CC=CC(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (9.82414, 8.45778, "Zr"),
    "[O-]C(=O)C1=C[C]2C(=NN=N2)C=C1.[O-]C(=O)[C]1C=CC2=NN=NC2=C1.[O-]C(=O)c1ccc2=N[N]N=c2c1.[OH].[Zn]": (6.82151, 5.80512, "Zn"),
    "[O-]C(=O)C1=C[CH]C(C=C1)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (10.97178, 8.95221, "Zn"),
    "[O-]C(=O)C1=CC(=CN([CH]1)Cc1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-].[Zn].n1ccc(cc1)C=Cc1ccncc1": (5.33318, 4.51857, "Zn"),
    "[O-]C(=O)C1=CC2=NN=N[C]2C=C1.[O-]C(=O)C1=CC=C2C(=NN=N2)[CH]1.[O-]C(=O)C1=C[CH]C2=NN=NC2=C1.[OH].[Zn]": (6.95277, 5.98087, "Zn"),
    "[O-]C(=O)C1=CC2=NN=N[C]2C=C1.[O-]C(=O)C1=CC=C2C(=NN=N2)[CH]1.[OH].[Zn]": (4.80099, 4.24264, "Zn"),
    "[O-]C(=O)C1=CC2=NN=NC2=C[CH]1.[O-]C(=O)C1=C[C]2C(=NN=N2)C=C1.[O-]C(=O)c1ccc2c(c1)[N]N=N2.[O].[Zn]": (4.03404, 3.63636, "Zn"),
    "[O-]C(=O)C1=CN=N[CH]1.[O-]C(=O)[C]1C=NN=C1.[Zn][O]([Zn])([Zn])[Zn]": (10.81396, 5.19047, "Zn"),
    "[O-]C(=O)C1=NN=C([CH]1)C(=O)[O-].[O-]C(=O)C1=N[N]C(=C1)C(=O)[O-].[O-]C(=O)[C]1N=NC(=C1)C(=O)[O-].[O-]C(=O)c1ccncc1.[Zn]": (5.29277, 3.75821, "Zn"),
    "[O-]C(=O)c1c(F)c(F)c(c(c1F)F)C(=O)[O-].[Pr]": (4.62788, 3.52991, "Pr"),
    "[O-]C(=O)c1c(F)c(F)c(c(c1F)F)C(=O)[O-].[Tb][Tb]": (3.53975, 2.89855, "Tb"),
    "[O-]C(=O)c1c(F)c(F)c(c(c1F)F)c1c(F)c(F)c(c(c1F)F)C(=O)[O-].[Zn]": (7.57818, 5.57079, "Zn"),
    "[O-]C(=O)c1c[n-]n(c1)C(n1[n-]cc(c1)C(=O)[O-])c1ccc(cc1)C(n1[n-]cc(c1)C(=O)[O-])n1[n-]cc(c1)C(=O)[O-].[OH]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[OH]3[Zr]35[OH]6[Zr]2([OH]71)[OH]43": (8.14938, 5.73016, "Zr"),
    "[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-].[Ti]": (6.25402, 4.56727, "Ti"),
    "[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-].[Ti]O[Ti]": (4.20028, 3.67349, "Ti"),
    "[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-].[Zn]": (11.72528, 10.94185, "Zn"),
    "[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-].[Zn].n1ccc(cc1)C=Cc1ccncc1": (7.14455, 4.72838, "Zn"),
    "[O-]C(=O)c1cc(C(=O)[O-])c(c(c1)C(=O)[O-])[O].[Zn].n1ccc(cc1)c1ccncc1": (6.83229, 2.91537, "Zn"),
    "[O-]C(=O)c1cc(C(=O)[O-])c(cc1C(=O)[O-])C(=O)[O-].[Sm].[Sm][Sm]": (6.85822, 4.38655, "Sm"),
    "[O-]C(=O)c1cc(C(=O)[O-])c(cc1C(=O)[O-])C(=O)[O-].[Zn]": (11.5324, 10.59043, "Zn"),
    "[O-]C(=O)c1cc(C)c(c(c1)C)c1cccc(c1)c1c(C)cc(cc1C)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (38.91559, 21.05336, "Zr"),
    "[O-]C(=O)c1cc(c2cc(cc(c2)C(=O)[O-])C(=O)[O-])c(cc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-].[Zn][O]1[Zn][O]([Zn]1)[Zn]": (5.05381, 3.72999, "Zn"),
    "[O-]C(=O)c1cc(c2ccc(cc2)C(=O)[O-])c(cc1c1ccc(cc1)C(=O)[O-])C(=O)[O-].[Tb]": (5.90634, 4.81591, "Tb"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Tb]": (6.88171, 6.36573, "Tb"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn].[Zn][O]([Zn])([Zn])[Zn]": (7.5478, 6.22346, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(c2cc(cc(c2)C(=O)[O-])C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (6.69877, 5.40684, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[OH].[Sc]": (7.29761, 7.13277, "Sc"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[OH].[V]": (7.31261, 7.0938, "V"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn].n1ncn[nH]1": (5.73229, 4.20006, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn][Zn]": (10.21223, 5.01419, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)c1cc(cc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (10.40655, 5.09847, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1ccc(c(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (5.9825, 4.52202, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1ccc(cc1)C(=C(c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1ccc(cc1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn][Zn]": (13.72333, 6.58171, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])Cn1nc(nc1c1ccncc1)c1ccncc1.[Zn]": (4.56185, 3.67847, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (9.83426, 7.01492, "Zr"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn].n1ccc(cc1)C=Cc1ccncc1": (4.2583, 2.48974, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn].n1ccc(cc1)CCc1ccncc1": (4.32855, 3.65959, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])N1CCCC1.[Zn]": (7.25206, 5.23684, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)C(=O)[O-])O[C]1=[N]=[C](=[N]=[C](=[N]=1)Oc1cc(cc(c1)C(=O)[O-])C(=O)[O-])Oc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn].[Zn][Zn]": (14.34886, 6.30486, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)Oc1cc(cc(c1)C(=O)[O-])C(=O)[O-])Oc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn][OH]1[Zn][OH2][Zn][OH]([Zn][OH2][Zn]1)[Zn]": (6.01545, 4.52404, "Zn"),
    "[O-]C(=O)c1cc(cc(c1)Oc1cccc(c1)C(=O)[O-])Oc1cccc(c1)C(=O)[O-].[OH2][Mn][OH2][Mn][OH2][Mn][OH2]": (5.87641, 4.92231, "Mn"),
    "[O-]C(=O)c1cc(cc(c1)S([O])([O])[O])C(=O)[O-].[Zn][OH][Zn].c1ncn(c1)CC(Cn1cncc1)(Cn1cncc1)Cn1cncc1": (4.26643, 2.55509, "Zn"),
    "[O-]C(=O)c1cc(cc(n1)C(=O)[O-])c1cc(nc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (4.38152, 2.99318, "Zn"),
    "[O-]C(=O)c1cc(ccc1C(=O)[O-])Oc1c(cccc1C(=O)[O-])C(=O)[O-].[OH2][Ce]": (6.02822, 5.14433, "Ce"),
    "[O-]C(=O)c1cc(ccc1C(=O)[O-])Oc1c(cccc1C(=O)[O-])C(=O)[O-].[Pr]": (5.93521, 5.05929, "Pr"),
    "[O-]C(=O)c1cc(ccc1C(=O)[O-])Oc1c(cccc1C(=O)[O-])C(=O)[O-].[Sm]": (6.01576, 5.15845, "Sm"),
    "[O-]C(=O)c1cc(ccc1c1ccc(c(c1)N(=O)=O)C(=O)[O-])C(=O)[O-].[Zn][OH]1[Zn][OH]([Zn]1)[Zn].n1ccc(cc1)c1ccncc1": (6.88202, 3.80287, "Zn"),
    "[O-]C(=O)c1cc(ccc1c1ccc(nc1)C(=O)[O-])C(=O)[O-].[Zn][OH][Zn]": (5.00069, 3.24152, "Zn"),
    "[O-]C(=O)c1cc(COc2cccc(c2)C(=O)O)cc(c1)C(=O)[O-].[Zn].n1ccc(cc1)CCc1ccncc1": (4.65353, 4.1972, "Zn"),
    "[O-]C(=O)c1cc(CSc2nc3c([nH]2)cccc3)cc(c1)C(=O)[O-].[Zn]": (5.29331, 4.03957, "Zn"),
    "[O-]C(=O)c1cc(CSc2nc3c([nH]2)cccc3)cc(c1)C(=O)[O-].[Zn].c1ncn(c1)c1ccc(cc1)c1ccc(cc1)n1cncc1": (5.29134, 3.52181, "Zn"),
    "[O-]C(=O)c1cc(N2[N]C=N[CH]2)c(cc1N1[N]C=N[CH]1)C(=O)[O-].[Zn]": (5.6478, 4.32887, "Zn"),
    "[O-]C(=O)c1cc(nc(c1)n1[n-]cc(c1)C(=O)[O-])n1[n-]cc(c1)C(=O)[O-].[Sc][O]([Sc])[Sc]": (11.9339, 9.85072, "Sc"),
    "[O-]C(=O)c1cc(NC2=NC(=[N]=C([N]2)Nc2cc(cc(c2)C(=O)[O-])C(=O)[O-])Nc2cc(cc(c2)C(=O)[O-])C(=O)[O-])cc(c1)C(=O)[O-].[Tb]O[Tb]": (16.50327, 4.60014, "Tb"),
    "[O-]C(=O)c1cc(NC2=NC(=[N]=C([N]2)Nc2cc(cc(c2)C(=O)[O-])C(=O)[O-])Nc2cc(cc(c2)C(=O)[O-])C(=O)[O-])cc(c1)C(=O)[O-].[Zn].[Zn][O]([Zn])[Zn]": (9.69734, 4.09287, "Zn"),
    "[O-]C(=O)c1cc(Nc2ccccc2)c(cc1Nc1ccccc1)C(=O)[O-].[Zn][O]1[Zn][O]([Zn]1)[Zn]": (6.11542, 4.24797, "Zn"),
    "[O-]C(=O)c1cc(NCc2ccncc2)cc(c1)C(=O)[O-].[Sm]": (3.72178, 2.99213, "Sm"),
    "[O-]C(=O)c1cc(NCc2ccncc2)cc(c1)C(=O)[O-].[Tb]": (3.74664, 2.97877, "Tb"),
    "[O-]C(=O)c1cc(NCc2ccncc2)cc(c1)C(=O)[O-].[Yb]": (3.68514, 2.8452, "Yb"),
    "[O-]C(=O)c1cc(O)c(cc1O)C(=O)[O-].[O-]C(=O)c1cc([O])c(cc1[O])C(=O)[O-].[Tb]": (5.91874, 5.47496, "Tb"),
    "[O-]C(=O)c1cc(O)c(cc1O)C(=O)[O-].[Tb]": (6.46172, 4.50656, "Tb"),
    "[O-]C(=O)c1cc(Oc2cc(cc(c2)C(=O)[O-])C(=O)[O-])cc(c1)C(=O)[O-].[Zn]": (5.01483, 2.84606, "Zn"),
    "[O-]C(=O)c1cc(Oc2ccc(cc2)C2=NN=N[N]2)cc(c1)C(=O)[O-].[OH2][Eu][OH2]": (4.58904, 3.79464, "Eu"),
    "[O-]C(=O)c1cc(Oc2ccc(cc2)C2=NN=N[N]2)cc(c1)C(=O)[O-].[OH2][Gd]": (4.63435, 3.76627, "Gd"),
    "[O-]C(=O)c1cc(Oc2ccc(cc2)C2=NN=N[N]2)cc(c1)C(=O)[O-].[OH2][Sm][OH2]": (4.59113, 3.81916, "Sm"),
    "[O-]C(=O)c1cc(OCc2ccc(cc2)C(=O)[O-])cc(c1)OCc1ccc(cc1)C(=O)[O-].[OH].[Zn]": (7.23448, 6.45356, "Zn"),
    "[O-]C(=O)c1cc2ccccc2c(c1O)c1c(O)c(cc2c1cccc2)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (8.92524, 4.60995, "Zn"),
    "[O-]C(=O)c1ccc(c(c1)[O])C(=O)[O-].[OH].[Zn]": (13.36572, 13.28871, "Zn"),
    "[O-]C(=O)c1ccc(c(c1)Br)C(=O)[O-].[O].[V]": (3.74263, 3.52093, "V"),
    "[O-]C(=O)c1ccc(c(c1)C(F)(F)F)C(=O)[O-].[O].[V]": (6.81587, 4.8163, "V"),
    "[O-]C(=O)c1ccc(c(c1)N)[O].[Y][OH]1[Y]2[OH]([Y]1[OH]2[Y])[Y]": (6.59775, 3.98138, "Y"),
    "[O-]C(=O)c1ccc(c(c1)n1cncc1)C(=O)[O-].[Pb]": (3.58998, 2.74204, "Pb"),
    "[O-]C(=O)c1ccc(c(c1)n1cncc1)C(=O)[O-].[Pb].[Zn]": (4.69165, 3.22734, "Zn,Pb"),
    "[O-]C(=O)c1ccc(c(c1N)N)C(=O)[O-].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)CN1CCN(CC1)Cc1ccncc1": (7.03576, 5.263, "Zn"),
    "[O-]C(=O)C1CCC(C1(C)C)(C)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (6.42741, 5.33782, "Zn"),
    "[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-].[Zn].[Zn]I.c1ncn(c1)c1cc(cc(c1)n1cncc1)n1cncc1": (5.82322, 4.02198, "Zn"),
    "[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-].[Zn][Zn].n1ccc(cc1)CCc1ccncc1": (4.37219, 3.38023, "Zn"),
    "[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-].[Zn][Zn].n1ccc(cc1)OCC(COc1ccncc1)(COc1ccncc1)COc1ccncc1": (3.21704, 2.44664, "Zn"),
    "[O-]C(=O)c1ccc(cc1)[B]12ON3C4=C(N5[Fe]6783N(O1)C1=C(N8O[B](ON7C3=C(N6O2)CCCC3)(O5)c2ccc(cc2)C(=O)[O-])CCCC1)CCCC4.[Zn][Zn]": (6.8367, 5.86263, "Zn,Fe"),
    "[O-]C(=O)c1ccc(cc1)[Si](c1ccc(cc1)C(=O)[O-])(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn]": (7.41499, 5.39472, "Zn,Si"),
    "[O-]C(=O)c1ccc(cc1)[Si](c1ccc(cc1)C(=O)[O-])(c1ccc(cc1)C(=O)[O-])O.[Zn][OH]1[Zn][OH]([Zn]1)[Zn]": (7.95864, 5.64514, "Zn,Si"),
    "[O-]C(=O)c1ccc(cc1)[Si](c1ccc(cc1)C(=O)[O-])(O[Si](c1ccc(cc1)C(=O)[O-])(c1ccc(cc1)C(=O)[O-])C)C.[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (10.23605, 7.94535, "Si,Zr"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1c(F)c(F)c(c(c1F)F)C#Cc1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (19.18618, 13.02178, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1c2c(c(c3c1C1c4c(C3c3c1cccc3)cccc4)C#Cc1ccc(cc1)C(=O)[O-])C1c3c(C2c2c1cccc2)cccc3.[Zn][Zn]": (9.56202, 7.99894, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1cc(C#Cc2ccc(cc2)C(=O)[O-])c(cc1C#Cc1ccc(cc1)C(=O)[O-])C#Cc1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (9.619, 8.95222, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c(c1)c1cc(cc(c1[nH]2)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (13.74408, 7.17576, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1cc(C#CC#Cc2cc(cc(c2)c2ccc(cc2)C(=O)[O-])c2ccc(cc2)C(=O)[O-])cc(c1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (15.52353, 8.15201, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-].[OH].[Sc]": (5.96067, 5.71458, "Sc"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-].[OH]1[Hf]2345[OH][Hf]6781[O]1[Hf]9%10[OH]7[Hf]7%11%12%13[O]8[Hf]8%14%15([OH]6[Hf]61[OH]9[Hf]([O]%10%12)([O]%146)[OH]%13%15)[OH][Hf]169([OH]4[Hf]4%10[O]2[Hf]2%12[OH]3[Hf]3([O]51)([O]%12[Hf]([OH]42)([O]6%10)[OH]93)([OH]7)[OH]%11)[OH]8": (15.48228, 8.99991, "Hf"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-].[OH]1[Zr]2345[OH][Zr]6781[O]1[Zr]9%10[OH]7[Zr]7%11%12%13[O]8[Zr]8%14%15([OH]6[Zr]61[OH]9[Zr]([O]%10%12)([O]%146)[OH]%13%15)[OH][Zr]169([OH]4[Zr]4%10[O]2[Zr]2%12[OH]3[Zr]3([O]51)([O]%12[Zr]([OH]42)([O]6%10)[OH]93)([OH]7)[OH]%11)[OH]8": (15.6067, 9.04109, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C#Cc1ccc(cc1)C1=C2C=CC(=N2)C(=c2ccc(=C(C3=NC(=C(c4[nH]c1cc4)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-])C=C3)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-])[nH]2)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (25.24149, 10.49588, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O]12[Th]34[O]5[Th]62[O]2[Th]71[O]4[Th]14[O]3[Th]35[O]6[Th]2([O]71)[O]43": (9.53216, 4.31912, "Th"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (8.89938, 5.56526, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (8.57883, 4.07716, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c(c1)c1cc(cc(c1[nH]2)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (12.55429, 9.64029, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c(c1)c1cc(cc(c1[nH]2)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (12.91193, 7.01638, "Zr"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc2-c3c(C(c2c1)(C)C)c1-c2ccc(cc2C(c1c1-c2c(C(c31)(C)C)cc(cc2)C(=O)[O-])(C)C)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (21.77624, 7.63056, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[OH].[V]": (6.89356, 6.68644, "V"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Sc]": (3.96948, 3.00871, "Sc"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn]": (7.20343, 5.1239, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)C1=C[N]N=C1.n1ccc(cc1)[C]1C=NN=C1": (6.35126, 3.89746, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)C1=CC=C2N([CH]1)CC([N]2)c1ccc(cc1)c1ccncc1.n1ccc(cc1)C1=CN2C(=NC(C2)c2ccc(cc2)c2ccncc2)C=C1": (6.65423, 4.59023, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)c1c2CCC[CH]c2c(c2c1nc1ccccc1n2)c1ccncc1.n1ccc(cc1)c1c2nc3ccccc3nc2c(c2c1cccc2)c1ccncc1": (6.71711, 4.38612, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (14.86745, 7.89338, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn][OH]1[Zn][OH]([Zn]1)[Zn]": (5.37644, 2.95718, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C(c1ccc(cc1)C(=O)[O-])N1[N]C=N[CH]1.[Zn]": (5.8685, 3.23791, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C[NH](Cc1ccc(cc1)C(=O)[O-])CCCN(Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)C(=O)[O-].[Zn]": (9.30214, 8.99325, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)[CH][CH]c1ccc(cc1)C(=O)[O-].[Tm].[Tm][Tm]": (10.0181, 8.74126, "Tm"),
    "[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)[O-].[Zn].[Zn][Zn].n1ccc(cc1)c1ccc(cc1)N(c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1": (6.28877, 4.52526, "Zn"),
    "[O-]C(=O)c1ccc(cc1)C1=C(SC(=C2SC(=C(S2)c2ccc(cc2)C(=O)[O-])c2ccc(cc2)C(=O)[O-])S1)c1ccc(cc1)C(=O)[O-].[U]": (8.58792, 5.46645, "U"),
    "[O-]C(=O)c1ccc(cc1)C1=C2C=CC3=[N]2[Cu]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2ccc(cc2)C(=O)[O-])cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (25.91648, 14.4538, "Cu,Zr"),
    "[O-]C(=O)c1ccc(cc1)C1=C2C=CC3=[N]2[Zn]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2ccc(cc2)C(=O)[O-])cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Ce]34[O]5[Ce]62[O]2[Ce]71[O]4[Ce]14[O]3[Ce]35[O]6[Ce]2([O]71)[O]43": (23.2696, 14.5945, "Ce,Zn"),
    "[O-]C(=O)c1ccc(cc1)C1=C2C=CC3=[N]2[Zn]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2ccc(cc2)C(=O)[O-])cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn][Zn].c1ccc2c(c1)[nH]c(n2)C=Cc1nc2c([nH]1)cccc2": (6.73649, 4.79556, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1c2cccc3c2c2c(c1c1ccc(cc1)C(=O)[O-])cccc2c(c3c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (28.48606, 16.86175, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1cc(C#CC#Cc2cc(cc(c2)c2ccc(cc2)C(=O)[O-])c2ccc(cc2)C(=O)[O-])cc(c1)c1ccc(cc1)C(=O)[O-].[O]12[Hf]34[O]5[Hf]62[O]2[Hf]71[O]4[Hf]14[O]3[Hf]35[O]6[Hf]2([O]71)[O]43": (15.77552, 12.2299, "Hf"),
    "[O-]C(=O)c1ccc(cc1)c1cc(C#CC#Cc2cc(cc(c2)c2ccc(cc2)C(=O)[O-])c2ccc(cc2)C(=O)[O-])cc(c1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (16.55771, 13.56943, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1cc(C)c(cc1C)c1cc(c2cc(C)c(cc2C)c2ccc(cc2)C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1cc(C)c(cc1C)c1ccc(cc1)C(=O)[O-])c1cc(C)c(cc1C)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (17.75046, 8.47189, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c(c(c1C)c1c(C)c(cc(c1O)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])O.[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]3[Zr]1389%10[O]%114[Zr]4%12%13%145[O]56[Zr]6%15%162([O]71[O]86[Zr]12[O]%10[Zr]6([O]3%114)[O]%13[Zr]([O]%125%15)([O]%161)[O]26)[O]9%14": (10.60005, 10.2764, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O].[V]": (5.93115, 5.17612, "V"),
    "[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c(c1)c1cc(cc(c1[nH]2)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (13.93085, 11.69175, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c3c1CCC13CCc3c1c(OP(=O)(O2)[O])c(cc3c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (19.8152, 12.73503, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Ce]34[O]5[Ce]62[O]2[Ce]71[O]4[Ce]14[O]3[Ce]35[O]6[Ce]2([O]71)[O]43": (23.51979, 17.73807, "Ce"),
    "[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (30.19427, 28.66711, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn]": (6.89226, 6.44672, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c2c3c1ccc1c3c(cc2)c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn][Zn]": (5.94412, 5.16816, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])C1=NN=N[N]1.[OH]12[Tb]34[OH]5[Tb]672[O]2[Tb]891[OH]4[Tb]14%10[OH]3[Tb]3%115[OH]7[Tb]57[OH]6[Tb]6%122[OH]9[Tb]2([OH]81)[OH]%10[Tb]([OH]35)([O]4%11)([OH]62)[OH]7%12": (15.78006, 11.0802, "Tb"),
    "[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O-]C=O.[Sc][O]([Sc])[Sc]": (20.34171, 19.92491, "Sc"),
    "[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Yb][Yb]": (4.73732, 3.96673, "Yb"),
    "[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)C=Cc1ccncc1": (9.12982, 7.14176, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1cc(cc(n1)c1ccc(cc1)C(=O)[O-])c1ccncc1.[Tb][OH]1[Tb][OH]2[Tb]1[OH]1[Tb]2[OH]([Tb]1)[Tb]": (6.30191, 3.57459, "Tb"),
    "[O-]C(=O)c1ccc(cc1)c1cc2c(cc1c1ccc(cc1)C(=O)[O-])c1cc(c3ccc(cc3)C(=O)[O-])c(cc1c1c2cc(c2ccc(cc2)C(=O)[O-])c(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (12.90854, 5.36266, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(c(c1)[O])C(=O)[O-].[OH].[Zn]": (11.52189, 10.02524, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(c2c1N[C](N2)c1ccc(cc1)[C]1Nc2c(N1)c(ccc2c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (11.61449, 9.32322, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=C(c1ccc(cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (10.6532, 5.07152, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (12.59507, 5.60823, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[OH]12[Tb]34[OH]5[Tb]62[OH]2[Tb]71[OH]4[Tb]14[OH]3[Tb]35[OH]6[Tb]2([OH]71)[OH]43": (13.37735, 6.88633, "Tb"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn].[Zn][Zn].n1ccc(cc1)c1ccc(cc1)N(c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1": (4.58326, 2.85966, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)C=Cc1ccncc1": (5.31297, 5.06772, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (10.86811, 8.81679, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn][Zn]": (4.83867, 4.02901, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C1=C2C=CC(=N2)C(=c2ccc(=C(C3=NC(=C(c4[nH]c1cc4)c1ccc(cc1)c1ccc(cc1)C(=O)[O-])C=C3)c1ccc(cc1)c1ccc(cc1)C(=O)[O-])[nH]2)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (21.33814, 8.58272, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C1=C2C=CC3=[N]2[Ni]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2ccc(cc2)c2ccc(cc2)C(=O)[O-])cc1)c1ccc(cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (21.37941, 8.74134, "Ni,Zr"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (17.52486, 9.15991, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1ccc(cc1)c1nc2c([nH]1)c1cccnc1c1c2cccn1.[O-]C=O.[Zn]": (10.77433, 10.34801, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1ccc2c(c1)c1cc(ccc1[nH]2)c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (7.59184, 6.0757, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1cccc(c1)c1ccc(cc1)C(=O)[O-].[O]12[Hf]34[O]5[Hf]62[O]2[Hf]71[O]4[Hf]14[O]3[Hf]35[O]6[Hf]2([O]71)[O]43": (6.92134, 5.93913, "Hf"),
    "[O-]C(=O)c1ccc(cc1)c1cncc(c1)c1ccc(cc1)C(=O)[O-].[Zn]": (4.89324, 3.67818, "Zn"),
    "[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)[O-])c(nc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (9.29295, 7.14182, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)[O-])c(nc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[OH]5[Zr]62[OH]2[Zr]71[OH]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[OH]43": (9.30717, 7.21012, "Zr"),
    "[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)[O-])c(nc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[OH]12[Hf]34[OH]5[Hf]62[OH]2[Hf]71[OH]4[Hf]14[OH]3[Hf]35[OH]6[Hf]2([OH]71)[OH]43": (9.19603, 6.9911, "Hf"),
    "[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)[O-])c(nc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Pb]": (4.65844, 3.66349, "Pb"),
    "[O-]C(=O)c1ccc(cc1)c1nc(c2ccc(cc2)C(=O)[O-])c(nc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Sc]O[Sc]": (6.81679, 4.02175, "Sc"),
    "[O-]C(=O)c1ccc(cc1)c1nn(nc1c1ccc(cc1)C(=O)[O-])c1ccccc1.[Zn][Zn]": (5.85166, 4.7117, "Zn"),
    "[O-]C(=O)c1ccc(cc1)CN1CCN(CCN(CC1)Cc1ccc(cc1)C(=O)[O-])Cc1ccc(cc1)C(=O)[O-].[Zn]": (5.49532, 3.6076, "Zn"),
    "[O-]C(=O)c1ccc(cc1)CNCc1ccc(cc1)C(=O)[O-].[Zn][Zn]": (15.28978, 13.75598, "Zn"),
    "[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn].[Zn][Zn].n1ccc(cc1)c1ccncc1": (8.91532, 5.96302, "Zn"),
    "[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)C=Cc1ccncc1": (6.90883, 3.90614, "Zn"),
    "[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (11.61707, 9.67324, "Zn"),
    "[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)c1ccc(s1)C(=O)[O-])c1ccc(cc1)c1ccc(s1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (13.71134, 11.05968, "Zn"),
    "[O-]C(=O)c1ccc(cc1)n1ccnc1c1nccn1c1ccc(cc1)C(=O)[O-].[Zn]": (5.87904, 4.42765, "Zn"),
    "[O-]C(=O)c1ccc(cc1)n1cnnc1.[Zn]": (5.6878, 4.46539, "Zn"),
    "[O-]C(=O)c1ccc(cc1)n1nc(c(n1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn].[Zn]O[Zn].[Zn][O]([Zn])[Zn]": (7.03598, 4.41271, "Zn"),
    "[O-]C(=O)c1ccc(cc1)n1nnc(c1)c1cc(cc(c1)c1nnn(c1)c1ccc(cc1)C(=O)[O-])c1nnn(c1)c1ccc(cc1)C(=O)[O-].[Zn].[Zn]O[Zn]": (18.21119, 15.60206, "Zn"),
    "[O-]C(=O)c1ccc(cc1)NC1=[N]=C(N=C([N]1)Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-])Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (12.49257, 9.0047, "Zn"),
    "[O-]C(=O)c1ccc(cc1)NC1=NC(=[N]=C([N]1)Nc1ccc(cc1)C(=O)[O-])Nc1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (13.58014, 8.80376, "Zn"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[O]12[Y]34[O]5[Y]62[O]2[Y]71[O]4[Y]14[O]3[Y]35[O]6[Y]2([O]71)[O]43": (11.52258, 6.73257, "Y"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (9.07817, 6.77757, "Zr"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Tb]": (7.11031, 6.37447, "Tb"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn]": (5.81954, 3.69681, "Zn"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)CNc1ccc(cc1)NCc1ccncc1": (6.88365, 6.42016, "Zn"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)CNc1cccc2c1cccc2NCc1ccncc1": (6.75137, 6.49633, "Zn"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn][Zn]": (4.89084, 4.20307, "Zn"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn][Zn].n1ccc(cc1)C1=CN2N(S1)C=C(S2)c1ccncc1.n1ccc(cc1)c1nc2c(s1)nc(s2)c1ccncc1": (6.0665, 4.22099, "Zn"),
    "[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn][Zn].n1ccc(cc1)c1ccncc1": (4.73011, 2.94949, "Zn"),
    "[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Pr]": (6.03249, 4.77547, "Er"),
    "[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Sm]": (6.62817, 4.99333, "Sm"),
    "[O-]C(=O)c1ccc(cc1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Tb]": (5.97358, 4.67804, "Tb"),
    "[O-]C(=O)c1ccc(cc1)P(=O)(c1ccc(cc1)C(=O)O)c1ccc(cc1)C(=O)[O-].[Zn][Zn]": (6.62246, 3.70658, "Zn"),
    "[O-]C(=O)c1ccc(cc1)S(=O)(=O)c1ccc(cc1)C(=O)[O-].[OH].[Zn]": (4.82391, 4.37452, "Zn"),
    "[O-]C(=O)c1ccc(cc1F)c1ccc(cc1)N(c1ccc(cc1)c1ccc(c(c1)F)C(=O)[O-])c1ccc(cc1)N(c1ccc(cc1)c1ccc(c(c1)F)C(=O)[O-])c1ccc(cc1)c1ccc(c(c1)F)C(=O)[O-].[Zn]": (5.82462, 3.79137, "Zn"),
    "[O-]C(=O)c1ccc(cc1NC1=NC(=[N]=C([N]1)Nc1cc(ccc1C(=O)[O-])C(=O)[O-])Nc1cccc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (16.8948, 8.02784, "Zn"),
    "[O-]C(=O)c1ccc(cc1NC1=NC(=[N]=C([N]1)Nc1ccc(cc1)C(=O)[O-])Nc1cc(ccc1C(=O)[O-])C(=O)[O-])C(=O)[O-].[Zn]": (7.85261, 7.16307, "Zn"),
    "[O-]C(=O)c1ccc(nc1)c1ccc(cn1)C(=O)[O-].[Sc]": (6.15436, 5.5019, "Sc"),
    "[O-]C(=O)c1ccc(nc1)c1ccc(cn1)C(=O)[O-].[Th]": (5.34946, 4.5768, "Th"),
    "[O-]C(=O)c1ccc(o1)C(=O)[O-].[Pr]": (5.86694, 4.44854, "Pr"),
    "[O-]C(=O)c1ccc(o1)C(=O)[O-].[Zn]": (5.7396, 4.59935, "Zn"),
    "[O-]C(=O)c1ccc(s1)C(=O)[O-].[O]P(=O)[O].[Zn]": (9.27985, 8.95188, "Zn"),
    "[O-]C(=O)c1ccc2c(c1)[nH]c(n2)c1cccnc1.[Zn]": (6.21817, 5.22361, "Zn"),
    "[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2c1ccc(cc1)c1ccc(cc1)n1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-].[Zn][Zn]": (22.41586, 11.98152, "Zn"),
    "[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2c1ccccc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (10.48991, 3.42602, "Zn"),
    "[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2Cc1ccc(cc1)Cn1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-].[Zn].n1ccc(cc1)C=Cc1ccncc1": (6.06834, 2.89795, "Zn"),
    "[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2Cc1ccc(cc1)Cn1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-].[Zn].n1ccc(cc1)c1ccncc1": (4.50717, 2.85634, "Zn"),
    "[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (10.53539, 8.97079, "Zr"),
    "[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].[OH2][Eu]O[Eu][OH2]": (4.54687, 3.96791, "Eu"),
    "[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].[Yb]": (4.44624, 2.68084, "Yb"),
    "[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].[Zn].n1ccc(cc1)c1ccc(cc1)N(c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1": (5.88419, 4.79322, "Zn"),
    "[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].[Zn][Zn]": (5.6888, 4.41398, "Zn"),
    "[O-]C(=O)c1ccc2c(c1)ccc(n2)C(=O)[O-].[Zn]": (4.96882, 3.23985, "Zn"),
    "[O-]C(=O)c1ccc2-c3c(Cc2c1)cc(cc3)C(=O)[O-].[Zn][O]1([Zn])[Zn]23[Zn]1([O]2([Zn])[Zn])[O]3([Zn])[Zn]": (14.46267, 10.01487, "Zn"),
    "[O-]C(=O)c1ccc2-c3c(Cc2c1)cc(cc3)C(=O)[O-].[Zn][OH]([Zn]([OH]([Zn])[Zn])[OH]([Zn])[Zn])[Zn]": (8.10628, 4.95434, "Zn"),
    "[O-]C(=O)c1ccc2-c3c(Cc2c1)cc(cc3)C(=O)[O-].[Zn][OH]([Zn][OH]([Zn])[Zn])[Zn]": (14.37106, 10.64638, "Zn"),
    "[O-]C(=O)c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(=O)[O-].[Zn].n1ccc(cc1)OCC(COc1ccncc1)(COc1ccncc1)COc1ccncc1": (4.90477, 2.92555, "Zn"),
    "[O-]C(=O)c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(=O)[O-])(c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(=O)[O-])c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(=O)[O-].[O]12[Hf]34[O]5[Hf]62[O]2[Hf]71[O]4[Hf]14[O]3[Hf]35[O]6[Hf]2([O]71)[O]43": (19.21939, 8.37152, "Hf"),
    "[O-]C(=O)c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(=O)[O-])(c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(=O)[O-])c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (17.33084, 7.53875, "Zr"),
    "[O-]C(=O)c1cccc(c1)C(=O)[O-].[Zn]": (4.70973, 3.97539, "Zn"),
    "[O-]C(=O)c1cccc(c1)C(=O)[O-].[Zn].n1ccc(cc1)N1CCN(CC1)c1ccncc1": (6.92787, 5.95334, "Zn"),
    "[O-]C(=O)c1cccc(c1)C(=O)[O-].[Zn][OH]1[Zn][OH]([Zn]21[OH]([Zn])[Zn][OH]2[Zn])[Zn]": (7.34133, 6.06347, "Zn"),
    "[O-]C(=O)c1cccc(c1)c1ccncc1.[Zn]": (7.69017, 6.24677, "Zn"),
    "[O-]C(=O)c1cccc(c1)OCc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn][OH]1[Zn][OH]([Zn]1)[Zn]": (5.07212, 3.5354, "Zn"),
    "[O-]C(=O)c1ccncc1N.[Zn]": (7.5175, 7.32289, "Zn"),
    "[O-]C(=O)c1cnc(nc1)c1ncc(cn1)C(=O)[O-].[O]12[Eu]34[O]5[Eu]62[O]2[Eu]71[O]4[Eu]14[O]3[Eu]35[O]6[Eu]2([O]71)[O]43": (14.28983, 7.23189, "Eu"),
    "[O-]C(=O)c1cncc(c1)C(=O)[O-].[Pr]": (4.97189, 3.79936, "Pr"),
    "[O-]C(=O)c1cncc(c1)C(=O)[O-].[Zn]": (6.10528, 5.07966, "Zn"),
    "[O-]C(=O)c1cncc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (6.77542, 5.74655, "Zn"),
    "[O-]C(=O)c1ncc(nc1)C(=O)[O-].[Y]": (5.86101, 5.26698, "Y"),
    "[O-]C(=O)CC(=O)[O-].[Zn]": (4.60833, 3.89453, "Zn"),
    "[O-]C(=O)CCC(C(=O)[O-])NC(=O)N.[Zn].n1ccc(cc1)C=Cc1ccncc1": (5.9439, 5.18128, "Zn"),
    "[O-]C(=O)CCCC(=O)[O-].[O-]C(=O)c1cnccc1C(=O)[O-].[OH2][Tb]": (7.28222, 5.74426, "Tb"),
    "[O-]C(=O)CCCC(=O)[O-].[O-]C(=O)c1cnccc1C(=O)[O-].[Sm]": (7.3842, 5.83467, "Sm"),
    "[O-]C(=O)CCP(=O)([O])[O].[V]": (4.18946, 2.64927, "V"),
    "[O-]C(=O)CN(C1=NC(=[N]=C([N]1)N1CCN(CC1)C1=NC(=[N]=C([N]1)N(CC(=O)[O-])CC(=O)[O-])N(CC(=O)[O-])CC(=O)[O-])N(CC(=O)[O-])CC(=O)[O-])CC(=O)[O-].[Zn].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (4.84734, 3.33854, "Zn"),
    "[O-]C(=O)CN(CC(=O)[O-])CCCN(CC(=O)[O-])CC(=O)[O-].[OH2][La]": (4.2387, 3.0724, "La"),
    "[O-]C(=O)CN1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)CC(=O)[O-].[Zn].n1ccc(cc1)C=Cc1ccncc1": (5.50326, 4.37361, "Zn"),
    "[O-]C(=O)COc1ccc(cc1)N(CC(=O)[O-])CC(=O)[O-].[Sm]": (4.63496, 3.87226, "Sm"),
    "[O-]C=O.[Zn]": (4.64754, 3.60747, "Zn"),
    "[O]C1=C[CH]N(C=C1)Cc1c2ccccc2c(c2c1cccc2)Cn1ccc(=O)cc1.[O]S(c1cccc2c1cccc2S([O])([O])[O])([O])[O].[Zn]": (5.6268, 3.58472, "Zn"),
    "[O]c1cc(cc(c1[O])[O])C1=C2C=CC(=N2)C=c2ccc(=C(C3=NC(=Cc4[nH]c1cc4)C=C3)c1cc([O])c(c(c1)[O])[O])[nH]2.[Zr]": (5.14326, 4.66746, "Zr"),
    "[O]c1cc(ccc1[O])C1=NC(=[N]=C([N]1)c1ccc(c(c1)[O])[O])c1ccc(c(c1)[O])[O].[Ti]": (9.25126, 4.2936, "Ti"),
    "[O]N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)[O].[Sm]": (7.15715, 6.77952, "Sm"),
    "[O]P(=O)(C[NH](CP(=O)([O])[O])Cc1ccc(cc1)S([O])([O])[O])[O].[Pb]": (3.34978, 3.00336, "Pb"),
    "[O]P(=O)(O)[O].[Zn].n1ccc(cc1)c1ccc(cc1)c1ccncc1": (5.20335, 4.624, "Zn"),
    "[O]S(c1cccc2c1cccc2S([O])([O])[O])([O])[O].[Pr]": (4.32306, 2.50132, "Pr"),
    "[S][Cd][S].n1ccc(cc1)c1cc(c2ccncc2)c(cc1c1ccncc1)c1ccncc1": (11.07774, 9.25679, "Cd"),
    "[Zn].c1ncn(c1)c1ccc(cc1)N(c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1": (8.48692, 7.9488, "Zn"),
    "[Zn].n1ccc(cc1)C=Cc1ccncc1": (4.85029, 3.71599, "Zn"),
    "[Zn].n1ccc(cc1)Sc1ccncc1": (4.15296, 3.04527, "Zn,Si"),
    "[Zn].n1ccncc1": (3.94533, 2.93868, "Zn,Si"),
    "[Zn][OH][Zn].c1ncn(c1)c1ccc(cc1)N(c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1": (11.94829, 11.34475, "Zn"),
    "[Zn]O[Zn].c1ncn(c1)c1ccc(cc1)N(c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1": (7.35718, 3.96602, "Zn"),
    "Brc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cr][O]([Cr])[Cr].[O-]C(=O)c1ccncc1.[Zn][Zn]": (11.79013, 6.60797, "Zn,Cr"),
    "Brc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (7.80637, 6.90024, "Zn"),
    "Brc1cc2[CH]N3O[B]4(ON5[Co]6783[O]3c2c(c1)[CH]N1[Co]29%103[O]7c3c([CH]5)cc(cc3[CH]N%10O[B](O1)(ON9[CH]c1c([O]82)c([CH]N6O4)cc(c1)Br)c1ccc(cc1)C(=O)[O-])Br)c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (13.57581, 11.0805, "Zn,Co"),
    "C([NH2]Cc1cccnc1)CCC[NH2]Cc1cccnc1.[Co].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (6.55261, 5.37267, "Co"),
    "C(Cc1ccncc1)Cc1ccncc1.[Cd].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-]": (5.59392, 3.363, "Cd"),
    "C(Cc1ccncc1)Cc1ccncc1.[Co].[O-]C(=O)c1ccc2c(c1)c1cc(ccc1n2Cc1ccc(cc1)Cn1c2ccc(cc2c2c1ccc(c2)C(=O)[O-])C(=O)[O-])C(=O)[O-]": (5.31366, 3.51306, "Co"),
    "C(Cc1ccncc1)Cc1ccncc1.[Cu].[O-]C(=O)c1cc(OCC=CCOc2cc(cc(c2)C(=O)[O-])C(=O)[O-])cc(c1)C(=O)[O-]": (5.4856, 3.48036, "Cu"),
    "C(Cc1ccncc1)Cc1ccncc1.[Cu][Cu].[O-]C(=O)CCCC(=O)[O-]": (6.2648, 5.55557, "Cu"),
    "C(Cc1ccncc1)Cc1ccncc1.[O-]C(=O)CN(C1=NC(=[N]=C([N]1)N(CC(=O)[O-])CC(=O)[O-])N1CCN(CC1)C1=NC(=[N]=C([N]1)N(CC(=O)[O-])CC(=O)[O-])N(CC(=O)[O-])CC(=O)[O-])CC(=O)[O-].[Zn]": (6.15089, 4.65972, "Zn"),
    "C(Cc1ccncc1)Cc1ccncc1.CCOc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (4.96581, 3.72779, "Zn"),
    "C(Cn1cncc1)CCn1cncc1.[O-]C(=O)c1cc2c(s1)cc1c(c2)sc(c1)C(=O)[O-].[Zn]": (5.16535, 3.80955, "Zn"),
    "C(Cn1cnnn1)Cn1cnnn1.[Cu]": (4.90578, 3.35404, "Cu"),
    "C(Oc1cc2Cc3cc(OCCn4cncc4)c(cc3Cc3c(Cc2cc1OCCn1cncc1)cc(OCCn1cncc1)c(c3)OCCn1cncc1)OCCn1cncc1)Cn1cncc1.[Cd].[O-]C(=O)c1cccc(c1)C(=O)[O-]": (7.76646, 4.38395, "Cd"),
    "C[C](c1cccnc1)[N][N][C](c1cccnc1)C.[O-]C(=O)c1ccc(cc1)S(=O)(=O)c1ccc(cc1)C(=O)[O-].[Zn][Zn]": (5.00855, 3.32708, "Zn"),
    "C[C]1N=NC(=C1c1ccc(cc1)C(=O)[O-])C.[O-]C(=O)c1ccc(cc1)c1c(C)[n-][nH]c1C.[Zn]": (4.554, 3.89796, "Zn"),
    "C[Si]1(CCc2cccnc2)O[Si](C)(CCc2cccnc2)O[Si](O[Si](O1)(C)CCc1cccnc1)(C)CCc1cccnc1.I[Cu]12[Cu]3([Cu]1([Cu]23I)I)I": (4.15822, 3.45765, "Cu,Si"),
    "C=CCOc1cc(C(=O)[O-])c(cc1C(=O)[O-])OCC=C.[Ce]": (5.68837, 4.11978, "Ce"),
    "C=CCOc1cc(C(=O)[O-])c(cc1C(=O)[O-])OCC=C.[Nd]": (5.68336, 4.09122, "Nd"),
    "C1=C[C]2C(=c3c(=C2[C](c2ccncc2)c2ccncc2)cccc3)C=C1.[C]#N.[Cu].n1ccc(cc1)[C](C1=c2ccccc2=C2C1=CC=C[CH]2)c1ccncc1": (4.51819, 3.42821, "Cu"),
    "C1=C[N]C=N1.C1=N[CH]C=N1.[Zn]": (6.29616, 5.28591, "Zn"),
    "C1=N[CH]N([N]1)Cc1ccc(cc1)Cn1cncn1.N1=C[N]N([CH]1)Cc1ccc(cc1)CN1[N]C=N[CH]1.[Co].[O-]C(=O)c1ccc(cc1)S(=O)(=O)c1ccc(cc1)C(=O)[O-]": (4.87338, 4.29506, "Co"),
    "C1=N[N]C=N1.[N]1=CN=NC=1.[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-].[Zn]": (4.81423, 2.47825, "Zn"),
    "C1=N[N]C=N1.[N]1=CN=NC=1.[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].[Zn]": (5.17865, 3.17816, "Zn"),
    "C1=NC=C2C(=[N]=C[N]2)[N]1.[Zn]": (4.86043, 4.2216, "Zn"),
    "C1=NC=C2C(=[N]=C[N]2)[N]1.C1=Nc2c([N]1)ncnc2.[Zn]": (7.52222, 4.33825, "Zn"),
    "C1=NC=C2C(=CN=N2)[CH]1.N1=C[C]2C(=CN=N2)C=C1.[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn]": (4.81973, 4.21277, "Zn"),
    "C1=NC=C2C(=NC=N2)[N]1.[Zn]": (4.80398, 4.2195, "Zn"),
    "C1CN2CCN1CC2.[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (4.66108, 3.86054, "Co"),
    "C1CN2CCN1CC2.[Ni].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (4.30395, 3.76836, "Ni"),
    "C1CN2CCN1CC2.[Ni].[O-]C(=O)c1ccc(s1)C(=O)[O-]": (4.27518, 3.53473, "Ni"),
    "C1CN2CCN1CC2.[O-]C(=O)c1cc(C)c(cc1C)C(=O)[O-].[Zn][Zn]": (7.26135, 5.92834, "Zn"),
    "C1CN2CCN1CC2.[O-]C(=O)c1ccc(s1)C(=O)[O-].[Zn][Zn]": (7.81562, 5.42195, "Zn"),
    "C1CN2CCN1CC2.I[Cu]12[Cu]3([Cu]1([Cu]23I)I)I.[Cu].c1cc(cc(c1)C1=Nc2c([N]1)cccc2)C1=Nc2c([N]1)cccc2": (8.09458, 6.64328, "Cu"),
    "C1CN2CCN1CC2.Oc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Co]": (4.31235, 2.86438, "Co"),
    "CC([S])(C)C.[Ag][Ag][Ag][Ag][Ag][Ag].[O-]C(=O)c1c(F)c(F)c(c(c1F)F)C(=O)[O-]": (9.76235, 8.74983, "Ag"),
    "CC(=N[N]C(=O)c1ccncc1)C(=N[N]C(=O)c1ccncc1)C.[Cd]": (13.51891, 10.1478, "Cd"),
    "CC(=N[N]C(=S)N)c1cc(cc(c1)C(=N[N]C(=S)N)C)C(=N[N]C(=S)N)C.[Cu]": (9.50808, 7.56799, "Cu"),
    "CC(=NN=C(c1ccncc1)C)c1ccncc1.[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn][Zn]": (4.83378, 3.74001, "Zn"),
    "CC(=NN=C(c1ccncc1)C)c1ccncc1.C[C](c1ccncc1)[N][N][C](c1ccncc1)C.[Cd].[O]S(c1cccc(c1)S([O])([O])[O])([O])[O]": (4.95457, 3.98467, "Cd"),
    "CC(=O)N(C)C.[Cd].[O-]C(=O)c1c(C)c(C)c(c(c1C)C)B(c1c(C)c(C)c(c(c1C)C)C(=O)[O-])c1c(C)c(C)c(c(c1C)C)C(=O)[O-]": (7.60747, 3.9467, "Cd"),
    "CC(C(=O)[O-])NCc1ccncc1.[Zn]": (5.73481, 5.39718, "Zn"),
    "CC(C(=O)Nc1cc(ccc1C(=O)[O-])C(=O)[O-])O.[Cd]": (11.50272, 8.4606, "Cd"),
    "CC(C1=Nc2c([N]1)cccc2)[O].[O-]C(=O)C1CCC(C1(C)C)(C)C(=O)[O-].[Zn]": (5.55465, 3.62286, "Zn"),
    "CC(C1=NN=C([N]1)C(C)C)C.[Cu]": (9.39866, 8.82379, "Cu"),
    "CC(C1=NN=C([N]1)C(O)C)O.[Cu]": (11.01739, 9.30306, "Cu"),
    "CC(c1cc2Sc3cc(cc(c3[O])Sc3cc(cc(Sc4c(c(Sc(c1)c2[O])cc(c4)C(C)(C)C)[O])c3[O])C(C)(C)C)C(C)(C)C)(C)C.[Ni].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cncnc1.[O]S(=O)(=O)[O]": (7.26101, 4.11236, "Ni"),
    "CC(N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)C(C(=O)[O-])C)C(=O)[O-].[Cd].n1ccc(cc1)c1ccncc1": (6.1592, 5.62314, "Cd"),
    "CC(N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)C(C(=O)[O-])C)C(=O)[O-].O=C1N(c2ccncc2)C(=O)c2c3c1ccc1c3c(cc2)C(=O)N(C1=O)c1ccncc1.[Cd]": (5.4861, 4.07609, "Cd"),
    "Cc1[nH][n-]c(c1c1c(C)[n-][nH]c1C)C.[Cd].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (5.87576, 4.00855, "Cd"),
    "Cc1[nH][n-]c(c1c1c(C)[n-][nH]c1C)C.[Fe][OH][Fe].[O-]C(=O)c1cc(C(=O)[O-])c(cc1C(=O)[O-])C(=O)[O-]": (9.27312, 7.76131, "Fe"),
    "Cc1[nH][n-]c(c1c1c(C)[n-][nH]c1C)C.[Mn].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (9.90635, 2.42508, "Mn"),
    "Cc1[nH][n-]c(c1c1c(C)[n-][nH]c1C)C.[Ni].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (9.03942, 2.40726, "Ni"),
    "CC1=C(C(=N[N]1)C)N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)C1=C(C)N=N[C]1C.CC1=NN=C([C]1N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)C1=C(C)[N]N=C1C)C.C[C]1N=NC(=C1N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)[C]1C(=NN=C1C)C)C.[Cu].[Cu][Cu]": (8.035, 4.37134, "Cu"),
    "CC1=NC=C[N]1.CC1=N[CH]C=N1.[Zn]": (11.38092, 3.3255, "Zn"),
    "CC1=NN=C([C]1N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)C1=C(C)[N]N=C1C)C.CC1=N[N]C(=C1N1C(=O)c2ccc3c4c2c(C1=O)ccc4C(=O)N(C3=O)C1=C(C)[N]N=C1C)C.O=C1N([C]2C(=NN=C2C)C)C(=O)c2c3c1ccc1c3c(cc2)C(=O)N(C1=O)[C]1C(=NN=C1C)C.[Cu].[Cu][Cu]": (7.51719, 4.17605, "Cu"),
    "CC1=NN=C([N]1)C.[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (9.25518, 5.85382, "Zn"),
    "CC1=NN=C([N]1)C.[O-]C(=O)c1cc(cc(c1)C1=N[N]N=N1)C(=O)[O-].[Zn]": (9.45114, 6.4791, "Zn"),
    "CC1=NN=C([N]1)C.[O-]C(=O)c1cc(cc(c1)C1=NN=N[N]1)C(=O)[O-].[Zn]": (8.59169, 5.65808, "Zn"),
    "CC1=NN=C([N]1)CC1=[N]=C(N=N1)C.CC1=[N]=C(N=N1)CC1=[N]=C(N=N1)C.[Cu]": (6.31761, 5.94846, "Cu"),
    "CC1=NN=C[N]1.[O-]C(=O)c1sc2c(c1C)c(c(s2)C(=O)[O-])C.[Zn].[Zn][Zn]": (10.63464, 9.46333, "Zn"),
    "Cc1c(c2ccc(cc2)C(=O)[O-])c(C)c(c(c1c1ccc(cc1)C(=O)[O-])C)c1ccc(cc1)C(=O)[O-].[In].[OH]": (10.02424, 5.84722, "In"),
    "Cc1c(cc(c(c1c1c(C)c(cc(c1O)c1ccc(c2c1cccc2)C(=O)[O-])c1ccc(c2c1cccc2)C(=O)[O-])O)c1ccc(c2c1cccc2)C(=O)[O-])c1ccc(c2c1cccc2)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]3[Zr]1389%10[O]%114[Zr]4%12%13%145[O]56[Zr]6%15%162([O]71[O]86[Zr]12[O]%10[Zr]6([O]3%114)[O]%13[Zr]([O]%125%15)([O]%161)[O]26)[O]9%14": (8.22493, 6.38072, "Zr"),
    "Cc1cc(C(=O)[O-])c(c(c1C)c1c(C)c(C)cc(c1O)C(=O)[O-])O.[Zn][O]([Zn])([Zn])[Zn]": (8.13406, 4.29439, "Zn"),
    "Cc1cc(C)c(c(c1C)B(c1c(C)c(C)c(c(c1C)C)C(=O)[O-])c1c(C)c(C)c(c(c1C)C)C(=O)[O-])C.[Zn]": (7.15079, 6.5153, "Zn"),
    "Cc1cc(C2=C[N]N=C2)c(cc1[C]1C=NN=C1)C.[Co]": (4.23296, 3.57101, "Co"),
    "Cc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cr][O]([Cr])[Cr].[O-]C(=O)c1ccncc1.[Zn][Zn]": (11.32485, 7.62193, "Zn,Cr"),
    "Cc1cc(cc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cu][Cu]": (11.30481, 6.66246, "Cu"),
    "Cc1cc(cc(c1c1ccncc1)C)c1nc2c(s1)nc(s2)c1cc(C)c(c(c1)C)c1ccncc1.[O-]C(=O)c1ccc(s1)C(=O)[O-].[Zn][Zn]": (6.0961, 4.34676, "Zn"),
    "Cc1cc(ccc1c1ccc(cc1C)C(=O)[O-])C(=O)[O-].[O]12[Th]34[O]5[Th]62[O]2[Th]71[O]4[Th]14[O]3[Th]35[O]6[Th]2([O]71)[O]43": (15.55311, 14.01621, "Th"),
    "Cc1cc(ccc1c1ccc(cc1C)C(=O)[O-])C(=O)[O-].[O]12[U]34[O]5[U]62[O]2[U]71[O]4[U]14[O]3[U]35[O]6[U]2([O]71)[O]43": (15.13285, 14.00013, "U"),
    "Cc1cc(ccc1c1ccc(cc1C)C(=O)[O-])C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (14.79057, 13.9519, "Zr"),
    "Cc1cc(ccc1n1cnnc1)c1ccc(c(c1)C)n1cnnc1.[Cd].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (5.20043, 3.16992, "Cd"),
    "Cc1cnccc1c1cccc(c1)C(=O)[O-].[Cu]": (7.13716, 5.1592, "Cu"),
    "Cc1nc(C)c(nc1C)C.[Ag]1[Ag][Ag][Ag][Ag][Ag]1.[O-]C(=O)c1cc(cc(c1)N(=O)=O)C(=O)[O-]": (5.17559, 4.77124, "Ag"),
    "Cc1nccn1c1ccc(cc1)n1ccnc1C.[Cd].[O-]C(=O)c1ccc(cc1)C(c1ccc(cc1)C(=O)[O-])N1[N]C=N[CH]1": (9.07712, 6.4111, "Cd"),
    "Cc1nccn1c1ncnc(c1)n1ccnc1C.[Co][Co].[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-]": (4.25065, 2.91668, "Co"),
    "Cc1nccn1Cc1c2ccccc2c(c2c1cccc2)Cn1ccnc1C.[Cd].[O-]C(=O)c1ccc(c(c1)N)C(=O)[O-]": (5.08472, 3.22525, "Cd"),
    "Cc1nccn1Cc1c2ccccc2c(c2c1cccc2)Cn1ccnc1C.[Cd].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (5.78772, 4.02753, "Cd"),
    "Cc1nccn1CCCn1ccnc1C.[Co][Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (5.14896, 3.62698, "Co"),
    "Cc1nccn1CCCn1ccnc1C.[Cu].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (4.1714, 3.40897, "Cu"),
    "Cc1ncn(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Co][Co]": (4.45932, 2.75223, "Co"),
    "Cc1ncn(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cu][Cu]": (4.386, 2.77373, "Cu"),
    "Cc1sc(cc1C1=C(c2cc(sc2C)c2ccncc2)C(C(C1(F)F)(F)F)(F)F)c1ccncc1.[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn]": (9.58799, 9.15532, "Zn"),
    "CCC(Oc1cc(c(cc1c1ccncc1)OC(CC)C)c1ccncc1)C.[Cd]": (4.68036, 2.65083, "Cd"),
    "CCC1(CC)c2cc(ccc2-c2c1c1-c3ccc(cc3C(c1c1-c3c(C(c21)(CC)CC)cc(cc3)C(=O)[O-])(CC)CC)C(=O)[O-])C(=O)[O-].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (19.35863, 7.23576, "Zn"),
    "CCC1=NC(=C([N]1)C)C=NC1CCCCC1N=CC1=C(C)[N]C(=N1)CC.CCC1=N[C](C(=N1)C)C=NC1CCCCC1N=CC1=C(C)[N]C(=N1)CC.CCC1=N[C](C(=N1)C=NC1CCCCC1N=C[C]1N=C(N=C1C)CC)C.[Zn]Br": (7.24464, 6.56289, "Zn"),
    "CCc1sc(cc1C1=C(c2cc(sc2CC)c2ccncc2)C(C(C1(F)F)(F)F)(F)F)c1ccncc1.[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn]": (6.24664, 3.23188, "Zn"),
    "CCCC1(CCC)c2cc(ccc2-c2c1c1-c3ccc(cc3C(c1c1-c3c(C(c21)(CCC)CCC)cc(cc3)C(=O)[O-])(CCC)CCC)C(=O)[O-])C(=O)[O-].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])([Zn])[Zn]": (16.25601, 6.43045, "Zn"),
    "CCCC1c2cc(C(CCC)c3cc(C(c4cc(C(c5cc1c([O])c(c5[O])[O])CCC)c([O])c(c4[O])[O])CCC)c(c(c3[O])[O])[O])c(c(c2[O])[O])[O].[Mg].[O]CCOCC[O]": (11.55243, 4.53412, "Mg"),
    "CCCCCCOc1cc(C=Cc2ccncc2)c(cc1C=Cc1ccncc1)OCCCCCC.[O-]C(=O)c1ccc(cc1)S(=O)(=O)c1ccc(cc1)C(=O)[O-].[Zn][Zn]": (5.3698, 3.52897, "Zn"),
    "CCCOc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn].n1ccc(cc1)c1ccncc1": (4.6791, 3.61937, "Zn"),
    "CCN(C1=C[CH]C2=C(c3c(OC2=C1)cc(cc3)N(CC)CC)c1ccccc1C(=O)[O-])CC.CCN(C1=C[C]2C(=C(c3c(O2)cc(cc3)N(CC)CC)c2ccccc2C(=O)[O-])C=C1)CC.Cc1cc(c2cc(cc(c2)C(=O)[O-])C(=O)[O-])c(c(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])N.[Zn]": (7.0133, 4.3484, "Zn"),
    "CCOc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (6.98194, 5.60229, "Zn"),
    "Cl[C]1C(=O)C(=O)[C](C(=O)C1=O)Cl.[Er]": (5.28005, 3.47451, "Er"),
    "Cl[C]1C(=O)C(=O)[C](C(=O)C1=O)Cl.[Fe].[O]S(=O)(=O)[O]": (7.95164, 6.60155, "Fe"),
    "Cl[Cd]Cl.c1cc(CN(Cc2cccc(c2)Cn2cncc2)Cc2cccc(c2)Cn2cncc2)cc(c1)Cn1cncc1": (5.68146, 2.54273, "Cd"),
    "Cl[Cd]Cl.n1ccc(cc1)c1ccc(cc1)C(=C(c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1": (7.11368, 5.92665, "Cd"),
    "Cl[Co].[Co].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (5.16671, 2.46687, "Co"),
    "Cl[Co].[Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (5.65303, 3.7818, "Co"),
    "Cl[Cu].[Cu][Cu].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cncnc1": (6.99899, 4.36761, "Cu"),
    "Cl[Cu][O]([Cu](Cl)(Cl)Cl)([Cu](Cl)Cl)[Cu].Cl[Cu][O]([Cu](Cl)Cl)([Cu](Cl)Cl)[Cu]Cl.[O-]C(=O)c1ccncc1.[Sc][O]1[Sc][O]([Sc]1)[Sc]": (10.95157, 6.03297, "Cu,Sc"),
    "Cl[Cu]Cl.n1ccc(cc1)c1ccc(cc1)C(=C(c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1": (7.39096, 6.21369, "Cu"),
    "Cl[Fe][O]([Fe]Cl)([Fe]Cl)([Fe]Cl)([Fe]Cl)[Fe]Cl.[Fe].[O]CC(c1ccncc1)(C[O])C[O]": (6.95143, 4.41404, "Fe"),
    "Cl[Fe]Cl.[Fe].n1ccc(cc1)c1cc(nc(c1)c1ccccn1)c1ccccn1": (7.1229, 4.47055, "Fe"),
    "Cl[Mn].[Mn].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (5.63922, 4.18387, "Mn"),
    "Cl[Mn]Cl.c1ncn(c1)c1ccc(cc1)N(c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1": (7.41556, 5.52, "Mn"),
    "Cl[Mn]Cl.n1ccc(cc1)c1ccc(cc1)C(=C(c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1)c1ccc(cc1)c1ccncc1": (7.38868, 6.24423, "Mn"),
    "Cl[Ni]Cl.n1ccc(cc1)Nc1ccncc1": (6.35552, 4.69168, "Ni"),
    "Cl[Zn].[O-]C(=O)c1ccc(cc1)c1cc(nc(c1)c1ccncc1)c1ccncc1": (4.66266, 3.90863, "Zn"),
    "Cl[Zn]Cl.c1ccc2c(c1)n(cn2)c1cc(cc(c1)n1cnc2c1cccc2)n1cnc2c1cccc2": (4.433, 3.76253, "Zn"),
    "Clc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (8.21835, 7.31824, "Zn"),
    "Clc1nccnc1Cl.[Cu][Cu].[O-]C(=O)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (12.61119, 11.43871, "Cu"),
    "CN(c1c(F)c(F)c(c(c1F)F)C1=C2C=CC(=C(c3ccc(cc3)n3ccnc3)C3=NC(=C(C4=CC=C(C(=C5N=C1C=C5)c1ccc(cc1)n1ccnc1)[N]4)c1c(F)c(F)c(c(c1F)F)N(C)C)C=C3)[N]2)C.[Fe]": (14.63467, 10.9264, "Fe"),
    "CN(c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C.[Cu][Cu]": (6.65873, 6.2066, "Cu"),
    "COC(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cu][Cu]": (6.55349, 4.71526, "Cu"),
    "COc1cc(c2ccc(cc2)C(=O)[O-])c(cc1OC)c1ccc(cc1)C(=O)[O-].[Co].[O-]C=O.n1ccc(cc1)NNc1ccncc1": (5.3519, 3.96561, "Co"),
    "COc1cc(c2ccc(cc2)C(=O)[O-])c(cc1OC)c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)NNc1ccncc1": (4.66367, 3.73123, "Zn"),
    "COc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cr][O]([Cr])[Cr].[O-]C(=O)c1ccncc1.[Zn][Zn]": (11.54376, 6.59796, "Zn,Cr"),
    "COc1cc2Cc3cc(c4ccc(cc4)C(=O)[O-])c(cc3Cc3c(Cc2cc1c1ccc(cc1)C(=O)[O-])cc(OC)c(c3)c1ccc(cc1)C(=O)[O-])OC.[Co]": (6.5579, 5.55083, "Co"),
    "COc1ccc(cc1C(=O)[O-])c1ccc(c(c1)C(=O)[O-])OC.[La]": (4.90147, 3.39592, "La"),
    "COc1cccc(c1[O])[CH][N]NC(=O)c1ccc(cc1)NC(=O)c1ccncc1.[Cd].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (6.82055, 4.25216, "Cd"),
    "COc1cccc(c1[O])[CH][N]NC(=O)c1cccnc1.[Cd].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (6.99462, 3.97878, "Cd"),
    "F[Cd].[Cd].[O-]C(=O)c1ccc(cc1)C(=O)[O-].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (9.39189, 4.95806, "Cd"),
    "F[Co].[Co].[O-]C(=O)c1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[O]S(=O)(=O)[O].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (8.18299, 7.27755, "Co"),
    "F[Fe](F)(F)F.F[Fe](F)F.[Fe].[O-]C(=O)c1ccc(o1)C(=O)[O-]": (5.81881, 4.18743, "Fe"),
    "F[Ni].[O-]C(=O)c1ccc(cc1)C1=NN=N[N]1.n1ccc(cc1)c1ccncc1": (6.8055, 6.19081, "Ni"),
    "F[Np]123O[Np]4O[Np]56[O]3[Np]3O[Np]7(O1)(F)O[Np]18(F)O[Np]9[O]7[Np](O3)(O6)O[Np]3([O]8[Np]6O[Np]7(O1)(O[Np]18O[Np]%10(O2)[O]4[Np]2(O5)(F)O[Np](O%10)[O]1[Np]1(O2)(F)O[Np](O8)[O]7[Np](O1)(O6)O3)F)O9.[O-]C(=O)c1ccc(cc1)c1cc(c2ccc(cc2)C(=O)[O-])c(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (11.81221, 6.17137, "Np"),
    "F[Tb].F[Tb]F.[O-]C(=O)c1ccc(cc1)C(=O)[O-].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Tb]": (9.97794, 9.08835, "Tb"),
    "F[Zn].[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn].n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (8.59472, 4.47227, "Zn"),
    "F[Zr](F)F.F[Zr]F.[O]P(=O)(c1ccc(cc1)C(c1ccc(cc1)P(=O)([O])[O])(c1ccc(cc1)P(=O)([O])[O])c1ccc(cc1)P(=O)([O])[O])[O]": (12.00356, 7.22815, "Zr"),
    "FC(C1=C(c2ccc(cc2)C2=C(N=N[C]2C(F)(F)F)C(F)(F)F)C(=N[N]1)C(F)(F)F)(F)F.FC(C1=NN=C([C]1c1ccc(cc1)C1=C([N]N=C1C(F)(F)F)C(F)(F)F)C(F)(F)F)(F)F.[Co].[OH]": (3.40112, 2.79036, "Co"),
    "FC(c1cc(cc(c1)C1=C[N]N=C1)C1=C[N]N=C1)(F)F.FC(c1cc(cc(c1)C1=C[N]N=C1)[C]1C=NN=C1)(F)F.FC(c1cc(cc(c1)[C]1C=NN=C1)[C]1C=NN=C1)(F)F.[Ni]12[O]34[Ni]5[O]62[Ni]2[O]71[Ni]4[O]14[Ni]3[O]35[Ni]6[O]2([Ni]71)[Ni]43": (5.92744, 3.68774, "Ni"),
    "Fc1cc([C]2C=NN=C2)c(cc1[C]1C=NN=C1)F.[Co]": (9.91946, 9.58016, "Co"),
    "Fc1cncc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cu][Cu]": (4.38065, 2.79948, "Cu"),
    "I[Cu]([Cu][Cu][Cu](I)I)I.[Cu][Cu](I)I.c1ccc(cn1)C#Cc1cc(C#Cc2cccnc2)cc(c1)C#Cc1cccnc1": (5.36632, 4.23886, "Cu"),
    "I[Cu][Cu]I.[Cu][Cu](I)I.c1ccc(cn1)C#Cc1cc(C#Cc2cccnc2)cc(c1)C#Cc1cccnc1": (4.80042, 4.04778, "Cu"),
    "I[Cu][Cu]I.[Cu][Cu].[O-]C(=O)c1ccc(cc1)c1cncnc1": (15.26082, 10.84317, "Cu"),
    "I[Cu][Cu]I.[Eu].[O-]C(=O)c1ccncc1": (6.92453, 5.91349, "Cu,Eu"),
    "I[Cu][Cu]I.[O]CC(c1ccncc1)(C[O])C[O].[Sb]": (9.81656, 8.96763, "Cu,Sb"),
    "I[Cu]1(I)[Cu][Cu]1(I)I.I[Cu]1[Cu]([Cu]1(I)I)(I)I.[Ce].[O-]C(=O)c1ccc(cc1)N1[CH]C=C(C=C1)c1ccncc1": (5.52909, 3.39426, "Ce,Cu"),
    "I[Cu]12[Cu]3[Cu]1[Cu]23(I)(I)I.N#CC1=C(C#N)[N]C=N1": (6.57032, 4.77193, "Cu"),
    "I[Zn]I.n1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccncc1)c1ccncc1": (8.18232, 7.42372, "Zn"),
    "Ic1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (7.41681, 6.42624, "Zn"),
    "N#C[C](c1ccc(cc1)[C](C#N)C#N)C#N.[Rh][Rh]": (5.28665, 3.62054, "Rh"),
    "N#C[C]1C(=O)[C]([O])C(=C(C1=O)[O])Cl.[Fe]": (7.82632, 5.83106, "Fe"),
    "N#Cc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Co]": (6.44904, 4.58464, "Co"),
    "N1[CH]C=C(C=C1)C1=C2C=CC(=C(C3=NC(=C(C4=CC=C(C(=C5N=C1C=C5)c1ccncc1)[N]4)C1=C[CH]NC=C1)C=C3)c1ccncc1)[N]2.[Co]": (6.53077, 4.96028, "Co"),
    "N1=C[C](C=N1)c1ccc(cc1)C1=C[N]N=C1.[N]1N=CC(=C1)c1ccc(cc1)C1=C[N]N=C1.[Ni]12[O]34[Ni]5[O]62[Ni]2[O]71[Ni]4[O]14[Ni]3[O]35[Ni]6[O]2([Ni]71)[Ni]43": (14.69154, 5.16822, "Ni"),
    "N1=C[C](C=N1)c1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccc(cc1)C1=C[N]N=C1)c1ccc(cc1)C1=C[N]N=C1.N1=C[C](C=N1)c1ccc(cc1)C1=NC(=[N]=C([N]1)c1ccc(cc1)[C]1C=NN=C1)c1ccc(cc1)[C]1C=NN=C1.N1=C[C](C=N1)c1ccc(cc1)C1=[N]=C(N=C([N]1)c1ccc(cc1)C1=C[N]N=C1)c1ccc(cc1)C1=C[N]N=C1.N1=C[C](C=N1)c1ccc(cc1)C1=[N]=C(N=C([N]1)c1ccc(cc1)C1=C[N]N=C1)c1ccc(cc1)[C]1C=NN=C1.N1=C[C](C=N1)c1ccc(cc1)C1=[N]=C([N]C(=N1)c1ccc(cc1)C1=C[N]N=C1)c1ccc(cc1)C1=C[N]N=C1.[Ni]": (18.11345, 5.03402, "Ni"),
    "N1=C[N]N([CH]1)c1ccc(cc1)C1=NN=N[N]1.[Cu]": (4.62691, 4.02117, "Cu"),
    "N1=C[N]N([CH]1)c1ccc(cc1)C1=NN=N[N]1.[O-]C(=O)c1ccc(cc1)[Si](c1ccc(cc1)C(=O)[O-])(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn][O]([Zn])[Zn]": (6.19022, 3.98017, "Zn,Si"),
    "N1=C[N]N([CH]1)c1ccc(cc1)N(c1ccc(cc1)N1[N]C=N[CH]1)c1ccc(cc1)N1[N]C=N[CH]1.[O-]C(=O)c1ccc(cc1)c1cccc(c1)c1ccc(cc1)C(=O)[O-].[Zn]": (4.84074, 2.72589, "Zn"),
    "N1=CC=N[N]1.[CH]1C=NN=N1.[Cd].[N]1C=CN=N1": (6.42627, 4.13446, "Cd"),
    "NC(=O)CN(Cc1ccc2c(n1)cccc2)CCCCN(Cc1ccc2c(n1)cccc2)CC(=O)N.[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn]": (4.76297, 3.4784, "Zn"),
    "NC(=S)c1ccncc1.[Cu]I": (5.17339, 4.44401, "Cu"),
    "NC(=S)NN=Cc1ccncc1.[Ag]": (14.60252, 14.18833, "Ag"),
    "NC1=C2[N]C=[N]=C2[N]C=N1.NC1=NC=[N]=C2C1=NC=N2.[O-]C(=O)c1ccc(cc1)C1=C2C=CC3=[N]2[Zn]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2ccc(cc2)C(=O)[O-])cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn]O[Zn].[Zn][Zn]": (16.87479, 10.45402, "Zn"),
    "NC1=C2N=CN=C2N=C[N]1.[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].[Zn].[Zn]O[Zn]": (24.11442, 19.56277, "Zn"),
    "NC1=N[N]C(=N1)N.NC1=[N]=C(N=N1)N.[Co].[Co][Co].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (8.12547, 6.11997, "Co"),
    "NC1=N[N]C=N1.NC1=[N]=CN=N1.[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn]": (4.97233, 3.59683, "Zn"),
    "NC1=NC(=[N]=C([N]1)N)c1ccncc1.NC1=[N]=C(N)N=C([N]1)c1ccncc1.[Co][Co].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-]": (9.82648, 4.70794, "Co"),
    "NC1=NC=N[N]1.NC1=NN=C[N]1.NC1=N[N]C=N1.NC1=[N]=CN=N1.[Co].[O-]C(=O)c1cccc(c1)c1cccc(c1)C(=O)[O-]": (4.91809, 3.4925, "Co"),
    "NC1=NC=NC2=NC=N[C]12.[Cu].[Cu]1[OH]2[Cu][OH]3[Cu]4562[OH]1[Cu][OH]6[Cu][OH]5[Cu][OH]4[Cu]3": (8.37218, 6.14771, "Cu"),
    "NC1=NC=NC2=NC=N[C]12.Nc1cc(ccc1c1ccc(cc1N)C(=O)[O-])C(=O)[O-].[Zn].[Zn][O]([Zn])([Zn])[Zn]": (13.36303, 8.26092, "Zn"),
    "NC1=NN=C([N]1)N.[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (9.4964, 5.39515, "Zn"),
    "NC1=NN=C([N]1)N.[O-]C(=O)c1cc(cc(c1)C1=NN=N[N]1)C(=O)[O-].[O-]C(=O)c1cc(cc(c1)C1=N[N]N=N1)C(=O)[O-].[Zn]": (9.18995, 6.02541, "Zn"),
    "NC1=NN=C([N]1)N.[O-]C(=O)c1cc(cc(c1)C1=NN=N[N]1)C(=O)[O-].[Zn]": (5.34821, 3.64058, "Zn"),
    "NC1=NN=C([N]1)N.[O-]C(=O)c1cccc(c1)C(=O)[O-].[Zn]": (5.65164, 3.52855, "Zn"),
    "NC1=NN=C([N]1)N.NC1=[N]=C(N=N1)N.[Co].[O-]C(=O)c1cc(nc(c1)C(=O)[O-])C(=O)[O-]": (6.62081, 2.52169, "Co"),
    "NC1=NN=C[N]1.NC1=[N]=CN=N1.[Zn][S]([Zn])[Zn]": (6.42145, 2.85127, "Zn"),
    "NC1=NN=N[N]1.[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (12.12551, 5.06332, "Zn"),
    "Nc1c(cc(cc1c1ccc(cc1)C(=O)[O-])c1cc(c2ccc(cc2)C(=O)[O-])c(c(c1)c1ccc(cc1)C(=O)[O-])N)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (30.4164, 29.15594, "Zr"),
    "Nc1c(cc(cc1c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Cu].[Cu][Cu]": (12.06834, 10.9241, "Cu"),
    "Nc1cc(C(=O)[O-])c(c(c1)C(=O)[O-])C(=O)[O-].[Co].[OH2][Co].n1ccc(cc1)c1ccncc1": (5.14208, 3.54214, "Co"),
    "Nc1cc(C(=O)[O-])c(c(c1)C(=O)[O-])C(=O)[O-].[Ni].n1ccc(cc1)C=Cc1ccncc1": (5.66002, 3.80897, "Ni"),
    "Nc1cc(C(=O)[O-])c(c(c1)C(=O)[O-])C(=O)[O-].[Ni].n1ccc(cc1)c1ccncc1": (5.07307, 3.56004, "Ni"),
    "Nc1cc(C(=O)[O-])c(c(c1)C(=O)[O-])C(=O)[O-].Nc1cnccc1c1ccncc1.[Ni]": (5.28079, 3.64571, "Ni"),
    "Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Co][O]1[Co][O]([Co]1)[Co].[O-]C(=O)c1ccc(cc1)c1ccncc1": (6.42474, 4.90193, "Co"),
    "Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Co][OH]([Co][OH]([Co])[Co])[Co]": (5.87708, 3.64729, "Co"),
    "Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cr][O]([Cr])[Cr].[O-]C(=O)c1ccncc1.[Zn][Zn]": (12.38016, 7.20357, "Zn,Cr"),
    "Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn].n1cc([nH]c1)c1ccc(cc1)c1[nH]cnc1": (3.6645, 2.63718, "Zn"),
    "Nc1ccc(cc1)Cn1ncnc1.[Cd]": (5.25157, 3.57485, "Cd"),
    "Nc1cncc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cu][O]([Cu])([Cu])[Cu]": (8.75331, 4.94575, "Cu"),
    "Nc1cnccc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Co][O]([Co])[Co].[O-]C=O": (8.42238, 8.03127, "Co"),
    "Nc1cnccc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Co][OH]([Co])[Co]": (4.48042, 2.99612, "Co"),
    "Nc1cnccc1c1ccncc1.[Cu]": (8.85794, 5.7866, "Cu"),
    "Nc1nc(N)c(cc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cu][Cu]": (10.56906, 5.22934, "Cu"),
    "Nc1ncnc2=[N]=CN=c12.O=N(=O)c1cc(cc(c1)c1cc(ccc1C(=O)[O-])C(=O)[O-])c1cc(ccc1C(=O)[O-])C(=O)[O-].[O-]C=O.[Zn].[Zn][Zn]": (7.29375, 4.92532, "Zn"),
    "Nn1c(nnc1c1cccc(c1)c1ccncc1)c1cccc(c1)c1ccncc1.[Cd]": (4.95702, 4.0645, "Cd"),
    "Nn1c(nnc1c1ccncc1)c1ccncc1.[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn]": (7.64152, 3.58966, "Zn"),
    "NNC(=O)NN=C(c1ccncc1)C.[Zn]": (5.08449, 3.85921, "Zn"),
    "O.[Co].[O-]C(=O)C1CCC(CC1)C(=O)[O-]": (4.25315, 3.76589, "Co"),
    "O.O=Cc1c([O])c(C=O)c(c(c1[O])C=O)[O].[Cu]": (8.13006, 7.89447, "Cu"),
    "O[Cu]O.[Cu].[Cu][Cu].[O-]C(=O)c1cncc(c1)C(=O)[O-]": (9.66995, 5.60506, "Cu"),
    "O[Er].[O-]C(=O)c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-]": (9.75883, 8.23795, "Er"),
    "O[Gd].[Gd].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])N1[CH]C=C(C=C1)c1ccncc1.[O][CH][O]": (5.14789, 3.61962, "Gd"),
    "O[In][OH][In][OH][In]O.[O-]C(=O)c1ccc(cc1)P(=O)(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (5.47137, 3.17727, "In"),
    "O[Zn][O]([Zn])[Zn].[O-]C(=O)c1ccc2-c3c(S(=O)(=O)c2c1)cc(cc3[O])C(=O)[O-]": (10.05358, 7.79549, "Zn"),
    "O[Zr]123(O)[OH]4[Zr]56([O]3[Zr]37([OH]2[Zr]28([O]1[Zr]14([O]6[Zr]([OH]53)([OH]21)([O]78)(O)O)(O)O)(O)O)(O)O)(O)O.[O-]C(=O)c1ccc(cc1)C1=C2C=CC3=[N]2[Fe]24n5c1ccc5C(=C1[N]2=C(C=C1)C(=c1n4c(=C3c2ccc(cc2)C(=O)[O-])cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (16.95031, 14.45168, "Fe,Zr"),
    "O=[C]1=NC2=N[C](=[N]=C3N2C(=N[C](=O)=N3)[N]1)=O.O=[C]1=NC2=[N]=[C](=O)N=C3N2C(=N[C](=O)=N3)[N]1.[La]": (5.66062, 5.50843, "La"),
    "O=[C]1=NC2=N[C](=NC3=[N]=[C](=O)N=C([N]1)N23)=O.O=[C]1=NC2=N[C](=[N]=C3N2C(=N[C](=O)=N3)[N]1)=O.[Ce]": (5.60637, 5.50315, "Ce"),
    "O=[C]1=NC2=N[C](=NC3=[N]=[C](=O)N=C([N]1)N23)=O.O=[C]1=NC2=N[C](=[N]=C3N2C(=N[C](=O)=N3)[N]1)=O.[Pr]": (5.58275, 5.44827, "Pr"),
    "O=C([C]1C=NN=C1)NCC(=O)[O-].[O-]C(=O)CNC(=O)C1=C[N]N=C1.[Zn]": (8.61802, 7.72596, "Zn"),
    "O=C(C(=O)Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-])Nc1cc(cc(c1)C(=O)O)C(=O)[O-].[Cd]": (5.20872, 3.4546, "Cd"),
    "O=C(C1=CN=N[CH]1)Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].O=C(C1=C[N]N=C1)Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].O=C([C]1C=NN=C1)Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Zn]": (8.37161, 7.49472, "Zn"),
    "O=C(c1cc(cc(c1)C(=O)[O-])C(=O)[O-])Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cd]": (4.53525, 3.60165, "Cd"),
    "O=C(c1cc(cc(c1)C(=O)Nc1ccc(cc1)C(=O)[O-])C(=O)Nc1ccc(cc1)C(=O)[O-])Nc1ccc(cc1)C(=O)[O-].[La]": (8.06565, 5.57702, "La"),
    "O=C(c1cc(cc(c1)C(=O)Nc1ccc(cc1)C(=O)[O-])C(=O)Nc1ccc(cc1)C(=O)[O-])Nc1ccc(cc1)C(=O)[O-].[Y]": (8.35731, 5.62923, "Y"),
    "O=C(c1cc(cc(c1)C(=O)Nc1ccncc1)C(=O)Nc1ccncc1)Nc1ccncc1.[Ni].[O-]C(=O)c1ccc(c(c1)S([O])([O])[O])C(=O)[O-]": (9.33118, 5.24845, "Ni"),
    "O=C(c1cc(cc(c1)C(=O)NCc1cccnc1)C(=O)NCc1cccnc1)NCc1cccnc1.[Cd].[O-]C(=O)c1cc(cc(c1)C(=O)[O-])C(=O)[O-]": (4.57745, 3.18544, "Cd"),
    "O=C(c1ccc(cc1)C(=O)[O-])Nc1cc2ccccc2cc1NC(=O)c1ccc(cc1)C(=O)[O-].[Eu].[Eu][Eu]": (6.38938, 4.82083, "Eu"),
    "O=C(c1ccc(cc1)C(=O)[O-])NC1CCCCC1NC(=O)c1ccc(cc1)C(=O)[O-].[Co].n1ccc(cc1)c1ccc(cc1)c1ccncc1": (5.8476, 3.94159, "Co"),
    "O=C(c1ccc(cc1)C(=O)Nc1ccncc1)Nc1ccncc1.[Co][Co].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-]": (7.50262, 5.69127, "Co"),
    "O=C(c1ccc(cc1)C(=O)NCC(=O)[O-])NCC(=O)[O-].[In].[OH]": (4.95019, 4.49382, "In"),
    "O=C(c1ccc(cc1)C=Cc1ccc(cc1)C(=O)Nc1cccnc1)Nc1cccnc1.[Cd].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (5.97916, 3.85246, "Cd"),
    "O=C(c1ccc(s1)C(=O)Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-])Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Ni][OH2][Ni]": (11.74076, 5.45981, "Ni"),
    "O=C(c1cccc(n1)C(=O)Nc1cccc(c1)C(=O)[O-])Nc1cccc(c1)C(=O)[O-].[Cu][Cu]": (4.85859, 4.12851, "Cu"),
    "O=C(c1ccccc1OCC(c1ccncc1)(COc1ccccc1C(=O)NCc1ccccc1)COc1ccccc1C(=O)NCc1ccccc1)NCc1ccccc1.[Eu]": (5.17376, 4.04652, "Eu"),
    "O=C(c1ccccc1OCC(c1ccncc1)(COc1ccccc1C(=O)NCc1ccccc1)COc1ccccc1C(=O)NCc1ccccc1)NCc1ccccc1.[Gd]": (4.94344, 3.73164, "Gd"),
    "O=C(c1ccccc1OCC(c1ccncc1)(COc1ccccc1C(=O)NCc1ccccc1)COc1ccccc1C(=O)NCc1ccccc1)NCc1ccccc1.[Tb]": (5.17025, 3.9894, "Tb"),
    "O=C(c1cccnc1)N[N][CH]c1cccnc1.[Cd].[O-]C(=O)c1cc(cc(c1)N(=O)=O)C(=O)[O-]": (5.0765, 3.92433, "Cd"),
    "O=C(c1ccncc1)Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cu]": (3.9725, 3.30626, "Cu"),
    "O=C(c1ccncc1)Nc1ccc(cc1)NC(=O)c1ccncc1.[Co].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-]": (5.77046, 4.75025, "Co"),
    "O=C(c1ccncc1)Nc1ccc(cc1)S(=O)(=O)c1ccc(cc1)NC(=O)c1ccncc1.[Co][Co].[O-]C(=O)c1ccc(cc1)S(=O)(=O)c1ccc(cc1)C(=O)[O-]": (7.68226, 5.73122, "Co"),
    "O=C(c1ccncc1)NN=Cc1ccncc1.[Co].[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-]": (6.08907, 3.5319, "Co"),
    "O=C(N1CCCC1C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cu][Cu]": (6.89711, 4.73934, "Cu"),
    "O=C(N1CCCC1C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Cu].n1ccc(cc1)c1ccncc1": (5.84761, 4.82798, "Cu"),
    "O=C(Nc1ccc(cc1)C(=O)[O-])Nc1ccc(cc1)C(=O)[O-].[Cu][Cu].n1ccc(cc1)c1ccncc1": (11.37052, 9.86802, "Cu"),
    "O=C(Nc1cccc2c1cccc2NC(=O)Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-])Nc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cd].c1ncn(c1)Cc1ccc(cc1)c1ccc(cc1)Cn1cncc1": (4.55938, 2.83126, "Cd"),
    "O=C(Nc1ccncc1)Nc1ccncc1.[Cd].[O-]C(=O)c1ccc(cc1)N(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (7.42252, 5.62882, "Cd"),
    "O=C(Nc1ccncc1)Nc1ccncc1.[Co].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (4.97849, 3.67499, "Co"),
    "O=C(Nc1ccncc1)Nc1ccncc1.[O-]C(=O)c1ccc(cc1)Oc1ccc(cc1)C(=O)[O-].[Zn]": (8.64683, 5.89218, "Zn"),
    "O=C(NCc1cccnc1)CCCCCCC(=O)NCc1cccnc1.[Cd].[O-]C(=O)c1ccc(c2c1cccc2)C(=O)[O-]": (6.31819, 4.66502, "Cd"),
    "O=C=O.[Mn].[O-]C(=O)c1ccc(cc1)C1=C2C=CC(=C(c3ccc(cc3)C(=O)[O-])C3=NC(=C(C4=CC=C(C(=C5N=C1C=C5)c1ccc(cc1)C(=O)[O-])[N]4)c1ccc(cc1)C(=O)[O-])C=C3)[N]2.[Zn][Zn]": (8.03478, 4.99407, "Zn,Mn"),
    "O=C1C(=O)C(=C1Nc1cccc(c1)C(=O)[O-])Nc1cccc(c1)C(=O)[O-].[Cd].n1ccc(cc1)c1ccncc1": (5.68434, 2.48875, "Cd"),
    "O=C1C(=O)C(=C1Nc1cccc(c1)C(=O)[O-])Nc1cccc(c1)C(=O)[O-].[Co].n1ccc(cc1)c1ccncc1": (6.44898, 5.79069, "Co"),
    "O=C1C(=O)C(=C1Nc1cccc(c1)C(=O)[O-])Nc1cccc(c1)C(=O)[O-].[O].[Zn]": (9.21355, 8.42973, "Zn"),
    "O=C1C(=O)C(=O)C1=O.[Co].[OH]": (4.13692, 3.80839, "Co"),
    "O=C1c2cc(ccc2-c2c1cc(cc2)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Eu]": (5.55831, 3.99162, "Eu"),
    "O=C1c2cc(ccc2-c2c1cc(cc2)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Gd]": (5.37591, 3.59599, "Gd"),
    "O=C1c2cc(ccc2-c2c1cc(cc2)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Tb]": (5.37255, 3.53538, "Tb"),
    "O=C1c2cc(ccc2-c2c1cc(cc2)c1ccncc1)c1ccncc1.[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn][Zn]": (7.11267, 3.81215, "Zn"),
    "O=C1c2ccc(cc2C(=O)c2c1cc(cc2)C(=O)[O-])C(=O)[O-].[Mn].[O-]C(=O)c1ccc2c(c1)C(=O)c1c(C2=O)ccc(c1)C(=O)[O-]": (7.60082, 6.12799, "Mn"),
    "O=C1c2ccc3c4c2c(C(=O)N1n1cnnc1)ccc4C(=O)N(C3=O)n1cnnc1.[Fe].[O]": (3.99564, 3.68069, "Fe"),
    "O=C1N([C]2C(=NN=C2C)C)C(=O)c2c3c1ccc1c3c(cc2)C(=O)N(C1=O)[C]1C(=NN=C1C)C.[Cu]1[OH][Cu][OH][Cu][OH][Cu][OH][Cu][OH][Cu][OH][Cu][OH][Cu][OH][Cu][OH][Cu][OH][Cu][OH][Cu][OH]1": (9.0116, 6.2013, "Cu"),
    "O=C1N(c2cccc(c2)C(=O)[O-])C(=O)c2c3c1ccc1c3c(cc2)C(=O)N(C1=O)c1cccc(c1)C(=O)[O-].[Eu]": (11.19496, 10.13408, "Eu"),
    "O=C1N(c2ccncc2)C(=O)c2c3c1cc(Cl)c1c3c(c(c2)Cl)c2c3c1c(Cl)cc1c3c(cc2Cl)C(=O)N(C1=O)c1ccncc1.[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-].[Zn][Zn]": (8.32876, 5.6982, "Zn"),
    "O=C1N(c2ccncc2)C(=O)c2c3c1ccc1c3c(cc2)C(=O)N(C1=O)c1ccncc1.[Ni].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (4.90255, 3.60054, "Ni"),
    "O=C1N(c2ccncc2)C(=O)c2c3c1ccc1c3c(cc2)C(=O)N(C1=O)c1ccncc1.[Ni].[O-]C(=O)c1ccc2c(c1)ccc(c2)C(=O)[O-]": (5.95504, 5.06167, "Ni"),
    "O=C1N(c2ccncc2)C(=O)c2c3c1ccc1c3c(cc2)C(=O)N(C1=O)c1ccncc1.[O-]C(=O)c1ccc(cc1)c1cc(cc(c1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-].[Zn]": (9.51234, 6.58632, "Zn"),
    "O=C1N(Cc2cccnc2)C(=O)c2c3c1ccc1c3c(cc2)C(=O)N(C1=O)Cc1cccnc1.[O-]C(=O)c1ccc(cc1)C(=O)[O-].[Zn]": (5.97175, 2.83006, "Zn"),
    "O=C1NC(=O)C2=NC=[N]=C2[N]1.O=C1NC(=O)N=C2[C]1N=C[N]2.O=C1NC(=O)[C]2C(=NC=N2)[N]1.[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=O)[O-].[Zn][O]1[Zn][O]([Zn]1)[Zn]": (9.49982, 6.32548, "Zn"),
    "O=C1Nc2cc(ccc2-c2c(N1)cc(cc2)C(=O)[O-])C(=O)[O-].[Zn][Zn]": (10.47983, 6.30167, "Zn"),
    "O=C1Nc2cc(ccc2-c2c(N1)cc(cc2)C(=O)[O-])C(=O)[O-].[Zn][Zn].n1ccc(cc1)CCc1ccncc1": (8.64973, 6.50826, "Zn"),
    "O=C1O[Cd]2345OC(=O)c6ccc(-c7cc8c(-c9ccc1cc9)cc([O])c(-c1c(cc(-c9ccc([C](O2)O3)cc9)c2cc(-c3ccc([C](O4)O5)cc3)ccc12)[O])c8cc7)cc6.[Cd]": (8.24343, 6.46185, "Cd"),
    "O=C1O[Cd]234O[C](O2)c2ccc(-c5ccc(-n6c7ccc(-c8ccc1cc8)cc7c1cc(-c7ccc([C](O3)O4)cc7)ccc61)cc5)cc2.[OH2][Cd][OH2]": (8.63493, 7.5169, "Cd"),
    "O=CC1=CN=N[CH]1.O=CC1=C[N]N=C1.O=C[C]1C=NN=C1.[Cu][O]([Cu])[Cu]": (6.81528, 6.08875, "Cu"),
    "O=Cc1ccc(cc1[O])c1ccncc1.[Co]": (11.21785, 10.48012, "Co"),
    "O=Cc1ccc(cc1[O])c1ccncc1.[Cu]": (10.63307, 10.00815, "Cu"),
    "O=Cc1ccc(cc1[O])c1ccncc1.[Zn]": (5.10201, 4.50206, "Zn"),
    "O=Cc1ccc(cc1OCc1ccncc1)OCc1ccncc1.[Co][Co].[O-]C(=O)c1ccc(cc1)C(=O)[O-]": (5.67777, 3.97572, "Co"),
    "O=CN(C)C.[Cd].[O-]C(=O)c1ccc(cc1)c1ccc(cc1)C(=C(c1ccc(cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)C(=O)[O-])c1ccc(cc1)c1ccc(cc1)C(=O)[O-]": (9.929, 7.41692, "Cd"),
    "O=CN(C)C.[Mn].[O-]C(=O)c1ccc(cc1)C(=C(c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-])c1ccc(cc1)C(=O)[O-]": (4.70482, 3.53716, "Mn"),
    "O=N(=O)C1=N[CH]C=N1.[N]1C=NN=N1.[Zn]": (5.61495, 4.15563, "Zn"),
    "O=N(=O)c1cc(cc(c1)c1cc(cc(c1)C(=O)[O-])C(=O)[O-])c1cc(cc(c1)C(=O)[O-])C(=O)[O-].[O-]C=O.[Zn].[Zn][Zn]": (9.76418, 6.94382, "Zn"),
    "O=N(=O)c1cc(ccc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-].[Pr]": (9.00205, 4.40372, "Pr"),
    "O=N(=O)c1cc(ccc1c1cc(cc(c1)C(=O)[O-])C(=O)[O-])C(=O)[O-].O[Gd]": (5.85143, 4.17377, "Gd"),
    "O=P(c1ccc(cc1)n1cncc1)(c1ccc(cc1)n1cncc1)c1ccc(cc1)n1cncc1.[Ni].[O-]C(=O)c1ccc(cc1)C=Cc1ccc(cc1)C(=O)[O-]": (7.0348, 6.10182, "Ni"),
    "O=P(c1ccccc1)(c1ccccc1)c1ccc(cc1)c1cc(nc(c1)c1ccncc1)c1ccncc1.[Co]": (5.93349, 3.83703, "Co"),
    "O1[Mo]2[Mo]1O2.[O-]C(=O)c1ccc(cc1)C1=C2C=CC(=N2)C(=c2ccc(=C(C3=NC(=C(c4[nH]c1cc4)c1ccc(cc1)C(=O)[O-])C=C3)c1ccc(cc1)C(=O)[O-])[nH]2)c1ccc(cc1)C(=O)[O-]": (6.98637, 5.74587, "Mo"),
    "O1[W]23O[W]45O[W]61O[W]17O[W]8(O3)O[W]3(O2)O[W]2(O5)O[W]5(O4)O[W](O6)(O1)[O]1[Ni]46[O]7[Ni]7[O]8[Ni]8([O]3[Ni]3[O]2[Ni]2([O]5[Ni]1[O]62)[O]83)[O]47.[O-]C(=O)c1cc(cc(c1)S([O])([O])[O])C(=O)[O-]": (14.763, 10.54169, "Ni,W"),
    "O1[Zr]2O[Zr]3O[Zr]4O[Zr]1O[Zr]1O[Zr](O2)O[Zr](O3)O[Zr](O1)O4.[O-]C(=O)c1ccc(cc1)C#Cc1ccc(cc1)C(c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-])(c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-])c1ccc(cc1)C#Cc1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (18.84439, 11.02909, "Zr"),
    "OC(=O)c1cc(C(=O)O)c(cc1N1[N]C=N[CH]1)N1[N]C=N[CH]1.[Co].[O-]C(=O)c1cc(C(=O)[O-])c(cc1N1[N]C=N[CH]1)N1[N]C=N[CH]1.[O-]C(=O)c1cc(C(=O)[O-])c(cc1N1[N]C=N[CH]1)n1ncnc1": (6.07235, 3.93851, "Co"),
    "OC(=O)c1cc(cc(c1)c1cc(ccc1C(=O)[O-])C(=O)[O-])c1cc(ccc1C(=O)[O-])C(=O)[O-].[Co][OH]1[Co][OH]([Co]1)[Co]": (4.67821, 3.63338, "Co"),
    "OC(=O)c1cc(cc(c1)n1cncc1)n1cncc1.[Cu]": (6.05836, 5.06464, "Cu,Ti"),
    "OC(=O)c1cc(cc(c1)Oc1ccccc1C(=O)[O-])Oc1ccccc1C(=O)[O-].[Co].n1ccc(cc1)c1ccncc1": (5.49014, 3.54007, "Co"),
    "OC(=O)c1ccc(cc1)CNc1cc(cc(c1)C(=O)[O-])C(=O)[O-].[Cd].n1ccc(cc1)c1ccncc1": (5.13307, 2.56257, "Cd"),
    "OC(=O)c1ccc(cc1c1ncccc1C(=O)[O-])C(=O)[O-].[Cd]": (6.07712, 4.50995, "Cd"),
    "OC(P(=O)(O)[O])c1ccc(cc1)C(P(=O)(O)[O])O.OC(P(=O)(O)[O])c1ccc(cc1)C(P(=O)([O])O)O.[Eu]": (5.69914, 3.57907, "Eu"),
    "Oc1c(cc(cc1c1ccc(cc1)C(=O)[O-])c1cc(c2ccc(cc2)C(=O)[O-])c(c(c1)c1ccc(cc1)C(=O)[O-])O)c1ccc(cc1)C(=O)[O-].[O]12[Zr]34[O]5[Zr]62[O]2[Zr]71[O]4[Zr]14[O]3[Zr]35[O]6[Zr]2([O]71)[O]43": (30.78, 29.4358, "Zr"),
}

# Atom scale for linker structures inside the MOF diagram.
# Relative to BASE_RADII from turtle_renderer.
# Higher = bigger atoms = more crowded looking.
LINKER_ATOM_SCALE = 0.30

# Per-face scale multipliers for the cube (relative to LINKER_ATOM_SCALE).
FRONT_LINKER_SCALE = 1.00   # front face — reference size
DEPTH_LINKER_SCALE = 0.90   # z-axis struts — slightly smaller
BACK_LINKER_SCALE  = 0.70   # back face — furthest away, smallest

# Fraction of the edge the linker occupies (leaves gap near metal balls).
# 1.0 = fills all available space; 0.75 = 12.5% gap each side.
LINKER_INSET = 0.82

# Guest ion + hydration shell display scale.
# Shell display radius = pore_radius_px * GUEST_DISPLAY_SCALE.
# 0.5 = shell fills half the pore; 1.0 = shell fills the full pore.
GUEST_DISPLAY_SCALE = 0.60

# How far back the cabinet-projection back face sits.
# 1.0 = depth struts same length as face edges; 1.5 = 50% longer.
DEPTH_STRUT_FACTOR = 1.55

# ─────────────────────────────────────────────────────────────────────────────
# DERIVED — do not edit these
# ─────────────────────────────────────────────────────────────────────────────
def _pore_driven_side(pore_diameter_ang, scale=1.0):
    """Square side from pore diagonal: side = pore_diameter / sqrt(2)."""
    return (pore_diameter_ang / math.sqrt(2)) * PX_PER_ANG * scale


def _lookup_mof(linker_smiles, metal):
    """
    Look up pore data from MOF_DB.
    Tries to find an entry whose identifier contains the linker SMILES
    and whose metal matches. Prefers exact/minimal entries.
    Returns (LCD_ang, PLD_ang) or None if not found.
    """
    # Build candidate identifier strings — try simple metal+linker combos
    candidates = [
        f"{linker_smiles}.[{metal}]",
        f"[{metal}].{linker_smiles}",
        f"[{metal}][{metal}].{linker_smiles}",
        f"{linker_smiles}.[{metal}][{metal}]",
    ]
    for cand in candidates:
        if cand in MOF_DB:
            return MOF_DB[cand][:2]  # (LCD, PLD)

    # Fuzzy: find entries containing the linker SMILES with matching metal
    best = None
    for key, (lcd, pld, metals) in MOF_DB.items():
        if linker_smiles in key and metal in metals.split(","):
            # prefer shorter identifiers (fewer extra components)
            if best is None or len(key) < len(best[0]):
                best = (key, lcd, pld)
    if best:
        return best[1], best[2]
    return None


class MOFRenderer:

    def __init__(self, turtle_obj, metal, linker_smiles,
                 cx=0, cy=0, scale=1.0, metal_charge=0, guest_ion=None):
        self.t            = turtle_obj
        self.metal        = metal
        self.metal_charge = metal_charge
        self.linker_smiles = linker_smiles
        self.cx           = cx
        self.cy           = cy
        self.scale        = scale
        self.guest_ion    = guest_ion

        # ── Step 1: parse and layout linker at natural scale ─────────────
        self.linker_mol = SmilesParser(linker_smiles).parse()
        LayoutEngine(self.linker_mol).layout()
        self._center_linker()

        # Fixed rendering scale — linker always drawn at this size, never stretched
        self._mol_scale = LINKER_ATOM_SCALE * scale

        # Linker natural half-width in pixels at _mol_scale
        xs = [a.x for a in self.linker_mol.atoms]
        ys = [a.y for a in self.linker_mol.atoms]
        atom_pad = max(BASE_RADII.values()) * self._mol_scale
        self._linker_half_w = (max(xs) - min(xs)) / 2 * self._mol_scale + atom_pad
        self._linker_half_h = (max(ys) - min(ys)) / 2 * self._mol_scale + atom_pad

        # ── Step 2: metal radius — sized relative to linker atoms ─────────
        self.metal_r = max(BASE_RADII.get(metal, 28) * self._mol_scale * 2.2,
                           14 * scale)
        self.metal_fill, self.metal_text = ATOM_COLORS.get(metal, DEFAULT_ATOM_COLOR)

        # ── Step 3: square side = linker width + one metal_r each end ─────
        # Metal corners sit exactly where the linker endpoints land
        self._sq_size = self._linker_half_w * 2 + 2 * self.metal_r

        # ── Step 4: pore data — only used for fit verdict + readout ───────
        db_result = _lookup_mof(linker_smiles, metal)
        if db_result:
            self._lcd_ang, self._pld_ang = db_result
        else:
            self._lcd_ang = MOF_PORE_DIAMETER_FALLBACK
            self._pld_ang = MOF_PORE_DIAMETER_FALLBACK * 0.75

        self._pore_fit_ang = self._pld_ang / 2
        self._pore_r_ang   = self._lcd_ang / 2
        self._pore_r_px    = max(self._sq_size / 2 - self.metal_r, 0)

        # Guest ion lookup
        self._guest_ionic_ang    = None
        self._guest_hydrated_ang = None
        self._guest_verified     = None
        if guest_ion:
            entry = ION_RADII.get(guest_ion)
            if entry:
                self._guest_ionic_ang, self._guest_hydrated_ang, self._guest_verified = entry

    def _center_linker(self):
        xs = [a.x for a in self.linker_mol.atoms]
        ys = [a.y for a in self.linker_mol.atoms]
        cx = (max(xs) + min(xs)) / 2
        cy = (max(ys) + min(ys)) / 2
        for a in self.linker_mol.atoms:
            a.x -= cx
            a.y -= cy

    # ── Public overloads ──────────────────────────────────────────────────────

    def draw(self):
        """Square (no guest) + cube (guest in cube only)."""
        self._render(linker_mode=True, guest_in_square=False, guest_in_cube=True)

    def draw_with_guest(self):
        """Guest ion shown in both panels."""
        self._render(linker_mode=True, guest_in_square=True, guest_in_cube=True)

    def draw_without_guest(self):
        """No guest ion anywhere."""
        self._render(linker_mode=True, guest_in_square=False, guest_in_cube=False)

    def draw_simple(self):
        """Plain-line edges; guest in cube only."""
        self._render(linker_mode=False, guest_in_square=False, guest_in_cube=True)

    def draw_simple_with_guest(self):
        """Plain-line edges; guest in both panels."""
        self._render(linker_mode=False, guest_in_square=True, guest_in_cube=True)

    def draw_simple_without_guest(self):
        """Plain-line edges; no guest."""
        self._render(linker_mode=False, guest_in_square=False, guest_in_cube=False)

    # ── Internal dispatcher ───────────────────────────────────────────────────

    def _render(self, linker_mode, guest_in_square, guest_in_cube):
        s   = self._sq_size
        gap = max(s * 0.30, 50 * self.scale)

        sq_cx = self.cx - s * 0.60 - gap * 0.5
        cb_cx = self.cx + s * 2.2 * 0.35 + gap * 0.5

        if linker_mode:
            self._draw_square(sq_cx, self.cy, s, show_guest=guest_in_square)
            self._draw_cube(cb_cx, self.cy, s, show_guest=guest_in_cube)
        else:
            self._draw_square_simple(sq_cx, self.cy, s, show_guest=guest_in_square)
            self._draw_cube_simple(cb_cx, self.cy, s, show_guest=guest_in_cube)

        if (guest_in_cube or guest_in_square) and self.guest_ion:
            self._draw_pore_readout(cb_cx, self.cy, s)

    # ── Square SBU — linker mode ──────────────────────────────────────────────

    def _draw_square(self, cx, cy, side, show_guest=False):
        h       = side / 2
        corners = [(cx+h, cy+h), (cx-h, cy+h), (cx-h, cy-h), (cx+h, cy-h)]
        sc      = self._face_scale(side) * FRONT_LINKER_SCALE
        # Draw order: guest → linkers → metals (metals always topmost)
        if show_guest and self.guest_ion:
            self._draw_guest_ion(cx, cy)
        for i, j in [(0,1),(1,2),(2,3),(3,0)]:
            self._draw_linker_between(corners[i], corners[j], scale_override=sc)
        for x, y in corners:
            self._draw_metal(x, y)
        self._write(cx, cy + h + self.metal_r + 10,
                    f"Square SBU [{self.metal}4]", "#333333", 9)

    # ── Square SBU — simple mode ──────────────────────────────────────────────

    def _draw_square_simple(self, cx, cy, side, show_guest=False):
        h       = side / 2
        corners = [(cx+h, cy+h), (cx-h, cy+h), (cx-h, cy-h), (cx+h, cy-h)]
        # Draw order: guest → lines → metals
        if show_guest and self.guest_ion:
            self._draw_guest_ion(cx, cy)
        self.t.pensize(2)
        self.t.pencolor("#555555")
        for i, j in [(0,1),(1,2),(2,3),(3,0)]:
            self._line(corners[i][0], corners[i][1],
                       corners[j][0], corners[j][1])
        for x, y in corners:
            self._draw_metal(x, y)
        self._write(cx, cy + h + self.metal_r + 10,
                    f"Square SBU [{self.metal}4]", "#333333", 9)

    # ── Cube — linker mode ────────────────────────────────────────────────────

    def _draw_cube(self, cx, cy, side, show_guest=False):
        """
        Same 5-layer painter's algorithm as _draw_cube_simple but with
        full linker ball-and-stick instead of plain lines.
        No white fill — correct depth order eliminates the need for it.

        front/back corner indices:
          [0]=top-right  [1]=top-left  [2]=bot-left  [3]=bot-right
          back = front shifted up-right by cabinet projection offset
        """
        front, back = self._cube_corners(cx, cy, side)
        fs = self._face_scale() * FRONT_LINKER_SCALE
        ds = self._face_scale() * DEPTH_LINKER_SCALE
        bs = self._face_scale() * BACK_LINKER_SCALE

        # ── Layer 1: back face linkers + back metals ──────────────────────
        for i, j in [(0,1),(1,2),(2,3),(3,0)]:
            self._draw_linker_between(back[i], back[j], alpha=0.38, scale_override=bs)
        for x, y in back:
            self._draw_metal(x, y, small=True)

        # ── Layer 2: left/distal depth struts (indices 1 and 2) ──────────
        for i in [1, 2]:
            self._draw_linker_between(back[i], front[i], alpha=0.55, scale_override=ds)

        # ── Layer 3: guest ion ────────────────────────────────────────────
        if show_guest and self.guest_ion:
            vis_cx, vis_cy = self._cube_visual_center(cx, cy, side)
            self._draw_guest_ion(vis_cx, vis_cy)

        # ── Layer 4: right/proximal depth struts (indices 0 and 3) ───────
        for i in [0, 3]:
            self._draw_linker_between(back[i], front[i], alpha=1.0, scale_override=ds)

        # ── Layer 5: front face linkers + front metals ────────────────────
        for i, j in [(0,1),(1,2),(2,3),(3,0)]:
            self._draw_linker_between(front[i], front[j], alpha=1.0, scale_override=fs)
        for x, y in front:
            self._draw_metal(x, y)

        top_y = max(y for _, y in back + front)
        ddx   = back[0][0] - front[0][0]
        self._write(cx + ddx/2, top_y + self.metal_r + 10,
                    f"MOF Cube [{self.metal}8]", "#333333", 9)

    # ── Cube — simple mode ────────────────────────────────────────────────────

    def _draw_cube_simple(self, cx, cy, side, show_guest=False):
        """
        Painter's algorithm — 5 depth layers, no white fill needed:

        corners layout (cabinet projection, back offset up-right):
          front: [0]=top-right  [1]=top-left  [2]=bot-left  [3]=bot-right
          back:  same indices, shifted by (dx,dy)

        Layer 1 — BACK: back face edges + back metals (furthest away)
        Layer 2 — LEFT/DISTAL struts: left-side depth struts (indices 1,2)
                   these are the far/left struts that sit behind the ion
        Layer 3 — GUEST ION + hydration shell
        Layer 4 — RIGHT/PROXIMAL struts: right-side depth struts (indices 0,3)
                   these are closer and should overdraw the ion edges
        Layer 5 — FRONT: front face edges + front metals (closest)
        """
        front, back = self._cube_corners(cx, cy, side)
        dim   = self._dim_color("#555555", 0.38)
        solid = "#555555"

        # ── Layer 1: back face edges + back metals ────────────────────────
        self.t.pensize(1)
        self.t.pencolor(dim)
        for i, j in [(0,1),(1,2),(2,3),(3,0)]:
            self._line(back[i][0], back[i][1], back[j][0], back[j][1])
        for x, y in back:
            self._draw_metal(x, y, small=True)

        # ── Layer 2: left/distal depth struts (indices 1 and 2) ──────────
        # These are the left-side struts — further from the viewer in the
        # projection so they sit behind the guest ion.
        self.t.pensize(1)
        self.t.pencolor(dim)
        for i in [1, 2]:
            self._line(back[i][0], back[i][1],
                       front[i][0], front[i][1])

        # ── Layer 3: guest ion ────────────────────────────────────────────
        if show_guest and self.guest_ion:
            vis_cx, vis_cy = self._cube_visual_center(cx, cy, side)
            self._draw_guest_ion(vis_cx, vis_cy)

        # ── Layer 4: right/proximal depth struts (indices 0 and 3) ───────
        # These are the right-side struts — closer to the viewer so they
        # overdraw the edges of the guest ion where they cross.
        self.t.pensize(2)
        self.t.pencolor(solid)
        for i in [0, 3]:
            self._line(back[i][0], back[i][1],
                       front[i][0], front[i][1])

        # ── Layer 5: front face edges + front metals ──────────────────────
        self.t.pensize(2)
        self.t.pencolor(solid)
        for i, j in [(0,1),(1,2),(2,3),(3,0)]:
            self._line(front[i][0], front[i][1], front[j][0], front[j][1])
        for x, y in front:
            self._draw_metal(x, y)

        top_y = max(y for _, y in back + front)
        ddx = back[0][0] - front[0][0]
        self._write(cx + ddx/2, top_y + self.metal_r + 10,
                    f"MOF Cube [{self.metal}8]", "#333333", 9)

    # ── Geometry helpers ──────────────────────────────────────────────────────

    def _face_scale(self, side=None):
        """Return fixed mol_scale — linker always at natural size."""
        return self._mol_scale

    def _cube_corners(self, cx, cy, side):
        """Cabinet-projection corners. DEPTH_STRUT_FACTOR lengthens z-struts."""
        h  = side / 2
        dx = side * 0.38 * DEPTH_STRUT_FACTOR
        dy = side * 0.28 * DEPTH_STRUT_FACTOR
        front = [(cx+h, cy+h), (cx-h, cy+h), (cx-h, cy-h), (cx+h, cy-h)]
        back  = [(x+dx, y+dy) for x, y in front]
        return front, back

    def _cube_visual_center(self, cx, cy, side):
        """Midpoint between front-face centre and back-face centre."""
        dx = side * 0.38 * DEPTH_STRUT_FACTOR
        dy = side * 0.28 * DEPTH_STRUT_FACTOR
        return cx + dx / 2, cy + dy / 2

    def _fill_polygon(self, pts, color):
        t = self.t
        t.penup(); t.goto(pts[0]); t.pendown()
        t.pencolor(color); t.fillcolor(color); t.pensize(1)
        t.begin_fill()
        for p in pts[1:]:
            t.goto(p)
        t.goto(pts[0])
        t.end_fill()
        t.penup()
        t.pensize(1)  # always restore so subsequent lines are visible

    # ── Linker rendering ──────────────────────────────────────────────────────

    def _draw_linker_between(self, p1, p2, alpha=1.0, scale_override=None):
        x1, y1 = p1
        x2, y2 = p2
        dx = x2-x1; dy = y2-y1
        edge_len = math.sqrt(dx*dx + dy*dy)
        if edge_len < 1:
            return
        angle = math.atan2(dy, dx)
        if edge_len < self.metal_r * 2:
            return

        # Always render at fixed _mol_scale — never stretch to fit.
        # scale_override applies per-face multipliers (depth/back).
        mol_scale = scale_override if scale_override is not None \
                    else self._mol_scale

        mx, my = (x1+x2)/2, (y1+y2)/2

        self.t.pensize(max(1, 3 * mol_scale * alpha))
        for bond in self.linker_mol.bonds:
            a, b   = bond.a, bond.b
            ax, ay = self._transform(a.x, a.y, mx, my, angle, mol_scale)
            bx, by = self._transform(b.x, b.y, mx, my, angle, mol_scale)
            ra = BASE_RADII.get(a.symbol, 18) * mol_scale
            rb = BASE_RADII.get(b.symbol, 18) * mol_scale
            sx1, sy1, sx2, sy2 = self._trim(ax, ay, bx, by, ra, rb)
            self.t.pencolor(self._dim_color("#888888", alpha))
            if bond.order == 2:
                self._double_line(sx1, sy1, sx2, sy2, 3 * mol_scale)
            else:
                self._line(sx1, sy1, sx2, sy2)

        self.t.pensize(1)
        for atom in self.linker_mol.atoms:
            ax, ay = self._transform(atom.x, atom.y, mx, my, angle, mol_scale)
            r      = BASE_RADII.get(atom.symbol, 18) * mol_scale
            fill, text_col = ATOM_COLORS.get(atom.symbol, DEFAULT_ATOM_COLOR)
            if alpha < 1.0:
                fill = self._dim_color(fill, alpha)
            self._draw_ball(ax, ay, r, fill)
            if r >= LABEL_MIN_RADIUS * 0.8:
                fs = self._fit_font(atom.symbol, r)
                if fs >= 5:
                    tc = text_col if alpha > 0.6 else "#999999"
                    self._write_centered(ax, ay, atom.symbol, tc, fs)

    def _transform(self, lx, ly, mx, my, angle, mol_scale):
        sx, sy = lx * mol_scale, ly * mol_scale
        c, s   = math.cos(angle), math.sin(angle)
        return mx + sx*c - sy*s, my + sx*s + sy*c

    def _trim(self, x1, y1, x2, y2, r1, r2):
        dx, dy = x2-x1, y2-y1
        l = math.sqrt(dx*dx+dy*dy)
        if l < 1:
            return x1, y1, x2, y2
        ux, uy = dx/l, dy/l
        return x1+ux*r1, y1+uy*r1, x2-ux*r2, y2-uy*r2

    def _line(self, x1, y1, x2, y2):
        self.t.penup(); self.t.goto(x1, y1)
        self.t.pendown(); self.t.goto(x2, y2)
        self.t.penup()

    def _double_line(self, x1, y1, x2, y2, spacing):
        dx, dy = x2-x1, y2-y1
        l = math.sqrt(dx*dx+dy*dy) + 0.001
        px, py = -dy/l*spacing, dx/l*spacing
        self._line(x1+px, y1+py, x2+px, y2+py)
        self._line(x1-px, y1-py, x2-px, y2-py)

    # ── Guest ion ─────────────────────────────────────────────────────────────

    def _draw_guest_ion(self, center_x, center_y):
        """
        Draw hydration shell (blue) then bare ion on top.
        Display size = pore_r_px * GUEST_DISPLAY_SCALE.
        Ion/shell ratio preserved from real data.
        Fit verdict uses hydrated radius vs pore diameter.
        """
        if self._guest_ionic_ang is None:
            return

        ionic_ang    = self._guest_ionic_ang
        hydrated_ang = self._guest_hydrated_ang
        effective_ang = hydrated_ang if hydrated_ang is not None else ionic_ang

        # Map angstroms to pixels using the pore as the reference:
        #   pore_fit_ang (PLD/2) maps exactly to pore_r_px on screen.
        # This means an ion at 100% of the pore radius fills the pore exactly,
        # and an ion at 140% visually overflows — immediately obvious.
        # GUEST_DISPLAY_SCALE zooms fitting ions up/down for visibility,
        # but TOO LARGE ions are always shown at their true overflow size.
        px_per_ang_pore  = self._pore_r_px / max(self._pore_fit_ang, 0.001)
        hydrated_ang_eff = hydrated_ang if hydrated_ang else ionic_ang
        true_hyd_px      = hydrated_ang_eff * px_per_ang_pore
        true_ion_px      = ionic_ang        * px_per_ang_pore

        if effective_ang > self._pore_fit_ang:
            # TOO LARGE: boost by 1.4× so the overflow is clearly visible —
            # the shell bulges well past the linkers/metals on all sides.
            display_hydrated = true_hyd_px * 1.4
            display_ion      = true_ion_px * 1.4
        else:
            # FITS: apply GUEST_DISPLAY_SCALE for visibility tuning
            display_hydrated = true_hyd_px * GUEST_DISPLAY_SCALE
            display_ion      = true_ion_px * GUEST_DISPLAY_SCALE

        # Fit colour based on hydrated radius vs PLD (the real bottleneck)
        if effective_ang <= self._pore_fit_ang * 0.80:
            ion_color = "#3FB950"
        elif effective_ang <= self._pore_fit_ang:
            ion_color = "#D29922"
        else:
            ion_color = "#F85149"

        t = self.t

        # ── Hydration shell ───────────────────────────────────────────────
        if hydrated_ang is not None and display_hydrated > display_ion + 2:
            t.penup(); t.goto(center_x, center_y - display_hydrated)
            t.pendown()
            t.pencolor("#2A6099"); t.pensize(1)
            t.fillcolor("#4A90D9")
            t.begin_fill(); t.circle(display_hydrated); t.end_fill()
            t.penup()

            # Arc text "Hydration Shell" along bottom of shell
            label    = "Hydration Shell"
            n        = len(label)
            annulus  = display_hydrated - display_ion
            fs_shell = min(max(6, int(annulus * 0.38)), 11)
            # Place text near the outer edge of the shell (85% of the way out)
            # so characters have maximum arc radius = maximum spacing
            label_r  = display_ion + annulus * 0.85
            char_w   = fs_shell * 1.1
            char_span = char_w / max(label_r, 1)
            total_span = char_span * n
            if total_span > math.radians(160):
                char_span  = math.radians(160) / n
                total_span = char_span * n
            start_ang = -math.pi/2 - total_span/2 + char_span/2
            t.pencolor("#FFFFFF")
            saved = t.heading() if hasattr(t, 'heading') else 0
            for k, ch in enumerate(label):
                ang  = start_ang + k * char_span
                t.penup()
                t.goto(center_x + label_r * math.cos(ang),
                       center_y + label_r * math.sin(ang))
                if hasattr(t, 'setheading'):
                    t.setheading(math.degrees(ang) + 90)
                t.write(ch, align="center", font=("Arial", fs_shell, "bold"))
            if hasattr(t, 'setheading'):
                t.setheading(saved)

        # ── Bare ion ──────────────────────────────────────────────────────
        t.penup(); t.goto(center_x, center_y - display_ion)
        t.pendown()
        t.pencolor(ion_color); t.pensize(2)
        t.fillcolor(ion_color)
        t.begin_fill(); t.circle(display_ion); t.end_fill()
        t.penup()

        fs = max(6, int(display_ion * 0.55))
        if display_ion >= 10:
            t.goto(center_x, center_y - fs * LABEL_Y_FRACTION)
            t.pencolor("#FFFFFF" if ion_color != "#D29922" else "#333333")
            t.write(self.guest_ion, align="center", font=("Arial", fs, "bold"))

    def _draw_pore_readout(self, cube_cx, cube_cy, sq_size):
        ionic_ang    = self._guest_ionic_ang
        hydrated_ang = self._guest_hydrated_ang
        effective_ang = hydrated_ang if hydrated_ang is not None else ionic_ang
        verified      = self._guest_verified or ""

        if effective_ang is None:
            verdict, verdict_col = f"Ion '{self.guest_ion}' not in database", "#8B949E"
        elif effective_ang <= self._pore_fit_ang * 0.80:
            verdict, verdict_col = "FITS  (comfortable)", "#3FB950"
        elif effective_ang <= self._pore_fit_ang:
            verdict, verdict_col = "FITS  (tight)",       "#D29922"
        else:
            verdict, verdict_col = "TOO LARGE",           "#F85149"

        bottom_y = cube_cy - sq_size / 2 - self.metal_r - 30
        # Pore values are diameters; ion values are radii.
        # For the comparison we use PLD/2 (radius) vs ion radius.
        lines = [
            (f"Pore LCD (diam.): {self._lcd_ang:.2f} A  →  r = {self._lcd_ang/2:.2f} A", "#8B949E"),
            (f"Pore PLD (diam.): {self._pld_ang:.2f} A  →  r = {self._pld_ang/2:.2f} A  [fit]", "#8B949E"),
        ]
        if effective_ang is not None:
            if ionic_ang is not None:
                lines.append((f"Ion bare radius:    {ionic_ang:.2f} A", "#8B949E"))
            if hydrated_ang is not None:
                lines.append((f"Ion hydrated radius:{hydrated_ang:.2f} A  vs PLD r={self._pore_fit_ang:.2f} A", "#4A90D9"))
            lines.append((verdict, verdict_col))
            src_note = "Exp. verified" if "Experimental" in verified else "Est./unverified"
            lines.append((f"* {src_note} ion radii; pore from MOF_data.csv", "#6E7681"))
        else:
            lines.append((verdict, verdict_col))

        for i, (text, col) in enumerate(lines):
            self.t.penup(); self.t.goto(cube_cx, bottom_y - i * 13)
            self.t.pencolor(col)
            self.t.write(text, align="center", font=("Arial", 8, "normal"))

    # ── Metal ball ────────────────────────────────────────────────────────────

    def _draw_metal(self, x, y, small=False):
        r = self.metal_r * (0.72 if small else 1.0)
        t = self.t
        t.penup(); t.goto(x, y-r); t.pendown()
        t.pencolor("#555555"); t.pensize(1)
        t.fillcolor(self.metal_fill)
        t.begin_fill(); t.circle(r); t.end_fill()
        t.penup()
        if not small:
            if self.metal_charge > 0:
                suffix = "+" if self.metal_charge == 1 else f"+{self.metal_charge}"
            elif self.metal_charge < 0:
                suffix = "-" if self.metal_charge == -1 else f"{self.metal_charge}"
            else:
                suffix = ""
            fs = max(7, int(r * 0.70))
            t.goto(x, y - fs * LABEL_Y_FRACTION)
            t.pencolor(self.metal_text)
            t.write(self.metal + suffix, align="center", font=("Arial", fs, "bold"))

    def _draw_ball(self, x, y, radius, fill_color):
        t = self.t
        t.penup(); t.goto(x, y-radius); t.pendown()
        t.pencolor("#555555"); t.pensize(1)
        t.fillcolor(fill_color)
        t.begin_fill(); t.circle(radius); t.end_fill()
        t.penup()

    def _write(self, x, y, text, color, size):
        self.t.penup(); self.t.goto(x, y)
        self.t.pencolor(color)
        self.t.write(text, align="center", font=("Arial", size, "normal"))

    def _write_centered(self, x, y, text, color, font_size):
        self.t.penup()
        self.t.goto(x, y - font_size * LABEL_Y_FRACTION)
        self.t.pencolor(color)
        self.t.write(text, align="center", font=("Arial", font_size, "bold"))

    def _fit_font(self, label, radius):
        side = radius * math.sqrt(2) * 0.85
        n    = len(label)
        fs   = int(min(side/0.72, side/(0.65*max(n,1))) * LABEL_FONT_SCALE)
        return max(fs, 0)

    @staticmethod
    def _dim_color(hex_color, alpha):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        r = int(r + (255-r)*(1-alpha))
        g = int(g + (255-g)*(1-alpha))
        b = int(b + (255-b)*(1-alpha))
        return f"#{r:02x}{g:02x}{b:02x}"
