# Authentication architecture

Phase 3 adds real Admin, Faculty, and Student authentication without public registration or automatic user migration.

## Login and institution ownership

The Flet client submits only an identifier and password. FastAPI resolves the User and derives the user's ID, Institution ID, and role from MongoDB. These values are never accepted from the client as post-login authorization facts. Email and username are lowercase and unique within an Institution.

The current login form has no Institution selector. If the same identifier exists in multiple Institutions, authentication rejects the ambiguous lookup with the generic invalid-credentials response. Institution discovery or an institution-code login step must be designed before enabling such users.

Accounts must be active. Invalid passwords increment a failure counter; the configured threshold applies a temporary lock. Responses never distinguish a missing identifier from an incorrect password, and hashes are excluded by the safe user serializer.

## Passwords and tokens

Passwords use `argon2-cffi`'s Argon2id implementation and currently require at least eight characters. The policy lives in one service so it can be strengthened later.

Access tokens are HS256 JWTs by default and expire after 15 minutes. Claims are limited to user ID (`sub`), Institution ID, role, token type, token version, issue/expiry timestamps, and JTI. Every authenticated request verifies the signature and expiry, reloads the User, enforces active status, then compares Institution ID, role, and token version. No fallback secret exists; a missing or shorter-than-32-byte `JWT_SECRET` produces `AUTH_NOT_CONFIGURED`.

Refresh tokens are high-entropy opaque credentials. MongoDB stores only their SHA-256 digest in `auth_sessions`, with user/Institution ownership, a token family, expiry, metadata, and revocation timestamps. Refresh atomically claims and revokes the old record before issuing the next pair. Use of a correctly matching rotated token is treated as reuse and revokes the remaining family. A TTL index removes only records whose explicit `expires_at` has passed.

Logout revokes the current refresh session. Logout-all revokes every user session and increments `token_version`, invalidating previously issued access tokens when they are revalidated.

## API and RBAC

The lifecycle endpoints are `/api/v1/auth/login`, `refresh`, `logout`, `logout-all`, and `me`. Reusable dependencies provide authenticated-user, single/multiple-role, and Institution checks. Development/test-only verification routes demonstrate Admin, Faculty, and Student boundaries. UI navigation is role-aware for usability; backend dependencies remain authoritative.

Configured CORS origins are explicit and comma-separated. The server adds no CORS middleware when none are configured, never uses a wildcard, and does not enable credentialed cookies. Native Android requests are not governed by browser CORS, while Flet Web deployments require their exact browser origins.

## Client lifecycle and token storage

`AuthState` owns the current user, loading/error status, and a token-storage abstraction. Phase 3 deliberately provides memory-only storage: credentials disappear at process exit and are never written to a plaintext file. The API client adds the bearer access token, attempts one refresh after a 401, retries the original request once, and clears state if refresh fails. It cannot enter a refresh loop.

Production Android persistence requires a reviewed platform keystore/secure-storage integration. Browser persistence requires a reviewed server-assisted/session strategy that accounts for XSS and CSRF; ordinary local storage is not claimed to be secure. Until then, users sign in again after restarting.

## Development preview separation

`ENABLE_DEV_ROLE_PREVIEW=true` only has effect in `APP_ENV=development`. Preview roles remain static UI tooling: they do not call auth endpoints, create tokens, or set `AuthState`. Real sessions never display the preview switcher. Turning the flag off removes all preview controls and leaves only real login.

The guarded Phase 2 academic development API still depends solely on `ENABLE_DEV_ACADEMIC_API`; authentication does not expose it.

## Provisioning and operations

Public signup is intentionally absent. `scripts/create_admin.py` is a manual development bootstrap that requires an existing Institution ID, a configured database whose name begins with `attendai_python`, and exact confirmation of the database target. It is never executed automatically and never prints a password.

Security logs contain only generic events and user/family identifiers. Passwords, hashes, tokens, secrets, and raw credentials are never logged.
