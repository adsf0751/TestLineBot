from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


LOG_FILE = Path(__file__).resolve().parents[1] / "logs" / "line_users.log"
MAX_NICKNAME_LENGTH = 30
MAX_VICTORY_DECLARATION_LENGTH = 100


@dataclass(frozen=True)
class LineUser:
    line_user_id: str
    nickname: str


def bind_user(
    users: dict[str, LineUser],
    line_user_id: str,
    nickname: str,
    source_key: str | None = None,
    log_file: Path = LOG_FILE,
) -> LineUser:
    clean_nickname = nickname.strip()
    error = validate_nickname(clean_nickname)
    if error is not None:
        raise ValueError(error)

    user = LineUser(line_user_id=line_user_id, nickname=clean_nickname)
    users[line_user_id] = user
    write_user_log(user, action="bind_user", source_key=source_key, log_file=log_file)

    return user


def validate_nickname(nickname: str) -> str | None:
    clean_nickname = nickname.strip()

    if not clean_nickname:
        return "暱稱不可空白，請使用 /user-暱稱 進行綁定。"

    if len(clean_nickname) > MAX_NICKNAME_LENGTH:
        return f"暱稱不可超過 {MAX_NICKNAME_LENGTH} 個字。"

    return None


def set_victory_declaration(
    victory_declarations: dict[str, str],
    line_user_id: str,
    declaration: str,
    source_key: str | None = None,
    nickname: str | None = None,
    log_file: Path = LOG_FILE,
) -> str:
    clean_declaration = declaration.strip()
    error = validate_victory_declaration(clean_declaration)
    if error is not None:
        raise ValueError(error)

    victory_declarations[line_user_id] = clean_declaration
    write_victory_declaration_log(
        line_user_id,
        clean_declaration,
        source_key=source_key,
        nickname=nickname,
        log_file=log_file,
    )

    return clean_declaration


def validate_victory_declaration(declaration: str) -> str | None:
    clean_declaration = declaration.strip()

    if not clean_declaration:
        return "勝利宣言不可空白，請使用 /userWin-勝利宣言 進行設定。"

    if len(clean_declaration) > MAX_VICTORY_DECLARATION_LENGTH:
        return f"勝利宣言不可超過 {MAX_VICTORY_DECLARATION_LENGTH} 個字。"

    return None


def get_user(users: dict[str, LineUser], line_user_id: str | None) -> LineUser | None:
    if line_user_id is None:
        return None

    return users.get(line_user_id)


def get_nickname(users: dict[str, LineUser], line_user_id: str | None) -> str | None:
    user = get_user(users, line_user_id)
    if user is None:
        return None

    return user.nickname


def get_victory_declaration(
    victory_declarations: dict[str, str],
    line_user_id: str | None,
) -> str | None:
    if line_user_id is None:
        return None

    return victory_declarations.get(line_user_id)


def load_users_from_log(log_file: Path = LOG_FILE) -> dict[str, LineUser]:
    users: dict[str, LineUser] = {}
    if not log_file.exists():
        return users

    for line in log_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if record.get("action") != "bind_user":
            continue

        line_user_id = record.get("line_user_id")
        nickname = record.get("nickname")
        if not isinstance(line_user_id, str) or not isinstance(nickname, str):
            continue

        clean_nickname = nickname.strip()
        if validate_nickname(clean_nickname) is not None:
            continue

        users[line_user_id] = LineUser(line_user_id=line_user_id, nickname=clean_nickname)

    return users


def load_victory_declarations_from_log(log_file: Path = LOG_FILE) -> dict[str, str]:
    victory_declarations: dict[str, str] = {}
    if not log_file.exists():
        return victory_declarations

    for line in log_file.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if record.get("action") != "set_victory_declaration":
            continue

        line_user_id = record.get("line_user_id")
        declaration = record.get("victory_declaration")
        if not isinstance(line_user_id, str) or not isinstance(declaration, str):
            continue

        clean_declaration = declaration.strip()
        if validate_victory_declaration(clean_declaration) is not None:
            continue

        victory_declarations[line_user_id] = clean_declaration

    return victory_declarations


def format_bind_reply(user: LineUser) -> str:
    return "\n".join(
        [
            f"玩家：{user.nickname}",
            "已完成 LINE 使用者暱稱綁定。",
        ]
    )


def format_victory_declaration_reply(declaration: str) -> str:
    return "\n".join(
        [
            "勝利宣言已設定。",
            f"勝利宣言：{declaration}",
        ]
    )


def format_user_context(users: dict[str, LineUser], line_user_id: str | None) -> str:
    nickname = get_nickname(users, line_user_id)
    if nickname is not None:
        return f"玩家：{nickname}"

    if line_user_id is None:
        return "玩家：無法辨識 LINE 使用者"

    return "玩家：未綁定（輸入 /user-暱稱 綁定）"


def write_user_log(
    user: LineUser,
    action: str,
    source_key: str | None = None,
    log_file: Path = LOG_FILE,
) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "action": action,
        "line_user_id": user.line_user_id,
        "nickname": user.nickname,
    }

    if source_key is not None:
        record["source_key"] = source_key

    with log_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_victory_declaration_log(
    line_user_id: str,
    declaration: str,
    source_key: str | None = None,
    nickname: str | None = None,
    log_file: Path = LOG_FILE,
) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "action": "set_victory_declaration",
        "line_user_id": line_user_id,
        "victory_declaration": declaration,
    }

    if nickname is not None:
        record["nickname"] = nickname

    if source_key is not None:
        record["source_key"] = source_key

    with log_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")
