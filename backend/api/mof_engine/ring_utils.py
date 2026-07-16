class RingFinder:


    def __init__(self, mol):

        self.mol = mol


    def find_rings(self):

        """
        Returns list of rings:

        [

          [atom0, atom1, atom2, ...],

          [...]

        ]
        """


        rings = []

        visited_edges = set()


        for atom in self.mol.atoms:


            self.dfs(atom, None, [], visited_edges, rings)


        return self.clean_rings(rings)


    def dfs(self, node, parent, path, visited_edges, rings):

        path.append(node)


        for bond in node.bonds:


            nxt = bond.a if bond.b == node else bond.b


            edge = self.edge_id(node, nxt)


            if nxt == parent:

                continue


            if edge in visited_edges:

                continue


            visited_edges.add(edge)


            if nxt in path:

                idx = path.index(nxt)

                cycle = path[idx:]


                if len(cycle) >= 3:

                    rings.append(cycle)


            else:

                self.dfs(nxt, node, path[:], visited_edges, rings)


    def edge_id(self, a, b):

        return (min(a.id, b.id), max(a.id, b.id))


    def clean_rings(self, rings):

        """
        Remove duplicates and subrings
        """


        unique = []


        for r in rings:


            if not self.contains(unique, r):

                unique.append(r)


        return unique


    def contains(self, rings, r):

        for rr in rings:


            if self.same_ring(rr, r):

                return True


        return False


    def same_ring(self, a, b):

        if len(a) != len(b):

            return False


        ids_a = sorted([x.id for x in a])

        ids_b = sorted([x.id for x in b])


        return ids_a == ids_b