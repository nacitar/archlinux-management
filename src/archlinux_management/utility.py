from __future__ import annotations

import importlib.resources
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

LOG = logging.getLogger(__name__)

SECTION_REGEX = re.compile(r"^\s*\[\s*(?P<name>[^]]+)\s*\]\s*$")
KEY_VALUE_PATTERN = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<key>[^=]+)(?P<assignment>\s*=\s*)(?P<value>.+?)(?P<ws_post>\s*)$"
)


def sanitize_package_name(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.strip().lower())


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


def prompt_yes_no(message: str) -> bool:
    while True:
        response = input(f":: {message} [y/n] ")
        lower_response = response.lower()
        if lower_response in ["y", "yes", "n", "no"]:
            break
        print(f"Invalid selection: {response}")
    return lower_response[0] == "y"


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


class ReviewedFileUpdater:
    original: Path
    changed: Path

    def __init__(self, original: str | Path, changed: str | Path) -> None:
        self.original = Path(original)
        self.changed = Path(changed)

    def review(self) -> bool:
        # nvim -d test.txt test2.txt +'set noma|wincmd w'
        LOG.info(f"Review requested for file: {self.original}")
        if prompt_yes_no("Review the changes?"):
            LOG.info("Using diff utility for review...")
            # TODO: support other utilities?
            subprocess.run(
                [
                    "nvim",
                    "-d",
                    "+set noma|wincmd w",
                    str(self.original),
                    str(self.changed),
                ],
                check=True,
            )
        return prompt_yes_no("Proceed with installation?")

    def remove(self, review: bool = True) -> None:
        if not review or self.review():
            LOG.info(f"Removing file: {self.original}")
            if prompt_yes_no("Proceed with removal?"):
                command_with_escalation(["unlink", str(self.original)])

    def replace(self, review: bool = True) -> None:
        if not review or self.review():
            LOG.info(f"Replacing file: {self.original}")
            command_with_escalation(
                [
                    "cp",
                    "--no-preserve=mode,ownership",
                    str(self.changed),
                    str(self.original),
                ]
            )
