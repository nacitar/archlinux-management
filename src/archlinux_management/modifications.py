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
            return updater.apply()
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
        return updater.apply()


def pc_speaker_device_owned_by_audio_group(
    options: ModificationOptions,
) -> bool:
    with FileUpdater.from_resource(
        target=Path("/etc/udev/rules.d/99-beep.rules"),
        resource="99-beep.rules",
        options=options,
    ) as updater:
        if options.apply:
            return updater.apply()
        else:
            return updater.remove()


def systemd_networkd_wait_for_any_interface_5s_timeout(
    options: ModificationOptions,
) -> bool:
    with FileUpdater.from_resource(
        target=Path(
            "/etc/systemd/system/"
            "systemd-networkd-wait-online.service.d/wait-for-any.conf"
        ),
        resource="systemd_networkd_wait_for_any_interface_5s_timeout.conf",
        options=options,
    ) as updater:
        if options.apply:
            return updater.apply()
        else:
            return updater.remove()


def xorg_conf_tear_free(options: ModificationOptions) -> bool:
    with FileUpdater.from_resource(
        target=Path("/etc/X11/xorg.conf.d/20-tearfree.conf"),
        resource="xorg_tearfree.conf",
        options=options,
    ) as updater:
        if options.apply:
            return updater.apply()
        else:
            return updater.remove()


def sysctl_steamos_vm_max_map_count(options: ModificationOptions) -> bool:
    with FileUpdater.from_resource(
        target=Path("/etc/sysctl.d/80-gamecompatibility.conf"),
        resource="sysctl_steamos_vm.max_map_count.conf",
        options=options,
    ) as updater:
        if options.apply:
            return updater.apply()
        else:
            return updater.remove()


MODIFICATION_MENU = Menu[Callable[[ModificationOptions], bool]](
    "Select modification",
    {
        "pacman hook to run paccache": pacman_hook_paccache,
        "journald size and age limits": journald_limits_size_and_age,
        "pc speaker device owned by audio group": (
            pc_speaker_device_owned_by_audio_group
        ),
        "systemd-networkd wait for ANY interface (5s timeout)": (
            systemd_networkd_wait_for_any_interface_5s_timeout
        ),
        "xorg.conf tear free": xorg_conf_tear_free,
        "SteamOS value for vm.max_map_count": sysctl_steamos_vm_max_map_count,
    },
)
MODIFICATION_LOOKUP: dict[str, Callable[[ModificationOptions], bool]] = {
    value.__name__: value for value in MODIFICATION_MENU.values()
}
