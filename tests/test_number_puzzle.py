import json
import random
import tempfile
import unittest
from pathlib import Path

from games.number_puzzle import (
    NumberPuzzleProblem,
    create_problem,
    format_answer_reply,
    format_problem_reply,
    validate_problem,
    write_problem_log,
)


class NumberPuzzleTest(unittest.TestCase):
    def test_create_problem_generates_valid_integer_target(self):
        rng = random.Random(42)

        for _ in range(100):
            problem = create_problem(rng)

            self.assertEqual(3, len(problem.numbers))
            self.assertTrue(all(1 <= number <= 9 for number in problem.numbers))
            self.assertTrue(1 <= problem.target <= 999)
            self.assertTrue(validate_problem(problem))

    def test_replies_contain_question_target_and_answer(self):
        problem = NumberPuzzleProblem((2, 3, 4), 20, "(2 + 3) * 4")

        self.assertIn("題目：2、3、4", format_problem_reply(problem))
        self.assertIn("目標值：20", format_problem_reply(problem))
        self.assertIn("(2 + 3) * 4 = 20", format_answer_reply(problem))

    def test_write_problem_log_validates_and_records_problem(self):
        problem = NumberPuzzleProblem((2, 3, 4), 20, "(2 + 3) * 4")

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "number_puzzle.log"
            write_problem_log(problem, log_file)

            record = json.loads(log_file.read_text(encoding="utf-8"))

        self.assertIn("time", record)
        self.assertEqual("number_puzzle", record["game"])
        self.assertEqual([2, 3, 4], record["question"])
        self.assertEqual(20, record["target"])
        self.assertEqual("(2 + 3) * 4 = 20", record["formula_answer"])

    def test_invalid_problem_is_not_logged(self):
        problem = NumberPuzzleProblem((2, 3, 4), 21, "(2 + 3) * 4")

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "number_puzzle.log"

            with self.assertRaises(ValueError):
                write_problem_log(problem, log_file)

            self.assertFalse(log_file.exists())


if __name__ == "__main__":
    unittest.main()
