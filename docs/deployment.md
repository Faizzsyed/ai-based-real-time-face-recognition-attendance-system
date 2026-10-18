# AttendAI Deployment Guide

For the strictly free Render + MongoDB Atlas testing workflow, use [the cloud test runbook](free-cloud-testing.md). It defines the isolated database, free-only resource settings, private bootstrap and acceptance gates. It does not claim final production sign-off.

## 1. Prerequisites
- Python 3.11+ or Docker.
- A MongoDB cluster (e.g., MongoDB Atlas or a managed instance).
- Required ONNX models (`face_detection_yunet_2023mar.onnx`, `face_recognition_sface_2021dec.onnx`) present in the `models/` directory if face biometrics are enabled.

## 2. Environment Variables
You must explicitly configure secure settings for production. The backend uses strict validation when `APP_ENV=production`.
- `APP_ENV=production`
- `MONGODB_URI`: Must be explicitly set to a valid connection string.
- `JWT_SECRET`: Must be exactly 32+ characters long.
- `FACE_EMBEDDING_ENCRYPTION_KEY`: Must be exactly 32 characters long if `FACE_AI_ENABLED=true`.
- `CORS_ORIGINS`: Empty disables browser cross-origin access and works for native clients. If browser origins are needed, list explicit HTTPS origins. Wildcards (`*`) are rejected.
- `FACE_REFERENCE_STORAGE`: `auto` uses private local files in development and encrypted MongoDB GridFS in production. Production rejects `local`.
- `CLOUD_TEST_MODE`: When true, requires production mode, verified Atlas TLS settings and `MONGODB_DATABASE=attendai_cloud_test`; a URI selecting the development database is rejected.

See `.env.example` for all configurable variables. Never commit your `.env` file to source control.

## 3. Local Backend
For local development, simply run:
```bash
python -m uvicorn app.main:app --app-dir backend --reload
```
By default, this binds to `http://127.0.0.1:8000`.

## 4. LAN Backend
To expose the API to Android testing on your local network:
```bash
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```
For a desktop client, set `API_BASE_URL` in its environment or `.env` to your machine's LAN IP. For Android, explicitly build with that URL:

```powershell
.\scripts\build_android.ps1 -Target apk -ApiUrl "http://192.168.1.50:8000"
```

The phone must be able to reach that address over the LAN. HTTP builds enable Android cleartext traffic only for development; HTTPS builds retain the secure manifest default. The script restores the manifest settings and any previous generated module even if the build fails.

## 5. Production Backend
We provide startup scripts for production:
- Windows: `.\scripts\start_prod.ps1`
- Linux/Mac: `./scripts/start_prod.sh`

Run with your virtual environment active. Both launchers select the backend's `app` package using `--app-dir`, set `APP_ENV=production`, and accept process environment variables `API_HOST` (default `0.0.0.0`) and `PORT`, then `API_PORT` (default `8000`). Backend security and MongoDB settings come from environment variables or the backend root `.env`. Bind arguments in these launchers use the process environment; a `.env` file alone does not set the launcher's host/port. Keep proxy header trust limited to your actual reverse proxy; do not trust arbitrary internet senders.

Or use Docker:
```bash
docker build -t attendai-backend .
docker run -p 8000:8000 --env-file .env -e APP_ENV=production -e API_HOST=0.0.0.0 attendai-backend
```

## 6. MongoDB Configuration
Production requires a dedicated MongoDB instance.
- **Persistence**: Encrypted face templates, encrypted GridFS reference images, attendance and accounts persist in MongoDB. Recognition uses templates independently of optional reference photos. The free-test runbook does not enable paid backups or persistent disks.
- Initialization is idempotent; existing collections will not be dropped at startup.

## 7. Model Setup
Face AI uses `YuNet` for detection and `SFace` for recognition. The Docker build runs the existing checksum-pinned downloader, including the MediaPipe asset used by desktop liveness; laptop files are not required or uploaded. MediaPipe Python runs in the desktop client, not the backend. Enabled but unavailable backend models cause readiness to return 503. With `FACE_AI_ENABLED=false`, manual attendance remains available.

## 8. HTTPS / Reverse Proxy Assumptions
Deploy the FastAPI backend behind a secure reverse proxy (e.g., Nginx, Caddy, or a managed cloud load balancer) terminating TLS.
Client requests will flow like this:
`Client -> HTTPS -> Reverse Proxy -> HTTP -> Uvicorn/FastAPI`

## 9. Health & Readiness Checks
- **Health Check**: `GET /api/v1/health` (Returns process status and DB connection state).
- **Readiness Check**: `GET /api/v1/ready` pings MongoDB and verifies enabled YuNet/SFace models. Missing dependencies return sanitized 503 responses.

## 10. Frontend API URL Configuration
The architecture remains `Flet Android/Desktop -> HTTPS -> FastAPI -> MongoDB`. Only the backend receives `MONGODB_URI`, JWT signing secrets and biometric encryption keys. Clients receive JWTs from the auth API; they never open a database connection.

Desktop resolution is `API_BASE_URL` in the process environment, then the desktop working-directory `.env`, then `http://127.0.0.1:8000`. Use `APP_ENV=production` and `API_BASE_URL=https://api.example.com` for a production desktop client; production always requires HTTPS even if `ALLOW_INSECURE_DEV_API=true` was accidentally set.

`app/core/api_config.py` owns URL validation and normalization. Backend roots, optional proxy prefixes and a trailing `/api/v1/` are accepted; the client stores the normalized root and adds `/api/v1/...` exactly once. Credentials, query parameters, fragments, malformed hosts/ports and Android loopback/unspecified addresses are rejected with messages that omit the submitted value. `ApiClient` construction and the server settings dialog both use the same policy. Server settings apply to the current session; the next startup uses the configured URL again.

The API badge checks `GET /api/v1/health`. Connected means that an HTTP response reached the client, including an API error response; Offline means a transport failure. Database readiness is separate: `/api/v1/ready` returns 503 while MongoDB is unavailable. The badge never means that the APK connected directly to MongoDB.

## 11. Android Production API URL
Use the existing wrapper with an explicit, future public API URL:

```powershell
.\scripts\build_android.ps1 -Target apk -ApiUrl "https://api.example.com"
```

Replace the example only after a backend endpoint exists. No actual domain has been selected, deployed or validated by this configuration work. Use `-Target aab` for the equivalent app bundle.

The exact build flow is:

1. `build_android.ps1 -ApiUrl` calls `prepare_android_config.py`, which uses the same validator as the client.
2. It temporarily writes the normalized public URL to the ignored `app/core/build_config.py` as `ANDROID_API_BASE_URL`.
3. Flet packages that Python module with the existing app. At startup, `main.py` preserves the packaged `app.*` import layout, and `get_settings()` reads the generated constant.
4. The packaged URL overrides runtime `API_BASE_URL`. Android does not load a runtime `.env`; missing/invalid generated URLs fail clearly instead of choosing localhost. HTTP build URLs select development mode, and HTTPS build URLs select production mode and disallow HTTP overrides.
5. `ApiClient` resolves the same value for health, authentication, refresh and all role APIs. The existing post-build verifier checks the embedded module, isolated client imports, URL policy, Internet permission and manifest cleartext setting. Dotenv files are excluded and rejected in the payload.
6. The wrapper restores temporary source/configuration changes in `finally`.

The same APK can point Admin, Faculty and Student users to one backend; their login and existing backend permissions determine their roles. For different Wi-Fi/mobile networks, the endpoint must actually be public, use a trusted TLS certificate, and reach a properly configured private MongoDB service. Native Flet clients do not require wildcard browser CORS. Keep explicit allowed web origins and the existing `allow_credentials=False` policy.

Direct `flet build apk` does not execute this injection workflow. Setting a build machine's `.env` alone does not configure an Android APK.

## 12. Logs
Logging format and level can be configured via `LOG_LEVEL` (e.g., `INFO`, `WARNING`, `ERROR`) and `LOG_FORMAT`. The backend ensures that no stack traces or filesystem paths are leaked to clients in HTTP 500 errors.

## 13. Backup Considerations
- **Database**: Ensure point-in-time recovery on your MongoDB cluster.
- **Secrets**: Securely back up your `FACE_EMBEDDING_ENCRYPTION_KEY` and `JWT_SECRET`. If the encryption key is lost, biometric authentication will fail for all enrolled users, requiring full re-enrollment.

## 14. Deployment Checklist
- [ ] TLS configured on Reverse Proxy.
- [ ] `.env` deployed securely and securely populated.
- [ ] Models downloaded.
- [ ] `APP_ENV` set to `production`.
- [ ] CORS explicitly defined.
- [ ] Readiness check passing.

## 15. Rollback Basics
To rollback, simply revert to the previous Git commit tag and restart the Uvicorn workers. Database migrations are purely additive via indexes.
