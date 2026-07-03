from smiles_lexer import Lexer, Token

class Atom:
    """Represents an individual node in the chemical connection graph."""
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
    """Represents a structural linkage connecting two specific Atom objects."""
    def __init__(self, a, b, order=1, aromatic=False):
        self.a = a
        self.b = b
        self.order = order
        self.aromatic = aromatic

    def __repr__(self):
        return f"Bond({self.a.id}-{self.b.id}, order={self.order})"


class Molecule:
    """Stores the collection of atoms, bonds, and pending ring/branch closures."""
    def __init__(self):
        self.atoms = []
        self.bonds = []
        self.rings = {}   # Maps ring_id string -> (Atom object, bond_order int)
        self.pending_bond = 1
        self.branch_stack = []

    def add_atom(self, atom):
        """Registers a new atom into the molecular graph and assigns its unique sequential ID."""
        atom.id = len(self.atoms)
        self.atoms.append(atom)
        return atom

    def add_bond(self, a, b, order=1, aromatic=False):
        """Constructs an edge linkage between two atoms and registers it bidirectionally."""
        bond = Bond(a, b, order, aromatic)
        self.bonds.append(bond)
        a.bonds.append(bond)
        b.bonds.append(bond)
        return bond


class SmilesParser:
    """Parses a simplified tokenized sequence into a structured Molecule chemical graph."""
    AROMATIC = {"c", "n", "o", "s", "p", "b"}

    def __init__(self, text):
        self.tokens = Lexer(text).tokenize()
        self.i = 0
        self.mol = Molecule()
        self.current = None  # Tracks the last active atom to append consecutive bonds

    def peek(self):
        """Returns the token at the current reading position without advancing."""
        if self.i >= len(self.tokens):
            return None
        return self.tokens[self.i]

    def advance(self):
        """Consumes the token at the current reading position and increments the index counter."""
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        """Main evaluation loop that iterates through all tokens to assemble the molecular layout."""
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
                # Open branch: push the current active context atom onto the stack
                self.advance()
                self.mol.branch_stack.append(self.current)

            elif tok.kind == Token.RPAREN:
                # Close branch: pop the context atom back off to return to the attachment hub
                self.advance()
                self.current = self.mol.branch_stack.pop()

            elif tok.kind == Token.RING:
                self.handle_ring(tok.value)
                self.advance()

            elif tok.kind == Token.DOT:
                # Handle structural component disconnect markers (e.g. [Ag].[In] complex salts)
                self.advance()
                # Clear context so the next isolated molecule structure doesn't graft onto the last atom
                self.current = None  

            else:
                # CRITICAL DEFENSIVE FALLBACK: If an unmapped token enters the system,
                # immediately consume it to guarantee the pointer advances, preventing infinite web loops.
                self.advance()

        return self.mol

    # -------------------------
    # ATOMS
    # -------------------------
    def handle_atom(self, symbol):
        """Processes unbracketed organic elements and handles implicit downstream bonding."""
        aromatic = symbol in self.AROMATIC
        atom = Atom(symbol, aromatic=aromatic)
        atom = self.mol.add_atom(atom)

        # Automatically connect to the preceding neighbor atom if connectivity context exists
        if self.current is not None:
            self.mol.add_bond(self.current, atom, self.mol.pending_bond)

        self.current = atom
        self.mol.pending_bond = 1

    # -------------------------
    # BRACKET ATOMS
    # -------------------------
    def handle_bracket(self, text):
        """Processes complex bracket-enclosed species like isolated metal nodes or multi-atom ions."""
        symbol, charge = self.parse_bracket(text)
        atom = Atom(symbol, charge=charge, aromatic=False, raw=text)
        atom = self.mol.add_atom(atom)

        # Automatically connect to the preceding neighbor atom if connectivity context exists
        if self.current is not None:
            self.mol.add_bond(self.current, atom, self.mol.pending_bond)

        self.current = atom
        self.mol.pending_bond = 1

    def parse_bracket(self, text):
        """Extracts the element core symbol and formal ionic charge metadata from within brackets."""
        symbol = text[0]
        if len(text) > 1 and text[1].islower():
            symbol += text[1]
            i = 2
        else:
            i = 1

        remainder = text[i:]
        charge = 0

        # Calculate implicit relative charge offsets based on repeated structural signs
        plus = remainder.count("+")
        minus = remainder.count("-")

        if plus:
            charge = plus
        if minus:
            charge = -minus

        # Extract explicit trailing numeric notation flags (e.g., [Cu+2] -> 2)
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
        """Alters the valency parameters for the next downstream covalent connection."""
        if bond_char == "-":
            self.mol.pending_bond = 1
        elif bond_char == "=":
            self.mol.pending_bond = 2
        elif bond_char == "#":
            self.mol.pending_bond = 3
        elif bond_char == ":":
            self.mol.pending_bond = 1

    # -------------------------
    # RINGS
    # -------------------------
    def handle_ring(self, digit):
        """Logs ring closure indexes or evaluates them if a matching closure digit exists."""
        if digit not in self.mol.rings:
            # Store opening anchor details: (originating atom, expected bond configuration order)
            self.mol.rings[digit] = (self.current, self.mol.pending_bond)
        else:
            # Resolve closing anchor: connect current atom to the stored original opening atom
            other, order = self.mol.rings[digit]
            self.mol.add_bond(other, self.current, order)
            del self.mol.rings[digit]
            
        self.mol.pending_bond = 1


# -------------------------
# RUNNER SYSTEM VERIFICATION
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
        "[Ag].[In].[O-]C(=O)c1cccnc1",  # Verifies dot separation parsing stability
        "[NH4+]",
        "O=C([O-])C"
    ]

    for t in tests:
        print(f"\nParsing Formula: {t}")
        mol = SmilesParser(t).parse()

        print("  Mapped Atoms:")
        for a in mol.atoms:
            print(f"    {a}")
        print("  Mapped Bonds:")
        for b in mol.bonds:
            print(f"    {b}")