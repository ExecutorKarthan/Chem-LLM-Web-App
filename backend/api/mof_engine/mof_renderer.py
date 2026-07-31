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

# Minimum on-screen radius (px) for the bare guest ion ball.
GUEST_MIN_DISPLAY_PX = 9

# Fixed angstrom-to-pixel reference for guest ion / hydration shell sizing
# at mol_scale == 1, tied to the SAME per-atom scale factor as everything
# else (self._mol_scale) rather than to this linker's own drawn square
# size. Deriving it from the panel's own size was tried and reverted: a
# large multi-armed linker (bigger square panel) made the exact same real
# ion radius balloon to 1.5x+ the size it'd draw at for a small linker,
# with nothing about the ion itself having changed. This same fixed scale
# is also used for the dashed LCD/PLD pore-boundary reference circles
# drawn alongside the guest ion (see _draw_guest_ion) — using one shared
# scale for both is what makes "the guest is bigger than the real pore"
# a genuine, visible fact rather than two independently-sized elements
# that happen to be drawn near each other.
GUEST_PX_PER_ANGSTROM = 54.0

# Hydration shell fill/outline colors — single source of truth shared by
# _draw_guest_ion (the actual drawing) and get_legend_entries (the key),
# so the legend swatch can never fall out of sync with what's on screen.
HYDRATION_SHELL_COLOR = "#4A90D9"
HYDRATION_SHELL_OUTLINE = "#2A6099"

# Extra vertical breathing room between the square-SBU panel and the cube
# panel, now that they're stacked (square on top, cube below) instead of
# side by side.
PANEL_GAP_PX = 70

# Small breathing room above the square panel, purely aesthetic (no
# label text reserves space here anymore — see _draw_square /
# _draw_cube, which used to write a "Square SBU [Metal4]" / "MOF Cube
# [Metal8]" label above each panel. Those were removed: the numbers
# were just this schematic's fixed corner count (always 4 for the
# square, always 8 for the cube) mislabeled as if it were the metal's
# real coordination number, which has nothing to do with it and could
# easily be read as a chemistry claim the drawing wasn't actually
# making).
TOP_MARGIN_PX = 15

# How far back the cabinet-projection back face sits.
DEPTH_STRUT_FACTOR = 1.55

# ── Canvas auto-fit ──────────────────────────────────────────────────────
# The canvas is always exactly CANVAS_TARGET_WIDTH x CANVAS_TARGET_HEIGHT
# (the frontend overrides these to match the real container size — see
# SkulptDisplay.tsx's sizingPreamble). The canvas itself is never resized
# to match the structure; instead, the structure (square SBU panel
# stacked above the cube panel) is scaled — uniformly, so it's never
# stretched/distorted — to fit inside that fixed canvas: shrunk down if
# it would otherwise be too big to fit, or grown up if it comfortably
# fits with room to spare, so it isn't left small in a much bigger
# canvas. See MOFRenderer._auto_fit() / _footprint_at_scale().
#
# Earlier versions of this instead resized the *canvas* to match the
# structure (small structure -> small canvas) and relied on CSS to
# center a canvas that could be smaller than its container, with
# overflow:auto as a fallback for the rare oversized case. That
# combination is exactly what broke: a canvas larger than its
# container, centered via flexbox, gets its overflow clipped from the
# *start* in most browsers (not the end) — so the top (square) panel
# vanished while the bottom (cube) panel showed as scrolled-and-still-
# cut-off. A fixed-size canvas can't be smaller or larger than its
# container in the first place, which removes the failure mode
# entirely rather than patching around it again.
CANVAS_TARGET_WIDTH  = 950.0
CANVAS_TARGET_HEIGHT = 620.0
CANVAS_MARGIN_PX     = 50.0   # breathing room added around the measured footprint

# MIN_AUTO_SCALE is intentionally very permissive (not a practical
# floor): "never cut off" is an unconditional requirement now, so an
# extremely large structure should render very small rather than clip.
# This just guards against a literal zero/negative scale in a
# pathological edge case.
MIN_AUTO_SCALE = 0.05
MAX_AUTO_SCALE = 2.5   # never grow a structure beyond this multiple of its requested scale

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
    """Splits a dot-separated MOF identifier (metal(s) + linker, e.g.
    '[Cu][Cu].c1ccc(...)cc1') into its component SMILES fragments."""
    return [f for f in identifier.split(".") if f.strip()]


def _is_pure_ion_fragment(fragment):
    """True if a fragment is nothing but bracket-atom ions (e.g. '[Cu]'
    or '[Cu][Cu]') with no organic linker structure in it."""
    return bool(_PURE_ION_FRAGMENT_RE.match(fragment.strip()))


def _select_linker_fragment(identifier):
    """
    Picks which fragment of a composite identifier is the actual
    organic linker to render (as opposed to the metal ion fragments
    that make up the rest of the formula). Fragments that are pure ions
    are excluded outright; among what's left, the fragment that parses
    to the most atoms wins, on the assumption that the real linker is
    the largest organic piece — this matters because some identifiers
    contain multiple non-ion fragments (e.g. a linker plus a solvent
    molecule) and only the linker should be drawn.
    """
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
    """
    Finds (LCD, PLD) pore dimensions for a linker+metal pair by trying
    progressively looser matches against MOF_DB, since the exact
    identifier string used elsewhere in the app doesn't always match
    the DB's key formatting:
      1. The linker SMILES alone, in case it's already a full DB key.
      2. A few common ways of combining it with the metal as a
         dot-separated formula (metal first/last, single/double metal).
      3. Any DB key that contains the linker SMILES as a substring and
         lists this metal among its compatible metals — preferring the
         shortest such key, on the assumption that a shorter matching
         key is a closer/more specific match than a longer one that
         merely happens to contain the same substring.
    Returns None if nothing matches by any of these.
    """
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

        # NOTE: MOF_DB lookup by (metal, linker) happens once, correctly,
        # in the "Step 4: pore data" block below via the module-level
        # _lookup_mof(linker_smiles, metal) — there used to be a second,
        # earlier attempt at this same lookup here that called a
        # self._fuzzy_lookup(...) method that was never defined on this
        # class (an AttributeError waiting to happen on any mof_id miss),
        # and whose result (self.data) was never actually read anywhere.
        # Removed as dead code rather than fixed, since Step 4 already
        # does this job.

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

        # ── Step 2: pore + guest ion data (scale-independent) ──────────────
        # Looked up before auto-fit runs (not after, as in an earlier
        # version of this code) so that _footprint_at_scale can reserve
        # enough room for a guest ion that's genuinely bigger than the
        # pore — see _draw_guest_ion for why that's now drawn to true
        # scale rather than an arbitrary fixed size.
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

        self._guest_ionic_ang    = None
        self._guest_hydrated_ang = None
        self._guest_verified     = None
        if guest_ion:
            self._guest_ionic_ang = guest_ion_metadata[0]
            self._guest_hydrated_ang = guest_ion_metadata[1]
            self._guest_verified = guest_ion_metadata[2]

        # ── Step 3: auto-fit — decide how much to scale the whole drawing
        # and what canvas size to request, based on how big this specific
        # linker's real geometry is (and, now, how big the guest ion is
        # relative to the real pore, if one is selected). ─────────────────
        self.scale, self.canvas_width, self.canvas_height = self._auto_fit(scale, metal)

        # ── Step 4: everything below derives from the FINAL, auto-fit
        # scale — mol_scale, metal radius, square side. ───────────────────
        self._mol_scale = LINKER_ATOM_SCALE * self.scale
        atom_pad = max(BASE_RADII.values()) * self._mol_scale
        self._linker_half_w = self._linker_raw_w / 2 * self._mol_scale + atom_pad
        self._linker_half_h = self._linker_raw_h / 2 * self._mol_scale + atom_pad

        self.metal_r = max(BASE_RADII.get(metal, 28) * self._mol_scale * 2.2,
                           14 * self.scale)
        self.metal_fill, self.metal_text = ATOM_COLORS.get(metal, DEFAULT_ATOM_COLOR)

        self._sq_size = self._linker_half_w * 2 + 2 * self.metal_r

        # ── Step 5: shared guest-ion / pore-boundary pixel scale. Both the
        # guest ion (+ hydration shell) and the new LCD/PLD boundary
        # circles drawn in _draw_guest_ion use this SAME conversion, which
        # is deliberately NOT derived from this panel's own drawn size
        # (_sq_size / metal_r) — see GUEST_PX_PER_ANGSTROM's comment for
        # why: a linker-size-derived scale previously made the exact same
        # real ion balloon up for a bigger linker, with nothing about the
        # ion having changed. Using one fixed, linker-independent scale
        # for both the ion and the boundary circles keeps ion sizing
        # consistent across different MOFs while still making "guest
        # bigger than the real pore" a genuine, visible fact within any
        # single rendering (see _draw_guest_ion). self._pore_r_px is not
        # used for guest-ion scaling for that reason; it's kept only as
        # a generically useful "how much room this panel's own drawn
        # geometry leaves" measurement, currently unused elsewhere.
        self._pore_r_px = max(self._sq_size / 2 - self.metal_r, 0)
        self._guest_px_per_ang = GUEST_PX_PER_ANGSTROM * self._mol_scale

    # ── Canvas auto-fit ──────────────────────────────────────────────────

    def _footprint_at_scale(self, scale, metal):
        """
        Re-derives just the sizes needed to estimate the total on-screen
        footprint (square SBU panel stacked above the cube panel) at a
        given scale, without touching self or the turtle. Mirrors the
        same formulas _render()/_draw_cube() use for panel placement.

        The cube panel isn't symmetric around its own center the way the
        square panel is: _cube_corners() offsets the back face by
        (dx, dy) from the front face, so the cube's true bounding box
        extends dx further to the right and dy further upward than a
        flat square of the same side length would. That asymmetry has to
        be counted here (and mirrored in _render()'s cube positioning),
        or the canvas gets sized/positioned as if the cube were as
        compact as the square and the far side of the cube ends up
        clipped.
        """
        mol_scale = LINKER_ATOM_SCALE * scale
        atom_pad = max(BASE_RADII.values()) * mol_scale
        linker_half_w = self._linker_raw_w / 2 * mol_scale + atom_pad
        linker_half_h = self._linker_raw_h / 2 * mol_scale + atom_pad
        metal_r = max(BASE_RADII.get(metal, 28) * mol_scale * 2.2, 14 * scale)
        sq_size = linker_half_w * 2 + 2 * metal_r

        h = sq_size / 2
        dx = sq_size * 0.38 * DEPTH_STRUT_FACTOR
        dy = sq_size * 0.28 * DEPTH_STRUT_FACTOR

        # Each linker strut is rotated to match whichever edge it's drawn
        # on (see _draw_linker_between), so its perpendicular thickness
        # (linker_half_h) bulges outward beyond that edge - horizontally
        # past the left/right (vertical) edges, and vertically past the
        # top/bottom (horizontal) edges. Both panels need the
        # linker_half_h term on BOTH axes, not just width: a simple
        # rod-shaped linker has small perpendicular thickness so this was
        # easy to miss, but a branched/wide linker's real thickness can
        # be substantial and was bulging straight past an un-padded
        # bottom edge before this fix.
        sq_half_w = h + metal_r + linker_half_h
        sq_panel_h = 2 * (h + metal_r + linker_half_h)

        # Cube panel: right/top extents get the extra dx/dy from the
        # back-face offset; left/bottom extents don't.
        cube_half_w = h + dx / 2 + metal_r + linker_half_h
        cube_panel_h = 2 * (h + metal_r + linker_half_h) + dy

        # If a guest ion is selected, _draw_guest_ion draws it (and its
        # hydration shell), plus dashed LCD/PLD boundary circles, using a
        # fixed, linker-independent px-per-angstrom scale (see
        # GUEST_PX_PER_ANGSTROM / self._guest_px_per_ang) rather than one
        # derived from this panel's own drawn size. That means a guest
        # (or the LCD boundary itself, for a genuinely large pore) can be
        # bigger than the linker/metal ring drawn here, deliberately
        # overflowing it (that's the honest point being made when a guest
        # doesn't fit) — but the CANVAS still has to be big enough to show
        # that overflow in full rather than clipping it.
        if self._guest_ionic_ang is not None:
            px_per_ang_candidate = GUEST_PX_PER_ANGSTROM * mol_scale
            effective_guest_ang = self._guest_hydrated_ang or self._guest_ionic_ang
            needed_r_px = max(
                effective_guest_ang * px_per_ang_candidate,
                self._pore_r_ang * px_per_ang_candidate,
            )
            sq_half_w = max(sq_half_w, needed_r_px)
            sq_panel_h = max(sq_panel_h, 2 * needed_r_px)
            cube_half_w = max(cube_half_w, needed_r_px)
            cube_panel_h = max(cube_panel_h, 2 * needed_r_px)

        total_width = max(2 * sq_half_w, 2 * cube_half_w)
        vgap = max(sq_size * 0.35, PANEL_GAP_PX * scale * 0.6)
        total_height = TOP_MARGIN_PX + sq_panel_h + vgap + cube_panel_h

        return total_width, total_height

    def _auto_fit(self, requested_scale, metal):
        """
        Returns (final_scale, canvas_width, canvas_height). The canvas
        dimensions returned are always exactly (CANVAS_TARGET_WIDTH,
        CANVAS_TARGET_HEIGHT) — this method never resizes the canvas
        itself, only the drawing's scale, so it fits inside that fixed
        canvas: shrunk down (never below MIN_AUTO_SCALE) if the
        structure would otherwise be too big to fit, or grown up (never
        above MAX_AUTO_SCALE) if it comfortably fits with room to
        spare, so it isn't left small inside a much bigger canvas.
        """
        natural_w, natural_h = self._footprint_at_scale(requested_scale, metal)

        fit = min(
            (CANVAS_TARGET_WIDTH - CANVAS_MARGIN_PX) / natural_w,
            (CANVAS_TARGET_HEIGHT - CANVAS_MARGIN_PX) / natural_h,
        )
        fit = max(fit, MIN_AUTO_SCALE)
        fit = min(fit, MAX_AUTO_SCALE)

        return requested_scale * fit, CANVAS_TARGET_WIDTH, CANVAS_TARGET_HEIGHT

    def _center_linker(self):
        """
        Orients the linker so its longest atom-to-atom span runs
        horizontally, then centers it on the origin. The rotation step
        finds the two atoms farthest apart (an approximation of the
        molecule's principal axis, cheap to compute and good enough for
        a schematic diagram) and rotates the whole molecule by the
        negative of that pair's angle so the span lies along the x-axis.
        This keeps linkers drawn consistently "lying down" across the
        square SBU and cube panels, rather than at whatever arbitrary
        angle the layout engine's DFS happened to produce.
        """
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
        s  = self._sq_size
        h  = s / 2
        dx = s * 0.38 * DEPTH_STRUT_FACTOR
        dy = s * 0.28 * DEPTH_STRUT_FACTOR

        vgap = max(s * 0.35, PANEL_GAP_PX * self.scale * 0.6)

        sq_half_h          = h + self.metal_r + self._linker_half_h
        cube_half_h_bottom = h + self.metal_r + self._linker_half_h
        cube_half_h_top    = h + dy + self.metal_r + self._linker_half_h

        # Mirror _footprint_at_scale's guest-ion overflow accounting here
        # so the panels are actually spaced far enough apart in practice,
        # not just budgeted for in the canvas size. Uses the precise
        # per-call guest_in_square/guest_in_cube flags (unlike
        # _footprint_at_scale, which runs once during __init__ before any
        # particular draw_*() variant is chosen, so it conservatively
        # assumes a guest ion might appear in either panel).
        if self._guest_ionic_ang is not None:
            effective_guest_ang = self._guest_hydrated_ang or self._guest_ionic_ang
            needed_half_px = max(
                effective_guest_ang * self._guest_px_per_ang,
                self._pore_r_ang * self._guest_px_per_ang,
            )
            if guest_in_square:
                sq_half_h = max(sq_half_h, needed_half_px)
            if guest_in_cube:
                cube_half_h_bottom = max(cube_half_h_bottom, needed_half_px)
                cube_half_h_top = max(cube_half_h_top, needed_half_px)

        # Square panel above, cube panel below, split around self.cy with
        # vgap as the visual separation between the square's bottom edge
        # and the cube's top edge.
        sq_cx, sq_cy = self.cx, self.cy + vgap / 2 + sq_half_h

        # The cube's own (cx, cy) is defined as its FRONT face's center
        # (see _cube_corners), but the back face sits dx right / dy up
        # from that. Horizontally, that means centering the cube panel
        # in its slot requires nudging its front-face-center left by
        # dx/2 first — the same correction _cube_visual_center already
        # makes for guest-ion placement, mirrored here for the panel's
        # own bounding box (see _footprint_at_scale, which budgets width
        # using this same averaged dx/2 half-extent). Vertically no such
        # shift is needed: cube_half_h_top/cube_half_h_bottom already
        # measure the true top/bottom edges directly from the front-face
        # center, so placing cube_cy from cube_half_h_top alone lands
        # the top edge exactly at the intended slot boundary.
        cube_cx = self.cx - dx / 2
        cube_cy = self.cy - vgap / 2 - cube_half_h_top

        if linker_mode:
            self._draw_square(sq_cx, sq_cy, s, show_guest=guest_in_square)
            self._draw_cube(cube_cx, cube_cy, s, show_guest=guest_in_cube)
        else:
            self._draw_square_simple(sq_cx, sq_cy, s, show_guest=guest_in_square)
            self._draw_cube_simple(cube_cx, cube_cy, s, show_guest=guest_in_cube)

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
        hydrated_ang_eff = hydrated_ang if hydrated_ang else ionic_ang

        # Deliberately no drawn pore-boundary circle here: the guest ion
        # and hydration shell are drawn to true, honest scale (via
        # self._guest_px_per_ang — a fixed, linker-independent scale, see
        # GUEST_PX_PER_ANGSTROM's comment for why it's not derived from
        # this panel's own drawn size) purely to give an accurate sense
        # of relative size next to the linkers/metals. Whether that size
        # actually fits through the real pore is answered by the LCD/PLD
        # numbers in the readout panel, not by this drawing — adding an
        # explicit boundary line here would let someone read "fits/
        # doesn't fit" straight off the picture without ever looking at
        # the data.
        display_hydrated = hydrated_ang_eff * self._guest_px_per_ang
        display_ion      = ionic_ang        * self._guest_px_per_ang

        if display_ion < GUEST_MIN_DISPLAY_PX:
            # Very small ions (e.g. Li+) would otherwise render as a
            # near-invisible dot; grow both the ion and its hydration
            # shell by the same amount so the shell doesn't end up
            # smaller than the (now-enlarged) bare ion inside it. This is
            # purely a visibility floor (a few pixels at most) — it
            # doesn't distort the size relationship to the pore the way
            # the old fixed 1.4x/0.6x multipliers did.
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
            screen.tracer(1, 0)
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