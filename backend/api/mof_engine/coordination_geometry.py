import math


class CoordinationGeometry:
    """
    Overrides the layout engine's generic organic-chain placement for
    metal centers, snapping each metal's directly-bonded neighbors into
    the idealized 2D projection of its expected coordination geometry
    (linear, tetrahedral/square planar, or octahedral) based on how
    many neighbors it has. This runs as a final pass after `relax()`,
    so it deliberately overwrites whatever position relaxation settled
    on for those neighbor atoms.

    Note: 2- and 6-coordinate metals get one fixed geometry each, but a
    4-coordinate metal is genuinely ambiguous (could be tetrahedral or
    square planar depending on the real molecule) - `tetrahedral_or_square`
    always draws the square-planar arrangement since that's a reasonable
    flattened 2D projection either way.
    """

    def __init__(self, mol):
        self.mol = mol

    # -------------------------
    # ENTRY POINT
    # -------------------------

    def apply(self):
        """Find every metal atom and re-place its neighbors according
        to the geometry implied by its coordination number."""
        for atom in self.mol.atoms:
            if self.is_metal(atom):
                neighbors = self.get_neighbors(atom)
                n = len(neighbors)

                if n == 2:
                    self.linear(atom, neighbors)
                elif n == 4:
                    self.tetrahedral_or_square(atom, neighbors)
                elif n == 6:
                    self.octahedral(atom, neighbors)
                # Any other coordination number (3, 5, 7+) is left as
                # whatever the generic layout/relaxation already produced.


    # -------------------------
    # METAL DETECTION
    # -------------------------

    def is_metal(self, atom):
        """True if the atom's element is one of the MOF metal centers
        this engine knows how to lay out. Not an exhaustive list of all
        metallic elements - just the ones expected to appear as nodes
        in the supported MOF structures."""
        metals = {
            "Cu", "Zn", "Fe", "Co", "Ni", "Mn",
            "Pd", "Pt", "Ag", "Au"
        }
        return atom.symbol in metals

    # -------------------------
    # NEIGHBORS
    # -------------------------

    def get_neighbors(self, atom):
        """Returns every atom directly bonded to `atom`."""
        out = []
        for b in atom.bonds:
            out.append(b.a if b.b == atom else b.b)
        return out


    # -------------------------
    # LINEAR
    # -------------------------

    def linear(self, m, nbs):
        """Places a 2-coordinate metal's two neighbors directly
        opposite each other along the x-axis, `dx` apart from the
        metal on each side (the 180-degree linear geometry)."""
        if len(nbs) != 2:
            return

        a, b = nbs
        dx = 80

        a.x = m.x - dx
        a.y = m.y

        b.x = m.x + dx
        b.y = m.y


    # -------------------------
    # TETRAHEDRAL (projected 2D)
    # -------------------------

    def tetrahedral_or_square(self, m, nbs):
        """Places a 4-coordinate metal's neighbors at the four compass
        points around it (0, 90, 180, 270 degrees) - the square-planar
        arrangement. Used as the 2D projection for both square-planar
        and tetrahedral 4-coordinate centers, since a true tetrahedron
        can't be drawn without perspective distortion in a flat
        depiction anyway."""
        if len(nbs) != 4:
            return

        angles = [
            0,
            math.pi / 2,
            math.pi,
            3 * math.pi / 2
        ]

        radius = 70

        for i, atom in enumerate(nbs):
            angle = angles[i]
            atom.x = m.x + radius * math.cos(angle)
            atom.y = m.y + radius * math.sin(angle)


    # -------------------------
    # OCTAHEDRAL (2D projection)
    # -------------------------

    def octahedral(self, m, nbs):
        """Places a 6-coordinate metal's neighbors in a flattened 2D
        projection of an octahedron: the first four neighbors go at
        the compass points (the equatorial plane), and the remaining
        two - which in 3D would sit directly above/below the metal
        along the axis perpendicular to the page - are projected onto
        the same plane at 45 and 225 degrees so all six stay visible
        and distinguishable instead of overlapping the metal itself."""
        if len(nbs) != 6:
            return

        radius = 80

        angles = [
            0,
            math.pi / 2,
            math.pi,
            3 * math.pi / 2,
            math.pi / 4,
            5 * math.pi / 4
        ]

        for i, atom in enumerate(nbs):
            angle = angles[i]
            atom.x = m.x + radius * math.cos(angle)
            atom.y = m.y + radius * math.sin(angle)