
# Create your views here.
from django.shortcuts import render
# Create your views here.
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import RegisterUserSerializer
from rest_framework.permissions import AllowAny
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import PasswordResetSerializer, SetNewPasswordSerializer
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from .models import NewUser
from rest_framework.generics import GenericAPIView
from drf_spectacular.utils import extend_schema, extend_schema_view


 
# ─── JWT Token ────────────────────────────────────────────────────────────────


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['user_name'] = user.user_name
        token['email']=user.email
        token['phone_number']=user.phone_number
        token['location']=user.location
        token['approved']=user.approved
        token['is_staff']=user.is_staff
        # ✅ ADD THIS (IMPORTANT)
        token['roles'] = list(user.groups.values_list('name', flat=True))
        # ...
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Gate: users must be admin-approved before they can obtain a token.
        # Existing users were backfilled to approved=True on 2026-07-21; new
        # signups default to approved=False and need staff to flip the flag.
        if not self.user.approved:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied(
                detail=(
                    "Your account is awaiting administrator approval. "
                    "Please contact a platform administrator."
                )
            )
        return data

@extend_schema(
    tags=['Auth'],
    summary="Obtain JWT token pair",
    description=(
        "Authenticate with email and password to receive an access token and refresh token. "
        "The access token is short-lived (5 minutes). Use the refresh token to get a new access token. "
        "The token payload includes: `user_name`, `email`, `phone_number`, `location`, `approved`, `is_staff`."
    ),
)  
class MyTokenObtainPairView(TokenObtainPairView): 
    serializer_class=MyTokenObtainPairSerializer


# ─── Registration ─────────────────────────────────────────────────────────────

@extend_schema(
    tags=['Auth'],
    summary="Register a new user",
    description="Create a new user account. Provide all required fields in the request body. Returns the created user data on success.",
)
class CustomUserCreate(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        reg_serializer = RegisterUserSerializer(data=request.data)
        if reg_serializer.is_valid():
            user = reg_serializer.save()
            if user:
                json = reg_serializer.data
                return Response(json, status=status.HTTP_201_CREATED)
        return Response(reg_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# ─── Routes ───────────────────────────────────────────────────────────────────
 
@extend_schema(exclude=True) 
@api_view(['GET'])
def getRoutes(request):
    routes=[ 
        '/api/token',
        '/api/token/refresh',
    ]
    return Response(routes)


# ─── Logout / Blacklist ───────────────────────────────────────────────────────
 
@extend_schema(
    tags=['Auth'],
    summary="Logout — blacklist refresh token",
    description=(
        "Invalidates the provided refresh token by adding it to the blacklist. "
        "Call this on logout to prevent the refresh token from being reused. "
        "Send `{ \"refresh_token\": \"<token>\" }` in the request body."
    ),
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'refresh_token': {'type': 'string', 'example': 'eyJ0eXAiOiJKV1Q...'}
            },
            'required': ['refresh_token']
        }
    },
)
class BlacklistTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes=()
    def post(self,request):
        try:
            refresh_token =request.data["refresh_token"]
            token=RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response(status=status.HTTP_400_BAD_REQUEST)




# ─── Password Reset ───────────────────────────────────────────────────────────
 
@extend_schema(
    tags=['Auth'],
    summary="Request a password reset email",
    description=(
        "Sends a password reset link to the provided email address if an account exists. "
        "The link is valid for a limited time and contains a UID and token. "
        "Always returns a 200 response regardless of whether the email exists (to prevent user enumeration)."
    ),
)
class PasswordResetView(GenericAPIView):
    serializer_class = PasswordResetSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = NewUser.objects.filter(email=email).first()
        if user:
            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{settings.FRONTEND_URL}/reset/{uid}/{token}/"
            subject = 'Password Reset Requested'
            message = f'Hi {user.user_name},\n\nYou requested a password reset. Click the link below to reset your password:\n{reset_url}\n\nIf you did not request this, please ignore this email.'
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])

        return Response({"message": "Password reset email has been sent."}, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth'],
    summary="Confirm password reset with token",
    description=(
        "Validates the UID and token from the reset link and sets a new password. "
        "`uidb64` is the base64-encoded user ID and `token` is the reset token from the email link. "
        "Provide the new password in the request body."
    ),
)
class PasswordResetConfirmView(GenericAPIView):
    serializer_class = SetNewPasswordSerializer

    def post(self, request, uidb64, token):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = NewUser.objects.get(pk=uid)
            if default_token_generator.check_token(user, token):
                serializer = self.get_serializer(data=request.data)
                serializer.is_valid(raise_exception=True)
                user.set_password(serializer.validated_data['password'])
                user.save()
                return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid token."}, status=status.HTTP_400_BAD_REQUEST)
        except (TypeError, ValueError, OverflowError, NewUser.DoesNotExist):
            return Response({"error": "Invalid token or user ID."}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(
    tags=['Auth'],
    summary="Password reset complete confirmation",
    description="Returns a confirmation message indicating the password reset flow is complete. Used as a landing endpoint after a successful reset.",
)
class PasswordResetCompleteView(GenericAPIView):
    def get(self, request):
        return Response({"message": "Password has been reset successfully."}, status=status.HTTP_200_OK)


from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from .serializers import UserListSerializer


class _IsStaffAndActive(IsAuthenticated):
    def has_permission(self, request, view):
        return bool(
            super().has_permission(request, view)
            and request.user
            and request.user.is_staff
            and request.user.is_active
        )


class _UserListPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 200


@extend_schema(
    tags=['Auth'],
    summary="List all registered users (staff only)",
    description=(
        "Returns a paginated list of every user on the platform, with their "
        "roles (Django groups) and status flags. Accessible only to active "
        "staff members."
    ),
)
class UserListView(APIView):
    permission_classes = [_IsStaffAndActive]

    def get(self, request):
        queryset = NewUser.objects.all().order_by('-start_date').prefetch_related('groups')
        paginator = _UserListPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = UserListSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


# Group names this endpoint knows how to add/remove. Membership in other
# groups (if any) is preserved untouched.
_MANAGED_ROLE_GROUPS = ('Author', 'Reviewer', 'Editor')


@extend_schema(
    tags=['Auth'],
    summary="Update a user's flags and roles (staff only)",
    description=(
        "PATCH accepts any subset of: is_active, is_staff, is_superuser, "
        "approved, roles. `roles` is a list restricted to Author/Reviewer/"
        "Editor; membership in those three groups is replaced with what is "
        "sent. Self-guard: staff cannot strip their own is_active/is_staff/"
        "is_superuser. Auto-sets is_staff=True when is_superuser=True."
    ),
)
class UserUpdateView(APIView):
    permission_classes = [_IsStaffAndActive]

    def patch(self, request, user_id):
        from django.contrib.auth.models import Group
        from django.shortcuts import get_object_or_404

        target = get_object_or_404(NewUser, id=user_id)
        payload = request.data or {}

        is_self = request.user.id == target.id
        errors = {}

        # Whitelist of boolean flags we accept.
        bool_fields = ('is_active', 'is_staff', 'is_superuser', 'approved')
        updates = {}
        for f in bool_fields:
            if f in payload:
                val = payload[f]
                if not isinstance(val, bool):
                    errors[f] = 'Must be a boolean.'
                    continue
                updates[f] = val

        # Self-guard: reject stripping own privileges.
        if is_self:
            for f in ('is_active', 'is_staff', 'is_superuser'):
                if updates.get(f) is False:
                    errors[f] = (
                        f'You cannot set {f}=False on your own account. '
                        f'Ask another admin to do it.'
                    )

        # Django convention: a superuser must be able to reach /admin, so
        # flipping is_superuser=True implies is_staff=True.
        if updates.get('is_superuser') is True:
            updates['is_staff'] = True

        # Role management: replace membership in the three managed groups.
        roles_payload = payload.get('roles', None)
        role_groups_to_set = None
        if roles_payload is not None:
            if not isinstance(roles_payload, list) or not all(
                isinstance(r, str) for r in roles_payload
            ):
                errors['roles'] = 'Must be a list of group name strings.'
            else:
                unknown = [
                    r for r in roles_payload if r not in _MANAGED_ROLE_GROUPS
                ]
                if unknown:
                    errors['roles'] = (
                        f'Unknown role(s): {unknown}. Allowed: '
                        f'{list(_MANAGED_ROLE_GROUPS)}.'
                    )
                else:
                    role_groups_to_set = list(set(roles_payload))

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # Apply flag updates.
        if updates:
            for f, v in updates.items():
                setattr(target, f, v)
            target.save(update_fields=list(updates.keys()))

        # Apply role updates: remove from managed groups the user shouldn't be
        # in, and add to the ones they should. Other groups untouched.
        if role_groups_to_set is not None:
            managed_groups = Group.objects.filter(name__in=_MANAGED_ROLE_GROUPS)
            managed_by_name = {g.name: g for g in managed_groups}
            for name in _MANAGED_ROLE_GROUPS:
                g = managed_by_name.get(name)
                if not g:
                    continue
                if name in role_groups_to_set:
                    target.groups.add(g)
                else:
                    target.groups.remove(g)

        # Return the fresh state so the UI can update the row in place.
        target.refresh_from_db()
        serializer = UserListSerializer(target)
        return Response(serializer.data, status=status.HTTP_200_OK)