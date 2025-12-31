# users/urls.py
from django.urls import path
from .views import (
    EmailLoginView, forgot_password, password_reset_confirm, change_avatar, logout_view, email_subscription
)

app_name = "users"

urlpatterns = [
    path("login/", EmailLoginView.as_view(), name="login"),
    path("forgot-password/", forgot_password, name="forgot_password"),
    path("password-reset/<str:token>/", password_reset_confirm, name="password_reset_confirm"),
    path("logout/", logout_view, name="logout"),                 
    path("change-avatar/", change_avatar, name="change_avatar"),
    path('email-subscription/', email_subscription, name='email_subscription'),

]
