import math


class RingLayout:
    """
    Lays out one ring at a time, anchored to wherever the caller's DFS
    says the entry/shared atom should go, instead of at a fixed offset
    unrelated to molecular connectivity. This is what keeps independent
    rings (e.g. the two halves of a biphenyl linker) and fused rings
    (e.g. naphthalene- or triphenylene-type systems) from landing on
    top of each other.

    The circumradius is computed per ring from `bond_length`, not fixed,
    since a regular n-gon's edge length is 2*R*sin(pi/n) — a single
    fixed radius gives correct edges only for one specific ring size and
    increasingly wrong (too long) edges for smaller rings, which is why
    5-membered rings used to come out visibly more distorted than
    6-membered ones once relaxation tried to compress them back down.
    """

    def __init__(self, mol, bond_length=65):
        self.mol = mol
        self.bond_length = bond_length

    def _radius_for(self, n):
        return self.bond_length / (2 * math.sin(math.pi / n))

    def place_ring(self, ring, entry_atom, x, y, incoming_angle):
        """
        Places a ring that has no atoms placed yet. `entry_atom` (the
        atom the DFS arrived through) ends up at (x, y); the rest of the
        ring is distributed evenly around a center that bulges outward
        along `incoming_angle`, so the ring continues in the direction
        the chain was already traveling.
        """
        n = len(ring)
        radius = self._radius_for(n)

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

    def place_fused_ring(self, ring, visited, reference_point):
        """
        Places a ring that has one or two atoms already fixed (shared
        with an already-placed neighboring ring). `reference_point` is
        used only to pick which side to bulge toward - it's typically
        the other ring's centroid, so this ring grows away from it
        rather than back on top of it.

        For the common ortho-fusion case (two adjacent atoms already
        fixed, i.e. a shared edge), both fixed points are used to solve
        for the one circle of this ring's own radius that passes
        through both exactly - rather than anchoring on a single point
        and hoping the second one lands correctly, which is what
        produced stretched edges and blown-out interior angles on the
        outer rings of fused systems like a triphenylene-type core.
        """
        n = len(ring)
        radius = self._radius_for(n)
        ref_x, ref_y = reference_point

        shared = [a for a in ring if a in visited]

        if len(shared) >= 2:
            p, q = shared[0], shared[1]
            mx, my = (p.x + q.x) / 2, (p.y + q.y) / 2
            dx, dy = q.x - p.x, q.y - p.y
            d = math.hypot(dx, dy)
            if d < 1e-6:
                d = 1e-6
            perp_x, perp_y = -dy / d, dx / d

            half_chord = d / 2
            h_sq = radius * radius - half_chord * half_chord
            h = math.sqrt(h_sq) if h_sq > 0 else 0.0

            c1 = (mx + perp_x * h, my + perp_y * h)
            c2 = (mx - perp_x * h, my - perp_y * h)

            d1 = math.hypot(c1[0] - ref_x, c1[1] - ref_y)
            d2 = math.hypot(c2[0] - ref_x, c2[1] - ref_y)
            cx, cy = c1 if d1 > d2 else c2

            start_idx = ring.index(p)
            ordered = ring[start_idx:] + ring[:start_idx]
            p_angle = math.degrees(math.atan2(p.y - cy, p.x - cx))
            q_angle = math.degrees(math.atan2(q.y - cy, q.x - cx))

            def ang_diff(a, b):
                return abs((a - b + 180) % 360 - 180)

            step = 360 / n
            plus_err = ang_diff(p_angle + step, q_angle)
            minus_err = ang_diff(p_angle - step, q_angle)
            if minus_err < plus_err:
                step = -step

            for i, atom in enumerate(ordered):
                if atom in visited:
                    continue
                angle = math.radians(p_angle + step * i)
                atom.x = cx + radius * math.cos(angle)
                atom.y = cy + radius * math.sin(angle)
        else:
            shared_atom = shared[0] if shared else None
            if shared_atom is None:
                return
            away_angle = math.degrees(math.atan2(shared_atom.y - ref_y, shared_atom.x - ref_x))
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