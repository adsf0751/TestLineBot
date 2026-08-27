from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


DIGIT_COUNT = 4
DIGITS = "0123456789"
LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "one_a_two_b.log"
DEFAULT_BAN_MINUTES = 5
DEFAULT_CONSECUTIVE_GUESS_LIMIT = 3
MAX_BAN_MINUTES = 1440
MAX_CONSECUTIVE_GUESS_LIMIT = 20


@dataclass(frozen=True)
class GuessResult:
    guess: str
    a_count: int
    b_count: int
    line_user_id: str | None = None
    nickname: str | None = None

    @property
    def result_text(self) -> str:
        return f"{self.a_count}A{self.b_count}B"


@dataclass(frozen=True)
class MutedPlayer:
    line_user_id: str
    nickname: str | None
    muted_until: datetime


@dataclass
class OneATwoBSettings:
    ban_minutes: int = DEFAULT_BAN_MINUTES
    consecutive_guess_limit: int = DEFAULT_CONSECUTIVE_GUESS_LIMIT
    guess_ban_enabled: bool = True


@dataclass
class OneATwoBGame:
    answer: str
    guesses: list[GuessResult] = field(default_factory=list)
    muted_players: dict[str, MutedPlayer] = field(default_factory=dict)
    guess_ban_start_index: int = 0

    @property
    def is_solved(self) -> bool:
        return any(result.a_count == DIGIT_COUNT for result in self.guesses)


def create_game(rng: random.Random | None = None) -> OneATwoBGame:
    random_source = rng or random
    answer = "".join(random_source.sample(DIGITS, DIGIT_COUNT))

    return OneATwoBGame(answer=answer)


def validate_guess_text(guess: str) -> str | None:
    if len(guess) != DIGIT_COUNT:
        return "猜測必須是 4 位數字，例如 @-1234。"

    if any(digit not in DIGITS for digit in guess):
        return "猜測只能包含數字，例如 @-1234。"

    if len(set(guess)) != DIGIT_COUNT:
        return "猜測數字不可重複，例如 @-1234。"

    return None


def score_guess(answer: str, guess: str) -> GuessResult:
    answer_error = validate_guess_text(answer)
    if answer_error is not None:
        raise ValueError(f"答案格式錯誤：{answer_error}")

    guess_error = validate_guess_text(guess)
    if guess_error is not None:
        raise ValueError(guess_error)

    a_count = sum(answer_digit == guess_digit for answer_digit, guess_digit in zip(answer, guess))
    b_count = len(set(answer) & set(guess)) - a_count

    return GuessResult(guess=guess, a_count=a_count, b_count=b_count)


def submit_guess(
    game: OneATwoBGame,
    guess: str,
    line_user_id: str | None = None,
    nickname: str | None = None,
) -> GuessResult:
    if game.is_solved:
        raise ValueError("本局 1A2B 已結束，不能繼續猜測。")

    scored_result = score_guess(game.answer, guess)
    result = GuessResult(
        guess=scored_result.guess,
        a_count=scored_result.a_count,
        b_count=scored_result.b_count,
        line_user_id=line_user_id,
        nickname=nickname,
    )
    game.guesses.append(result)

    return result


def set_ban_minutes(settings: OneATwoBSettings, ban_minutes: int) -> None:
    error = validate_ban_minutes(ban_minutes)
    if error is not None:
        raise ValueError(error)

    settings.ban_minutes = ban_minutes


def validate_ban_minutes(ban_minutes: int) -> str | None:
    if ban_minutes < 1:
        return "禁言時間必須至少 1 分鐘，例如 /banTime-5。"

    if ban_minutes > MAX_BAN_MINUTES:
        return f"禁言時間不可超過 {MAX_BAN_MINUTES} 分鐘。"

    return None


def set_consecutive_guess_limit(settings: OneATwoBSettings, guess_limit: int) -> None:
    error = validate_consecutive_guess_limit(guess_limit)
    if error is not None:
        raise ValueError(error)

    settings.consecutive_guess_limit = guess_limit


def set_guess_ban_enabled(settings: OneATwoBSettings, enabled: bool) -> None:
    settings.guess_ban_enabled = enabled


def reset_guess_ban_tracking(game: OneATwoBGame) -> None:
    game.guess_ban_start_index = len(game.guesses)


def validate_consecutive_guess_limit(guess_limit: int) -> str | None:
    if guess_limit < 1:
        return "單一玩家連續猜測次數必須至少 1 次，例如 /guessLimit-3。"

    if guess_limit > MAX_CONSECUTIVE_GUESS_LIMIT:
        return f"單一玩家連續猜測次數不可超過 {MAX_CONSECUTIVE_GUESS_LIMIT} 次。"

    return None


def would_exceed_consecutive_guess_limit(
    game: OneATwoBGame,
    line_user_id: str | None,
    guess_limit: int,
    guess_ban_enabled: bool = True,
) -> bool:
    if not guess_ban_enabled or line_user_id is None:
        return False

    tracked_guesses = game.guesses[game.guess_ban_start_index:]
    consecutive_count = 0
    for guess_result in reversed(tracked_guesses):
        if guess_result.line_user_id != line_user_id:
            break
        consecutive_count += 1

    return consecutive_count >= guess_limit


def mute_player(
    game: OneATwoBGame,
    line_user_id: str,
    nickname: str | None,
    muted_at: datetime,
    ban_minutes: int,
) -> MutedPlayer:
    mute = MutedPlayer(
        line_user_id=line_user_id,
        nickname=nickname,
        muted_until=muted_at + timedelta(minutes=ban_minutes),
    )
    game.muted_players[line_user_id] = mute

    return mute


def get_active_mute(
    game: OneATwoBGame,
    line_user_id: str | None,
    now: datetime,
) -> MutedPlayer | None:
    if line_user_id is None:
        return None

    mute = game.muted_players.get(line_user_id)
    if mute is None:
        return None

    if mute.muted_until <= now:
        del game.muted_players[line_user_id]
        return None

    return mute


def collect_expired_mutes(game: OneATwoBGame, now: datetime) -> list[MutedPlayer]:
    expired_mutes: list[MutedPlayer] = []
    for line_user_id, mute in list(game.muted_players.items()):
        if mute.muted_until <= now:
            expired_mutes.append(mute)
            del game.muted_players[line_user_id]

    return expired_mutes


def release_all_mutes(game: OneATwoBGame) -> list[MutedPlayer]:
    released_mutes = list(game.muted_players.values())
    game.muted_players.clear()

    return released_mutes


def write_game_log(
    game: OneATwoBGame,
    action: str,
    result: GuessResult | None = None,
    muted_player: MutedPlayer | None = None,
    source_key: str | None = None,
    line_user_id: str | None = None,
    nickname: str | None = None,
    log_file: Path = LOG_FILE,
) -> None:
    if validate_guess_text(game.answer) is not None:
        raise ValueError("1A2B 答案格式錯誤，拒絕寫入 log")

    if result is not None and result not in game.guesses:
        raise ValueError("猜測結果不屬於目前回合，拒絕寫入 log")

    log_file.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "game": "one_a_two_b",
        "action": action,
        "answer": game.answer,
        "guess_count": len(game.guesses),
        "history": [_format_guess_record(guess_result) for guess_result in game.guesses],
    }

    if source_key is not None:
        record["source_key"] = source_key

    if line_user_id is not None:
        record["line_user_id"] = line_user_id

    if nickname is not None:
        record["nickname"] = nickname

    if result is not None:
        record["guess"] = result.guess
        record["result"] = result.result_text
        record["a_count"] = result.a_count
        record["b_count"] = result.b_count

    if muted_player is not None:
        record["muted_line_user_id"] = muted_player.line_user_id
        record["muted_until"] = muted_player.muted_until.isoformat(timespec="seconds")
        if muted_player.nickname is not None:
            record["muted_nickname"] = muted_player.nickname

    with log_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def format_new_game_reply() -> str:
    return "\n".join(
        [
            "1A2B 新遊戲已開始",
            "請輸入 @-xxxx 猜測 4 位不重複數字。",
            "輸入 @-h 查看指令。",
        ]
    )


def _format_guess_record(result: GuessResult) -> dict[str, str | int]:
    record: dict[str, str | int] = {
        "guess": result.guess,
        "result": result.result_text,
        "a_count": result.a_count,
        "b_count": result.b_count,
    }

    if result.line_user_id is not None:
        record["line_user_id"] = result.line_user_id

    if result.nickname is not None:
        record["nickname"] = result.nickname

    return record


def format_guess_reply(result: GuessResult) -> str:
    lines = [
        f"猜測：{result.guess}",
        f"結果：{result.result_text}",
    ]

    if result.a_count == DIGIT_COUNT:
        lines.append("答對了。")

    return "\n".join(lines)


def format_locked_game_reply() -> str:
    return "\n".join(
        [
            "本局 1A2B 已結束，不能繼續猜測。",
            "輸入 @-l 查看當前紀錄，或輸入 @-n 開新遊戲。",
        ]
    )


def format_ban_time_reply(ban_minutes: int) -> str:
    return f"1A2B 禁言時間已設定為 {ban_minutes} 分鐘。"


def format_guess_limit_reply(guess_limit: int) -> str:
    return f"1A2B 單一玩家連續猜測上限已設定為 {guess_limit} 次。"


def format_guess_ban_enabled_reply(enabled: bool) -> str:
    if enabled:
        return "1A2B 連續猜測禁言已啟用。"

    return "1A2B 連續猜測禁言已關閉。"


def format_newly_muted_player_reply(
    mute: MutedPlayer,
    guess_limit: int,
    ban_minutes: int,
) -> str:
    return "\n".join(
        [
            f"{_format_player_name(mute)} 連續猜測超過 {guess_limit} 次，暫停猜測 {ban_minutes} 分鐘。",
            "其他玩家可以繼續猜測。",
        ]
    )


def format_active_mute_reply(mute: MutedPlayer, now: datetime) -> str:
    remaining_seconds = max(0, int((mute.muted_until - now).total_seconds()))
    remaining_minutes = max(1, (remaining_seconds + 59) // 60)

    return "\n".join(
        [
            f"{_format_player_name(mute)} 目前暫停猜測中，約 {remaining_minutes} 分鐘後可繼續。",
            "其他玩家可以繼續猜測。",
        ]
    )


def format_mute_release_notices(mutes: list[MutedPlayer]) -> str:
    if not mutes:
        return ""

    return "\n".join(
        f"{_format_player_name(mute)} 的 1A2B 暫停猜測已解除，可以接續遊玩。"
        for mute in mutes
    )


def format_answer_reply(game: OneATwoBGame) -> str:
    return "\n".join(
        [
            "1A2B 答案",
            game.answer,
        ]
    )


def format_history_reply(game: OneATwoBGame) -> str:
    if not game.guesses:
        return "目前沒有猜測紀錄。"

    lines = ["1A2B 目前回合猜測紀錄"]
    for index, result in enumerate(game.guesses, start=1):
        lines.append(f"{index}. {result.guess}：{result.result_text}")

    return "\n".join(lines)


def format_help_reply() -> str:
    return "\n".join(
        [
            "1A2B 可用指令",
            "@-n：開新遊戲",
            "@-a：查看答案",
            "@-l：查看當前回合猜測紀錄",
            "@-h：查看 1A2B 指令",
            "@-xxxx：猜測 4 位不重複數字，例如 @-1234",
        ]
    )


def _format_player_name(mute: MutedPlayer) -> str:
    if mute.nickname is not None:
        return f"玩家 {mute.nickname}"

    return "該玩家"
