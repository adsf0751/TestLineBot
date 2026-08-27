import json
import random
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from games.one_a_two_b import (
    OneATwoBGame,
    OneATwoBSettings,
    collect_expired_mutes,
    create_game,
    format_active_mute_reply,
    format_answer_reply,
    format_ban_time_reply,
    format_guess_ban_enabled_reply,
    format_guess_reply,
    format_guess_limit_reply,
    format_help_reply,
    format_history_reply,
    format_locked_game_reply,
    format_mute_release_notices,
    format_new_game_reply,
    format_newly_muted_player_reply,
    get_active_mute,
    mute_player,
    release_all_mutes,
    reset_guess_ban_tracking,
    score_guess,
    set_ban_minutes,
    set_consecutive_guess_limit,
    set_guess_ban_enabled,
    submit_guess,
    would_exceed_consecutive_guess_limit,
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

        result = submit_guess(game, "1243", line_user_id="U123", nickname="小明")

        self.assertEqual("2A2B", result.result_text)
        self.assertEqual([result], game.guesses)
        self.assertEqual("U123", result.line_user_id)
        self.assertEqual("小明", result.nickname)
        self.assertIn("1. 1243：2A2B", format_history_reply(game))

    def test_consecutive_guess_limit_uses_guess_ban_switch(self):
        game = OneATwoBGame(answer="1234")

        submit_guess(game, "5678", line_user_id="A")
        submit_guess(game, "5679", line_user_id="A")

        self.assertTrue(would_exceed_consecutive_guess_limit(game, "A", 2))
        self.assertFalse(would_exceed_consecutive_guess_limit(game, "A", 2, guess_ban_enabled=False))
        self.assertFalse(would_exceed_consecutive_guess_limit(game, "B", 2))

        reset_guess_ban_tracking(game)
        self.assertFalse(would_exceed_consecutive_guess_limit(game, "A", 2))

    def test_mute_lifecycle_and_setting_validation(self):
        game = OneATwoBGame(answer="1234")
        settings = OneATwoBSettings()
        now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        later = datetime(2026, 1, 1, 12, 6, tzinfo=timezone.utc)

        set_ban_minutes(settings, 5)
        set_consecutive_guess_limit(settings, 2)
        set_guess_ban_enabled(settings, False)
        mute = mute_player(game, "U123", "小明", now, settings.ban_minutes)

        self.assertFalse(settings.guess_ban_enabled)
        self.assertIs(mute, get_active_mute(game, "U123", now))
        self.assertIn("5 分鐘", format_ban_time_reply(settings.ban_minutes))
        self.assertIn("2 次", format_guess_limit_reply(settings.consecutive_guess_limit))
        self.assertIn("關閉", format_guess_ban_enabled_reply(settings.guess_ban_enabled))
        self.assertIn("小明", format_newly_muted_player_reply(mute, 2, 5))
        self.assertIn("約 5 分鐘", format_active_mute_reply(mute, now))

        self.assertEqual([mute], collect_expired_mutes(game, later))
        self.assertIn("可以接續遊玩", format_mute_release_notices([mute]))
        self.assertIsNone(get_active_mute(game, "U123", later))

        mute_player(game, "U123", "小明", now, settings.ban_minutes)
        self.assertEqual(1, len(release_all_mutes(game)))
        self.assertEqual({}, game.muted_players)

    def test_submit_guess_rejects_after_game_is_solved(self):
        game = OneATwoBGame(answer="1234")
        solved_result = submit_guess(game, "1234")

        with self.assertRaises(ValueError) as context:
            submit_guess(game, "1325")

        self.assertTrue(game.is_solved)
        self.assertEqual([solved_result], game.guesses)
        self.assertIn("已結束", str(context.exception))

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
        self.assertIn("@-l", format_locked_game_reply())

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
