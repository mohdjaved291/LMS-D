from django.utils import timezone
from rest_framework import serializers
from .models import Review, FAQ, Category, Course, Author, Enrollment, LearningPoint, CourseInclusion, CourseSection
from django.contrib.auth import get_user_model
from django.db.models import Avg
from content.serializers import VideoMiniSerializer, VideoSerializer
from content.models import Video
from progress.models import SyllabusProgress
from progress.serializers import SyllabusProgressSerializer
from progress.utils import calculate_course_progress_percent
from batch.serializers import BatchMiniSerializer
from batch.models import BatchStudent


User = get_user_model()

class CourseMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'title']

# ---------- Category ----------
class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        exclude = ["created_at"]

    def validate_name(self, value):
        if Category.objects.filter(name=value).exists():
            raise serializers.ValidationError("Category name must be unique.")
        return value

# ---------- Author ----------
class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ['id', 'name', 'bio', 'image', 'organization']

class CourseFilterSerializer(serializers.ModelSerializer):
    rating = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    special_tag = serializers.SerializerMethodField()
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Course
        fields = [
            'id',
            'title',
            'thumbnail',
            'author',
            'duration',
            'original_price',
            'discounted_price',
            'rating',
            'rating_count',
            'special_tag'
        ]

    def get_rating(self, obj):
        avg_rating = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg_rating or 0, 1)

    def get_rating_count(self, obj):
        return obj.reviews.count()

    def get_special_tag(self, obj):
        tag = obj.get_special_tag_display()
        return tag if obj.special_tag != 'none' else None


class CourseOverviewSerializer(serializers.ModelSerializer):
    videos = serializers.SerializerMethodField()
    syllabus_progress = serializers.SerializerMethodField()
    syllabus = serializers.SerializerMethodField()      # Full chapter-wise structure (modules with videos).
    current_video = serializers.SerializerMethodField() # Last watched video by the student.
    next_video = serializers.SerializerMethodField()    # The next unwatched video in the course.
    live_sessions = serializers.SerializerMethodField() # All sessions related to the course.

    class Meta:
        model = Course
        fields = ['id', 'title', 'description', 'videos', 'syllabus_progress', 'syllabus', 'current_video', 'next_video', 'live_sessions']

    def get_videos(self, obj):
        videos = Video.objects.filter(course=obj)
        return VideoSerializer(videos, many=True).data

    def get_syllabus_progress(self, obj):
        user = self.context['request'].user
        try:
            progress = SyllabusProgress.objects.get(syllabus__course=obj, student=user)
            return SyllabusProgressSerializer(progress).data
        except SyllabusProgress.DoesNotExist:
            return None

    def get_syllabus(self, obj):
        from content.models import Syllabus
        from content.serializers import SyllabusWithVideosSerializer
        syllabus_qs = Syllabus.objects.filter(course=obj).prefetch_related('videos')
        return SyllabusWithVideosSerializer(syllabus_qs, many=True).data

    def get_current_video(self, obj):
        user = self.context['request'].user
        from progress.models import VideoProgress
        vp = VideoProgress.objects.filter(video__course=obj, student=user).order_by('-last_watched_on').first()
        if vp:
            return VideoSerializer(vp.video).data
        return None

    def get_next_video(self, obj):
        user = self.context['request'].user
        all_videos = Video.objects.filter(course=obj).order_by('id')
        from progress.models import VideoProgress
        watched = VideoProgress.objects.filter(student=user, video__in=all_videos, is_completed=True).values_list('video_id', flat=True)
        next_video = all_videos.exclude(id__in=watched).first()
        if next_video:
            return VideoSerializer(next_video).data
        return None

    def get_live_sessions(self, obj):
        from content.models import LiveSession
        from content.serializers import LiveSessionSerializer
        return LiveSessionSerializer(LiveSession.objects.filter(batch__batch_specific_course=obj), many=True).data


# ---------- User ----------
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', "full_name"]

# ---------- Review ----------
class ReviewSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ['id', 'user', 'course', 'rating', 'feedback']
        read_only_fields = ['created_at', 'updated_at']

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5")
        return value

class CreateReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ['course', 'rating', 'feedback']

    def validate(self, data):
        user = self.context['request'].user
        course = data['course']
        if Review.objects.filter(user=user, course=course).exists():
            raise serializers.ValidationError("You have already reviewed this course")
        return data

# ---------- FAQ ----------

class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer']
        read_only_fields = ['created_at']

class CreateFAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['question', 'answer']

#----course specific-----
class LearningPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningPoint
        fields = ['point']

class CourseInclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseInclusion
        fields = ['item']

class CourseSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseSection
        fields = ['title', 'description', 'file']

class CourseDetailSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field='name', queryset=Category.objects.all())
    author = AuthorSerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(source='author', queryset=Author.objects.all(), write_only=True)

    learning_points = LearningPointSerializer(many=True, required=True)
    inclusions = CourseInclusionSerializer(many=True, required=True)
    sections = CourseSectionSerializer(many=True, required=True)

    reviews = ReviewSerializer(many=True, read_only=True)
    faqs = FAQSerializer(many=True, read_only=True)

    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    special_tag = serializers.ChoiceField(choices=Course.BADGE_CHOICES,default='none')
    is_enrolled = serializers.SerializerMethodField()
    is_discount_active = serializers.SerializerMethodField()
    discount_days_left_text = serializers.SerializerMethodField()

    class Meta:
        model = Course
        exclude = ['created_at', 'updated_at']

    def create(self, validated_data):
        learning_points_data = validated_data.pop('learning_points')
        inclusions_data = validated_data.pop('inclusions')
        sections_data = validated_data.pop('sections')

        course = Course.objects.create(**validated_data)

        for point_data in learning_points_data:
            LearningPoint.objects.create(course=course, **point_data)
        for item_data in inclusions_data:
            CourseInclusion.objects.create(course=course, **item_data)
        for section_data in sections_data:
            CourseSection.objects.create(course=course, **section_data)

        return course

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        # Optional: handle updating nested fields if needed (e.g., sections, inclusions)
        return instance

    def get_average_rating(self, obj):
        avg_rating = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg_rating or 0, 1)

    def get_review_count(self, obj):
        return obj.reviews.count()

    #def get_special_tag(self, obj):
    #    return obj.get_special_tag_display() if hasattr(obj, 'get_special_tag_display') else None

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Enrollment.objects.filter(user=request.user, course=obj).exists()
        return False

    def get_is_discount_active(self, obj):
        return obj.discount_end_date and obj.discount_end_date >= timezone.now()

    def get_discount_days_left_text(self, obj):
        if obj.discount_end_date:
            days_left = (obj.discount_end_date - timezone.now()).days
            return f"{days_left} day(s) left" if days_left >= 0 else "Expired"
        return ""
    
    # Add display name in output
    def to_representation(self,instance):
        data=super().to_representation(instance)
        data['special_tag_display']=instance.get_special_tag_display()
        return data

#-----Enrollment-----
class EnrollmentSerializer(serializers.ModelSerializer):
    course = CourseFilterSerializer(read_only=True)
    user = UserSerializer(read_only=True)
    last_watched_video = VideoMiniSerializer(read_only=True)
    batch = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = ['id', 'user', 'course', 'batch', 'enrolled_at', 'progress_percent', 'last_watched_video']

    def get_batch(self, obj):
        batch_student = BatchStudent.objects.filter(
            student=obj.user,
            batch__batch_specific_course=obj.course,
            batch__is_archived=False,
        ).select_related('batch').first()
        return BatchMiniSerializer(batch_student.batch).data if batch_student else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Dynamically calculate progress
        data['progress_percent'] = calculate_course_progress_percent(
            user=instance.user,
            course=instance.course
        )
        return data

# Updating the progress of a student enrolled in a course.
class EnrollmentProgressUpdateSerializer(serializers.Serializer):
    enrollment = serializers.IntegerField()
    progress_percent = serializers.FloatField(min_value=0, max_value=100)
    last_watched_video = serializers.IntegerField()

    def validate(self, attrs):
        request = self.context['request']
        user = request.user
        enrollment_id = attrs.get('enrollment')
        video_id = attrs.get('last_watched_video')

        if user.is_superuser or (getattr(user, 'role', None) in ['admin', 'staff']):
            try:
                enrollment = Enrollment.objects.get(id=enrollment_id)
            except Enrollment.DoesNotExist:
                raise serializers.ValidationError("Enrollment not found or unauthorized.")

        else:
            try:
                enrollment = Enrollment.objects.get(id=enrollment_id, user=user)
            except Enrollment.DoesNotExist:
                raise serializers.ValidationError("Enrollment not found or unauthorized.")

        course = enrollment.course

        try:
            video = Video.objects.get(id=video_id, course=course)
        except Video.DoesNotExist:
            raise serializers.ValidationError("Video not found in the enrolled course.")

        attrs['enrollment'] = enrollment
        attrs['video'] = video
        return attrs

    def save(self, **kwargs):
        enrollment = self.validated_data['enrollment']
        video = self.validated_data['video']
        progress_percent = self.validated_data['progress_percent']

        enrollment.progress_percent = progress_percent
        enrollment.last_watched_video = video
        enrollment.save()
        return enrollment

    enrolled_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Enrollment
        fields = ['id', 'user', 'course', 'enrolled_at']

class CourseListSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field='name', read_only=True)
    author = AuthorSerializer(read_only=True)
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    is_discount_active = serializers.SerializerMethodField()
    discount_days_left_text = serializers.SerializerMethodField()
    special_tag = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'thumbnail',
            'original_price', 'discounted_price', 'discounted_percentage',
            'is_discount_active', 'discount_days_left_text',
            'category', 'author',
            'average_rating', 'review_count',
            'special_tag', "is_archived",
        ]

    def get_average_rating(self, obj):
        avg_rating = obj.reviews.aggregate(avg=Avg('rating'))['avg']
        return round(avg_rating or 0, 1)

    def get_review_count(self, obj):
        return obj.reviews.count()

    def get_is_discount_active(self, obj):
        return obj.discount_end_date and obj.discount_end_date >= timezone.now()

    def get_discount_days_left_text(self, obj):
        if obj.discount_end_date:
            days_left = (obj.discount_end_date - timezone.now()).days
            return f"{days_left} day(s) left" if days_left >= 0 else "Expired"
        return ""

    def get_special_tag(self, obj):
        return obj.get_special_tag_display() if hasattr(obj, 'get_special_tag_display') else None