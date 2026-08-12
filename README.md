# PI-4 Control

A private, dark-mode management dashboard for a Raspberry Pi 4. Version 1 provides system and network monitoring, fixed systemd service status/restarts, and guarded reboot/shutdown controls. It uses FastAPI and plain browser assets, listens on port 8080, and rejects peers outside localhost, `192.168.1.0/24`, and Tailscale's `100.64.0.0/10` range.

The app runs unprivileged as `x`. Metrics are read through Python/psutil and the Pi thermal sensor. Service inspection uses a fixed `systemctl show` invocation; Tailscale IP discovery uses `tailscale ip -4`. Privileged operations can only invoke four root-owned helper scripts through narrowly scoped sudoers rules. The Access panel is deliberately a placeholder for a future, separately designed SQLite trusted-device subsystem.

## Install on Raspberry Pi OS

The included service assumes this repository is at `/home/x/pi-dashboard`. If it is elsewhere, update both `WorkingDirectory` and `ExecStart` in the unit.

```bash
cd /home/x/pi-dashboard
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

Install the fixed helpers as root-owned, non-user-writable executables:

```bash
sudo install -o root -g root -m 0755 install/pi-dashboard-shutdown /usr/local/sbin/pi-dashboard-shutdown
sudo install -o root -g root -m 0755 install/pi-dashboard-reboot /usr/local/sbin/pi-dashboard-reboot
sudo install -o root -g root -m 0755 install/pi-dashboard-restart-aryehlab /usr/local/sbin/pi-dashboard-restart-aryehlab
sudo install -o root -g root -m 0755 install/pi-dashboard-restart-camera /usr/local/sbin/pi-dashboard-restart-camera
```

Never make these helpers writable by `x`: that would allow replacing a permitted command. Check with `ls -l /usr/local/sbin/pi-dashboard-*`.

Validate the sudoers source **before installing it**. Keep another root session open while changing sudoers so a mistake cannot lock you out.

```bash
sudo visudo -cf install/pi-dashboard.sudoers
sudo install -o root -g root -m 0440 install/pi-dashboard.sudoers /etc/sudoers.d/pi-dashboard
sudo visudo -cf /etc/sudoers.d/pi-dashboard
sudo -u x sudo -n -l
```

The rule allows `x` to run only the four named helpers as root, without a password. It does not grant general passwordless sudo.

Install and start the dashboard unit:

```bash
sudo install -o root -g root -m 0644 install/pi-control-dashboard.service /etc/systemd/system/pi-control-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable --now pi-control-dashboard.service
sudo systemctl status pi-control-dashboard.service
```

After updates, use `sudo systemctl restart pi-control-dashboard.service`. Logs are available with `journalctl -u pi-control-dashboard.service -n 100 --no-pager`.

## Access and test

Open `http://192.168.1.<pi-address>:8080` on the local `192.168.1.0/24` LAN, or `http://<tailscale-ip>:8080` from a device on the same tailnet. Find the latter with `tailscale ip -4` on the Pi. The app intentionally binds to `0.0.0.0`; its middleware applies the source-IP allowlist.

**Do not publish port 8080 through Cloudflare Tunnel, router port forwarding, or any public reverse proxy.** The dashboard has no user authentication. Keep it private to LAN/Tailscale and do not add it to the existing cloudflared configuration.

Test JSON endpoints locally:

```bash
curl http://127.0.0.1:8080/api/system
curl http://127.0.0.1:8080/api/network
curl http://127.0.0.1:8080/api/services
```

For development, run `.venv/bin/uvicorn app:app --host 0.0.0.0 --port 8080`. Run automated checks with `.venv/bin/pip install pytest httpx` followed by `.venv/bin/pytest`.

## Troubleshooting

- **403 Access denied:** confirm the client address is loopback, `192.168.1.x`, or `100.64.0.0/10`. A reverse proxy changes the peer IP and is not supported by this version.
- **Helper is not installed / restart failed:** verify the exact helper paths, root ownership, mode `0755`, sudoers mode `0440`, and both `visudo` checks. Run `sudo -u x sudo -n -l` to inspect only the effective permission list; avoid manually testing shutdown/reboot helpers unless you intend the action.
- **Service unavailable:** check the exact units with `systemctl status aryehlab.service printer-camera.service cloudflared.service tailscaled.service`.
- **No temperature:** `/sys/class/thermal/thermal_zone0/temp` must exist and be readable. Non-Pi development systems correctly report it as unavailable.
- **No interface/Tailscale:** Wi-Fi and Tailscale are optional. Check `ip address` and `tailscale status`; the rest of the dashboard remains operational.
- **Dashboard will not start:** run `.venv/bin/python -c "import app"`, inspect the journal, and confirm the repository/venv paths in the unit.

## Repository layout

`app.py` owns HTTP routing; `dashboard/` separates system, network, service, and access-control logic; `static/` is the framework-free frontend; `install/` contains deployable root helper, sudoers, and systemd templates; `tests/` checks API behavior and the security boundary.

