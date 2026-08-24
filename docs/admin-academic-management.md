# Admin academic management

Phase 4 turns the Phase 2 academic hierarchy into authenticated, tenant-scoped Admin functionality. The production base path is `/api/v1/admin/academic`; it does not depend on `ENABLE_DEV_ACADEMIC_API`.

## First-time bootstrap

Configure only the NEW Python database through `MONGODB_URI` and `MONGODB_DATABASE`. The expected development database is `attendai_python_dev`. Then run the manual workflow:

```powershell
.\.venv\Scripts\python.exe .\scripts\bootstrap_institution_admin.py
```

The script displays the database name, collects Institution and Admin details, requires the exact confirmation `YES`, validates an IANA timezone, hashes the password with Argon2id, and creates both records. It refuses missing configuration, known legacy names, and database names outside the `attendai_python*` namespace. Re-running with the same completed records makes no changes. It is never called by application startup.

## Setup order

1. Review Institution details.
2. Create an Academic Year and mark it current.
3. Create an active Department.
4. Create a Program under that Department.
5. Create Semesters within the Program and current Academic Year.
6. Create Classes and Divisions with matching year, Department, Program, and Semester.
7. Create Subjects with matching Department, Program, and Semester.

The dashboard wizard and manual pages call the same production APIs and services. Setup status is `Incomplete`, `Partially Configured`, or `Ready` based on these seven checks.

## Routes and ownership

Admins can view and update their own Institution at `/institution`, and obtain setup progress at `/setup-status`. Academic Years, Departments, Programs, Semesters, Classes, and Subjects expose list, detail, create, and patch operations.

Every route requires a valid active Admin. `institution_id` comes from the revalidated access-token user and is never accepted from request bodies. Scoped detail and update queries include that Institution ID. Cross-tenant references are rejected, while scoped records from another Institution appear not found.

Institution code, status, and identity are immutable through ordinary Admin updates. Creates record `created_by` and `updated_by`; updates record `updated_by`. There is no hard-delete or cascade-delete endpoint.

## Validation and listing

Academic list responses consistently contain `items`, `page`, `pageSize`, `total`, and `totalPages`, with a configured maximum page size. Name/code search uses an escaped case-insensitive expression. Resource-specific filters include status, current year, Department, Program, Semester, division, and subject type.

Setting an Academic Year current first validates the candidate and then unsets the previous current year. A partial unique index remains authoritative during races. Date ordering, semester limits, active Department requirements, hierarchy ownership, duplicate codes, and safe deactivation rules are enforced in services and indexes.

## UI behavior

Only Admin navigation exposes the Academic Setup pages. Pages include search, status filtering, pagination, create/edit forms, reference dropdowns, status chips, loading, empty, and API/database error states. Deactivation prompts for confirmation and never deletes dependents. Faculty and Student shells cannot route to these management pages.

Development Preview remains token-free. It may render the management layout for UI inspection, but it does not call production APIs or fabricate data.
