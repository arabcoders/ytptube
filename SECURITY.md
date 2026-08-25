# Security Policy

## Reporting a vulnerability

Report security issues via [GitHub](https://github.com/arabcoders/ytptube/security/advisories/new). Do not open a public issue.

Expect a reply within a few days, usually within hours. Include:

- The security impact
- A working re-production. `PoC` code is preferred, but a detailed description of the steps to reproduce is acceptable.
- The YTPTube release version shown in the UI footer
- Relevant configuration with secrets removed

Security issues in yt-dlp itself, including vulnerabilities in its extractors, option parsing, or command execution,
should be reported to the [yt-dlp project](https://github.com/yt-dlp/yt-dlp/security/advisories/new), not to YTPTube.

Report issues to YTPTube when the vulnerability is caused by its integration or exposes functionality without the
required authentication boundary.

## Supported versions

Only the latest release is supported. Update to the current Docker image or latest native release before reporting.
Reports that cannot be reproduced on the latest release will be closed.

## Reports we close

YTPTube is an administrative application, not a sandbox for untrusted users. Anyone with valid application credentials
is trusted to manage the entire YTPTube instance and what it has access to.

Reports that only describe the following behavior will be closed:

- Unauthenticated access when `YTP_DISABLE_AUTH=true`, including the default configuration in native builds. This setting
  disables application authentication and is intended for deployments protected by a trusted reverse proxy or private network.
- First-user registration through `/setup` while no account exists. This is the intended bootstrap flow; reports must
  demonstrate access after setup is complete or another authentication boundary bypass.
- Behavior caused by yt-dlp itself, including command execution or path control through options such as `--exec`, `--output`,
  or `--netrc`. yt-dlp is not sandboxed and can execute arbitrary commands.
- YTPTube does not sandbox outbound network access. Authenticated administrators can cause requests to internal services,
including through redirects or yt-dlp behavior or even via dns rebinding.

A report about these areas must demonstrate a boundary bypass, such as access without valid authentication while auth is
enabled.

## Generated reports

Verify scanner and LLM output before submitting it. Reports that contain unreviewed generated output without a working 
reproduction and demonstrated impact will be closed.
