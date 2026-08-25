from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from games.number_puzzle import (
    LOG_FILE as NUMBER_PUZZLE_LOG_FILE,
    NumberPuzzleProblem,
    create_problem,
    format_answer_reply as format_number_puzzle_answer_reply,
    format_help_reply as format_number_puzzle_help_reply,
    format_problem_reply as format_number_puzzle_problem_reply,
    write_problem_log,
)
from games.one_a_two_b import (
    LOG_FILE as ONE_A_TWO_B_LOG_FILE,
    OneATwoBGame,
    create_game as create_one_a_two_b_game,
    format_answer_reply as format_one_a_two_b_answer_reply,
    format_guess_reply as format_one_a_two_b_guess_reply,
    format_help_reply as format_one_a_two_b_help_reply,
    format_history_reply as format_one_a_two_b_history_reply,
    format_new_game_reply as format_one_a_two_b_new_game_reply,
    submit_guess as submit_one_a_two_b_guess,
    validate_guess_text as validate_one_a_two_b_guess_text,
    write_game_log as write_one_a_two_b_game_log,
)
from services.line_users import (
    LOG_FILE as LINE_USERS_LOG_FILE,
    LineUser,
    bind_user,
    format_bind_reply,
    format_user_context,
    get_nickname,
    load_users_from_log,
)


@dataclass
class LogFiles:
    line_users: Path = LINE_USERS_LOG_FILE
    number_puzzle: Path = NUMBER_PUZZLE_LOG_FILE
    one_a_two_b: Path = ONE_A_TWO_B_LOG_FILE


@dataclass
class GameSessionState:
    current_number_puzzles: dict[str, NumberPuzzleProblem] = field(default_factory=dict)
    current_one_a_two_b_games: dict[str, OneATwoBGame] = field(default_factory=dict)
    line_users: dict[str, LineUser] = field(default_factory=load_users_from_log)


def handle_command(
    text: str,
    source_key: str,
    line_user_id: str | None,
    state: GameSessionState,
    log_files: LogFiles | None = None,
) -> str | None:
    command_text = text.strip()
    logs = log_files or LogFiles()
    nickname = get_nickname(state.line_users, line_user_id)

    if command_text.startswith("/user-"):
        if line_user_id is None:
            return "無法取得 LINE 使用者 ID，請在 LINE 使用者訊息中使用 /user-暱稱。"

        try:
            user = bind_user(
                state.line_users,
                line_user_id,
                command_text[len("/user-"):],
                source_key=source_key,
                log_file=logs.line_users,
            )
        except ValueError as exc:
            return str(exc)

        return format_bind_reply(user)

    if command_text == "/-h":
        return _with_user_context(format_all_games_help_reply(), state, line_user_id)

    if command_text == "!-h":
        return _with_user_context(format_number_puzzle_help_reply(), state, line_user_id)

    if command_text == "!-n":
        problem = create_problem()
        write_problem_log(
            problem,
            log_file=logs.number_puzzle,
            source_key=source_key,
            line_user_id=line_user_id,
            nickname=nickname,
        )
        state.current_number_puzzles[source_key] = problem

        return _with_user_context(format_number_puzzle_problem_reply(problem), state, line_user_id)

    if command_text == "!-a":
        problem = state.current_number_puzzles.get(source_key)
        if problem is None:
            return _with_user_context("目前沒有算式拼圖題目，請先輸入 !-n 產生新題目。", state, line_user_id)

        return _with_user_context(format_number_puzzle_answer_reply(problem), state, line_user_id)

    if command_text == "@-h":
        return _with_user_context(format_one_a_two_b_help_reply(), state, line_user_id)

    if command_text == "@-n":
        game = create_one_a_two_b_game()
        write_one_a_two_b_game_log(
            game,
            action="new_game",
            source_key=source_key,
            line_user_id=line_user_id,
            nickname=nickname,
            log_file=logs.one_a_two_b,
        )
        state.current_one_a_two_b_games[source_key] = game

        return _with_user_context(format_one_a_two_b_new_game_reply(), state, line_user_id)

    if command_text == "@-a":
        game = state.current_one_a_two_b_games.get(source_key)
        if game is None:
            return _with_user_context("目前沒有 1A2B 遊戲，請先輸入 @-n 開新遊戲。", state, line_user_id)

        write_one_a_two_b_game_log(
            game,
            action="show_answer",
            source_key=source_key,
            line_user_id=line_user_id,
            nickname=nickname,
            log_file=logs.one_a_two_b,
        )
        return _with_user_context(format_one_a_two_b_answer_reply(game), state, line_user_id)

    if command_text == "@-l":
        game = state.current_one_a_two_b_games.get(source_key)
        if game is None:
            return _with_user_context("目前沒有 1A2B 遊戲，請先輸入 @-n 開新遊戲。", state, line_user_id)

        write_one_a_two_b_game_log(
            game,
            action="show_history",
            source_key=source_key,
            line_user_id=line_user_id,
            nickname=nickname,
            log_file=logs.one_a_two_b,
        )
        return _with_user_context(format_one_a_two_b_history_reply(game), state, line_user_id)

    if command_text.startswith("@-"):
        game = state.current_one_a_two_b_games.get(source_key)
        if game is None:
            return _with_user_context("目前沒有 1A2B 遊戲，請先輸入 @-n 開新遊戲。", state, line_user_id)

        guess = command_text[2:]
        error = validate_one_a_two_b_guess_text(guess)
        if error is not None:
            return _with_user_context(f"{error}\n輸入 @-h 查看 1A2B 指令。", state, line_user_id)

        result = submit_one_a_two_b_guess(game, guess)
        write_one_a_two_b_game_log(
            game,
            action="guess",
            result=result,
            source_key=source_key,
            line_user_id=line_user_id,
            nickname=nickname,
            log_file=logs.one_a_two_b,
        )
        return _with_user_context(format_one_a_two_b_guess_reply(result), state, line_user_id)

    return None


def format_all_games_help_reply() -> str:
    return "\n".join(
        [
            "目前可用遊戲功能與指令",
            "算式拼圖",
            "!-n：產生新題目",
            "!-a：查看當前題目的答案",
            "!-h：查看算式拼圖指令",
            "",
            "1A2B",
            "@-n：開新遊戲",
            "@-a：查看答案",
            "@-l：查看當前回合猜測紀錄",
            "@-h：查看 1A2B 指令",
            "@-xxxx：猜測 4 位不重複數字，例如 @-1234",
            "",
            "全域",
            "/-h：列出目前所有可用的遊戲功能及指令",
            "/user-暱稱：依照 LINE 使用者 ID 綁定暱稱，例如 /user-小明",
        ]
    )


def _with_user_context(text: str, state: GameSessionState, line_user_id: str | None) -> str:
    return "\n".join(
        [
            format_user_context(state.line_users, line_user_id),
            text,
        ]
    )
