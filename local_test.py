from __future__ import annotations

import sys

from services.command_router import GameSessionState, handle_command


LOCAL_LINE_USER_ID = "local-user"
LOCAL_SOURCE_KEY = f"local:user_id:{LOCAL_LINE_USER_ID}"


def main() -> None:
    _configure_output_encoding()
    state = GameSessionState()

    if len(sys.argv) > 1:
        command_text = " ".join(sys.argv[1:])
        print(_handle_local_command(command_text, state))
        return

    print("LINE 遊戲本地測試模式")
    print("輸入 /-h 查看指令，輸入 exit 離開。")

    while True:
        try:
            command_text = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if command_text.lower() in {"exit", "quit", "q"}:
            break

        if not command_text:
            continue

        print(_handle_local_command(command_text, state))


def _handle_local_command(command_text: str, state: GameSessionState) -> str:
    reply = handle_command(
        command_text,
        source_key=LOCAL_SOURCE_KEY,
        line_user_id=LOCAL_LINE_USER_ID,
        state=state,
    )

    if reply is None:
        return "未支援的指令，請輸入 /-h 查看目前可用指令。"

    return reply


def _configure_output_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    main()
