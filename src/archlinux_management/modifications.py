from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .configuration import Configuration
from .file_updater import FileUpdater, FileUpdaterOptions
from .tui import Menu


@dataclass
class ModificationOptions(FileUpdaterOptions):
    apply: bool


def pacman_hook_paccache(options: ModificationOptions) -> bool:
    with FileUpdater.from_resource(
        target=Path("/usr/share/libalpm/hooks/paccache.hook"),
        resource="paccache.hook",
        options=options,
    ) as updater:
        if options.apply:
            return updater.update()
        else:
            return updater.remove()


def journald_limits_size_and_age(options: ModificationOptions) -> bool:
    conf_path = Path("/etc/systemd/journald.conf")
    configuration = Configuration.from_file(conf_path)
    if options.apply:
        configuration.set("Journal.SystemMaxUse", "200M")
        configuration.set("Journal.MaxRetentionSec", "2week")
    else:
        configuration.comment("Journal.SystemMaxUse", "")
        configuration.comment("Journal.MaxRetentionSec", "")
    with FileUpdater.from_configuration(
        target=conf_path, configuration=configuration, options=options
    ) as updater:
        return updater.update()


MODIFICATION_MENU = Menu[Callable[[ModificationOptions], bool]](
    "Select modification",
    {
        "pacman hook to run paccache": pacman_hook_paccache,
        "journald size and age limits": journald_limits_size_and_age,
    },
)
MODIFICATION_LOOKUP: dict[str, Callable[[ModificationOptions], bool]] = {
    value.__name__: value for value in MODIFICATION_MENU.values()
}
