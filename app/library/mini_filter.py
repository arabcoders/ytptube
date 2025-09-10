import operator
import re
from typing import Any

TOKEN = tuple[str, str]
AST_NODE = tuple[str, ...]


def match_str(expr: str, dct: dict) -> bool:
    """
    Convenience function to evaluate a filter expression against a dict.

    Note: This implementation uses numeric duration/filesize values in tests to avoid
    yt-dlp's inconsistent unit parsing behavior. yt-dlp's match_str has known issues
    with duration unit formats like "2m" that don't behave consistently with their
    numeric equivalents (e.g., "120").

    Args:
        expr (str): Filter expression string
        dct (dict):  Dictionary of values to check against

    Returns:
        bool: True/False if expression matches

    """
    return MiniFilter(expr).evaluate(dct)


class MiniFilter:
    """
    Parser and evaluator for yt-dlp style match-filters, extended with
    support for OR (`||`) and grouping with parentheses.

    Features:
    - Supports AND (`&`), OR (`||`), and parentheses `()`
    - Reuses yt-dlp style operators (=, >=, *=, ~=, etc.)
    - Export to yt-dlp compatible `--match-filters`.
    """

    # Type aliases for better readability
    Token = tuple[str, str]
    ASTNode = tuple[str, ...]

    # Supported string operators
    STRING_OPERATORS: dict[str, callable] = {
        "*=": operator.contains,
        "^=": lambda attr, value: isinstance(attr, str) and attr.startswith(value),
        "$=": lambda attr, value: isinstance(attr, str) and attr.endswith(value),
        "~=": lambda attr, value: bool(re.search(value, attr or "")),
    }

    # Comparison operators (numeric + string)
    COMPARISON_OPERATORS: dict[str, callable] = {
        **STRING_OPERATORS,
        "<=": operator.le,
        "<": operator.lt,
        ">=": operator.ge,
        ">": operator.gt,
        "=": operator.eq,
    }

    # Unary operators (for presence/absence checks)
    UNARY_OPERATORS: dict[str, callable] = {
        "": lambda v: (v is True) if isinstance(v, bool) else (v is not None),
        "!": lambda v: (v is False) if isinstance(v, bool) else (v is None),
    }

    def __init__(self, expr: str) -> None:
        """
        Initialize a parser for the given filter expression.

        :param expr: Filter expression string, e.g. "(duration<10m & filesize>1MB) || uploader*='BBC'"
        """
        self.expr: str = expr
        self.tokens: list[TOKEN] = self._tokenize(expr)
        self.pos: int = 0
        self.ast: AST_NODE = self._parse_or()

    @staticmethod
    def run(expr: str, dct: dict | bool = False) -> bool:
        """
        Convenience method to evaluate an expression directly.

        :param expr: Filter expression string
        :param dct:  Dictionary of values to check against
        :return:     True/False if expression matches
        """
        return MiniFilter(expr).evaluate(dct)

    def evaluate(self, dct: dict | bool = False) -> bool:
        """
        Evaluate the parsed expression against a dictionary.

        :param dct: Dictionary of attributes (video metadata, etc.)
        :return:    True/False result of expression
        """
        return self._eval(self.ast, dct)

    def export(self) -> list[str]:
        """
        Export expression into yt-dlp compatible `--match-filters` strings.

        Since yt-dlp does not support OR (`||`) or parentheses,
        this method flattens the expression into multiple AND-only strings.

        Example:
            (a=1 & b=2) || c=3
            → ["a=1&b=2", "c=3"]

        :return: List of AND-only filter strings

        """
        return ["&".join(parts) for parts in self._export(self.ast)]

    def _tokenize(self, expr: str) -> list[TOKEN]:
        """
        Split expression into tokens (AND, OR, LPAREN, RPAREN, ATOM).
        Ensures that OR (||) and AND (&) are recognized before ATOM.
        """
        # First, let's normalize spaces around operators to make parsing easier
        # Replace spaced operators with non-spaced ones
        normalized_expr: str = expr
        for op in ["<=", ">=", "<", ">", "*=", "^=", "$=", "~=", "="]:
            # Replace "key op value" with "key op value" (removing extra spaces)
            pattern: str = rf"([a-z_]+)\s*(!?)\s*({re.escape(op)})\s*"
            replacement = r"\1\2\3"
            normalized_expr = re.sub(pattern, replacement, normalized_expr)

        token_spec: list[set] = [
            (r"\|\|", "OR"),  # must come before ATOM
            (r"&", "AND"),
            (r"\(", "LPAREN"),
            (r"\)", "RPAREN"),
            (r"[^\s&|()]+", "ATOM"),  # don't allow whitespace in ATOM
            (r"\s+", None),  # skip whitespace
        ]
        regex: str = "|".join(f"(?P<{name}>{pat})" for pat, name in token_spec if name)
        master: re.Pattern[str] = re.compile(regex)
        tokens: list[TOKEN] = []
        for m in master.finditer(normalized_expr):
            kind: str | None = m.lastgroup
            if kind:
                tokens.append((kind, m.group()))
        return tokens

    def _parse_or(self) -> AST_NODE:
        """
        Parse OR-expression: and_expr ('||' and_expr)*
        """
        left: AST_NODE = self._parse_and()
        while self._accept("OR"):
            right: AST_NODE = self._parse_and()
            left = ("OR", left, right)
        return left

    def _parse_and(self) -> AST_NODE:
        """
        Parse AND-expression: atom ('&' atom)*
        """
        left: AST_NODE = self._parse_atom()
        while self._accept("AND"):
            right: AST_NODE = self._parse_atom()
            left = ("AND", left, right)
        return left

    def _parse_atom(self) -> AST_NODE:
        """
        Parse atomic expression: '(' expr ')' | ATOM
        """
        if self._accept("LPAREN"):
            node: AST_NODE = self._parse_or()
            self._expect("RPAREN")
            return node

        tok: TOKEN = self._expect("ATOM")
        return ("ATOM", tok[1].strip())

    def _accept(self, kind: str) -> bool:
        """
        Consume token if it matches expected kind.
        """
        if self.pos < len(self.tokens) and kind == self.tokens[self.pos][0]:
            self.pos += 1
            return True

        return False

    def _expect(self, kind: str) -> TOKEN:
        """
        Consume and return token if it matches expected kind,
        otherwise raise SyntaxError.
        """
        if self.pos < len(self.tokens) and kind == self.tokens[self.pos][0]:
            tok = self.tokens[self.pos]
            self.pos += 1
            return tok

        raise SyntaxError("Expected " + kind)

    def _eval(self, node: AST_NODE, dct: dict) -> bool:
        """
        Recursively evaluate AST node against dict.
        """
        node_type: str = node[0]

        if "ATOM" == node_type:
            return self._match_one(node[1], dct)

        if "AND" == node_type:
            return self._eval(node[1], dct) and self._eval(node[2], dct)

        if "OR" == node_type:
            return self._eval(node[1], dct) or self._eval(node[2], dct)

        raise ValueError("Invalid AST node " + node_type)

    def _export(self, node: AST_NODE) -> list[list[str]]:
        """
        Recursively flatten AST into AND-only filter groups.
        """
        node_type = node[0]
        if "ATOM" == node_type:
            return [[node[1]]]

        if "AND" == node_type:
            left: list[list[str]] = self._export(node[1])
            right: list[list[str]] = self._export(node[2])
            return [_l + _r for _l in left for _r in right]

        if "OR" == node_type:
            left = self._export(node[1])
            right = self._export(node[2])
            return left + right

        raise ValueError("Invalid AST node " + node_type)

    def _match_one(self, filter_part: str, dct: dict) -> bool:
        operator_rex: re.Pattern[str] = re.compile(
            r"""(?x)
            (?P<key>[a-z_]+)
            \s*(?P<negation>!\s*)?(?P<op>{})(?P<none_inclusive>\s*\?)?\s*
            (?:
                (?P<quote>["\'])(?P<quoted_strval>.+?)(?P=quote)|
                (?P<strval>.+?)
            )
            """.format("|".join(map(re.escape, self.COMPARISON_OPERATORS.keys())))
        )

        if m := operator_rex.fullmatch(filter_part.strip()):
            from yt_dlp.utils import parse_duration, parse_filesize

            g: dict[str, str | Any] = m.groupdict()
            unnegated_op: Any = self.COMPARISON_OPERATORS[g["op"]]
            op = (lambda a, v: not unnegated_op(a, v)) if g["negation"] else unnegated_op

            comparison_value: str | Any = g["quoted_strval"] or g["strval"]

            if g["quote"]:
                comparison_value = comparison_value.replace(rf"\{g['quote']}", g["quote"])

            actual_value: Any | None = dct.get(g["key"])

            if None is actual_value:
                return False

            # numeric coercion using yt-dlp utils
            numeric_comparison = None
            try:
                numeric_comparison = int(comparison_value)
            except ValueError:
                numeric_comparison: int | None | float = parse_filesize(comparison_value) or parse_duration(
                    comparison_value
                )

            if numeric_comparison is not None and g["op"] in self.STRING_OPERATORS:
                msg = f"Operator {g['op']} only supports string values!"
                raise ValueError(msg)

            # Also try to convert actual_value to numeric if we have a numeric comparison
            final_actual_value = actual_value
            if numeric_comparison is not None and isinstance(actual_value, str):
                try:
                    final_actual_value = int(actual_value)
                except ValueError:
                    final_actual_value = parse_filesize(actual_value) or parse_duration(actual_value) or actual_value

            return op(final_actual_value, numeric_comparison if None is not numeric_comparison else comparison_value)

        # unary operators
        operator_rex = re.compile(r"(?P<op>{})\s*(?P<key>[a-z_]+)".format("|".join(self.UNARY_OPERATORS)))
        if m := operator_rex.fullmatch(filter_part.strip()):
            op: Any = self.UNARY_OPERATORS[m.group("op")]
            actual_value = dct.get(m.group("key"))
            return op(actual_value)

        msg: str = f"Invalid filter part {filter_part!r}"
        raise ValueError(msg)
