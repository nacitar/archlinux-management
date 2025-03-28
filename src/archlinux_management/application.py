from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import KW_ONLY, dataclass
from logging import Handler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Sequence

from . import tui
from .modifications import (
    MODIFICATION_LOOKUP,
    MODIFICATION_MENU,
    ModificationOptions,
)
from .term_style import TermStyle

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
    logging.getLogger().handlers = []
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(
        logging.Formatter(fmt="{levelname:s}: {message:s}", style="{")
    )
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
        "-m",
        "--modification",
        choices=tuple(MODIFICATION_LOOKUP.keys()),
        help="The modification to manage.  Displays a menu by default.",
    )
    parser.add_argument(
        "-o",
        "--operation",
        choices=("apply", "remove"),
        help="The modification to manage.  Displays a menu by default",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help=(
            "Non-interactive execution; disables prompting for reviews, "
            "confirmations, or sudo password."
        ),
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

    try:
        if args.modification:
            modification = MODIFICATION_LOOKUP[args.modification]
        else:
            modification = MODIFICATION_MENU.prompt()
        if args.operation:
            apply: bool = args.operation == "apply"
        else:
            apply = tui.Menu[bool](
                "Select operation", {"apply": True, "remove": False}
            ).prompt()
    except (KeyboardInterrupt, EOFError) as e:
        print()
        tui.error(f"{type(e).__name__} received; aborting...")
        return 1

    # TODO: allow multiple operations in one interactive session?  Only makes
    # sense if args.modification wasn't specified... and honestly operation
    # only makes sense WITH modification, they should go together.
    return not modification(
        ModificationOptions(
            review=not args.non_interactive,
            confirm=not args.non_interactive,
            sudo_prompt=not args.non_interactive,
            apply=apply,
        )
    )
