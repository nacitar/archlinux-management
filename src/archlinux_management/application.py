from __future__ import annotations

import argparse
import logging
import time
from dataclasses import KW_ONLY, dataclass
from logging import Handler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Sequence

from .utility import Configuration, ReviewedFileUpdater, load_resource

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
    *, options: LogFileOptions | None = None, utc: bool = False
) -> None:
    handlers: list[logging.Handler] = []
    message = "logging configured"
    if options:
        handlers.append(options.create_handler())
        message += f", logging to file: {Path(options.path).resolve()}"
    else:
        handlers.append(logging.NullHandler())
    logging.basicConfig(
        style="{",
        format=(
            "[{asctime:s}.{msecs:03.0f}]"
            " [{module:s}] {levelname:s}: {message:s}"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
        level=options.level if options else logging.INFO,
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
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Increase log verbosity to DEBUG.",
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

    setup_logging(
        options=(
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

    if args.modification == "pacman_hook_paccache":
        # TODO: adjust logic for ReviewedFileUpdater
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
