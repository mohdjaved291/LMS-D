from django.contrib.auth import get_user_model, authenticate, login
from django.contrib.auth import login as auth_login
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator as token_generator
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from .permissions import IsStaff
from .models import StaffProfile,NameVerification,TwoFactorAuth
from .serializers import GoogleAuthSerializer, StaffProfileSerializer, ChangePasswordSerializer,TwoFactorAuthSerializer
from django.contrib.auth import login as django_login
from django.shortcuts import render

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    TokenSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    ResendEmailSerializer,
    AccountSettingsSerializer,
    NameVerificationSerializer
)

from django.utils import timezone
import random

User = get_user_model()

def home(request):
    return render(request,'home.html')

# Register + Send Email
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate OTP and save on user
        otp = random.randint(100000, 999999)
        user.otp = otp
        user.otp_created_at = timezone.now()
        user_email = user.email
        user.save()

        # Send OTP email
        try:
            send_mail(
                "Your OTP for Email Verification",
                f"Your OTP is: {otp}",
                'ashokpython20@gmail.com',
                [user_email],
                fail_silently=True,
            )
        except Exception as e:
            # Log the error properly (better to use logging here in real projects)
            print("Email sending failed:", e)

        return Response(
            {"detail": "Registration successful. Please check your email to verify your account."},
            status=status.HTTP_201_CREATED,
        )


# JWT Login + Active Check
class LoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data

        token_serializer = TokenSerializer(context={"user": user})
        tokens = token_serializer.validate({})
        return Response(tokens, status=status.HTTP_200_OK)


# Email Verification Link
class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        otp = request.data.get('otp')

        try:
            user = User.objects.get(otp=otp)
        except User.DoesNotExist:
            return Response({"message": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)

        expiry_time = user.otp_created_at + timezone.timedelta(minutes=10)
        if timezone.now() > expiry_time:
            return Response({"message": "OTP expired."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = True
        user.otp = None
        user.otp_created_at = None
        user.save()

        return Response({"message": "Email verified successfully. You can now login."})



# Protected Profile (JWT Required)
class UserProfileView(generics.RetrieveAPIView):
    #queryset=User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# Password Reset Request
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer=PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message':'Password reset email sent.'},status=200)
        return Response(serializer.errors,status=400)


# Password Reset Confirm
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    serializer_class=PasswordResetConfirmSerializer

    def post(self, request, uidb64, token):
        data=request.data.copy()
        data["uidb64"]=uidb64
        data["token"]=token

        serializer=self.serializer_class(data=data)

        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password has been reset successfully."})

        return Response(serializer.errors,status=400)


# Resend Email Verification
class ResendEmailVerificationView(APIView):
    permission_classes = [AllowAny]
    serializer_class=ResendEmailSerializer

    def post(self, request):
        serializer=ResendEmailSerializer(data=request.data)

        if serializer.is_valid():
            email=serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            if user.is_active:
                return Response({"message": "Email is already verified."})
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        verify_url = f"http://127.0.0.1:8000/accounts/verify-email/{uid}/{token}/"

        send_mail(
            "Verify your email",
            f"Click the link to verify your Account:\n{verify_url}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )

        return Response({"message": "Verification email resent successfully."})


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------Staff------------

class StaffListCreateAPIView(APIView):
    permission_classes = [IsAdminUser,IsStaff]

    def get(self, request):
        staff_profiles = StaffProfile.objects.filter(user__role='staff')  # updated
        serializer = StaffProfileSerializer(staff_profiles, many=True)
        return Response(serializer.data)

    def post(self, request):
        user_id = request.data.get('user')
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        if StaffProfile.objects.filter(user=user).exists():
            return Response({'error': 'Staff profile already exists for this user'}, status=400)

        data = request.data.copy()
        data['user'] = user.id
        data['role'] = 'staff'  # updated
        serializer = StaffProfileSerializer(data=data)
        if serializer.is_valid():
            serializer.save(user=user)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class StaffDetailAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get_object(self, pk, role='user__staff'):  # updated
        try:
            return StaffProfile.objects.get(pk=pk)
        except StaffProfile.DoesNotExist:
            return None

    def get(self, request, pk):
        profile = self.get_object(pk)
        if not profile:
            return Response({'error': 'Staff not found'}, status=404)
        serializer = StaffProfileSerializer(profile)
        return Response(serializer.data)

    def patch(self, request, pk):
        profile = self.get_object(pk)
        if not profile:
            return Response({'error': 'Staff not found'}, status=404)
        serializer = StaffProfileSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)

    def delete(self, request, pk):
        profile = self.get_object(pk)
        if not profile:
            return Response({'error': 'Staff not found'}, status=404)
        profile.delete()
        return Response({'message': 'staff deleted'}, status=204)
    
class AccountSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class=AccountSettingsSerializer
    permission_classes=[IsAuthenticated]

    def get_object(self):
        return self.request.user
    
# Name verification for Certificate
class NameVerificationView(generics.RetrieveUpdateAPIView):
    serializer_class=NameVerificationSerializer
    permission_classes=[IsAuthenticated]

    def get_object(self):
        obj, created=NameVerification.objects.get_or_create(user=self.request.user)
        return obj
    
# Admin approval for Name Verification
class ApproveNameVerificationView(APIView):
    permission_classes=[IsAdminUser]

    def post(self,request,user_id):
        try:
            verification=NameVerification.objects.get(user_id=user_id)
            action=request.data.get("action") # approve | reject | pending
            
            if action=="approve":
                verification.status="approved"
                verification.verified_at=timezone.now()
            elif action=="reject":
                verification.status="rejected"

            verification.save()
            return Response({"status":verification.status})
        except NameVerification.DoesNotExist:
            return Response({"error":"Request not found"}, status=404)
        
# Enable/Disable 2FA
class TwoFactorSettingsView(generics.RetrieveUpdateAPIView):
    serializer_class=TwoFactorAuthSerializer
    permission_classes=[IsAuthenticated]

    def get_object(self):
        obj,created=TwoFactorAuth.objects.get_or_create(user=self.request.user)
        return obj
    
# Send OTP (Email)
class SendOTPView(APIView):
    permission_classes=[IsAuthenticated]

    def post(self,request):
        otp=str(random.randint(100000,999999))
        request.session['2fa_otp']=otp

        send_mail(
            'Your 2FA Code',
            f'Your OTP code is {otp}',
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email],
            fail_silently=False,
        )
        return Response({"message": "OTP sent to your email"})
    
# verify OTP
class VerifyOTPView(APIView):
    permission_classes=[IsAuthenticated]

    def post(self,request):
        user_otp=request.data.get("otp")
        session_otp=request.session.get("2fa_otp")

        if user_otp==session_otp:
            return Response({"status": "verified"})
        return Response({"status": "invalid"}, status=400)