# systemd Service (Linux)

apex includes a systemd unit file for running the API server as a managed background service on Linux. This provides automatic startup on boot, crash recovery, and integration with standard Linux service management tools.

## Prerequisites

Before installing the service, ensure that:

1. apex is installed in a virtual environment at `/opt/apex/.venv` (or adjust paths accordingly).
2. A dedicated `apex` system user exists (recommended for security).
3. An inference engine (such as Ollama) is running and accessible.

Create the user and installation directory:

```bash
sudo useradd --system --create-home --home-dir /opt/apex apex
sudo -u apex python3 -m venv /opt/apex/.venv
sudo -u apex git clone https://github.com/apex/apex.git /opt/apex/apex
cd /opt/apex/apex && sudo -u apex uv sync --extra server
```

## Installing the Service

The unit binds `0.0.0.0`, so an **API key is required** — and the unit
declares `EnvironmentFile=/etc/apex/env` (no `-` prefix), so it will
**fail to start** until that file exists with a key. Create it first:

```bash
sudo mkdir -p /etc/apex
echo "apex_API_KEY=$(APEX auth generate-key)" | sudo tee /etc/apex/env
sudo chmod 600 /etc/apex/env
```

Then copy the unit file, reload the daemon, and enable the service:

```bash
sudo cp deploy/systemd/apex.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable apex
sudo systemctl start apex
```

Clients must send `Authorization: Bearer <key>` on `/v1/*` and `/api/*`
requests. (If you instead bind to `127.0.0.1`, the key is optional and you
can drop the `EnvironmentFile` line.)

Verify it is running:

```bash
sudo systemctl status apex
```

## Service File Reference

The provided unit file at `deploy/systemd/apex.service`:

```ini
[Unit]
Description=apex API Server
After=network.target

[Service]
Type=simple
User=apex
WorkingDirectory=/opt/apex
ExecStart=/opt/apex/.venv/bin/APEX serve --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
Environment=HOME=/opt/apex

[Install]
WantedBy=multi-user.target
```

### `[Unit]` Section

| Directive     | Value              | Description                                                                 |
|---------------|--------------------|-----------------------------------------------------------------------------|
| `Description` | `apex API Server` | Human-readable name shown in `systemctl status` and logs.              |
| `After`       | `network.target`   | Delays startup until the network stack is available, since the server binds to a network socket and may need to reach a remote engine. |

### `[Service]` Section

| Directive          | Value                                                              | Description                                                                                     |
|--------------------|--------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|
| `Type`             | `simple`                                                           | The process started by `ExecStart` is the main service process. systemd considers the service started immediately. |
| `User`             | `apex`                                                       | Runs the server as the `apex` user rather than root, limiting the blast radius of any security issue. |
| `WorkingDirectory` | `/opt/apex`                                                  | Sets the working directory for the process. This is where apex looks for local files and writes data. |
| `ExecStart`        | `/opt/apex/.venv/bin/APEX serve --host 0.0.0.0 --port 8000` | The command to start the server. Uses the full path to the `APEX` binary inside the virtual environment. |
| `Restart`          | `on-failure`                                                       | Automatically restarts the service if it exits with a non-zero exit code. Does not restart on clean shutdown (`systemctl stop`). |
| `RestartSec`       | `5`                                                                | Waits 5 seconds before attempting a restart, preventing rapid restart loops if the service crashes immediately on startup. |
| `Environment`      | `HOME=/opt/apex`                                             | Sets the `HOME` environment variable so apex finds its configuration at `~/.apex/config.toml` (resolving to `/opt/apex/.apex/config.toml`). |

### `[Install]` Section

| Directive    | Value               | Description                                                                                 |
|--------------|---------------------|---------------------------------------------------------------------------------------------|
| `WantedBy`   | `multi-user.target` | The service starts when the system reaches multi-user mode (standard boot target for servers). `systemctl enable` creates a symlink under this target. |

## Configuration Options

### Changing the Bind Address and Port

Edit the `ExecStart` line to change the host or port:

```ini
ExecStart=/opt/apex/.venv/bin/APEX serve --host 127.0.0.1 --port 9000
```

!!! tip
    Binding to `127.0.0.1` restricts access to localhost only. Use this when running behind a reverse proxy like Nginx or Caddy.

### Setting the Engine and Model

Pass additional flags to `APEX serve`:

```ini
ExecStart=/opt/apex/.venv/bin/APEX serve --host 0.0.0.0 --port 8000 --engine ollama --model qwen3:8b
```

### Adding Environment Variables

Add multiple `Environment` directives or use `EnvironmentFile` for complex configurations:

```ini
[Service]
Environment=HOME=/opt/apex
Environment=apex_ENGINE_DEFAULT=vllm
Environment=apex_OLLAMA_HOST=http://localhost:11434
```

Or load from a file:

```ini
[Service]
EnvironmentFile=/opt/apex/.env
```

### Changing the User

If you prefer a different service user, update both the `User` directive and the paths:

```ini
[Service]
User=myuser
WorkingDirectory=/home/myuser/apex
ExecStart=/home/myuser/apex/.venv/bin/APEX serve --host 0.0.0.0 --port 8000
Environment=HOME=/home/myuser/apex
```

### Using a Configuration File

Ensure the configuration file exists at the path where `HOME` points:

```bash
sudo -u apex mkdir -p /opt/apex/.apex
sudo -u apex cp config.toml /opt/apex/.apex/config.toml
```

The server reads `~/.apex/config.toml` on startup, where `~` resolves from the `HOME` environment variable.

## Viewing Logs

apex logs are captured by journald. View them with `journalctl`:

```bash
# View all logs for the service
sudo journalctl -u apex

# Follow logs in real time
sudo journalctl -u apex -f

# View logs since the last boot
sudo journalctl -u apex -b

# View logs from the last hour
sudo journalctl -u apex --since "1 hour ago"

# View only error-level messages
sudo journalctl -u apex -p err
```

## Managing the Service

### Start, Stop, and Restart

```bash
# Start the service
sudo systemctl start apex

# Stop the service
sudo systemctl stop apex

# Restart the service (stop + start)
sudo systemctl restart apex

# Reload configuration without full restart (sends SIGHUP)
sudo systemctl reload-or-restart apex
```

### Check Status

```bash
sudo systemctl status apex
```

Example output:

```
● apex.service - apex API Server
     Loaded: loaded (/etc/systemd/system/apex.service; enabled; preset: enabled)
     Active: active (running) since Fri 2026-02-21 10:00:00 UTC; 2h ago
   Main PID: 12345 (APEX)
      Tasks: 4 (limit: 4915)
     Memory: 256.0M
        CPU: 1min 23s
     CGroup: /system.slice/apex.service
             └─12345 /opt/apex/.venv/bin/python /opt/apex/.venv/bin/APEX serve --host 0.0.0.0 --port 8000
```

### Enable and Disable on Boot

```bash
# Enable automatic start on boot
sudo systemctl enable apex

# Disable automatic start on boot
sudo systemctl disable apex
```

### Apply Changes After Editing the Unit File

After modifying `/etc/systemd/system/apex.service`, reload the systemd daemon and restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart apex
```

## Running Alongside Ollama

If Ollama is also managed via systemd, you can add an ordering dependency so the apex service waits for Ollama to start:

```ini
[Unit]
Description=apex API Server
After=network.target ollama.service
Requires=ollama.service
```

| Directive  | Description                                                              |
|------------|--------------------------------------------------------------------------|
| `After`    | Ensures apex starts after Ollama.                                  |
| `Requires` | If Ollama fails to start, apex will not start either.              |

!!! note
    Use `Wants` instead of `Requires` if you want apex to start even when Ollama is unavailable (for example, if you plan to start Ollama manually later).

