from __future__ import annotations

import ast
import json
import random
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from itertools import permutations, product
from pathlib import Path


OPERATORS = ("+", "-", "*", "/", "^")
MIN_NUMBER = 1
MAX_NUMBER = 9
MIN_TARGET = 1
MAX_TARGET = 999
MAX_EXPONENT = 4
MAX_INTERMEDIATE_ABS = 10000
LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "number_puzzle.log"


@dataclass(frozen=True)
class NumberPuzzleProblem:
    numbers: tuple[int, int, int]
    target: int
    answer_expression: str

    @property
    def question_text(self) -> str:
        return "、".join(str(number) for number in self.numbers)

    @property
    def answer_text(self) -> str:
        return f"{self.answer_expression} = {self.target}"


def create_problem(rng: random.Random | None = None) -> NumberPuzzleProblem:
    random_source = rng or random

    for _ in range(200):
        numbers = tuple(random_source.randint(MIN_NUMBER, MAX_NUMBER) for _ in range(3))
        candidates = list(_build_valid_candidates(numbers))
        if not candidates:
            continue

        expression, target = random_source.choice(candidates)
        problem = NumberPuzzleProblem(numbers=numbers, target=target, answer_expression=expression)

        if validate_problem(problem):
            return problem

    raise RuntimeError("無法產生有效的數字拼圖題目")


def validate_problem(problem: NumberPuzzleProblem) -> bool:
    try:
        value = evaluate_expression(problem.answer_expression)
    except ValueError:
        return False

    return value.denominator == 1 and value.numerator == problem.target


def write_problem_log(problem: NumberPuzzleProblem, log_file: Path = LOG_FILE) -> None:
    if not validate_problem(problem):
        raise ValueError("題目算式驗算失敗，拒絕寫入 log")

    log_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "game": "number_puzzle",
        "question": list(problem.numbers),
        "target": problem.target,
        "formula_answer": problem.answer_text,
    }

    with log_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def format_problem_reply(problem: NumberPuzzleProblem) -> str:
    return "\n".join(
        [
            "數字拼圖",
            f"題目：{problem.question_text}",
            f"目標值：{problem.target}",
            "輸入 !-a 查看答案",
        ]
    )


def format_answer_reply(problem: NumberPuzzleProblem) -> str:
    return "\n".join(
        [
            "數字拼圖答案",
            problem.answer_text,
        ]
    )


def evaluate_expression(expression: str) -> Fraction:
    python_expression = expression.replace("^", "**")

    try:
        tree = ast.parse(python_expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("算式語法錯誤") from exc

    return _evaluate_ast(tree.body)


def _build_valid_candidates(numbers: tuple[int, int, int]) -> list[tuple[str, int]]:
    candidates: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    for a, b, c in set(permutations(numbers, 3)):
        operands = (Fraction(a), Fraction(b), Fraction(c))

        for first_operator, second_operator in product(OPERATORS, repeat=2):
            left_first = _apply_operator(operands[0], operands[1], first_operator)
            if left_first is not None:
                value = _apply_operator(left_first, operands[2], second_operator)
                expression = f"({a} {first_operator} {b}) {second_operator} {c}"
                _append_candidate(candidates, seen, expression, value)

            right_first = _apply_operator(operands[1], operands[2], second_operator)
            if right_first is not None:
                value = _apply_operator(operands[0], right_first, first_operator)
                expression = f"{a} {first_operator} ({b} {second_operator} {c})"
                _append_candidate(candidates, seen, expression, value)

    return candidates


def _append_candidate(
    candidates: list[tuple[str, int]],
    seen: set[tuple[str, int]],
    expression: str,
    value: Fraction | None,
) -> None:
    if value is None or value.denominator != 1:
        return

    target = value.numerator
    if not MIN_TARGET <= target <= MAX_TARGET:
        return

    candidate = (expression, target)
    if candidate in seen:
        return

    if evaluate_expression(expression) != value:
        return

    seen.add(candidate)
    candidates.append(candidate)


def _evaluate_ast(node: ast.AST) -> Fraction:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return Fraction(node.value)

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_evaluate_ast(node.operand)

    if isinstance(node, ast.BinOp):
        left = _evaluate_ast(node.left)
        right = _evaluate_ast(node.right)

        if isinstance(node.op, ast.Add):
            operator = "+"
        elif isinstance(node.op, ast.Sub):
            operator = "-"
        elif isinstance(node.op, ast.Mult):
            operator = "*"
        elif isinstance(node.op, ast.Div):
            operator = "/"
        elif isinstance(node.op, ast.Pow):
            operator = "^"
        else:
            raise ValueError("不支援的運算符號")

        value = _apply_operator(left, right, operator)
        if value is None:
            raise ValueError("算式計算結果無效")

        return value

    raise ValueError("算式包含不支援的內容")


def _apply_operator(left: Fraction, right: Fraction, operator: str) -> Fraction | None:
    try:
        if operator == "+":
            value = left + right
        elif operator == "-":
            value = left - right
        elif operator == "*":
            value = left * right
        elif operator == "/":
            if right == 0:
                return None
            value = left / right
        elif operator == "^":
            value = _apply_power(left, right)
            if value is None:
                return None
        else:
            return None
    except (OverflowError, ZeroDivisionError):
        return None

    if abs(value) > MAX_INTERMEDIATE_ABS:
        return None

    return value


def _apply_power(left: Fraction, right: Fraction) -> Fraction | None:
    if left.denominator != 1 or right.denominator != 1:
        return None

    exponent = right.numerator
    if exponent < 0 or exponent > MAX_EXPONENT:
        return None

    if left == 0 and exponent == 0:
        return None

    return left**exponent
