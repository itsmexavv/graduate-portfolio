"""A lexer, recursive-descent parser and bounded interpreter. No eval/exec."""
import math
import re
from shared.core import APIError

TOKEN = re.compile(r"(?P<SPACE>\s+)|(?P<COMMENT>\#[^\n]*)|(?P<NUMBER>\d+(?:\.\d+)?)|(?P<ID>[A-Za-z_][A-Za-z_0-9]*)|(?P<SYMBOL>[+*/()={}\-;])|(?P<BAD>.)")


def tokenize(source):
    tokens = []
    for match in TOKEN.finditer(source):
        kind = match.lastgroup
        if kind in ("SPACE", "COMMENT"):
            continue
        line = source.count("\n", 0, match.start()) + 1
        column = match.start() - source.rfind("\n", 0, match.start())
        if kind == "BAD":
            raise APIError(f"Unexpected character {match.group()!r} at line {line}, column {column}.", 422)
        tokens.append({"kind": kind, "value": match.group(), "line": line, "column": column})
        if len(tokens) > 1500:
            raise APIError("Program exceeds 1,500 tokens.", 422)
    tokens.append({"kind": "EOF", "value": "EOF", "line": source.count("\n")+1, "column": 1})
    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens, self.index = tokens, 0

    @property
    def current(self):
        return self.tokens[self.index]

    def fail(self, message):
        t = self.current
        raise APIError(f"{message} at line {t['line']}, column {t['column']}.", 422)

    def take(self, value=None, kind=None):
        token = self.current
        if (value is not None and token["value"] != value) or (kind is not None and token["kind"] != kind):
            self.fail(f"Expected {value or kind}, got {token['value']!r}")
        self.index += 1
        return token["value"]

    def statements(self, nested=False, depth=0):
        if depth > 20:
            self.fail("Repeat nesting exceeds 20")
        body = []
        while self.current["kind"] != "EOF" and self.current["value"] != "}":
            keyword = self.take(kind="ID")
            if keyword == "let":
                name = self.take(kind="ID")
                if name in ("let", "print", "repeat"):
                    self.fail("Reserved words cannot be variable names")
                self.take("=")
                body.append({"type": "Let", "name": name, "expression": self.expression()})
                self.take(";")
            elif keyword == "print":
                body.append({"type": "Print", "expression": self.expression()})
                self.take(";")
            elif keyword == "repeat":
                count = self.expression()
                self.take("{")
                body.append({"type": "Repeat", "count": count, "body": self.statements(True, depth+1)})
                self.take("}")
            else:
                self.fail(f"Unknown statement {keyword!r}")
        if not nested:
            self.take(kind="EOF")
        return body

    def expression(self, minimum=0, depth=0):
        if depth > 40:
            self.fail("Expression nesting exceeds 40")
        token = self.current
        if token["value"] == "-":
            self.take("-")
            left = {"type": "Unary", "expression": self.expression(30, depth+1)}
        elif token["value"] == "(":
            self.take("(")
            left = self.expression(0, depth+1)
            self.take(")")
        elif token["kind"] == "NUMBER":
            raw = self.take(kind="NUMBER")
            left = {"type": "Number", "value": float(raw) if "." in raw else int(raw)}
        elif token["kind"] == "ID":
            left = {"type": "Variable", "name": self.take(kind="ID")}
        else:
            self.fail("Expected a number, variable or parenthesized expression")
        precedence = {"+": 10, "-": 10, "*": 20, "/": 20}
        while self.current["value"] in precedence and precedence[self.current["value"]] >= minimum:
            operator = self.take()
            right = self.expression(precedence[operator]+1, depth+1)
            left = {"type": "Binary", "operator": operator, "left": left, "right": right}
        return left


class Interpreter:
    def __init__(self):
        self.variables, self.output, self.steps = {}, [], 0

    def tick(self):
        self.steps += 1
        if self.steps > 10_000:
            raise APIError("Execution exceeded 10,000 steps.", 422)

    def evaluate(self, node):
        self.tick()
        kind = node["type"]
        if kind == "Number":
            value = node["value"]
        elif kind == "Variable":
            if node["name"] not in self.variables:
                raise APIError(f"Undefined variable: {node['name']}.", 422)
            value = self.variables[node["name"]]
        elif kind == "Unary":
            value = -self.evaluate(node["expression"])
        else:
            a, b = self.evaluate(node["left"]), self.evaluate(node["right"])
            operator = node["operator"]
            if operator == "/" and b == 0:
                raise APIError("Division by zero.", 422)
            if operator == "+": value = a+b
            elif operator == "-": value = a-b
            elif operator == "*": value = a*b
            else: value = a/b
        if abs(value) > 1e12 or not math.isfinite(value):
            raise APIError("Numeric result exceeds the supported range (+/- 1e12).", 422)
        return value

    def execute(self, body):
        for node in body:
            self.tick()
            if node["type"] == "Let":
                self.variables[node["name"]] = self.evaluate(node["expression"])
            elif node["type"] == "Print":
                value = self.evaluate(node["expression"])
                if len(self.output) >= 500:
                    raise APIError("Output exceeds 500 lines.", 422)
                self.output.append(f"{value:g}")
            else:
                count = self.evaluate(node["count"])
                if int(count) != count or not 0 <= count <= 100:
                    raise APIError("Repeat count must be a whole number from 0 to 100.", 422)
                for _ in range(int(count)):
                    self.execute(node["body"])


def run(source):
    if not isinstance(source, str) or not source.strip() or len(source) > 4000:
        raise APIError("Source must contain 1–4,000 characters.", 422)
    tokens = tokenize(source)
    try:
        ast = {"type": "Program", "body": Parser(tokens).statements()}
        interpreter = Interpreter()
        interpreter.execute(ast["body"])
    except RecursionError:
        raise APIError("Program structure is too deeply nested.", 422)
    return {"tokens": tokens[:-1], "ast": ast, "output": interpreter.output, "variables": interpreter.variables, "steps": interpreter.steps}


class MiniLang:
    def handle(self, method, path, data, query):
        if path == "/run" and method == "POST":
            return run(data.get("source"))
        raise APIError("Endpoint not found.", 404)
