from __future__ import annotations

import importlib.resources
import logging
import os
import re
import subprocess
from dataclasses import KW_ONLY, dataclass
from pathlib import Path
from shutil import which
from tempfile import NamedTemporaryFile
from types import TracebackType
from typing import Any, Sequence, Type

from . import tui

LOG = logging.getLogger(__name__)

SECTION_REGEX = re.compile(r"^\s*\[\s*(?P<name>[^]]+)\s*\]\s*$")
KEY_VALUE_PATTERN = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<key>[^=]+)(?P<assignment>\s*=\s*)(?P<value>.+?)(?P<ws_post>\s*)$"
)


RESOURCES_PACKAGE = f"{__package__}.resources"


def get_resource_content(name: str) -> str:
    with importlib.resources.open_text(RESOURCES_PACKAGE, name) as file:
        return file.read()


@dataclass
class _ConfigurationField:
    indent: str
    comment: str
    key: str
    assignment: str
    value: str
    ws_post: str

    def __str__(self) -> str:
        return (
            f"{self.indent}{self.comment}"
            f"{self.key}{self.assignment}{self.value}{self.ws_post}"
        )


@dataclass
class _Section:
    name: str
    lines: list[str | _ConfigurationField]


class Configuration:
    """
    A class that allows updating config files, respecting commented values
    used as placeholders.
    """

    def __init__(
        self,
        lines: list[str],
        *,
        comment_char: str = "#",
        section_divider: str = ".",
        default_indent: int = 0,
    ) -> None:
        self._comment_char = comment_char
        self._section_divider = section_divider
        self._default_indent = default_indent
        self._fields: dict[str, list[_ConfigurationField]] = {}
        self._sections: list[_Section] = []

        comment_regex = re.compile(rf"^{re.escape(self._comment_char)}\s*")
        section = _Section("", [])
        self._sections.append(section)
        for line in lines:
            if match := SECTION_REGEX.match(line):
                section = _Section(match.group("name"), [])
                self._sections.append(section)
                continue
            elif match := KEY_VALUE_PATTERN.match(line):
                key = match.group("key")
                if comment_match := comment_regex.match(key):
                    comment = key[: comment_match.end()]
                    key = key[comment_match.end() :]
                else:
                    comment = ""
                value = match.group("value")

                if key:  # to prevent matching "# = value"
                    field = _ConfigurationField(
                        indent=match.group("indent"),
                        comment=comment,
                        key=key,
                        assignment=match.group("assignment"),
                        value=value,
                        ws_post=match.group("ws_post"),
                    )
                    if section.name:
                        key = f"{section.name}{self._section_divider}{key}"
                    section.lines.append(field)
                    self._fields.setdefault(key, []).append(field)
                    continue
            section.lines.append(line)

    def _get_set_fields(self, key: str) -> list[_ConfigurationField]:
        return [
            field for field in self._fields.get(key, []) if not field.comment
        ]

    def get(self, key: str) -> str:
        fields = self._get_set_fields(key)
        if not fields:
            return ""
        return fields[-1].value

    def comment(self, key: str) -> None:
        fields = self._get_set_fields(key)
        if fields:
            fields[-1].comment = self._comment_char

    def set(self, key: str, value: str) -> None:
        # get uncommented fields, or a commented one if there's only one
        fields = self._get_set_fields(key)
        if not fields:
            fields = self._fields.get(key, [])
            if len(fields) > 1:
                fields = []
        # set the last entry, uncommenting if needed
        if fields:
            fields[-1].comment = ""
            fields[-1].value = value
        else:
            # add it to the end of the last of this section, or a new section
            parts = key.split(self._section_divider, 1)
            if len(parts) == 2:
                section_name = parts[0]
                section_key = parts[1]
            else:
                section_name = ""
            found_section = False
            for section in reversed(self._sections):
                if section.name == section_name:
                    found_section = True
                    break
            field = _ConfigurationField(
                indent=" " * self._default_indent,
                comment="",
                key=section_key,
                assignment="=",
                value=value,
                ws_post="",
            )
            if found_section:
                section.lines.append(field)
            else:
                self._sections.append(_Section(section_name, [field]))
            self._fields.setdefault(key, []).append(field)

    @classmethod
    def from_content(cls, content: str) -> Configuration:
        return cls(content.splitlines())

    @classmethod
    def from_file(cls, path: str | Path) -> Configuration:
        return cls.from_content(Path(path).read_text())

    def __str__(self) -> str:
        lines: list[str] = []
        for section in self._sections:
            if (
                lines and lines[-1].strip()
            ):  # if the last line written isn't whitespace
                lines.append("")
            if section.name:
                lines.append(f"[{section.name}]")
            for line in section.lines:
                lines.append(str(line))
        return os.linesep.join(lines)


def command_with_escalation(
    command: Sequence[str | bytes | os.PathLike[Any]], *, quiet: bool = True
) -> None:
    options: dict[str, Any] = {}
    if quiet:
        options.update(
            {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        )

    if subprocess.run(command, **options).returncode:
        LOG.warning("sudo appears to be required.")
        subprocess.run(["sudo"] + list(command), check=True, **options)


def diff_merge(
    original: str | Path, other: str | Path, *, diffprog: str = ""
) -> None:
    for command in [
        diffprog,
        os.environ.get("DIFFPROG", ""),
        "nvim -d",
        "vim -d",
    ]:
        if command:
            command_line = command.split() + [str(original), str(other)]
            if which(command_line[0]):
                LOG.info(f"Invoking diffprog: {command_line}")
                subprocess.run(command_line)
                return
    raise RuntimeError("no diffprog specified or located.")


@dataclass
class ReviewedFileUpdater:
    original: Path
    _ = KW_ONLY
    other: Path
    delete: bool = False

    @classmethod
    def from_content(
        cls, original: Path, *, content: str
    ) -> ReviewedFileUpdater:
        with NamedTemporaryFile(
            "w+", delete=False, suffix=original.suffix
        ) as temp_file:
            temp_file.write(content)
            temp_file.close()
        return ReviewedFileUpdater(original, Path(temp_file.name), delete=True)

    @classmethod
    def from_resource(
        cls, original: Path, *, resource: str
    ) -> ReviewedFileUpdater:
        return cls.from_content(
            original, content=get_resource_content(resource)
        )

    def __enter__(self) -> ReviewedFileUpdater:
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self.delete:
            self.other.unlink()
        return None

    @classmethod
    def from_configuration(
        cls, original: Path, configuration: Configuration
    ) -> ReviewedFileUpdater:
        return cls.from_content(original, content=str(configuration))

    def remove(self, *, review: bool = True, confirm: bool = True) -> None:
        tui.info(f"Removing file: {self.original}")
        if review and tui.prompt_yes_no("Compare existing with expected?"):
            diff_merge(self.original, self.other)

        if not confirm or tui.prompt_yes_no("Proceed with removal?"):
            LOG.info(f"Removing: {self.original}")
            command_with_escalation(["unlink", str(self.original)])

    def replace(self, *, review: bool = True, confirm: bool = True) -> None:
        tui.info(f"Replacing file: {self.original}")
        if review and tui.prompt_yes_no("Review the changes?"):
            diff_merge(self.original, self.other)

        if not confirm or tui.prompt_yes_no("Proceed with replacement?"):
            LOG.info(f"Replacing: {self.original}")
            command_with_escalation(
                [
                    "cp",
                    "--no-preserve=mode,ownership",
                    str(self.other),
                    str(self.original),
                ]
            )
