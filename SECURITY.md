# Security Policy

A0 executes local PowerShell/Python orchestration and downloads third-party components from pinned upstream sources. Downloads are verified by hashes/commits where the A0 contract defines them.

## Supported release

- `v8.2.0-A0-STABLE` — frozen baseline; critical defects only.

## Reporting

Do not publish secrets, tokens, private URLs, credentials, or personally identifying logs in public issues. Redact local usernames and private paths where practical.

Security-sensitive reports should describe the component, affected version, reproduction conditions, and whether the issue occurs before or after third-party code is installed.

A0 is provided without warranty. Users remain responsible for reviewing downloaded third-party code and model licenses.
