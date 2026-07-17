import math


class RingLayout:
    """
    Lays out one ring at a time, anchored to wherever the caller's DFS
    says the entry/shared atom should go, instead of at a fixed offset
    unrelated to molecular connectivity. This is what keeps independent
    rings (e.g. the two halves of a biphenyl linker) and fused rings
    (e.g. naphthalene-type systems) from landing on top of each other.
    """

    def __init__(self, mol, ring_size=90):
        self.mol = mol
        self.ring_size = ring_size

    def place_ring(self, ring, entry_atom, x, y, incoming_angle):
        """
        Places a ring that has no atoms placed yet. `entry_atom` (the
        atom the DFS arrived through) ends up at (x, y); the rest of the
        ring is distributed evenly around a center that bulges outward
        along `incoming_angle`, so the ring continues in the direction
        the chain was already traveling.
        """
        n = len(ring)
        radius = self.ring_size

        rad = math.radians(incoming_angle)
        cx = x + radius * math.cos(rad)
        cy = y + radius * math.sin(rad)

        start_idx = ring.index(entry_atom)
        ordered = ring[start_idx:] + ring[:start_idx]

        # entry_atom sits at the point on the circle closest to (x, y),
        # i.e. directly opposite the direction we bulged the center out.
        base_angle = incoming_angle + 180
        for i, atom in enumerate(ordered):
            angle = math.radians(base_angle + (360 * i / n))
            atom.x = cx + radius * math.cos(angle)
            atom.y = cy + radius * math.sin(angle)

    def place_fused_ring(self, ring, shared_atom, away_angle, visited):
        """
        Places a ring that shares one or two atoms (ortho-fusion) with an
        already-placed ring. Anchors on `shared_atom`'s existing, fixed
        position and bulges the new ring's center out along `away_angle`
        (computed by the caller from the *other* ring's centroid), so the
        new ring grows away from what it's fused to rather than back
        onto it. Any ring atom already in `visited` (a second shared
        atom, for edge-fused systems) is left untouched.
        """
        n = len(ring)
        radius = self.ring_size

        rad = math.radians(away_angle)
        cx = shared_atom.x + radius * math.cos(rad)
        cy = shared_atom.y + radius * math.sin(rad)

        start_idx = ring.index(shared_atom)
        ordered = ring[start_idx:] + ring[:start_idx]

        base_angle = away_angle + 180
        for i, atom in enumerate(ordered):
            if atom in visited:
                continue
            angle = math.radians(base_angle + (360 * i / n))
            atom.x = cx + radius * math.cos(angle)
            atom.y = cy + radius * math.sin(angle)