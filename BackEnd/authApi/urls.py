from django.urls import path
from . import views
from .views import CustomUserCreate,BlacklistTokenView
from .views import MyTokenObtainPairView
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from django.contrib.auth import views as auth_views
from .views import PasswordResetView, PasswordResetConfirmView, PasswordResetCompleteView, UserListView, UserUpdateView
from drf_spectacular.utils import extend_schema


TaggedTokenRefreshView = extend_schema(
    tags=['Auth'],
    summary="Refresh JWT access token",
    description=(
        "Provide a valid refresh token to receive a new short-lived access token. "
        "Send `{ \"refresh\": \"<token>\" }` in the request body."
    ),
)(TokenRefreshView)

urlpatterns=[
    path('',views.getRoutes),
    path('token/',MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    # path('token/refresh', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/refresh', TaggedTokenRefreshView.as_view(), name='token_refresh'),
    path('register/',CustomUserCreate.as_view(),name="create_user"),
    path('logout/blacklist/', BlacklistTokenView.as_view(),
         name='blacklist'),
    path('reset_password/', PasswordResetView.as_view(), name='api_reset_password'),
    path('reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='api_password_reset_confirm'),
    path('reset_password_complete/', PasswordResetCompleteView.as_view(), name='api_password_reset_complete'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('users/<int:user_id>/', UserUpdateView.as_view(), name='user-update'),
   
#     path('reset_password/',
#          auth_views.PasswordResetView.as_view(template_name="password_reset.html"),
#          name="reset_password"),
#     path('reset_password_sent/',
#          auth_views.PasswordResetDoneView.as_view(template_name="password_reset_sent.html"),
#          name="password_reset_done"),
#     path('reset/<uidb64>/<token>/',
#          auth_views.PasswordResetConfirmView.as_view(template_name="password_reset_form.html"), 
#          name="password_reset_confirm"),
#     path('reset_password_complete/',
#          auth_views.PasswordResetCompleteView.as_view(template_name="password_reset_done.html"),
#          name="password_reset_complete"),


]