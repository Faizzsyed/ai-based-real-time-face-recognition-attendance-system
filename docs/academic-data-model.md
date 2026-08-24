# Academic data model

```text
Institution
|-- Academic Years
|-- Departments
    |-- Programs
        |-- Semesters
            |-- Class Divisions
            |-- Subjects
```

## Collections

| Entity | Collection | Important scope/uniqueness |
| --- | --- | --- |
| Institution | `institutions` | globally unique `code` |
| AcademicYear | `academic_years` | institution + name; one current year per institution |
| Department | `departments` | institution + code |
| Program | `programs` | institution + department + code |
| Semester | `semesters` | institution + program + academic year + number |
| ClassDivision | `class_divisions` | institution + year + program + semester + division |
| Subject | `subjects` | institution + program + semester + code |

All records use UTC `created_at` and `updated_at`. Production Admin creates also record `created_by`/`updated_by`, and patches record `updated_by`. Hierarchy records use `active`/`inactive`; deactivation is blocked with `RESOURCE_IN_USE` when active dependents exist. No cascade deletion or hard-delete endpoint is provided.

Setting a new current Academic Year validates the new record and safely unsets the prior current year. The partial unique index on `is_current=true` remains authoritative against concurrent writes.

## Ownership rule

Every entity except Institution stores `institution_id`, even when ownership is inferable through a parent. Parent references must resolve inside the same institution. Cross-institution references return `CROSS_INSTITUTION_REFERENCE`.

Production Admin APIs derive Institution scope from the revalidated authenticated User. They reject body-supplied `institution_id`, and every detail/update repository query includes the trusted scope. Never query tenant-owned academic resources solely by document ID.

## ObjectId and API representation

MongoDB references are stored as ObjectId values. Conversion is centralized in `backend/app/db/object_id.py`; API documents serialize ObjectIds as strings. Invalid identifiers produce the safe `VALIDATION_ERROR` contract.
