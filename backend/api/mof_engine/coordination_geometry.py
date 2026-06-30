import math


class CoordinationGeometry:


    def __init__(self, mol):

        self.mol = mol


    # -------------------------
    # ENTRY POINT
    # -------------------------

    def apply(self):

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


    # -------------------------
    # METAL DETECTION
    # -------------------------

    def is_metal(self, atom):

        metals = {

            "Cu", "Zn", "Fe", "Co", "Ni", "Mn",

            "Pd", "Pt", "Ag", "Au"

        }

        return atom.symbol in metals


    # -------------------------
    # NEIGHBORS
    # -------------------------

    def get_neighbors(self, atom):

        out = []


        for b in atom.bonds:

            out.append(b.a if b.b == atom else b.b)


        return out


    # -------------------------
    # LINEAR
    # -------------------------

    def linear(self, m, nbs):

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