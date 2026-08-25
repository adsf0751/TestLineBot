import json
import tempfile
import unittest
from pathlib import Path

from services.command_router import GameSessionState, LogFiles, handle_command


class CommandRouterTest(unittest.TestCase):
    def test_user_binding_and_help_can_run_without_line_sdk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={})

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
        self.assertEqual("local-user", record["line_user_id"])
        self.assertEqual("本地玩家", record["nickname"])

    def test_number_puzzle_command_flow_writes_user_info_to_log(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_files = self._make_log_files(temp_dir)
            state = GameSessionState(line_users={})
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
            state = GameSessionState(line_users={})
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

    def test_unknown_command_returns_none(self):
        state = GameSessionState(line_users={})

        reply = handle_command(
            "hello",
            source_key="local:user_id:local-user",
            line_user_id="local-user",
            state=state,
        )

        self.assertIsNone(reply)

    def _bind_local_user(self, state: GameSessionState, log_files: LogFiles) -> None:
        handle_command(
            "/user-本地玩家",
            source_key="local:user_id:local-user",
            line_user_id="local-user",
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
