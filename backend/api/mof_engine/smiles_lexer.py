"""
smiles_lexer.py

Lexer for a simplified SMILES grammar.

Supports:

Atoms:
    C N O P S F Cl Br I
    c n o p s b

Bracket atoms:
    [Cu]
    [Zn+2]
    [O-]
    [NH4+]

Bonds:
    -
    =
    #
    :

Branches:
    (
    )

Rings:
    1-9

Ignores:
    stereochemistry
    isotopes
"""



class Token:

    ATOM = "ATOM"

    BRACKET = "BRACKET"

    BOND = "BOND"

    LPAREN = "LPAREN"

    RPAREN = "RPAREN"

    RING = "RING"


    def __init__(self, kind, value):

        self.kind = kind

        self.value = value


    def __repr__(self):

        return f"Token({self.kind},{repr(self.value)})"



ORGANIC = {

    "B",

    "C",

    "N",

    "O",

    "P",

    "S",

    "F",

    "I",

    "Cl",

    "Br",

    "b",

    "c",

    "n",

    "o",

    "p",

    "s"

}



class Lexer:


    def __init__(self,text):

        self.text=text

        self.i=0


    def peek(self):

        if self.i>=len(self.text):

            return None

        return self.text[self.i]


    def advance(self):

        ch=self.peek()

        self.i+=1

        return ch


    def eof(self):

        return self.i>=len(self.text)


    def tokenize(self):

        tokens=[]


        while not self.eof():

            ch=self.peek()


            if ch in " \t\r\n":

                self.advance()

                continue


            if ch in "-=#:":

                tokens.append(

                    Token(

                        Token.BOND,

                        self.advance()

                    )

                )

                continue


            if ch=="(":

                self.advance()

                tokens.append(

                    Token(

                        Token.LPAREN,

                        "("

                    )

                )

                continue


            if ch==")":

                self.advance()

                tokens.append(

                    Token(

                        Token.RPAREN,

                        ")"

                    )

                )

                continue


            if ch.isdigit():

                tokens.append(

                    Token(

                        Token.RING,

                        self.advance()

                    )

                )

                continue


            if ch=="[":

                content=self.read_bracket()

                tokens.append(

                    Token(

                        Token.BRACKET,

                        content

                    )

                )

                continue


            atom=self.read_atom()


            if atom is None:

                raise ValueError(

                    f"Unexpected character "

                    f"{repr(ch)} "

                    f"at position {self.i}"

                )


            tokens.append(

                Token(

                    Token.ATOM,

                    atom

                )

            )


        return tokens


    def read_bracket(self):

        """
        Reads:

        [Cu+2]

        [O-]

        [NH4+]

        returns:

        Cu+2

        O-

        NH4+
        """


        assert self.peek()=="["


        self.advance()


        chars=[]


        while True:


            ch=self.peek()


            if ch is None:

                raise ValueError(

                    "Unterminated bracket atom"

                )


            if ch=="]":

                self.advance()

                break


            chars.append(

                self.advance()

            )


        return "".join(chars)


    def read_atom(self):

        """
        Reads:

        C

        O

        Cl

        Br

        c

        n
        """


        ch=self.peek()


        if ch is None:

            return None


        # Two-letter atoms


        if self.i+1<len(self.text):


            two=self.text[self.i:self.i+2]


            if two in ORGANIC:


                self.i+=2


                return two


        # One-letter atoms


        if ch in ORGANIC:


            self.i+=1


            return ch


        return None



if __name__=="__main__":


    tests=[

        "CCO",

        "C=C",

        "C#N",

        "C1CCCCC1",

        "c1ccccc1",

        "CC(O)C",

        "[Cu+2]",

        "C1=CC([Cu+2])=CC=C1",

        "[NH4+]"

    ]


    for s in tests:


        print()


        print(s)


        lexer=Lexer(s)


        toks=lexer.tokenize()


        for t in toks:


            print(t)