import math


class RingLayout:


    def __init__(self, mol):

        self.mol = mol

        self.ring_size = 90

        self.placed = set()


    def layout_rings(self, rings, cx=0, cy=0):


        if not rings:

            return


        # Start placement around origin

        angle_offset = 0


        for ring in rings:


            self.place_ring(ring, cx, cy, angle_offset)


            angle_offset += 0.5  # stagger rings


    def place_ring(self, ring, cx, cy, offset):


        n = len(ring)


        radius = self.ring_size


        # detect if ring already partially placed (fused system)


        shared = self.find_shared_atoms(ring)


        if shared:


            self.place_fused_ring(ring, shared)

            return


        for i, atom in enumerate(ring):


            angle = (2 * math.pi * i / n) + offset


            atom.x = cx + radius * math.cos(angle)

            atom.y = cy + radius * math.sin(angle)


            self.placed.add(atom)


    def find_shared_atoms(self, ring):


        for atom in ring:


            if atom in self.placed:

                return atom


        return None


    def place_fused_ring(self, ring, shared_atom):


        # anchor fused ring on existing atom


        base_x = shared_atom.x

        base_y = shared_atom.y


        n = len(ring)


        radius = self.ring_size


        # find direction from neighbors already placed


        for i, atom in enumerate(ring):


            if atom == shared_atom:

                atom.x = base_x

                atom.y = base_y

                continue


            angle = (2 * math.pi * i / n)


            atom.x = base_x + radius * math.cos(angle)

            atom.y = base_y + radius * math.sin(angle)


            self.placed.add(atom)