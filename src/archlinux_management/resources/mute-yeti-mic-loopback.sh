#!/bin/bash
device_type="Microphone"
device_name="USB-Audio - Yeti Stereo Microphone"
alsa_card_number=$(sed -n \
	's/^\s*\([0-9]\+\)\s\+\['"${device_type}"'\s*\]: '"${device_name}"'$/\1/p' \
	/proc/asound/cards
)
if [[ -z ${alsa_card_number} ]]; then
	>&2 echo "ERROR: could not find alsa card number for [${device_type}] ${device_name}"
	exit 1
fi

amixer -c "${alsa_card_number}" sset Mic,0 "${1:-off}"
