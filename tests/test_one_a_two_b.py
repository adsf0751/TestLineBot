import json
import random
import tempfile
import unittest
from pathlib import Path

from games.one_a_two_b import (
    OneATwoBGame,
    create_game,
    format_answer_reply,
    format_guess_reply,
    format_help_reply,
    format_history_reply,
    format_new_game_reply,
    score_guess,
    submit_guess,
    validate_guess_text,
    write_game_log,
)


class OneATwoBTest(unittest.TestCase):
    def test_create_game_generates_four_unique_digits(self):
        rng = random.Random(42)

        for _ in range(100):
            game = create_game(rng)

            self.assertEqual(4, len(game.answer))
            self.assertTrue(game.answer.isdigit())
            self.assertEqual(4, len(set(game.answer)))

    def test_score_guess_returns_a_and_b_counts(self):
        result = score_guess("1234", "1325")

        self.assertEqual("1325", result.guess)
        self.assertEqual(1, result.a_count)
        self.assertEqual(2, result.b_count)
        self.assertEqual("1A2B", result.result_text)

    def test_submit_guess_records_history(self):
        game = OneATwoBGame(answer="1234")

        result = submit_guess(game, "1243")

        self.assertEqual("2A2B", result.result_text)
        self.assertEqual([result], game.guesses)
        self.assertIn("1. 1243：2A2B", format_history_reply(game))

    def test_validate_guess_rejects_invalid_text(self):
        self.assertIsNone(validate_guess_text("1234"))
        self.assertIsNotNone(validate_guess_text("123"))
        self.assertIsNotNone(validate_guess_text("12A4"))
        self.assertIsNotNone(validate_guess_text("1123"))
        self.assertIsNotNone(validate_guess_text("１２３４"))

    def test_reply_formatters_contain_commands_and_state(self):
        game = OneATwoBGame(answer="1234")
        solved_result = submit_guess(game, "1234")

        self.assertIn("@-xxxx", format_help_reply())
        self.assertIn("@-h", format_new_game_reply())
        self.assertIn("1234", format_answer_reply(game))
        self.assertIn("4A0B", format_guess_reply(solved_result))
        self.assertIn("答對了", format_guess_reply(solved_result))

    def test_write_game_log_records_new_game_guess_and_answer(self):
        game = OneATwoBGame(answer="1234")

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "one_a_two_b.log"
            write_game_log(
                game,
                action="new_game",
                source_key="user:test",
                line_user_id="U123",
                nickname="小明",
                log_file=log_file,
            )

            result = submit_guess(game, "1325")
            write_game_log(
                game,
                action="guess",
                result=result,
                source_key="user:test",
                line_user_id="U123",
                nickname="小明",
                log_file=log_file,
            )
            write_game_log(
                game,
                action="show_history",
                source_key="user:test",
                line_user_id="U123",
                nickname="小明",
                log_file=log_file,
            )
            write_game_log(
                game,
                action="show_answer",
                source_key="user:test",
                line_user_id="U123",
                nickname="小明",
                log_file=log_file,
            )

            records = [
                json.loads(line)
                for line in log_file.read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual("new_game", records[0]["action"])
        self.assertEqual("1234", records[0]["answer"])
        self.assertEqual("user:test", records[0]["source_key"])
        self.assertEqual("U123", records[0]["line_user_id"])
        self.assertEqual("小明", records[0]["nickname"])
        self.assertEqual(0, records[0]["guess_count"])

        self.assertEqual("guess", records[1]["action"])
        self.assertEqual("U123", records[1]["line_user_id"])
        self.assertEqual("小明", records[1]["nickname"])
        self.assertEqual("1325", records[1]["guess"])
        self.assertEqual("1A2B", records[1]["result"])
        self.assertEqual(1, records[1]["a_count"])
        self.assertEqual(2, records[1]["b_count"])
        self.assertEqual([{"guess": "1325", "result": "1A2B", "a_count": 1, "b_count": 2}], records[1]["history"])

        self.assertEqual("show_history", records[2]["action"])
        self.assertEqual(1, records[2]["guess_count"])
        self.assertEqual("show_answer", records[3]["action"])
        self.assertEqual(1, records[3]["guess_count"])

    def test_write_game_log_rejects_unrelated_guess_result(self):
        game = OneATwoBGame(answer="1234")
        unrelated_result = score_guess("1234", "1325")

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "one_a_two_b.log"

            with self.assertRaises(ValueError):
                write_game_log(game, action="guess", result=unrelated_result, log_file=log_file)

            self.assertFalse(log_file.exists())


if __name__ == "__main__":
    unittest.main()
