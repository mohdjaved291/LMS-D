import hmac
import hashlib
import razorpay
from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta, datetime
from django.db.models import Avg
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from accounts.permissions import IsAdmin, IsStaff
from content.models import Video, Syllabus, LiveSession
from content.serializers import VideoMiniSerializer, SyllabusWithVideosSerializer, LiveSessionSerializer
from progress.models import VideoProgress
from progress.serializers import SyllabusProgressDetailSerializer
from .models import Category, Course, Review, FAQ, Enrollment, Author
from .permissions import canArchiveCourse, canDeleteCourse, IsCourseManager, IsAdminUser
from .serializers import (
    CategorySerializer,
    CourseDetailSerializer,
    CourseFilterSerializer,
    CourseOverviewSerializer,
    ReviewSerializer,
    CreateReviewSerializer,
    FAQSerializer,
    CreateFAQSerializer,
    EnrollmentSerializer,
    AuthorSerializer,
    EnrollmentProgressUpdateSerializer,
    CourseListSerializer,
)
from .utils import is_user_enrolled


User = get_user_model()

# ---------------- CATEGORY VIEWS ----------------

class CategoryListCreateAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        categories = Category.objects.all()
        data = []
        for category in categories:
            serializer = CategorySerializer(category)
            category_data = serializer.data
            category_data['course_count'] = category.courses.count()
            data.append(category_data)
        return Response(data)

    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CategoryDetailAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CategorySerializer(category)
        data = serializer.data
        data['course_count'] = category.courses.count()
        return Response(data)

    def put(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CategorySerializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        category = Category.objects.get(pk=pk)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        try:
            category = Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TopNewCourseListAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        thirty_days_ago = timezone.now() - timedelta(days=30)
        courses = Course.objects.annotate(avg_rating=Avg('reviews__rating')).filter(
            created_at__gte=thirty_days_ago, avg_rating__gte=4
        ).order_by('-avg_rating')

        serializer = CourseFilterSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TopNewCourseDetailAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get_object(self, pk):
        try:
            return Course.objects.get(pk=pk)
        except Course.DoesNotExist:
            return None

    def get(self, request, pk):
        course = self.get_object(pk)
        if not course:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CourseDetailSerializer(course)
        return Response(serializer.data)

    def put(self, request, pk):
        course = self.get_object(pk)
        if not course:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CourseDetailSerializer(course, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        course = self.get_object(pk)
        if not course:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CourseDetailSerializer(course, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        course = self.get_object(pk)
        if not course:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        course.delete()
        return Response({'detail': 'Course deleted successfully'}, status=204)

# ---------------- TRENDING COURSES ----------------

class TrendingCourseAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        trending_courses = Course.objects.filter(is_trending=True).annotate(
            avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
        serializer = CourseFilterSerializer(trending_courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TrendingCourseDetailAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def get_object(self, pk):
        try:
            return Course.objects.get(pk=pk, is_trending=True)
        except Course.DoesNotExist:
            return None

    def get(self, request, pk):
        course = self.get_object(pk)
        if not course:
            return Response({'error': 'Trending course not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CourseDetailSerializer(course, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

# ---------------- REVIEW VIEWS ----------------

class ReviewListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Review.objects.all()
        course_id = self.request.query_params.get('course_id')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        return queryset

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateReviewSerializer
        return ReviewSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_update(self, serializer):
        if serializer.instance.user != self.request.user:
            raise PermissionDenied("You can only update your own reviews")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user != self.request.user:
            raise PermissionDenied("You can only delete your own reviews")
        instance.delete()

# ---------------- FAQ VIEWS ----------------

class FAQListCreateView(generics.ListCreateAPIView):
    queryset = FAQ.objects.filter(is_active=True).order_by('-created_at')
    serializer_class = FAQSerializer
    permission_classes = [permissions.AllowAny]

class FAQDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    permission_classes = [permissions.AllowAny]

# ---------------- COURSE VIEWS ----------------

class CourseListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        courses = Course.objects.filter(is_archived=False)
        serializer = CourseListSerializer(courses, many=True, context={'request': request})
        return Response(serializer.data, status=200)

    def post(self, request):
        if not IsCourseManager().has_permission(request, self) and not IsAdminUser().has_permission(request,self):
            return Response({'error': 'You do not have permission to create courses.'}, status=403)

        serializer = CourseDetailSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            course = serializer.save(created_by=request.user)
            return Response(CourseDetailSerializer(course, context={'request': request}).data, status=201)
        return Response(serializer.errors, status=400)

class CourseDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        return get_object_or_404(Course, pk=pk)

    def get(self, request, pk):
        course = self.get_object(pk)

        # user = request.user

        # if user.is_authenticated and hasattr(user, 'role') and user.role == 'student':
        #     if not is_user_enrolled(user, course):
        #         return Response({'detail': 'Access denied. You are not enrolled in this course.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = CourseDetailSerializer(course, context={'request': request})
        return Response(serializer.data)

    def put(self, request, pk):
        course = self.get_object(pk)
        if not IsCourseManager().has_permission(request, self) and not IsAdminUser().has_permission(request,self):
            return Response({'error': 'You do not have permission to edit courses.'}, status=403)

        serializer = CourseDetailSerializer(course, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def patch(self, request, pk):
        course = self.get_object(pk)
        if not IsCourseManager().has_permission(request, self) and not IsAdminUser().has_permission(request,self):
            return Response({'error': 'You do not have permission to edit courses.'}, status=403)

        serializer = CourseDetailSerializer(course, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        course = self.get_object(pk)
        if not canDeleteCourse().has_object_permission(request, self, course):
            return Response({'error': 'You are not allowed to delete this course.'}, status=403)

        course.delete()
        return Response({'detail': 'Course deleted successfully'}, status=204)

class CourseOverviewView(generics.ListAPIView):
    serializer_class = SyllabusProgressDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        course_id = self.kwargs['course_id']
        user = self.request.user

        course = get_object_or_404(Course, id=course_id)

        if user.role == 'student':
            enrollment = Enrollment.objects.filter(user=user, course=course).exists()
            if not enrollment:
                raise PermissionDenied("You are not enrolled in this course.")

        return Syllabus.objects.filter(course=course).order_by('order')

class DetailedCourseOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)

        is_staff = user.is_staff or user.is_superuser
        is_enrolled = Enrollment.objects.filter(user=user, course=course).exists()
        if not is_staff and not is_enrolled:
            return Response({"detail": "You are not enrolled in this course."}, status=status.HTTP_403_FORBIDDEN)

        course_data = CourseOverviewSerializer(course, context={"request": request}).data

        last_progress = VideoProgress.objects.filter(student=user, video__course=course).order_by('-last_watched_on').first()
        current_video = last_progress.video if last_progress else Video.objects.filter(course=course).first()
        current_video_data = VideoMiniSerializer(current_video).data if current_video else None

        all_videos = list(Video.objects.filter(course=course).order_by('id'))
        try:
            index = all_videos.index(current_video)
            next_video = all_videos[index + 1] if index + 1 < len(all_videos) else None
        except Exception:
            next_video = None
        next_video_data = VideoMiniSerializer(next_video).data if next_video else None

        syllabus = Syllabus.objects.filter(course=course).prefetch_related('videos')
        syllabus_data = SyllabusWithVideosSerializer(syllabus, many=True).data

        now = datetime.now()
        live_sessions = LiveSession.objects.filter(batch__batch_specific_course=course, start_time__gte=now).order_by('start_time')
        live_sessions_data = LiveSessionSerializer(live_sessions, many=True).data

        return Response({
            "course": course_data,
            "current_video": current_video_data,
            "next_video": next_video_data,
            "syllabus": syllabus_data,
            "live_sessions": live_sessions_data
        })

# Enroll in a course
class EnrollCourseAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        user = request.user

        if Enrollment.objects.filter(user=user, course=course).exists():
            return Response({'detail': 'Already enrolled in this course.'}, status=status.HTTP_400_BAD_REQUEST)

        enrollment = Enrollment.objects.create(user=user, course=course)
        serializer = EnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# List of Enrollments for the currently logged-in user ("My Learnings")
class MyEnrollmentsAPIView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Enrollment.objects.filter(user=self.request.user).select_related('course', 'last_watched_video')

# List enrolled courses for the admin and staff
class UserEnrollmentListAPIView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [IsAdmin | IsStaff]

    def get_queryset(self):
        if self.request.user.role in ['admin', 'staff']:
            return Enrollment.objects.select_related('course', 'user').all()
        raise PermissionDenied("Only staff or admin can view enrollments.")

# To update a student's progress in a course they are enrolled in.
class EnrollmentProgressUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = EnrollmentProgressUpdateSerializer(data=request.data, context={'request': request})

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response({"message": "Enrollment progress updated"}, status=status.HTTP_200_OK)

# ---------------- AUTHOR VIEWS ----------------

class AuthorListCreateAPIView(generics.ListCreateAPIView):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [permissions.AllowAny]

class AuthorDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = [permissions.AllowAny]

class CourseArchiveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        course = get_object_or_404(Course, pk=pk)
        if not canArchiveCourse().has_object_permission(request, self, course):
            return Response({'error': 'You are not allowed to archive this course.'}, status=403)

        course.is_archived = True
        course.save()
        return Response({'message': 'Course archived successfully.'})


# -------- Razorpay Payment Views --------

class RazorpayCreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get('amount')
        course_id = request.data.get('course_id')

        if not amount or not course_id:
            return Response({'error': 'amount and course_id are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response({'error': 'Razorpay is not configured on the server.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            order = client.order.create({
                'amount': int(float(amount)) * 100,
                'currency': 'INR',
                'notes': {'course_id': str(course_id)},
            })
            return Response({
                'order_id': order['id'],
                'amount': order['amount'],
                'currency': order['currency'],
                'key': settings.RAZORPAY_KEY_ID,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RazorpayVerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get('razorpay_payment_id')
        order_id = request.data.get('razorpay_order_id')
        signature = request.data.get('razorpay_signature')
        course_id = request.data.get('course_id')

        if not all([payment_id, order_id, signature, course_id]):
            return Response({'error': 'Missing required payment fields.'}, status=status.HTTP_400_BAD_REQUEST)

        # Verify Razorpay signature
        body = f'{order_id}|{payment_id}'.encode()
        expected_signature = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if expected_signature != signature:
            return Response({'error': 'Payment verification failed. Invalid signature.'}, status=status.HTTP_400_BAD_REQUEST)

        # Enroll the student in the course
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)

        enrollment, created = Enrollment.objects.get_or_create(
            user=request.user,
            course=course,
        )

        return Response({
            'success': True,
            'enrolled': created,
            'payment_id': payment_id,
            'message': 'Payment verified and enrollment successful.' if created else 'Already enrolled.',
        })
