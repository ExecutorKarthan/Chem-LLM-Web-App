"""
smiles_lexer.py

Lexer for a simplified SMILES grammar.

Supports:
Atoms:           C N O P S F Cl Br I, c n o p s b
Bracket atoms:   [Cu], [Zn+2], [O-], [NH4+]
Bonds:           -, =, #, :
Branches:        (, )
Rings:           1-9
Disconnects:     . (DOT)

Ignores: stereochemistry, isotopes
"""

class Token:
    ATOM = "ATOM"
    BRACKET = "BRACKET"
    BOND = "BOND"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    RING = "RING"
    DOT = "DOT"

    def __init__(self, kind, value):
        self.kind = kind
        self.value = value

    def __repr__(self):
        return f"Token({self.kind},{repr(self.value)})"


# Valid unbracketed organic elements from the standard SMILES subset
ORGANIC = {
    "B", "C", "N", "O", "P", "S", "F", "I", "Cl", "Br",
    "b", "c", "n", "o", "p", "s"
}


class Lexer:
    def __init__(self, text):
        self.text = text
        self.i = 0  # Character stream read offset pointer

    def peek(self):
        """Look at the current stream character without shifting position."""
        if self.i >= len(self.text):
            return None
        return self.text[self.i]

    def advance(self):
        """Consume and return the current character, advancing the pointer forward."""
        ch = self.peek()
        self.i += 1
        return ch

    def eof(self):
        """Returns True if the read pointer has reached the end of the text stream."""
        return self.i >= len(self.text)

    def tokenize(self):
        """Processes the input text string into a list of parsed valid chemical Tokens."""
        tokens = []

        while not self.eof():
            ch = self.peek()

            # Skip standard whitespace characters
            if ch in " \t\r\n":
                self.advance()
                continue

            # Intercept explicit chemical bonds
            if ch in "-=#:":
                tokens.append(Token(Token.BOND, self.advance()))
                continue

            # Branching points (e.g. side chains)
            if ch == "(":
                self.advance()
                tokens.append(Token(Token.LPAREN, "("))
                continue

            if ch == ")":
                self.advance()
                tokens.append(Token(Token.RPAREN, ")"))
                continue

            # Intercept dot disconnect markers (complexes/salts)
            if ch == ".":
                self.advance()
                tokens.append(Token(Token.DOT, "."))
                continue

            # Ring closure structural tracking digits
            if ch.isdigit():
                tokens.append(Token(Token.RING, self.advance()))
                continue

            # Bracket-enclosed elements (metals, formal charges, ions)
            if ch == "[":
                content = self.read_bracket()
                tokens.append(Token(Token.BRACKET, content))
                continue

            # Standard naked organic atoms
            atom = self.read_atom()
            if atom is not None:
                tokens.append(Token(Token.ATOM, atom))
                continue

            # DEFENSIVE FALLBACK: If nothing matched, consume the character and throw
            # This completely guarantees the loop index increments, preventing page lockups!
            bad_char = self.advance()
            raise ValueError(f"Unexpected character {repr(bad_char)} at position {self.i - 1}")

        return tokens

    def read_bracket(self):
        """Extracts text internal parameters bounded inside brackets (e.g. [Cu+2] -> Cu+2)."""
        assert self.peek() == "["
        self.advance()  # Skip opening bracket '['
        chars = []

        while True:
            ch = self.peek()
            if ch is None:
                raise ValueError("Unterminated bracket atom")
            if ch == "]":
                self.advance()  # Skip closing bracket ']'
                break
            chars.append(self.advance())

        return "".join(chars)

    def read_atom(self):
        """Reads organic characters, matching two-letter symbols first before falling back."""
        ch = self.peek()
        if ch is None:
            return None

        # Give priority to match two-character organic elements (e.g. 'Cl', 'Br')
        if self.i + 1 < len(self.text):
            two = self.text[self.i:self.i+2]
            if two in ORGANIC:
                self.i += 2
                return two

        # Match single-character organic elements
        if ch in ORGANIC:
            self.i += 1
            return ch

        return None


if __name__ == "__main__":
    tests = [
        "CCO",
        "C=C",
        "C#N",
        "C1CCCCC1",
        "c1ccccc1",
        "CC(O)C",
        "[Cu+2]",
        "[Ag].[In].[O-]C(=O)c1cccnc1",  # Test case containing the dot disconnect rules
        "[NH4+]"
    ]

    for s in tests:
        print(f"\nParsing String: {s}")
        lexer = Lexer(s)
        try:
            toks = lexer.tokenize()
            for t in toks:
                print(f"  {t}")
        except ValueError as e:
            print(f"  Lexing Failed: {e}")