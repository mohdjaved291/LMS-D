# LMS Backend — Django REST Framework

A RESTful API backend for a Learning Management System supporting students, staff, and admin roles with third-party integrations for payments and video hosting.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| Framework | Django 5.2 + Django REST Framework |
| Authentication | JWT via `djangorestframework-simplejwt` |
| Database | SQLite (development) |
| Payment | Razorpay |
| Video | Vimeo (ID-based embedding) |
| File Storage | Local (`media/`) |
| CORS | `django-cors-headers` |
| Static Files | WhiteNoise |

---

## Project Structure

```
LMS-D/
├── accounts/        # User auth, roles, 2FA, Google OAuth
├── course/          # Courses, enrollment, Razorpay payment
├── batch/           # Batches, student/staff assignment
├── content/         # Videos, live sessions, syllabus, modules
├── progress/        # Video and syllabus progress tracking
├── assignment/      # Assignments and student submissions
├── quiz/            # Quizzes
├── announcements/   # Announcements portal
├── notifications/   # Notification system
├── chats/           # Batch-level chat
├── myprofile/       # Student profile management
├── lms/             # Project config (settings.py, urls.py)
├── requirements.txt
├── manage.py
└── .gitignore
```

---

## Setup

### Prerequisites
- Python 3.12
- pip

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd LMS-D

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

Server runs at `http://127.0.0.1:8000`

---

## Environment Variables

Create a `.env` file or set these in your terminal before running the server:

```bash
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
```

> Never commit real credentials. Use test keys from [Razorpay Dashboard](https://dashboard.razorpay.com) during development.

---

## API Endpoints

### Authentication
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/register/` | Register new user | No |
| POST | `/login/` | Login, returns JWT tokens | No |
| POST | `/verify-email/` | Verify email via OTP | No |
| POST | `/google-login/` | Login with Google token | No |
| POST | `/token/refresh/` | Refresh access token | No |
| POST | `/password-reset/` | Request password reset | No |
| GET | `/profile/` | Get current user profile | Yes |
| PATCH | `/account-settings/` | Update account settings | Yes |
| POST | `/change-password/` | Change password | Yes |

### Courses
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/courses/courses/` | List all courses | No |
| GET | `/courses/courses/<id>/` | Course detail | No |
| GET | `/courses/my-learnings/` | Student enrolled courses | Yes |
| POST | `/courses/courses/<id>/enroll/` | Enroll in course | Yes |
| GET | `/courses/categories/` | List categories | No |

### Payment
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/courses/payment/create-order/` | Create Razorpay order | Yes |
| POST | `/courses/payment/verify/` | Verify payment + enroll student | Yes |

### Batches
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/batches/` | List batches | Yes |
| GET | `/batches/<id>/` | Batch detail | Yes |

### Content
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/content/videos/` | List videos (filter: `?course=<id>`) | Yes |
| GET | `/content/videos/<id>/` | Video detail | Yes |
| GET | `/content/livesessions/` | List live sessions (filter: `?batch=<id>`) | Yes |
| GET | `/content/syllabus-with-videos/<course_id>/` | Course syllabus with videos | Yes |

### Progress
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/progress/my-progress/` | Get all video progress for current user | Yes |
| POST | `/progress/update-video-progress/` | Save video watch progress | Yes |
| GET | `/progress/my-syllabus-progress/` | Get syllabus completion status | Yes |

### Assignments
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/api/assignment/` | List assignments | Yes |
| POST | `/api/assignment/submit/` | Submit assignment file | Yes |

### Announcements
| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| GET | `/announcements/` | List announcements for current user | Yes |
| POST | `/announcements/` | Create announcement (admin/staff) | Yes |

---

## User Roles

| Role | Access |
|------|--------|
| `admin` | Full access to all endpoints and Django admin panel |
| `staff` | Access to assigned batches, content management |
| `student` | Access to enrolled courses, own progress, announcements |

---

## File Upload Limits

| Type | Max Size | Allowed Formats |
|------|----------|----------------|
| Assignment submission | 50 MB | `.pdf`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx` |
| Recorded video | 500 MB | `.mp4`, `.mov`, `.avi` |

---

## Django Admin

Access the admin panel at `http://127.0.0.1:8000/admin/` with superuser credentials.

Use the admin panel to:
- Create and manage users
- Add courses, batches, and videos
- Set `vimeo_video_id` on video records
- Create live sessions with Zoom/Google Meet links
- Post announcements

---

## Running Tests

```bash
python manage.py test
```

---

## Default Admin Credentials (Development)

```
Email:    admin@gmail.com
Password: admin123
```

> Change these immediately in any non-local environment.