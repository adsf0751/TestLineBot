from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
    OneATwoBSettings,
    collect_expired_mutes as collect_expired_one_a_two_b_mutes,
    create_game as create_one_a_two_b_game,
    format_active_mute_reply as format_one_a_two_b_active_mute_reply,
    format_answer_reply as format_one_a_two_b_answer_reply,
    format_ban_time_reply as format_one_a_two_b_ban_time_reply,
    format_guess_ban_enabled_reply as format_one_a_two_b_guess_ban_enabled_reply,
    format_guess_reply as format_one_a_two_b_guess_reply,
    format_guess_limit_reply as format_one_a_two_b_guess_limit_reply,
    format_help_reply as format_one_a_two_b_help_reply,
    format_history_reply as format_one_a_two_b_history_reply,
    format_locked_game_reply as format_one_a_two_b_locked_game_reply,
    format_mute_release_notices as format_one_a_two_b_mute_release_notices,
    format_new_game_reply as format_one_a_two_b_new_game_reply,
    format_newly_muted_player_reply as format_one_a_two_b_newly_muted_player_reply,
    get_active_mute as get_active_one_a_two_b_mute,
    mute_player as mute_one_a_two_b_player,
    release_all_mutes as release_all_one_a_two_b_mutes,
    reset_guess_ban_tracking as reset_one_a_two_b_guess_ban_tracking,
    submit_guess as submit_one_a_two_b_guess,
    set_ban_minutes as set_one_a_two_b_ban_minutes,
    set_consecutive_guess_limit as set_one_a_two_b_consecutive_guess_limit,
    set_guess_ban_enabled as set_one_a_two_b_guess_ban_enabled,
    validate_guess_text as validate_one_a_two_b_guess_text,
    would_exceed_consecutive_guess_limit as would_exceed_one_a_two_b_consecutive_guess_limit,
    write_game_log as write_one_a_two_b_game_log,
)
from services.line_users import (
    LOG_FILE as LINE_USERS_LOG_FILE,
    LineUser,
    bind_user,
    format_bind_reply,
    format_user_context,
    format_victory_declaration_reply,
    get_nickname,
    get_victory_declaration,
    load_victory_declarations_from_log,
    load_users_from_log,
    set_victory_declaration,
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
    one_a_two_b_settings: OneATwoBSettings = field(default_factory=OneATwoBSettings)
    line_users: dict[str, LineUser] = field(default_factory=load_users_from_log)
    victory_declarations: dict[str, str] = field(default_factory=load_victory_declarations_from_log)


def handle_command(
    text: str,
    source_key: str,
    line_user_id: str | None,
    state: GameSessionState,
    log_files: LogFiles | None = None,
    now: datetime | None = None,
) -> str | None:
    command_text = text.strip()
    logs = log_files or LogFiles()
    current_time = now or datetime.now().astimezone()
    nickname = get_nickname(state.line_users, line_user_id)

    if command_text.startswith("/banTime-"):
        try:
            ban_minutes = _parse_positive_int_command(command_text, "/banTime-", "禁言時間")
            set_one_a_two_b_ban_minutes(state.one_a_two_b_settings, ban_minutes)
        except ValueError as exc:
            return str(exc)

        return _with_user_context(
            format_one_a_two_b_ban_time_reply(state.one_a_two_b_settings.ban_minutes),
            state,
            line_user_id,
        )

    if command_text.startswith("/guessLimit-"):
        try:
            guess_limit = _parse_positive_int_command(command_text, "/guessLimit-", "單一玩家連續猜測次數")
            set_one_a_two_b_consecutive_guess_limit(state.one_a_two_b_settings, guess_limit)
        except ValueError as exc:
            return str(exc)

        return _with_user_context(
            format_one_a_two_b_guess_limit_reply(state.one_a_two_b_settings.consecutive_guess_limit),
            state,
            line_user_id,
        )

    if command_text.startswith("/guessBan-"):
        try:
            enabled = _parse_tf_command(command_text, "/guessBan-", "連續猜測禁言開關")
            set_one_a_two_b_guess_ban_enabled(state.one_a_two_b_settings, enabled)
        except ValueError as exc:
            return str(exc)

        release_notice = ""
        if enabled:
            _reset_all_one_a_two_b_guess_ban_tracking(state)
        else:
            release_notice = _release_all_one_a_two_b_mutes(state)

        return _with_user_context(
            _append_reply_blocks(
                format_one_a_two_b_guess_ban_enabled_reply(state.one_a_two_b_settings.guess_ban_enabled),
                release_notice,
            ),
            state,
            line_user_id,
        )

    if command_text.startswith("/userWin-"):
        if line_user_id is None:
            return "無法取得 LINE 使用者 ID，請在 LINE 使用者訊息中使用 /userWin-勝利宣言。"

        try:
            declaration = set_victory_declaration(
                state.victory_declarations,
                line_user_id,
                command_text[len("/userWin-"):],
                source_key=source_key,
                nickname=nickname,
                log_file=logs.line_users,
            )
        except ValueError as exc:
            return str(exc)

        return _with_user_context(format_victory_declaration_reply(declaration), state, line_user_id)

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
        release_notice = _collect_one_a_two_b_mute_release_notice(state, source_key, current_time)
        return _with_user_context(
            _append_reply_blocks(format_one_a_two_b_help_reply(), release_notice),
            state,
            line_user_id,
        )

    if command_text == "@-n":
        release_notice = _release_one_a_two_b_mutes_for_new_game(state, source_key)
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

        return _with_user_context(
            _append_reply_blocks(format_one_a_two_b_new_game_reply(), release_notice),
            state,
            line_user_id,
        )

    if command_text == "@-a":
        game = state.current_one_a_two_b_games.get(source_key)
        if game is None:
            return _with_user_context("目前沒有 1A2B 遊戲，請先輸入 @-n 開新遊戲。", state, line_user_id)

        release_notice = _collect_one_a_two_b_mute_release_notice(state, source_key, current_time)
        write_one_a_two_b_game_log(
            game,
            action="show_answer",
            source_key=source_key,
            line_user_id=line_user_id,
            nickname=nickname,
            log_file=logs.one_a_two_b,
        )
        return _with_user_context(
            _append_reply_blocks(format_one_a_two_b_answer_reply(game), release_notice),
            state,
            line_user_id,
        )

    if command_text == "@-l":
        game = state.current_one_a_two_b_games.get(source_key)
        if game is None:
            return _with_user_context("目前沒有 1A2B 遊戲，請先輸入 @-n 開新遊戲。", state, line_user_id)

        release_notice = _collect_one_a_two_b_mute_release_notice(state, source_key, current_time)
        write_one_a_two_b_game_log(
            game,
            action="show_history",
            source_key=source_key,
            line_user_id=line_user_id,
            nickname=nickname,
            log_file=logs.one_a_two_b,
        )
        return _with_user_context(
            _append_reply_blocks(format_one_a_two_b_history_reply(game), release_notice),
            state,
            line_user_id,
        )

    if command_text.startswith("@-"):
        game = state.current_one_a_two_b_games.get(source_key)
        if game is None:
            return _with_user_context("目前沒有 1A2B 遊戲，請先輸入 @-n 開新遊戲。", state, line_user_id)

        release_notice = _collect_one_a_two_b_mute_release_notice(state, source_key, current_time)
        if game.is_solved:
            return _with_user_context(
                _append_reply_blocks(format_one_a_two_b_locked_game_reply(), release_notice),
                state,
                line_user_id,
            )

        active_mute = get_active_one_a_two_b_mute(game, line_user_id, current_time)
        if active_mute is not None:
            return _with_user_context(
                _append_reply_blocks(format_one_a_two_b_active_mute_reply(active_mute, current_time), release_notice),
                state,
                line_user_id,
            )

        guess = command_text[2:]
        error = validate_one_a_two_b_guess_text(guess)
        if error is not None:
            return _with_user_context(
                _append_reply_blocks(f"{error}\n輸入 @-h 查看 1A2B 指令。", release_notice),
                state,
                line_user_id,
            )

        if would_exceed_one_a_two_b_consecutive_guess_limit(
            game,
            line_user_id,
            state.one_a_two_b_settings.consecutive_guess_limit,
            state.one_a_two_b_settings.guess_ban_enabled,
        ):
            mute = mute_one_a_two_b_player(
                game,
                line_user_id=line_user_id or "",
                nickname=nickname,
                muted_at=current_time,
                ban_minutes=state.one_a_two_b_settings.ban_minutes,
            )
            write_one_a_two_b_game_log(
                game,
                action="mute_player",
                muted_player=mute,
                source_key=source_key,
                line_user_id=line_user_id,
                nickname=nickname,
                log_file=logs.one_a_two_b,
            )
            return _with_user_context(
                _append_reply_blocks(
                    format_one_a_two_b_newly_muted_player_reply(
                        mute,
                        state.one_a_two_b_settings.consecutive_guess_limit,
                        state.one_a_two_b_settings.ban_minutes,
                    ),
                    release_notice,
                ),
                state,
                line_user_id,
            )

        result = submit_one_a_two_b_guess(game, guess, line_user_id=line_user_id, nickname=nickname)
        write_one_a_two_b_game_log(
            game,
            action="guess",
            result=result,
            source_key=source_key,
            line_user_id=line_user_id,
            nickname=nickname,
            log_file=logs.one_a_two_b,
        )
        reply = format_one_a_two_b_guess_reply(result)
        if result.a_count == len(game.answer):
            reply = _append_victory_declaration(reply, state, line_user_id)

        return _with_user_context(_append_reply_blocks(reply, release_notice), state, line_user_id)

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
            "/userWin-勝利宣言：設定贏得遊戲時自動發布的玩家宣言",
            "/banTime-分鐘：設定 1A2B 暫停猜測時間，例如 /banTime-5",
            "/guessLimit-次數：設定 1A2B 單一玩家連續猜測上限，例如 /guessLimit-3",
            "/guessBan-T/F：設定 1A2B 連續猜測禁言開關，例如 /guessBan-F",
        ]
    )


def _parse_positive_int_command(command_text: str, prefix: str, label: str) -> int:
    value_text = command_text[len(prefix):].strip()
    if not value_text or not value_text.isdecimal():
        raise ValueError(f"{label}必須是正整數，例如 {prefix}3。")

    return int(value_text)


def _parse_tf_command(command_text: str, prefix: str, label: str) -> bool:
    value_text = command_text[len(prefix):].strip().upper()
    if value_text == "T":
        return True

    if value_text == "F":
        return False

    raise ValueError(f"{label}必須是 T 或 F，例如 {prefix}T。")


def _collect_one_a_two_b_mute_release_notice(
    state: GameSessionState,
    source_key: str,
    now: datetime,
) -> str:
    game = state.current_one_a_two_b_games.get(source_key)
    if game is None:
        return ""

    return format_one_a_two_b_mute_release_notices(
        collect_expired_one_a_two_b_mutes(game, now)
    )


def _release_one_a_two_b_mutes_for_new_game(state: GameSessionState, source_key: str) -> str:
    game = state.current_one_a_two_b_games.get(source_key)
    if game is None:
        return ""

    return format_one_a_two_b_mute_release_notices(release_all_one_a_two_b_mutes(game))


def _release_all_one_a_two_b_mutes(state: GameSessionState) -> str:
    released_mutes = []
    for game in state.current_one_a_two_b_games.values():
        released_mutes.extend(release_all_one_a_two_b_mutes(game))
        reset_one_a_two_b_guess_ban_tracking(game)

    return format_one_a_two_b_mute_release_notices(released_mutes)


def _reset_all_one_a_two_b_guess_ban_tracking(state: GameSessionState) -> None:
    for game in state.current_one_a_two_b_games.values():
        reset_one_a_two_b_guess_ban_tracking(game)


def _append_reply_blocks(text: str, *blocks: str) -> str:
    return "\n".join([text, *(block for block in blocks if block)])


def _append_victory_declaration(
    text: str,
    state: GameSessionState,
    line_user_id: str | None,
) -> str:
    declaration = get_victory_declaration(state.victory_declarations, line_user_id)
    if declaration is None:
        return text

    return "\n".join(
        [
            text,
            f"勝利宣言：{declaration}",
        ]
    )


def _with_user_context(text: str, state: GameSessionState, line_user_id: str | None) -> str:
    return "\n".join(
        [
            format_user_context(state.line_users, line_user_id),
            text,
        ]
    )
