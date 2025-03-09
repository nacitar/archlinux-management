#!/bin/bash
set -eu

if ((EUID)); then
    >&2 echo "ERROR: must be ran with root privileges."
    exit 1
fi
# run from script directory
cd "$(dirname "$(realpath "${BASH_SOURCE[0]}")")"

install_file() {
    if [[ ${#} -ne 2 ]]; then
        >&2 echo "USAGE: install_file <source> <destination>"
        return 1
    fi
    local src=${1} dest=${2}
    if [[ ! -e ${dest} ]]; then
        echo "Installing: ${dest}"
        cp "${src}" "${dest}"
    else
        echo "Skipping: ${dest}"
    fi
}
install_file 'paccache.hook' '/usr/share/libalpm/hooks/paccache.hook'
