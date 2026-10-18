# Android phone connectivity and login

October 18 recovery: the current verified laptop address is `172.20.10.2`.
The fresh demo copy is `dist/AttendAI-Demo.apk`; see
`docs/continuation-recovery.md` for its final verification and database state.
Recheck the laptop IP after changing networks. For a stable demo server, run
`./scripts/run_backend.ps1 -NoReload`.

From the project root, start one backend:

```powershell
.\scripts\run_backend.ps1 -NoReload
```

The development server binds to `0.0.0.0:8000`. If a listener already exists,
the script stops with its PID/address instead of starting another server.
Stop the old server using Ctrl+C in its terminal, then rerun the command.
`0.0.0.0` is a bind address; enter the laptop's Wi-Fi IPv4 address in the phone.

Build with the current laptop address (check `ipconfig` after changing networks):

```powershell
.\scripts\build_android.ps1 -Target apk -ApiUrl "http://172.20.10.2:8000"
```

Output: `app\build\android\apk\attendai.apk` (ARM64).
The script bundles `core/build_config.py`. The packaged runtime gives its URL
precedence over `.env`/environment settings. Origins and bases ending in
`/api/v1` are normalized before adding endpoint paths. Android rejects loopback
addresses. The build verifies the URL inside the final APK/AAB and imports its
actual Python sources in isolation with a conflicting environment URL to check
precedence. This is a host-side packaging check, not an Android device test.

HTTP is for local development only. An explicitly supplied HTTP build temporarily
sets the Flet application manifest's `usesCleartextTraffic` to `true`; HTTPS
builds keep it `false`. The script restores the original project configuration
and any preexisting generated config, even when the build fails. Use HTTPS for
production. Python HTTPX uses native sockets, so an absent Android cleartext flag
alone does not prove why a Python request failed; the laptop's loopback-only bind
was a confirmed connectivity blocker.

## Check the network before opening the app

1. Put the phone and laptop on the same trusted Wi-Fi; avoid guest networks.
2. On the laptop, open `http://172.20.10.2:8000/api/v1/health`.
3. Open that exact URL in the phone browser. Expect `success: true`, `status: ok`
   and `database: connected`. `/api/v1/ready` should also return HTTP 200.
4. If localhost works but the LAN URL fails on the laptop, verify the listener:

   ```powershell
   Get-NetTCPConnection -LocalPort 8000 -State Listen
   Get-NetConnectionProfile
   ```

   The listener should use `0.0.0.0`, not `127.0.0.1`.

5. If the laptop's LAN URL works but the phone browser fails, check Windows
   Firewall and the router's AP/client isolation settings. At verification time,
   Wi-Fi was classified as **Public**, with firewall enabled and no explicit
   TCP 8000 inbound rule. This does not by itself prove firewall blocking.
   Do not disable the firewall. If needed, open an Administrator PowerShell and
   add a rule restricted to this TCP port, this laptop address and the phone IP
   (replace the example phone IP and use your current network profile):

   ```powershell
   New-NetFirewallRule -DisplayName "AttendAI phone dev 8000" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -LocalAddress 172.20.10.2 -RemoteAddress "172.20.10.3" -Profile Public
   ```

   Remove the temporary rule after testing:

   ```powershell
   Remove-NetFirewallRule -DisplayName "AttendAI phone dev 8000"
   ```

   If the scoped rule does not help, check guest Wi-Fi/client isolation and
   VPN routing. A successful request from the laptop cannot verify the phone's
   network path.

## Install and test

1. Copy `app\build\android\apk\attendai.apk` to the phone and install/update it.
   If Android reports a signing mismatch, uninstalling clears local application
   state; do that only if an update cannot be installed.
2. Open the app, continue to Login, and use the top-right menu's **Server
   settings** to confirm the built URL. **Check API** retries the status check.
3. Sign in using an existing institution account's email **or** username and
   its existing password. The JSON payload is `identifier` plus `password`;
   no account/password creation is part of this fix.
4. Check valid credentials, invalid credentials, and Wi-Fi off. A 401 should
   show the backend's credential error while the API remains reachable. Network
   failures should identify timeout, connection/refusal or DNS where available.
   Logs include request IDs and error classes, never passwords/tokens/payloads.
5. At narrow width, check that the actions menu is visible, the form scrolls,
   the keyboard leaves the password/Login reachable, and status/navigation bars
   do not cover content. Repeat in dark mode and landscape. Development role
   previews remain labelled UI-only and do not create authentication tokens.

## Regression checks

Run backend and frontend suites in separate Python processes, because both
packages are named `app`. From the project root:

```powershell
$taskRoot = (Get-Location).Path
$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = "$taskRoot\backend;$taskRoot"
    & .\.venv\Scripts\python.exe -m pytest backend/tests -q
    $env:PYTHONPATH = $taskRoot
    & .\.venv\Scripts\python.exe -m pytest app --ignore=app/build -q
} finally {
    $env:PYTHONPATH = $oldPythonPath
}
git diff --check
```

Android/Flet references: [Flet Android manifest customization](https://flet.dev/docs/publish/android/)
and [Android application network policy](https://developer.android.com/guide/topics/manifest/application-element#usesCleartextTraffic).
