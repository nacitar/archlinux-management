from __future__ import annotations

import importlib.resources
import logging
import os
import shlex
import subprocess
from pathlib import Path
from shutil import which
from typing import Sequence, TypedDict

from . import tui

logger = logging.getLogger(__name__)


def get_resource_content(name: str, *, package: str | None = None) -> str:
    if not package:
        package = f"{__package__}.resources"
    logger.info(f"Loading resource from {package}: {name}")
    with importlib.resources.open_text(package, name) as file:
        return file.read()


class _ExecuteCommandOptions(TypedDict, total=False):
    stdout: int
    stderr: int
    check: bool


def execute_command(
    command: Sequence[str],
    *,
    quiet: bool = True,
    escalate: bool = False,
    use_tui: bool = False,
    sudo_prompt: bool = True,
    successful_returncode: int = 0,
) -> bool:

    options: _ExecuteCommandOptions = {}
    quiet_options: _ExecuteCommandOptions = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if quiet:
        options.update(quiet_options)

    cli_output = f"Executing {shlex.join(command)}"
    logger.info(cli_output)
    if use_tui:
        tui.info(cli_output)

    result = subprocess.run(command, **options)
    if escalate and result.returncode != successful_returncode:
        if use_tui:
            tui.detail("sudo may be required; invoking with sudo...")
        sudo_command = ["sudo"]
        if not sudo_prompt:
            if use_tui:
                tui.detail(
                    "non-interactive; sudo will only use existing "
                    "authentication timestamp."
                )
            sudo_command.append("-n")
            if subprocess.run(
                sudo_command + ["-v"], **quiet_options
            ).returncode:
                message = "No valid sudo authentication token."
                logger.info(message)  # intentionally not error in log
                if use_tui:
                    tui.error(message)
                return False
        result = subprocess.run(sudo_command + list(command), **options)
    if result.returncode != successful_returncode:
        logger.info("Execution failed!")
        return False
    logger.info("Execution succeeded!")
    return True


def launch_diff_tool(
    original: Path, other: Path, *, diffprog: str = ""
) -> None:
    for command in [
        diffprog,
        os.environ.get("DIFFPROG", ""),
        "nvim -d",
        "vim -d",
    ]:
        if command:
            command_line = shlex.split(command) + [str(original), str(other)]
            if which(command_line[0]):
                logger.info(f"Invoking diffprog: {shlex.join(command_line)}")
                subprocess.run(command_line)
                return
    raise RuntimeError("no diffprog specified or located.")


def launch_editor(path: Path, *, editor: str = "") -> None:
    for command in [
        editor,
        os.environ.get("VISUAL", ""),
        os.environ.get("EDITOR", ""),
        "nvim",
        "vim",
    ]:
        if command:
            command_line = shlex.split(command) + [str(path)]
            if which(command_line[0]):
                logger.info(f"Invoking editor: {shlex.join(command_line)}")
                subprocess.run(command_line)
                return
    raise RuntimeError("no diffprog specified or located.")
