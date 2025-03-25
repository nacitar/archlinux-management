from __future__ import annotations

import argparse
import logging
from dataclasses import KW_ONLY, dataclass
from logging import Handler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Sequence

from .utility import Configuration, ReviewedFileUpdater, get_resource_content

LOG = logging.getLogger(__name__)


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
    parser = argparse.ArgumentParser(description="Does something.")
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
        help="Maximum console log verbosity (DEBUG).  Overrides -v and -q.",
    )
    operation_group = parser.add_mutually_exclusive_group(required=True)
    operation_group.add_argument(
        "-i",
        "--install",
        action="store_true",
        help="Install the selected modification.",
    )
    operation_group.add_argument(
        "-u",
        "--uninstall",
        action="store_true",
        help="Uninstall the selected modification.",
    )
    parser.add_argument(
        "modification",
        type=str,
        choices=["pacman_hook_paccache", "journald_limits"],
        help="The target modification.",
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

    if args.modification == "pacman_hook_paccache":
        # TODO: adjust logic for ReviewedFileUpdater
        target_path = Path("/usr/share/libalpm/hooks/paccache.hook")
        if args.install:
            if target_path.exists():
                LOG.warning(f"SKIPPING, already installed: {target_path}")
            else:
                LOG.info(f"writing file: {target_path}")
                target_path.write_text(get_resource_content("paccache.hook"))
        elif args.uninstall:
            if target_path.exists():
                target_path.unlink()
            else:
                LOG.warning(f"SKIPPING, not present: {target_path}")
        else:
            raise NotImplementedError()
        return 0
    elif args.modification == "journald_limits":
        # conf_path = Path("/etc/systemd/journald.conf")
        conf_path = Path("/home/nacitar/tmp/journald.conf")
        # TODO: the real change?
        configuration = Configuration.from_file(conf_path)
        configuration.set("Journal.RateLimitBurst", "moo")
        configuration.set("Journal.Waffles", "syrup")
        configuration.set("Banana.Biscuit", "snarf")
        configuration.set("Journal.Waffles", "butter")
        configuration.comment("Journal.Waffles")

        # TODO: handle install/uninstall?
        with ReviewedFileUpdater.from_configuration(
            conf_path, configuration
        ) as updater:
            updater.replace()

    # configuration = Configuration.from_file("/etc/systemd/journald.conf")
    # print(len(configuration._sections))
    # print(configuration.get("Journal.RateLimitBurst"))
    # configuration.set("Journal.RateLimitBurst", "moo")
    # configuration.set("Journal.Waffles", "syrup")
    # print(configuration.get("Journal.RateLimitBurst"))
    # configuration.set("Banana.Biscuit", "snarf")
    # configuration.set("Journal.Waffles", "butter")
    # configuration.comment("Journal.Waffles")
    # print()
    # print(configuration)
    return 0
