# mof_renderer.py

# Draws two MOF topology diagrams side by side:
#   1. Square SBU  — 4 metal corners, 4 linker ball-and-stick edges
#   2. 2D cube projection — 8 metal corners, 12 linker edges (cabinet projection)

# Geometry is pore-driven:
#   - MOF_PORE_DIAMETER_ANG sets the pore size in Angstroms
#   - Everything else (square size, linker scale, metal placement) is derived
#     from that one number via PX_PER_ANG

# Public API (all on MOFRenderer):
#   draw()                     — square (no guest) + cube (guest in cube only)
#   draw_with_guest()          — guest in both panels
#   draw_without_guest()       — no guest anywhere
#   draw_simple()              — plain lines, guest in cube only
#   draw_simple_with_guest()   — plain lines, guest in both
#   draw_simple_without_guest()— plain lines, no guest


import math
import re

from smiles_parser import SmilesParser
from layout_engine import LayoutEngine
from turtle_renderer import (
    ATOM_COLORS, BASE_RADII, DEFAULT_ATOM_COLOR,
    LABEL_Y_FRACTION, LABEL_FONT_SCALE, LABEL_MIN_RADIUS
)
# MOF_DB is imported further down, right where it's used/documented.

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
#
# MOF_DB itself lives in api/assets/MOF_data.csv, not here. Since this file
# runs client-side in Skulpt (no filesystem access), Django reads the CSV and
# serves a generated `mof_data` module in its place — see get_mof_engine_file()
# / _build_mof_data_source() in api/views.py. To add or update a MOF entry,
# edit the CSV; no code change or redeploy needed.
from mof_data import MOF_DB

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

# Minimum on-screen radius (px) for the bare guest ion ball. Small ions
# (e.g. Li+, Be2+) would otherwise scale down to a couple of pixels —
# too small to see or label — so we float them up to this floor purely
# for legibility. Does not affect the fit verdict, which is computed
# from the true (unfloored) angstrom values.
GUEST_MIN_DISPLAY_PX = 9

# Extra horizontal breathing room between the square-SBU panel and the
# cube panel, on top of the geometric gap needed to clear the cube's
# depth offset.
PANEL_GAP_PX = 70

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

        # The cube's back face is pushed up-right by the cabinet-projection
        # depth offset, which makes the cube panel visually wider than the
        # square panel. We size the gap off the square/cube edges (not the
        # bare center-to-center distance) so the two panels always end up
        # with real, consistent breathing room between them.
        sq_half_w   = s / 2 + self.metal_r
        cube_half_w = s / 2 + self.metal_r  # cube's left edge mirrors the square

        gap = max(s * 0.45, PANEL_GAP_PX * self.scale)

        sq_cx = self.cx - gap / 2 - sq_half_w
        cb_cx = self.cx + gap / 2 + cube_half_w

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

        # Floor the ball size so small ions (Li+, Be2+, ...) stay visible
        # and legible instead of shrinking to a near-invisible dot. This
        # only ever grows the display size, never shrinks it, so it can't
        # make a "TOO LARGE" ion look like it fits.
        if display_ion < GUEST_MIN_DISPLAY_PX:
            grow = GUEST_MIN_DISPLAY_PX - display_ion
            display_ion += grow
            if display_hydrated > 0:
                display_hydrated += grow

        # Fit colour (green/amber/red) based on hydrated radius vs PLD —
        # used as the ion's outline, so the fit verdict is still visible
        # at a glance even though the fill below is element-specific.
        if effective_ang <= self._pore_fit_ang * 0.80:
            fit_color = "#3FB950"
        elif effective_ang <= self._pore_fit_ang:
            fit_color = "#D29922"
        else:
            fit_color = "#F85149"

        # Fill colour is element-specific (same palette the metal corner
        # balls use) so switching the guest ion — e.g. Na+ -> K+, both of
        # which "fit comfortably" — visibly changes the ball's colour
        # instead of always rendering the same fit-status colour.
        element_symbol = re.match(r"[A-Za-z]+", self.guest_ion or "")
        element_symbol = element_symbol.group(0) if element_symbol else ""
        ion_fill, ion_text_col = ATOM_COLORS.get(element_symbol, DEFAULT_ATOM_COLOR)

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
        # Fill = element colour (identifies *which* ion this is).
        # Outline = fit colour (identifies whether it fits the pore).
        t.penup(); t.goto(center_x, center_y - display_ion)
        t.pendown()
        t.pencolor(fit_color); t.pensize(3)
        t.fillcolor(ion_fill)
        t.begin_fill(); t.circle(display_ion); t.end_fill()
        t.penup()

        # Label always drawn — GUEST_MIN_DISPLAY_PX above guarantees the
        # ball is big enough to hold at least a small label.
        fs = max(6, int(display_ion * 0.55))
        t.goto(center_x, center_y - fs * LABEL_Y_FRACTION)
        t.pencolor(ion_text_col)
        t.write(self.guest_ion, align="center", font=("Arial", fs, "bold"))

        # Remember the lowest point this guest ion reaches on screen so
        # the pore-fit readout text (drawn below the cube) can avoid it.
        self._guest_bottom_y = center_y - max(display_ion, display_hydrated)

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

        # Start the readout below whichever is lower: the cube/molecule
        # itself, or the guest ion ball (large "TOO LARGE" ions and
        # hydration shells can bulge below the molecule's own footprint
        # and would otherwise overlap the first line(s) of text).
        structure_bottom_y = cube_cy - sq_size / 2 - self.metal_r
        guest_bottom_y = getattr(self, "_guest_bottom_y", structure_bottom_y)
        bottom_y = min(structure_bottom_y, guest_bottom_y) - 30
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
        t.fillcolor(self.metal_fill if not small else self._dim_color(self.metal_fill, 0.55))
        t.begin_fill(); t.circle(r); t.end_fill()
        t.penup()

        # Label every corner, front and back — previously the back (small)
        # cube corners were left unlabeled entirely.
        if self.metal_charge > 0:
            suffix = "+" if self.metal_charge == 1 else f"+{self.metal_charge}"
        elif self.metal_charge < 0:
            suffix = "-" if self.metal_charge == -1 else f"{self.metal_charge}"
        else:
            suffix = ""
        fs = max(7, int(r * 0.70))
        t.goto(x, y - fs * LABEL_Y_FRACTION)
        t.pencolor(self.metal_text if not small else self._dim_color(self.metal_text, 0.6))
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