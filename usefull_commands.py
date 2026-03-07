# see mounts


# run s3 import servicr with outputs
sudo systemctl start sd-s3-sync.service
# see logs
journalctl -u sd-s3-sync.service
# or only current boot -b
#nmcli
nmcli device wifi list
# or
nmcli dev wifi
# rescan list
sudo nmcli device wifi rescan
