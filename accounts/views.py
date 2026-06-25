from django.contrib.auth import authenticate
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse, inline_serializer

from .serializers import LoginSerializer, RegisterSerializer


@extend_schema(
    summary="Register a new user",
    description="Registers a new user account and returns JWT access and refresh tokens.",
    request=RegisterSerializer,
    responses={
        201: inline_serializer(
            name="RegisterSuccessResponse",
            fields={
                "id": serializers.IntegerField(),
                "username": serializers.CharField(),
                "token": serializers.CharField(help_text="JWT Access Token"),
                "refresh": serializers.CharField(help_text="JWT Refresh Token"),
            }
        ),
        400: OpenApiResponse(description="Validation error (invalid data or username/email already exists)")
    }
)
class RegisterView(APIView):
    """POST /api/auth/register - create a new user account."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response({
            'id': user.id,
            'username': user.username,
            'token': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="User Login",
    description="Authenticates credentials and returns JWT access and refresh tokens.",
    request=LoginSerializer,
    responses={
        200: inline_serializer(
            name="LoginSuccessResponse",
            fields={
                "token": serializers.CharField(help_text="JWT Access Token"),
                "refresh": serializers.CharField(help_text="JWT Refresh Token"),
                "user": inline_serializer(
                    name="UserMinResponse",
                    fields={
                        "id": serializers.IntegerField(),
                        "username": serializers.CharField(),
                    }
                )
            }
        ),
        400: OpenApiResponse(description="Validation error"),
        401: OpenApiResponse(description="Invalid username or password")
    }
)
class LoginView(APIView):
    """POST /api/auth/login - authenticate and receive JWT tokens."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {'detail': 'Invalid username or password.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)

        return Response({
            'token': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {'id': user.id, 'username': user.username},
        }, status=status.HTTP_200_OK)


@extend_schema(
    summary="User Logout",
    description="Blacklists the provided refresh token so it cannot be used again.",
    request=inline_serializer(
        name="LogoutRequest",
        fields={
            "refresh": serializers.CharField(help_text="The refresh token to blacklist")
        }
    ),
    responses={
        200: inline_serializer(
            name="LogoutSuccessResponse",
            fields={
                "message": serializers.CharField()
            }
        ),
        400: OpenApiResponse(description="Missing token or invalid/expired token")
    }
)
class LogoutView(APIView):
    """POST /api/auth/logout - blacklist the refresh token so it can't be reused."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': 'Refresh token is required to logout.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            return Response(
                {'detail': 'Invalid or expired token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)