from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator as token_generator
from django.core.mail import send_mail
from django.conf import settings
import requests
from django.core.exceptions import ValidationError as DjangoValidationError
import random
from django.utils import timezone

from accounts.models import StaffProfile,NameVerification,TwoFactorAuth

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id","full_name","email","phone_number","date_of_birth", "role",]

class RegisterSerializer(serializers.ModelSerializer):
    confirm_password=serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["full_name","email","phone_number","date_of_birth", "role", "password","confirm_password"]
        extra_kwargs = {"password": {"write_only": True}}

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages)
        return value
    
    def validate(self,attrs):
        if attrs["password"]!=attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password":"Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("confirm_password")

        otp = random.randint(100000, 999999)
        user = User.objects.create_user(
            full_name=validated_data["full_name"],
            email=validated_data["email"],
            phone_number=validated_data["phone_number"],
            date_of_birth=validated_data["date_of_birth"],
            password=validated_data["password"],
            role=validated_data.get("role", "student"),
            is_active=False,
            otp=otp,
            otp_created_at=timezone.now(),
        )

        # Send email verification
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)

        try:
            send_mail(
            "Your OTP for Email Verification",
            f"Your OTP is: {otp}",
            'ashokpython20@gmail.com',
            [user.email],
            fail_silently=False,
            )
        except Exception as e:
            # Log the error properly
            print("Email sending failed:", e)

        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")
        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_active:
            raise serializers.ValidationError("Email not verified. Please check your inbox.")

        return user

class TokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()

    def validate(self, data):
        user = self.context["user"]
        refresh = RefreshToken.for_user(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}

#  Google Sign-In Serializer
class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, data):
        token = data.get("token")
        response = requests.get(f"https://oauth2.googleapis.com/tokeninfo?id_token={token}")
        if response.status_code != 200:
            raise serializers.ValidationError("Invalid Google token")

        user_info = response.json()
        email = user_info.get("email")
        full_name = user_info.get("given_name", "")

        user, created = User.objects.get_or_create(email=email, defaults={
            "full_name": full_name,
            "is_active": True,
        })

        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

#  Password Reset Request Serializer
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user with this email.")
        return value

    def save(self):
        email = self.validated_data["email"]
        user = User.objects.get(email=email)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        reset_url = f"http://127.0.0.1:8000/accounts/password-reset-confirm/{uid}/{token}/"

        send_mail(
            "Reset Your Password",
            f"Click the link to reset your password:\n\n{reset_url}",
            'ashokpython20@gmail.com',
            [user.email],
            fail_silently=False,
        )

#  Password Reset Confirm Serializer
class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(min_length=6, write_only=True)
    confirm_password=serializers.CharField(min_length=6,write_only=True)
    uidb64=serializers.CharField()
    token=serializers.CharField()

    def validate(self, data):
        if data["new_password"]!=data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match.")
        
        try:
            uid = force_str(urlsafe_base64_decode(data["uidb64"]))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError("Invalid user.")

        if not token_generator.check_token(user, data["token"]):
            raise serializers.ValidationError("Invalid or expired token.")

        self.user = user
        return data

    def save(self):
        password = self.validated_data["new_password"]
        self.user.set_password(password)
        self.user.save()

class ResendEmailSerializer(serializers.Serializer):
    email=serializers.EmailField()


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'full_name']

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_new_password = serializers.CharField(required=True)

    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({"confirm_new_password": "New passwords do not match."})
        try:
            validate_password(data['new_password'], self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"new_password": e.messages})
        return data

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


# ------------------Staff Profile---------------------------

class StaffProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = StaffProfile
        fields = '__all__'

# ----------- Account settings ------------------------------
class AccountSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model=User
        fields=['id','full_name','email','time_zone','language']
        read_only_fields=['email']

# -------- Name verification for certificates -----------------
class NameVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model=NameVerification
        fields=['legal_name','status','verified_at']
        read_only_fields=['status','verified_at']

# ------- Two Factor Authentication --------------------
class TwoFactorAuthSerializer(serializers.ModelSerializer):
    class Meta:
        model=TwoFactorAuth
        fields=['is_enabled']
        read_only_fields=[]