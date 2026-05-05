from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from course.models import Course, Enrollment

# 50 MB limit for assignment submissions
MAX_ASSIGNMENT_SIZE = 50 * 1024 * 1024

ALLOWED_ASSIGNMENT_FORMATS = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx']


def validate_assignment_file_size(file):
    if file.size > MAX_ASSIGNMENT_SIZE:
        raise ValidationError(f"File size must not exceed 50 MB. Your file is {file.size // (1024*1024)} MB.")


def validate_assignment_file_format(file):
    import os
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in ALLOWED_ASSIGNMENT_FORMATS:
        raise ValidationError(
            f"Unsupported file format '{ext}'. Allowed formats: {', '.join(ALLOWED_ASSIGNMENT_FORMATS)}"
        )


class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    due_date = models.DateTimeField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="created_assignments")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.course.title})"


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="submissions")
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions")
    file = models.FileField(
        upload_to="assignments/",
        validators=[validate_assignment_file_size, validate_assignment_file_format]
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    grade = models.CharField(max_length=10, blank=True, null=True)  # e.g. A, B, C, Pass/Fail

    class Meta:
        unique_together = ('assignment', 'student')  # One submission per student per assignment

    def __str__(self):
        return f"{self.student.email} - {self.assignment.title}"
