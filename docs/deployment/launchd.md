# launchd Service (macOS)

apex includes a launchd property list (plist) for running the API server as a background service on macOS. This provides automatic startup at login, automatic restart if the process exits, and log capture.

## Prerequisites

Before installing the service, ensure that apex is installed and the `APEX` command is available at `/usr/local/bin/APEX`. If you installed via `uv` or `pip` with a different prefix, adjust the path in the plist accordingly.

```bash
git clone https://github.com/apex/apex.git && cd apex && uv sync --extra server
which APEX  # Verify the installation path
```

Also ensure that an inference engine (such as Ollama) is running and accessible on the machine.

## Installing the Service

Copy the plist file to `~/Library/LaunchAgents` and load it:

```bash
cp deploy/launchd/com.apex.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.apex.plist
```

The service starts immediately (due to `RunAtLoad`) and will automatically restart at each login.

!!! note "Binds loopback by default"
    The plist binds `127.0.0.1` — reachable from this Mac but not the network,
    the right default for a personal device, and no API key is needed. To
    expose it on your LAN, change the host to `0.0.0.0` **and** uncomment the
    `EnvironmentVariables` block to set `apex_API_KEY`
    (`APEX auth generate-key`); an unauthenticated `0.0.0.0` server refuses
    to start.

Verify it is running:

```bash
launchctl list | grep apex
```

You should see a line with the PID and the label `com.apex`. A `0` in the status column indicates the service is running normally.

Confirm the server is responding:

```bash
curl http://localhost:8000/health
```

## Plist Reference

The provided plist file at `deploy/launchd/com.apex.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.apex</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/APEX</string>
        <string>serve</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
    </array>
    <!-- To expose on the LAN: set host to 0.0.0.0 and uncomment this block.
    <key>EnvironmentVariables</key>
    <dict>
        <key>apex_API_KEY</key>
        <string>REPLACE_WITH_A_REAL_KEY</string>
    </dict>
    -->
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/apex.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/apex.stderr.log</string>
</dict>
</plist>
```

### Key-by-Key Explanation

| Key                  | Value                          | Description                                                                                          |
|----------------------|--------------------------------|------------------------------------------------------------------------------------------------------|
| `Label`              | `com.apex`               | Unique identifier for the service. Used with `launchctl` commands to manage the service.             |
| `ProgramArguments`   | `["/usr/local/bin/APEX", "serve", "--host", "127.0.0.1", "--port", "8000"]` | The command and arguments to execute. Binds loopback by default; see the note above to expose on the LAN with an API key. |
| `RunAtLoad`          | `true`                         | Start the service immediately when the plist is loaded (and on each login).                          |
| `KeepAlive`          | `true`                         | Automatically restart the service if it exits for any reason. launchd monitors the process and relaunches it. |
| `StandardOutPath`    | `/tmp/apex.stdout.log`   | File where standard output is written. Contains server startup messages and access logs.             |
| `StandardErrorPath`  | `/tmp/apex.stderr.log`   | File where standard error is written. Contains error messages and stack traces.                      |

## Viewing Logs

Server output is written to the two log files specified in the plist:

```bash
# View standard output (startup messages, access logs)
cat /tmp/apex.stdout.log

# View standard error (errors, warnings)
cat /tmp/apex.stderr.log

# Follow logs in real time
tail -f /tmp/apex.stdout.log /tmp/apex.stderr.log
```

!!! tip "Persistent log location"
    Files in `/tmp` may be cleared on reboot. For persistent logs, change the paths in the plist to a permanent location:

    ```xml
    <key>StandardOutPath</key>
    <string>/Users/yourname/.apex/apex.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/yourname/.apex/apex.stderr.log</string>
    ```

    After changing the plist, unload and reload the service for the changes to take effect.

## Managing the Service

### Loading and Unloading

```bash
# Load the service (starts it due to RunAtLoad)
launchctl load ~/Library/LaunchAgents/com.apex.plist

# Unload the service (stops it and prevents it from starting at login)
launchctl unload ~/Library/LaunchAgents/com.apex.plist
```

### Starting and Stopping

If the service is loaded but you want to manually stop or start it without unloading:

```bash
# Stop the service
launchctl stop com.apex

# Start the service
launchctl start com.apex
```

!!! warning
    Because `KeepAlive` is set to `true`, using `launchctl stop` will cause launchd to restart the service almost immediately. To fully stop the service, use `launchctl unload` instead.

### Checking Status

```bash
# List all loaded services matching "apex"
launchctl list | grep apex
```

The output columns are:

| Column | Description                                                    |
|--------|----------------------------------------------------------------|
| PID    | Process ID (or `-` if not running)                             |
| Status | Last exit status (`0` = normal)                                |
| Label  | The service label (`com.apex`)                           |

## Configuration Changes

### Changing the Port or Host

Edit the `ProgramArguments` array in the plist. Each argument must be a separate `<string>` element:

```xml
<key>ProgramArguments</key>
<array>
    <string>/usr/local/bin/APEX</string>
    <string>serve</string>
    <string>--host</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>9000</string>
</array>
```

### Specifying an Engine and Model

Add additional arguments to the array:

```xml
<key>ProgramArguments</key>
<array>
    <string>/usr/local/bin/APEX</string>
    <string>serve</string>
    <string>--host</string>
    <string>0.0.0.0</string>
    <string>--port</string>
    <string>8000</string>
    <string>--engine</string>
    <string>ollama</string>
    <string>--model</string>
    <string>qwen3:8b</string>
</array>
```

### Setting Environment Variables

Add an `EnvironmentVariables` dictionary to the plist:

```xml
<key>EnvironmentVariables</key>
<dict>
    <key>apex_ENGINE_DEFAULT</key>
    <string>ollama</string>
    <key>apex_OLLAMA_HOST</key>
    <string>http://localhost:11434</string>
</dict>
```

### Using a Different `APEX` Binary Path

If `APEX` is installed in a virtual environment or a non-standard location, update the first element of `ProgramArguments`:

```xml
<key>ProgramArguments</key>
<array>
    <string>/Users/yourname/.local/bin/APEX</string>
    <string>serve</string>
    <string>--host</string>
    <string>0.0.0.0</string>
    <string>--port</string>
    <string>8000</string>
</array>
```

### Applying Changes

After editing the plist file, unload and reload the service:

```bash
launchctl unload ~/Library/LaunchAgents/com.apex.plist
launchctl load ~/Library/LaunchAgents/com.apex.plist
```

## System-Wide Installation

The instructions above install the service as a **user agent** (runs only when you are logged in). To run apex as a system-wide daemon that starts at boot regardless of user login:

1. Copy the plist to `/Library/LaunchDaemons/` (requires `sudo`).
2. Set the file ownership to `root:wheel`.
3. Optionally add a `UserName` key to run as a specific user.

```bash
sudo cp deploy/launchd/com.apex.plist /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.apex.plist
sudo launchctl load /Library/LaunchDaemons/com.apex.plist
```

!!! note
    System daemons in `/Library/LaunchDaemons/` run as root by default. Add a `UserName` key to run as a less-privileged user:

    ```xml
    <key>UserName</key>
    <string>apex</string>
    ```

