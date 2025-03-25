from __future__ import annotations

from .term_style import TermStyle


def info(message: str) -> None:
    print(
        f"{TermStyle.GREEN}{TermStyle.BOLD}==>"
        f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
    )


def detail(message: str) -> None:
    print(
        f"  {TermStyle.BLUE}{TermStyle.BOLD}->"
        f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
    )


def warning(message: str) -> None:
    print(
        f"{TermStyle.YELLOW}{TermStyle.BOLD}==> WARNING:"
        f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
    )


def error(message: str) -> None:
    print(
        f"{TermStyle.RED}{TermStyle.BOLD}==> ERROR:"
        f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
    )


def prompt(
    message: str,
    answers: list[str] | None = None,
    default: str = "",
    *,
    lower: bool = True,
    alternates: dict[str, str] | None = None,
) -> str:
    if answers:
        answer_display = f" [{
            "/".join(
                answer.lower() if answer != default else answer.upper()
                for answer in answers
            )
        }]"
        if default and default not in answers:
            raise ValueError(
                f'default "{default}" not valid: {answer_display}'
            )
    else:
        answer_display = ""
    message = f"{message}{answer_display} "
    while True:
        answer = (
            input(
                f"{TermStyle.GREEN}{TermStyle.BOLD}::"
                f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
            )
            or default
        )
        if lower:
            answer = answer.lower()
        if alternates:
            answer = alternates.get(answer, answer)
        if not answers or answer in answers:
            return answer
        detail("Invalid answer.")
    return answer


PROMPT_YES_NO_ALTERNATES: dict[str, str] = {"yes": "y", "no": "n"}


def prompt_yes_no(message: str, default: str = "") -> bool:
    return (
        prompt(
            message, ["y", "n"], default, alternates=PROMPT_YES_NO_ALTERNATES
        )
        == "y"
    )
