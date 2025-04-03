from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import KW_ONLY, dataclass
from logging import Handler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Sequence

from . import tui
from .modifications import MODIFICATION_MENU, TASK_MENU, ModificationOptions
from .term_style import TermStyle
from .tui import Menu

logger = logging.getLogger(__name__)


@dataclass
class LogFileOptions:
    path: Path
    _ = KW_ONLY
    max_kb: int
    backup_count: int
    level: int = logging.DEBUG
    encoding: str = "utf-8"
    append: bool = True

    def create_handler(self) -> Handler:
        handler = RotatingFileHandler(
            self.path,
            mode="a" if self.append else "w",
            encoding=self.encoding,
            maxBytes=self.max_kb * 1024,
            backupCount=self.backup_count,
        )
        handler.setLevel(self.level)
        return handler


def configure_logging(
    console_level: int, log_file_options: LogFileOptions | None = None
) -> None:
    class SuppressConsoleOutputFor__main__(logging.Filter):
        def __init__(self) -> None:
            super().__init__()

        def filter(self, record: logging.LogRecord) -> bool:
            return record.name != (
                f"{__package__}.__main__" if __package__ else "__main__"
            )

    logging.getLogger().handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(
        logging.Formatter(fmt="{levelname:s}: {message:s}", style="{")
    )
    console_handler.addFilter(SuppressConsoleOutputFor__main__())
    logging.getLogger().addHandler(console_handler)
    global_level = console_level
    if log_file_options:
        global_level = min(global_level, log_file_options.level)
        file_handler = log_file_options.create_handler()
        file_handler.setFormatter(
            logging.Formatter(
                fmt=(
                    "[{asctime:s}.{msecs:03.0f}]"
                    " [{levelname:s}] {module:s}: {message:s}"
                ),
                datefmt="%Y-%m-%d %H:%M:%S",
                style="{",
            )
        )
        logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(global_level)
    logging.info("logging configured")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Applies or removes modifications to an ArchLinux system."
    )
    log_group = parser.add_argument_group("logging")
    log_group.add_argument(
        "--log-file",
        metavar="FILE",
        help="Path to a file where logs will be written, if specified.",
    )
    log_verbosity_group = log_group.add_mutually_exclusive_group(
        required=False
    )
    log_verbosity_group.add_argument(
        "-v",
        "--verbose",
        action="store_const",
        dest="console_level",
        const=logging.INFO,
        help="Increase console log level to INFO.",
    )
    log_verbosity_group.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        dest="console_level",
        const=logging.ERROR,
        help="Decrease console log level to ERROR.  Overrides -v.",
    )
    log_verbosity_group.add_argument(
        "--debug",
        action="store_const",
        dest="console_level",
        const=logging.DEBUG,
        help="Maximizes console log verbosity to DEBUG.  Overrides -v and -q.",
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help=(
            "Control colorized output: "
            "'auto' (default), 'always', or 'never'."
        ),
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=(
            "Non-interactive execution; disables prompting for reviews, "
            "confirmations, or sudo password."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available subcommands", required=False
    )
    modification_parser = subparsers.add_parser(
        "modification", help="Perform modifications."
    )
    modification_parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove the modification instead of applying it.",
    )
    modification_parser.add_argument(
        "modification_names", help="Target modification names.", nargs="+"
    )

    task_parser = subparsers.add_parser("task", help="Execute tasks.")

    task_parser.add_argument(
        "task_names", help="Target task names.", nargs="+"
    )

    args = parser.parse_args(args=argv)

    configure_logging(
        console_level=args.console_level or logging.WARNING,
        log_file_options=(
            None
            if not args.log_file
            else LogFileOptions(
                path=Path(args.log_file),
                max_kb=512,  # 0 for unbounded size and no rotation
                backup_count=1,  # 0 for no rolling backups
                # append=False
            )
        ),
    )
    TermStyle.set_enabled(
        args.color == "always"
        or (args.color == "auto" and sys.stdout.isatty())
    )

    category_menu = Menu[str](
        "Select category", {"Modifications": "modification", "Tasks": "task"}
    )

    apply: bool | None = None
    modifications: list[Callable[[ModificationOptions], bool]] = []
    if args.command == "modification":
        apply = False if args.remove else True
        modification_lookup = {
            value.__name__: value for value in MODIFICATION_MENU.values()
        }
        for modification_name in args.modification_names:
            modification_value = modification_lookup.get(
                modification_name, None
            )
            if modification_value is None:
                tui.error(
                    f"Not a valid modification name: {modification_name}"
                )
                tui.detail(
                    "Must be one of: "
                    f"{', '.join(sorted(modification_lookup.keys()))}"
                )
                return 1
            modifications.append(modification_value)
    tasks: list[Callable[[], bool]] = []
    if args.command == "task":
        task_lookup = {value.__name__: value for value in TASK_MENU.values()}
        for task_name in args.task_names:
            task_value = task_lookup.get(task_name, None)
            if task_value is None:
                tui.error(f"Not a valid task name: {task_name}")
                tui.detail(
                    f"Must be one of: {', '.join(sorted(task_lookup.keys()))}"
                )
                return 1
            tasks.append(task_value)

    prompt_again = True
    while prompt_again:
        if args.command:
            prompt_again = False
            command = args.command
        else:
            command = ""
        try:
            if not command:
                command = category_menu.prompt()
            try:
                if command == "modification":
                    while True:
                        if not modifications:
                            modifications.append(MODIFICATION_MENU.prompt())
                            apply = None
                        if apply is None:
                            try:
                                apply = tui.Menu[bool](
                                    "Select operation",
                                    {"apply": True, "remove": False},
                                ).prompt()
                            except EOFError:
                                continue
                        break
                    for modification in modifications:
                        modification(
                            ModificationOptions(
                                review=not args.non_interactive,
                                confirm=not args.non_interactive,
                                sudo_prompt=not args.non_interactive,
                                apply=apply,
                            )
                        )
                    modifications.clear()
                elif command == "task":
                    if not tasks:
                        tasks.append(TASK_MENU.prompt())
                    for task in tasks:
                        task()
                    tasks.clear()
                else:
                    raise AssertionError(f"Invalid command: {command}")
            except EOFError:
                continue
        except (KeyboardInterrupt, EOFError) as e:
            print()
            tui.error(f"{type(e).__name__} received; aborting...")
            return 0
    return 0
