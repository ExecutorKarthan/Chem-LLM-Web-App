import math
from ring_utils import RingFinder
from ring_layout import RingLayout
from coordination_geometry import CoordinationGeometry

class LayoutEngine:


    def __init__(self, mol):

        self.mol = mol

        self.visited = set()

        self.bond_length = 60

        self.ring_size = 80


    # ----------------------------
    # MAIN ENTRY
    # ----------------------------

    def layout(self):

        # Ensure every atom has x,y before any relaxation runs
        for atom in self.mol.atoms:
            if not hasattr(atom, 'x'):
                atom.x = 0.0
            if not hasattr(atom, 'y'):
                atom.y = 0.0

        rings = RingFinder(self.mol).find_rings()

        ring_layout = RingLayout(self.mol)
        ring_layout.layout_rings(rings)

        # Mark ring atoms as visited so layout_from_atom won't overwrite them
        for ring in rings:
            for atom in ring:
                self.visited.add(atom)

        # Place substituents hanging off ring atoms, radially outward
        for ring in rings:
            cx = sum(a.x for a in ring) / len(ring)
            cy = sum(a.y for a in ring) / len(ring)
            self.layout_ring(ring, cx, cy)

        # DFS from first atom to catch any non-ring atoms not yet placed
        self.layout_from_atom(self.mol.atoms[0], 0, 0, 0)


        self.relax(60)


        CoordinationGeometry(self.mol).apply()


    # ----------------------------
    # RECURSIVE PLACEMENT
    # ----------------------------

    def layout_from_atom(self, atom, x, y, angle):

        if atom in self.visited:

            return


        atom.x = x

        atom.y = y

        self.visited.add(atom)


        neighbors = self.get_neighbors(atom)

        unvisited = [n for n in neighbors if n not in self.visited]

        if not unvisited:
            return

        # Spread branches symmetrically around the incoming angle.
        # 120° step gives correct sp2/sp3 geometry for chains and substituents.
        angle_step = 2 * math.pi / 3

        for i, n in enumerate(unvisited):

            new_angle = angle + (i - (len(unvisited) - 1) / 2.0) * angle_step

            nx = x + self.bond_length * math.cos(new_angle)
            ny = y + self.bond_length * math.sin(new_angle)

            self.layout_from_atom(n, nx, ny, new_angle)


    # ----------------------------
    # NEIGHBORS
    # ----------------------------

    def get_neighbors(self, atom):

        out = []


        for b in atom.bonds:

            if b.a == atom:

                out.append(b.b)

            else:

                out.append(b.a)


        return out


    # ----------------------------
    # RING DETECTION (simple DFS cycle)
    # ----------------------------

    def detect_ring(self, start):

        path = []

        visited = set()


        result = self._dfs_cycle(start, None, visited, path)


        return result


    def _dfs_cycle(self, node, parent, visited, path):

        visited.add(node)

        path.append(node)


        for b in node.bonds:


            nxt = b.b if b.a == node else b.a


            if nxt == parent:

                continue


            if nxt in path:

                # cycle found

                idx = path.index(nxt)

                return path[idx:]


            if nxt not in visited:

                res = self._dfs_cycle(nxt, node, visited, path)

                if res:

                    return res


        path.pop()

        return None


    # ----------------------------
    # RING LAYOUT (polygon)
    # ----------------------------

    def layout_ring(self, ring_atoms, cx, cy):

        n = len(ring_atoms)

        radius = self.ring_size

        for i, atom in enumerate(ring_atoms):

            angle = 2 * math.pi * i / n

            atom.x = cx + radius * math.cos(angle)

            atom.y = cy + radius * math.sin(angle)

            self.visited.add(atom)

        # Place substituents hanging off each ring atom radially outward
        for atom in ring_atoms:

            # Outward direction from ring center
            dx = atom.x - cx
            dy = atom.y - cy
            dist = math.sqrt(dx*dx + dy*dy) + 0.001
            ux = dx / dist
            uy = dy / dist

            # How many substituents need placing?
            subs = [n for n in self.get_neighbors(atom) if n not in self.visited]

            if not subs:
                continue

            # Fan substituents around the outward direction
            # For 1 sub: straight out. For 2: ±30°. For 3: ±60° and straight.
            n_subs = len(subs)
            if n_subs == 1:
                offsets = [0]
            elif n_subs == 2:
                offsets = [-math.pi / 6, math.pi / 6]
            else:
                offsets = [math.pi * k / (n_subs - 1) - math.pi / 2
                           for k in range(n_subs)]

            for sub_atom, offset in zip(subs, offsets):
                out_angle = math.atan2(uy, ux) + offset
                nx = atom.x + self.bond_length * math.cos(out_angle)
                ny = atom.y + self.bond_length * math.sin(out_angle)
                self.layout_from_atom(sub_atom, nx, ny, out_angle)


    # ----------------------------
    # SIMPLE RELAXATION
    # ----------------------------

    def relax(self, iterations=50):

        for _ in range(iterations):

            self.apply_repulsion()

            self.apply_bond_attraction()


    def apply_repulsion(self):

        atoms = self.mol.atoms


        for i in range(len(atoms)):

            for j in range(i + 1, len(atoms)):


                a = atoms[i]

                b = atoms[j]


                dx = a.x - b.x

                dy = a.y - b.y


                dist = math.sqrt(dx * dx + dy * dy) + 0.01


                if dist < 80:

                    force = 5 / dist


                    a.x += dx / dist * force

                    a.y += dy / dist * force


                    b.x -= dx / dist * force

                    b.y -= dy / dist * force


    def apply_bond_attraction(self):

        for bond in self.mol.bonds:


            a = bond.a

            b = bond.b


            dx = b.x - a.x

            dy = b.y - a.y


            dist = math.sqrt(dx * dx + dy * dy) + 0.01


            desired = self.bond_length


            force = (dist - desired) * 0.05


            a.x += dx / dist * force

            a.y += dy / dist * force


            b.x -= dx / dist * force

            b.y -= dy / dist * force