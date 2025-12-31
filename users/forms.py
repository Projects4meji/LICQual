from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import CustomUser, EmailSubscription

class EmailAuthenticationForm(AuthenticationForm):
    # AuthenticationForm uses `username` even if your USERNAME_FIELD is email.
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "class": "w-full border rounded-md px-3 py-2 focus:outline-none focus:ring",
            "placeholder": "you@example.com",
            "autocomplete": "email",
        }),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={
            "class": "w-full border rounded-md px-3 py-2 pr-10 focus:outline-none focus:ring",
            "placeholder": "••••••••",
            "autocomplete": "current-password",
        }),
    )
    
    def clean_username(self):
        """
        Normalize the email address before authentication.
        This ensures that emails stored with normalize_email() can be found
        regardless of the case the user types.
        """
        email = self.cleaned_data.get('username')
        if email:
            # Use the same normalization as CustomUserManager
            from django.contrib.auth.base_user import BaseUserManager
            manager = BaseUserManager()
            return manager.normalize_email(email)
        return email

class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "class": "block w-full rounded-md border-2 border-gray-300 shadow-sm text-base px-4 py-2",
            "placeholder": "you@example.com",
            "autocomplete": "email",
        }),
    )


class PasswordResetConfirmForm(forms.Form):
    password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={
            "class": "block w-full rounded-md border-2 border-gray-300 shadow-sm text-base px-4 py-2",
            "autocomplete": "new-password",
        }),
    )
    password_confirm = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={
            "class": "block w-full rounded-md border-2 border-gray-300 shadow-sm text-base px-4 py-2",
            "autocomplete": "new-password",
        }),
    )

    def clean(self):
        data = super().clean()
        if data.get("password") != data.get("password_confirm"):
            self.add_error("password_confirm", "Passwords do not match.")
        return data


class AvatarForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["avatar"]


class EmailSubscriptionForm(forms.ModelForm):
    class Meta:
        model = EmailSubscription
        fields = ["email"]
        widgets = {
            "email": forms.EmailInput(attrs={
                "placeholder": "Enter your email address",
                "class": "w-full px-4 py-3 rounded-lg bg-white/10 border border-white/20 text-white placeholder-white/60",
                "required": True,
                "autocomplete": "email",
            })
        }

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()