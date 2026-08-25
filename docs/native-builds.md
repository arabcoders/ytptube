# Native builds

YTPTube provides native builds for Windows, macOS, and Linux. Each archive contains YTPTube and its Python runtime, so
you do not need to install Python to run it.

## Download and start

Download the archive for your operating system and architecture from [GitHub Releases](https://github.com/arabcoders/ytptube/releases).
Archive names follow this pattern:

```text
ytptube-{OS}-{arch}-{tag}.zip
```

Extract the full archive, then start YTPTube:

- Linux and macOS: run `./YTPTube` from a terminal.
  - you may need to make the file executable with `chmod +x YTPTube`.
- Windows: run `YTPTube.exe`.

Keep the executable with the files that were extracted beside it. YTPTube opens its interface in your default browser
and remembers the selected local port for later launches.

> [!IMPORTANT]
> The native build listens on `127.0.0.1` and disables authentication by default. This setup is intended for use from the
> same computer. Enable authentication before changing `YTP_HOST` or making YTPTube available through a reverse proxy.
> See the [security recommendations](../FAQ.md#security-recommendations) before allowing access from another device.

## Required programs

Some features call programs that are not included in the archive:

- Install [ffmpeg](https://ffmpeg.org/download.html) for media merging, conversion, thumbnail generation, and browser
  playback or transcoding.
- Some extractors require [Deno](https://deno.land/#installation) as a JavaScript runtime.

Add these programs to `PATH`, then restart YTPTube.

## Files and settings

The default `YTP_CONFIG_PATH` depends on the operating system:

- Linux: `${XDG_CONFIG_HOME:-$HOME/.config}/ytptube`
- macOS: `~/Library/Application Support/ytptube`
- Windows: `%LOCALAPPDATA%\arabcoders\ytptube`

- `YTP_DOWNLOAD_PATH` uses the user's Downloads directory.
- `YTP_TEMP_PATH` uses the operating system's application cache directory.

Native builds use these defaults:

- `YTP_HOST=127.0.0.1` listens for connections from the same computer.
- `YTP_PORT=8081` selects an available port and stores it for later launches. Set another port number to use a fixed port.
- `YTP_DISABLE_AUTH=true` starts without a local account.
- `YTP_CORS_ORIGINS=` is empty, so browser API requests are limited to the same origin.
- `YTP_ACCESS_LOG=false` disables HTTP access logging.
- `YTP_NO_BROWSER=false` opens the interface in the default browser after startup.

The configuration directory contains the database, logs, package overrides, and an optional `.env` file. Add persistent
settings to `.env`, one per line:

```env
YTP_PORT=8082
YTP_DISABLE_AUTH=false
```

Values set in the process environment take priority over `.env`. Values in `.env` take priority over the native defaults.
See the [environment-variable reference](../FAQ.md#environment-variables) for all available settings.

Run `YTPTube --no-browser` to prevent the browser from opening for one launch. Set `YTP_NO_BROWSER=true` in `.env` to
keep that behavior. After setting `YTP_DISABLE_AUTH=false`, restart YTPTube and open the interface to create the first
account.

## Update YTPTube

Download and extract the latest native release. Your database and settings remain in the configuration directory, outside
the extracted application directory. Do not copy files from an older archive over a new release.

## Override yt-dlp

The native build does not run YTPTube's automatic yt-dlp or custom-package updater. Installing a newer native release
replaces the bundled yt-dlp. To use a different yt-dlp release, install it into the native package directory with a Python
interpreter that matches the build's Python major and minor version and architecture.

Stop YTPTube before changing packages. The commands below use Python 3.13.

### Linux

```bash
export YTP_CONFIG_PATH="${XDG_CONFIG_HOME:-$HOME/.config}/ytptube"
TARGET="$YTP_CONFIG_PATH/python3.13-packages"
mkdir -p "$TARGET"
python3.13 -m pip install --upgrade --target "$TARGET" "yt-dlp[default]"
./YTPTube
```

### macOS

```bash
export YTP_CONFIG_PATH="$HOME/Library/Application Support/ytptube"
TARGET="$YTP_CONFIG_PATH/python3.13-packages"
mkdir -p "$TARGET"
python3.13 -m pip install --upgrade --target "$TARGET" "yt-dlp[default]"
./YTPTube
```

### Windows

Use PowerShell with a Python installation that matches the build's architecture:

```powershell
$env:YTP_CONFIG_PATH = Join-Path $env:LOCALAPPDATA "arabcoders\ytptube"
$target = Join-Path $env:YTP_CONFIG_PATH "python3.13-packages"
New-Item -ItemType Directory -Force $target | Out-Null
py -3.13 -m pip install --upgrade --target $target "yt-dlp[default]"
.\YTPTube.exe
```

### Select a yt-dlp release

After setting `TARGET` on Linux or macOS, use one of these commands:

```bash
# Pinned release
python3.13 -m pip install --upgrade --target "$TARGET" "yt-dlp[default]==2026.01.26"

# Nightly channel
python3.13 -m pip install --upgrade --pre --target "$TARGET" "yt-dlp[default]"

# Master channel; requires Git
python3.13 -m pip install --upgrade --target "$TARGET" \
  "yt-dlp[default] @ git+https://github.com/yt-dlp/yt-dlp.git@master"
```

On Windows, use the `$target` variable from the PowerShell example:

```powershell
# Pinned release
py -3.13 -m pip install --upgrade --target $target "yt-dlp[default]==2026.01.26"

# Nightly channel
py -3.13 -m pip install --upgrade --pre --target $target "yt-dlp[default]"

# Master channel; requires Git
py -3.13 -m pip install --upgrade --target $target "yt-dlp[default] @ git+https://github.com/yt-dlp/yt-dlp.git@master"
```

To load packages from another directory, set `YTP_PYTHON_PATH` when starting YTPTube:

```bash
YTP_PYTHON_PATH="/path/to/packages" ./YTPTube
```

Separate multiple directories with `:` on Linux and macOS or `;` on Windows. Keep `YTP_PYTHON_PATH` set for each launch.
Only use directories that untrusted users cannot modify. Packages loaded from these directories run with YTPTube's
permissions. Reinstall package overrides when a native release changes its bundled Python major or minor version.

## Reset a password

Stop YTPTube, then run:

```bash
YTPTube --reset-password --username USERNAME
```

On Windows, use the path to `YTPTube.exe`. Resetting the password invalidates the account's existing sessions.

## Stop YTPTube

Open the account menu and select **Shutdown**, or press `Ctrl+C` in the terminal that started YTPTube. Closing the browser
tab does not stop the application.

## macOS blocks the application

If macOS reports that the Python shared library failed to load or refuses to open the extracted build, remove the
quarantine attribute from the extracted directory. Replace the example path with the directory you downloaded:

```bash
xattr -cr "$HOME/Downloads/YTPTube-v2.6.7"
```

If macOS still blocks YTPTube, open **System Settings > Privacy & Security** and allow it from the security message shown
there.
