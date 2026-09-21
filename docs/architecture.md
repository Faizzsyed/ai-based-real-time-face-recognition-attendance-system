# Architecture

## Overview
The AI Based Real-Time Face Recognition Attendance System is built using a modern, decoupled architecture.

### Backend (FastAPI + MongoDB)
- **Framework**: FastAPI (Python 3.11+)
- **Database**: MongoDB (tenant-isolated collections via `institution_id`)
- **Authentication**: JWT-based access tokens with refresh token rotation and Argon2id password hashing.
- **Biometrics Engine**: YuNet for face detection and SFace for embedding extraction. Facial features are encrypted at rest using AES.

### Frontend (Flet)
- **Framework**: Flet (Flutter for Python)
- **Platforms**: Desktop (Windows/Mac/Linux) and Mobile (Android).
- **Desktop Biometrics**: Native Python OpenCV is used for live webcam access. MediaPipe is used for client-side development-grade challenge-response liveness.
- **Android Biometrics**: Native camera and live liveness are intentionally disabled on mobile due to Python package limitations (OpenCV/MediaPipe unsupported dynamically). Android utilizes a native photo picker, which uploads images to the backend for processing.

## Core Modules
1. **Auth & Identity**: RBAC (Admin, Faculty, Student) enforcing tenant isolation.
2. **Academic Core**: Institutions, Departments, Programs, Semesters, Subjects, Class Divisions.
3. **Timetable & Attendance**: Faculty assignments and schedule-based attendance sessions.
4. **Biometrics**: Face enrollment and AI-assisted real-time attendance tracking.
5. **Workflows**: Requests, Notifications, and Audit logging.

## Concurrency and Scaling
The backend relies on MongoDB's atomic operators (e.g., `$set`, `$inc`, `find_one_and_update`) to prevent stale-state race conditions during attendance submittal and enrollment validation.
