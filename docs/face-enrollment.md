# Secure Student Face Enrollment

Phase 9 performs detection, quality validation, embedding generation, averaging, and encryption on the server. The Flet client sends temporary image bytes and receives safe metadata only. It never receives ONNX models, embeddings, ciphertext, nonces, or encryption keys.

## Setup

The backend uses Python 3.11-compatible `opencv-contrib-python-headless`, NumPy, and `cryptography`. Do not install another OpenCV wheel in the same environment.

1. Install `backend/requirements.txt`.
2. Run `python scripts/download_face_models.py`. It downloads YuNet and SFace from the official OpenCV Zoo and verifies pinned SHA-256 hashes.
3. Generate a random 32-byte key, encode it as Base64 or 64 hexadecimal characters, and set `FACE_EMBEDDING_ENCRYPTION_KEY`. Keep it in a secret manager; never commit, print, or rotate it without a template migration plan.
4. Set `FACE_AI_ENABLED=true` when the deployment is operationally approved. The default model paths are under the project `models/` directory.

ONNX files are excluded by `models/*.onnx`. They must not be committed or embedded in an app build.

## Data and privacy

`face_enrollments` has one unique Institution/Student document. The embedding is normalized and encrypted with AES-256-GCM. Authenticated additional data binds the ciphertext to its Institution, Student, and model version, preventing a stored payload from being moved to another identity undetected. APIs construct allow-listed status payloads and never serialize `encrypted_embedding`.

Image uploads are read into bounded memory, processed, closed, and not written to disk. A managed profile photo can be read from `uploads/student_profiles`, but the enrollment workflow does not create another raw-image copy. Removing enrollment deletes the encrypted template document.

The UI explains the biometric purpose, temporary-frame behavior, removal option, and consent responsibility. AttendAI does not claim that enabling this feature automatically establishes legal compliance; the Institution must determine and document its lawful basis and consent/notice process.

## Quality and capture

Accepted images are JPEG, PNG, or WebP and at most 5 MB by default. YuNet must find exactly one face above the configured confidence threshold. The pipeline rejects small, blurry, poorly lit, invalid, or multi-face images.

Camera enrollment requires exactly three byte-distinct frames. Each frame must pass quality checks, consecutive normalized embeddings must be stable, and the final template is the normalized average. This is a quality/stability control, not liveness proof. Profile-photo enrollment uses one managed photo.

Flet 0.86.5 does not expose a built-in camera control in the installed runtime. Windows native desktop camera capture is therefore not assumed. The supported UI path lets Web/Android users capture photos with device facilities and select them through Flet's supported FilePicker; desktop users may select externally captured frames. No unsupported camera API is invoked.

## Manual camera test checklist

This checklist must be executed on each target Web/Android deployment separately:

- Confirm camera permission and three-file selection on the actual device/browser.
- Verify sharp, evenly lit, single-face captures pass and progress shows capture 1/3 through 3/3.
- Verify blur, darkness/glare, small face, no face, multiple faces, duplicate frames, and oversized/unsupported files fail safely.
- Verify replacing and removing a template, then reloading status.
- Inspect server storage/logs to confirm raw frames and plaintext embeddings are absent.
- Record device, browser/app version, model hashes, lighting conditions, and observed results.

No claim about real-face recognition accuracy, bias, liveness resistance, or field performance is made until representative real-camera testing and evaluation are completed.

## APIs

All routes are Admin-only and Institution-scoped:

- `GET /api/v1/admin/students/{id}/face/status`
- `POST /api/v1/admin/students/{id}/face/analyze`
- `POST /api/v1/admin/students/{id}/face/enroll`
- `POST /api/v1/admin/students/{id}/face/enroll-from-profile`
- `DELETE /api/v1/admin/students/{id}/face`
