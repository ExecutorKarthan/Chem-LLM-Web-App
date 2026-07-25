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
from ring_utils import RingFinder
from turtle_renderer import (
    ATOM_COLORS, BASE_RADII, DEFAULT_ATOM_COLOR,
    LABEL_Y_FRACTION, LABEL_FONT_SCALE, LABEL_MIN_RADIUS
)
# MOF_DB is imported further down, right where it's used/documented.

# ─────────────────────────────────────────────────────────────────────────────
# TUNING CONSTANTS  — adjust these to change the look
# ─────────────────────────────────────────────────────────────────────────────

# Fallback pore diameter (Å) used when the MOF is not found in MOF_DB.
MOF_PORE_DIAMETER_FALLBACK = 10.0

# Pixels per Angstrom — controls the overall physical size on screen.
# Increase to zoom in; decrease to zoom out.
PX_PER_ANG = 28.0

# ── MOF database: identifier -> (LCD_Å, PLD_Å, metal_types) ──────────────
from mof_data import MOF_DB

# Atom scale for linker structures inside the MOF diagram.
# Relative to BASE_RADII from turtle_renderer.
LINKER_ATOM_SCALE = 0.30

# Per-face scale multipliers for the cube (relative to LINKER_ATOM_SCALE).
FRONT_LINKER_SCALE = 1.00   # front face — reference size
DEPTH_LINKER_SCALE = 0.90   # z-axis struts — slightly smaller
BACK_LINKER_SCALE  = 0.70   # back face — furthest away, smallest

# Fraction of the edge the linker occupies (leaves gap near metal balls).
LINKER_INSET = 0.82

# Guest ion + hydration shell display scale.
GUEST_DISPLAY_SCALE = 0.60

# Minimum on-screen radius (px) for the bare guest ion ball.
GUEST_MIN_DISPLAY_PX = 9

# Fixed angstrom-to-pixel reference for guest ion / hydration shell sizing
# at mol_scale == 1, tied to the SAME per-atom scale factor as everything
# else (self._mol_scale) rather than to this linker's own drawn square
# size (_pore_r_px / _pore_fit_ang). The old approach derived px-per-Å
# from how big THIS linker's schematic happened to be drawn, so a large
# multi-armed linker (bigger square panel) made the exact same real ion
# radius balloon to 1.5x+ the size it'd draw at for a small linker, with
# nothing about the ion itself having changed. Calibrated so a typical
# small linker at scale=1.0 draws the same size hydration shell as before.
GUEST_PX_PER_ANGSTROM = 54.0

# Hydration shell fill/outline colors — single source of truth shared by
# _draw_guest_ion (the actual drawing) and get_legend_entries (the key),
# so the legend swatch can never fall out of sync with what's on screen.
HYDRATION_SHELL_COLOR = "#4A90D9"
HYDRATION_SHELL_OUTLINE = "#2A6099"

# Extra horizontal breathing room between the square-SBU panel and the cube panel.
PANEL_GAP_PX = 70

# How far back the cabinet-projection back face sits.
DEPTH_STRUT_FACTOR = 1.55

# ── Canvas auto-fit ──────────────────────────────────────────────────────
# The square SBU panel and the cube panel are drawn side by side, and their
# combined width scales directly with the linker's own (now geometrically
# correct, post-layout-fix) bounding box - a big multi-ring linker is
# legitimately bigger on screen than a small one. Rather than fixing one
# canvas size and letting large structures run off-page, we size the
# canvas to the structure (within a sensible min/max) and, only once a
# structure is too big even for the max canvas, scale the whole drawing
# down so it still fits. See MOFRenderer._auto_fit() / _footprint_at_scale().
MIN_CANVAS_WIDTH  = 520.0
MIN_CANVAS_HEIGHT = 380.0
MAX_CANVAS_WIDTH  = 950.0
MAX_CANVAS_HEIGHT = 620.0
CANVAS_MARGIN_PX  = 50.0   # breathing room added around the measured footprint
MIN_AUTO_SCALE    = 0.35   # never shrink a structure below this fraction

# ─────────────────────────────────────────────────────────────────────────────
# DERIVED — do not edit these
# ─────────────────────────────────────────────────────────────────────────────
def _pore_driven_side(pore_diameter_ang, scale=1.0):
    return (pore_diameter_ang / math.sqrt(2)) * PX_PER_ANG * scale


# ─────────────────────────────────────────────────────────────────────────────
# LINKER FRAGMENT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
_PURE_ION_FRAGMENT_RE = re.compile(r"^(\[[^\[\]]+\])+$")


def _split_identifier_fragments(identifier):
    return [f for f in identifier.split(".") if f.strip()]


def _is_pure_ion_fragment(fragment):
    return bool(_PURE_ION_FRAGMENT_RE.match(fragment.strip()))


def _select_linker_fragment(identifier):
    fragments = _split_identifier_fragments(identifier)
    candidates = [f for f in fragments if not _is_pure_ion_fragment(f)]
    if not candidates:
        return identifier

    best_frag, best_count = candidates[0], -1
    for frag in candidates:
        try:
            count = len(SmilesParser(frag).parse().atoms)
        except Exception:
            continue
        if count > best_count:
            best_frag, best_count = frag, count
    return best_frag


def _lookup_mof(linker_smiles, metal):
    if linker_smiles in MOF_DB:
        return MOF_DB[linker_smiles][:2]

    candidates = [
        f"{linker_smiles}.[{metal}]",
        f"[{metal}].{linker_smiles}",
        f"[{metal}][{metal}].{linker_smiles}",
        f"{linker_smiles}.[{metal}][{metal}]",
    ]
    for cand in candidates:
        if cand in MOF_DB:
            return MOF_DB[cand][:2]

    best = None
    for key, (lcd, pld, metals) in MOF_DB.items():
        if linker_smiles in key and metal in metals.split(","):
            if best is None or len(key) < len(best[0]):
                best = (key, lcd, pld)
    if best:
        return best[1], best[2]
    return None


class MOFRenderer:

    def __init__(self, turtle_obj, metal, linker_smiles,
             cx=0, cy=0, scale=1.0, metal_charge=0, guest_ion=None, guest_ion_metadata = None, mof_id=None):
        self.t            = turtle_obj
        self.metal        = metal
        self.metal_charge = metal_charge
        self.linker_smiles = linker_smiles
        self.cx           = cx
        self.cy           = cy
        self.guest_ion    = guest_ion

        if mof_id and mof_id in MOF_DB:
            self.data = MOF_DB[mof_id]
        else:
            self.data = self._fuzzy_lookup(metal, linker_smiles)

        # ── Step 1: parse and layout linker (scale-independent) ───────────
        render_smiles = _select_linker_fragment(linker_smiles)
        self.linker_mol = SmilesParser(render_smiles).parse()
        LayoutEngine(self.linker_mol).layout()
        self._center_linker()

        # Rings where every member atom is aromatic get a delocalized-pi
        # circle drawn inside them at render time, instead of (or in
        # addition to) explicit double bonds — see _draw_aromatic_circles.
        self._aromatic_rings = [
            ring for ring in RingFinder(self.linker_mol).find_rings()
            if ring and all(getattr(a, 'aromatic', False) for a in ring)
        ]

        xs = [a.x for a in self.linker_mol.atoms]
        ys = [a.y for a in self.linker_mol.atoms]
        if not xs or not ys:
            xs, ys = [0.0], [0.0]
        self._linker_raw_w = max(xs) - min(xs)
        self._linker_raw_h = max(ys) - min(ys)

        # ── Step 2: auto-fit — decide how much to scale the whole drawing
        # and what canvas size to request, based on how big this specific
        # linker's real geometry is. ───────────────────────────────────────
        self.scale, self.canvas_width, self.canvas_height = self._auto_fit(scale, metal)

        # ── Step 3: everything below derives from the FINAL, auto-fit
        # scale — mol_scale, metal radius, square side. ───────────────────
        self._mol_scale = LINKER_ATOM_SCALE * self.scale
        atom_pad = max(BASE_RADII.values()) * self._mol_scale
        self._linker_half_w = self._linker_raw_w / 2 * self._mol_scale + atom_pad
        self._linker_half_h = self._linker_raw_h / 2 * self._mol_scale + atom_pad

        self.metal_r = max(BASE_RADII.get(metal, 28) * self._mol_scale * 2.2,
                           14 * self.scale)
        self.metal_fill, self.metal_text = ATOM_COLORS.get(metal, DEFAULT_ATOM_COLOR)

        self._sq_size = self._linker_half_w * 2 + 2 * self.metal_r

        # ── Step 4: pore data ────────────────────────────────────────────
        if mof_id and mof_id in MOF_DB:
            self._lcd_ang, self._pld_ang, _ = MOF_DB[mof_id] 
        else:
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
            self._guest_ionic_ang = guest_ion_metadata[0]
            self._guest_hydrated_ang = guest_ion_metadata[1]
            self._guest_verified = guest_ion_metadata[2]

    # ── Canvas auto-fit ──────────────────────────────────────────────────

    def _footprint_at_scale(self, scale, metal):
        """
        Re-derives just the sizes needed to estimate the total on-screen
        footprint (square SBU panel + cube panel, side by side) at a given
        scale, without touching self or the turtle. Mirrors the same
        formulas _render()/_draw_cube() use for panel placement.
        """
        mol_scale = LINKER_ATOM_SCALE * scale
        atom_pad = max(BASE_RADII.values()) * mol_scale
        linker_half_w = self._linker_raw_w / 2 * mol_scale + atom_pad
        linker_half_h = self._linker_raw_h / 2 * mol_scale + atom_pad
        metal_r = max(BASE_RADII.get(metal, 28) * mol_scale * 2.2, 14 * scale)
        sq_size = linker_half_w * 2 + 2 * metal_r

        panel_half_w = sq_size / 2 + metal_r + linker_half_h
        gap = max(sq_size * 0.45, PANEL_GAP_PX * scale)

        total_width = 4 * panel_half_w + gap
        depth_dy = sq_size * 0.28 * DEPTH_STRUT_FACTOR
        total_height = sq_size + 2 * metal_r + depth_dy + 40  # label/margin allowance

        return total_width, total_height

    def _auto_fit(self, requested_scale, metal):
        """
        Returns (final_scale, canvas_width, canvas_height). Small
        structures get a canvas sized to fit them (within a sensible
        min/max) at their requested scale unchanged. Structures too big
        even for the max canvas get scaled down (never below
        MIN_AUTO_SCALE) so they still fit rather than running off-page.
        """
        natural_w, natural_h = self._footprint_at_scale(requested_scale, metal)
        padded_w = natural_w + CANVAS_MARGIN_PX
        padded_h = natural_h + CANVAS_MARGIN_PX

        if padded_w <= MAX_CANVAS_WIDTH and padded_h <= MAX_CANVAS_HEIGHT:
            canvas_w = max(MIN_CANVAS_WIDTH, padded_w)
            canvas_h = max(MIN_CANVAS_HEIGHT, padded_h)
            return requested_scale, canvas_w, canvas_h

        fit = min(
            (MAX_CANVAS_WIDTH - CANVAS_MARGIN_PX) / natural_w,
            (MAX_CANVAS_HEIGHT - CANVAS_MARGIN_PX) / natural_h,
        )
        fit = max(fit, MIN_AUTO_SCALE)
        return requested_scale * fit, MAX_CANVAS_WIDTH, MAX_CANVAS_HEIGHT

    def _center_linker(self):
        atoms = self.linker_mol.atoms
        if not atoms:
            return

        best_pair, best_dist2 = None, -1.0
        for i in range(len(atoms)):
            for j in range(i + 1, len(atoms)):
                dx = atoms[i].x - atoms[j].x
                dy = atoms[i].y - atoms[j].y
                d2 = dx * dx + dy * dy
                if d2 > best_dist2:
                    best_dist2, best_pair = d2, (atoms[i], atoms[j])

        if best_pair is not None and best_dist2 > 1e-6:
            a, b = best_pair
            long_angle = math.atan2(b.y - a.y, b.x - a.x)
            c, s = math.cos(-long_angle), math.sin(-long_angle)
            for atom in atoms:
                x, y = atom.x, atom.y
                atom.x = x * c - y * s
                atom.y = x * s + y * c

        xs = [a.x for a in atoms]
        ys = [a.y for a in atoms]
        cx = (max(xs) + min(xs)) / 2
        cy = (max(ys) + min(ys)) / 2
        for a in atoms:
            a.x -= cx
            a.y -= cy

    # ── Public overloads ──────────────────────────────────────────────────────

    def draw(self):
        self._render(linker_mode=True, guest_in_square=False, guest_in_cube=True)

    def draw_with_guest(self):
        self._render(linker_mode=True, guest_in_square=True, guest_in_cube=True)

    def draw_without_guest(self):
        self._render(linker_mode=True, guest_in_square=False, guest_in_cube=False)

    def draw_simple(self):
        self._render(linker_mode=False, guest_in_square=False, guest_in_cube=True)

    def draw_simple_with_guest(self):
        self._render(linker_mode=False, guest_in_square=True, guest_in_cube=True)

    def draw_simple_without_guest(self):
        self._render(linker_mode=False, guest_in_square=False, guest_in_cube=False)

    # ── Internal dispatcher ───────────────────────────────────────────────────

    def _render(self, linker_mode, guest_in_square, guest_in_cube):
        s   = self._sq_size
        sq_half_w   = s / 2 + self.metal_r + self._linker_half_h
        cube_half_w = s / 2 + self.metal_r + self._linker_half_h

        gap = max(s * 0.45, PANEL_GAP_PX * self.scale)

        sq_cx = self.cx - gap / 2 - sq_half_w
        cb_cx = self.cx + gap / 2 + cube_half_w

        if linker_mode:
            self._draw_square(sq_cx, self.cy, s, show_guest=guest_in_square)
            self._draw_cube(cb_cx, self.cy, s, show_guest=guest_in_cube)
        else:
            self._draw_square_simple(sq_cx, self.cy, s, show_guest=guest_in_square)
            self._draw_cube_simple(cb_cx, self.cy, s, show_guest=guest_in_cube)

    # ── Square SBU — linker mode ──────────────────────────────────────────────

    def _draw_square(self, cx, cy, side, show_guest=False):
        h       = side / 2
        corners = [(cx+h, cy+h), (cx-h, cy+h), (cx-h, cy-h), (cx+h, cy-h)]
        sc      = self._face_scale(side) * FRONT_LINKER_SCALE
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
        front, back = self._cube_corners(cx, cy, side)
        fs = self._face_scale() * FRONT_LINKER_SCALE
        ds = self._face_scale() * DEPTH_LINKER_SCALE
        bs = self._face_scale() * BACK_LINKER_SCALE

        # ── Layer 1: back face linkers + back metals ──────────────────────
        for i, j in [(0,1),(1,2),(2,3),(3,0)]:
            self._draw_linker_between(back[i], back[j], alpha=0.38, scale_override=bs)
        for x, y in back:
            self._draw_metal(x, y, small=True)

        # ── Layer 2: left/distal depth struts ─────────────────────────────
        for i in [1, 2]:
            self._draw_linker_between(back[i], front[i], alpha=0.55, scale_override=ds)

        # ── Layer 3: guest ion ────────────────────────────────────────────
        if show_guest and self.guest_ion:
            vis_cx, vis_cy = self._cube_visual_center(cx, cy, side)
            self._draw_guest_ion(vis_cx, vis_cy)

        # ── Layer 4: right/proximal depth struts ──────────────────────────
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

        # ── Layer 2: left/distal depth struts ─────────────────────────────
        self.t.pensize(1)
        self.t.pencolor(dim)
        for i in [1, 2]:
            self._line(back[i][0], back[i][1],
                       front[i][0], front[i][1])

        # ── Layer 3: guest ion ────────────────────────────────────────────
        if show_guest and self.guest_ion:
            vis_cx, vis_cy = self._cube_visual_center(cx, cy, side)
            self._draw_guest_ion(vis_cx, vis_cy)

        # ── Layer 4: right/proximal depth struts ──────────────────────────
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
        return self._mol_scale

    def _cube_corners(self, cx, cy, side):
        h  = side / 2
        dx = side * 0.38 * DEPTH_STRUT_FACTOR
        dy = side * 0.28 * DEPTH_STRUT_FACTOR
        front = [(cx+h, cy+h), (cx-h, cy+h), (cx-h, cy-h), (cx+h, cy-h)]
        back  = [(x+dx, y+dy) for x, y in front]
        return front, back

    def _cube_visual_center(self, cx, cy, side):
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
        t.pensize(1)

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

        mol_scale = scale_override if scale_override is not None \
                    else self._mol_scale

        mx, my = (x1+x2)/2, (y1+y2)/2

        # ── DEFENSIVE PLACEMARKER DRAWING ────────────────────────────────────
        # If the linker SMILES has no bonds (unparseable / empty SMILES fragment),
        # draw a stylized 3D shaded rod instead of leaving an empty canvas.
        if not self.linker_mol.bonds:
            sx1, sy1, sx2, sy2 = self._trim(x1, y1, x2, y2, self.metal_r, self.metal_r)
            
            # Thick background/shadow rod
            self.t.pensize(max(2, 10 * mol_scale * alpha))
            self.t.pencolor(self._dim_color("#B0B8C0", alpha))
            self._line(sx1, sy1, sx2, sy2)
            
            # Shaded inner highlighting
            self.t.pensize(max(1, 3 * mol_scale * alpha))
            self.t.pencolor(self._dim_color("#E1E4E8", alpha))
            self._line(sx1, sy1, sx2, sy2)
            return
        # ─────────────────────────────────────────────────────────────────────

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

        self._draw_aromatic_circles(mx, my, angle, mol_scale, alpha)

        self.t.pensize(1)
        for atom in self.linker_mol.atoms:
            ax, ay = self._transform(atom.x, atom.y, mx, my, angle, mol_scale)
            r      = BASE_RADII.get(atom.symbol, 18) * mol_scale
            fill, _ = ATOM_COLORS.get(atom.symbol, DEFAULT_ATOM_COLOR)
            if alpha < 1.0:
                fill = self._dim_color(fill, alpha)
            self._draw_ball(ax, ay, r, fill)
            if r >= LABEL_MIN_RADIUS * 0.8:
                fs = self._fit_font(atom.symbol, r)
                if fs >= 5:
                    self._write_centered(ax, ay, atom.symbol, self._contrast_text_color(fill), fs)

    def _draw_aromatic_circles(self, mx, my, angle, mol_scale, alpha):
        """
        Draws an inscribed circle inside every ring where all member atoms
        are aromatic — the standard delocalized-pi-electron depiction.

        This is used instead of alternating single/double (Kekulé) bonds
        because assigning a specific Kekulé structure correctly requires
        solving a matching problem over the ring system, and getting it
        wrong would show a chemically misleading structure. The circle is
        unambiguous and correct regardless of substitution pattern or
        ring fusion, at the cost of not distinguishing bond orders within
        the ring visually.
        """
        if not self._aromatic_rings:
            return

        t = self.t
        color = self._dim_color("#707070", alpha) if alpha < 1.0 else "#707070"

        for ring in self._aromatic_rings:
            cx = sum(a.x for a in ring) / len(ring)
            cy = sum(a.y for a in ring) / len(ring)
            avg_r = sum(math.hypot(a.x - cx, a.y - cy) for a in ring) / len(ring)
            circle_r = avg_r * 0.62 * mol_scale
            if circle_r < 2:
                continue

            px, py = self._transform(cx, cy, mx, my, angle, mol_scale)
            t.penup(); t.goto(px, py - circle_r); t.pendown()
            t.pencolor(color)
            t.pensize(max(1, 1.5 * mol_scale * alpha))
            t.circle(circle_r)
            t.penup()
        t.pensize(1)

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
        if self._guest_ionic_ang is None:
            return

        ionic_ang    = self._guest_ionic_ang
        hydrated_ang = self._guest_hydrated_ang
        effective_ang = hydrated_ang if hydrated_ang is not None else ionic_ang

        px_per_ang       = GUEST_PX_PER_ANGSTROM * self._mol_scale
        hydrated_ang_eff = hydrated_ang if hydrated_ang else ionic_ang
        true_hyd_px      = hydrated_ang_eff * px_per_ang
        true_ion_px      = ionic_ang        * px_per_ang

        if effective_ang > self._pore_fit_ang:
            display_hydrated = true_hyd_px * 1.4
            display_ion      = true_ion_px * 1.4
        else:
            display_hydrated = true_hyd_px * GUEST_DISPLAY_SCALE
            display_ion      = true_ion_px * GUEST_DISPLAY_SCALE

        if display_ion < GUEST_MIN_DISPLAY_PX:
            grow = GUEST_MIN_DISPLAY_PX - display_ion
            display_ion += grow
            if display_hydrated > 0:
                display_hydrated += grow

        element_symbol = re.match(r"[A-Za-z]+", self.guest_ion or "")
        element_symbol = element_symbol.group(0) if element_symbol else ""
        ion_fill, _ = ATOM_COLORS.get(element_symbol, DEFAULT_ATOM_COLOR)

        t = self.t

        if hydrated_ang is not None and display_hydrated > display_ion + 2:
            t.penup(); t.goto(center_x, center_y - display_hydrated)
            t.pendown()
            t.pencolor(HYDRATION_SHELL_OUTLINE); t.pensize(1)
            t.fillcolor(HYDRATION_SHELL_COLOR)
            t.begin_fill(); t.circle(display_hydrated); t.end_fill()
            t.penup()

        t.penup(); t.goto(center_x, center_y - display_ion)
        t.pendown()
        t.pencolor("#555555"); t.pensize(1)
        t.fillcolor(ion_fill)
        t.begin_fill(); t.circle(display_ion); t.end_fill()
        t.penup()

        fs = max(6, int(display_ion * 0.55))
        t.goto(center_x, center_y - fs * LABEL_Y_FRACTION)
        t.pencolor(self._contrast_text_color(ion_fill))
        t.write(self.guest_ion, align="center", font=("Arial", fs, "bold"))

        self._guest_bottom_y = center_y - max(display_ion, display_hydrated)

    def get_readout_lines(self):
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

        lines = [
            (f"Largest Cavity Diameter (LCD): {self._lcd_ang:.2f} \u00c5  \u2192  cavity radius {self._lcd_ang/2:.2f} \u00c5", "#8B949E"),
            (f"Pore Limiting Diameter (PLD): {self._pld_ang:.2f} \u00c5  \u2192  bottleneck radius {self._pld_ang/2:.2f} \u00c5", "#8B949E"),
        ]
        if effective_ang is not None:
            if ionic_ang is not None:
                lines.append((f"Guest ion radius (bare): {ionic_ang:.2f} \u00c5", "#8B949E"))
            if hydrated_ang is not None:
                lines.append((f"Guest ion radius (hydrated): {hydrated_ang:.2f} \u00c5  vs. PLD bottleneck {self._pore_fit_ang:.2f} \u00c5", HYDRATION_SHELL_COLOR))
            src_note = "Exp. verified" if "Experimental" in verified else "Est./unverified"
            lines.append((f"* {src_note} ion radii; pore from MOF_data.csv", "#6E7681"))

        return lines

    # ── Metal ball ────────────────────────────────────────────────────────────

    def _draw_metal(self, x, y, small=False):
        r = self.metal_r * (0.72 if small else 1.0)
        t = self.t
        fill = self.metal_fill if not small else self._dim_color(self.metal_fill, 0.55)
        t.penup(); t.goto(x, y-r); t.pendown()
        t.pencolor("#555555"); t.pensize(1)
        t.fillcolor(fill)
        t.begin_fill(); t.circle(r); t.end_fill()
        t.penup()

        if self.metal_charge > 0:
            suffix = "+" if self.metal_charge == 1 else f"+{self.metal_charge}"
        elif self.metal_charge < 0:
            suffix = "-" if self.metal_charge == -1 else f"{self.metal_charge}"
        else:
            suffix = ""
        fs = max(7, int(r * 0.70))
        t.goto(x, y - fs * LABEL_Y_FRACTION)
        t.pencolor(self._contrast_text_color(fill))
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

    def get_legend_entries(self):
        """
        Returns an ordered list of (symbol, fill_hex) for every distinct
        element actually present in this specific render — the linker's
        own atoms, the metal node, and the guest ion (if any) — deduping
        aromatic lowercase symbols (e.g. 'c') with their element ('C')
        since they share the same color. Metal first, then linker atoms
        in the order they appear, then the guest ion.

        Deliberately reads straight from ATOM_COLORS (the same table the
        drawing itself uses) rather than a separate hardcoded list, so
        the legend can't silently drift out of sync with what's drawn.
        """
        symbols = []
        seen = set()

        def add(sym):
            if not sym:
                return
            canonical = sym.upper() if sym in SmilesParser.AROMATIC else sym
            if canonical not in seen:
                seen.add(canonical)
                symbols.append(canonical)

        add(self.metal)
        for atom in self.linker_mol.atoms:
            add(atom.symbol)
        if self.guest_ion:
            m = re.match(r"[A-Za-z]+", self.guest_ion)
            if m:
                add(m.group(0))

        entries = []
        for sym in symbols:
            fill, _ = ATOM_COLORS.get(sym, DEFAULT_ATOM_COLOR)
            entries.append((sym, fill))

        # Matches the fill color _draw_guest_ion uses for the hydration
        # shell — kept as one literal here and referenced there too, so
        # if that color ever changes it only needs updating in one place.
        if self.guest_ion and self._guest_hydrated_ang is not None:
            entries.append(("Hydration Shell", HYDRATION_SHELL_COLOR))
        return entries

    @staticmethod
    def _contrast_text_color(fill_hex):
        h = fill_hex.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return "#1A1A1A" if luminance > 140 else "#FFFFFF"

    @staticmethod
    def _dim_color(hex_color, alpha):
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        r = int(r + (255-r)*(1-alpha))
        g = int(g + (255-g)*(1-alpha))
        b = int(b + (255-b)*(1-alpha))
        return f"#{r:02x}{g:02x}{b:02x}"


# ─────────────────────────────────────────────────────────────────────────────
# SKULPT COMPATIBILITY LAYER / BRIDGE
# ─────────────────────────────────────────────────────────────────────────────

def draw_lattice(metal, linker_smiles, mof_id=None, guest_ion=None, guest_ion_metadata = None, simple_mode=False):
    """
    Top-level wrapper function called by the UI Skulpt template string.
    Instantiates a Skulpt canvas turtle and maps parameters to the MOFRenderer object.
    """
    import turtle

    screen = turtle.Screen()
    # `speed(0)` below only skips the per-move animation delay — the
    # screen still repaints the canvas after every individual drawing
    # command by default (tracer defaults to on). A full cube has ~16
    # linker instances worth of atoms/bonds/labels plus metal balls and
    # the guest ion, so that's thousands of incremental repaints. Turning
    # tracer off batches everything into one paint at the end instead.
    try:
        screen.tracer(0, 0)
    except Exception:
        pass

    t = turtle.Turtle()
    t.speed(0)
    t.hideturtle()
    
    # TYPE-SAFE BOOLEAN COERCION:
    # Protects against Javascript passing strings like "false", "False", or "0".
    if isinstance(simple_mode, str):
        is_simple = simple_mode.strip().lower() in ("true", "1")
    else:
        is_simple = bool(simple_mode)
    
    renderer = MOFRenderer(
        turtle_obj=t,
        metal=str(metal).strip() if metal else "",
        linker_smiles=str(linker_smiles).strip() if linker_smiles else "",
        mof_id=mof_id, 
        guest_ion=guest_ion if guest_ion else None,
        guest_ion_metadata=guest_ion_metadata if guest_ion_metadata else None
    )

    # Best-effort: size the actual canvas to match what this structure
    # needs (renderer.canvas_width/height, computed in __init__). If
    # Skulpt's turtle module doesn't support a runtime Screen resize this
    # just silently no-ops — renderer.scale was already chosen so the
    # drawing fits within whatever canvas size the page gave it.
    try:
        screen.setup(renderer.canvas_width, renderer.canvas_height)
    except Exception:
        pass

    has_guest = renderer.guest_ion is not None

    # Emit a structured legend line for the UI to parse (see
    # SkulptDisplay.tsx's outf handler) — built from the same
    # ATOM_COLORS table the drawing itself uses, so it can't drift out
    # of sync with what's actually on the canvas. Printed before drawing
    # so it's still available even if the draw itself fails partway.
    legend = renderer.get_legend_entries()
    print("@@LEGEND@@" + ";".join(f"{sym}:{color}" for sym, color in legend))

    try:
        if is_simple:
            if has_guest:
                renderer.draw_simple_with_guest()
            else:
                renderer.draw_simple_without_guest()
        else:
            if has_guest:
                renderer.draw_with_guest()
            else:
                renderer.draw_without_guest()
    finally:
        # Re-assert the hidden state immediately before the final flush.
        # `t.hideturtle()` was already called right after creating `t`,
        # but with tracer(0)/update() batching everything into one final
        # repaint, the turtle cursor icon has been showing up at its last
        # position in that repaint — re-asserting it right here, as the
        # very last thing before the flush, is the reliable fix.
        try:
            t.hideturtle()
        except Exception:
            pass
        # Flush the whole drawing to the canvas in one paint. In a
        # `finally` so a partial/failed draw still shows whatever was
        # completed instead of leaving a blank canvas.
        try:
            screen.update()
        except Exception:
            pass