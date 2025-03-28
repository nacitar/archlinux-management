from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

SECTION_REGEX = re.compile(r"^\s*\[\s*(?P<name>[^]]+)\s*\]\s*$")
KEY_VALUE_PATTERN = re.compile(
    r"^(?P<indent>\s*)"
    r"(?P<key>[^=]+)(?P<assignment>\s*=\s*)(?P<value>.*)(?P<ws_post>\s*)$"
)


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

    def comment(self, key: str, value: str | None = None) -> None:
        fields = self._get_set_fields(key)
        if fields:
            fields[-1].comment = self._comment_char
            if value is not None:
                fields[-1].value = value

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
