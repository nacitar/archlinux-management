from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import KW_ONLY, dataclass
from logging import Handler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Sequence

from .utility import Configuration, load_resource

LOG = logging.getLogger(__name__)


@dataclass
class LogFileOptions:
    path: str | Path
    _ = KW_ONLY
    max_kb: int
    backup_count: int
    level: int = logging.INFO
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


def setup_logging(
    *,
    console_level: int = logging.WARNING,
    file_options: LogFileOptions | None = None,
    utc: bool = False,
) -> None:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    handlers: list[logging.Handler] = [console_handler]
    message = "logging configured"
    if file_options:
        handlers.append(file_options.create_handler())
        global_level = min(console_level, file_options.level)
        message += f", logging to file: {Path(file_options.path).resolve()}"
    else:
        global_level = console_level
    logging.basicConfig(
        style="{",
        format=(
            "[{asctime:s}.{msecs:03.0f}]"
            " [{module:s}] {levelname:>8s}: {message:s}"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        level=global_level,
        handlers=handlers,
    )
    if utc:
        logging.Formatter.converter = time.gmtime
    LOG.info(message)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Does something.")
    parser.add_argument(
        "--log-path",
        type=str,
        help="Path to the log file to be written.",
        default="",
    )
    loglevel_group = parser.add_mutually_exclusive_group(required=False)
    loglevel_group.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Increase log verbosity to INFO for console.",
    )
    loglevel_group.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Increase log verbosity to DEBUG for console and log file.",
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
        choices=["pacman_hook_paccache"],
        help="The target modification.",
    )
    args = parser.parse_args(args=argv)

    setup_logging(
        console_level=(
            logging.DEBUG
            if args.debug
            else logging.INFO if args.verbose else logging.WARNING
        ),
        file_options=(
            None
            if not args.log_path
            else LogFileOptions(
                path=args.log_path,
                max_kb=512,  # 0 for unbounded size and no rotation
                backup_count=1,  # 0 for no rolling backups
                level=logging.DEBUG if args.debug else logging.INFO,
                # append=False
            )
        ),
        # utc=True
    )

    if os.geteuid():
        LOG.error("must run as root.")
        return 1
    if args.modification == "pacman_hook_paccache":
        target_path = Path("/usr/share/libalpm/hooks/paccache.hook")
        if args.install:
            if target_path.exists():
                LOG.warning(f"SKIPPING, already installed: {target_path}")
            else:
                LOG.info(f"writing file: {target_path}")
                target_path.write_text(load_resource("paccache.hook"))
        elif args.uninstall:
            if target_path.exists():
                target_path.unlink()
            else:
                LOG.warning(f"SKIPPING, not present: {target_path}")
        else:
            raise NotImplementedError()
        return 0

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
