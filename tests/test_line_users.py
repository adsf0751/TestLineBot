import json
import tempfile
import unittest
from pathlib import Path

from services.line_users import (
    LineUser,
    bind_user,
    format_bind_reply,
    format_user_context,
    get_nickname,
    load_users_from_log,
    validate_nickname,
)


class LineUsersTest(unittest.TestCase):
    def test_bind_user_records_nickname_by_line_user_id(self):
        users = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "line_users.log"
            user = bind_user(
                users,
                line_user_id="U123",
                nickname="小明",
                source_key="user:user_id:U123",
                log_file=log_file,
            )

            record = json.loads(log_file.read_text(encoding="utf-8"))

        self.assertEqual(LineUser(line_user_id="U123", nickname="小明"), user)
        self.assertEqual("小明", get_nickname(users, "U123"))
        self.assertEqual("bind_user", record["action"])
        self.assertEqual("U123", record["line_user_id"])
        self.assertEqual("小明", record["nickname"])
        self.assertEqual("user:user_id:U123", record["source_key"])

    def test_bind_user_trims_nickname_and_formats_reply(self):
        users = {}

        with tempfile.TemporaryDirectory() as temp_dir:
            user = bind_user(users, "U123", "  阿芳  ", log_file=Path(temp_dir) / "line_users.log")

        self.assertEqual("阿芳", user.nickname)
        self.assertIn("玩家：阿芳", format_bind_reply(user))

    def test_validate_nickname_rejects_blank_and_too_long_text(self):
        self.assertIsNotNone(validate_nickname(""))
        self.assertIsNotNone(validate_nickname(" " * 4))
        self.assertIsNotNone(validate_nickname("一" * 31))
        self.assertIsNone(validate_nickname("玩家A"))

    def test_format_user_context_handles_bound_and_unbound_users(self):
        users = {"U123": LineUser(line_user_id="U123", nickname="小明")}

        self.assertEqual("玩家：小明", format_user_context(users, "U123"))
        self.assertIn("未綁定", format_user_context(users, "U456"))
        self.assertIn("無法辨識", format_user_context(users, None))

    def test_load_users_from_log_restores_latest_binding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "line_users.log"
            users = {}
            bind_user(users, "U123", "小明", log_file=log_file)
            bind_user(users, "U123", "阿明", log_file=log_file)

            restored_users = load_users_from_log(log_file)

        self.assertEqual("阿明", restored_users["U123"].nickname)


if __name__ == "__main__":
    unittest.main()
