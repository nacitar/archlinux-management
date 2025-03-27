from __future__ import annotations

from pathlib import Path
from typing import Callable

from .tui import Menu
from .utility import Configuration, ReviewedFileUpdater


def pacman_hook_paccache(apply: bool) -> None:
    with ReviewedFileUpdater.from_resource(
        target=Path("/usr/share/libalpm/hooks/paccache.hook"),
        resource="paccache.hook",
    ) as updater:
        if apply:
            updater.replace()
        else:
            updater.remove()


def journald_limits_size_and_age(apply: bool) -> None:
    conf_path = Path("/etc/systemd/journald.conf")
    configuration = Configuration.from_file(conf_path)
    if apply:
        configuration.set("Journal.SystemMaxUse", "200M")
        configuration.set("Journal.MaxRetentionSec", "2week")
    else:
        configuration.comment("Journal.SystemMaxUse", "")
        configuration.comment("Journal.MaxRetentionSec", "")
    with ReviewedFileUpdater.from_configuration(
        target=conf_path, configuration=configuration
    ) as updater:
        updater.replace()


menu = Menu[Callable[[bool], None]](
    "Select modification",
    {
        "pacman hook to run paccache": pacman_hook_paccache,
        "journald size and age limits": journald_limits_size_and_age,
    },
)
argument_lookup: dict[str, Callable[[bool], None]] = {
    value.__name__: value for value in menu.values()
}
