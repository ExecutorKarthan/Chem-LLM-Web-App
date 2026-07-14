import math
from ring_utils import RingFinder
from ring_layout import RingLayout
from coordination_geometry import CoordinationGeometry

class LayoutEngine:
    def __init__(self, mol):
        self.mol = mol
        self.visited = set()
        self.bond_length = 65  # Increased slightly for clean structural spacing
        self.ring_size = 85

    def layout(self):
        # 1. Initialize coordinates to clear undefined state traps
        for atom in self.mol.atoms:
            if not hasattr(atom, 'x'):
                atom.x = 0.0
            if not hasattr(atom, 'y'):
                atom.y = 0.0

        rings = RingFinder(self.mol).find_rings()

        # Improved initialization: Space out distinct ring groups so they don't pile up at (0,0)
        ring_layout = RingLayout(self.mol)
        for idx, ring in enumerate(rings):
            # Stagger initial ring origins linearly down a diagonal layout path
            shift_x = idx * 50 
            shift_y = idx * 20
            ring_layout.layout_rings([ring], cx=shift_x, cy=shift_y)

        # Register initialized ring elements to prevent subsequent overwrite shifts
        for ring in rings:
            for atom in ring:
                self.visited.add(atom)

        # 2. Run depth-first layout sweep from the first root node to align branches/substituents
        if self.mol.atoms:
            self.layout_from_atom(self.mol.atoms[0], 0, 0, 0)

        # 3. Perform intensified force relaxation to push overlapping rings cleanly outward
        self.relax(iterations=150)

        # Apply specific target metal geometry configuration rules
        CoordinationGeometry(self.mol).apply()

    def layout_from_atom(self, atom, x, y, angle):
        """
        Your engine's native DFS fallback layout router.
        """
        if atom in self.visited:
            return
        self.visited.add(atom)
        atom.x = x
        atom.y = y

        # Get adjacent neighbors
        neighbors = [b.b if b.a == atom else b.a for b in self.mol.bonds if b.a == atom or b.b == atom]
        unvisited = [n for n in neighbors if n not in self.visited]
        if not unvisited:
            return

        num_branches = len(unvisited)
        spread = 120 if num_branches > 1 else 0
        start_angle = angle - spread / 2

        for i, neighbor in enumerate(unvisited):
            branch_angle = start_angle + (i * spread / (num_branches - 1 if num_branches > 1 else 1))
            rad = math.radians(branch_angle)
            nx = x + self.bond_length * math.cos(rad)
            ny = y + self.bond_length * math.sin(rad)
            self.layout_from_atom(neighbor, nx, ny, branch_angle)

    def relax(self, iterations=150):
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

                # If elements belong to bulky rigid aromatic cores, amplify physical space bounds
                min_distance = 75 if (hasattr(a, 'aromatic') or hasattr(b, 'aromatic')) else 60
                if dist < min_distance:
                    force = (min_distance - dist) * 0.45
                    
                    a.x += (dx / dist) * force
                    a.y += (dy / dist) * force
                    b.x -= (dx / dist) * force
                    b.y -= (dy / dist) * force

    def apply_bond_attraction(self):
        for bond in self.mol.bonds:
            a = bond.a
            b = bond.b

            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx * dx + dy * dy) + 0.01

            desired = self.bond_length
            force = (dist - desired) * 0.25

            a.x += (dx / dist) * force
            a.y += (dy / dist) * force
            b.x -= (dx / dist) * force
            b.y -= (dy / dist) * force