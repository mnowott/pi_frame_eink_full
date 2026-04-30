# T-008: Add systemd sandboxing to all services

Status: Closed
Last updated: 2026-03-07

## Problem

All four systemd services run with no (or minimal) sandboxing. A compromised service has full filesystem access as the service user.

| Service | Current Sandboxing |
|---------|-------------------|
| `epaper.service` | None |
| `sd-s3-sync.service` | None |
| `settingsapp.service` | `NoNewPrivileges=true` only |
| `imageuiapp.service` (EC2) | None |

## Plan

Add a baseline hardening block to every service unit:

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

### Per-service additions

**epaper.service** — needs hardware and SD access:
```ini
ReadWritePaths=/mnt/epaper_sd
DeviceAllow=/dev/spidev0.0 rw
DeviceAllow=/dev/spidev0.1 rw
DeviceAllow=/dev/gpiomem rw
SupplementaryGroups=spi i2c gpio
```

**sd-s3-sync.service** — needs SD and network:
```ini
ReadWritePaths=/mnt/epaper_sd
PrivateDevices=true
```

**settingsapp.service** — needs SD access and port 80:
```ini
ReadWritePaths=/mnt/epaper_sd
ReadWritePaths=~/.config/epaper_settings
PrivateDevices=true
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
```

**imageuiapp.service** — needs network only:
```ini
PrivateDevices=true
ProtectHome=read-only
```

### Files to modify

- `eInkFrameWithStreamlitMananger/setup.sh` (generates epaper.service)
- `pi-s3-sync/systemd/sd-s3-sync.service`
- `s3_image_croper_ui_app/install_settings.sh` (generates settingsapp.service)
- `s3_image_croper_ui_app/install_as_aws_linux_caddy.sh` (generates imageuiapp.service + caddy.service)

### Validation

After each change, verify the service still starts:
```bash
sudo systemctl daemon-reload
sudo systemctl restart <service>
sudo systemctl status <service>
journalctl -u <service> --no-pager -n 20
```

Use `systemd-analyze security <service>` to score the hardening level.

## Acceptance Criteria

- All services have the baseline sandboxing block
- All services pass `systemd-analyze security` with score < 5.0 (MEDIUM or better)
- All services still function correctly after sandboxing
- `docs/services/*.md` updated with new unit file contents
