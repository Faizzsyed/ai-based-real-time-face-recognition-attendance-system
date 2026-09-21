# AttendAI Deployment Guide

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
- `CORS_ORIGINS`: Must be explicitly set (e.g., `https://attendance.example.com`). Wildcards (`*`) are rejected.

See `.env.example` for all configurable variables. Never commit your `.env` file to source control.

## 3. Local Backend
For local development, simply run:
```bash
python -m uvicorn backend.app.main:app --reload
```
By default, this binds to `http://127.0.0.1:8000`.

## 4. LAN Backend
To expose the API to Android testing on your local network:
```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```
Update your frontend `.env` to point `API_BASE_URL` to your machine's IP (e.g., `http://192.168.1.5:8000`).

## 5. Production Backend
We provide startup scripts for production:
- Windows: `.\scripts\start_prod.ps1`
- Linux/Mac: `./scripts/start_prod.sh`

Or use Docker:
```bash
docker build -t attendai-backend .
docker run -p 8000:8000 --env-file .env attendai-backend
```

## 6. MongoDB Configuration
Production requires a dedicated MongoDB instance.
- **Persistence**: Face embeddings, attendance logs, and user schemas are persisted in MongoDB. Ensure automated backups are configured for your cluster.
- Initialization is idempotent; existing collections will not be dropped at startup.

## 7. Model Setup
Face AI uses `YuNet` for detection and `SFace` for recognition. Ensure `.onnx` files are inside the `models/` folder. The application gracefully degrades if models are missing, switching strictly to manual attendance reporting if `FACE_AI_ENABLED=false` or if models fail to load.

## 8. HTTPS / Reverse Proxy Assumptions
Deploy the FastAPI backend behind a secure reverse proxy (e.g., Nginx, Caddy, or a managed cloud load balancer) terminating TLS.
Client requests will flow like this:
`Client -> HTTPS -> Reverse Proxy -> HTTP -> Uvicorn/FastAPI`

## 9. Health & Readiness Checks
- **Health Check**: `GET /api/v1/health` (Returns process status and DB connection state).
- **Readiness Check**: `GET /api/v1/ready` (Returns 503 Service Unavailable if MongoDB is not connected; useful for load balancer routing).

## 10. Frontend API URL Configuration
The Flet client resolves the backend API via the `API_BASE_URL` environment variable.
For production deployments, compile the Flet client with the production API URL injected via environment variables or explicitly baked into the configuration before building.

## 11. Android Production API URL
Before building the APK/AAB with `flet build apk`, set the `API_BASE_URL` in your `.env` or system environment variables to the production HTTPS endpoint. The Android client will securely embed this URL.

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
