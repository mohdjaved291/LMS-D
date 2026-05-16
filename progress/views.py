from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from batch.models import Batch
from content.serializers import VideoSerializer
from course.models import Course, Enrollment
from .models import VideoProgress, SyllabusProgress
from content.models import Video, Syllabus
from .serializers import VideoProgressSerializer, SyllabusProgressSerializer, SyllabusProgressDetailSerializer


class VideoProgressListView(generics.ListAPIView):
    serializer_class = VideoProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = VideoProgress.objects.filter(student=self.request.user)
        video_id = self.request.query_params.get('video')
        if video_id:
            queryset = queryset.filter(video_id=video_id)
        return queryset

class UpdateVideoProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        video_id = request.data.get("video_id")
        watched_seconds = request.data.get("watched_seconds")

        if not video_id or watched_seconds is None:
            return Response({"error": "Missing video_id or watched_seconds."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            video = Video.objects.get(id=video_id)
        except Video.DoesNotExist:
            return Response({"error": "Video not found."}, status=status.HTTP_404_NOT_FOUND)

        progress, created = VideoProgress.objects.get_or_create(
            student=user,
            video=video,
            defaults={'watched_seconds': watched_seconds}
        )

        if not created:
            progress.watched_seconds = max(progress.watched_seconds, int(watched_seconds))
            progress.last_watched_on = timezone.now()

        if progress.watched_seconds >= int(video.duration * 0.9):
            progress.is_completed = True

        progress.save()
        return Response({"message": "Progress updated successfully."}, status=status.HTTP_200_OK)

class SyllabusProgressListView(generics.ListAPIView):
    serializer_class = SyllabusProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return SyllabusProgress.objects.filter(student=self.request.user)

class CourseSyllabusProgressListView(generics.ListAPIView):
    serializer_class = SyllabusProgressDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        course_id = self.request.query_params.get('course_id')
        if not course_id:
            return Syllabus.objects.none()
        return Syllabus.objects.filter(course_id=course_id).order_by('order')

class UpdateSyllabusProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        syllabus_id = request.data.get("syllabus_id")
        is_completed = request.data.get("is_completed", False)

        if not syllabus_id:
            return Response({"error": "Missing syllabus_id."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            syllabus = Syllabus.objects.get(id=syllabus_id)
        except Syllabus.DoesNotExist:
            return Response({"error": "Syllabus not found."}, status=status.HTTP_404_NOT_FOUND)

        progress, created = SyllabusProgress.objects.get_or_create(
            student=user,
            syllabus=syllabus,
        )

        # Auto calculate progress percent based on video completion
        total_videos = syllabus.videos.count()
        if total_videos > 0:
            completed_videos = syllabus.videos.filter(
                videoprogress__student=user,
                videoprogress__is_completed=True
            ).count()
            progress.progress_percent = int((completed_videos / total_videos) * 100)
        else:
            progress.progress_percent = 0

        # Mark syllabus complete if all videos are done
        if progress.progress_percent == 100 or is_completed in [True, 'true', 'True', 1, '1']:
            progress.is_completed = True
            progress.completed_on = timezone.now()
            progress.progress_percent = 100
        else:
            progress.is_completed = False
            progress.completed_on = None

        progress.save()

        return Response({
            "message": "Syllabus progress updated.",
            "progress_percent": progress.progress_percent,
            "is_completed": progress.is_completed
        }, status=status.HTTP_200_OK)


class NextVideoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)

        try:
            enrollment = Enrollment.objects.get(user=user, course=course)
        except Enrollment.DoesNotExist:
            return Response({'detail': 'Not enrolled in this course.'}, status=status.HTTP_403_FORBIDDEN)

        # Fetch all videos in order
        videos = Video.objects.filter(course=course).order_by('id')

        for video in videos:
            progress = VideoProgress.objects.filter(student=user, video=video).first()
            if not progress or not progress.is_completed:
                serializer = VideoSerializer(video)
                return Response({
                    "next_video": serializer.data,
                    "video_id": video.id,
                })

        return Response({"detail": "You've completed all videos in this course."}, status=status.HTTP_200_OK)


class PreviousVideoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)

        try:
            enrollment = Enrollment.objects.get(user=user, course=course)
        except Enrollment.DoesNotExist:
            return Response({'detail': 'Not enrolled in this course.'}, status=status.HTTP_403_FORBIDDEN)

        last_video = enrollment.last_watched_video

        if not last_video:
            return Response({'detail': 'No previous video available.'}, status=status.HTTP_404_NOT_FOUND)

        all_videos = Video.objects.filter(course=course).order_by('id')
        previous_video = all_videos.filter(id__lt=last_video.id).last()

        if not previous_video:
            return Response({'detail': 'No previous video available.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = VideoSerializer(previous_video)
        return Response(serializer.data)

class CurrentVideoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)

        try:
            enrollment = Enrollment.objects.get(user=user, course=course)
        except Enrollment.DoesNotExist:
            return Response({'detail': 'Not enrolled in this course.'}, status=status.HTTP_403_FORBIDDEN)

        current_video = enrollment.last_watched_video

        if not current_video:
            return Response({'detail': 'No video watched yet.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = VideoSerializer(current_video)
        return Response(serializer.data)


# Adding Batch-Wise Syllabus Progress
class BatchSyllabusProgressListView(generics.ListAPIView):
    serializer_class = SyllabusProgressDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        batch_id = self.request.query_params.get('batch_id')
        if not batch_id:
            return Syllabus.objects.none()

        try:
            batch = Batch.objects.get(id=batch_id)
        except Batch.DoesNotExist:
            return Syllabus.objects.none()

        return Syllabus.objects.filter(course=batch.batch_specific_course).order_by('order')

