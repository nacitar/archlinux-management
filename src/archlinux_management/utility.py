from __future__ import annotations

import importlib.resources
import logging
import os
import re
import subprocess
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from shutil import which
from tempfile import NamedTemporaryFile
from types import TracebackType
from typing import Any, ClassVar, Sequence, Type

from .style import Style

LOG = logging.getLogger(__name__)

SECTION_REGEX = re.compile(r"^\s*\[\s*(?P<name>[^]]+)\s*\]\s*$")
KEY_VALUE_PATTERN = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<key>[^=]+)(?P<assignment>\s*=\s*)(?P<value>.+?)(?P<ws_post>\s*)$"
)


RESOURCES_PACKAGE = f"{__package__}.resources"


def load_resource(name: str) -> str:
    with importlib.resources.open_text(RESOURCES_PACKAGE, name) as file:
        return file.read()


@dataclass
class ConfigurationField:
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
class Section:
    name: str
    lines: list[str | ConfigurationField]


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
        self._fields: dict[str, list[ConfigurationField]] = {}
        self._sections: list[Section] = []

        comment_regex = re.compile(rf"^{re.escape(self._comment_char)}\s*")
        section = Section("", [])
        self._sections.append(section)
        for line in lines:
            if match := SECTION_REGEX.match(line):
                section = Section(match.group("name"), [])
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
                    field = ConfigurationField(
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

    def _get_set_fields(self, key: str) -> list[ConfigurationField]:
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
            field = ConfigurationField(
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
                self._sections.append(Section(section_name, [field]))
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


@dataclass
class Tui:
    __YES_NO_ALTERNATES: ClassVar[dict[str, str]] = {"yes": "y", "no": "n"}
    LOG: logging.Logger = field(default=LOG)

    def info(self, message: str, *, log: bool = True) -> None:
        if log:
            self.LOG.info(message)
        print(
            f"{Style.GREEN}{Style.BOLD}==>"
            f"{Style.RESET_COLOR} {message}{Style.RESET}"
        )

    def detail(self, message: str, *, log: bool = True) -> None:
        if log:
            self.LOG.info(f"- {message}")
        print(
            f"  {Style.BLUE}{Style.BOLD}->"
            f"{Style.RESET_COLOR} {message}{Style.RESET}"
        )

    def warning(self, message: str, *, log: bool = True) -> None:
        if log:
            self.LOG.warning(message)
        print(
            f"{Style.YELLOW}{Style.BOLD}==> WARNING:"
            f"{Style.RESET_COLOR} {message}{Style.RESET}"
        )

    def error(self, message: str, *, log: bool = True) -> None:
        if log:
            self.LOG.error(message)
        print(
            f"{Style.RED}{Style.BOLD}==> ERROR:"
            f"{Style.RESET_COLOR} {message}{Style.RESET}"
        )

    def prompt(
        self,
        message: str,
        answers: list[str] | None = None,
        default: str = "",
        *,
        log: bool = True,
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
                    f"{Style.GREEN}{Style.BOLD}::"
                    f"{Style.RESET_COLOR} {message}{Style.RESET}"
                )
                or default
            )
            if lower:
                answer = answer.lower()
            if alternates:
                answer = alternates.get(answer, answer)
            if not answers or answer in answers:
                return answer
            self.detail("Invalid answer.", log=False)
        if log:
            self.LOG.info(f"PROMPT: {message}{answer}")
        return answer

    def prompt_yes_no(self, message: str, default: str = "") -> bool:
        return (
            self.prompt(
                message,
                ["y", "n"],
                default,
                alternates=type(self).__YES_NO_ALTERNATES,
            )
            == "y"
        )


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
    original: str | Path, changed: str | Path, *, diffprog: str = ""
) -> None:
    for command in [
        diffprog,
        os.environ.get("DIFFPROG", ""),
        "nvim -d",
        "vim -d",
    ]:
        if command:
            command_line = command.split() + [str(original), str(changed)]
            if which(command_line[0]):
                LOG.info(f"Invoking diffprog: {command_line}")
                subprocess.run(command_line)
                return
    raise RuntimeError("no diffprog specified or located.")


@dataclass
class ReviewedFileUpdater:
    original: Path
    _ = KW_ONLY
    changed: Path
    delete: bool = False
    _tui: Tui = field(init=False, default_factory=lambda: Tui(LOG))

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

    def __enter__(self) -> ReviewedFileUpdater:
        return self

    def __exit__(
        self,
        exc_type: Type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self.delete:
            self.changed.unlink()
        return None

    @classmethod
    def from_configuration(
        cls, original: Path, configuration: Configuration
    ) -> ReviewedFileUpdater:
        return cls.from_content(original, content=str(configuration))

    def review(self) -> bool:
        self._tui.info(f"Review requested for file: {self.original}")
        if self._tui.prompt_yes_no("Review the changes?"):
            diff_merge(self.original, self.changed)
        return self._tui.prompt_yes_no("Proceed with installation?")

    def remove(self, review: bool = True) -> None:
        if not review or self.review():
            self._tui.info(f"Removing file: {self.original}")
            if self._tui.prompt_yes_no("Proceed with removal?"):
                command_with_escalation(["unlink", str(self.original)])

    def replace(self, review: bool = True) -> None:
        if not review or self.review():
            self._tui.info(f"Replacing file: {self.original}")
            command_with_escalation(
                [
                    "cp",
                    "--no-preserve=mode,ownership",
                    str(self.changed),
                    str(self.original),
                ]
            )
