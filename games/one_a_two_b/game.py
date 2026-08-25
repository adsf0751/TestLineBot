from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


DIGIT_COUNT = 4
DIGITS = "0123456789"
LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "one_a_two_b.log"


@dataclass(frozen=True)
class GuessResult:
    guess: str
    a_count: int
    b_count: int

    @property
    def result_text(self) -> str:
        return f"{self.a_count}A{self.b_count}B"


@dataclass
class OneATwoBGame:
    answer: str
    guesses: list[GuessResult] = field(default_factory=list)


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


def submit_guess(game: OneATwoBGame, guess: str) -> GuessResult:
    result = score_guess(game.answer, guess)
    game.guesses.append(result)

    return result


def write_game_log(
    game: OneATwoBGame,
    action: str,
    result: GuessResult | None = None,
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
    return {
        "guess": result.guess,
        "result": result.result_text,
        "a_count": result.a_count,
        "b_count": result.b_count,
    }


def format_guess_reply(result: GuessResult) -> str:
    lines = [
        f"猜測：{result.guess}",
        f"結果：{result.result_text}",
    ]

    if result.a_count == DIGIT_COUNT:
        lines.append("答對了。")

    return "\n".join(lines)


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
