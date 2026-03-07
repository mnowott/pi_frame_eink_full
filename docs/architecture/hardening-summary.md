# Hardening Summary

Last updated: 2026-03-07

## What `final_hardening.sh` Does

| Layer | What | Config |
|-------|------|--------|
| **Hardware watchdog** | Auto-reboots if system hangs | `dtparam=watchdog=on`, timeout=15s, max-load-1=24 |
| **Volatile journald** | Logs to RAM only, no SD wear | `Storage=volatile`, 50MB cap, 3-day retention |
| **OverlayFS root** | Root filesystem read-only; changes lost on reboot | `raspi-config nonint enable_overlayfs` |
| **Shell notice** | Login warning explaining overlay behavior | Appended to `~/.bashrc` |

## What's NOT Hardened (Gap Analysis)

### Critical / High

| Gap | Risk | Impact |
|-----|------|--------|
| **No firewall** | All ports open to LAN | Anyone on network can reach port 80 (SettingsApp), SSH, etc. |
| **SettingsApp unauthenticated on 0.0.0.0:80** | No auth, no TLS | Anyone on LAN can change display settings, Wi-Fi config |
| **Systemd services unsandboxed** | Full filesystem access | Compromised service can read/write anything as service user |
| **SSH not hardened** | Default sshd config | Password auth likely enabled, root login possibly allowed |
| **SD mount missing nosuid/noexec/nodev** | Code execution from removable media | Malicious SD card could run setuid binaries |

### Medium

| Gap | Risk | Impact |
|-----|------|--------|
| **Swap not disabled** | SD card wear from swap writes | Reduces SD card lifespan |
| **Kernel params not hardened** | Default sysctl values | IP redirects, source routing, and other network attacks possible |
| **Polkit rule too broad** | All NM actions allowed for netdev group | Over-permissive NetworkManager access |
| **No automatic updates** | No unattended-upgrades | Security patches require manual overlay disable + reboot cycle |
| **Bluetooth enabled** | Unnecessary attack surface | BT stack vulnerabilities exploitable on Pi Zero W/2W/3/4 |

### Low

| Gap | Risk | Impact |
|-----|------|--------|
| **Serial console enabled** | Physical access attack vector | Attacker with UART can get shell |
| **HDMI CEC enabled** | CEC device can send commands | Minor; mostly theoretical |

## Systemd Service Hardening Status

| Service | NoNewPrivileges | ProtectSystem | PrivateTmp | Sandbox Score |
|---------|:-:|:-:|:-:|:--|
| `epaper.service` | - | - | - | **None** |
| `sd-s3-sync.service` | - | - | - | **None** |
| `settingsapp.service` | Yes | - | - | **Minimal** |
| `imageuiapp.service` (EC2) | - | - | - | **None** |

Recommended baseline for all services:

```ini
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictNamespaces=true
LockPersonality=true
RestrictRealtime=true
RestrictSUIDSGID=true
```

Additional per-service:
- `epaper.service`: needs `ReadWritePaths=/mnt/epaper_sd` and SPI/I2C device access (`DeviceAllow=/dev/spidev* rw`, `/dev/gpiomem rw`)
- `sd-s3-sync.service`: needs `ReadWritePaths=/mnt/epaper_sd` and network access
- `settingsapp.service`: needs `ReadWritePaths=/mnt/epaper_sd` and `CAP_NET_BIND_SERVICE`

## SD Card Mount Security

Current mount options:
```
defaults,uid=<user>,gid=<group>,umask=0022,nofail
```

Missing:
```
nosuid    — prevent setuid execution from removable media
noexec    — prevent binary execution from SD card
nodev     — prevent device file creation on SD card
```

Recommended:
```
defaults,uid=<user>,gid=<group>,umask=0022,nofail,nosuid,noexec,nodev
```

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
