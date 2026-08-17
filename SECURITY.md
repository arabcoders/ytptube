# Security Policy

## Reporting a vulnerability

Report security issues through [GitHub private vulnerability reporting](https://github.com/arabcoders/ytptube/security/advisories/new) (`Security` > `Report a vulnerability`). Do not open a public issue.

Expect an initial response within a few days. Include:

- A working reproduction
- The YTPTube release version shown in the UI footer
- The security impact
- Relevant configuration with secrets removed

## Supported versions

Only the latest release is supported. Update to the current Docker image or latest native release before reporting. 
Reports that cannot be reproduced on the latest release will be closed.

## Reports we close

YTPTube is an administrative application, not a sandbox for untrusted users. Anyone with valid application credentials 
is trusted to manage downloads, tasks, files, and yt-dlp options.

Reports that only describe the following behavior will be closed:

- Unauthenticated access when `YTP_DISABLE_AUTH=true`, including the default configuration in native builds. This setting 
disables application authentication and is intended for deployments protected by a trusted reverse proxy or private network.
- First-user registration through `/setup` while no account exists. This is the intended bootstrap flow; reports must 
demonstrate access after setup is complete or another authentication boundary bypass.
- Command execution through yt-dlp options such as `--exec` by an authenticated user when `YTP_DISABLE_EXEC=false`.
- Path traversal or output path control through yt-dlp output templates by an authenticated user. Output templates are 
passed to yt-dlp and are not a path sandbox.
- Internal network requests made by an authenticated administrator.

`YTP_DISABLE_EXEC=true` blocks some command-execution options. It does not turn yt-dlp into a sandbox.

A report about these areas must demonstrate a boundary bypass, such as access without valid authentication while auth is 
enabled.

## Generated reports

Verify scanner and LLM output before submitting it. Reports that contain unreviewed generated output without a working 
reproduction and demonstrated impact will be closed.
