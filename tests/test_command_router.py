import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.command_router import GameSessionState, LogFiles, handle_command


class CommandRouterTest(unittest.TestCase):
    def test_user_binding_and_help_can_run_without_line_sdk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})

            bind_reply = handle_command(
                "/user-本地玩家",
                source_key="local:user_id:local-user",
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            help_reply = handle_command(
                "/-h",
                source_key="local:user_id:local-user",
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )

            record = json.loads(log_files.line_users.read_text(encoding="utf-8"))

        self.assertIn("玩家：本地玩家", bind_reply)
        self.assertTrue(help_reply.startswith("玩家：本地玩家"))
        self.assertIn("/user-暱稱", help_reply)
        self.assertIn("/userWin-勝利宣言", help_reply)
        self.assertIn("/banTime-分鐘", help_reply)
        self.assertIn("/guessLimit-次數", help_reply)
        self.assertIn("/guessBan-T/F", help_reply)
        self.assertEqual("local-user", record["line_user_id"])
        self.assertEqual("本地玩家", record["nickname"])

    def test_one_a_two_b_setting_commands_update_runtime_limits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            self._bind_local_user(state, log_files)

            ban_reply = handle_command(
                "/banTime-7",
                source_key="local:user_id:local-user",
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            limit_reply = handle_command(
                "/guessLimit-2",
                source_key="local:user_id:local-user",
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            disabled_reply = handle_command(
                "/guessBan-F",
                source_key="local:user_id:local-user",
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            enabled_reply = handle_command(
                "/guessBan-T",
                source_key="local:user_id:local-user",
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )

        self.assertIn("7 分鐘", ban_reply)
        self.assertIn("2 次", limit_reply)
        self.assertIn("關閉", disabled_reply)
        self.assertIn("啟用", enabled_reply)
        self.assertEqual(7, state.one_a_two_b_settings.ban_minutes)
        self.assertEqual(2, state.one_a_two_b_settings.consecutive_guess_limit)
        self.assertTrue(state.one_a_two_b_settings.guess_ban_enabled)

    def test_number_puzzle_command_flow_writes_user_info_to_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            self._bind_local_user(state, log_files)

            new_reply = handle_command(
                "!-n",
                source_key="local:user_id:local-user",
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            answer_reply = handle_command(
                "!-a",
                source_key="local:user_id:local-user",
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            record = json.loads(log_files.number_puzzle.read_text(encoding="utf-8"))

        self.assertIn("玩家：本地玩家", new_reply)
        self.assertIn("目標值：", new_reply)
        self.assertIn("數字拼圖答案", answer_reply)
        self.assertEqual("local-user", record["line_user_id"])
        self.assertEqual("本地玩家", record["nickname"])

    def test_one_a_two_b_command_flow_writes_user_info_to_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            self._bind_local_user(state, log_files)
            source_key = "local:user_id:local-user"

            new_reply = handle_command(
                "@-n",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            answer = state.current_one_a_two_b_games[source_key].answer
            guess_reply = handle_command(
                f"@-{answer}",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            history_reply = handle_command(
                "@-l",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            records = [
                json.loads(line)
                for line in log_files.one_a_two_b.read_text(encoding="utf-8").splitlines()
            ]

        self.assertIn("1A2B 新遊戲已開始", new_reply)
        self.assertIn("4A0B", guess_reply)
        self.assertIn(f"1. {answer}：4A0B", history_reply)
        self.assertEqual(["new_game", "guess", "show_history"], [record["action"] for record in records])
        self.assertTrue(all(record["line_user_id"] == "local-user" for record in records))
        self.assertTrue(all(record["nickname"] == "本地玩家" for record in records))

    def test_one_a_two_b_locks_after_win_until_new_game(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            self._bind_local_user(state, log_files)
            source_key = "local:user_id:local-user"

            handle_command(
                "@-n",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            answer = state.current_one_a_two_b_games[source_key].answer
            first_guess_reply = handle_command(
                f"@-{answer}",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            locked_reply = handle_command(
                "@-9876",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            history_reply = handle_command(
                "@-l",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            restart_reply = handle_command(
                "@-n",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            records = [
                json.loads(line)
                for line in log_files.one_a_two_b.read_text(encoding="utf-8").splitlines()
            ]

        self.assertIn("答對了", first_guess_reply)
        self.assertIn("已結束", locked_reply)
        self.assertIn("@-l", locked_reply)
        self.assertIn(f"1. {answer}：4A0B", history_reply)
        self.assertIn("1A2B 新遊戲已開始", restart_reply)
        self.assertEqual(["new_game", "guess", "show_history", "new_game"], [record["action"] for record in records])
        self.assertEqual(1, records[2]["guess_count"])
        self.assertEqual(0, records[3]["guess_count"])

    def test_one_a_two_b_mutes_repeated_guesser_when_guess_ban_is_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            source_key = "group:group_id:G1"
            now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
            self._bind_user(state, log_files, source_key, "player-a", "小明")
            self._bind_user(state, log_files, source_key, "player-b", "阿芳")
            handle_command("/banTime-10", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("/guessLimit-2", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("@-n", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            state.current_one_a_two_b_games[source_key].answer = "1234"

            for offset, guess in enumerate(("@-5678", "@-5679"), start=1):
                reply = handle_command(
                    guess,
                    source_key=source_key,
                    line_user_id="player-a",
                    state=state,
                    log_files=log_files,
                    now=now + timedelta(seconds=offset),
                )
                self.assertIn("結果：", reply)

            muted_reply = handle_command(
                "@-5689",
                source_key=source_key,
                line_user_id="player-a",
                state=state,
                log_files=log_files,
                now=now + timedelta(seconds=3),
            )
            active_mute_reply = handle_command(
                "@-5680",
                source_key=source_key,
                line_user_id="player-a",
                state=state,
                log_files=log_files,
                now=now + timedelta(seconds=4),
            )
            other_player_reply = handle_command(
                "@-6703",
                source_key=source_key,
                line_user_id="player-b",
                state=state,
                log_files=log_files,
                now=now + timedelta(seconds=5),
            )
            release_reply = handle_command(
                "@-l",
                source_key=source_key,
                line_user_id="player-b",
                state=state,
                log_files=log_files,
                now=now + timedelta(minutes=11),
            )
            returned_reply = handle_command(
                "@-6704",
                source_key=source_key,
                line_user_id="player-a",
                state=state,
                log_files=log_files,
                now=now + timedelta(minutes=11, seconds=1),
            )
            records = [
                json.loads(line)
                for line in log_files.one_a_two_b.read_text(encoding="utf-8").splitlines()
            ]
            guess_records = [record for record in records if record["action"] == "guess"]

        self.assertIn("玩家 小明 連續猜測超過 2 次", muted_reply)
        self.assertIn("暫停猜測中", active_mute_reply)
        self.assertIn("結果：", other_player_reply)
        self.assertIn("玩家 小明 的 1A2B 暫停猜測已解除，可以接續遊玩", release_reply)
        self.assertIn("結果：", returned_reply)
        mute_records = [record for record in records if record["action"] == "mute_player"]
        self.assertEqual(1, len(mute_records))
        self.assertEqual("player-a", mute_records[0]["muted_line_user_id"])
        self.assertEqual(4, len(guess_records))
        self.assertNotIn("5689", [record["guess"] for record in guess_records])
        self.assertNotIn("5680", [record["guess"] for record in guess_records])

    def test_one_a_two_b_guess_ban_switch_can_disable_muting(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            source_key = "group:group_id:G1"
            now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
            self._bind_user(state, log_files, source_key, "player-a", "小明")
            handle_command("/guessLimit-1", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("/guessBan-F", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("@-n", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            state.current_one_a_two_b_games[source_key].answer = "1234"

            first_reply = handle_command("@-5678", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            second_reply = handle_command("@-5679", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            third_reply = handle_command("@-5689", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            records = [
                json.loads(line)
                for line in log_files.one_a_two_b.read_text(encoding="utf-8").splitlines()
            ]

        self.assertIn("結果：", first_reply)
        self.assertIn("結果：", second_reply)
        self.assertIn("結果：", third_reply)
        self.assertNotIn("mute_player", [record["action"] for record in records])

    def test_guess_ban_disable_releases_existing_mutes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            source_key = "group:group_id:G1"
            now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
            self._bind_user(state, log_files, source_key, "player-a", "小明")
            handle_command("/guessLimit-1", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("@-n", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            state.current_one_a_two_b_games[source_key].answer = "1234"
            handle_command("@-5678", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            muted_reply = handle_command("@-5679", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)

            disabled_reply = handle_command(
                "/guessBan-F",
                source_key=source_key,
                line_user_id="player-a",
                state=state,
                log_files=log_files,
                now=now,
            )
            resumed_reply = handle_command(
                "@-5689",
                source_key=source_key,
                line_user_id="player-a",
                state=state,
                log_files=log_files,
                now=now,
            )

        self.assertIn("暫停猜測", muted_reply)
        self.assertIn("關閉", disabled_reply)
        self.assertIn("玩家 小明 的 1A2B 暫停猜測已解除，可以接續遊玩", disabled_reply)
        self.assertIn("結果：", resumed_reply)
        self.assertEqual({}, state.current_one_a_two_b_games[source_key].muted_players)

    def test_guess_ban_enable_restarts_consecutive_guess_tracking(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            source_key = "group:group_id:G1"
            now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
            self._bind_user(state, log_files, source_key, "player-a", "小明")
            handle_command("/guessLimit-1", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("/guessBan-F", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("@-n", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            state.current_one_a_two_b_games[source_key].answer = "1234"
            handle_command("@-5678", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            handle_command("@-5679", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)

            enabled_reply = handle_command(
                "/guessBan-T",
                source_key=source_key,
                line_user_id="player-a",
                state=state,
                log_files=log_files,
                now=now,
            )
            first_after_enable_reply = handle_command(
                "@-5689",
                source_key=source_key,
                line_user_id="player-a",
                state=state,
                log_files=log_files,
                now=now,
            )
            second_after_enable_reply = handle_command(
                "@-5680",
                source_key=source_key,
                line_user_id="player-a",
                state=state,
                log_files=log_files,
                now=now,
            )

        self.assertIn("啟用", enabled_reply)
        self.assertIn("結果：", first_after_enable_reply)
        self.assertIn("暫停猜測", second_after_enable_reply)

    def test_one_a_two_b_new_game_releases_active_mutes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            source_key = "group:group_id:G1"
            now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
            self._bind_user(state, log_files, source_key, "player-a", "小明")
            self._bind_user(state, log_files, source_key, "player-b", "阿芳")
            handle_command("/banTime-10", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("/guessLimit-1", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files)
            handle_command("@-n", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            state.current_one_a_two_b_games[source_key].answer = "1234"
            handle_command("@-5678", source_key=source_key, line_user_id="player-b", state=state, log_files=log_files, now=now)
            handle_command("@-5679", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)
            handle_command("@-5689", source_key=source_key, line_user_id="player-a", state=state, log_files=log_files, now=now)

            restart_reply = handle_command(
                "@-n",
                source_key=source_key,
                line_user_id="player-b",
                state=state,
                log_files=log_files,
                now=now + timedelta(minutes=1),
            )

        self.assertIn("1A2B 新遊戲已開始", restart_reply)
        self.assertIn("玩家 小明 的 1A2B 暫停猜測已解除，可以接續遊玩", restart_reply)
        self.assertEqual({}, state.current_one_a_two_b_games[source_key].muted_players)

    def test_user_win_declaration_is_announced_when_one_a_two_b_is_solved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={}, victory_declarations={})
            self._bind_local_user(state, log_files)
            source_key = "local:user_id:local-user"

            declaration_reply = handle_command(
                "/userWin-這場我收下了",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            handle_command(
                "@-n",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            answer = state.current_one_a_two_b_games[source_key].answer
            guess_reply = handle_command(
                f"@-{answer}",
                source_key=source_key,
                line_user_id="local-user",
                state=state,
                log_files=log_files,
            )
            user_records = [
                json.loads(line)
                for line in log_files.line_users.read_text(encoding="utf-8").splitlines()
            ]

        self.assertIn("勝利宣言已設定", declaration_reply)
        self.assertIn("答對了", guess_reply)
        self.assertIn("勝利宣言：這場我收下了", guess_reply)
        self.assertEqual("set_victory_declaration", user_records[1]["action"])
        self.assertEqual("這場我收下了", user_records[1]["victory_declaration"])

    def test_unknown_command_returns_none(self):
        state = GameSessionState(line_users={}, victory_declarations={})

        reply = handle_command(
            "hello",
            source_key="local:user_id:local-user",
            line_user_id="local-user",
            state=state,
        )

        self.assertIsNone(reply)

    def _bind_local_user(self, state: GameSessionState, log_files: LogFiles) -> None:
        self._bind_user(state, log_files, "local:user_id:local-user", "local-user", "本地玩家")

    def _bind_user(
        self,
        state: GameSessionState,
        log_files: LogFiles,
        source_key: str,
        line_user_id: str,
        nickname: str,
    ) -> None:
        handle_command(
            f"/user-{nickname}",
            source_key=source_key,
            line_user_id=line_user_id,
            state=state,
            log_files=log_files,
        )

    def _make_log_files(self, temp_dir: str) -> LogFiles:
        base_path = Path(temp_dir)

        return LogFiles(
            line_users=base_path / "line_users.log",
            number_puzzle=base_path / "number_puzzle.log",
            one_a_two_b=base_path / "one_a_two_b.log",
        )


if __name__ == "__main__":
    unittest.main()
