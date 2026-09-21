# Security & Privacy

## Authentication & Authorization
1. **Passwords**: Hashed securely using Argon2id.
2. **JWT & Refresh Rotation**: Short-lived access tokens (15m) and rotating refresh tokens (7d).
3. **Token Invalidation**: `token_version` tracking in the database revokes all active access tokens immediately upon account locking, password change, or forced logout. Refresh token reuse invalidates the entire token family.
4. **RBAC & Isolation**: Every database collection enforces `institution_id` isolation to prevent cross-tenant data leaks. Roles (Admin, Faculty, Student) strictly define API access scopes.

## Biometric Privacy
1. **No Raw Embeddings**: The backend never returns raw face embeddings to clients in API responses.
2. **Encryption at Rest**: SFace embeddings are symmetrically encrypted using AES-GCM before being stored in MongoDB. The encryption key (`FACE_EMBEDDING_ENCRYPTION_KEY`) must be explicitly configured in the production environment.
3. **Image Retention**: Uploaded face images are used strictly for feature extraction during enrollment/attendance and are not retained indefinitely on the filesystem unless explicitly configured for audit purposes.

## Liveness & Anti-Spoofing
The system implements **development-grade challenge-response liveness**.
- It uses MediaPipe on the desktop client to detect blinking and head poses.
- **Disclaimer**: This is *not* a certified PAD (Presentation Attack Detection) system, nor is it bank-grade or production anti-spoofing. It is intended to prevent trivial static-image spoofing in academic environments.
- Android clients do not support real-time Python liveness; they rely on native photo capture and backend processing.

## Production Hardening
- Wildcard CORS (`*`) with credentials is fundamentally blocked in production.
- Health/Readiness endpoints do not leak stack traces, database URIs, or secret keys.
- Input validation (Pydantic) sanitizes request payloads, preventing oversized/malformed data ingestion.
