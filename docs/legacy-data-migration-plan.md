# Legacy data migration plan (not executed)

Migration must use an explicit, reviewed tool and a new-database destination. It must never run during application startup.

| Legacy collection/model | New target | Probable mappings | Required transformations/questions |
| --- | --- | --- | --- |
| Departments | `departments` | name, code, description, status | Attach verified `institution_id`; resolve duplicate codes per institution. |
| Classes | `class_divisions` | name, academicYear, semester, division, departmentId | Resolve new AcademicYear, Program, Semester IDs; remove duplicated textual relationships. |
| Subjects | `subjects` | name, code, departmentId, semester, type, credits | Resolve Program/Semester; normalize subject type and codes. |
| FacultyAssignments | Later Phase 6 model | facultyId, subjectId, classId, year | Wait for new Faculty and assignments models. |
| TimetableEntries | Later Phase 7 model | class, subject, faculty, day/time | Wait for assignments; normalize timezone and source/review state. |
| Students | Later Phase 5 model | user, roll/enrolment, class/department, profile | Define institution ownership, identity matching, consent, and photo storage migration. |
| Faculty | Later Phase 6 model | user, employee ID, department, designation | Define institution membership and cross-institution employment policy. |
| AttendanceSession/Record | Later Phase 8 model | academic references, status, counts, records | Map only after academic/student/faculty IDs; preserve audit trail and lock semantics. |

## Unresolved questions

- Which institution owns each legacy record?
- How are legacy academic-year strings mapped to date ranges?
- Which legacy classes map to which Program?
- How are duplicate codes and denormalized department names reconciled?
- What biometric consent and retention policy governs any later face-data migration?
- Which records are demo/experimental and must be excluded?

Before migration, produce read-only counts, deterministic ID mapping tables, validation reports, and a rollback plan. No migration is part of Phase 2.
