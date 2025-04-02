from __future__ import annotations

import filecmp
import logging
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import TracebackType
from typing import Type

from . import tui
from .configuration import Configuration
from .utility import (
    execute_command,
    get_resource_content,
    launch_diff_tool,
    launch_editor,
)

logger = logging.getLogger(__name__)


@dataclass
class FileUpdaterOptions:
    review: bool
    confirm: bool
    sudo_prompt: bool


@dataclass(kw_only=True)
class FileUpdater:
    target: Path
    staging: Path
    options: FileUpdaterOptions
    delete: bool
    mode: int = 0o644
    owner: str = ""
    group: str = ""

    @classmethod
    def from_content(
        cls,
        *,
        target: Path,
        content: str,
        options: FileUpdaterOptions,
        mode: int = 0o644,
        owner: str = "",
        group: str = "",
    ) -> FileUpdater:
        with NamedTemporaryFile(
            "w+", delete=False, suffix=target.suffix
        ) as temp_file:
            temp_file.write(content)
            temp_file.close()
        return FileUpdater(
            target=target,
            staging=Path(temp_file.name),
            options=options,
            delete=True,
            mode=mode,
            owner=owner,
            group=group,
        )

    @classmethod
    def from_resource(
        cls,
        *,
        target: Path,
        resource: str,
        options: FileUpdaterOptions,
        mode: int = 0o644,
        owner: str = "",
        group: str = "",
    ) -> FileUpdater:
        return cls.from_content(
            target=target,
            content=get_resource_content(resource),
            options=options,
            mode=mode,
            owner=owner,
            group=group,
        )

    @classmethod
    def from_configuration(
        cls,
        *,
        target: Path,
        configuration: Configuration,
        options: FileUpdaterOptions,
        mode: int = 0o644,
        owner: str = "",
        group: str = "",
    ) -> FileUpdater:
        return cls.from_content(
            target=target,
            content=str(configuration),
            options=options,
            mode=mode,
            owner=owner,
            group=group,
        )

    def __enter__(self) -> FileUpdater:
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self.delete:
            self.staging.unlink()
        return None

    def matches(self) -> bool:
        return self.target.exists() and filecmp.cmp(
            self.target, self.staging, shallow=False
        )

    def remove(self) -> bool:
        if not self.target.exists():
            tui.warning(f"Not installed; skipping removal: {self.target}")
        else:
            tui.info(f"Removing file: {self.target}")
            if self.options.review:
                if self.matches():
                    tui.detail(
                        "Skipping review because file matches expected."
                    )
                elif tui.prompt_yes_no(
                    "Installed file does not match expected; compare them?"
                ):
                    launch_diff_tool(self.target, self.staging)
            if not self.options.confirm or tui.prompt_yes_no(
                "Proceed with removal?"
            ):
                result = execute_command(
                    ["unlink", str(self.target)],
                    escalate=True,
                    use_tui=True,
                    sudo_prompt=self.options.sudo_prompt,
                )
                if result:
                    logger.info(f"File removed: {self.target}")
                    tui.info("Removal successful!")
                else:
                    logger.info(f"Failed to remove file: {self.target}")
                    tui.error("Removal failed!")
                return result
        logger.info(f"File removal skipped: {self.target}")
        return True

    def apply(self) -> bool:
        if self.matches():
            tui.warning(
                f"Installed file matches; skipping update: {self.target}"
            )
        else:
            tui.info(f"Updating file: {self.target}")
            if self.options.review:
                if not self.target.exists():
                    tui.detail("Target does not exist.")
                    if tui.prompt_yes_no(
                        "Review/edit the content to be installed?"
                    ):
                        launch_editor(self.staging)
                elif tui.prompt_yes_no("Review/edit the changes to be made?"):
                    launch_diff_tool(self.target, self.staging)

            if not self.options.confirm or tui.prompt_yes_no(
                "Proceed with update?"
            ):
                extra_args: list[str] = []
                if self.owner:
                    extra_args.extend(["-o", self.owner])
                if self.group:
                    extra_args.extend(["-g", self.group])
                result = execute_command(
                    ["install", "-m", f"0{oct(self.mode)[2:]}"]
                    + extra_args
                    + [str(self.staging), str(self.target)],
                    escalate=True,
                    use_tui=True,
                    quiet=False,
                    sudo_prompt=self.options.sudo_prompt,
                )
                if result:
                    logger.info(f"File updated: {self.target}")
                    tui.info("Update successful!")
                else:
                    logger.info(f"Failed to update file: {self.target}")
                    tui.error("Update failed!")
                return result
        logger.info(f"File update skipped: {self.target}")
        return True
