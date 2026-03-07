# T-009: OS and network hardening

Status: Closed
Last updated: 2026-03-07

## Problem

Beyond the existing `final_hardening.sh` (watchdog, journald, OverlayFS), multiple OS and network hardening measures are missing. The Pi is exposed on the local network with no firewall, default SSH config, and unnecessary services.

## Plan

### 1. Firewall (ufw)

Add to `final_hardening.sh`:

```bash
sudo apt-get install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw limit 22/tcp comment "SSH rate-limited"
sudo ufw allow from 192.168.0.0/16 to any port 80 comment "SettingsApp LAN only"
sudo ufw --force enable
```

### 2. SSH hardening

Create `/etc/ssh/sshd_config.d/99-epaper.conf`:

```
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

### 3. SD card mount security options

Update `install_sd_card_reader.sh` mount options from:
```
defaults,uid=...,gid=...,umask=0022,nofail
```
to:
```
defaults,uid=...,gid=...,umask=0022,nofail,nosuid,noexec,nodev
```

### 4. Kernel parameters

Create `/etc/sysctl.d/99-epaper.conf`:

```
kernel.sysrq = 0
kernel.dmesg_restrict = 1
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv6.conf.all.disable_ipv6 = 1
```

### 5. Disable unused peripherals

Add to `/boot/config.txt`:
```
dtoverlay=disable-bt
hdmi_ignore_cec_init=1
```

### 6. Disable swap

```bash
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
sudo update-rc.d dphys-swapfile remove
```

### 7. Polkit rule tightening

Narrow `10-nmcli-netdev.rules` to only Wi-Fi connection actions instead of all NetworkManager operations.

## Implementation Notes

- Steps 1-6 should be added to `final_hardening.sh` since they must persist (and OverlayFS is enabled last, making later changes non-persistent without disable/reboot).
- SSH hardening: ensure the user has key-based auth working before disabling password auth. Add a confirmation prompt.
- Firewall: the LAN range `192.168.0.0/16` should be configurable (some networks use 10.x or 172.16.x).

## Acceptance Criteria

- `final_hardening.sh` configures firewall, sysctl, swap, peripherals
- SSH hardened with key-only auth (with safety prompt)
- SD card mount uses `nosuid,noexec,nodev`
- `docs/services/hardening.md` and `docs/architecture/hardening-summary.md` updated
