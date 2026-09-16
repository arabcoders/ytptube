# Authentication

YTPTube server installations require a local account. OIDC and proxy authentication can be enabled together.

> [!NOTE]
> Create and test the local account before enabling external authentication. It remains available for local login and is the
> account used by external logins.

External identities aren't provisioned separately. Every admitted OIDC or proxy identity uses `auth.external_user`, which has
full administrator access.

## Configure external authentication

External authentication is configured in `{YTP_CONFIG_PATH}/config.toml`, normally `/config/config.toml`. There are no environment variables for these settings.

```toml
[auth]
external_user = "owner"

[auth.oidc]
issuer = "https://id.example.org"
client_id = "ytptube"
client_secret = "client-secret"
redirect_uri = "https://ytp.example.org/ytptube/api/auth/oidc/callback"

[auth.remote_user]
enabled = true
header = "Remote-User"
trusted_proxies = ["10.0.0.10", "2001:db8::10/128"]
```

> [!IMPORTANT]
> The redirect URI must exactly match the URI registered with the OIDC provider, including its scheme, host, port where
> applicable, path, and deployment prefix or base path.

Register the redirect URI with the OIDC provider. OIDC uses provider discovery, authorization code flow, and PKCE. Start at
`GET /api/auth/oidc/login`; the provider returns to `GET /api/auth/oidc/callback`.

Restart YTPTube after changing the file, then verify local login, OIDC login, and proxy login separately. Local logout ends the YTPTube session, but doesn't end the OIDC provider session. Proxy logout is controlled by the proxy.

## Trusted reverse-proxy requirements

> [!IMPORTANT]
> This method is safe only when clients cannot reach the YTPTube origin directly.

YTPTube trusts the configured `auth.remote_user` header only when the raw connection peer belongs to `auth.remote_user.trusted_proxies` and the request is same-origin. The default header is `Remote-User`. `X-Forwarded-For` never authenticates the proxy.

Configure the proxy to strip inbound identity headers, authenticate the request, and set the header itself. `YTP_TRUSTED_PROXIES` is separate. It only controls client IP metadata from `X-Forwarded-For`.

## Troubleshooting and protection

- Confirm `auth.external_user` names an existing local account.
- Check that the OIDC redirect URI matches exactly, including its scheme, host, port, path, and base path.
- For proxy login failures, check the raw peer CIDR, same-origin request, and header stripping/setting rules.
- Restart after every configuration change.

Protect `config.toml` and its backups. They contain the OIDC `client_secret`.
