"""Tests for MutaGate mutation testing engine."""
import pytest
from mutators import apply_mutations
from mutagate import format_report, run_mutation_testing


def test_arithmetic_mutation_add_to_sub():
    source = "def calc(a, b):\n    return a + b\n"
    mutants = apply_mutations(source, {2})
    arith = [m for m in mutants if m["operator"] == "arithmetic"]
    assert len(arith) >= 1
    assert "Sub" in arith[0]["description"]
    assert "a - b" in arith[0]["code"]
    assert arith[0]["line"] == 2


def test_arithmetic_mutation_mul_to_div():
    source = "def tax(amount):\n    return amount * 1.1\n"
    mutants = apply_mutations(source, {2})
    arith = [m for m in mutants if m["operator"] == "arithmetic"]
    assert any("Div" in m["description"] for m in arith)
    assert any("amount / 1.1" in m["code"] for m in arith)


def test_comparison_mutation():
    source = "def check(x):\n    return x > 0\n"
    mutants = apply_mutations(source, {2})
    cmp_m = [m for m in mutants if m["operator"] == "comparison"]
    assert len(cmp_m) >= 1
    assert "GtE" in cmp_m[0]["description"]
    assert ">= 0" in cmp_m[0]["code"] or ">=" in cmp_m[0]["code"]


def test_return_value_mutation():
    source = "def get_value():\n    return 42\n"
    mutants = apply_mutations(source, {2})
    ret_m = [m for m in mutants if m["operator"] == "return_value"]
    assert len(ret_m) >= 1
    assert "None" in ret_m[0]["code"]
    assert ret_m[0]["description"] == "return value -> return None"


def test_boolean_mutation():
    source = "def f(a, b):\n    return a and b\n"
    mutants = apply_mutations(source, {2})
    bool_m = [m for m in mutants if m["operator"] == "boolean"]
    assert len(bool_m) >= 1
    assert "Or" in bool_m[0]["description"]
    assert " or " in bool_m[0]["code"]


def test_negate_condition_mutation():
    source = "def f(x):\n    if x > 0:\n        return 1\n    return 0\n"
    mutants = apply_mutations(source, {2})
    neg_m = [m for m in mutants if m["operator"] == "negate_cond"]
    assert len(neg_m) >= 1
    assert "not" in neg_m[0]["code"]


def test_target_lines_scoping():
    source = "x = 1 + 2\ny = 3 + 4\n"
    mutants = apply_mutations(source, {1})
    for m in mutants:
        assert m["line"] == 1


def test_no_mutations_on_clean_code():
    source = "x = 'hello'\n"
    mutants = apply_mutations(source, {1})
    assert mutants == []


def test_syntax_error_returns_empty():
    assert apply_mutations("def broken(:", {1}) == []


def test_format_report_fail():
    report = {"status": "fail", "total": 5, "killed": 3, "survived": 2,
              "kill_rate": 60.0, "threshold": 80.0,
              "survivors": [{"file": "calc.py", "line": 10, "operator": "arithmetic",
                             "description": "Add -> Sub", "suggestion": "Add assertion"}]}
    text = format_report(report)
    assert "FAIL" in text
    assert "60.0%" in text
    assert "calc.py:10" in text
    assert "Add -> Sub" in text


def test_format_report_pass():
    report = {"status": "pass", "total": 4, "killed": 4, "survived": 0,
              "kill_rate": 100.0, "threshold": 80.0, "survivors": []}
    text = format_report(report)
    assert "PASS" in text
    assert "100.0%" in text


def test_run_mutation_no_changes():
    report = run_mutation_testing(files_override={})
    assert report["status"] == "pass"
    assert report["total"] == 0
    assert report["kill_rate"] == 100.0
