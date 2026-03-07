# Hardening Summary

Last updated: 2026-03-07

## What `final_hardening.sh` Does

| Layer | What | Config |
|-------|------|--------|
| **Hardware watchdog** | Auto-reboots if system hangs | `dtparam=watchdog=on`, timeout=15s, max-load-1=24 |
| **Volatile journald** | Logs to RAM only, no SD wear | `Storage=volatile`, 50MB cap, 3-day retention |
| **Firewall (ufw)** | Deny incoming by default; SSH rate-limited; port 80 LAN-only | All RFC1918 ranges allowed for port 80 |
| **SSH hardening** | Root login off, MaxAuthTries=3, keepalive | Password auth left enabled (manual disable after key setup) |
| **Kernel params** | Disable SysRq, source routing, enable syncookies | `/etc/sysctl.d/99-epaper.conf` |
| **Disable peripherals** | Bluetooth off, HDMI CEC off | `/boot/config.txt` overlays |
| **Disable swap** | Reduce SD card wear | `dphys-swapfile uninstall` |
| **OverlayFS root** | Root filesystem read-only; changes lost on reboot | `raspi-config nonint enable_overlayfs` |
| **Shell notice** | Login warning explaining overlay behavior | Appended to `~/.bashrc` |

## What's NOT Hardened (Remaining Gaps)

### Medium

| Gap | Risk | Impact |
|-----|------|--------|
| **SettingsApp unauthenticated on 0.0.0.0:80** | No auth, no TLS | Anyone on LAN can change display settings (mitigated by firewall LAN-only rule) |
| **No automatic updates** | No unattended-upgrades | Security patches require manual overlay disable + reboot cycle |
| **Password auth still enabled in SSH** | Brute-force risk | Manual step required after confirming key-based auth works |

### Low

| Gap | Risk | Impact |
|-----|------|--------|
| **Serial console enabled** | Physical access attack vector | Attacker with UART can get shell |

## Systemd Service Hardening Status

All services now have full baseline sandboxing (T-008 completed):

| Service | NoNewPrivileges | ProtectSystem | PrivateTmp | ProtectHome | Extra |
|---------|:-:|:-:|:-:|:-:|:--|
| `epaper.service` | Yes | strict | Yes | read-only | SPI/GPIO DeviceAllow, ReadWritePaths=/mnt/epaper_sd |
| `sd-s3-sync.service` | Yes | strict | Yes | read-only | PrivateDevices, ReadWritePaths=/mnt/epaper_sd |
| `settingsapp.service` | Yes | strict | Yes | read-only | PrivateDevices, CAP_NET_BIND_SERVICE, ReadWritePaths for SD + config |
| `imageuiapp.service` (EC2) | Yes | strict | Yes | read-only | PrivateDevices |

## SD Card Mount Security

Mount options (updated in `install_sd_card_reader.sh`):
```
defaults,uid=<user>,gid=<group>,umask=0022,nofail,nosuid,noexec,nodev
```

- `nosuid` — prevent setuid execution from removable media
- `noexec` — prevent binary execution from SD card
- `nodev` — prevent device file creation on SD card

## Recommended Firewall Rules

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw limit 22/tcp comment "SSH rate-limited"
sudo ufw allow from 192.168.0.0/16 to any port 80 comment "SettingsApp LAN only"
sudo ufw enable
```

## Recommended SSH Hardening

```
# /etc/ssh/sshd_config.d/99-epaper.conf
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
PermitEmptyPasswords no
X11Forwarding no
AllowTcpForwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
```

## Recommended Kernel Parameters

```bash
# /etc/sysctl.d/99-epaper.conf
kernel.sysrq = 0
kernel.dmesg_restrict = 1
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv6.conf.all.disable_ipv6 = 1
```

## Recommended Peripheral Disablement

```bash
# /boot/config.txt (or /boot/firmware/config.txt)
dtoverlay=disable-bt       # Disable Bluetooth
hdmi_ignore_cec_init=1     # Disable HDMI CEC

# Disable swap
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
sudo update-rc.d dphys-swapfile remove

# Disable serial console
sudo raspi-config nonint do_serial 1
```

## Maintenance Workflow (with OverlayFS)

Since the root filesystem is read-only under OverlayFS, applying updates or config changes requires:

```bash
# 1. Disable overlay (requires reboot)
sudo raspi-config nonint disable_overlayfs
sudo reboot

# 2. Make changes (apt upgrade, config edits, etc.)
sudo apt update && sudo apt upgrade -y

# 3. Re-enable overlay (requires reboot)
sudo raspi-config nonint enable_overlayfs
sudo reboot
```

The SD card mount at `/mnt/epaper_sd` is unaffected by OverlayFS — it remains writable at all times.

## Related Tickets

- [T-001](../tickets/T-001-credential-cleanup.md) — Hardcoded credentials (Critical)
- [T-008](../tickets/T-008-systemd-sandboxing.md) — Systemd service sandboxing
- [T-009](../tickets/T-009-os-network-hardening.md) — OS and network hardening
