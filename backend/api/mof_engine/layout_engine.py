import math
from ring_utils import RingFinder
from ring_layout import RingLayout
from coordination_geometry import CoordinationGeometry


class LayoutEngine:
    def __init__(self, mol):
        self.mol = mol
        self.visited = set()
        self.bond_length = 65

    def layout(self):
        # 1. Initialize coordinates to clear undefined state traps
        for atom in self.mol.atoms:
            if not hasattr(atom, 'x'):
                atom.x = 0.0
            if not hasattr(atom, 'y'):
                atom.y = 0.0

        self.rings = RingFinder(self.mol).find_rings()

        self.atom_rings = {}
        for ring in self.rings:
            for atom in ring:
                self.atom_rings.setdefault(atom, []).append(ring)

        self.ring_layout = RingLayout(self.mol, bond_length=self.bond_length)
        self.placed_ring_ids = set()

        # 2. Single DFS sweep that places rings AND chain atoms/branches
        # together, so substituents and subsequent rings in a chain are
        # never skipped just because their attachment point happens to
        # be a ring atom.
        if self.mol.atoms:
            self.layout_from_atom(self.mol.atoms[0], 0.0, 0.0, 0.0)

        # 3. Anything the DFS never reached (disconnected fragments, e.g.
        # counter-ions from a dot-separated formula) still needs real
        # coordinates so it doesn't default to (0, 0) on top of atom 0.
        self.layout_disconnected_fragments()

        # 4. Group fused rings into rigid clusters so relaxation can
        # translate them as whole units instead of deforming them.
        self._build_ring_clusters()

        # 5. Force relaxation to clean up remaining local overlaps
        self.relax(iterations=150)

        # Apply specific target metal geometry configuration rules
        CoordinationGeometry(self.mol).apply()

    # -------------------------
    # CORE TRAVERSAL
    # -------------------------

    def layout_from_atom(self, atom, x, y, angle):
        if atom in self.visited:
            return

        ring = self._unplaced_ring_containing(atom)

        if ring is not None:
            if any(a in self.visited for a in ring):
                # Fused ring: one (or two, for edge-fusion) of its atoms
                # were already placed while laying out a neighboring
                # ring.
                shared = next(a for a in ring if a in self.visited)
                reference_point = self._reference_point_from_other_ring(shared, ring)
                self.ring_layout.place_fused_ring(ring, self.visited, reference_point)
            else:
                self.ring_layout.place_ring(ring, atom, x, y, angle)

            self.placed_ring_ids.add(id(ring))
            for a in ring:
                self.visited.add(a)
            branch_atoms = ring
        else:
            self.visited.add(atom)
            atom.x = x
            atom.y = y
            branch_atoms = [atom]

        # Continue outward from every atom we just placed (every ring
        # atom, not just the entry atom) so exocyclic substituents and
        # the next ring in a chain (e.g. biphenyl-style linkers) get
        # laid out instead of defaulting to (0, 0).
        for branch_atom in branch_atoms:
            neighbors = self._bonded_neighbors(branch_atom)
            unvisited = [n for n in neighbors if n not in self.visited]
            if not unvisited:
                continue

            if ring is not None:
                base_angle = self._ring_outward_angle(branch_atom, ring)
            else:
                base_angle = angle  # keep heading the direction the chain was already going

            num_branches = len(unvisited)
            spread = 100 if num_branches > 1 else 0
            start_angle = base_angle - spread / 2
            step = spread / (num_branches - 1) if num_branches > 1 else 0

            for i, neighbor in enumerate(unvisited):
                branch_angle = start_angle + i * step
                rad = math.radians(branch_angle)
                nx = branch_atom.x + self.bond_length * math.cos(rad)
                ny = branch_atom.y + self.bond_length * math.sin(rad)
                self.layout_from_atom(neighbor, nx, ny, branch_angle)

    # -------------------------
    # HELPERS
    # -------------------------

    def _bonded_neighbors(self, atom):
        return [b.b if b.a == atom else b.a for b in atom.bonds]

    def _unplaced_ring_containing(self, atom):
        for ring in self.atom_rings.get(atom, []):
            if id(ring) not in self.placed_ring_ids:
                return ring
        return None

    def _ring_outward_angle(self, atom, ring):
        """Direction pointing from the ring's centroid through `atom`,
        so substituents fan away from the ring instead of back through it."""
        cx = sum(a.x for a in ring) / len(ring)
        cy = sum(a.y for a in ring) / len(ring)
        if atom.x == cx and atom.y == cy:
            return 0.0
        return math.degrees(math.atan2(atom.y - cy, atom.x - cx))

    def _reference_point_from_other_ring(self, shared_atom, new_ring):
        """For a fused ring, find whichever already-placed ring also
        contains the shared atom and return its centroid, so the new
        ring can be placed on the far side of that point."""
        other_rings = [
            r for r in self.atom_rings.get(shared_atom, [])
            if r is not new_ring and id(r) in self.placed_ring_ids
        ]
        if not other_rings:
            return (shared_atom.x, shared_atom.y)
        r = other_rings[0]
        cx = sum(a.x for a in r) / len(r)
        cy = sum(a.y for a in r) / len(r)
        return (cx, cy)

    def layout_disconnected_fragments(self):
        remaining = [a for a in self.mol.atoms if a not in self.visited]
        if not remaining:
            return

        seen = set()
        offset = 0
        for atom in remaining:
            if atom in seen:
                continue
            component = self._collect_component(atom, seen)
            start_x = 300 + offset
            start_y = 300 + offset
            self.layout_from_atom(component[0], start_x, start_y, 0.0)
            offset += 150

    def _collect_component(self, start, seen):
        stack = [start]
        component = []
        local_seen = set()
        while stack:
            a = stack.pop()
            if a in local_seen:
                continue
            local_seen.add(a)
            seen.add(a)
            component.append(a)
            for n in self._bonded_neighbors(a):
                if n not in local_seen:
                    stack.append(n)
        return component

    # -------------------------
    # RIGID RING CLUSTERS
    # -------------------------

    def _build_ring_clusters(self):
        """
        Groups rings that share at least one atom (fused/ortho-fused
        systems, e.g. the 4-ring core of a triphenylene-type linker)
        into single rigid clusters. Atoms in the same cluster keep the
        exact relative geometry `RingLayout` gave them — regular
        interior angles included — through the relaxation pass; the
        cluster as a whole is still free to be nudged around by forces
        from atoms/clusters outside it.
        """
        n = len(self.rings)
        parent = list(range(n))

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k

        def union(k1, k2):
            r1, r2 = find(k1), find(k2)
            if r1 != r2:
                parent[r1] = r2

        atom_ring_idxs = {}
        for i, ring in enumerate(self.rings):
            for a in ring:
                atom_ring_idxs.setdefault(a, []).append(i)
        for idxs in atom_ring_idxs.values():
            for k in idxs[1:]:
                union(idxs[0], k)

        root_to_cluster_id = {}
        self.atom_cluster = {}
        self.cluster_atoms = []
        for i, ring in enumerate(self.rings):
            root = find(i)
            if root not in root_to_cluster_id:
                root_to_cluster_id[root] = len(self.cluster_atoms)
                self.cluster_atoms.append(set())
            cid = root_to_cluster_id[root]
            for a in ring:
                self.cluster_atoms[cid].add(a)
                self.atom_cluster[a] = cid

    # -------------------------
    # FORCE RELAXATION
    # -------------------------

    def relax(self, iterations=150):
        for _ in range(iterations):
            deltas = {a: [0.0, 0.0] for a in self.mol.atoms}
            self._accumulate_repulsion(deltas)
            self._accumulate_bond_attraction(deltas)
            self._rigidify_clusters(deltas)
            for a, (dx, dy) in deltas.items():
                a.x += dx
                a.y += dy

    def _same_cluster(self, a, b):
        ca = self.atom_cluster.get(a)
        cb = self.atom_cluster.get(b)
        return ca is not None and ca == cb

    def _accumulate_repulsion(self, deltas):
        atoms = self.mol.atoms
        for i in range(len(atoms)):
            for j in range(i + 1, len(atoms)):
                a = atoms[i]
                b = atoms[j]

                if self._same_cluster(a, b):
                    # Same rigid ring cluster — relative geometry (and
                    # interior angles) are already correct; don't fight it.
                    continue

                dx = a.x - b.x
                dy = a.y - b.y
                dist = math.sqrt(dx * dx + dy * dy)

                if dist < 1e-6:
                    angle = (i - j) * 2.399963229  # golden angle, radians
                    dx, dy = math.cos(angle), math.sin(angle)
                    dist = 1e-3

                min_distance = 75 if (getattr(a, 'aromatic', False) or getattr(b, 'aromatic', False)) else 60
                if dist < min_distance:
                    force = (min_distance - dist) * 0.45
                    fx, fy = (dx / dist) * force, (dy / dist) * force
                    deltas[a][0] += fx
                    deltas[a][1] += fy
                    deltas[b][0] -= fx
                    deltas[b][1] -= fy

    def _accumulate_bond_attraction(self, deltas):
        for bond in self.mol.bonds:
            a, b = bond.a, bond.b

            if self._same_cluster(a, b):
                # Ring-internal bond — spacing is already exactly
                # bond_length from RingLayout; nothing to pull.
                continue

            dx = b.x - a.x
            dy = b.y - a.y
            dist = math.sqrt(dx * dx + dy * dy) + 0.01

            force = (dist - self.bond_length) * 0.25
            fx, fy = (dx / dist) * force, (dy / dist) * force
            deltas[a][0] += fx
            deltas[a][1] += fy
            deltas[b][0] -= fx
            deltas[b][1] -= fy

    def _rigidify_clusters(self, deltas):
        """Replace each cluster atom's individual delta with the
        cluster's average delta, so the whole ring (or fused-ring group)
        moves together as one rigid body instead of stretching."""
        for cluster in self.cluster_atoms:
            if not cluster:
                continue
            avg_dx = sum(deltas[a][0] for a in cluster) / len(cluster)
            avg_dy = sum(deltas[a][1] for a in cluster) / len(cluster)
            for a in cluster:
                deltas[a][0] = avg_dx
                deltas[a][1] = avg_dy