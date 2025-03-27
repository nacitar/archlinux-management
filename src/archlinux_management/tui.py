from __future__ import annotations

from dataclasses import dataclass

from .term_style import TermStyle


def info(message: str, *, indent: int = 0, indicator: str = "==>") -> None:
    print(
        f"{' '*indent}{TermStyle.GREEN}{TermStyle.BOLD}{indicator}"
        f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
    )


def detail(message: str, *, indent: int = 0, indicator: str = "->") -> None:
    print(
        f"{' '*(indent+2)}{TermStyle.BLUE}{TermStyle.BOLD}{indicator}"
        f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
    )


def warning(message: str, *, indent: int = 0, indicator: str = "==>") -> None:
    print(
        f"{' '*indent}{TermStyle.YELLOW}{TermStyle.BOLD}{indicator} WARNING:"
        f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
    )


def error(message: str, *, indent: int = 0, indicator: str = "==>") -> None:
    print(
        f"{' '*indent}{TermStyle.RED}{TermStyle.BOLD}{indicator} ERROR:"
        f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET}"
    )


def prompt(
    message: str,
    answers: list[str] | None = None,
    default: str = "",
    *,
    indent: int = 0,
    lower: bool = True,
    alternates: dict[str, str] | None = None,
    show_options: bool = True,
    indicator: str = "::",
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
    if show_options:
        message = f"{message}{answer_display}"
    while True:
        answer = (
            input(
                f"{' '*indent}{TermStyle.GREEN}{TermStyle.BOLD}{indicator}"
                f"{TermStyle.RESET_COLOR} {message}{TermStyle.RESET} "
            )
            or default
        )
        if lower:
            answer = answer.lower()
        if alternates:
            answer = alternates.get(answer, answer)
        if not answers or answer in answers:
            return answer
        detail("Invalid answer.", indent=indent + 2)
    return answer


PROMPT_YES_NO_ALTERNATES: dict[str, str] = {"yes": "y", "no": "n"}


def prompt_yes_no(
    message: str, default: str = "", *, show_options: bool = True
) -> bool:
    return (
        prompt(
            message,
            ["y", "n"],
            default,
            alternates=PROMPT_YES_NO_ALTERNATES,
            show_options=show_options,
        )
        == "y"
    )


@dataclass
class Menu:
    class _PreviousMenuError(RuntimeError):
        pass

    message: str
    options: dict[str, str | Menu]

    def __prompt(self, allow_back: bool = False) -> str:
        while True:
            keys = list(self.options.keys())
            if not keys:
                raise ValueError(f"no options provided for {type(self)}.")
            info(self.message)
            option_width = len(str(len(keys)))
            answers = ["0"] if allow_back else []
            for i in range(len(keys)):
                print(f"  {i+1:>{option_width}}. {keys[i]}")
                answers.append(str(i + 1))
            answer = prompt(
                f"Choice{' (0 for previous menu)' if allow_back else ''}:",
                answers,
                show_options=False,
            )
            print()
            if answer == "0":
                raise type(self)._PreviousMenuError()
            value: str | Menu = self.options[keys[int(answer) - 1]]
            if isinstance(value, Menu):
                try:
                    value = value.__prompt(True)
                except type(self)._PreviousMenuError:
                    continue
            return value

    def prompt(self) -> str:
        return self.__prompt(allow_back=False)
