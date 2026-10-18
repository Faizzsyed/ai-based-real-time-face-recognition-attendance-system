# Free cross-network AttendAI testing

Prepared 19 October 2026. This is a cloud-test setup, not final production approval. The user reports desktop webcam enrollment and face attendance working locally. No existing development data is to be migrated.

The source is prepared for **Render Free → MongoDB Atlas Free**, using database **attendai_cloud_test**. Account access is still required before resource creation, public verification or an APK build. Browser discovery returned no available browsers even after access was reported enabled. Render/Atlas integrations were suggested but have not been confirmed connected. GitHub integration authentication was confirmed; local `gh` authentication was invalid.

## What changed

- Docker installs `backend/requirements.txt`, includes Linux TLS/timezone dependencies, downloads checksum-verified models at build time and binds `0.0.0.0` using `PORT` (local fallback 8000).
- `render.yaml` defines one Docker web service, `plan: free`, branch `demo-cloud`, Singapore, `/api/v1/ready`, automatic deployments off, and no disks/databases/add-ons. Atlas is configured separately; do not create Render Postgres.
- Production references use encrypted GridFS payloads in the same application database. A single scoped manifest publishes a completed image set; partial uploads are cleaned without exposing incomplete sets. Old payloads are removed after replacement. Authorized routes decrypt in memory with no-store responses. Keys are not stored in GridFS metadata.
- Recognition requires the encrypted template in `face_enrollments`, not the optional reference photographs. Reference failure cannot roll back or corrupt that template; the enrollment response reports a reference warning. This warning must be resolved before persistence acceptance passes.
- Local development keeps private local encrypted files. Historical local JPG/ENC references are readable without migration. A cloud save never rewrites laptop historical files.
- Cloud-test configuration rejects the local database, a non-Atlas URI, disabled Atlas TLS verification and production local reference storage. Empty CORS disables cross-origin browser access; native clients need no wildcard.
- Readiness pings MongoDB and checks enabled backend models. Health reports process reachability independently. MongoDB uses a bounded pool and longer production connection timeouts.

## Strict free boundary

Use an Atlas **Free** cluster (formerly M0), never Flex/dedicated, and a Render **Free** web service. Do not enable paid storage, backups, dedicated outbound IPs, private networking, add-ons or upgrades. Do not add a payment method for this test. If an existing Render workspace has paid overage billing that cannot be disabled or strictly bounded for this test, stop before creating resources and resolve that account condition first.

Render's official [free-service documentation](https://render.com/docs/free) describes ephemeral files, idle spin-down after 15 minutes, roughly one-minute cold starts and monthly quotas. Accounts without a payment method are suspended rather than charged when applicable quotas are exhausted. This does not authorize upgrades if a free limit is reached. Atlas [Free cluster limits](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/) include a small shared storage/throughput budget. Encrypted photos and indexes consume that budget; keep the demo dataset small. No paid backup option is required or enabled by this runbook.

## Models and container

Only `models/.gitkeep` is tracked. Real laptop model files are ignored, not uploaded. Docker runs `scripts/download_face_models.py`; its authoritative OpenCV/Google URLs, expected sizes and pinned SHA-256 hashes are already part of the project. A mismatch fails the build. All three installed laptop assets passed that checksum verification in this task.

YuNet/SFace run on the server. MediaPipe liveness runs on the Windows desktop; its asset is also reproducibly provisioned by the downloader. Android live face recognition remains outside the acceptance claim. Source/licensing references: [OpenCV Zoo](https://github.com/opencv/opencv_zoo), [YuNet](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), [SFace](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface), [MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker). Preserve upstream licenses and notices when redistributing model assets.

Docker is not installed in the current shell environment, so an actual Linux image build and Render memory/CPU performance remain deployment checks. Do not treat the source/build-input tests as a completed container build. Enabled missing models make readiness fail safely. If the Free instance cannot run this workload within its limits, report **FREE CLOUD TESTING: BLOCKED** rather than selecting paid compute.

## Render setup

1. In the signed-in Render dashboard, verify the account/workspace can remain free without adding payment/card details or enabling chargeable overages.
2. New → Web Service → select this GitHub repository and branch `demo-cloud`. Use Docker, repository root, `./Dockerfile`, Singapore, **Free**, and no disk. Alternatively create a Blueprint from `render.yaml`, reviewing the single Free service before applying it. Do not override the Docker command or add a paid pre-deploy job.
3. Set the nonsecret environment configuration from the Blueprint. Enter each secret privately in Render's Environment page; never paste it into chat or source. Do not reuse the laptop's development JWT/encryption key.
4. The service may initially fail readiness while Atlas networking is being configured. Open the actual service → **Connect → Outbound**. Copy **all CIDR ranges shown for that service**. Do not use sample ranges from documentation and do not purchase dedicated IPs. These are shared regional ranges; database authentication still matters. Official [outbound IP steps](https://render.com/docs/outbound-ip-addresses).
5. Complete the Atlas allowlist below, then manually deploy/restart to retry the initial database connection. Wait for readiness. Record the actual Render-assigned HTTPS URL; the service name alone does not prove a particular subdomain exists.

## Atlas setup and exact network-access steps

1. Sign in to Atlas → create/select a project dedicated to this test → build a **Free** cluster. Choose a supported free region near the Render region. Verify tier is Free/M0, not Flex or a dedicated tier, and do not enable optional paid networking/backups.
2. Security → Database Access → Add Database User. Use a dedicated application user with a privately generated strong password and **readWrite on attendai_cloud_test only**. Do not grant all-database/admin access. Set and retain the password privately; do not send it to the assistant.
3. Security → Network Access → IP Access List → Add IP Address. Paste each exact CIDR copied from Render's **Connect → Outbound** tab. Label them for this specific cloud test. Add all listed ranges, then wait until Atlas shows them active. **Do not add 0.0.0.0/0.** No exact ranges were available to the agent, so none have been invented or added.
4. For the private local bootstrap only, allow the developer laptop's actual current public IP as a /32 using Atlas's “Add Current IP Address” option. Remove that temporary entry after bootstrap. This is not the laptop's private LAN address.
5. Atlas → cluster Connect → Drivers → Python. Privately construct the dedicated user's SRV URI, keeping its default TLS verification and selecting `attendai_cloud_test`. Put it only into Render's secret `MONGODB_URI` field and the bootstrap's hidden prompt. Do not change local `.env` or point Render at `attendai_python_dev`.

## Environment variables

Names are unchanged where already present. The two new settings describe storage selection and the guarded test target. Render supplies `PORT`; do not hardcode it.

| Variable | Cloud setting/purpose |
| --- | --- |
| APP_ENV | production |
| CLOUD_TEST_MODE | true; enables isolated-target checks |
| MONGODB_URI | Secret, dedicated Atlas SRV connection string |
| MONGODB_DATABASE | attendai_cloud_test |
| JWT_SECRET | Secret, new random cloud signing key of at least 32 characters |
| JWT_ALGORITHM | Existing HS256 default |
| JWT_ACCESS_TOKEN_MINUTES | Existing 15-minute default |
| JWT_REFRESH_TOKEN_DAYS | Existing 7-day default; rotation/revocation unchanged |
| AUTH_MAX_FAILED_ATTEMPTS | Existing 5-attempt default |
| AUTH_LOCKOUT_MINUTES | Existing 15-minute default |
| FACE_AI_ENABLED | true |
| FACE_REFERENCE_STORAGE | mongodb |
| FACE_EMBEDDING_ENCRYPTION_KEY | Secret, new secure 32-character cloud key; retain it securely across redeploys |
| FACE_LIVENESS_MODE | optional server evidence; desktop device challenge remains enabled |
| FACE_DETECTION_MODEL_PATH | Existing root-relative models path default |
| FACE_RECOGNITION_MODEL_PATH | Existing root-relative models path default |
| FACE_DETECTION_THRESHOLD | Existing 0.90 default |
| FACE_MATCH_THRESHOLD | Existing 0.363 default |
| FACE_IDENTIFICATION_MIN_MARGIN | Existing 0.08 default |
| FACE_ENROLLMENT_CONSISTENCY_THRESHOLD | Existing 0.40 default |
| FACE_RECOGNITION_COOLDOWN_SECONDS | Existing 8-second default |
| FACE_MAX_IMAGE_BYTES | Existing 5 MiB default |
| CORS_ORIGINS | Empty for native-only clients; explicit HTTPS origins if browser clients are later added |
| ENABLE_DEV_ACADEMIC_API | false |
| ENABLE_DEV_ROLE_PREVIEW | false |
| LOG_LEVEL | INFO |
| LOG_FORMAT | Existing console default |
| ENABLE_API_REQUEST_LOGGING | Existing true default; secret/payload sanitization remains |
| ENABLE_FILE_LOGGING | false |
| PORT | Supplied by Render; Docker binds 0.0.0.0 |

Generate cloud keys privately with a trusted local cryptographic generator/password manager. Never run a generation command through chat if its output contains the keys. Render environment fields are the deployment secret store; keys must not appear in MongoDB, APKs, git commits, URLs, screenshots or the report. Preserve the encryption key securely: replacing it without a migration makes old biometric data unreadable.

## Private first-Admin bootstrap

Render Free has no shell/one-off jobs, so run the existing bootstrap locally with its new guarded option:

```powershell
.\.venv\Scripts\python.exe scripts/bootstrap_institution_admin.py --cloud-test
```

It privately prompts for the Atlas URI and Admin password with `getpass`, ignores the developer `.env`, fixes the target to `attendai_cloud_test`, rejects non-Atlas/insecure connections, requires a cloud Admin password of at least 16 characters and asks for a final local YES. It creates only one Institution and one hashed-password Admin. The same matching pair is idempotent; conflicting/nonempty bootstrap state is rejected. No Faculty, Students, attendance or face templates are seeded. The temporary signing key created internally for configuration validation is not the Render signing key and is never printed or persisted. No bootstrap has been run against a real database in this task.

## Public verification gate

After the real service URL exists, run:

```powershell
.\.venv\Scripts\python.exe scripts/verify_cloud_api.py --api-url "https://ACTUAL-SERVICE.onrender.com"
```

Replace the placeholder only with the actual dashboard URL. This checks trusted HTTPS, health, the exact cloud database name, live readiness, loaded face models, unauthenticated access rejection, unknown-route 404 and absence of traceback text. It writes a nonsecret receipt to ignored `dist/cloud-api-verification.json`. It allows a 90-second cold-start timeout without disabling TLS verification. Wait/retry during a cold start; do not interpret it as proof of an API design failure. A live Admin login/refresh and three-role acceptance are additional checks, not implied by the unauthenticated probe.

## Fresh cloud workflow and persistence acceptance

1. Start a desktop client with `API_BASE_URL` set to the verified HTTPS root in that process, using production/HTTPS client settings. Do not overwrite the local backend database configuration. Confirm API Connected and the cloud instance's health/readiness before login.
2. Log in as the cloud Admin → Easy Setup. Create the minimum academic year, department, program, semester, class, subject, Faculty, Student, assignment and timetable through the real APIs. Enter test users' passwords privately; do not copy old local records.
3. Restart the client and verify those cloud records remain. Manually restart the Render service and verify again. An idle spin-down/reconnect is a separate persistence check. No state may depend on runtime local disk.
4. Desktop Admin → cloud Student → consent → real webcam → device challenge → automatic three captures. Confirm enrolled status and authorized reference display. Inspect only safe metadata/counts in Atlas: encrypted template, `face_reference_sets`, GridFS files/chunks. Do not print embeddings, ciphertext or keys. A reference warning fails persistence acceptance even if the template itself enrolled.
5. Restart Render, reconnect and verify the reference still displays and recognition still works. GridFS persistence is covered by isolated storage-recreation tests; this live restart check is still mandatory.
6. Desktop Faculty → correct cloud lecture → Face → Start Camera. Recognize the cloud Student, confirm Present in draft and continuous scanning. Exercise a manual Absent override, then review/finalize all roster marks. The Student must see only the finalized attendance.

## APK gate and artifact

Do not build a “cloud” APK until public verification passes. Then, using the exact same verified URL:

```powershell
.\scripts\build_android.ps1 -Target apk -ApiUrl "https://ACTUAL-SERVICE.onrender.com"
Copy-Item -LiteralPath app/build/android/apk/attendai.apk -Destination dist/AttendAI-Cloud-Test.apk
Get-Item -LiteralPath dist/AttendAI-Cloud-Test.apk | Select-Object FullName,Length
```

The wrapper verifies the packaged API URL, source bytes, runtime import policy, Internet permission and HTTPS/cleartext settings, and rejects dotenv files. Record final size, SHA-256, URL and verification result. No cloud APK has been built in this task; existing LAN artifacts are not cloud artifacts.

## Friend on a different network

Device A is the developer Windows laptop (Admin/Faculty); Device B is the friend's Android phone on mobile data or another Wi-Fi/location. Give the friend the freshly verified cloud APK and account credentials through a separate private channel; the assistant must not send messages/credentials on your behalf.

1. Both clients show API Connected to the same actual HTTPS backend. First open after idle may take about a minute.
2. Admin changes a harmless academic display field in the cloud test data; the friend refreshes and sees it.
3. Faculty saves attendance as draft; the Student must not see it as official attendance yet.
4. Faculty reviews/finalizes; the friend refreshes and sees the finalized result, including any manual override.
5. Student submits a correction request; Admin/Faculty receives it, reviews through the existing workflow, and notifications synchronize.
6. Verify dashboards, academic data, reports/navigation and role restrictions. Student cannot open Admin/Faculty endpoints.
7. Log out/in and restart both clients. Verify records, reference images, finalized results and account sessions behave correctly after a Render restart/reconnect.

Android live enrollment/face recognition is **not verified** by this procedure. The verified camera workflow remains desktop. Cloud account access, real public checks, live persistence, three-role testing and cross-network device checks must pass before status can become **CLOUD TEST: READY FOR REMOTE DEVICES**.
