"""AST-based mutation operators for Python source code."""
import ast
import copy

ARITH = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
CMP = {
    ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
}
BOOL = {ast.And: ast.Or, ast.Or: ast.And}

SUGGESTIONS = {
    "arithmetic": "Add assertion checking the computed result value",
    "comparison": "Add boundary/edge-case tests (off-by-one values)",
    "return_value": "Assert the return value explicitly, don't just call the function",
    "boolean": "Test both true and false branches of this condition",
    "negate_cond": "Ensure tests cover both outcomes of this conditional",
}


def _label(tree):
    """Assign stable sequential IDs to all AST nodes."""
    for i, node in enumerate(ast.walk(tree)):
        node._mid = i


def _collect_sites(tree, target_lines):
    """Find all mutable AST nodes on target lines."""
    sites = []
    for node in ast.walk(tree):
        ln = getattr(node, "lineno", None)
        if ln is None or (target_lines and ln not in target_lines):
            continue
        mid = node._mid
        if isinstance(node, ast.BinOp) and type(node.op) in ARITH:
            new_t = ARITH[type(node.op)]
            sites.append((mid, ln, "arithmetic",
                          f"{type(node.op).__name__} -> {new_t.__name__}",
                          ("op", new_t)))
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in CMP:
                    new_t = CMP[type(op)]
                    sites.append((mid, ln, "comparison",
                                  f"{type(op).__name__} -> {new_t.__name__}",
                                  ("cmp", i, new_t)))
        if isinstance(node, ast.Return) and node.value is not None:
            sites.append((mid, ln, "return_value",
                          "return value -> return None", ("ret",)))
        if isinstance(node, ast.BoolOp) and type(node.op) in BOOL:
            new_t = BOOL[type(node.op)]
            sites.append((mid, ln, "boolean",
                          f"{type(node.op).__name__} -> {new_t.__name__}",
                          ("op", new_t)))
        if isinstance(node, ast.If):
            sites.append((mid, ln, "negate_cond",
                          "if cond -> if not cond", ("negate",)))
    return sites


def _apply_site(tree, mid, mutation):
    """Apply a single mutation to the tree node identified by mid."""
    for node in ast.walk(tree):
        if getattr(node, "_mid", -1) != mid:
            continue
        kind = mutation[0]
        if kind == "op":
            node.op = mutation[1]()
        elif kind == "cmp":
            node.ops[mutation[1]] = mutation[2]()
        elif kind == "ret":
            node.value = ast.Constant(value=None)
        elif kind == "negate":
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        break


def apply_mutations(source, target_lines=None):
    """Generate all single-point mutated versions of source code."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    _label(tree)
    sites = _collect_sites(tree, target_lines)
    results = []
    for mid, ln, operator, desc, mutation in sites:
        tc = copy.deepcopy(tree)
        _label(tc)
        _apply_site(tc, mid, mutation)
        ast.fix_missing_locations(tc)
        try:
            code = ast.unparse(tc)
        except Exception:
            continue
        results.append({"code": code, "line": ln, "operator": operator,
                        "description": desc, "suggestion": SUGGESTIONS.get(operator, "")})
    return results
