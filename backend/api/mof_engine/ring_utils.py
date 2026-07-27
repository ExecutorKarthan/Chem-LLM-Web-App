from collections import deque


class RingFinder:
    """
    Finds the molecule's rings using an approximate SSSR (smallest set of
    smallest rings): for every bond, find the shortest cycle that uses
    it via BFS with that bond temporarily removed, then de-duplicate and
    cap the result at the graph's cyclomatic number.

    This replaces an earlier DFS-back-edge approach that, for fused
    polycyclic systems with three or more rings sharing edges around a
    central ring (e.g. a triphenylene-like core), could report a large
    non-minimal cycle (the outer boundary) instead of the true minimal
    central ring — leaving that central ring's atoms undiscovered and
    causing the layout engine to mis-place the fused core.
    """

    def __init__(self, mol):
        self.mol = mol

    def find_rings(self):
        """Returns the molecule's SSSR as a list of rings, each a list
        of atoms in traversal order. See class docstring for the
        approach and why it replaced the old DFS back-edge method."""
        candidate_rings = []
        for bond in self.mol.bonds:
            ring = self._shortest_ring_through_bond(bond)
            if ring is not None:
                candidate_rings.append(ring)

        return self._select_sssr(candidate_rings)

    def _shortest_ring_through_bond(self, bond):
        """
        BFS from bond.a to bond.b without using `bond` itself. The path
        found, plus the bond, is the shortest cycle containing that bond
        (or None if the bond is a bridge / not part of any ring).
        """
        start, end = bond.a, bond.b
        visited = {start}
        queue = deque([(start, [start])])

        while queue:
            node, path = queue.popleft()
            for b in node.bonds:
                if b is bond:
                    continue
                nxt = b.a if b.b == node else b.b
                if nxt is end:
                    return path + [end]
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, path + [nxt]))

        return None

    def _select_sssr(self, candidate_rings):
        """
        Collapse candidate rings down to one (the smallest found) per
        unique atom set, sort smallest-first, and cap at the number of
        independent cycles the molecule actually has so redundant larger
        rings don't sneak in ahead of a still-undiscovered smaller one.
        """
        unique = {}
        for ring in candidate_rings:
            key = frozenset(a.id for a in ring)
            if key not in unique or len(ring) < len(unique[key]):
                unique[key] = ring

        rings = sorted(unique.values(), key=len)

        max_rings = self._cyclomatic_number()
        return rings[:max_rings] if max_rings is not None else rings

    def _cyclomatic_number(self):
        """edges - atoms + connected_components, i.e. how many
        independent rings the molecule's graph actually contains."""
        atoms = self.mol.atoms
        bonds = self.mol.bonds
        if not atoms:
            return 0

        parent = {a: a for a in atoms}

        def find(a):
            while parent[a] is not a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra is not rb:
                parent[ra] = rb

        for bond in bonds:
            union(bond.a, bond.b)

        components = len({find(a) for a in atoms})
        return len(bonds) - len(atoms) + components