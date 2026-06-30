from smiles_lexer import Lexer, Token


class Atom:

    def __init__(self, symbol, charge=0, aromatic=False, raw=None):

        self.symbol = symbol

        self.charge = charge

        self.aromatic = aromatic

        self.raw = raw

        self.id = None

        self.bonds = []


    def __repr__(self):

        return f"Atom({self.symbol}, charge={self.charge}, aromatic={self.aromatic})"



class Bond:

    def __init__(self, a, b, order=1, aromatic=False):

        self.a = a

        self.b = b

        self.order = order

        self.aromatic = aromatic


    def __repr__(self):

        return f"Bond({self.a.id}-{self.b.id}, order={self.order})"



class Molecule:

    def __init__(self):

        self.atoms = []

        self.bonds = []

        self.rings = {}   # ring_id -> (atom, bond_order)

        self.pending_bond = 1

        self.branch_stack = []


    def add_atom(self, atom):

        atom.id = len(self.atoms)

        self.atoms.append(atom)

        return atom


    def add_bond(self, a, b, order=1, aromatic=False):

        bond = Bond(a, b, order, aromatic)

        self.bonds.append(bond)

        a.bonds.append(bond)

        b.bonds.append(bond)

        return bond



class SmilesParser:


    AROMATIC = set(["c","n","o","s","p","b"])


    def __init__(self, text):

        self.tokens = Lexer(text).tokenize()

        self.i = 0

        self.mol = Molecule()

        self.current = None


    def peek(self):

        if self.i >= len(self.tokens):

            return None

        return self.tokens[self.i]


    def advance(self):

        tok = self.peek()

        self.i += 1

        return tok


    def parse(self):

        while self.peek() is not None:

            tok = self.peek()


            if tok.kind == Token.ATOM:

                self.handle_atom(tok.value)

                self.advance()


            elif tok.kind == Token.BRACKET:

                self.handle_bracket(tok.value)

                self.advance()


            elif tok.kind == Token.BOND:

                self.handle_bond(tok.value)

                self.advance()


            elif tok.kind == Token.LPAREN:

                self.advance()

                self.mol.branch_stack.append(self.current)


            elif tok.kind == Token.RPAREN:

                self.advance()

                self.current = self.mol.branch_stack.pop()


            elif tok.kind == Token.RING:

                self.handle_ring(tok.value)

                self.advance()


        return self.mol


    # -------------------------
    # ATOMS
    # -------------------------

    def handle_atom(self, symbol):

        aromatic = symbol in self.AROMATIC

        atom = Atom(symbol, aromatic=aromatic)

        atom = self.mol.add_atom(atom)


        if self.current is not None:

            self.mol.add_bond(self.current, atom, self.mol.pending_bond)


        self.current = atom

        self.mol.pending_bond = 1


    # -------------------------
    # BRACKET ATOMS
    # -------------------------

    def handle_bracket(self, text):

        symbol, charge = self.parse_bracket(text)


        atom = Atom(symbol, charge=charge, aromatic=False, raw=text)

        atom = self.mol.add_atom(atom)


        if self.current is not None:

            self.mol.add_bond(self.current, atom, self.mol.pending_bond)


        self.current = atom

        self.mol.pending_bond = 1


    def parse_bracket(self, text):

        """
        Parses:

        Cu+2
        O-
        NH4+
        Fe+++
        Zn
        """


        symbol = ""

        i = 0


        # element symbol

        symbol += text[0]


        if len(text) > 1 and text[1].islower():

            symbol += text[1]

            i = 2

        else:

            i = 1


        remainder = text[i:]


        charge = 0


        plus = remainder.count("+")

        minus = remainder.count("-")


        if plus:

            charge = plus

        if minus:

            charge = -minus


        # handle numeric charge like +2

        if "+" in remainder:

            parts = remainder.split("+")

            if len(parts) > 1 and parts[1].isdigit():

                charge = int(parts[1])


        if "-" in remainder:

            parts = remainder.split("-")

            if len(parts) > 1 and parts[1].isdigit():

                charge = -int(parts[1])


        return symbol, charge


    # -------------------------
    # BONDS
    # -------------------------

    def handle_bond(self, bond_char):

        if bond_char == "-":

            self.mol.pending_bond = 1

        elif bond_char == "=":

            self.mol.pending_bond = 2

        elif bond_char == "#":

            self.mol.pending_bond = 3

        elif bond_char == ":":

            self.mol.pending_bond = 1

            # aromatic flag handled via atom type


    # -------------------------
    # RINGS
    # -------------------------

    def handle_ring(self, digit):

        if digit not in self.mol.rings:

            # store (atom, bond_order)

            self.mol.rings[digit] = (

                self.current,

                self.mol.pending_bond

            )

        else:

            other, order = self.mol.rings[digit]


            self.mol.add_bond(

                other,

                self.current,

                order

            )


            del self.mol.rings[digit]


        self.mol.pending_bond = 1



# -------------------------
# TEST
# -------------------------

if __name__ == "__main__":

    tests = [

        "CCO",

        "C=C",

        "C#N",

        "C1CCCCC1",

        "c1ccccc1",

        "CC(O)C",

        "[Cu+2]",

        "C1=CC([Cu+2])=CC=C1",

        "[NH4+]",

        "O=C([O-])C"

    ]


    for t in tests:

        print("\n", t)

        mol = SmilesParser(t).parse()


        for a in mol.atoms:

            print(a)


        for b in mol.bonds:

            print(b)