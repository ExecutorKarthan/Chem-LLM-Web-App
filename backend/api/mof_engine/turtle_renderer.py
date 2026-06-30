import turtle
import math


# CPK color convention: (fill_color, text_color)
ATOM_COLORS = {
    "H":  ("#FFFFFF", "#333333"),
    "C":  ("#404040", "#FFFFFF"),
    "c":  ("#404040", "#FFFFFF"),
    "N":  ("#4466FF", "#FFFFFF"),
    "n":  ("#4466FF", "#FFFFFF"),
    "O":  ("#EE2211", "#FFFFFF"),
    "o":  ("#EE2211", "#FFFFFF"),
    "S":  ("#DDCC00", "#333333"),
    "s":  ("#DDCC00", "#333333"),
    "F":  ("#22BB44", "#FFFFFF"),
    "Cl": ("#22BB44", "#FFFFFF"),
    "Br": ("#994400", "#FFFFFF"),
    "I":  ("#6600AA", "#FFFFFF"),
    "P":  ("#FF8800", "#FFFFFF"),
    "p":  ("#FF8800", "#FFFFFF"),
    "Cu": ("#BB6600", "#FFFFFF"),
    "Zn": ("#7799AA", "#FFFFFF"),
    "Fe": ("#CC6633", "#FFFFFF"),
    "Co": ("#4477CC", "#FFFFFF"),
    "Ni": ("#44AA77", "#FFFFFF"),
    "Mn": ("#9933AA", "#FFFFFF"),
    "Pd": ("#AAAAAA", "#333333"),
    "Pt": ("#CCCCCC", "#333333"),
    "Ag": ("#AAAAAA", "#333333"),
    "Au": ("#DDAA00", "#333333"),
}

DEFAULT_ATOM_COLOR = ("#AABBCC", "#333333")

# Base radii — will be scaled at render time
BASE_RADII = {
    "H":  10,
    "C":  18, "c":  18,
    "N":  17, "n":  17,
    "O":  17, "o":  17,
    "S":  20, "s":  20,
    "F":  14,
    "Cl": 20,
    "Br": 22,
    "I":  24,
    "P":  19, "p":  19,
    "Cu": 22, "Zn": 21, "Fe": 21,
    "Co": 21, "Ni": 21, "Mn": 21,
    "Pd": 22, "Pt": 22,
    "Ag": 22, "Au": 22,
}

DEFAULT_BASE_RADIUS = 18

BOND_THICKNESS  = 5
DOUBLE_SPACING  = 6
TRIPLE_SPACING  = 6
LABEL_MIN_RADIUS = 8   # below this radius, skip drawing labels

# Cap-height fraction: Arial bold glyphs occupy this fraction of font_size.
# The visual centre of the glyph is at baseline + CAP_CENTER * font_size.
# Tweak if labels still drift up or down.
LABEL_CAP_CENTER = 0.36

# Total downward shift from baseline expressed as a fraction of font_size.
# baseline is at goto_y, rendered centre is at goto_y + CAP_CENTER * font_size.
# We want that centre at atom_y, so:  goto_y = atom_y - LABEL_Y_FRACTION * font_size
# Calibrated value: 0.36 (cap centre) + platform offset.
# Increase this number to move labels DOWN, decrease to move UP.
LABEL_Y_FRACTION = 0.85   # increase to move labels DOWN, decrease to move UP

# LABEL_FONT_SCALE: fraction of the inscribed square used for font size.
LABEL_FONT_SCALE = 0.60


METALS = {"Cu","Zn","Fe","Co","Ni","Mn","Pd","Pt","Ag","Au","Li","Na","K","Ca","Mg","Al"}

def _is_ionic_bond(bond):
    """
    True only when the bond looks genuinely ionic:
    at least one atom is a metal AND the other carries a formal charge.
    A charged non-metal bonded to another non-metal (e.g. [O-] in carboxylate)
    is still a covalent bond and should be drawn as a solid line.
    """
    a, b = bond.a, bond.b
    a_metal = a.symbol in METALS
    b_metal = b.symbol in METALS
    if not (a_metal or b_metal):
        return False   # neither is a metal → covalent
    # metal present: ionic if the other atom carries a charge
    if a_metal and b.charge != 0:
        return True
    if b_metal and a.charge != 0:
        return True
    return False


class TurtleRenderer:

    def __init__(self, mol, turtle_obj, offset_x=0, offset_y=0,
                 scale=1.0, mode="ball_stick"):
        self.mol       = mol
        self.t         = turtle_obj
        self.offset_x  = offset_x
        self.offset_y  = offset_y
        self.scale     = scale          # uniform scale applied to radii + positions
        self.mode      = mode

    # --------------------------------------------------------
    # PUBLIC: bounding box of the molecule in MOL-space
    # (before offset or scale — caller uses this for layout)
    # --------------------------------------------------------

    @staticmethod
    def effective_radius(atom):
        """
        Return the base radius for an atom, expanded if charged so the
        full label (symbol + charge) always fits at a readable size.
        This is used by both get_bounds (layout) and draw_atoms (rendering)
        so the grid allocates enough room for charged atoms.
        """
        symbol = atom.symbol
        base_r = BASE_RADII.get(symbol, DEFAULT_BASE_RADIUS)
        if atom.charge == 0:
            return base_r
        if atom.charge > 0:
            suffix = "+" if atom.charge == 1 else f"+{atom.charge}"
        else:
            suffix = "-" if atom.charge == -1 else f"{atom.charge}"
        label = symbol + suffix
        n_chars = max(len(label), 1)
        min_font = 11
        side_needed = min_font * 0.65 * n_chars / LABEL_FONT_SCALE
        min_r = side_needed / (math.sqrt(2) * 0.85)
        return max(base_r, min_r)

    @staticmethod
    def get_bounds(mol):
        """
        Returns (min_x, min_y, max_x, max_y) in molecule coordinates,
        expanded by each atom's base radius so the box includes the balls.
        """
        if not mol.atoms:
            return 0, 0, 0, 0
        min_x = min_y =  float("inf")
        max_x = max_y = -float("inf")
        for a in mol.atoms:
            r = TurtleRenderer.effective_radius(a)
            min_x = min(min_x, a.x - r)
            max_x = max(max_x, a.x + r)
            min_y = min(min_y, a.y - r)
            max_y = max(max_y, a.y + r)
        return min_x, min_y, max_x, max_y

    @staticmethod
    def center_molecule(mol):
        min_x, min_y, max_x, max_y = TurtleRenderer.get_bounds(mol)
        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        for a in mol.atoms:
            a.x -= cx
            a.y -= cy

    # --------------------------------------------------------
    # MAIN DRAW
    # --------------------------------------------------------

    def draw(self):
        self.draw_bonds()
        self._render_aromatic_rings()
        self.draw_atoms()

    # --------------------------------------------------------
    # BONDS
    # --------------------------------------------------------

    def draw_bonds(self):
        self.t.pensize(max(1, BOND_THICKNESS * self.scale))

        for bond in self.mol.bonds:
            a = bond.a
            b = bond.b

            x1 = a.x * self.scale + self.offset_x
            y1 = a.y * self.scale + self.offset_y
            x2 = b.x * self.scale + self.offset_x
            y2 = b.y * self.scale + self.offset_y

            r1 = BASE_RADII.get(a.symbol, DEFAULT_BASE_RADIUS) * self.scale
            r2 = BASE_RADII.get(b.symbol, DEFAULT_BASE_RADIUS) * self.scale

            sx1, sy1, sx2, sy2 = self._trim_bond(x1, y1, x2, y2, r1, r2)

            ionic = _is_ionic_bond(bond)

            if ionic:
                self._dotted_bond(sx1, sy1, sx2, sy2, color="#3366FF")
            elif bond.order == 1:
                self.t.pencolor("#888888")
                self._line(sx1, sy1, sx2, sy2)
            elif bond.order == 2:
                self.t.pencolor("#888888")
                self._double_bond(sx1, sy1, sx2, sy2)
            elif bond.order == 3:
                self.t.pencolor("#888888")
                self._triple_bond(sx1, sy1, sx2, sy2)
            else:
                self.t.pencolor("#888888")
                self._line(sx1, sy1, sx2, sy2)

        self.t.pensize(1)

    def _trim_bond(self, x1, y1, x2, y2, r1, r2):
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        if length < 1:
            return x1, y1, x2, y2
        ux = dx / length
        uy = dy / length
        return (x1 + ux*r1, y1 + uy*r1,
                x2 - ux*r2, y2 - uy*r2)

    def _line(self, x1, y1, x2, y2):
        self.t.penup()
        self.t.goto(x1, y1)
        self.t.pendown()
        self.t.goto(x2, y2)
        self.t.penup()

    def _dotted_bond(self, x1, y1, x2, y2, color="#3366FF"):
        """
        Draw a dotted ionic bond: thin, short dashes, widely spaced.
        Dash length ~4px, gap ~6px, pensize=1.
        """
        self.t.pencolor(color)
        self.t.pensize(1)
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        if length < 1:
            return
        ux = dx / length
        uy = dy / length

        DASH  = 4   # pixels drawn
        GAP   = 7   # pixels skipped
        STEP  = DASH + GAP

        pos = 0.0
        while pos < length:
            dash_end = min(pos + DASH, length)
            fx = x1 + ux * pos
            fy = y1 + uy * pos
            tx = x1 + ux * dash_end
            ty = y1 + uy * dash_end
            self._line(fx, fy, tx, ty)
            pos += STEP

    def _double_bond(self, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy) + 0.001
        sp = DOUBLE_SPACING * self.scale
        px = -dy / length * sp
        py =  dx / length * sp
        self._line(x1+px, y1+py, x2+px, y2+py)
        self._line(x1-px, y1-py, x2-px, y2-py)

    def _triple_bond(self, x1, y1, x2, y2):
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx*dx + dy*dy) + 0.001
        sp = TRIPLE_SPACING * self.scale
        px = -dy / length * sp
        py =  dx / length * sp
        self._line(x1, y1, x2, y2)
        self._line(x1+px, y1+py, x2+px, y2+py)
        self._line(x1-px, y1-py, x2-px, y2-py)

    # --------------------------------------------------------
    # ATOMS
    # --------------------------------------------------------

    def draw_atoms(self):
        for atom in self.mol.atoms:
            x = atom.x * self.scale + self.offset_x
            y = atom.y * self.scale + self.offset_y

            fill_color, text_color = ATOM_COLORS.get(atom.symbol, DEFAULT_ATOM_COLOR)

            # Build the full label — always show complete charge
            symbol = atom.symbol
            if atom.charge > 0:
                charge_suffix = "+" if atom.charge == 1 else f"+{atom.charge}"
            elif atom.charge < 0:
                charge_suffix = "-" if atom.charge == -1 else f"{atom.charge}"
            else:
                charge_suffix = ""
            label = symbol + charge_suffix

            # Base radius from table, expanded for charged atoms
            base_r = TurtleRenderer.effective_radius(atom) * self.scale
            radius = base_r

            self._draw_ball(x, y, radius, fill_color)

            if radius >= LABEL_MIN_RADIUS:
                font_size = self._fit_font(label, radius)
                if font_size >= 5:
                    self._draw_label(x, y, label, text_color, font_size)

    def _draw_ball(self, x, y, radius, fill_color):
        self.t.penup()
        # turtle.circle() starts at the bottom of the circle (y - radius)
        self.t.goto(x, y - radius)
        self.t.pendown()
        self.t.pencolor("#555555")
        self.t.pensize(1)
        self.t.fillcolor(fill_color)
        self.t.begin_fill()
        self.t.circle(radius)
        self.t.end_fill()
        self.t.penup()

    def _fit_font(self, label, radius):
        """
        Return the largest integer font size (pts) such that the label
        fits inside a circle of the given radius.
        """
        side = radius * math.sqrt(2) * 0.85
        n_chars = len(label)
        fs_h = side / 0.72
        fs_w = side / (0.65 * max(n_chars, 1))
        fs = int(min(fs_h, fs_w) * LABEL_FONT_SCALE)
        return max(fs, 0)

    def _radius_for_label(self, label, min_font=11):
        """
        Inverse of _fit_font: return the minimum radius (px, in screen space)
        so that the label renders at at least min_font point size.
        """
        n_chars = max(len(label), 1)
        side_needed = min_font * 0.65 * n_chars / LABEL_FONT_SCALE
        return side_needed / (math.sqrt(2) * 0.85)

    def _draw_label(self, x, y, label, text_color, font_size):
        """
        Write label centred on (x, y).
        goto_y = y - LABEL_Y_FRACTION * font_size
        Increase LABEL_Y_FRACTION to move all labels down, decrease to move up.
        """
        self.t.penup()
        self.t.goto(x, y - LABEL_Y_FRACTION * font_size)
        self.t.pencolor(text_color)
        self.t.write(label, align="center", font=("Arial", font_size, "bold"))


    # --------------------------------------------------------
    # AROMATIC RING DETECTION + INNER DASHED CIRCLE
    # --------------------------------------------------------


    def _render_aromatic_rings(self):
        """Detect aromatic rings and draw inner dashed circles."""
        rings = self._find_aromatic_rings()
        for ring in rings:
            cx = sum(a.x for a in ring) / len(ring) * self.scale + self.offset_x
            cy = sum(a.y for a in ring) / len(ring) * self.scale + self.offset_y
            r_circ = sum(
                math.sqrt(
                    (a.x * self.scale + self.offset_x - cx) ** 2 +
                    (a.y * self.scale + self.offset_y - cy) ** 2
                )
                for a in ring
            ) / len(ring)
            inner_r = r_circ * 0.55
            self._dashed_circle(cx, cy, inner_r, color="#444444", dash_deg=18)

    def _find_aromatic_rings(self):
        aromatic_atoms = set(a for a in self.mol.atoms if a.aromatic)
        if not aromatic_atoms:
            return []

        def aromatic_neighbors(atom):
            return [
                (b.b if b.a == atom else b.a)
                for b in atom.bonds
                if (b.b if b.a == atom else b.a) in aromatic_atoms
            ]

        visited_rings = []
        seen_sets = []

        def dfs(start, node, parent, path):
            path.append(node)
            for nb in aromatic_neighbors(node):
                if nb is parent:
                    continue
                if nb is start and len(path) >= 5:
                    ring_set = frozenset(id(a) for a in path)
                    if ring_set not in seen_sets and len(path) <= 7:
                        seen_sets.append(ring_set)
                        visited_rings.append(path[:])
                    continue
                if nb not in path:
                    dfs(start, nb, node, path)
            path.pop()

        for atom in aromatic_atoms:
            dfs(atom, atom, None, [])

        return [r for r in visited_rings if 5 <= len(r) <= 6]

    def _dashed_circle(self, cx, cy, radius, color="#444444", dash_deg=20):
        """Draw a dashed circle by walking in small arc segments."""
        self.t.penup()
        self.t.pencolor(color)
        self.t.pensize(1)
        seg = dash_deg          # degrees drawn per dash
        gap = dash_deg          # degrees skipped per gap
        step = seg + gap
        angle = 0.0
        while angle < 360:
            # start of dash
            a0 = math.radians(angle)
            sx = cx + radius * math.cos(a0)
            sy = cy + radius * math.sin(a0)
            self.t.penup()
            self.t.goto(sx, sy)
            self.t.pendown()
            # walk the dash in small steps
            end_angle = min(angle + seg, 360)
            a = angle
            while a < end_angle:
                a = min(a + 2, end_angle)
                rx = cx + radius * math.cos(math.radians(a))
                ry = cy + radius * math.sin(math.radians(a))
                self.t.goto(rx, ry)
            self.t.penup()
            angle += step