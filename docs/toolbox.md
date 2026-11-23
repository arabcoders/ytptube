# Custom Toolbox tools

Toolbox runs commands on files from **Files** or **History**. A tool stores the command and settings.
A job runs that tool on one file.

> [!IMPORTANT]
> Enable [authentication](authentication.md) and sign in to manage tools. With authentication disabled,
> you can still run shipped and previously saved tools.
>
> Commands run with YTPTube's permissions and inherit its environment. Only save definitions you
> trust. Keep scripts and executables out of directories untrusted users can write to.

## Create and run a tool

This example saves the first audio track as a FLAC file. The Docker image includes FFmpeg. For a
native install, put FFmpeg on YTPTube's `PATH` or enter its full path in **Executable**.

1. Open **Configuration > Toolbox** and select **Add**.
2. Set **Name** to `Extract FLAC`, **Output extension** to `.flac`, and **Executable** to `ffmpeg`.
3. Under **Args**, add `-i`, `{input}`, `-map`, `0:a:0`, `-c:a`, `flac`, and `{output}` in that order.
   Add one row per argument. Select **Save**.
4. In **Files** or **History**, choose **Toolbox** from the file's action menu. Select **Extract FLAC**
   under **Operation**, then select **Start**.
5. Open the job under **Tools > Jobs**. When it succeeds, select the filename under **Result** to download
   it, or select **Files** to open its folder.

A separate output stays next to the source. For example, `Interview.mp4` can produce `Interview.tool-2.flac`.
Use **Cancel** in **Jobs** to stop a queued or running job. Editing or deleting a tool doesn't change
queued jobs or remove files created by earlier jobs.

## Tool settings

### Command

**Executable** accepts a name on YTPTube's `PATH`, an absolute path, or a path starting with `./` relative
to `YTP_CONFIG_PATH`. For example, use `./extract-flac.sh` for a script in the configuration directory or
`C:\Tools\ffmpeg.exe` for an executable on Windows.

Toolbox passes **Args** in order without a shell. Put `{input}`, `{output}`, or a parameter placeholder
such as `{param.COMPRESSION}` in its own row. Other arguments are passed as written. Toolbox doesn't
expand `$VARIABLE` or interpret pipes and redirects.

### Environment variables and parameters

- **Environment variables** are fixed text values passed to every run. For example, enter `0` as the
  value for `AUDIO_TRACK`.
- **Parameters** have defaults and can be changed for a single job. Select **Boolean** for a switch,
  **Number** for a number field, or **Choices** for a dropdown. To accept decimals, use a fractional
  default. For a dropdown, add the choices and select a default.

Jobs can change declared parameters, not the command or fixed environment. Parameters also pass their values as 
environment variables with the same names. Boolean values are passed as `true` or `false`. Don't reuse a name across 
the two sections or use these reserved names:

- `TB_IN`: Absolute path to the source file, also available as `{input}`.
- `TB_OUT`: Absolute path where the command should write its result, also available as `{output}`.

Write the result to the supplied output path, not the source. Write diagnostics to stderr to see them in the job log. 
Don't put secrets in parameter values or stderr, both are saved with the job.

### Overwrite

Enable **Allow overwriting the source** in the tool definition to show **Overwrite source** when
starting a job. Turn the switch on to replace the source after a successful job, or off to keep it
and save a separate file. If overwriting changes the extension, matching download history entries
point to the new file.

## Examples

### Configurable FLAC compression

Edit **Extract FLAC** and add a **Number** parameter named `COMPRESSION`. Set its default to `5`,
minimum to `0`, and maximum to `12`. In **Args**, insert `-compression_level` and
`{param.COMPRESSION}` as two rows immediately before `{output}`. The job form now has a **Compression**
field.

### FFmpeg progress

Add `-progress` and `pipe:1` as consecutive argument rows before `-i`. Toolbox reads FFmpeg's progress
and estimates the percentage from the source duration. If the duration is unavailable or FFmpeg doesn't report progress, 
the job runs without a percentage.

### Shell wrapper

On Linux, macOS, or in the YTPTube container, save this as `extract-flac.sh` in the directory set by
`YTP_CONFIG_PATH` (`/config` by default in Docker). For desktop paths, see [Files and settings](native-builds.md#files-and-settings).

```sh
#!/bin/sh
set -eu

exec ffmpeg -nostdin -hide_banner -loglevel error -n \
  -i "$TB_IN" -map "0:a:${AUDIO_TRACK}" -c:a flac \
  -compression_level "$COMPRESSION" "$TB_OUT"
```

Run `chmod +x extract-flac.sh` in that directory. In **Extract FLAC**, set **Executable** to
`./extract-flac.sh`, clear **Args**, and add `AUDIO_TRACK=0` under **Environment variables** using
`AUDIO_TRACK` as **Key** and `0` as **Value**. Add or keep the `COMPRESSION` parameter from the
[compression example](#configurable-flac-compression).

Set `AUDIO_TRACK` to `1` to extract the second audio track. Keep the quotes around paths so filenames
with spaces work. `exec` replaces the script process with FFmpeg so Toolbox can stop it on cancellation.

## Copy and share tools

Select **Add > Import from existing** to copy a saved or shipped tool. Give the copy a name and save
it. The original tool isn't changed.

To copy a tool to another instance, choose **Actions > Export**. On the destination, open **Add**, paste
the export into **Import string**, and select **Import**. This fills the form without saving it.
Exports include fixed environment values. Check them for secrets before sharing.

## Troubleshooting

- **Tool unavailable:** Check the executable name or path on the YTPTube server. For scripts, check that the
  file is executable and that its interpreter is installed.
- **Job failed:** Open **Log details** in the job. Check that the source contains the selected audio track
  or that the script writes to `TB_OUT`.
