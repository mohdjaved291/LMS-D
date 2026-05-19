from django.urls import path
from .views import (
    CategoryListCreateAPIView,
    CategoryDetailAPIView,
    CourseListCreateAPIView,
    CourseDetailAPIView,
    CourseOverviewView,
    DetailedCourseOverviewView,
    TopNewCourseListAPIView,
    TopNewCourseDetailAPIView,
    TrendingCourseAPIView,
    TrendingCourseDetailAPIView,
    ReviewListCreateView,
    ReviewDetailView,
    FAQListCreateView,
    FAQDetailView,


    # Author
    AuthorDetailAPIView, AuthorListCreateAPIView,

    #Enrollment
    EnrollCourseAPIView, UserEnrollmentListAPIView, MyEnrollmentsAPIView, EnrollmentProgressUpdateView,
    CourseArchiveAPIView,

    # Razorpay Payment
    RazorpayCreateOrderView, RazorpayVerifyPaymentView,

)

urlpatterns = [
    # Categories
    path('categories/', CategoryListCreateAPIView.as_view(), name='category-list-create'),
    path('categories/<int:pk>/', CategoryDetailAPIView.as_view(), name='category-detail'),

    # Courses
    path('courses/', CourseListCreateAPIView.as_view(), name='course-list-create'),
    path('courses/<int:pk>/', CourseDetailAPIView.as_view(), name='course-detail'),
    path('course-overview/<int:course_id>/', CourseOverviewView.as_view(), name='course-overview'),
    path('courses/<int:course_id>/overview/', DetailedCourseOverviewView.as_view(), name='detailed-course-overview'),

    # Top New Courses
    path('top-new/', TopNewCourseListAPIView.as_view(), name='top-new-courses'),
    path('top-new/<int:pk>/', TopNewCourseDetailAPIView.as_view(), name='top-new-course-detail'),

    # Trending Courses
    path('trending/', TrendingCourseAPIView.as_view(), name='trending-courses'),
    path('trending/<int:pk>/', TrendingCourseDetailAPIView.as_view(), name='trending-course-detail'),

    # Reviews
    path('reviews/', ReviewListCreateView.as_view(), name='review-list-create'),
    path('reviews/<int:pk>/', ReviewDetailView.as_view(), name='review-detail'),

    # FAQs
    path('faqs/', FAQListCreateView.as_view(), name='faq-list-create'),
    path('faqs/<int:pk>/', FAQDetailView.as_view(), name='faq-detail'),

    #Authors
    path('authors/', AuthorListCreateAPIView.as_view(), name='author-list'),
    path('authors/<int:pk>/', AuthorDetailAPIView.as_view(), name='author-detail'),

    #Enrollment
    path('courses/<int:course_id>/enroll/', EnrollCourseAPIView.as_view(), name='enroll-course'),
    path('enrollments/', UserEnrollmentListAPIView.as_view(), name='user-enrollments'),
    path('enrollment/update-progress/', EnrollmentProgressUpdateView.as_view(), name='update-enrollment-progress'),

    #My Learnings
    path('my-learnings/', MyEnrollmentsAPIView.as_view(), name='my-learnings'),

    #Archive Course
    path('courses/<int:pk>/archive/',CourseArchiveAPIView.as_view(),name='course-archive'),

    # Razorpay Payment
    path('payment/create-order/', RazorpayCreateOrderView.as_view(), name='razorpay-create-order'),
    path('payment/verify/', RazorpayVerifyPaymentView.as_view(), name='razorpay-verify-payment'),
]

