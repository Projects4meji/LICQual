# users/views.py
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect
from django.urls import reverse, reverse_lazy
import uuid
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from .models import CustomUser, PasswordResetToken
from .forms import ForgotPasswordForm, PasswordResetConfirmForm
from .forms import EmailAuthenticationForm
from django.contrib.auth import logout
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .forms import EmailSubscriptionForm
from .models import EmailSubscription
from django.utils.http import url_has_allowed_host_and_scheme
from datetime import datetime

class EmailLoginView(LoginView):
    template_name = "users/login.html"
    redirect_authenticated_user= False 
    authentication_form = EmailAuthenticationForm  # if you're using the custom form

    def get_success_url(self):
        # Honor ?next= if present
        next_url = self.get_redirect_url()
        if next_url:
            return next_url

        user = self.request.user
        if not user.is_authenticated:
            return reverse_lazy("users:login")

        # superadmin first (Django superuser)
        if user.is_superuser:
            return reverse_lazy("superadmin:superadmin_dashboard")

        # role-based routing
        if hasattr(user, "has_role"):
            if user.has_role("partner"):
                return reverse_lazy("superadmin:business_dashboard")
            if user.has_role("learner"):
                return reverse_lazy("learners:learner_dashboard")

        # fallback
        return reverse_lazy("users:user_dashboard")





def _send_password_reset_email(request, user: CustomUser, token: str) -> None:
    reset_url = request.build_absolute_uri(reverse('users:password_reset_confirm', args=[token]))
    subject = 'DocRide Password Reset'
    # You can render a nice HTML template if you want; keeping plain text simple here:
    message = (
        f"Hi {user.full_name or user.email},\n\n"
        f"Click this link to reset your password:\n{reset_url}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_TIMEOUT // 3600} hour(s).\n"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def _send_password_reset_success_email(user: CustomUser) -> None:
    subject = 'DocRide Password Reset Successful'
    message = (
        f"Hi {user.full_name or user.email},\n\n"
        "Your password was changed successfully. If you did not make this change, "
        "please contact support immediately.\n"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)




def send_welcome_email(user: CustomUser, raw_password: str | None = None) -> None:
    """
    Send a welcome email to the user.
    - If `raw_password` is provided (brand-new user), include it in the email.
    - Otherwise omit the password for existing users.
    """
    # Build absolute login URL if SITE_URL/PORTAL_URL is set; else leave relative
    base_url = getattr(settings, "SITE_URL", None) or getattr(settings, "PORTAL_URL", None)
    try:
        login_path = reverse("users:login")
        portal_url = (base_url.rstrip("/") + login_path) if base_url else login_path
    except Exception:
        portal_url = None

    # Build a public, absolute logo URL for email clients
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "") or ""
    
    if not logo_url:
        # Use the Django static URL - try multiple possible filenames
        from django.templatetags.static import static
        static_filenames = [
            "images/LICQual-Logo.jpg",  # New filename with hyphen
            "images/LICQual Logo .jpg",
            "images/LICQual Logo.jpg",
            "images/licqual-logo.jpg",
            "images/ictqual-logo.jpg",
        ]
        
        for static_filename in static_filenames:
            try:
                path = static(static_filename)
                # If STATIC_URL is absolute (e.g., CDN), use as-is
                if path.startswith("http://") or path.startswith("https://") or path.startswith("//"):
                    logo_url = path
                    break
                else:
                    # If STATIC_URL is relative, prepend SITE_URL to make it absolute
                    site = getattr(settings, "SITE_URL", None) or getattr(settings, "PORTAL_URL", None)
                    if site:
                        # Ensure site URL doesn't have trailing slash and path starts with /
                        site = site.rstrip('/')
                        if not path.startswith('/'):
                            path = '/' + path
                        logo_url = f"{site}{path}"
                        break
            except Exception:
                continue
        
        # If still no URL, try to build one from BASE_DIR and STATIC_URL
        if not logo_url:
            base_dir = getattr(settings, 'BASE_DIR', None)
            static_url = getattr(settings, 'STATIC_URL', '/static/')
            site = getattr(settings, "SITE_URL", None) or getattr(settings, "PORTAL_URL", None)
            
            if base_dir and site:
                # Check if file exists in static/images
                for filename in ['LICQual-Logo.jpg', 'LICQual Logo .jpg', 'LICQual Logo.jpg', 'licqual-logo.jpg', 'ictqual-logo.jpg']:
                    static_path = os.path.join(base_dir, 'static', 'images', filename)
                    if os.path.exists(static_path):
                        # Build absolute URL
                        if not static_url.startswith('http'):
                            static_url = static_url.lstrip('/')
                            if not static_url.startswith('/'):
                                static_url = '/' + static_url
                        logo_url = f"{site.rstrip('/')}{static_url}images/{filename}"
                        # URL encode spaces in filename
                        logo_url = logo_url.replace(' ', '%20')
                        break

    # Always try to embed the logo inline - email clients often block external images
    # Locate the static file on disk
    logo_cid = None
    img_bytes = None
    from django.contrib.staticfiles import finders
    import os
    
    # Try multiple possible logo filenames
    logo_filenames = [
        "images/LICQual-Logo.jpg",  # New filename with hyphen
        "images/LICQual Logo .jpg",
        "images/LICQual Logo.jpg",
        "images/licqual-logo.jpg",
        "images/ictqual-logo.jpg",
    ]
    
    # Also try direct path in static folder
    base_dir = getattr(settings, 'BASE_DIR', None)
    if base_dir:
        static_dirs = [
            os.path.join(base_dir, 'static', 'images'),
            os.path.join(base_dir, 'staticfiles', 'images'),
        ]
        for static_dir in static_dirs:
            for filename in ['LICQual-Logo.jpg', 'LICQual Logo .jpg', 'LICQual Logo.jpg', 'licqual-logo.jpg', 'ictqual-logo.jpg']:
                direct_path = os.path.join(static_dir, filename)
                if os.path.exists(direct_path):
                    logo_filenames.insert(0, direct_path)
                    break
    
    logo_fs_path = None
    import logging
    logger = logging.getLogger(__name__)
    
    for filename in logo_filenames:
        # If it's already a full path, use it directly
        if os.path.isabs(filename) or os.path.exists(filename):
            if os.path.exists(filename):
                logo_fs_path = filename
                logger.info(f"Found logo at direct path: {logo_fs_path}")
                break
        else:
            # Try using finders
            found_path = finders.find(filename)
            if found_path and os.path.exists(found_path):
                logo_fs_path = found_path
                logger.info(f"Found logo via finders: {logo_fs_path}")
                break
            elif found_path:
                logger.debug(f"Finder returned path but file doesn't exist: {found_path}")
    
    if logo_fs_path and os.path.exists(logo_fs_path):
        try:
            logger.info(f"Attempting to read logo file: {logo_fs_path}")
            with open(logo_fs_path, "rb") as f:
                img_bytes = f.read()
            # Verify we actually got image data
            if img_bytes and len(img_bytes) > 0:
                logger.info(f"Successfully read logo file: {len(img_bytes)} bytes")
                # Build absolute URL if we have SITE_URL but logo_url is not absolute yet
                if not logo_url or not (logo_url.startswith("http://") or logo_url.startswith("https://") or logo_url.startswith("//")):
                    site = getattr(settings, "SITE_URL", None) or getattr(settings, "PORTAL_URL", None)
                    if site:
                        # Find which filename was used
                        found_filename = None
                        for filename in ['LICQual-Logo.jpg', 'LICQual Logo .jpg', 'LICQual Logo.jpg', 'licqual-logo.jpg', 'ictqual-logo.jpg']:
                            if filename in logo_fs_path:
                                found_filename = filename
                                break
                        if not found_filename:
                            found_filename = os.path.basename(logo_fs_path)
                        
                        static_url = getattr(settings, 'STATIC_URL', '/static/')
                        if not static_url.startswith('http'):
                            static_url = static_url.lstrip('/')
                            if not static_url.startswith('/'):
                                static_url = '/' + static_url
                        logo_url = f"{site.rstrip('/')}{static_url}images/{found_filename}"
                        # URL encode spaces in filename
                        logo_url = logo_url.replace(' ', '%20')
                        logger.info(f"Built absolute logo URL: {logo_url}")
                
                # Set CID as fallback only if URL is not available
                if not logo_url or not (logo_url.startswith("http://") or logo_url.startswith("https://") or logo_url.startswith("//")):
                    logo_cid = "licqual-logo"
                else:
                    logo_cid = None  # Prefer URL over CID
            else:
                logger.warning(f"Logo file exists but is empty: {logo_fs_path}")
                img_bytes = None
                logo_cid = None
        except Exception as e:
            # Log error but continue - logo will just not appear
            logger.error(f"Could not load logo for welcome email: {e}", exc_info=True)
            logo_cid = None
            img_bytes = None
    else:
        # Log warning if logo file not found
        logger.warning(f"Logo file not found. Tried: {logo_filenames}")

    # Prepare base64 encoded image as fallback
    import base64
    logo_base64 = None
    if img_bytes and len(img_bytes) > 0:
        try:
            # Detect image type for data URI first
            if img_bytes.startswith(b'\xff\xd8'):
                img_mime_type = "image/jpeg"
            elif img_bytes.startswith(b'\x89PNG'):
                img_mime_type = "image/png"
            elif img_bytes.startswith(b'GIF'):
                img_mime_type = "image/gif"
            else:
                img_mime_type = "image/jpeg"  # Default to JPEG
            
            # Encode to base64
            encoded = base64.b64encode(img_bytes).decode('utf-8')
            logo_base64 = f"data:{img_mime_type};base64,{encoded}"
            
            # Log success for debugging
            logger.info(f"Successfully encoded logo as base64 ({len(img_bytes)} bytes, type: {img_mime_type})")
        except Exception as e:
            logger.warning(f"Could not encode logo as base64: {e}", exc_info=True)
            logo_base64 = None
    final_logo_url = ""
    if logo_url and (logo_url.startswith("http://") or logo_url.startswith("https://") or logo_url.startswith("//")):
        final_logo_url = logo_url
        logger.info(f"Using hosted logo URL: {final_logo_url}")

    # Prefer CID when available: it's the most reliable across clients (no external fetch).
    prefer_cid = bool(img_bytes)
    if prefer_cid:
        logo_cid = "licqual-logo"
        final_logo_url = ""

    ctx = {
        "email": user.email,
        "full_name": user.full_name or user.email.split("@", 1)[0].replace(".", " ").title(),
        "business_name": "LICQUAL",
        "portal_url": portal_url,
        "password": raw_password,                 # only shown if not None in the template
        "role_label": "Partner",
        "logo_url": final_logo_url,
        "logo_cid": logo_cid,
        "logo_base64": None,
    }

    html_body = render_to_string("users/send_welcome_email.html", ctx)

    plain_lines = [ "Welcome to LICQUAL!", f"Email: {user.email}" ]
    if raw_password:
        plain_lines.append(f"Password: {raw_password}")
    if portal_url:
        plain_lines.append(f"Login: {portal_url}")
    plain_body = "\n".join(plain_lines)

    # Use EmailMultiAlternatives and attach inline image correctly
    from django.core.mail import EmailMultiAlternatives
    from email.mime.image import MIMEImage
    
    msg = EmailMultiAlternatives(
        subject="Welcome to LICQUAL",
        body=plain_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )

    # Inline images should be sent as multipart/related for best client compatibility.
    msg.mixed_subtype = "related"

    msg.attach_alternative(html_body, "text/html")

    # Attach inline image if available
    if logo_cid and img_bytes:
        try:
            # Detect image type from bytes
            if img_bytes.startswith(b'\xff\xd8'):
                img_type = "jpeg"
            elif img_bytes.startswith(b'\x89PNG'):
                img_type = "png"
            elif img_bytes.startswith(b'GIF'):
                img_type = "gif"
            else:
                img_type = "jpeg"  # Default to JPEG
            
            img = MIMEImage(img_bytes, _subtype=img_type)
            # Content-ID must match exactly what's in the HTML template (without cid: prefix)
            img.add_header("Content-ID", f"<{logo_cid}>")
            img.add_header("Content-Disposition", "inline", filename="licqual-logo.jpg")
            msg.attach(img)
            logger.info("Attached logo as CID inline image")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not attach logo image to email: {e}")


    # Use fail_silently=True to prevent registration failures if email backend is not configured
    try:
        msg.send(fail_silently=False)
    except Exception as e:
        # Log error but don't fail the welcome email if backend is not configured
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to send welcome email to {user.email}: {e}")
        # Re-raise only if it's not a configuration issue
        if "not initialized" not in str(e).lower() and "credentials" not in str(e).lower():
            raise



def forgot_password(request):
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip()
            user = CustomUser.objects.filter(email__iexact=email).first()

            # Always show success message regardless, to avoid enumerating users
            if user:
                # create token
                token = uuid.uuid4().hex
                PasswordResetToken.objects.create(
                    user=user,
                    token=token,
                    expires_at=timezone.now() + timezone.timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT),
                )
                try:
                    _send_password_reset_email(request, user, token)
                except Exception:
                    # Still show generic success; log if you want
                    pass

            from django.contrib import messages
            messages.success(request, "If an account exists for that email, a reset link has been sent.")
            return render(request, 'users/forgot_password.html', {'form': form})
    else:
        form = ForgotPasswordForm()

    return render(request, 'users/forgot_password.html', {'form': form})


def password_reset_confirm(request, token):
    try:
        reset_token = PasswordResetToken.objects.get(token=token)
    except PasswordResetToken.DoesNotExist:
        from django.contrib import messages
        messages.error(request, "Invalid or expired reset link.")
        return redirect('users:forgot_password')

    if not reset_token.is_valid():
        from django.contrib import messages
        messages.error(request, "This reset link has expired.")
        return redirect('users:forgot_password')

    if request.method == 'POST':
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            user = reset_token.user
            user.set_password(form.cleaned_data['password'])
            user.save()
            # Invalidate this token
            reset_token.delete()
            try:
                _send_password_reset_success_email(user)
            except Exception:
                pass
            from django.contrib import messages
            messages.success(request, "Your password has been reset. Please log in.")
            return redirect('users:login')
    else:
        form = PasswordResetConfirmForm()

    return render(request, 'users/password_reset_confirm.html', {'form': form})



@login_required
def change_avatar(request):
    """
    Upload or remove the current user's avatar.
    """
    from .forms import AvatarForm

    if request.method == "POST":
        # Handle "Remove photo" action
        if request.POST.get("remove") == "1":
            if request.user.avatar and request.user.avatar.name:
                try:
                    request.user.avatar.delete(save=False)
                except Exception:
                    pass
            request.user.avatar = None
            request.user.save(update_fields=["avatar"])
            messages.success(request, "Profile photo removed.")
            return redirect("users:change_avatar")

        # Handle upload/update
        form = AvatarForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile photo has been updated.")
            return redirect("users:change_avatar")
    else:
        form = AvatarForm(instance=request.user)

    return render(request, "users/change_avatar.html", {"form": form})


@login_required
def logout_view(request):
    logout(request)
    return redirect("users:login")



@require_http_methods(["GET", "POST"])
def email_subscription(request):
    print("DEBUG: email_subscription view called with method:", request.method, "POST data:", request.POST, "Time:", datetime.now().isoformat())
    next_url = (
        request.POST.get("next")
        or request.GET.get("next")
        or request.META.get("HTTP_REFERER")
        or reverse("users:email_subscription")
    )
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("users:email_subscription")
    from_newsletter = (request.POST.get("from_newsletter") == "1")
    if from_newsletter and "#newsletter" not in next_url:
        next_url = f"{next_url}#newsletter"

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if not email:
            messages.error(
                request,
                "Please enter a valid email address.",
                extra_tags="newsletter",
            )
            return redirect(next_url)

        if EmailSubscription.objects.filter(email=email).exists():
            messages.info(
                request,
                "You're already on the list. 👍",
                extra_tags="newsletter",
            )
            return redirect(next_url)

        form = EmailSubscriptionForm(request.POST)
        if form.is_valid():
            sub, created = EmailSubscription.objects.get_or_create(
                email=email, defaults={"is_active": True}
            )
            if not created and not sub.is_active:
                sub.is_active = True
                sub.save(update_fields=["is_active"])
                messages.success(
                    request,
                    "Thank you very much for the Subscription. You have been successfully subscribed.",
                    extra_tags="newsletter",
                )
            elif created:
                messages.success(
                    request,
                    "Thank you very much for the Subscription. You have been successfully subscribed.",
                    extra_tags="newsletter",
                )
            else:
                messages.info(
                    request,
                    "You're already on the list. 👍",
                    extra_tags="newsletter",
                )
            return redirect(next_url)
        else:
            messages.error(
                request,
                form.errors.get("email", ["Invalid email address"])[0],
                extra_tags="newsletter",
            )
            return redirect(next_url)

    form = EmailSubscriptionForm()
    return render(request, "users/email_subscription.html", {"form": form})