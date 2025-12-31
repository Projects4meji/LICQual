from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from users.models import CustomUser, Role, EmailSubscription
import re
from PIL import ImageOps
from django.db import transaction, IntegrityError
from django.utils.crypto import get_random_string
from .models import Business, Course, LearnerRegistration, PaymentSession, LearnerRegistrationPayment, BusinessDiscount, BusinessCourseDiscount
from users.views import send_welcome_email
from django.conf import settings
from django.db.models import Q, Count
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.http import FileResponse, HttpResponse, Http404, HttpResponseForbidden
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.safestring import mark_safe
import json
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_date
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.text import slugify
from django.templatetags.static import static
from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.contrib.staticfiles import finders
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64
import io, json
from decimal import Decimal
from django.core.files.base import ContentFile
from django.utils.formats import date_format
from PIL import Image, ImageDraw, ImageFont
from .forms import BusinessForm, CourseForm, LearnerEditForm, AtpGlobalTemplateForm, CentreApplicationApprovalForm, BusinessDiscountForm, AwardedDateForm
from django.db.models.functions import Coalesce, NullIf, Trim
from django.db import models
from django.db.models import F, OuterRef, Subquery, Value, IntegerField
import io, os, zipfile
import io, random, string
from datetime import date, timedelta
from django.http import HttpResponseNotAllowed
from io import BytesIO
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
import csv
import io
import secrets
from django.utils.text import slugify
from django.contrib.staticfiles import finders
from users.storage_backends import CertTemplateStorage
import qrcode
# Pillow for drawing on the template PNG and exporting PDF
from PIL import Image, ImageDraw, ImageFont

import qrcode
try:
    import cairosvg  # for SVG templates (optional)
except Exception:
    cairosvg = None
import os
from django.views.decorators.cache import never_cache

import threading, logging
logger = logging.getLogger(__name__)


# --- Storage-safe template opener (PNG/JPG/SVG) ---
import io
try:
    import cairosvg  # optional, for SVG templates
except Exception:
    cairosvg = None
from PIL import Image
ATP_CERT_TEMPLATE_KEY = "atp/authorization_template.png"

def _get_default_certificate_template():
    """
    Get the default certificate template file path.
    Returns the path to the default template if it exists, None otherwise.
    """
    from django.conf import settings
    import os
    from django.core.files.storage import default_storage
    
    # Check for default template in certificate_samples folder
    default_paths = [
        os.path.join(settings.BASE_DIR, "certificate_samples", "LICQual Certificate.jpg"),
        os.path.join(settings.BASE_DIR, "certificate_samples", "LICQual Certificate.png"),
        os.path.join(settings.BASE_DIR, "certificate_samples", "LICQual Certificate.jpeg"),
    ]
    
    for path in default_paths:
        if os.path.exists(path):
            return path
    
    return None

def _open_template_image(course):
    """
    Open the course.certificate_template from its FileField storage (S3/Spaces).
    Returns a PIL.Image in RGBA. Supports PNG/JPG and SVG (via cairosvg).
    Falls back to default template if course template is not set.
    """
    tmpl = getattr(course, "certificate_template", None)
    
    # If no template is set, try to use default template
    if not tmpl:
        default_path = _get_default_certificate_template()
        if default_path:
            # Open default template from local filesystem
            with open(default_path, "rb") as f:
                return Image.open(f).convert("RGBA")
        raise FileNotFoundError("No certificate template set for this course and no default template found.")

    # IMPORTANT: open via the FileField's storage, not .path
    name = (tmpl.name or "").lower()
    with tmpl.open("rb") as f:
        if name.endswith(".svg"):
            if not cairosvg:
                raise RuntimeError("SVG template requires cairosvg to be installed.")
            # Render SVG to PNG bytes, pick a sensible size (~A4 @ 300dpi)
            png_bytes = cairosvg.svg2png(file_obj=f, output_width=3508, output_height=2480)
            return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
        else:
            # PNG/JPG
            return Image.open(f).convert("RGBA")



def _nocache(resp):
    resp["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp["Pragma"] = "no-cache"
    resp["Expires"] = "0"
    return resp


def _partner_business_for(user):
    """
    Try a few common patterns to get the partner's Business.
    Adjust to your actual schema if needed.
    """
    from .models import Business  # adjust import path if different

    # Pattern A: One business per user via FK (Business.user)
    if hasattr(Business, 'user_id'):
        b = Business.objects.filter(user=user).first()
        if b:
            return b

    # Pattern B: Many-to-many Business.users
    if hasattr(Business, 'users'):
        b = Business.objects.filter(users=user).first()
        if b:
            return b

    # Pattern C: if you store business on the user profile
    if hasattr(user, 'business'):
        return getattr(user, 'business', None)

    return None


@login_required
def superadmin_dashboard(request):
    if not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to view this page.")
    
    # Get statistics for the dashboard
    total_businesses = Business.objects.count()
    total_courses = Course.objects.count()
    total_learners = CustomUser.objects.filter(roles__name=Role.Names.LEARNER).distinct().count()
    total_registrations = LearnerRegistration.objects.count()
    pending_certificates = LearnerRegistration.objects.filter(certificate_issued_at__isnull=True).count()
    issued_certificates = LearnerRegistration.objects.filter(certificate_issued_at__isnull=False).count()
    
    # Recent businesses (last 5)
    recent_businesses = Business.objects.order_by('-created_at')[:5]
    
    # Recent courses (last 5)
    recent_courses = Course.objects.order_by('-created_at')[:5]
    
    context = {
        'total_businesses': total_businesses,
        'total_courses': total_courses,
        'total_learners': total_learners,
        'total_registrations': total_registrations,
        'pending_certificates': pending_certificates,
        'issued_certificates': issued_certificates,
        'recent_businesses': recent_businesses,
        'recent_courses': recent_courses,
    }
    
    return render(request, "superadmin/superadmin_dashboard.html", context)

@login_required
def website_messages(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    qs = ContactUs.objects.all()
    paginator = Paginator(qs, 25)
    page = request.GET.get("page")
    page_obj = paginator.get_page(page)
    return render(request, "superadmin/website_messages.html", {"page_obj": page_obj})

@login_required
def website_message_delete(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    if request.method == "POST":
        obj = get_object_or_404(ContactUs, pk=pk)
        obj.delete()
    return redirect("superadmin:website_messages")


def add_business(request):
    if request.method == "POST":
        form = BusinessForm(request.POST)
        if form.is_valid():
            business = form.save()

            # Find or create user by business email
            user = CustomUser.objects.filter(email__iexact=business.email).first()
            created_now = False
            plain_password = None

            if not user:
                # Create user with a random password we can email once
                # Use the Business we just saved
                safe_full_name = (
                    (business.business_name or business.name or "").strip() or "User"
                )[:30]

                safe_email = (business.email or "").strip()

                plain_password = get_random_string(12)
                user = CustomUser.objects.create_user(
                    email=safe_email,
                    password=plain_password,
                    full_name=safe_full_name,
                    is_active=True,
                )

                created_now = True



            # Ensure Partner role is assigned
            partner_role, _ = Role.objects.get_or_create(name=Role.Names.PARTNER)
            user.roles.add(partner_role)

            # Send welcome email:
            # - Include password only for brand-new users
            try:
                send_welcome_email(user=user, raw_password=(plain_password if created_now else None))
            except Exception as e:
                messages.warning(
                    request,
                    f"Business & user saved, but welcome email failed: {e}"
                )
            else:
                if created_now:
                    messages.success(
                        request,
                        "Business created, user account created, Partner role assigned, and welcome email sent with credentials."
                    )
                else:
                    messages.success(
                        request,
                        "Business created. Existing user found; Partner role ensured and welcome email sent."
                    )

            return redirect(reverse("superadmin:superadmin_dashboard"))
    else:
        form = BusinessForm()

    return render(request, "superadmin/add_business.html", {"form": form})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_business(request, pk):
    """
    Edit an existing business.
    """
    business = get_object_or_404(Business, pk=pk)
    
    if request.method == "POST":
        form = BusinessForm(request.POST, instance=business)
        if form.is_valid():
            business = form.save()
            messages.success(request, f"Business '{business.business_name or business.name}' updated successfully.")
            return redirect(reverse("superadmin:business_list"))
    else:
        form = BusinessForm(instance=business)
    
    return render(request, "superadmin/edit_business.html", {"form": form, "business": business})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def business_list(request):
    """
    List businesses and annotate each with a display name:
      1) Business.name (editable by superadmin)
      2) Else matching CustomUser.full_name (by email)
      3) Else matching CustomUser.email
      4) Else empty
    Supports search (q) and advance_payment filter.
    """
    # Subqueries: get the first matching CustomUser by Business.email (case-insensitive)
    partner_full_name_sq = Subquery(
        CustomUser.objects
        .filter(email__iexact=OuterRef("email"))
        .order_by("id")
        .values("full_name")[:1],
        output_field=models.CharField(),
    )
    partner_email_sq = Subquery(
        CustomUser.objects
        .filter(email__iexact=OuterRef("email"))
        .order_by("id")
        .values("email")[:1],
        output_field=models.CharField(),
    )

    businesses = (
        Business.objects
        .annotate(
            partner_name=Coalesce(
                # Prefer the Business.name (what you edit in Add/Edit Business)
                NullIf(Trim(F("name")), Value("")),
                # Then use the user's full name (if present)
                NullIf(Trim(partner_full_name_sq), Value("")),
                # Then fall back to the user's email
                partner_email_sq,
                # Finally, empty string
                Value(""),
                output_field=models.CharField(),
            )
        )
    )

    # Search filter
    q = request.GET.get("q", "").strip()
    if q:
        businesses = businesses.filter(
            Q(business_name__icontains=q) |
            Q(name__icontains=q) |
            Q(email__icontains=q) |
            Q(partner_name__icontains=q)
        )

    # Advance payment filter
    adv_payment = request.GET.get("adv_payment", "").strip()
    if adv_payment == "yes":
        businesses = businesses.filter(advance_payment=True)
    elif adv_payment == "no":
        businesses = businesses.filter(advance_payment=False)

    businesses = businesses.order_by("-created_at")

    return render(request, "superadmin/business_list.html", {
        "businesses": businesses,
        "q": q,
        "adv_payment": adv_payment,
    })





@login_required
def business_dashboard(request):
    # Only partners can access this dashboard
    if hasattr(request.user, "has_role") and not request.user.has_role(Role.Names.PARTNER):
        raise PermissionDenied("Not a partner.")

    is_learner = hasattr(request.user, "has_role") and request.user.has_role(Role.Names.LEARNER)

    # Match the partner's business via the account email
    partner_businesses = Business.objects.filter(email__iexact=request.user.email)

    # Get statistics for the dashboard
    from .models import LearnerRegistration
    from django.db.models import Count
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    total_courses = Course.objects.filter(businesses__in=partner_businesses).distinct().count() if partner_businesses.exists() else 0
    total_registrations = LearnerRegistration.objects.filter(business__in=partner_businesses).count() if partner_businesses.exists() else 0
    pending_certificates = LearnerRegistration.objects.filter(business__in=partner_businesses, certificate_issued_at__isnull=True).count() if partner_businesses.exists() else 0
    issued_certificates = LearnerRegistration.objects.filter(business__in=partner_businesses, certificate_issued_at__isnull=False).count() if partner_businesses.exists() else 0

    # Get monthly registration data for the last 12 months
    monthly_data = []
    monthly_labels = []
    
    if partner_businesses.exists():
        # Get the last 12 months with proper month boundaries
        now = timezone.now()
        from calendar import monthrange
        
        # Calculate 12 months: from 11 months ago to current month (inclusive)
        # Example: If today is Dec 15, 2024, show: Jan 2024, Feb 2024, ..., Nov 2024, Dec 2024
        for i in range(11, -1, -1):  # i goes from 11 (11 months ago) to 0 (current month)
            # Calculate the exact month by going back i months from current month
            current_year = now.year
            current_month = now.month
            
            # Calculate target month: current_month - i
            # When i=0: current month (December)
            # When i=11: 11 months ago (January)
            target_month = current_month - i
            target_year = current_year
            
            # Handle year rollover (when going back crosses year boundary)
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            
            # Create month start (first day of the month)
            month_start = timezone.make_aware(
                datetime(target_year, target_month, 1, 0, 0, 0, 0)
            )
            
            # Calculate month end properly
            if i == 0:
                # Current month - use current date/time as end
                month_end = now
            else:
                # Get last day of the month
                last_day = monthrange(target_year, target_month)[1]
                month_end = timezone.make_aware(
                    datetime(target_year, target_month, last_day, 23, 59, 59, 999999)
                )
            
            # Query registrations for this month (dynamic query - updates on each page load)
            # This ensures the graph updates when learners are registered or deleted
            count = LearnerRegistration.objects.filter(
                business__in=partner_businesses,
                created_at__gte=month_start,
                created_at__lte=month_end
            ).count()
            
            monthly_data.append(count)
            monthly_labels.append(month_start.strftime('%b %Y'))
    else:
        # If no businesses, return empty data for 12 months
        now = timezone.now()
        from calendar import monthrange
        for i in range(11, -1, -1):
            current_year = now.year
            current_month = now.month
            
            target_month = current_month - i
            target_year = current_year
            
            while target_month <= 0:
                target_month += 12
                target_year -= 1
            
            month_start = timezone.make_aware(
                datetime(target_year, target_month, 1, 0, 0, 0, 0)
            )
            monthly_data.append(0)
            monthly_labels.append(month_start.strftime('%b %Y'))

    return render(
        request,
        "superadmin/business_dashboard.html",
        {
            "is_learner": is_learner,
            "total_courses": total_courses,
            "total_registrations": total_registrations,
            "pending_certificates": pending_certificates,
            "issued_certificates": issued_certificates,
            "monthly_registrations": monthly_data,
            "monthly_labels": monthly_labels,
        },
    )






@login_required
def register_learners_business(request):
    """
    Show all courses assigned to the business and allow registering learners to any of them.
    """
    # Only partners can use this page
    if not (hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER)):
        raise PermissionDenied("Only Partner users can register learners.")

    # The partner's businesses are matched by their account email
    partner_businesses = Business.objects.filter(email__iexact=request.user.email)
    if not partner_businesses.exists():
        messages.error(request, "No matching business was found for your account.")
        return redirect("superadmin:business_dashboard")

    # Get all unrestricted courses assigned to the business
    courses = Course.objects.filter(
        businesses__in=partner_businesses,
        businesses__is_restricted=False
    ).distinct().order_by('title')

    # Get registration counts for each course
    from .models import LearnerRegistration
    course_data = []
    for course in courses:
        # Find the business that owns this course (prefer unrestricted)
        owning_business = partner_businesses.filter(courses=course, is_restricted=False).first()
        if not owning_business:
            continue
            
        registration_count = LearnerRegistration.objects.filter(
            course=course,
            business=owning_business
        ).count()
        
        course_data.append({
            'course': course,
            'business': owning_business,
            'registration_count': registration_count,
        })

    return render(
        request,
        "superadmin/register_learners_business.html",
        {
            "courses": course_data,
            "business": partner_businesses.first(),  # Primary business for display
        },
    )


@login_required
def add_course(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Not authorized.")

    if request.method == "POST":
        try:
            # Extract basic course data
            title = (request.POST.get('title') or '').strip()
            course_number = (request.POST.get('course_number') or '').strip()
            category = (request.POST.get('category') or '').strip()
            duration = (request.POST.get('duration') or '').strip()
            credit_hours = (request.POST.get('credit_hours') or '0').strip()
            certificate_sample = request.FILES.get('certificate_sample')
            certificate_template = request.FILES.get('certificate_template')
            
            if not title or not course_number:
                messages.error(request, "Qualification Title and Number are required.")
                return render(request, "superadmin/add_course.html", {})
            
            # Create the course
            from decimal import Decimal
            course = Course.objects.create(
                title=title,
                course_number=course_number,
                category=category,
                duration=duration,
                credit_hours=Decimal(credit_hours) if credit_hours else Decimal('0'),
            )
            
            # Save certificate template if uploaded, otherwise use default
            if certificate_template:
                try:
                    file_name = getattr(certificate_template, 'name', None)
                    if not file_name:
                        file_name = getattr(certificate_template, '_name', None) or getattr(certificate_template, 'filename', None)
                    
                    if file_name:
                        if not isinstance(file_name, str):
                            file_name = str(file_name) if file_name is not None else "certificate_template.png"
                        if not hasattr(certificate_template, 'name') or not certificate_template.name:
                            certificate_template.name = file_name
                        course.certificate_template = certificate_template
                        course.save()
                    else:
                        logger.warning("Certificate template file has no name attribute - skipping save")
                        messages.warning(request, "Certificate template file has no name and could not be saved.")
                except Exception as e:
                    logger.error(f"Error saving certificate template: {e}", exc_info=True)
                    messages.warning(request, f"Certificate template could not be saved: {e}")
            else:
                # Try to set default template if no template was uploaded
                default_path = _get_default_certificate_template()
                if default_path:
                    try:
                        from django.core.files import File
                        with open(default_path, 'rb') as f:
                            file_name = os.path.basename(default_path)
                            course.certificate_template.save(file_name, File(f), save=True)
                            logger.info(f"Applied default certificate template to course {course.id}")
                    except Exception as e:
                        logger.error(f"Error applying default certificate template: {e}", exc_info=True)
                        messages.info(request, "Default certificate template will be used when generating certificates.")
            
            # Save certificate sample if uploaded
            if certificate_sample:
                try:
                    # Ensure the file has a valid name - FileExtensionValidator needs this
                    file_name = getattr(certificate_sample, 'name', None)
                    if not file_name:
                        # Try to get name from other attributes
                        file_name = getattr(certificate_sample, '_name', None) or getattr(certificate_sample, 'filename', None)
                    
                    if file_name:
                        # Ensure file_name is a string for FileExtensionValidator
                        if not isinstance(file_name, str):
                            file_name = str(file_name) if file_name is not None else "certificate.pdf"
                        # Set the name if it's not already set
                        if not hasattr(certificate_sample, 'name') or not certificate_sample.name:
                            certificate_sample.name = file_name
                        course.certificate_sample = certificate_sample
                        course.save()
                    else:
                        logger.warning("Certificate sample file has no name attribute - skipping save")
                        messages.warning(request, "Certificate sample file has no name and could not be saved.")
                except TypeError as e:
                    if "expected string or bytes-like object" in str(e):
                        logger.error(f"FileExtensionValidator error: File name is None or invalid. Error: {e}", exc_info=True)
                        messages.error(request, "Certificate sample file name is invalid. Please ensure the file has a valid name.")
                    else:
                        raise
                except Exception as e:
                    logger.error(f"Error saving certificate sample: {e}", exc_info=True)
                    messages.warning(request, f"Certificate sample could not be saved: {e}")
        except TypeError as e:
            if "expected string or bytes-like object, got 'NoneType'" in str(e):
                logger.error(f"NoneType error in add_course POST processing: {e}", exc_info=True)
                messages.error(request, f"Error processing form data: A required field was empty. Please check all fields are filled correctly.")
                return render(request, "superadmin/add_course.html", {})
            raise
        
        # Extract and create sections
        sections_data = {}
        import re
        
        # Debug: Print all POST keys to see the structure
        # Use module-level logger (defined at top of file)
        logger.info("POST data keys:")
        for key in request.POST.keys():
            if key.startswith('sections['):
                logger.info(f"  {key} = {request.POST.get(key)}")
        
        for key, value in request.POST.items():
            # Ensure key is a string
            if not key or not isinstance(key, str):
                continue
            if key.startswith('sections['):
                # Parse: sections[1][title], sections[1][units][1][ref], etc.
                # Use a more specific pattern that handles nested brackets correctly
                try:
                    section_match = re.match(r'sections\[(\d+)\]\[([^\]]+)\](?:\[([^\]]+)\])?(?:\[([^\]]+)\])?', str(key))
                except (TypeError, AttributeError) as e:
                    logger.warning(f"Error matching regex pattern for key '{key}': {e}")
                    continue
                
                if section_match:
                    section_id = section_match.group(1)
                    first_key = section_match.group(2)
                    second_key = section_match.group(3)
                    third_key = section_match.group(4)
                    
                    if section_id not in sections_data:
                        sections_data[section_id] = {'units': {}}
                    
                    # Check if this is a unit field: sections[1][units][1][ref]
                    if first_key == 'units' and second_key and third_key:
                        unit_id = second_key
                        unit_field = third_key
                        
                        if unit_id not in sections_data[section_id]['units']:
                            sections_data[section_id]['units'][unit_id] = {}
                        # Ensure value is a string, not None
                        safe_value = str(value) if value is not None else ""
                        sections_data[section_id]['units'][unit_id][unit_field] = safe_value
                        logger.info(f"  Unit parsed: Section {section_id}, Unit {unit_id}, Field {unit_field} = {safe_value}")
                    else:
                        # Regular section field: sections[1][title]
                        # Ensure value is a string, not None
                        safe_value = str(value) if value is not None else ""
                        sections_data[section_id][first_key] = safe_value
        
        # Debug: Print sections_data structure
        logger.info(f"Parsed sections_data: {sections_data}")
        
        # Create sections and units
        from .models import QualificationSection, QualificationUnit
        
        for section_id, section_info in sections_data.items():
            section = QualificationSection.objects.create(
                course=course,
                section_title=str(section_info.get('title', '') or ''),
                order=int(section_info.get('order') or section_id),
                credits=int(section_info.get('credits') or 120),
                tqt_hours=int(section_info.get('tqt') or 1200),
                glh_hours=int(section_info.get('glh') or 600),
                remarks=str(section_info.get('remarks', 'Grade Pass') or 'Grade Pass'),
            )
            
            # Create units for this section
            units_dict = section_info.get('units', {})
            logger.info(f"Creating units for section {section_id}: {len(units_dict)} units found")
            
            for unit_id, unit_info in units_dict.items():
                logger.info(f"  Processing unit {unit_id}: {unit_info}")
                unit_ref = unit_info.get('ref') or ''
                unit_title = unit_info.get('title') or ''
                if unit_ref and unit_title:
                    unit = QualificationUnit.objects.create(
                        section=section,
                        unit_ref=str(unit_ref),
                        unit_title=str(unit_title),
                        order=int(unit_info.get('order', unit_id) or unit_id),
                        credits=int(unit_info.get('credits') or 0),
                        glh_hours=int(unit_info.get('glh') or 0),
                    )
                    logger.info(f"    Created unit: {unit.unit_ref} - {unit.unit_title}")
                else:
                    logger.warning(f"    Skipped unit {unit_id}: missing ref or title. Data: {unit_info}")
        
        messages.success(request, f'Qualification "{course.title}" added successfully with {len(sections_data)} section(s).')
        return redirect(reverse("superadmin:course_list"))
    
    return render(request, "superadmin/add_course.html", {})

@login_required
def course_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Not authorized.")
    courses = Course.objects.all().select_related()

    # Search filter
    q = request.GET.get("q", "").strip()
    if q:
        courses = courses.filter(
            Q(title__icontains=q) |
            Q(course_number__icontains=q) |
            Q(category__icontains=q)
        )

    # Certificate sample filter
    cert_sample = request.GET.get("cert_sample", "").strip()
    if cert_sample == "yes":
        # Courses that have a certificate sample (not null and not empty)
        # This matches the template check: {% if c.certificate_sample %}
        courses = courses.exclude(Q(certificate_sample__isnull=True) | Q(certificate_sample=""))
    elif cert_sample == "no":
        # Courses that don't have a certificate sample (null or empty)
        courses = courses.filter(Q(certificate_sample__isnull=True) | Q(certificate_sample=""))

    courses = courses.order_by("-created_at")

    return render(request, "superadmin/course_list.html", {
        "courses": courses,
        "q": q,
        "cert_sample": cert_sample,
    })


@login_required
def view_certificate_sample(request, course_id: int):
    """
    Serve the certificate sample PDF for a course.
    Allows access to:
    - Superusers (all courses)
    - Business partners (only courses assigned to their business)
    """
    course = get_object_or_404(Course, pk=course_id)
    
    # Check if user is superuser
    is_superuser = request.user.is_superuser
    
    # Check if user is a business partner
    is_partner = hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER)
    
    # If not superuser, check if partner has access to this course
    if not is_superuser:
        if not is_partner:
            raise PermissionDenied("Not authorized.")
        
        # Check if the course is assigned to the partner's business
        partner_businesses = Business.objects.filter(email__iexact=request.user.email)
        if not partner_businesses.exists():
            raise PermissionDenied("No business found for your account.")
        
        # Verify the course is assigned to at least one of the partner's businesses
        course_assigned = Course.objects.filter(
            pk=course_id,
            businesses__in=partner_businesses
        ).exists()
        
        if not course_assigned:
            raise PermissionDenied("You do not have access to this course.")
    
    if not course.certificate_sample:
        raise Http404("Certificate sample not found.")
    
    try:
        # Open the file from storage
        with course.certificate_sample.open("rb") as f:
            pdf_data = f.read()
        
        # Return PDF as inline response
        response = HttpResponse(pdf_data, content_type="application/pdf")
        safe_filename = slugify(course.title or "certificate_sample").replace("-", "_") or "certificate_sample"
        response["Content-Disposition"] = f'inline; filename="{safe_filename}.pdf"'
        response["Cache-Control"] = "public, max-age=3600"
        return response
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serving certificate sample for course {course_id}: {e}")
        raise Http404("Certificate sample file could not be loaded.")


@login_required
def edit_course(request, pk: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Not authorized.")
    course = get_object_or_404(
        Course.objects.prefetch_related('sections__units'),
        pk=pk
    )

    if request.method == "POST":
        from .models import QualificationSection, QualificationUnit
        import re
        
        # Update basic course data
        course.title = request.POST.get('title', '').strip()
        course.course_number = request.POST.get('course_number', '').strip()
        course.category = request.POST.get('category', '').strip()
        
        # Update duration and credit hours
        duration = request.POST.get('duration', '').strip()
        credit_hours = request.POST.get('credit_hours', '0').strip()
        from decimal import Decimal
        course.duration = duration
        course.credit_hours = Decimal(credit_hours) if credit_hours else Decimal('0')
        
        # Handle certificate sample upload
        certificate_sample = request.FILES.get('certificate_sample')
        if certificate_sample:
            course.certificate_sample = certificate_sample
        
        certificate_template = request.FILES.get('certificate_template')
        if certificate_template:
            try:
                file_name = getattr(certificate_template, 'name', None)
                if not file_name:
                    file_name = getattr(certificate_template, '_name', None) or getattr(certificate_template, 'filename', None)
                
                if file_name:
                    if not isinstance(file_name, str):
                        file_name = str(file_name) if file_name is not None else "certificate_template.png"
                    if not hasattr(certificate_template, 'name') or not certificate_template.name:
                        certificate_template.name = file_name
                    course.certificate_template = certificate_template
                else:
                    logger.warning("Certificate template file has no name attribute - skipping save")
                    messages.warning(request, "Certificate template file has no name and could not be saved.")
            except Exception as e:
                logger.error(f"Error saving certificate template: {e}", exc_info=True)
                messages.warning(request, f"Certificate template could not be saved: {e}")
        else:
            # If no template uploaded and course doesn't have one, try to set default
            if not course.certificate_template:
                default_path = _get_default_certificate_template()
                if default_path:
                    try:
                        from django.core.files import File
                        with open(default_path, 'rb') as f:
                            file_name = os.path.basename(default_path)
                            course.certificate_template.save(file_name, File(f), save=False)
                            logger.info(f"Applied default certificate template to course {course.id}")
                    except Exception as e:
                        logger.error(f"Error applying default certificate template: {e}", exc_info=True)
        
        course.save()
        
        # Handle section deletions
        delete_sections = request.POST.getlist('delete_sections[]')
        if delete_sections:
            QualificationSection.objects.filter(id__in=delete_sections).delete()
        
        # Handle unit deletions
        delete_units = request.POST.getlist('delete_units[]')
        if delete_units:
            QualificationUnit.objects.filter(id__in=delete_units).delete()
        
        # Extract and process sections
        sections_data = {}
        for key, value in request.POST.items():
            if key.startswith('sections['):
                # Use a more specific pattern that handles nested brackets correctly
                section_match = re.match(r'sections\[([^\]]+)\]\[([^\]]+)\](?:\[([^\]]+)\])?(?:\[([^\]]+)\])?', key)
                
                if section_match:
                    section_id = section_match.group(1)
                    first_key = section_match.group(2)
                    second_key = section_match.group(3)
                    third_key = section_match.group(4)
                    
                    if section_id not in sections_data:
                        sections_data[section_id] = {'units': {}}
                    
                    # Check if this is a unit field: sections[1][units][1][ref]
                    if first_key == 'units' and second_key and third_key:
                        unit_id = second_key
                        unit_field = third_key
                        
                        if unit_id not in sections_data[section_id]['units']:
                            sections_data[section_id]['units'][unit_id] = {}
                        sections_data[section_id]['units'][unit_id][unit_field] = value
                    else:
                        # Regular section field or id
                        sections_data[section_id][first_key] = value
        
        # Update or create sections
        for section_id, section_info in sections_data.items():
            if section_info.get('id'):
                # Update existing section
                section = QualificationSection.objects.filter(id=section_info['id']).first()
                if section:
                    section.section_title = section_info.get('title', '')
                    section.order = int(section_info.get('order', 1))
                    section.credits = int(section_info.get('credits', 120))
                    section.tqt_hours = int(section_info.get('tqt', 1200))
                    section.glh_hours = int(section_info.get('glh', 600))
                    section.remarks = section_info.get('remarks', 'Grade Pass')
                    section.save()
            else:
                # Create new section
                section = QualificationSection.objects.create(
                    course=course,
                    section_title=section_info.get('title', ''),
                    order=int(section_info.get('order', 1)),
                    credits=int(section_info.get('credits', 120)),
                    tqt_hours=int(section_info.get('tqt', 1200)),
                    glh_hours=int(section_info.get('glh', 600)),
                    remarks=section_info.get('remarks', 'Grade Pass'),
                )
            
            # Process units for this section
            for unit_id, unit_info in section_info.get('units', {}).items():
                if unit_info.get('ref') and unit_info.get('title'):
                    if unit_info.get('id'):
                        # Update existing unit
                        unit = QualificationUnit.objects.filter(id=unit_info['id']).first()
                        if unit:
                            unit.unit_ref = unit_info['ref']
                            unit.unit_title = unit_info['title']
                            unit.order = int(unit_info.get('order', 1))
                            unit.credits = int(unit_info.get('credits') or 0)
                            unit.glh_hours = int(unit_info.get('glh') or 0)
                            unit.save()
                    else:
                        # Create new unit
                        QualificationUnit.objects.create(
                            section=section,
                            unit_ref=unit_info['ref'],
                            unit_title=unit_info['title'],
                            order=int(unit_info.get('order', 1)),
                            credits=int(unit_info.get('credits') or 0),
                            glh_hours=int(unit_info.get('glh') or 0),
                        )
        
        # Renumber all sections to keep them sequential (1, 2, 3, ...)
        sections_to_renumber = course.sections.all().order_by('order')
        for index, section in enumerate(sections_to_renumber, start=1):
            if section.order != index:
                section.order = index
                section.save(update_fields=['order'])
        
        messages.success(request, f'Qualification "{course.title}" updated successfully.')
        return redirect(reverse("superadmin:course_list"))
    
    return render(request, "superadmin/edit_course.html", {"course": course})



@login_required
def assign_course(request, pk: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can assign courses.")

    course = get_object_or_404(Course, pk=pk)

    # Assuming your Course model has M2M field named `businesses`
    # If your field name differs, replace `businesses` below accordingly.
    assigned_ids = course.businesses.values_list("id", flat=True)

    # Base queryset = only businesses not already assigned to this course
    qs = Business.objects.exclude(id__in=assigned_ids)

    # Search (GET param ?q=)
    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) |
            Q(business_name__icontains=q) |
            Q(email__icontains=q) |
            Q(country__icontains=q)
        )

    if request.method == "POST":
        selected_ids = request.POST.getlist("business_ids")  # strings
        if not selected_ids:
            messages.warning(request, "Please select at least one business to assign.")
            return redirect(f"{reverse('superadmin:assign_course', args=[course.id])}?q={q}")

        # Only allow assigning from the unassigned set
        valid_to_assign = Business.objects.filter(id__in=selected_ids).exclude(id__in=assigned_ids)
        count = valid_to_assign.count()
        if count:
            course.businesses.add(*valid_to_assign)
            messages.success(request, f"Assigned course “{course.title}” to {count} business(es).")
        else:
            messages.info(request, "No new businesses were assigned (they may already be assigned).")

        return redirect(reverse("superadmin:course_list"))

    context = {
        "course": course,
        "businesses": qs.order_by("business_name", "name"),
        "query": q,
    }
    return render(request, "superadmin/assign_course.html", context)



@login_required
def assignment(request, pk: int):
    """
    Show businesses already assigned to this course.
    Allow superuser to Unassign per business.
    """
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can manage assignments.")

    course = get_object_or_404(Course, pk=pk)

    # Server-side search
    q = (request.GET.get("q") or "").strip()
    assigned_qs = (
        course.businesses
        .annotate(
            certificates_issued_count=Count(
                "registrations",
                filter=Q(
                    registrations__course=course,
                    registrations__certificate_issued_at__isnull=False,
                ),
                distinct=True,
            ),
            pending_count=Count(
                "registrations",
                filter=Q(
                    registrations__course=course,
                    registrations__certificate_issued_at__isnull=True,
                ),
                distinct=True,
            ),
        )
    )
    if q:
        assigned_qs = assigned_qs.filter(
            Q(name__icontains=q) |
            Q(business_name__icontains=q) |
            Q(email__icontains=q) |
            Q(country__icontains=q)
        )

    if request.method == "POST":
        biz_id = request.POST.get("unassign_business_id")
        if biz_id:
            b = Business.objects.filter(pk=biz_id).first()
            if b:
                course.businesses.remove(b)  # <— change field name if needed
                messages.success(request, f'Unassigned "{b.business_name or b.name}" from “{course.title}”.')
            else:
                messages.warning(request, "Business not found or already unassigned.")

        # Preserve the query on redirect
        redirect_url = reverse("superadmin:assignment", args=[course.id])
        if q:
            redirect_url += f"?q={q}"
        return redirect(redirect_url)

    context = {
        "course": course,
        "assigned": assigned_qs.order_by("business_name", "name"),
        "query": q,
    }
    return render(request, "superadmin/assignment.html", context)


@login_required
def business_details(request, business_id: int):
    # Only staff/superusers should access
    if not request.user.is_staff:
        raise PermissionDenied("Not allowed.")
    business = get_object_or_404(Business, pk=business_id)
    
    # Annotate courses with learner count for this business
    assigned_courses = business.courses.annotate(
        learner_count=Count(
            'registrations',
            filter=Q(registrations__business_id=business_id),
            distinct=True
        )
    ).order_by("title")
    
    return render(
        request,
        "superadmin/business_details.html",
        {"business": business, "assigned_courses": assigned_courses},
    )

@login_required
def unassign_course_from_business(request, business_id: int, course_id: int):
    if request.method != "POST":
        raise PermissionDenied("Invalid method.")

    if not request.user.is_staff:
        raise PermissionDenied("Not allowed.")

    business = get_object_or_404(Business, pk=business_id)
    course = get_object_or_404(Course, pk=course_id)

    # Remove the M2M link
    # Either works: business.courses.remove(course) OR course.assigned_to.remove(business)
    business.courses.remove(course)

    messages.success(request, f"Unassigned “{course.title}” from “{business.business_name or business.name}”.")
    return redirect("superadmin:business_details", business_id=business.id)


@login_required
def business_courses(request):
    """
    List courses assigned to the current partner's business (matched by email).
    """
    # Only partners are allowed here (mirror your other partner checks)
    if hasattr(request.user, "has_role") and not request.user.has_role("partner"):
        raise PermissionDenied("Not a partner.")

    # Match Business by the owner email
    businesses = Business.objects.filter(email__iexact=request.user.email)

    if not businesses.exists():
        messages.error(request, "No business found for your account.")
        return redirect("superadmin:business_dashboard")

    # Collect courses assigned to any of the user's businesses
    courses = Course.objects.filter(businesses__in=businesses).distinct().order_by("title")


    return render(
        request,
        "superadmin/business_courses.html",
        {"courses": courses},
    )

#assignment from business_details page
@login_required
def assign_courses(request, business_id: int):
    """
    Show all courses NOT yet assigned to this business, allow selecting multiple,
    and assign them on submit.
    """
    if not request.user.is_superuser:
        raise PermissionDenied("Only superadmins can assign courses.")

    business = get_object_or_404(Business, pk=business_id)

    # Search filter
    q = (request.GET.get("q") or "").strip()

    # Courses not yet assigned to this business
    courses_qs = Course.objects.exclude(businesses=business)
    if q:
        from django.db.models import Q
        courses_qs = courses_qs.filter(
            Q(title__icontains=q) |
            Q(course_number__icontains=q) |
            Q(category__icontains=q)
        )

    courses_qs = courses_qs.order_by("title")

    if request.method == "POST":
        ids = request.POST.getlist("course_ids")
        if not ids:
            messages.warning(request, "Please select at least one course to assign.")
            return redirect(reverse("superadmin:assign_courses", args=[business.id]))

        to_assign = Course.objects.filter(id__in=ids).exclude(businesses=business)
        if not to_assign.exists():
            messages.info(request, "No new courses to assign.")
            return redirect(reverse("superadmin:business_details", args=[business.id]))

        # Assign in one go via the reverse relation
        business.courses.add(*to_assign)
        messages.success(request, f"Assigned {to_assign.count()} course(s) to {business.business_name or business.name}.")
        return redirect(reverse("superadmin:business_details", args=[business.id]))

    return render(
        request,
        "superadmin/assign_courses.html",
        {
            "business": business,
            "courses": list(courses_qs),
            "q": q,
        },
    )



def send_registration_email(*, user, course, business, portal_url, plain_password=None, training_from=None, training_to=None):
    """
    Sends a styled HTML email to the learner about course registration.
    - If plain_password is provided, treats as a new user (includes credentials).
    - training_from / training_to are optional date objects (rendered as ISO format).
    """
    subject = "Course Registration — LICQUAL"

    # Build a public, absolute logo URL for email clients
    # 1) Prefer EMAIL_LOGO_URL if provided (must be absolute)
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "") or ""

    if not logo_url:
        # 2) Otherwise use the Django static URL (LICQual logo)
        path = static("images/LICQual-Logo.jpg")  # uses settings.STATIC_URL
        # If STATIC_URL is absolute (e.g., CDN), use as-is
        if path.startswith("http://") or path.startswith("https://") or path.startswith("//"):
            logo_url = path
        else:
            # 3) If STATIC_URL is relative, prepend SITE_URL to make it absolute
            site = getattr(settings, "SITE_URL", "")
            logo_url = f"{site.rstrip('/')}{path}" if site else ""


    # Always try to embed the logo inline - email clients often block external images
    # Locate the static file on disk first
    logo_cid = None
    img_bytes = None
    prefer_cid = False
    logo_fs_path = finders.find("images/LICQual-Logo.jpg")
    if logo_fs_path:
        try:
            with open(logo_fs_path, "rb") as f:
                img_bytes = f.read()
            # If we successfully read the file, set logo_cid
            logo_cid = "licqual-logo"
            prefer_cid = True
            # Only use URL if it's a full absolute URL, otherwise prefer inline embedding
            if not (logo_url.startswith("http://") or logo_url.startswith("https://") or logo_url.startswith("//")):
                logo_url = ""  # Clear relative URLs, use inline instead
        except Exception as e:
            # Log error but continue - logo will just not appear
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not load logo for registration email: {e}")
            logo_cid = None
            img_bytes = None

    # Build context with logo_cid preferred; use URL only when CID not available and URL is absolute
    def _is_absolute(u: str) -> bool:
        return u.startswith("http://") or u.startswith("https://") or u.startswith("//")

    final_logo_url = "" if prefer_cid else (logo_url if _is_absolute(logo_url) else "")

    ctx = {
        "logo_url": final_logo_url,
        "logo_cid": logo_cid if prefer_cid else "",
        "learner_name": user.get_full_name() or user.full_name or user.email,
        "learner_email": user.email,
        "business_name": getattr(business, "business_name", "") or getattr(business, "name", ""),
        "course_title": course.title,
        "contact_email": business.email,
        "portal_url": portal_url or "",
        "is_new_user": bool(plain_password),
        "plain_password": plain_password or "",
        "training_from": training_from.isoformat() if training_from else "",
        "training_to": training_to.isoformat() if training_to else "",
    }

    plain_lines = [
        f"Dear {ctx['learner_name']},",
        "",
        f"You have been registered by {ctx['business_name']} for the course:",
        f"{ctx['course_title']}",
        "",
        f"Contact: {ctx['contact_email']}",
    ]
    if ctx["training_from"] or ctx["training_to"]:
        plain_lines.append(f"Training Dates: {ctx['training_from']} to {ctx['training_to']}")
    if ctx["is_new_user"]:
        plain_lines += [
            "",
            "Your Login Credentials:",
            f"Email: {ctx['learner_email']}",
            f"Password: {ctx['plain_password']}",
        ]
    else:
        plain_lines.append("Note: Use 'Forgot Password' on the login page if needed.")
    if ctx["portal_url"]:
        plain_lines += ["", f"Access Training: {ctx['portal_url']}"]
    text_fallback = "\n".join(plain_lines)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "SERVER_EMAIL", None)

    html_body = render_to_string("superadmin/registration_email.html", ctx)

    # Use EmailMultiAlternatives and attach inline image correctly
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_fallback,
        from_email=from_email,
        to=[user.email],
    )
    msg.attach_alternative(html_body, "text/html")

    # Inline images should be sent as multipart/related for best client compatibility.
    msg.mixed_subtype = "related"

    # Attach inline image BEFORE attaching HTML (some email clients need this order)
    if logo_cid and img_bytes:
        img = MIMEImage(img_bytes, _subtype="jpeg")
        img.add_header("Content-ID", f"<{logo_cid}>")
        img.add_header("Content-Disposition", "inline", filename="LICQual-Logo.jpg")
        # Attach to the message's mixed part
        if hasattr(msg, '_container'):
            msg._container.attach(img)
        else:
            msg.attach(img)

    # Send via your SES backend (raw MIME supported)
    # Use fail_silently=True to prevent registration failures if email backend is not configured
    try:
        msg.send(fail_silently=True)
    except Exception as e:
        # Log error but don't raise - let caller handle if needed
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to send registration email: {e}")


def _generate_personalized_diploma(learner_name: str) -> bytes:
    """
    Generate a personalized diploma PDF with the learner's name printed on it.
    Returns PDF bytes. Uses PyPDF2 to overlay text on the existing diploma template.
    """
    # Find the empty diploma template
    diploma_path = finders.find("images/LICQual Diploma -  Template E.pdf")
    if not diploma_path:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("Diploma template not found")
        return None
    
    try:
        # Try to use PyPDF2 or pypdf to overlay text on existing PDF (best method)
        try:
            # Try PyPDF2 first (older but common), then pypdf (newer)
            try:
                import PyPDF2
                PdfReader = PyPDF2.PdfReader
                PdfWriter = PyPDF2.PdfWriter
            except ImportError:
                try:
                    import pypdf as PyPDF2
                    PdfReader = PyPDF2.PdfReader
                    PdfWriter = PyPDF2.PdfWriter
                except ImportError:
                    raise ImportError("Neither PyPDF2 nor pypdf is installed")
            
            from reportlab.pdfgen import canvas as reportlab_canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.colors import black
            from superadmin.certificate_fonts import load_font_for_reportlab
            
            # Read the existing PDF
            with open(diploma_path, "rb") as f:
                existing_pdf = PdfReader(f)
                existing_page = existing_pdf.pages[0]
                page_width = float(existing_page.mediabox.width)
                page_height = float(existing_page.mediabox.height)
            
            # Create a watermark PDF with the name
            watermark_buf = io.BytesIO()
            c = reportlab_canvas.Canvas(watermark_buf, pagesize=(page_width, page_height))
            
            # Register and use font (Raleway for learner name)
            try:
                font_family, font_size = load_font_for_reportlab('learner_name')
                # Use a slightly smaller size for diploma (adjust as needed)
                c.setFont(font_family, 42)
            except Exception:
                c.setFont("Helvetica-Bold", 42)
            
            # Position the name on the diploma
            # Adjust these coordinates based on your diploma template layout
            # Typically, name goes in the center-bottom area of the diploma
            # You may need to adjust y coordinate (0.42 = 42% from bottom) based on your template
            text_width = c.stringWidth(learner_name, c._fontname, 42)
            x = (page_width - text_width) / 2  # Center horizontally
            y = page_height * 0.42  # Adjust vertical position (0.42 = 42% from bottom)
            
            c.setFillColor(black)
            c.drawString(x, y, learner_name.upper())  # Use uppercase for diploma
            c.save()
            watermark_buf.seek(0)
            
            # Merge the watermark with the existing PDF
            watermark_pdf = PdfReader(watermark_buf)
            watermark_page = watermark_pdf.pages[0]
            
            # Create output PDF
            output_buf = io.BytesIO()
            writer = PdfWriter()
            
            # Merge pages (watermark on top)
            existing_page.merge_page(watermark_page)
            writer.add_page(existing_page)
            
            writer.write(output_buf)
            output_buf.seek(0)
            return output_buf.getvalue()
            
        except ImportError:
            # PyPDF2 not available, fallback to empty diploma
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("PyPDF2 not installed. Cannot personalize diploma. Install with: pip install PyPDF2")
            # Return empty diploma as fallback
            with open(diploma_path, "rb") as f:
                return f.read()
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to generate personalized diploma: {e}", exc_info=True)
        # Fallback: return empty diploma
        try:
            with open(diploma_path, "rb") as f:
                return f.read()
        except Exception:
            return None


def send_certificate_issued_email(*, user, course, business, certificate_pdf_bytes=None):
    """
    Sends an email to the learner when their certificate is issued.
    
    Args:
        user: The learner user
        course: The course
        business: The business
        certificate_pdf_bytes: Optional PDF bytes to attach. If None, will generate on-demand.
    """
    import logging
    logger = logging.getLogger(__name__)

    subject = "Certificate Issued — LICQual"

    # Build a public, absolute logo URL for email clients
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "") or ""

    if not logo_url:
        # Use the Django static URL - try multiple possible filenames
        candidate_static_paths = [
            "images/LICQual-Logo.jpg",
            "images/LICQual Logo .jpg",
            "images/LICQual Logo.jpg",
            "images/licqual-logo.jpg",
            "images/ictqual-logo.jpg",
        ]

        for static_path in candidate_static_paths:
            try:
                path = static(static_path)
                if path.startswith("http://") or path.startswith("https://") or path.startswith("//"):
                    logo_url = path
                    break
                site = getattr(settings, "SITE_URL", "")
                if site:
                    logo_url = f"{site.rstrip('/')}{path}"
                    break
            except Exception:
                continue

    # Do not embed the logo inline (CID) for this email. Keep logo_url only if it is an absolute URL.
    logo_cid = None
    img_bytes = None

    # Build context with logo_cid and ensure logo_url is only set if it's absolute
    ctx = {
        "logo_url": logo_url if (logo_url.startswith("http://") or logo_url.startswith("https://") or logo_url.startswith("//")) else "",
        "logo_cid": logo_cid,
        "learner_name": (user.get_full_name() or user.full_name or user.email or "").strip() or "Learner",
        "business_name": (getattr(business, "business_name", "") or getattr(business, "name", "") or "").strip() or "Business",
        "course_title": (course.title or "").strip() or "Course",
    }

    plain_lines = [
        f"Dear {ctx['learner_name']},",
        "",
        f"Congratulations! {ctx['business_name']} has issued your Certificate of Achievement for:",
        f"{ctx['course_title']}",
        "",
        "Your diploma PDF is attached to this email.",
        "",
        "---",
        "This email was sent via LICQual. Please do not reply to this message.",
        "© 2025 LICQual. All rights reserved.",
    ]
    text_fallback = "\n".join(plain_lines)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "SERVER_EMAIL", None)

    html_body = render_to_string("superadmin/certificate_issued_email.html", ctx)

    # Use EmailMultiAlternatives and attach inline image correctly
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_fallback,
        from_email=from_email,
        to=[user.email],
    )
    if logo_cid and img_bytes:
        msg.mixed_subtype = "related"
    msg.attach_alternative(html_body, "text/html")

    # Attach the actual certificate PDF if provided
    if certificate_pdf_bytes:
        try:
            learner_name = ctx.get('learner_name', '') or ''
            learner_name = str(learner_name).strip() if learner_name else "learner"
            safe_name = slugify(learner_name)[:50] or "certificate"
            filename = f"Certificate_{safe_name}.pdf"
            msg.attach(filename, certificate_pdf_bytes, "application/pdf")
            logger.info(f"Attached certificate PDF to email for {user.email}")
        except Exception as e:
            logger.warning(f"Could not attach certificate PDF to email: {e}")
    
    # Send the email
    try:
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        # Log the error but don't fail the certificate issuance
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send certificate issued email to {user.email}: {e}")
        return False


def _send_share_certificate_email_like_share_button(*, reg, certificate_pdf_bytes: bytes) -> tuple[bool, str | None]:
    import base64
    import logging
    import os

    logger = logging.getLogger(__name__)

    # Use the freshest learner name for the attachment filename
    from users.models import CustomUser
    db_alias = getattr(reg._state, "db", "default")
    fu = (
        CustomUser.objects.using(db_alias)
        .only("full_name", "email")
        .get(pk=reg.learner_id)
    )

    safe_name = slugify((fu.full_name or fu.email) or "certificate").replace("-", "_") or "certificate"
    learner_name = fu.full_name or fu.email
    business_name = getattr(reg.business, "business_name", "") or getattr(reg.business, "name", "")
    course_title = reg.course.title

    # Absolute learner dashboard URL if SITE_URL is configured
    base_url = getattr(settings, "SITE_URL", None) or getattr(settings, "PORTAL_URL", None)
    try:
        dash_path = reverse("learners:learner_dashboard")
        dashboard_url = (base_url.rstrip("/") + dash_path) if base_url else dash_path
    except Exception:
        dashboard_url = "#"

    # Logo handling (mirrors learners.views.share_certificate_email)
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "") or None
    logo_cid = None
    logo_base64 = None
    img_bytes = None

    logo_fs_path = None
    for candidate in [
        "images/LICQual-Logo.jpg",
        "images/LICQual Logo .jpg",
        "images/LICQual Logo.jpg",
        "images/licqual-logo.jpg",
        "images/ictqual-logo.jpg",
    ]:
        p = finders.find(candidate)
        if p and os.path.exists(p):
            logo_fs_path = p
            break

    if logo_fs_path and os.path.exists(logo_fs_path):
        try:
            with open(logo_fs_path, "rb") as f:
                img_bytes = f.read()
        except Exception as e:
            logger.error(f"Could not load logo for certificate email: {e}", exc_info=True)
            img_bytes = None

    if img_bytes and len(img_bytes) > 0:
        logo_cid = "licqual-logo"
        final_logo_url = ""
        logo_base64 = None
    else:
        final_logo_url = ""
        if logo_url and (logo_url.startswith("http://") or logo_url.startswith("https://") or logo_url.startswith("//")):
            final_logo_url = logo_url

        if not final_logo_url and img_bytes and len(img_bytes) > 0:
            try:
                if img_bytes.startswith(b"\xff\xd8"):
                    img_mime_type = "image/jpeg"
                elif img_bytes.startswith(b"\x89PNG"):
                    img_mime_type = "image/png"
                elif img_bytes.startswith(b"GIF"):
                    img_mime_type = "image/gif"
                else:
                    img_mime_type = "image/jpeg"
                encoded = base64.b64encode(img_bytes).decode("utf-8")
                logo_base64 = f"data:{img_mime_type};base64,{encoded}"
            except Exception as e:
                logger.warning(f"Could not encode logo as base64: {e}")
                logo_base64 = None

    ctx = {
        "learner_name": learner_name,
        "business_name": business_name,
        "course_title": course_title,
        "dashboard_url": dashboard_url,
        "logo_url": final_logo_url,
        "logo_cid": logo_cid if not final_logo_url else None,
        "logo_base64": logo_base64 if not final_logo_url else None,
    }

    subject = f"Your Certificate • {course_title}"
    html_body = render_to_string("learners/share_certificate_email.html", ctx)
    plain_body = (
        f"Dear {learner_name},\n\n"
        f"Your Certificate for the following course has been issued by {business_name}:\n"
        f"{course_title}\n\n"
        f"You can also access the certificate from your Dashboard:\n{dashboard_url}\n"
    )

    msg = EmailMultiAlternatives(
        subject=subject,
        body=plain_body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None) or getattr(settings, "SERVER_EMAIL", None),
        to=[reg.learner.email],
    )

    if logo_cid and img_bytes and not final_logo_url:
        msg.mixed_subtype = "related"
    msg.attach_alternative(html_body, "text/html")

    if logo_cid and img_bytes and not final_logo_url:
        try:
            from email.mime.image import MIMEImage
            if img_bytes.startswith(b"\xff\xd8"):
                img_type = "jpeg"
            elif img_bytes.startswith(b"\x89PNG"):
                img_type = "png"
            elif img_bytes.startswith(b"GIF"):
                img_type = "gif"
            else:
                img_type = "jpeg"

            img = MIMEImage(img_bytes, _subtype=img_type)
            img.add_header("Content-ID", f"<{logo_cid}>")
            img.add_header("Content-Disposition", "inline", filename="licqual-logo.jpg")
            msg.attach(img)
        except Exception as e:
            logger.warning(f"Could not attach logo image to certificate email: {e}")

    filename = f"{safe_name}.pdf"
    msg.attach(filename, certificate_pdf_bytes, "application/pdf")

    try:
        msg.send(fail_silently=False)
        return True, None
    except Exception as e:
        logger.error(
            f"Failed to send share certificate email to {reg.learner.email}: {e}",
            exc_info=True,
        )
        return False, str(e)


@login_required
def register_learners(request, course_id: int):
    """
    Allow a Partner user to register multiple learners for a course
    that is already assigned to (one of) their business(es).

    Updates:
    - Supports CSV upload (name required, email optional).
    - Provides sample CSV download (?download=sample).
    - If email is blank, a placeholder email is generated and NO email is sent.
    """
    # Only partners can use this page
    if not (hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER)):
        raise PermissionDenied("Only Partner users can register learners.")

    # The partner's businesses are matched by their account email
    partner_businesses = Business.objects.filter(email__iexact=request.user.email)
    if not partner_businesses.exists():
        messages.error(request, "No matching business was found for your account.")
        return redirect("superadmin:business_dashboard")

    course = get_object_or_404(Course, pk=course_id)

    # Prefer an UNRESTRICTED assignment if available
    owning_business = partner_businesses.filter(courses=course, is_restricted=False).first()
    if not owning_business:
        if partner_businesses.filter(courses=course).exists():
            messages.error(
                request,
                "Your Account has been Restricted. You cannot Register Learners. "
                "Please contact Support@ictqualab.co.uk for more details."
            )
            if request.POST.get("csv_upload") or request.FILES.get("csv_file"):
                return redirect("superadmin:registered_learners", course_id=course.id)
            return redirect("superadmin:business_courses")

        raise PermissionDenied("This course is not assigned to your business.")

    # --- Sample CSV download ---
    if request.method == "GET" and request.GET.get("download") == "sample":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = 'attachment; filename="ictqual_learners_sample.csv"'
        writer = csv.writer(resp)
        writer.writerow(["learner_name", "learner_email", "learner_dob"])
        writer.writerow(["Jane Doe", "jane.doe@example.com", "15-03-1990"])
        writer.writerow(["John Smith", "john.smith@example.com", "22-07-1985"])
        return resp


    if request.method == "POST":
        # Collect names/emails/dobs from manual form fields
        names = [ (n or "").strip() for n in request.POST.getlist("learner_name") ]
        emails = [ (e or "").strip().lower() for e in request.POST.getlist("learner_email") ]
        dobs = [ (d or "").strip() for d in request.POST.getlist("learner_dob") ]

        # If CSV uploaded, extend names/emails/dobs with CSV content
        csv_file = request.FILES.get("csv_file")
        if csv_file:
            # Parse CSV (UTF-8 with BOM safe)
            f = None
            try:
                # InMemoryUpload has .file, TemporaryUploadedFile supports wrapped access
                f = io.TextIOWrapper(getattr(csv_file, "file", csv_file), encoding="utf-8-sig")
            except Exception:
                f = io.TextIOWrapper(csv_file, encoding="utf-8-sig")
            try:
                # Try DictReader with headers; fallback to positional
                peek = f.read(4096)
                f.seek(0)
                as_dict = csv.DictReader(f) if "," in peek else None

                if as_dict and as_dict.fieldnames:
                    for row in as_dict:
                        nm = (row.get("learner_name") or "").strip()
                        em = (row.get("learner_email") or "").strip().lower()
                        db = (row.get("learner_dob") or "").strip()
                        # Append rows as-is; validation later
                        names.append(nm)
                        emails.append(em)
                        dobs.append(db)
                else:
                    f.seek(0)
                    for row in csv.reader(f):
                        if not row:
                            continue
                        nm = (row[0] if len(row) > 0 else "").strip()
                        em = ((row[1] if len(row) > 1 else "") or "").strip().lower()
                        db = ((row[2] if len(row) > 2 else "") or "").strip()
                        names.append(nm)
                        emails.append(em)
                        dobs.append(db)
            except Exception:
                messages.error(request, "Could not read CSV. Please ensure it is a valid .csv file.")
                return redirect("superadmin:business_courses")

        # Validate learner data
        valid_learners = []
        error_rows = 0

        # Iterate pairs (pad to longer)
        total = max(len(names), len(emails), len(dobs))
        for i in range(total):
            name = (names[i] if i < len(names) else "").strip()
            email = (emails[i] if i < len(emails) else "").strip().lower()
            dob = (dobs[i] if i < len(dobs) else "").strip()

            # Skip completely empty rows
            if not name and not email and not dob:
                continue

            # Both name and email are REQUIRED
            if not name or not email:
                error_rows += 1
                continue

            # Validate email format
            try:
                validate_email(email)
            except Exception:
                error_rows += 1
                continue

            valid_learners.append({'name': name, 'email': email, 'dob': dob})

        if error_rows:
            messages.error(
                request,
                f"{error_rows} learner(s) not registered due to invalid email ID format, missing name field or missing email field."
            )

        if not valid_learners:
            messages.error(request, "No valid learners to register.")
            return redirect("superadmin:register_learners", course_id=course.id)

        # Register learners directly (payment happens later for advance_payment businesses)
        created_count = 0
        existing_count = 0
        registered_count = 0  # Total registrations (new + existing)

        # Get or create LEARNER role
        learner_role, _ = Role.objects.get_or_create(name=Role.Names.LEARNER)

        # Build a login URL (optional)
        base_url = getattr(settings, "SITE_URL", None)
        try:
            login_path = reverse("users:login")
            portal_url = (base_url.rstrip("/") + login_path) if base_url else login_path
        except Exception:
            portal_url = None

        for learner_data in valid_learners:
            name = learner_data['name']
            email = learner_data['email']

            with transaction.atomic():
                user = CustomUser.objects.filter(email__iexact=email).first()
                plain_password = None

                if not user:
                    plain_password = get_random_string(12)
                    user = CustomUser.objects.create_user(
                        email=email,
                        password=plain_password,
                        full_name=name,
                        is_active=True,
                    )

                    created_count += 1

                # Ensure learner role
                user.roles.add(learner_role)

                # Link registration (allow same learner for same course under different businesses)
                registration, registration_created = LearnerRegistration.objects.get_or_create(
                    course=course,
                    learner=user,
                    business=owning_business,
                )
                
                if registration_created:
                    registered_count += 1
                else:
                    existing_count += 1

                # Send email to valid provided email (fail silently if email backend not configured)
                try:
                    send_registration_email(
                        user=user,
                        course=course,
                        business=owning_business,
                        portal_url=portal_url,
                        plain_password=plain_password,  # None for existing users
                    )
                except Exception as e:
                    # Log error but don't fail registration if email fails
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to send registration email to {user.email}: {e}")

        # Create invoice for the registrations
        if registered_count > 0:
            from pricing.views import get_discounted_price
            from pricing.models import InvoicePayment, InvoicedItem
            from django.utils import timezone
            from decimal import Decimal
            
            # Get pricing with discount
            final_price, base_price, discount_percentage, currency = get_discounted_price(owning_business, course, 'affiliate')
            
            # Calculate total amount
            total_amount = final_price * registered_count
            
            # Determine invoice status based on advance_payment setting
            invoice_status = 'unpaid' if owning_business.advance_payment else 'pending'
            
            # Create invoice
            invoice = InvoicePayment.objects.create(
                business=owning_business,
                invoice_no=f"INV-{timezone.now().strftime('%Y%m%d')}-{owning_business.id}-{course.id}",
                period_start=timezone.now(),
                period_end=timezone.now(),
                status=invoice_status,
            )
            
            # Create invoiced items for each new registration
            new_registrations = LearnerRegistration.objects.filter(
                course=course,
                business=owning_business,
                learner__email__in=[learner['email'] for learner in valid_learners[:registered_count]]
            )
            
            for registration in new_registrations:
                InvoicedItem.objects.create(
                    invoice=invoice,
                    registration=registration,
                    currency=currency,
                    unit_fee=final_price,
                    course_title_snapshot=course.title,
                )
            
            if owning_business.advance_payment:
                messages.success(
                    request,
                    f"{registered_count} Learner{'s' if registered_count != 1 else ''} Have Been Registered. "
                    f"Invoice #{invoice.invoice_no} has been generated for {currency} {total_amount:.2f}. "
                    f"Certificates can be issued once payment is completed."
                )
            else:
                messages.success(
                    request,
                    f"{registered_count} Learner{'s' if registered_count != 1 else ''} Have Been Registered. "
                    f"Invoice #{invoice.invoice_no} has been generated for {currency} {total_amount:.2f}."
                )
        else:
            messages.success(
                request,
                f"{registered_count} Learner{'s' if registered_count != 1 else ''} Have Been Registered."
            )

        if existing_count > 0:
            messages.info(
                request,
                f"{existing_count} learner{'s' if existing_count != 1 else ''} {'are' if existing_count != 1 else 'is'} already registered for this course."
            )

        # Redirect to registered learners page if any registrations were successful (new or existing)
        if registered_count > 0 or existing_count > 0:
            return redirect("superadmin:registered_learners", course_id=course.id)
        else:
            # If no registrations were successful, stay on the register page
            return redirect("superadmin:register_learners", course_id=course.id)


    # Build list of existing emails for this course and business (lowercased)
    existing_emails = list(
        course.registrations.filter(business=owning_business)
        .select_related('learner')
        .values_list('learner__email', flat=True)
    )
    existing_emails_json = mark_safe(json.dumps([(e or '').lower() for e in existing_emails]))

    return render(
        request,
        "superadmin/register_learners.html",
        {
            "course": course,
            "business": owning_business,
            "existing_emails_json": existing_emails_json,
        },
    )


@login_required
@require_POST
def bulk_issue_and_download(request):
    """
    Issue (where applicable) and download certificates for multiple selected registrations.
    - Superusers: can process all selected regs.
    - Partners: can process regs only for their own business (matched by their account email)
                AND the business must not be restricted.
    - Accepts awarded_date parameter that applies to all certificates being issued.
    Returns a ZIP file of certificate PDFs.
    """
    reg_ids = request.POST.getlist("reg_ids")
    course_id = request.POST.get("course_id")
    awarded_date_str = request.POST.get("awarded_date")

    # Validate awarded_date if provided
    awarded_date = None
    if awarded_date_str:
        form = AwardedDateForm({"awarded_date": awarded_date_str})
        if form.is_valid():
            awarded_date = form.cleaned_data['awarded_date']
        else:
            messages.error(request, f"Invalid awarded date: {', '.join([str(v) for v in form.errors.values()])}")
            if course_id and str(course_id).isdigit():
                return redirect("superadmin:registered_learners", course_id=int(course_id))
            return redirect("superadmin:business_courses")
    else:
        # If no date provided, use today (for backward compatibility)
        awarded_date = timezone.now().date()

    # Normalize IDs
    try:
        reg_ids = [int(x) for x in reg_ids if str(x).isdigit()]
    except Exception:
        reg_ids = []

    if not reg_ids:
        messages.error(request, "No learners selected.")
        if course_id and str(course_id).isdigit():
            return redirect("superadmin:registered_learners", course_id=int(course_id))
        return redirect("superadmin:business_courses")

    qs = (
        LearnerRegistration.objects
        .select_related("learner", "course", "business")
        .filter(id__in=reg_ids)
    )

    # Permission: partners limited to their own business and not restricted
    if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER) and not request.user.is_superuser:
        qs = qs.filter(
            business__email__iexact=request.user.email,
            business__is_restricted=False,
        )

    regs = list(qs)
    if not regs:
        messages.error(request, "No permitted learners selected.")
        if course_id and str(course_id).isdigit():
            return redirect("superadmin:registered_learners", course_id=int(course_id))
        return redirect("superadmin:business_courses")

    # Build ZIP in memory
    buf = io.BytesIO()
    added = 0
    newly_issued = []  # Track newly issued certificates for email notifications
    
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for reg in regs:
            # If not issued yet, issue now
            was_newly_issued = False
            needs_regeneration = False
            
            if not reg.certificate_issued_at:
                reg.certificate_issued_at = timezone.now()
                reg.awarded_date = awarded_date
                reg.status = LearnerRegistration.Status.ISSUED
                was_newly_issued = True
                needs_regeneration = True
            else:
                # Already issued - update awarded_date if different to ensure certificate shows correct date
                if reg.awarded_date != awarded_date:
                    reg.awarded_date = awarded_date
                    needs_regeneration = True

            # Ensure certificate number exists (your model assigns on save)
            if not reg.certificate_number:
                reg.save()
            elif needs_regeneration:
                # Save to persist awarded_date change
                reg.save()

            # Generate certificate PDF without saving to storage
            try:
                pdf_bytes = generate_certificate_pdf(reg)
                # Track newly issued certificates for email notification
                if was_newly_issued:
                    newly_issued.append(reg)
            except Exception as e:
                # Skip silently on render failure
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Bulk issue: Certificate generation failed for reg {reg.id}: {e}")
                continue

            if not pdf_bytes or len(pdf_bytes) == 0:
                continue

            # Safe filename: CERTNO_NameOrEmail.pdf
            name_bits = (reg.learner.full_name or reg.learner.email or "learner")
            if name_bits:
                name_bits = str(name_bits).strip() or "learner"
            else:
                name_bits = "learner"
            safe_name = slugify(name_bits)[:50] or "learner"
            certno = (reg.certificate_number or f"reg-{reg.id}").replace("/", "-")
            filename = f"{certno}_{safe_name}.pdf"

            zf.writestr(filename, pdf_bytes)
            added += 1

    if added == 0:
        messages.warning(request, "No certificates were available to download (missing templates or generation failed).")
        if course_id and str(course_id).isdigit():
            return redirect("superadmin:registered_learners", course_id=int(course_id))
        return redirect("superadmin:business_courses")

    # Send email notifications for newly issued certificates
    # Note: For bulk operations, we generate PDFs again for email (they're not saved)
    for reg in newly_issued:
        try:
            # Generate PDF for email attachment
            pdf_bytes = generate_certificate_pdf(reg)
            send_certificate_issued_email(
                user=reg.learner,
                course=reg.course,
                business=reg.business,
                certificate_pdf_bytes=pdf_bytes
            )
        except Exception as e:
            # Log the error but don't fail the bulk operation
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Bulk issue: Certificate issued but email failed for {reg.learner.email}: {e}")

    buf.seek(0)
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"certificates_{ts}.zip"
    resp = HttpResponse(buf.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{zip_name}"'
    return resp


@login_required
def registered_learners(request, course_id: int):
    """
    Show learners registered for this course (Partner sees only their business registrations).
    Supports search (q) and status filter (issued/pending).
    """
    course = get_object_or_404(Course, pk=course_id)

    # Scope by role: partners see only their business; superuser sees all
    if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER) and not request.user.is_superuser:
        businesses = Business.objects.filter(email__iexact=request.user.email)
        if not businesses.exists():
            raise PermissionDenied("No business associated with your account.")
        regs = course.registrations.filter(business__in=businesses)
    else:
        regs = course.registrations.all()

    # Search by name/email
    q = request.GET.get("q", "").strip()
    if q:
        regs = regs.filter(
            Q(learner__full_name__icontains=q) |
            Q(learner__email__icontains=q)
        )

    # Filter by action status
    status = request.GET.get("status", "").strip()  # 'issued' or 'pending' or ''
    if status == "issued":
        regs = regs.filter(certificate_issued_at__isnull=False)
    elif status == "pending":
        regs = regs.filter(certificate_issued_at__isnull=True)

    regs = regs.select_related("learner", "business", "course", "invoiced_item__invoice").order_by("-created_at")

    # Summary counts (after server-side q/status filtering)
    total_count = regs.count()
    issued_count = regs.filter(certificate_issued_at__isnull=False).count()
    pending_count = regs.filter(certificate_issued_at__isnull=True).count()

    return render(
        request,
        "superadmin/registered_learners.html",
        {
            "course": course,
            "registrations": regs,
            "q": q,
            "status": status,
            "total_count": total_count,
            "issued_count": issued_count,
            "pending_count": pending_count,
        },
    )




@login_required
@require_POST
def delete_registration(request, reg_id: int):
    """
    Delete a learner's registration for this course (row id = reg_id) if:
    - The current user is a Partner and the registration belongs to their business, OR user is superuser.
    - The certificate has NOT been issued yet.
    """
    reg = get_object_or_404(LearnerRegistration.objects.select_related("business", "course"), pk=reg_id)

    # Permission checks
    if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER) and not request.user.is_superuser:
        # Partner can only delete registrations of their own business
        partner_businesses = Business.objects.filter(email__iexact=request.user.email)
        if not partner_businesses.exists() or reg.business_id not in partner_businesses.values_list("id", flat=True):
            messages.error(request, "You are not allowed to delete this registration.")
            return redirect("superadmin:registered_learners", course_id=reg.course_id)

    # Prevent deletion if certificate already issued
    if reg.certificate_issued_at:
        messages.error(request, "Cannot delete. Certificate has already been issued for this learner.")
        return redirect("superadmin:registered_learners", course_id=reg.course_id)

    # Handle related InvoicedItem and InvoicePayment before deletion
    from pricing.models import InvoicedItem, InvoicePayment
    has_invoice = False
    try:
        invoiced_item = InvoicedItem.objects.select_related('invoice').get(registration=reg)
        invoice = invoiced_item.invoice
        has_invoice = True
        
        # Only allow deletion if invoice is unpaid
        if invoice.status == 'paid':
            messages.error(request, "Cannot delete. Payment has already been made for this registration.")
            return redirect("superadmin:registered_learners", course_id=reg.course_id)
        
        # Delete the invoiced item first (this changes the on_delete from PROTECT to allow deletion)
        invoiced_item.delete()
        
        # Check if invoice has any remaining items
        remaining_items_count = InvoicedItem.objects.filter(invoice=invoice).count()
        
        if remaining_items_count == 0:
            # Delete the invoice if it has no more items
            invoice.delete()
            messages.success(request, "Learner registration and associated invoice deleted.")
        else:
            messages.success(request, "Learner registration deleted and invoice amended.")
    except InvoicedItem.DoesNotExist:
        # No invoiced item, just proceed with deletion
        pass
    
    # Safe to delete the registration
    reg.delete()
    
    # Show success message if we haven't already
    if not has_invoice:
        messages.success(request, "Learner registration deleted.")
    
    return redirect("superadmin:registered_learners", course_id=reg.course_id)

@login_required
def issue_certificate(request, reg_id: int):
    """
    Mark a learner registration as 'issued' and generate the certificate file.
    Handles GET (show form) and POST (process with awarded_date).
    """
    reg = get_object_or_404(LearnerRegistration.objects.select_related("course", "business", "learner"), pk=reg_id)

    # Permission: Partner must own the business; superuser allowed
    if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER) and not request.user.is_superuser:
        if not Business.objects.filter(email__iexact=request.user.email, pk=reg.business_id).exists():
            raise PermissionDenied("You cannot modify this registration.")

    if request.method == "GET":
        # Return JSON for AJAX modal requests, or render form
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            form = AwardedDateForm()
            # Set min/max dates for the form
            today = timezone.now().date()
            max_past_date = today - timedelta(days=60)
            return JsonResponse({
                'form_html': form.as_p(),
                'min_date': max_past_date.strftime('%Y-%m-%d'),
                'max_date': today.strftime('%Y-%m-%d'),
            })
        # For non-AJAX GET, show form in a modal (handled by template)
        form = AwardedDateForm()
        return render(request, 'superadmin/issue_certificate_modal.html', {
            'registration': reg,
            'form': form,
        })

    if request.method != "POST":
        messages.error(request, "Invalid method.")
        return redirect("superadmin:registered_learners", course_id=reg.course_id)

    # Process POST with awarded_date form
    form = AwardedDateForm(request.POST)
    if not form.is_valid():
        error_msg = f"Invalid awarded date: {', '.join([str(v) for v in form.errors.values()])}"
        messages.error(request, error_msg)
        
        # If AJAX request, return JSON error
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({
                'success': False,
                'message': error_msg
            }, status=400)
        
        # Determine redirect URL based on referer or default
        referer = request.META.get('HTTP_REFERER', '')
        if 'all-registered-learners' in referer:
            return redirect("superadmin:all_registered_learners")
        return redirect("superadmin:registered_learners", course_id=reg.course_id)

    awarded_date = form.cleaned_data['awarded_date']

    # Mark issued (do NOT use update_fields to allow model.save() to populate certificate_number/status)
    reg.certificate_issued_at = timezone.now()
    reg.awarded_date = awarded_date
    reg.status = LearnerRegistration.Status.ISSUED
    reg.save()  # important: no update_fields

    # Generate certificate PDF without saving to storage
    try:
        logger.info(f"Starting certificate generation for registration {reg_id}")
        logger.info(f"Registration details - Certificate Number: {reg.certificate_number}, Learner Number: {reg.learner_number}")
        
        # Generate PDF bytes without saving to storage
        pdf_bytes = generate_certificate_pdf(reg)
        
        if not pdf_bytes or len(pdf_bytes) == 0:
            logger.error(f"Certificate generation completed but PDF is empty for registration {reg_id}")
            error_msg = "Certificate generation failed: PDF was not created. Please check server logs and contact support."
            messages.error(request, error_msg)
            
            # If AJAX request, return JSON error
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({
                    'success': False,
                    'message': error_msg
                }, status=500)
            
            referer = request.META.get('HTTP_REFERER', '')
            if 'all-registered-learners' in referer:
                return redirect("superadmin:all_registered_learners")
            return redirect("superadmin:registered_learners", course_id=reg.course_id)
        else:
            logger.info(f"Certificate successfully generated for registration {reg_id} (not saved to storage)")
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Certificate generation failed for registration {reg_id}: {e}\n{error_traceback}")
        
        # Determine user-friendly error message
        error_msg = str(e)
        if "template" in error_msg.lower() or "file" in error_msg.lower():
            user_msg = f"Certificate generation failed: Missing template files. Error: {error_msg[:200]}"
        elif "font" in error_msg.lower():
            user_msg = f"Certificate generation failed: Font issue. Error: {error_msg[:200]}"
        elif "NoneType" in error_msg or "expected string" in error_msg or "Missing required certificate data" in error_msg or "AWS S3 storage" in error_msg or "storage configuration" in error_msg:
            # Extract the detailed error message if available
            if "Missing required certificate data" in error_msg:
                # Show the full detailed error message
                user_msg = error_msg[:500]  # Show more characters for detailed errors
            elif "AWS S3 storage" in error_msg or "storage configuration" in error_msg:
                # Show the full storage configuration error
                user_msg = error_msg[:500]
            elif "bucket" in error_msg.lower() or "s3" in error_msg.lower():
                # S3 storage configuration issue
                user_msg = "Certificate generation failed: AWS S3 storage is not properly configured. Please check your .env file and ensure AWS_STORAGE_BUCKET_NAME is set, or set USE_REMOTE_MEDIA=False to use local storage."
            else:
                user_msg = f"Certificate generation failed: Missing required data. Error: {error_msg[:200]}. Please ensure all course sections and learner information are complete."
        else:
            user_msg = f"Certificate generation failed: {error_msg[:200]}"
        
        messages.error(request, user_msg)
        
        # If AJAX request, return JSON error
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({
                'success': False,
                'message': user_msg
            }, status=500)
        
        referer = request.META.get('HTTP_REFERER', '')
        if 'all-registered-learners' in referer:
            return redirect("superadmin:all_registered_learners")
        return redirect("superadmin:registered_learners", course_id=reg.course_id)

    # Send certificate email (same logic as Share Certificate button)
    try:
        email_sent, email_err = _send_share_certificate_email_like_share_button(reg=reg, certificate_pdf_bytes=pdf_bytes)
    except Exception as e:
        # Log the error but don't fail the certificate issuance
        logger.warning(f"Certificate issued but email failed: {e}")
        email_sent = False
        email_err = str(e)

    # Mark as shared (so learner can view in dashboard) regardless of email status.
    # If email fails, admin can still re-send using the Share Certificate button.
    LearnerRegistration.objects.filter(pk=reg.pk, certificate_shared_at__isnull=True).update(
        certificate_shared_at=timezone.now()
    )

    messages.success(request, "Certificate issued and shared successfully.")
    if not email_sent:
        err_preview = (email_err or "").strip()
        if len(err_preview) > 220:
            err_preview = err_preview[:220] + "…"
        messages.warning(
            request,
            "Certificate was issued and shared, but the email could not be sent. You can use the Share Certificate button to resend."
            + (f" (Email error: {err_preview})" if err_preview else "")
        )
    
    # If this is an AJAX request, return JSON with download URL
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        from django.urls import reverse
        download_url = reverse('superadmin:download_certificate', args=[reg_id])
        return JsonResponse({
            'success': True,
            'message': 'Certificate issued and shared successfully.' if email_sent else ('Certificate issued and shared successfully (email failed).' + (f' Email error: {err_preview}' if err_preview else '')),
            'download_url': download_url
        })
    
    # Determine redirect URL based on referer or default
    referer = request.META.get('HTTP_REFERER', '')
    if 'all-registered-learners' in referer:
        return redirect("superadmin:all_registered_learners")
    return redirect("superadmin:registered_learners", course_id=reg.course_id)



@login_required
@never_cache
def download_certificate(request, reg_id: int):

    """
    Download the certificate file if present; if missing but issued, generate it on-demand.
    """
    reg = get_object_or_404(LearnerRegistration.objects.select_related("course", "business", "learner"), pk=reg_id)

    # Permission: Partner must own the business; superuser allowed
    if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER) and not request.user.is_superuser:
        if not Business.objects.filter(email__iexact=request.user.email, pk=reg.business_id).exists():
            raise PermissionDenied("You cannot access this certificate.")

    # Determine redirect URL based on referer or next parameter
    def get_redirect_url():
        # Check if there's a next parameter
        next_url = request.GET.get("next") or request.POST.get("next")
        if next_url:
            return next_url
        
        # Check referer to see if user came from learner_specific page
        referer = request.META.get('HTTP_REFERER', '')
        if 'learner_specific' in referer or f'/learners/{reg.learner_id}/' in referer:
            return reverse("superadmin:learner_specific", args=[reg.learner_id])
        
        # Check if from all_registered_learners page
        if 'all-registered-learners' in referer:
            return reverse("superadmin:all_registered_learners")
        
        # Default to registered_learners for the course
        return reverse("superadmin:registered_learners", args=[reg.course_id])

    if not reg.certificate_issued_at:
        messages.error(request, "Certificate has not been issued yet.")
        return redirect(get_redirect_url())

    # Generate certificate PDF on-demand without saving to storage
    try:
        logger.info(f"Generating certificate on-demand for registration {reg_id}")
        logger.info(f"Registration details - Certificate Number: {reg.certificate_number}, Learner Number: {reg.learner_number}")
        
        # Generate PDF bytes without saving
        pdf_bytes = generate_certificate_pdf(reg)
        
        if not pdf_bytes or len(pdf_bytes) == 0:
            import traceback
            error_traceback = traceback.format_exc()
            logger.error(f"Certificate generation completed but PDF is empty for registration {reg_id}\n{error_traceback}")
            messages.error(request, "Certificate file could not be generated. Please check server logs and contact support.")
            return redirect(get_redirect_url())
        
        logger.info(f"Certificate successfully generated on-demand for download: registration {reg_id}")
        
        # Build a clean PDF filename from the learner's name
        from users.models import CustomUser
        db_alias = getattr(reg._state, "db", "default")
        fu = (CustomUser.objects.using(db_alias)
            .only("full_name", "email")
            .get(pk=reg.learner_id))
        learner_name = (fu.full_name or fu.email or "certificate")
        if learner_name:
            learner_name = str(learner_name).strip() or "certificate"
        else:
            learner_name = "certificate"

        safe_name = slugify(learner_name).replace("-", "_") or "certificate"
        download_filename = f"{safe_name}.pdf"
        
        # Return PDF as response
        from io import BytesIO
        pdf_buffer = BytesIO(pdf_bytes)
        fr = FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=download_filename,
            content_type='application/pdf'
        )
        # Prevent client/proxy caching of the binary
        fr["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        fr["Pragma"] = "no-cache"
        logger.info(f"Returning PDF file response: {download_filename}")
        return fr
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(f"Certificate generation failed for registration {reg_id} during download: {e}\n{error_traceback}")
        error_msg = str(e)
        if "NoneType" in error_msg or "expected string" in error_msg:
            messages.error(request, f"Certificate generation failed: Missing required data. Error: {error_msg[:200]}. Please ensure all course sections and learner information are complete.")
        else:
            messages.error(request, f"Certificate generation failed: {error_msg[:200]}")
        return redirect(get_redirect_url())

    # Legacy code for old stored files (kept for backward compatibility but should not be reached)
    if reg.certificate_file:
        try:
            stored_name = (reg.certificate_file.name or "").lower()
            if stored_name.endswith(".pdf"):
                file_handle = reg.certificate_file.open("rb")
                from users.models import CustomUser
                db_alias = getattr(reg._state, "db", "default")
                fu = (CustomUser.objects.using(db_alias)
                    .only("full_name", "email")
                    .get(pk=reg.learner_id))
                learner_name = (fu.full_name or fu.email or "certificate")
                safe_name = slugify(learner_name).replace("-", "_") or "certificate"
                download_filename = f"{safe_name}.pdf"
                fr = FileResponse(
                    file_handle,
                    as_attachment=True,
                    filename=download_filename,
                )
                fr["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                fr["Pragma"] = "no-cache"
                return fr
        except Exception:
            pass

    # Fallback: convert stored image to PDF (legacy support)
    try:
        if reg.certificate_file:
            with reg.certificate_file.open("rb") as f:
                img = Image.open(f).convert("RGB")
            buf = io.BytesIO()
            # Use a decent resolution for print-friendly output
            img.save(buf, format="PDF", resolution=300.0)
            buf.seek(0)
        response = HttpResponse(buf.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{download_filename}"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        return response

    except Exception:
        raise Http404("Certificate file not found or could not be converted to PDF.")


@login_required
@require_POST
def issue_all_certificates(request, course_id: int):
    """
    Issue certificates to all pending registrations for a course.
    """
    course = get_object_or_404(Course, pk=course_id)

    # Scope by role: partners see only their business; superuser sees all
    if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER) and not request.user.is_superuser:
        businesses = Business.objects.filter(email__iexact=request.user.email)
        if not businesses.exists():
            raise PermissionDenied("No business associated with your account.")
        regs = course.registrations.filter(
            business__in=businesses,
            certificate_issued_at__isnull=True
        )
    else:
        regs = course.registrations.filter(certificate_issued_at__isnull=True)

    # Filter out registrations that require payment
    regs = regs.select_related("learner", "business", "course", "invoiced_item__invoice")
    pending_regs = []
    for reg in regs:
        # Skip if payment is required and not paid
        if reg.invoiced_item and reg.invoiced_item.invoice.status == 'unpaid':
            continue
        pending_regs.append(reg)

    if not pending_regs:
        messages.info(request, "No pending certificates to issue (all require payment or are already issued).")
        return redirect("superadmin:registered_learners", course_id=course_id)

    # Use today's date as awarded_date
    awarded_date = timezone.now().date()
    issued_count = 0
    newly_issued = []

    for reg in pending_regs:
        try:
            reg.certificate_issued_at = timezone.now()
            reg.awarded_date = awarded_date
            reg.status = LearnerRegistration.Status.ISSUED
            reg.save()

            # Generate certificate PDF without saving and send email
            try:
                pdf_bytes = generate_certificate_pdf(reg)
                newly_issued.append(reg)
                issued_count += 1
                
                # Send email notification with PDF attached
                send_certificate_issued_email(
                    user=reg.learner,
                    course=reg.course,
                    business=reg.business,
                    certificate_pdf_bytes=pdf_bytes
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Certificate issued but email failed for {reg.learner.email}: {e}")

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to issue certificate for registration {reg.id}: {e}")

    if issued_count > 0:
        messages.success(request, f"Successfully issued {issued_count} certificate(s).")
    else:
        messages.warning(request, "No certificates were issued.")

    return redirect("superadmin:registered_learners", course_id=course_id)


@login_required
@require_POST
def download_all_certificates(request, course_id: int):
    """
    Download all issued certificates for a course as a ZIP file.
    """
    course = get_object_or_404(Course, pk=course_id)

    # Scope by role: partners see only their business; superuser sees all
    if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER) and not request.user.is_superuser:
        businesses = Business.objects.filter(email__iexact=request.user.email)
        if not businesses.exists():
            raise PermissionDenied("No business associated with your account.")
        regs = course.registrations.filter(
            business__in=businesses,
            certificate_issued_at__isnull=False
        )
    else:
        regs = course.registrations.filter(certificate_issued_at__isnull=False)

    regs = regs.select_related("learner", "business", "course")

    if not regs.exists():
        messages.warning(request, "No issued certificates to download.")
        return redirect("superadmin:registered_learners", course_id=course_id)

    # Build ZIP in memory
    buf = io.BytesIO()
    added = 0

    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for reg in regs:
            # Generate certificate PDF on-demand without saving
            try:
                pdf_bytes = generate_certificate_pdf(reg)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Certificate generation failed for reg {reg.id}: {e}")
                continue

            if not pdf_bytes or len(pdf_bytes) == 0:
                continue

            data = pdf_bytes

            # Safe filename: CERTNO_NameOrEmail.pdf
            name_bits = (reg.learner.full_name or reg.learner.email or "learner")
            if name_bits:
                name_bits = str(name_bits).strip() or "learner"
            else:
                name_bits = "learner"
            safe_name = slugify(name_bits)[:50] or "learner"
            certno = (reg.certificate_number or f"reg-{reg.id}").replace("/", "-")
            filename = f"{certno}_{safe_name}.pdf"

            zf.writestr(filename, data)
            added += 1

    if added == 0:
        messages.warning(request, "No certificates were available to download.")
        return redirect("superadmin:registered_learners", course_id=course_id)

    buf.seek(0)
    ts = timezone.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"certificates_{course.course_number}_{ts}.zip"
    resp = HttpResponse(buf.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{zip_name}"'
    return resp


def _date_range_from_request(request):
    """
    Returns (selected_key, start_dt, end_dt_exclusive) where dates are timezone-aware.
    selected_key is one of: today, week, month, quarter, year, custom
    """
    choice = (request.GET.get("range") or "today").lower()
    now = timezone.now()
    start = end = None

    if choice == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

    elif choice == "week":
        # Monday as the first day of week
        start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)

    elif choice == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

    elif choice == "quarter":
        q_start_month = ((now.month - 1) // 3) * 3 + 1
        start = now.replace(month=q_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        # add 3 months to get exclusive end
        if q_start_month >= 10:
            end = start.replace(year=start.year + 1, month=((q_start_month + 3 - 1) % 12) + 1)
        else:
            end = start.replace(month=q_start_month + 3)

    elif choice == "year":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(year=start.year + 1)

    elif choice == "custom":
        start_str = request.GET.get("start")
        end_str = request.GET.get("end")
        try:
            if start_str:
                start_naive = datetime.strptime(start_str, "%Y-%m-%d")
                start = timezone.make_aware(start_naive, timezone.get_current_timezone())
            if end_str:
                end_naive = datetime.strptime(end_str, "%Y-%m-%d")
                # make end exclusive by adding 1 day
                end = timezone.make_aware(end_naive, timezone.get_current_timezone()) + timedelta(days=1)
        except Exception:
            # fallback to today if parsing fails
            choice = "today"
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)

    else:
        # default
        choice = "today"
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

    return choice, start, end




@login_required
def business_performance(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    selected, start, end = _date_range_from_request(request)

    # Training registrations filter (existing logic)
    reg_filter = Q()
    if start and end:
        reg_filter &= Q(
            registrations__created_at__gte=start,
            registrations__created_at__lt=end
        )

    businesses = (
        Business.objects
        .annotate(
            registrations_count=Count("registrations", filter=reg_filter, distinct=True),
        )
        .order_by("business_name", "name")
    )

    # Calculate fees for each business (excluding Simple Solutions Ltd for legacy certificates)
    from pricing.models import CoursePricing
    from decimal import Decimal
    
    for business in businesses:
        total_fee = Decimal("0.00")
        
        # Skip fee calculation for Simple Solutions Ltd (legacy certificates)
        if business.business_name == "Simple Solutions Ltd" or business.name == "Simple Solutions Ltd":
            business.calculated_fee = "—"
            continue
            
        # Calculate fees for issued learner registrations
        issued_registrations = business.registrations.filter(
            certificate_issued_at__isnull=False
        )
        if start and end:
            issued_registrations = issued_registrations.filter(
                certificate_issued_at__gte=start,
                certificate_issued_at__lt=end
            )
        
        for reg in issued_registrations:
            try:
                # Get course pricing
                pricing = CoursePricing.objects.get(course=reg.course)
                base_price = pricing.affiliate_price
                
                # Apply business discount if exists
                final_price = base_price
                try:
                    course_discount = BusinessCourseDiscount.objects.get(business=business, course=reg.course)
                    pct = course_discount.affiliate_discount_percentage
                    if pct and pct > 0:
                        discount_amount = (base_price * pct) / 100
                        final_price = max(Decimal("0.00"), base_price - discount_amount)
                except BusinessCourseDiscount.DoesNotExist:
                    # Fallback to legacy business-wide discount ONLY if the business has no per-course discounts at all.
                    has_any_course_discount = BusinessCourseDiscount.objects.filter(business=business).exists()
                    if not has_any_course_discount:
                        try:
                            discount = business.discount
                            if discount.affiliate_discount_percentage > 0:
                                discount_amount = (base_price * discount.affiliate_discount_percentage) / 100
                                final_price = max(Decimal("0.00"), base_price - discount_amount)
                        except BusinessDiscount.DoesNotExist:
                            pass
                
                total_fee += final_price
            except CoursePricing.DoesNotExist:
                # Use default price if no pricing set
                total_fee += Decimal("20.00")  # Default affiliate price
        
        # Format the fee
        if total_fee > 0:
            business.calculated_fee = f"${total_fee:.2f}"
        else:
            business.calculated_fee = "—"

    # Display range: end is exclusive; show inclusive day
    end_display = (end - timedelta(seconds=1)) if end else None
    start_param = start.date().isoformat() if start else ""
    end_param = end_display.date().isoformat() if end_display else ""

    return render(
        request,
        "superadmin/business_performance.html",
        {
            "businesses": businesses,
            "selected": selected,
            "start": start,
            "end": end_display,
            "start_param": start_param,
            "end_param": end_param,
        },
    )

@login_required
def list_of_learners(request, business_id: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    # Optional course filter
    course_id = request.GET.get("course_id")
    
    # Only apply date filter if no course_id is provided
    # When coming from business_details with course_id, show all learners
    if course_id:
        selected = None
        start = None
        end = None
        end_display = None
    else:
        # Reuse the same helper for date window
        selected, start, end = _date_range_from_request(request)
        end_display = (end - timedelta(seconds=1)) if end else None

    # Optional free-text search
    q = (request.GET.get("q") or "").strip()

    regs = (
        LearnerRegistration.objects
        .select_related("learner", "course", "business")
        .filter(business_id=business_id)
    )
    
    # Filter by course if provided
    if course_id:
        regs = regs.filter(course_id=course_id)
    
    if start and end:
        regs = regs.filter(created_at__gte=start, created_at__lt=end)
    if q:
        regs = regs.filter(
            Q(learner__full_name__icontains=q) |
            Q(learner__email__icontains=q) |
            Q(course__title__icontains=q)
        )

    regs = regs.order_by("-created_at")
    business = Business.objects.get(pk=business_id)
    
    # Get course name if filtering
    course_name = None
    if course_id:
        try:
            from .models import Course
            course = Course.objects.get(pk=course_id)
            course_name = course.title
        except Course.DoesNotExist:
            pass

    return render(
        request,
        "superadmin/list_of_learners.html",
        {
            "business": business,
            "registrations": regs,
            "selected": selected,
            "start": start,
            "end": end_display,
            "q": q,
            "course_id": course_id,
            "course_name": course_name,
        },
    )


@login_required
def toggle_business_restriction(request, business_id: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")
    if request.method != "POST":
        return redirect("superadmin:business_list")

    business = get_object_or_404(Business, pk=business_id)
    business.is_restricted = not business.is_restricted
    business.save(update_fields=["is_restricted"])

    if business.is_restricted:
        messages.success(request, f"{business.business_name or business.name} is now RESTRICTED.")
    else:
        messages.success(request, f"{business.business_name or business.name} is now UNRESTRICTED.")
    return redirect("superadmin:business_list")


@login_required
def all_registered_learners(request):
    """
    Partner-wide view: show ALL learner registrations for ALL courses
    assigned to (any of) the partner's businesses (matched by email).
    Supports search (q) across course/learner and status filter (issued/pending).
    """
    # Only partners
    if hasattr(request.user, "has_role") and not request.user.has_role("partner"):
        raise PermissionDenied("Not a partner.")

    # Partner's businesses by account email
    businesses = Business.objects.filter(email__iexact=request.user.email)
    if not businesses.exists():
        messages.error(request, "No business found for your account.")
        return redirect("superadmin:business_dashboard")

    # Base queryset: all regs for these businesses
    regs = LearnerRegistration.objects.filter(business__in=businesses)

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        regs = regs.filter(
            Q(course__title__icontains=q) |
            Q(course__course_number__icontains=q) |
            Q(learner__full_name__icontains=q) |
            Q(learner__email__icontains=q)
        )

    # Status filter
    status = request.GET.get("status", "").strip()  # '', 'pending', 'issued'
    if status == "issued":
        regs = regs.filter(certificate_issued_at__isnull=False)
    elif status == "pending":
        regs = regs.filter(certificate_issued_at__isnull=True)

    regs = regs.select_related("learner", "business", "course", "invoiced_item__invoice").order_by("-created_at")

    # Summary counts (after server-side q/status filtering)
    total_count = regs.count()
    issued_count = regs.filter(certificate_issued_at__isnull=False).count()
    pending_count = regs.filter(certificate_issued_at__isnull=True).count()

    return render(
        request,
        "superadmin/all_registered_learners.html",
        {
            "registrations": regs,
            "q": q,
            "status": status,
            "total_count": total_count,
            "issued_count": issued_count,
            "pending_count": pending_count,
        },
    )




def _anchor_to_pillow(anchor: str) -> str:
    """
    Pass-through of common two-letter anchors Pillow supports.
    Use: lt, lm, lb, mt, mm, mb, rt, rm, rb. Defaults to 'mm'.
    """
    a = (anchor or "").lower()
    allowed = {"lt","lm","lb","mt","mm","mb","rt","rm","rb"}
    return a if a in allowed else "mm"

# ADD this view (above or below verify_certificate)
def verify_landing(request):
    # just renders the form with no result yet
    return render(request, "superadmin/verify.html", {
        "registration": None,
        "code": "",
    })



def verify_certificate(request, code: str = ""):
    """
    Verifies Training certificates (LearnerRegistration).
    If revoked, show only the revocation message (no details).
    """
    raw_code = (code or request.GET.get("code") or "").strip()
    norm_code = re.sub(r'[^A-Za-z0-9]', '', raw_code)  # remove spaces, hyphens, etc.

    ctx = {
        "code": raw_code,
        "registration": None,   # what the template looks for (training cert)
        "iso_cert": None,       # what the template looks for (ISO cert)
        "revoked": False,
    }

    if not raw_code:
        return render(request, "superadmin/verify.html", ctx)

    # Build a query that matches exactly what the user typed OR the normalized code
    def code_q(field):
        q = Q(**{f"{field}__iexact": raw_code})
        if norm_code and norm_code != raw_code:
            q |= Q(**{f"{field}__iexact": norm_code})
        return q

    # 0) Try ATP (AA000) on Business
    atp_biz = Business.objects.filter(code_q("atp_number")).first()
    if atp_biz:
        ctx["atp_business"] = atp_biz
        return render(request, "superadmin/verify.html", ctx)


    # Training certificates (e.g., AB1234)
    reg = (
        LearnerRegistration.objects
        .select_related("learner", "course", "business")
        .filter(code_q("certificate_number"))
        .first()
    )
    if reg and reg.certificate_issued_at:
        if getattr(reg, "is_revoked", False):
            ctx["revoked"] = True
            return render(request, "superadmin/verify.html", ctx)

        ctx["registration"] = reg
        return render(request, "superadmin/verify.html", ctx)

    # Not found
    return render(request, "superadmin/verify.html", ctx)


def _get_public_site_url() -> str:
    base = getattr(settings, "SITE_URL", "")
    # Ensure base is a string, not None
    if base is None:
        base = ""
    base = str(base).rstrip("/")
    return base or ""


def _verification_url_for(reg: LearnerRegistration) -> str:
    # Ensure certificate_number is a string, not None
    if reg.certificate_number is None or reg.certificate_number == "":
        # Fallback to registration ID if certificate_number is missing
        cert_number = str(reg.id) if reg.id is not None else "0"
    else:
        cert_number = str(reg.certificate_number)
    # Ensure cert_number is not empty
    if not cert_number or cert_number == "None":
        cert_number = str(reg.id) if reg.id is not None else "0"
    try:
        path = reverse("verify_certificate", args=[cert_number])
        # Ensure path is a string
        path = str(path) if path else f"/verify/{cert_number}/"
    except Exception as e:
        logger.error(f"Error generating verification URL for registration {reg.id}: {e}")
        # Fallback to a safe path
        path = f"/verify/{cert_number}/"
    site = _get_public_site_url()
    # Ensure site is a string
    site = str(site) if site else ""
    return f"{site}{path}" if site else path



# ===== LICQUAL CERTIFICATE CONFIGURATION =====

# SCALE FACTOR FOR HIGH-QUALITY TEXT
# Increase this to improve text quality when zooming (e.g., 2.0 = 2x resolution)
# Higher values = sharper text but larger file sizes and slower generation
# Recommended: 2.0 to 3.0 for professional quality
CERTIFICATE_SCALE_FACTOR = 2.0

# Font paths
FONT_CORBEL_REGULAR = "static/fonts/Corbel-Regular.ttf"
FONT_CORBEL_BOLD = "static/fonts/Corbel-Bold.ttf"
FONT_RALEWAY = "static/fonts/Raleway-VariableFont.ttf"
FONT_ROBOTO_REGULAR = "static/fonts/Roboto-Regular.ttf"
FONT_ROBOTO_BOLD = "static/fonts/Roboto-Bold.ttf"
FONT_BOOK_ANTIQUA_REGULAR = "static/fonts/Book Antiqua.ttf"
FONT_BOOK_ANTIQUA_BOLD = "static/fonts/Book Antiqua Bold.ttf"
FONT_BOOK_ANTIQUA_BOLD_ITALIC = "static/fonts/bookantiquabolditalic.ttf"
FONT_MONTSERRAT_REGULAR = "static/fonts/Montserrat-Regular.ttf"
FONT_MONTSERRAT_BOLD = "static/fonts/Montserrat-Bold.ttf"
FONT_CANDARA_REGULAR = "static/fonts/Candara-Regular.ttf"
FONT_CANDARA_BOLD = "static/fonts/Candara-Bold.ttf"

# Page 1 Configuration (LICQual Diploma -  Template E.pdf template)
# Based on the example PDF layout - single page with certificate and transcript sections
# Note: Static labels are on the template, we only overlay VALUES
# 
# ADJUSTABLE PARAMETERS:
# - spacing: Extra pixels between letters (0 = no extra spacing, 2 = default, increase for more space)
# - thickness: Stroke width for font weight (0 = normal, 1 = slightly bold, 2 = bold, 3+ = very bold)
# - align: "left", "center", or "right" for text alignment
PAGE1_CONFIG = {
    # Learner name - appears bold and prominent in the certificate section
    "learner_name": {
        "x": 425, "y": 300, "font": FONT_CANDARA_BOLD, "size": 32, "color": (0, 0, 0), "bold": True, "spacing": 1, "thickness": 0, "align": "center"
    },
    # Qualification title - appears bold below learner name
    "qualification_title": {
        "x": 425, "y": 370, "font": FONT_CANDARA_BOLD, "size": 16, "color": (0, 0, 0), "bold": True, "spacing": 1, "thickness": 0, "align": "center"
    },
    # Business name - appears under "Approved Training Centre"
    "business_name": {
        "x": 425, "y": 500, "font": FONT_CANDARA_BOLD, "size": 16, "color": (255, 255, 255), "bold": True, "spacing": 1, "thickness": 0, "align": "center"
    },
    # Course Number - value appears after the label (label is on template)
    "course_number": {
        "x": 320, "y": 527, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0), "line_height": 14
    },
    # Course Duration (Credits) - value appears after the label (label is on template)
    "course_duration": {
        "x": 320, "y": 543, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0), "line_height": 14
    },
    # Certificate Number - value appears after the label (label is on template)
    "certificate_number": {
        "x": 320, "y": 561, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0), "line_height": 14, "y_offset": -2
    },
    # Issued Date - value appears after the label (label is on template)
    "issued_date": {
        "x": 320, "y": 578, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0), "line_height": 14, "y_offset": -6
    },
    "qr_code": {
        "x": 30, "y": 650, "size": 80
    }
}

# Transcript Section Configuration (on same page as certificate)
# Based on LICQual Diploma.pdf - transcript section appears below certificate
# Note: Static labels are on the template, we only overlay VALUES
# 
# ADJUSTABLE PARAMETERS:
# - thickness: Stroke width for font weight (0 = normal, 1 = slightly bold, 2 = bold, 3+ = very bold)
TRANSCRIPT_CONFIG = {
    # Learner name in transcript section (centered, bold)
    "learner_name": {
        "x": 20, "y": 530, "font": FONT_CANDARA_BOLD, "size": 24, "color": (0, 0, 0), "bold": True, "spacing": 1, "thickness": 0, "align": "center"
    },
    # Course title in transcript section (centered, bold)
    "course_title": {
        "x": 400, "y": 860, "font": FONT_CANDARA_BOLD, "size": 18, "color": (0, 0, 0), "bold": True, "spacing": 1, "thickness": 0, "align": "center"
    },
    # Business name in transcript section (centered, bold)
    "business_name": {
        "x": 400, "y": 900, "font": FONT_CANDARA_BOLD, "size": 16, "color": (0, 0, 0), "bold": True, "spacing": 1, "thickness": 0, "align": "center"
    },
    # Units table - starting position
    "unit_table_start_y": 980,
    "unit_row_height": 24,
    # Table columns: UNIT | TITLE | CREDIT | GLH | GRADE
    "unit_ref": {
        "x": 85, "font": FONT_CANDARA_REGULAR, "size": 10, "color": (0, 0, 0), "thickness": 0  # Moved right to decrease column width from left
    },
    "unit_title": {
        "x": 125, "font": FONT_CANDARA_REGULAR, "size": 10, "color": (0, 0, 0), "thickness": 0  # Moved left to decrease width (space given to CREDIT)
    },
    "unit_credit": {
        "x": 415, "font": FONT_CANDARA_REGULAR, "size": 10, "color": (0, 0, 0), "thickness": 0  # Moved left to increase column width
    },
    "unit_glh": {
        "x": 460, "font": FONT_CANDARA_REGULAR, "size": 10, "color": (0, 0, 0), "thickness": 0  # Moved left to increase column width
    },
    "unit_grade": {
        "x": 495, "font": FONT_CANDARA_REGULAR, "size": 10, "color": (0, 0, 0), "thickness": 0  # Moved right to decrease column width (space given to GLH)
    },
    # Summary line at bottom of transcript
    "total_credits_label": {
        "x": 100, "y": 1200, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0)
    },
    "total_glh_label": {
        "x": 250, "y": 1200, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0)
    },
    "course_number_label": {
        "x": 400, "y": 1200, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0)
    },
    "certificate_number_label": {
        "x": 550, "y": 1200, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0)
    },
    "certificate_date_label": {
        "x": 100, "y": 1230, "font": FONT_CANDARA_REGULAR, "size": 11, "color": (0, 0, 0)
    }
}


def _safe_get_font_path(cfg: dict, default_font: str = None) -> str:
    """Safely get font path from config dictionary"""
    font_path = cfg.get("font")
    if font_path is None:
        logger.warning(f"Config has None font path, using default: {default_font or FONT_CORBEL_REGULAR}")
        return default_font or FONT_CORBEL_REGULAR
    font_path = str(font_path) if font_path else (default_font or FONT_CORBEL_REGULAR)
    if default_font:
        try:
            from django.conf import settings
            # If configured font is missing on disk, fall back to default_font (e.g., Roboto -> Raleway)
            if hasattr(settings, 'BASE_DIR') and settings.BASE_DIR:
                candidate_path = font_path
                if not os.path.isabs(candidate_path):
                    candidate_path = os.path.join(settings.BASE_DIR, candidate_path)
                if not os.path.exists(candidate_path):
                    return default_font
        except Exception:
            return default_font
    return font_path


def _draw_transcript_units_table(draw2: ImageDraw.ImageDraw, all_units_data: list, page2_unit_table_start_y: int, row_height: int) -> tuple[int, int, int]:
    total_units_count = len(all_units_data)

    y_position = _scale(page2_unit_table_start_y)
    scaled_row_height = _scale(row_height)

    table_left = _scale(TRANSCRIPT_CONFIG["unit_ref"]["x"] - 12)
    table_right = _scale(TRANSCRIPT_CONFIG["unit_grade"]["x"] + 50)
    header_row_height = _scale(18)
    header_top = _scale(page2_unit_table_start_y - 20)
    header_bottom = header_top + header_row_height
    table_top = header_bottom
    table_bottom = table_top + (scaled_row_height * total_units_count) if total_units_count > 0 else table_top + scaled_row_height

    border_color = (0, 0, 0)
    border_width = 1
    bright_red = (255, 0, 0)
    white_text = (255, 255, 255)

    draw2.rectangle([table_left, header_top, table_right, header_bottom], fill=bright_red, outline=None)
    draw2.rectangle([table_left, header_top, table_right, table_bottom], outline=border_color, width=border_width)

    header_font = _load_ictqual_font(FONT_CANDARA_BOLD, _scale(11))

    unit_title_x = _scale(TRANSCRIPT_CONFIG["unit_title"]["x"])
    unit_credit_x = _scale(TRANSCRIPT_CONFIG["unit_credit"]["x"])
    unit_glh_x = _scale(TRANSCRIPT_CONFIG["unit_glh"]["x"])
    unit_grade_x = _scale(TRANSCRIPT_CONFIG["unit_grade"]["x"])

    header_divider_positions = [
        unit_title_x - _scale(8),
        unit_credit_x - _scale(8),
        unit_glh_x - _scale(5),
        unit_grade_x - _scale(5),
    ]

    for div_x in header_divider_positions:
        if table_left < div_x < table_right:
            draw2.line([(div_x, header_top), (div_x, table_bottom)], fill=border_color, width=border_width)

    draw2.line([(table_left, header_bottom), (table_right, header_bottom)], fill=border_color, width=border_width)

    def _center_text_in_col(text: str, col_start: int, col_end: int) -> float:
        bbox = draw2.textbbox((0, 0), text, font=header_font)
        tw = bbox[2] - bbox[0]
        return ((col_start + col_end) / 2) - (tw / 2)

    unit_col_start = table_left
    unit_col_end = unit_title_x - _scale(8)
    credit_col_start = unit_credit_x - _scale(8)
    credit_col_end = unit_glh_x - _scale(5)
    glh_col_start = unit_glh_x - _scale(5)
    glh_col_end = unit_grade_x - _scale(5)
    grade_col_start = unit_grade_x - _scale(5)
    grade_col_end = table_right

    header_texts = [
        ("UNIT", _center_text_in_col("UNIT", unit_col_start, unit_col_end)),
        ("TITLE", float(unit_title_x)),
        ("CREDIT", _center_text_in_col("CREDIT", credit_col_start, credit_col_end)),
        ("GLH", _center_text_in_col("GLH", glh_col_start, glh_col_end)),
        ("GRADE", _center_text_in_col("GRADE", grade_col_start, grade_col_end)),
    ]
    for text, tx in header_texts:
        bbox = draw2.textbbox((0, 0), text, font=header_font)
        th = bbox[3] - bbox[1]
        ty = int(header_top + (header_row_height - th) / 2 - bbox[1])
        draw2.text((tx, ty), text, font=header_font, fill=white_text)

    for i in range(1, total_units_count + 1):
        y = y_position + (i * scaled_row_height)
        draw2.line([(table_left, y), (table_right, y)], fill=border_color, width=border_width)

    unit_ref_x_cfg = _scale(TRANSCRIPT_CONFIG["unit_ref"]["x"])

    for row_pos, unit_data in enumerate(all_units_data, start=1):
        unit = unit_data['unit']
        section = unit_data['section']
        section_credits = unit_data['section_credits']
        section_glh = unit_data['section_glh']
        num_units_in_section = unit_data['num_units_in_section']
        unit_idx = unit_data['global_idx']

        cfg = TRANSCRIPT_CONFIG["unit_ref"]
        font = _load_ictqual_font(_safe_get_font_path(cfg, FONT_CANDARA_REGULAR), _scale(cfg["size"]))
        try:
            if unit.unit_ref is None or str(unit.unit_ref).strip() == "":
                unit_ref = f"Unit {unit_idx}"
            else:
                unit_ref = str(unit.unit_ref).strip()
        except Exception:
            unit_ref = f"Unit {unit_idx}"
        unit_column_center = (unit_col_start + unit_col_end) / 2
        unit_ref_bbox = draw2.textbbox((0, 0), unit_ref, font=font)
        unit_ref_text_width = unit_ref_bbox[2] - unit_ref_bbox[0]
        unit_ref_text_height = unit_ref_bbox[3] - unit_ref_bbox[1]
        unit_ref_x = unit_column_center - (unit_ref_text_width / 2)
        unit_ref_y = int(y_position + (scaled_row_height - unit_ref_text_height) / 2 - unit_ref_bbox[1])
        draw2.text((unit_ref_x, unit_ref_y), unit_ref, font=font, fill=(0, 0, 0))

        cfg = TRANSCRIPT_CONFIG["unit_title"]
        font_path = _safe_get_font_path(cfg, FONT_CANDARA_REGULAR)
        try:
            if unit.unit_title is None or str(unit.unit_title).strip() == "":
                raise ValueError(f"Section {section.order}, Unit {unit_idx}: Unit Title is missing")
            unit_title = str(unit.unit_title).strip()
        except ValueError:
            raise
        except Exception:
            unit_title = ""
        title_col_start = unit_title_x
        title_col_end = unit_credit_x - _scale(8)
        cell_top = y_position
        cell_h = scaled_row_height
        title_col_center = (title_col_start + title_col_end) / 2
        max_title_width = max(_scale(40), (title_col_end - title_col_start) - _scale(4))
        max_title_height = max(_scale(10), cell_h - _scale(4))
        title_font, title_lines, title_line_h = _fit_wrapped_text_to_box(
            draw2,
            unit_title,
            font_path,
            _scale(cfg["size"]),
            max_title_width,
            max_title_height,
        )
        if title_lines:
            title_total_h = title_line_h * len(title_lines)
            start_y = int(cell_top + (cell_h - title_total_h) / 2)
            if len(title_lines) == 1:
                one_bbox = draw2.textbbox((0, 0), title_lines[0], font=title_font)
                one_h = (one_bbox[3] - one_bbox[1])
                start_y = int(cell_top + (cell_h - one_h) / 2)
            for i, line in enumerate(title_lines):
                bbox = draw2.textbbox((0, 0), line, font=title_font)
                tw = bbox[2] - bbox[0]
                tx = float(title_col_center - (tw / 2) - bbox[0])
                ty = int(start_y + (i * title_line_h) - bbox[1])
                draw2.text((tx, ty), line, font=title_font, fill=(0, 0, 0))

        cfg = TRANSCRIPT_CONFIG["unit_credit"]
        font = _load_ictqual_font(_safe_get_font_path(cfg, FONT_CANDARA_REGULAR), _scale(cfg["size"]))
        unit_credit_val = int(getattr(unit, "credits", 0) or 0)
        if unit_credit_val == 0 and (section_credits or 0) and num_units_in_section > 0:
            unit_credit_val = section_credits // num_units_in_section
        credit_text = str(unit_credit_val)
        credit_bbox = draw2.textbbox((0, 0), credit_text, font=font)
        credit_text_width = credit_bbox[2] - credit_bbox[0]
        credit_text_height = credit_bbox[3] - credit_bbox[1]
        credit_x = ((credit_col_start + credit_col_end) / 2) - (credit_text_width / 2)
        credit_y = int(y_position + (scaled_row_height - credit_text_height) / 2 - credit_bbox[1])
        draw2.text((credit_x, credit_y), credit_text, font=font, fill=(0, 0, 0))

        cfg = TRANSCRIPT_CONFIG["unit_glh"]
        font = _load_ictqual_font(_safe_get_font_path(cfg, FONT_CANDARA_REGULAR), _scale(cfg["size"]))
        unit_glh_val = int(getattr(unit, "glh_hours", 0) or 0)
        if unit_glh_val == 0 and (section_glh or 0) and num_units_in_section > 0:
            unit_glh_val = section_glh // num_units_in_section
        glh_text = str(unit_glh_val)
        glh_bbox = draw2.textbbox((0, 0), glh_text, font=font)
        glh_text_width = glh_bbox[2] - glh_bbox[0]
        glh_text_height = glh_bbox[3] - glh_bbox[1]
        glh_x = ((glh_col_start + glh_col_end) / 2) - (glh_text_width / 2)
        glh_y = int(y_position + (scaled_row_height - glh_text_height) / 2 - glh_bbox[1])
        draw2.text((glh_x, glh_y), glh_text, font=font, fill=(0, 0, 0))

        cfg = TRANSCRIPT_CONFIG["unit_grade"]
        font = _load_ictqual_font(_safe_get_font_path(cfg, FONT_CANDARA_REGULAR), _scale(cfg["size"]))
        remarks_text = str(section.remarks).strip() if section.remarks else "Pass"
        remarks_lower = remarks_text.lower()
        if "pass" in remarks_lower:
            grade = "Pass"
        elif "fail" in remarks_lower:
            grade = "Fail"
        else:
            grade = "Pass"
        grade_bbox = draw2.textbbox((0, 0), grade, font=font)
        grade_text_width = grade_bbox[2] - grade_bbox[0]
        grade_text_height = grade_bbox[3] - grade_bbox[1]
        grade_x = ((grade_col_start + grade_col_end) / 2) - (grade_text_width / 2)
        grade_y = int(y_position + (scaled_row_height - grade_text_height) / 2 - grade_bbox[1])
        draw2.text((grade_x, grade_y), grade, font=font, fill=(0, 0, 0))

        y_position += scaled_row_height

    return table_bottom, table_left, table_right

def _load_ictqual_font(font_path: str, size: int) -> ImageFont.ImageFont:
    """Load a font from static directory"""
    from django.conf import settings
    # Ensure font_path is a string, not None
    if font_path is None:
        logger.warning(f"_load_ictqual_font received None font_path, using default font")
        return ImageFont.load_default()
    font_path = str(font_path) if font_path else ""
    if not font_path:
        logger.warning(f"_load_ictqual_font received empty font_path, using default font")
        return ImageFont.load_default()
    # Ensure BASE_DIR is not None
    if not hasattr(settings, 'BASE_DIR') or settings.BASE_DIR is None:
        logger.error("settings.BASE_DIR is None, cannot load font")
        return ImageFont.load_default()
    full_path = os.path.join(settings.BASE_DIR, font_path)
    try:
        if os.path.exists(full_path):
            return ImageFont.truetype(full_path, size=size)
    except Exception as e:
        logger.warning(f"Failed to load font from {full_path}: {e}")
    return ImageFont.load_default()


def _open_template_page(page_num: int) -> Image.Image:
    """
    Open the static certificate template PDF and convert to image for drawing.
    Uses LICQual Diploma -  Template E.pdf as the template.
    page_num: 1 for first page, 2+ for subsequent pages (if PDF has multiple pages)
    
    Uses CERTIFICATE_SCALE_FACTOR for upscaling (e.g., 2.0 for 2x resolution)
    """
    from django.conf import settings
    from django.contrib.staticfiles import finders

    # Use the PDF template
    template_file = "LICQual Diploma -  Template E.pdf"
    template_path = finders.find(f"images/{template_file}")
    
    if not template_path:
        # Fallback to direct path
        template_path = os.path.join(settings.BASE_DIR, "static", "images", template_file)
    
    try:
        if os.path.exists(template_path):
            # Try PyMuPDF (fitz) first - easiest to install and works well
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(template_path)
                if page_num <= len(doc):
                    page = doc[page_num - 1]  # 0-indexed
                    # Render at high resolution (zoom factor = scale factor)
                    # 300 DPI base * scale factor
                    zoom = CERTIFICATE_SCALE_FACTOR
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page.get_pixmap(matrix=mat)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    doc.close()
                    logger.info(f"Loaded PDF template page {page_num} using PyMuPDF at {zoom}x zoom")
                    return img
                else:
                    logger.warning(f"PDF has only {len(doc)} pages, requested page {page_num}. Creating blank page with same dimensions.")
                    # Get dimensions from first page to create blank page with same size
                    first_page = doc[0]
                    zoom = CERTIFICATE_SCALE_FACTOR
                    mat = fitz.Matrix(zoom, zoom)
                    pix = first_page.get_pixmap(matrix=mat)
                    base_width, base_height = pix.width, pix.height
                    doc.close()
                    # Create blank page with same dimensions
                    img = Image.new("RGB", (base_width, base_height), "white")
                    logger.info(f"Created blank page {page_num} with dimensions {base_width}x{base_height}")
                    return img
            except ImportError:
                logger.warning("PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF")
            except Exception as e:
                logger.warning(f"Failed to load PDF with PyMuPDF: {e}", exc_info=True)
            
            # Fallback: Try pdf2image if available (requires poppler)
            try:
                from pdf2image import convert_from_path
                # Convert PDF page to image at high DPI (300 DPI for quality)
                dpi = int(300 * CERTIFICATE_SCALE_FACTOR)
                images = convert_from_path(template_path, dpi=dpi, first_page=page_num, last_page=page_num)
                if images:
                    img = images[0].convert("RGB")
                    logger.info(f"Loaded PDF template page {page_num} using pdf2image at {dpi} DPI")
                    return img
                else:
                    # Page doesn't exist, create blank page with same dimensions as first page
                    logger.warning(f"Page {page_num} doesn't exist in PDF. Creating blank page.")
                    first_page_images = convert_from_path(template_path, dpi=dpi, first_page=1, last_page=1)
                    if first_page_images:
                        first_img = first_page_images[0].convert("RGB")
                        base_width, base_height = first_img.size
                        img = Image.new("RGB", (base_width, base_height), "white")
                        logger.info(f"Created blank page {page_num} with dimensions {base_width}x{base_height}")
                        return img
            except ImportError:
                logger.warning("pdf2image not installed. Install it with: pip install pdf2image (requires poppler)")
            except Exception as e:
                logger.warning(f"Failed to load PDF with pdf2image: {e}", exc_info=True)
            
            # Final fallback error
            error_msg = (
                f"PDF template found at {template_path} but cannot convert to image. "
                "Please install one of: pip install PyMuPDF (recommended) or pip install pdf2image"
            )
            logger.error(error_msg)
            raise ImportError(error_msg)
    except Exception as e:
        logger.error(f"Error loading template PDF: {e}", exc_info=True)
        raise
    
    # Fallback: blank A4 landscape (scaled) - only if PDF not found
    logger.warning(f"PDF template not found at {template_path}, using blank template as fallback for page {page_num}")
    # Use same dimensions as would be used for page 1
    base_w, base_h = 2480, 1754
    return Image.new("RGB", (int(base_w * CERTIFICATE_SCALE_FACTOR), int(base_h * CERTIFICATE_SCALE_FACTOR)), "white")



def _scale(value):
    """Scale a coordinate or size value by CERTIFICATE_SCALE_FACTOR"""
    return int(value * CERTIFICATE_SCALE_FACTOR)


def _unscale(value: int) -> int:
    if CERTIFICATE_SCALE_FACTOR == 0:
        return 0
    return int(round(value / CERTIFICATE_SCALE_FACTOR))


def _wrap_text_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    text = "" if text is None else str(text).strip()
    if not text:
        return []
    words = text.split()
    if not words:
        return []

    def _text_width(s: str) -> int:
        bbox = draw.textbbox((0, 0), s, font=font)
        return bbox[2] - bbox[0]

    def _break_long_word(word: str) -> list[str]:
        if not word:
            return [""]
        out: list[str] = []
        chunk = ""
        for ch in word:
            candidate = chunk + ch
            if chunk and _text_width(candidate) > max_width:
                out.append(chunk)
                chunk = ch
            else:
                chunk = candidate
        if chunk:
            out.append(chunk)
        return out

    lines: list[str] = []
    current = words[0]
    if _text_width(current) > max_width:
        broken = _break_long_word(current)
        lines.extend(broken[:-1])
        current = broken[-1]
    for w in words[1:]:
        candidate = f"{current} {w}"
        if _text_width(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = w
            if _text_width(current) > max_width:
                broken = _break_long_word(current)
                lines.extend(broken[:-1])
                current = broken[-1]
    lines.append(current)
    return lines


def _fit_wrapped_text_to_box(draw: ImageDraw.ImageDraw, text: str, font_path: str, base_size_scaled: int, max_width: int, max_height: int) -> tuple[ImageFont.ImageFont, list[str], int]:
    size = max(4, int(base_size_scaled))
    while size >= 4:
        font = _load_ictqual_font(font_path, size)
        lines = _wrap_text_to_width(draw, text, font, max_width)
        if not lines:
            return font, [], 0
        bbox = draw.textbbox((0, 0), "Ag", font=font)
        line_h = (bbox[3] - bbox[1]) + _scale(2)
        total_h = line_h * len(lines)
        if total_h <= max_height:
            return font, lines, line_h
        size -= 1
    font = _load_ictqual_font(font_path, max(4, int(base_size_scaled)))
    lines = _wrap_text_to_width(draw, text, font, max_width)
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_h = (bbox[3] - bbox[1]) + _scale(2)
    return font, lines, line_h


def _draw_wrapped_text(draw: ImageDraw.ImageDraw, text: str, x: int, y: int, font_path: str, base_size_scaled: int, fill: tuple[int, int, int], max_width: int, max_height: int) -> tuple[int, int]:
    font, lines, line_h = _fit_wrapped_text_to_box(draw, text, font_path, base_size_scaled, max_width, max_height)
    if not lines:
        return 0, 0
    for i, line in enumerate(lines):
        draw.text((x, y + (i * line_h)), line, font=font, fill=fill)
    return (line_h * len(lines)), len(lines)


def _format_date_with_ordinal(date_obj):
    """
    Format date with ordinal suffix (e.g., '26th October 2025')
    """
    if not date_obj:
        return ""
    
    try:
        day = date_obj.day
        
        # Determine ordinal suffix
        if 10 <= day % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        
        formatted = date_obj.strftime(f"%d{suffix} %B %Y")
        # Ensure we have a string before calling lstrip
        if formatted:
            return formatted.lstrip('0')
        return formatted
    except (AttributeError, ValueError, TypeError) as e:
        logger.error(f"Error formatting date: {e}, date_obj: {date_obj}")
        return ""


def _draw_text_with_alignment(draw, text: str, x: int, y: int, font, color, align="left", image_width=None):
    """Draw text with alignment (left, center, right)"""
    # Ensure text is a string and not None
    if text is None:
        return
    if not text:
        return
    # Ensure text is a string type
    text = str(text)
    
    if align == "center" and image_width:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (image_width - text_width) // 2
    elif align == "right" and image_width:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = image_width - x - text_width
    
    draw.text((x, y), text, font=font, fill=color)


def _draw_text_with_spacing(draw, text: str, x: int, y: int, font, color, spacing: int = 0, thickness: int = 0):
    """
    Draw text with custom letter spacing and thickness.
    
    Args:
        draw: ImageDraw object
        text: Text to draw
        x, y: Starting position
        font: Font object
        color: Text color (RGB tuple)
        spacing: Extra pixels between characters (default 0)
        thickness: Stroke width for thickness (default 0)
    """
    # Ensure text is a string and not None
    if text is None:
        return
    if not text:
        return
    # Ensure text is a string type
    text = str(text)
    
    current_x = x
    for char in text:
        if thickness > 0:
            draw.text((current_x, y), char, font=font, fill=color, stroke_width=thickness, stroke_fill=color)
        else:
            draw.text((current_x, y), char, font=font, fill=color)
        
        # Get the width of the current character
        bbox = draw.textbbox((0, 0), char, font=font)
        char_width = bbox[2] - bbox[0]
        
        # Move to next character position (character width + spacing)
        current_x += char_width + spacing

def _generate_qr_png_bytes(data: str, size: int = 280) -> bytes:
    """Generate QR code as PNG bytes with high error correction for better scanning"""
    # Ensure data is a string, not None
    if data is None:
        data = ""
    data = str(data)
    
    # Use higher error correction (ERROR_CORRECT_H = ~30% error correction) for better scanning
    # Increase box_size for better quality, and border for quiet zone
    qr = qrcode.QRCode(
        version=None,  # Auto-determine version based on data
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # High error correction (~30%)
        box_size=10,
        border=4  # Larger border (quiet zone) for better scanning
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = img.resize((size, size), Image.Resampling.LANCZOS)  # Use high-quality resampling
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def generate_and_attach_certificate(reg: LearnerRegistration, save_to_storage: bool = True) -> bytes | None:
    """
    Build a multi-page ICTQUAL certificate PDF for the given registration.
    Page 1: General info (learner name, qualification title, business name, QR code)
    Page 2+: Sections with units, awarded date, duration, location, QR code
    
    Args:
        reg: The LearnerRegistration to generate certificate for
        save_to_storage: If True, save PDF to storage. If False, return PDF bytes without saving.
    
    Returns:
        If save_to_storage=False, returns PDF bytes. Otherwise returns None.
    """
    from io import BytesIO
    
    logger.info(f"Starting certificate generation for registration {reg.id}")
    
    # Validate required data before starting
    try:
        # Check course exists and has required fields
        if not reg.course:
            raise ValueError("Registration has no associated course")
        course = reg.course
        if not course.title:
            logger.warning(f"Course {course.id} has no title, using default")
        if not course.course_number:
            logger.warning(f"Course {course.id} has no course_number")
        
        # Check business exists
        if not reg.business:
            raise ValueError("Registration has no associated business")
        business = reg.business
        if not business.business_name and not business.name:
            logger.warning(f"Business {business.id} has no name")
        
        # Check learner exists
        if not reg.learner:
            raise ValueError("Registration has no associated learner")
    except Exception as e:
        logger.error(f"Data validation failed for registration {reg.id}: {e}")
        raise ValueError(f"Invalid registration data: {e}")
    
    # Ensure certificate number exists - save will generate it if missing
    if not reg.certificate_number:
        logger.info(f"Certificate number missing for registration {reg.id}, generating...")
        reg.save()  # This will trigger certificate_number generation in model.save()
        reg.refresh_from_db(fields=["certificate_number", "learner_number"])
    
    # Double-check certificate_number was generated
    if not reg.certificate_number:
        logger.error(f"Certificate number was not generated for registration {reg.id}")
        raise ValueError("Certificate number could not be generated. Please try again.")
    
    logger.info(f"Certificate number: {reg.certificate_number}, Learner number: {reg.learner_number}")
    
    # Get learner and course info
    from users.models import CustomUser
    fresh_user = CustomUser.objects.only("full_name", "email").get(pk=reg.learner_id)
    # Ensure learner_name is a string, not None
    name_val = fresh_user.full_name or fresh_user.email
    learner_name = str(name_val).strip() if name_val is not None else "Learner"
    if not learner_name:
        learner_name = "Learner"
    logger.info(f"Learner name: {learner_name}")
    
    # Get qualification sections and units
    course = reg.course
    sections = course.sections.prefetch_related('units').all().order_by('order')
    
    if not sections.exists():
        logger.error(f"No sections found for course {course.id} ({course.title})")
        raise ValueError(f"Course '{course.title}' has no sections. Please add sections to the course before issuing certificates.")
    
    logger.info(f"Found {sections.count()} section(s) for course {course.id}")
    
    # Validate sections have required data and log warnings
    missing_fields = []
    for section in sections:
        section_num = section.order or sections.count()
        # Check if section has units
        units = section.units.all()
        if not units.exists():
            missing_fields.append(f"Section {section_num} has NO UNITS - each section must have at least one unit")
            logger.error(f"Section {section.id} (order {section.order}) has no units")
        
        # Validate unit data
        for idx, unit in enumerate(units, 1):
            if unit.unit_ref is None or (isinstance(unit.unit_ref, str) and unit.unit_ref.strip() == ""):
                missing_fields.append(f"Section {section_num}, Unit {idx}: UNIT REF is missing or empty")
                logger.error(f"Unit {unit.id} in section {section.id} has None or empty unit_ref")
            if unit.unit_title is None or (isinstance(unit.unit_title, str) and unit.unit_title.strip() == ""):
                missing_fields.append(f"Section {section_num}, Unit {idx}: UNIT TITLE is missing or empty")
                logger.error(f"Unit {unit.id} in section {section.id} has None or empty unit_title")
        
        # Validate section fields
        if section.remarks is None:
            logger.warning(f"Section {section.id} has None remarks - will use default 'Grade Pass'")
        if section.tqt_hours is None:
            logger.warning(f"Section {section.id} has None tqt_hours - will use 0")
        if section.glh_hours is None:
            logger.warning(f"Section {section.id} has None glh_hours - will use 0")
        if section.credits is None:
            logger.warning(f"Section {section.id} has None credits - will use 0")
    
    # If critical fields are missing, raise detailed error
    if missing_fields:
        error_details = "\n".join(f"  - {field}" for field in missing_fields)
        error_msg = f"Missing required certificate data:\n{error_details}\n\nPlease edit the qualification and fill in all required fields."
        logger.error(f"Certificate generation failed for registration {reg.id}:\n{error_msg}")
        raise ValueError(error_msg)
    
    # Generate QR code (scaled size)
    try:
        verify_url = _verification_url_for(reg)
        if not verify_url or verify_url is None:
            verify_url = ""  # Ensure it's a string, not None
        verify_url = str(verify_url) if verify_url else ""
        logger.info(f"Verification URL generated: {verify_url[:50]}...")
    except Exception as e:
        logger.error(f"Error generating verification URL: {e}", exc_info=True)
        verify_url = ""
    qr_bytes = _generate_qr_png_bytes(verify_url, size=_scale(PAGE1_CONFIG["qr_code"]["size"]))
    
    # Create PDF buffer
    buffer = BytesIO()
    pages = []
    
    # ===== PAGE 1: General Information =====
    page1_img = _open_template_page(1)
    draw = ImageDraw.Draw(page1_img)
    img_width, img_height = page1_img.size

    def _draw_page1_value(key: str, value: str) -> None:
        cfg = PAGE1_CONFIG[key]
        font = _load_ictqual_font(_safe_get_font_path(cfg, FONT_CANDARA_REGULAR), _scale(cfg["size"]))
        x = _scale(cfg["x"])
        y = _scale(cfg["y"])
        y_offset = int(cfg.get("y_offset", 0))
        value = value or ""
        bbox = draw.textbbox((0, 0), value, font=font)
        text_h = bbox[3] - bbox[1]
        line_h = _scale(cfg.get("line_height", cfg["size"]))
        y_aligned = int(y + ((line_h - text_h) / 2) - bbox[1] + y_offset)
        draw.text((x, y_aligned), value, font=font, fill=cfg["color"])
    
    # Course Number (value only, label is on template)
    # Ensure course_number is a string before calling strip()
    if course.course_number is None or course.course_number == "":
        course_number = ""
    else:
        course_number = str(course.course_number).strip()
    _draw_page1_value("course_number", course_number)
    
    # Course Duration (Credits) - value only, label is on template
    # Calculate total credits from all sections
    total_credits_for_duration = sum(s.credits if s.credits is not None else 0 for s in sections)
    duration_text = f"{total_credits_for_duration} Credits"
    _draw_page1_value("course_duration", duration_text)
    
    # Certificate Number (value only, label is on template)
    # Safely get certificate_number
    if reg.certificate_number is None or reg.certificate_number == "":
        cert_num = ""
    else:
        cert_num = str(reg.certificate_number)
    _draw_page1_value("certificate_number", cert_num)
    
    # Issued Date (value only, label is on template)
    if reg.awarded_date:
        date_to_format = reg.awarded_date
    elif reg.certificate_issued_at:
        date_to_format = reg.certificate_issued_at.date()
    else:
        date_to_format = timezone.now().date()
    date_str = _format_date_with_ordinal(date_to_format) if date_to_format else ""
    _draw_page1_value("issued_date", date_str)
    
    # Learner Name (centered, bold - appears prominently in certificate section)
    cfg = PAGE1_CONFIG["learner_name"]
    font = _load_ictqual_font(_safe_get_font_path(cfg, FONT_CANDARA_BOLD), _scale(cfg["size"]))
    spacing = _scale(cfg.get("spacing", 0))
    thickness = cfg.get("thickness", 0)  # Don't scale thickness
    if cfg.get("align") == "center":
        # Center the text with 15px offset to the right
        bbox = draw.textbbox((0, 0), learner_name, font=font)
        text_width = bbox[2] - bbox[0]
        x = (img_width - text_width) // 2 + _scale(15)
        if thickness > 0:
            draw.text((x, _scale(cfg["y"])), learner_name, font=font, fill=cfg["color"], stroke_width=thickness, stroke_fill=cfg["color"])
        else:
            draw.text((x, _scale(cfg["y"])), learner_name, font=font, fill=cfg["color"])
    else:
        _draw_text_with_spacing(draw, learner_name, _scale(cfg["x"]), _scale(cfg["y"]), font, cfg["color"], spacing, thickness)
    
    # Qualification Title (centered, bold - appears below learner name)
    cfg = PAGE1_CONFIG["qualification_title"]
    font_path = _safe_get_font_path(cfg, FONT_CANDARA_BOLD)
    base_size_scaled = _scale(cfg["size"])
    spacing = _scale(cfg.get("spacing", 0))
    thickness = cfg.get("thickness", 0)  # Don't scale thickness
    # Ensure course.title is a string before calling strip()
    if course.title is None or course.title == "":
        course_title = "Course"
    else:
        course_title = str(course.title).strip() or "Course"
    if cfg.get("align") == "center":
        max_width = max(_scale(200), img_width - (_scale(110) * 2))
        max_height = _scale(42)
        font, lines, line_h = _fit_wrapped_text_to_box(
            draw,
            course_title,
            font_path,
            base_size_scaled,
            max_width,
            max_height,
        )
        y0 = _scale(cfg["y"]) - _scale(6)
        total_h = line_h * len(lines) if line_h and lines else 0
        start_y = int(y0 + (max_height - total_h) / 2) if total_h else int(y0)
        if len(lines) == 1:
            single_bbox = draw.textbbox((0, 0), lines[0], font=font)
            single_h = (single_bbox[3] - single_bbox[1])
            start_y = int(y0 + (max_height - single_h) / 2)

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (img_width - text_width) // 2 + _scale(15)
            y = int(start_y + (i * line_h) - bbox[1])
            if thickness > 0:
                draw.text((x, y), line, font=font, fill=cfg["color"], stroke_width=thickness, stroke_fill=cfg["color"])
            else:
                draw.text((x, y), line, font=font, fill=cfg["color"])
    else:
        font = _load_ictqual_font(font_path, base_size_scaled)
        _draw_text_with_spacing(draw, course_title, _scale(cfg["x"]), _scale(cfg["y"]), font, cfg["color"], spacing, thickness)
    
    # Business Name (centered, bold - appears under "Approved Training Centre")
    cfg = PAGE1_CONFIG["business_name"]
    course_title_cfg = PAGE1_CONFIG["qualification_title"]
    font_path = _safe_get_font_path(course_title_cfg, FONT_CANDARA_BOLD)
    base_size_scaled = _scale(course_title_cfg["size"])
    # Ensure business names are strings before calling strip()
    business_name_val = reg.business.business_name or reg.business.name
    if business_name_val is None or business_name_val == "":
        business_name = "Business"
    else:
        business_name = str(business_name_val).strip() or "Business"
    spacing = _scale(cfg.get("spacing", 0))
    thickness = cfg.get("thickness", 0)  # Don't scale thickness
    if cfg.get("align") == "center":
        max_width = max(_scale(200), img_width - (_scale(110) * 2))
        y0 = _scale(cfg["y"]) - _scale(6)
        next_y = _scale(PAGE1_CONFIG["course_number"]["y"])
        max_height = max(_scale(18), next_y - y0 - _scale(2))
        font, lines, line_h = _fit_wrapped_text_to_box(
            draw,
            business_name,
            font_path,
            base_size_scaled,
            max_width,
            max_height,
        )
        total_h = line_h * len(lines) if line_h and lines else 0
        start_y = int(y0 + (max_height - total_h) / 2) if total_h else int(y0)
        if len(lines) == 1:
            single_bbox = draw.textbbox((0, 0), lines[0], font=font)
            single_h = (single_bbox[3] - single_bbox[1])
            total_h = single_h
            start_y = int(y0 + (max_height - single_h) / 2)

        padding = _scale(2)
        max_line_w = 0
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            max_line_w = max(max_line_w, bbox[2] - bbox[0])
        bg_x1 = (img_width - max_line_w) // 2 + _scale(15) - padding
        bg_y1 = max(y0 - padding, start_y - padding)
        bg_x2 = bg_x1 + max_line_w + (padding * 2)
        bg_y2 = min(next_y - _scale(2), start_y + total_h + padding)
        if bg_y2 <= bg_y1:
            bg_y2 = bg_y1 + _scale(1)
        draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=(0, 100, 200))  # Blue background

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            text_width = bbox[2] - bbox[0]
            x = (img_width - text_width) // 2 + _scale(15)
            y = int(start_y + (i * line_h) - bbox[1])
            if thickness > 0:
                draw.text((x, y), line, font=font, fill=cfg["color"], stroke_width=thickness, stroke_fill=cfg["color"])
            else:
                draw.text((x, y), line, font=font, fill=cfg["color"])
    else:
        font = _load_ictqual_font(font_path, base_size_scaled)
        _draw_text_with_spacing(draw, business_name, _scale(cfg["x"]), _scale(cfg["y"]), font, cfg["color"], spacing, thickness)
    
    # QR Code
    qr_img = Image.open(BytesIO(qr_bytes))
    cfg = PAGE1_CONFIG["qr_code"]
    page1_img.paste(qr_img, (_scale(cfg["x"]), _scale(cfg["y"])))
    
    pages.append(page1_img)
    
    # ===== PAGE 2: Transcript Section with Units Table =====
    page2_img = _open_template_page(2)
    draw2 = ImageDraw.Draw(page2_img)
    img_width2, img_height2 = page2_img.size
    
    # Page 2 coordinates - adjusted for top of page (not bottom section like page 1)
    # Header section starts near top after template header
    PAGE2_HEADER_Y = 140  # Start below template header (moved up)
    PAGE2_COURSE_TITLE_Y = 165  # Moved down 5px
    PAGE2_BUSINESS_Y = 230
    PAGE2_UNIT_TABLE_START_Y = 268  # Units table starts here (moved down 3px)
    PAGE2_SUMMARY_Y = 360  # Summary at bottom
    PAGE2_DATE_Y = 390
    
    # Draw learner name in transcript section (left-aligned) - at top of page 2
    # Position aligned with "The Learner has been awarded..." line start
    PAGE2_LEFT_MARGIN = 75  # X position where content starts (aligned with units table)
    cfg = TRANSCRIPT_CONFIG["learner_name"]
    # Reduce font size for page 2 (from 24 to 20)
    font_size = int(cfg["size"] * 0.83)  # Reduce by ~17%
    font = _load_ictqual_font(_safe_get_font_path(cfg, FONT_CANDARA_BOLD), _scale(font_size))
    x = _scale(PAGE2_LEFT_MARGIN)
    thickness = cfg.get("thickness", 0)
    if thickness > 0:
        draw2.text((x, _scale(PAGE2_HEADER_Y)), learner_name, font=font, fill=(0, 0, 0), stroke_width=thickness, stroke_fill=(0, 0, 0))
    else:
        draw2.text((x, _scale(PAGE2_HEADER_Y)), learner_name, font=font, fill=(0, 0, 0))
    
    PAGE2_RIGHT_MARGIN = 75
    max_text_width = img_width2 - _scale(PAGE2_LEFT_MARGIN + PAGE2_RIGHT_MARGIN)
    
    cfg = TRANSCRIPT_CONFIG["course_title"]
    font_size = int(cfg["size"] * 0.83)
    x = _scale(PAGE2_LEFT_MARGIN)
    course_y = _scale(PAGE2_COURSE_TITLE_Y)
    course_font_path = _safe_get_font_path(cfg, FONT_CANDARA_BOLD)
    course_max_h = _scale(60)
    used_course_h, _ = _draw_wrapped_text(
        draw2,
        course_title,
        x,
        course_y,
        course_font_path,
        _scale(font_size),
        (0, 0, 0),
        max_text_width,
        course_max_h,
    )

    base_table_y = _scale(PAGE2_UNIT_TABLE_START_Y)
    table_y_scaled = max(base_table_y, course_y + max(used_course_h, _scale(18)) + _scale(18))
    PAGE2_UNIT_TABLE_START_Y = _unscale(table_y_scaled)
    
    # Draw units table for all sections - Table format: UNIT | TITLE | CREDIT | GLH | GRADE
    # First, collect all units from all sections into a flat list with section info
    all_units_data = []
    global_unit_idx = 0
    
    for section in sections:
        units = section.units.all().order_by('order')
        section_credits = section.credits if section.credits is not None else 0
        section_glh = section.glh_hours if section.glh_hours is not None else 0
        
        for unit in units:
            global_unit_idx += 1
            all_units_data.append({
                'unit': unit,
                'section': section,
                'section_credits': section_credits,
                'section_glh': section_glh,
                'num_units_in_section': units.count(),
                'global_idx': global_unit_idx
            })
    
    # Calculate total number of units
    total_units_count = len(all_units_data)

    total_credits = 0
    total_glh = 0
    for unit_data in all_units_data:
        unit = unit_data['unit']
        section_credits = unit_data['section_credits']
        section_glh = unit_data['section_glh']
        num_units_in_section = unit_data['num_units_in_section']
        unit_credit_val = int(getattr(unit, "credits", 0) or 0)
        if unit_credit_val == 0 and (section_credits or 0) and num_units_in_section > 0:
            unit_credit_val = section_credits // num_units_in_section
        unit_glh_val = int(getattr(unit, "glh_hours", 0) or 0)
        if unit_glh_val == 0 and (section_glh or 0) and num_units_in_section > 0:
            unit_glh_val = section_glh // num_units_in_section
        total_credits += unit_credit_val
        total_glh += unit_glh_val

    row_height = TRANSCRIPT_CONFIG["unit_row_height"]
    scaled_row_height = _scale(row_height)
    header_row_height = _scale(18)
    header_top = _scale(PAGE2_UNIT_TABLE_START_Y - 20)
    header_bottom = header_top + header_row_height
    table_top = header_bottom

    qr_size = _scale(80)
    qr_y = img_height2 - _scale(100)
    footer_required_height = _scale(150)

    max_table_bottom_non_last = qr_y - _scale(10)
    max_table_bottom_last = qr_y - footer_required_height

    max_rows_non_last = int((max_table_bottom_non_last - table_top) / scaled_row_height) if scaled_row_height > 0 else 1
    max_rows_last = int((max_table_bottom_last - table_top) / scaled_row_height) if scaled_row_height > 0 else 1
    max_rows_non_last = max(1, max_rows_non_last)
    max_rows_last = max(1, max_rows_last)

    unit_slices = []
    if total_units_count <= max_rows_last:
        unit_slices.append((0, total_units_count, True))
    else:
        start = 0
        remaining = total_units_count
        while remaining > max_rows_last:
            take = min(max_rows_non_last, remaining - max_rows_last)
            unit_slices.append((start, start + take, False))
            start += take
            remaining -= take
        unit_slices.append((start, total_units_count, True))

    for slice_index, (start, end, is_last_transcript_page) in enumerate(unit_slices):
        if slice_index > 0:
            page2_img = _open_template_page(2)
            draw2 = ImageDraw.Draw(page2_img)
            img_width2, img_height2 = page2_img.size

        table_bottom, table_left, table_right = _draw_transcript_units_table(
            draw2,
            all_units_data[start:end],
            PAGE2_UNIT_TABLE_START_Y,
            row_height,
        )

        if not is_last_transcript_page:
            cover_start_y = max(int(table_bottom + _scale(5)), _scale(PAGE2_SUMMARY_Y - 10))
            if cover_start_y < img_height2:
                draw2.rectangle([0, cover_start_y, img_width2, img_height2], fill=(255, 255, 255), outline=None)

        # Dynamic positioning: move summary + language blocks based on actual table height
        table_end_y = max(table_bottom, _scale(PAGE2_SUMMARY_Y))
        summary_anchor_y = table_bottom + _scale(10)  # Gap after last table row
        summary_start_y = summary_anchor_y - _scale(5)
        summary_end_y = max(
            summary_anchor_y + _scale(30),
            _scale(PAGE2_SUMMARY_Y + 40),
        )
        summary_y = summary_anchor_y + _scale(18)
        language_cert_start_y = summary_anchor_y + _scale(30)
        # Cover enough to hide template text when rows are few, without extending too far
        language_cert_end_y = max(
            summary_anchor_y + _scale(170),  # Slightly deeper cover for short tables
            _scale(PAGE2_DATE_Y + 40),
        )
        language_y = summary_anchor_y + _scale(45)
        qualification_y = summary_anchor_y + _scale(65)
        cert_info_y = summary_anchor_y + _scale(85)
        cert_date_y = summary_anchor_y + _scale(105)

        if not is_last_transcript_page:
            pages.append(page2_img)
            continue
    
    # ===== DRAW NEW PROGRAMMATIC SUMMARY LINES =====
    # Determine grading type from sections (check if all sections have Pass/Fail)
    # Always display "Pass/Fail" as the grading type
    grading_type = "Pass/Fail"
    
    # Draw summary information at bottom of transcript (using page 2 coordinates)
    # Position for summary line - aligned with business name (PAGE2_LEFT_MARGIN)
    # Keep summary text tied to dynamic anchor so it follows table height
    summary_font_size = 11
    font = _load_ictqual_font(FONT_CANDARA_REGULAR, _scale(summary_font_size))
    value_font = _load_ictqual_font(FONT_CANDARA_BOLD, _scale(summary_font_size))
    
    # Total Credits Achieved: [number] | - Start from left margin (same as business name)
    credits_label_x = _scale(PAGE2_LEFT_MARGIN)
    credits_label_text = "Total Credits Achieved:"
    # Calculate label width to position value right after label
    label_font = _load_ictqual_font(FONT_CANDARA_REGULAR, _scale(summary_font_size))
    label_bbox = draw2.textbbox((0, 0), credits_label_text, font=label_font)
    label_width = label_bbox[2] - label_bbox[0]
    credits_value_x = credits_label_x + label_width + _scale(5)  # Small gap after label
    credits_value_text = str(total_credits)
    credits_separator_x = credits_value_x + _scale(25)  # Space after number for separator
    credits_separator_text = "|"
    
    # Draw label
    draw2.text((credits_label_x, summary_y), credits_label_text, font=font, fill=(0, 0, 0))
    # Draw value in bright red
    bright_red = (255, 0, 0)  # Bright red color
    # Align value vertically with the label text (center-to-center)
    credits_label_bbox = draw2.textbbox((0, 0), credits_label_text, font=font)
    credits_label_center_y = summary_y + (credits_label_bbox[1] + credits_label_bbox[3]) / 2
    credits_value_bbox = draw2.textbbox((0, 0), credits_value_text, font=value_font)
    credits_value_y = int(credits_label_center_y - (credits_value_bbox[1] + credits_value_bbox[3]) / 2)
    draw2.text((credits_value_x, credits_value_y), credits_value_text, font=value_font, fill=bright_red)
    # Draw separator
    draw2.text((credits_separator_x, summary_y), credits_separator_text, font=font, fill=(0, 0, 0))
    
    # Total GLH Achieved: [number] |
    glh_label_x = credits_separator_x + _scale(5)  # Minimal gap after separator
    glh_label_text = "Total GLH Achieved:"
    # Calculate label width to position value right after label
    glh_label_bbox = draw2.textbbox((0, 0), glh_label_text, font=font)
    glh_label_width = glh_label_bbox[2] - glh_label_bbox[0]
    glh_value_x = glh_label_x + glh_label_width + _scale(5)  # Small gap after label
    glh_value_text = str(total_glh)
    glh_separator_x = glh_value_x + _scale(25)  # Space after number for separator
    glh_separator_text = "|"
    
    # Draw label
    draw2.text((glh_label_x, summary_y), glh_label_text, font=font, fill=(0, 0, 0))
    # Draw value in bright red
    glh_label_bbox2 = draw2.textbbox((0, 0), glh_label_text, font=font)
    glh_label_center_y = summary_y + (glh_label_bbox2[1] + glh_label_bbox2[3]) / 2
    glh_value_bbox = draw2.textbbox((0, 0), glh_value_text, font=value_font)
    glh_value_y = int(glh_label_center_y - (glh_value_bbox[1] + glh_value_bbox[3]) / 2)
    draw2.text((glh_value_x, glh_value_y), glh_value_text, font=value_font, fill=bright_red)
    # Draw separator
    draw2.text((glh_separator_x, summary_y), glh_separator_text, font=font, fill=(0, 0, 0))
    
    # Grading Type: Pass/Fail
    grading_label_x = glh_separator_x + _scale(5)  # Minimal gap after separator
    grading_label_text = "Grading Type:"
    # Calculate label width to position value right after label
    grading_label_bbox = draw2.textbbox((0, 0), grading_label_text, font=font)
    grading_label_width = grading_label_bbox[2] - grading_label_bbox[0]
    grading_value_x = grading_label_x + grading_label_width + _scale(5)  # Small gap after label
    grading_value_text = grading_type
    
    # Draw label
    draw2.text((grading_label_x, summary_y), grading_label_text, font=font, fill=(0, 0, 0))
    # Draw value
    draw2.text((grading_value_x, summary_y), grading_value_text, font=font, fill=(0, 0, 0))
    
    # ===== DRAW NEW PROGRAMMATIC LANGUAGE AND CERTIFICATE LINES =====
    # Language of Assessment: English
    language_font = _load_ictqual_font(FONT_CANDARA_REGULAR, _scale(11))
    language_label_x = _scale(PAGE2_LEFT_MARGIN)
    language_label_text = "Language of Assessment:"
    language_label_bbox = draw2.textbbox((0, 0), language_label_text, font=language_font)
    language_label_width = language_label_bbox[2] - language_label_bbox[0]
    language_value_x = language_label_x + language_label_width + _scale(5)
    language_value_text = "English"
    draw2.text((language_label_x, language_y), language_label_text, font=language_font, fill=(0, 0, 0))
    draw2.text((language_value_x, language_y), language_value_text, font=language_font, fill=(0, 0, 0))
    
    # "The learner has qualified for the above award on"
    qualification_text = "The learner has qualified for the above award on"
    draw2.text((language_label_x, qualification_y), qualification_text, font=language_font, fill=(0, 0, 0))
    qualification_date_font = _load_ictqual_font(FONT_CANDARA_BOLD, _scale(11))
    try:
        if reg.awarded_date:
            qualified_date = reg.awarded_date
        elif reg.certificate_issued_at:
            qualified_date = reg.certificate_issued_at.date()
        else:
            qualified_date = timezone.now().date()
    except Exception:
        qualified_date = timezone.now().date()
    qualification_date_text = _format_date_with_ordinal(qualified_date) if qualified_date else ""
    qualification_bbox = draw2.textbbox((0, 0), qualification_text, font=language_font)
    qualification_width = qualification_bbox[2] - qualification_bbox[0]
    qualification_date_x = language_label_x + qualification_width + _scale(6)
    qualification_center_y = qualification_y + (qualification_bbox[1] + qualification_bbox[3]) / 2
    qualification_date_bbox = draw2.textbbox((0, 0), qualification_date_text, font=qualification_date_font)
    qualification_date_y = int(qualification_center_y - (qualification_date_bbox[1] + qualification_date_bbox[3]) / 2)
    draw2.text((qualification_date_x, qualification_date_y), qualification_date_text, font=qualification_date_font, fill=(0, 0, 0))
    
    # Course Number | Certificate Number (labels regular, values bold)
    # Labels keep Candara; generated values use Montserrat
    cert_label_font = _load_ictqual_font(FONT_CANDARA_REGULAR, _scale(11))
    cert_value_font = _load_ictqual_font(FONT_CANDARA_BOLD, _scale(11))
    
    # Course Number
    course_num_label_x = language_label_x
    course_num_label_text = "Course Number:"
    course_num_label_bbox = draw2.textbbox((0, 0), course_num_label_text, font=cert_label_font)
    course_num_label_width = course_num_label_bbox[2] - course_num_label_bbox[0]
    course_num_value_x = course_num_label_x + course_num_label_width + _scale(5)
    course_num_text = course_number if course_number else ""
    course_num_value_bbox = draw2.textbbox((0, 0), course_num_text, font=cert_value_font)
    course_num_value_width = course_num_value_bbox[2] - course_num_value_bbox[0]
    course_num_separator_x = course_num_value_x + course_num_value_width + _scale(5)
    
    cert_info_center_y = cert_info_y + (course_num_label_bbox[1] + course_num_label_bbox[3]) / 2
    course_num_value_y = int(cert_info_center_y - (course_num_value_bbox[1] + course_num_value_bbox[3]) / 2)
    pipe_bbox = draw2.textbbox((0, 0), "|", font=cert_label_font)
    pipe_y = int(cert_info_center_y - (pipe_bbox[1] + pipe_bbox[3]) / 2)
    draw2.text((course_num_label_x, cert_info_y), course_num_label_text, font=cert_label_font, fill=(0, 0, 0))
    draw2.text((course_num_value_x, course_num_value_y), course_num_text, font=cert_value_font, fill=(0, 0, 0))
    draw2.text((course_num_separator_x, pipe_y), "|", font=cert_label_font, fill=(0, 0, 0))
    
    # Certificate Number
    cert_num_label_x = course_num_separator_x + _scale(5)
    cert_num_label_text = "Certificate Number:"
    cert_num_label_bbox = draw2.textbbox((0, 0), cert_num_label_text, font=cert_label_font)
    cert_num_label_width = cert_num_label_bbox[2] - cert_num_label_bbox[0]
    cert_num_value_x = cert_num_label_x + cert_num_label_width + _scale(5)
    cert_num_text = cert_num if cert_num else ""
    cert_num_value_bbox = draw2.textbbox((0, 0), cert_num_text, font=cert_value_font)
    cert_num_value_y = int(cert_info_center_y - (cert_num_value_bbox[1] + cert_num_value_bbox[3]) / 2)
    
    draw2.text((cert_num_label_x, cert_info_y), cert_num_label_text, font=cert_label_font, fill=(0, 0, 0))
    draw2.text((cert_num_value_x, cert_num_value_y), cert_num_text, font=cert_value_font, fill=(0, 0, 0))
    
    # Certificate Issue Date
    cert_date_label_text = "Certificate Issue Date:"
    cert_date_label_bbox = draw2.textbbox((0, 0), cert_date_label_text, font=cert_label_font)
    cert_date_label_width = cert_date_label_bbox[2] - cert_date_label_bbox[0]
    cert_date_value_x = language_label_x + cert_date_label_width + _scale(5)
    
    if reg.awarded_date:
        date_to_format = reg.awarded_date
    elif reg.certificate_issued_at:
        date_to_format = reg.certificate_issued_at.date()
    else:
        date_to_format = timezone.now().date()
    date_str = _format_date_with_ordinal(date_to_format) if date_to_format else ""
    cert_date_text = date_str
    
    draw2.text((language_label_x, cert_date_y), cert_date_label_text, font=cert_label_font, fill=(0, 0, 0))
    cert_date_label_bbox2 = draw2.textbbox((0, 0), cert_date_label_text, font=cert_label_font)
    cert_date_center_y = cert_date_y + (cert_date_label_bbox2[1] + cert_date_label_bbox2[3]) / 2
    cert_date_value_bbox = draw2.textbbox((0, 0), cert_date_text, font=cert_value_font)
    cert_date_value_y = int(cert_date_center_y - (cert_date_value_bbox[1] + cert_date_value_bbox[3]) / 2)
    draw2.text((cert_date_value_x, cert_date_value_y), cert_date_text, font=cert_value_font, fill=(0, 0, 0))
    
    # QR Code on transcript page - position centered horizontally at bottom
    qr_img = Image.open(BytesIO(qr_bytes))
    qr_size = _scale(80)  # Same size as page 1
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)
    # Position QR code centered on x-axis, near bottom
    qr_x = (img_width2 - qr_size) // 2  # Center horizontally
    qr_y = img_height2 - _scale(100)  # Position near bottom, leaving space for signature
    page2_img.paste(qr_img, (qr_x, qr_y))
    
    pages.append(page2_img)
    
    # Convert all pages to a single PDF with high resolution
    if not pages:
        raise ValueError("No certificate pages were generated. Check course sections and template files.")
    
    pdf_buffer = BytesIO()
    # Save first page as PDF with 300 DPI for high quality
    pages[0].save(
        pdf_buffer, 
        format='PDF', 
        save_all=True, 
        append_images=pages[1:] if len(pages) > 1 else [],
        resolution=300.0,
        quality=95
    )
    pdf_buffer.seek(0)
    
    # Verify PDF buffer has content
    pdf_data = pdf_buffer.read()
    if not pdf_data or len(pdf_data) == 0:
        raise ValueError("Generated PDF is empty. Certificate generation failed.")
    
    # If save_to_storage is False, return PDF bytes without saving
    if not save_to_storage:
        logger.info(f"Certificate PDF generated for registration {reg.id} (not saving to storage)")
        return pdf_data
    
    # Delete old file if present
    if reg.certificate_file:
        try:
            reg.certificate_file.delete(save=False)
        except Exception:
            pass

    # Save the PDF
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    cert_number = str(reg.certificate_number) if reg.certificate_number else 'certificate'
    filename = f"{cert_number}-{reg.id}-{timestamp}.pdf"
    
    # Check if S3 storage is configured properly
    from django.conf import settings
    if getattr(settings, 'USE_REMOTE_MEDIA', False):
        bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
        if not bucket_name:
            error_msg = (
                "Certificate generation failed: AWS S3 storage is enabled but bucket name is not configured. "
                "Please set AWS_STORAGE_BUCKET_NAME in your .env file or disable USE_REMOTE_MEDIA to use local storage."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
    
    try:
        reg.certificate_file.save(filename, ContentFile(pdf_data), save=True)
    except TypeError as e:
        if "expected string or bytes-like object, got 'NoneType'" in str(e):
            error_msg = (
                "Certificate generation failed: AWS S3 storage configuration is incomplete. "
                "Please check your .env file and ensure the following are set:\n"
                "- AWS_STORAGE_BUCKET_NAME\n"
                "- AWS_ACCESS_KEY_ID\n"
                "- AWS_SECRET_ACCESS_KEY\n"
                "- AWS_S3_REGION_NAME (optional, defaults to 'sfo3')\n\n"
                "Alternatively, set USE_REMOTE_MEDIA=False in your .env to use local file storage."
            )
            logger.error(f"{error_msg}\nOriginal error: {e}")
            raise ValueError(error_msg)
        raise
    
    # Ensure the save was successful
    reg.refresh_from_db(fields=["certificate_file"])
    if not reg.certificate_file:
        raise ValueError("Certificate file was not saved to database. Storage backend may have an issue.")
    
    return None


def generate_certificate_pdf(reg: LearnerRegistration) -> bytes:
    """
    Generate certificate PDF and return the bytes without saving to storage.
    This is used for on-demand generation to avoid filling up storage space.
    """
    return generate_and_attach_certificate(reg, save_to_storage=False)

def regenerate_certificates_for_user(user):
    """
    Rebuild all issued certificates for this user using the *current* name.
    Since certificates are now generated on-demand, this function is a no-op.
    Certificates will automatically use the current learner name when generated.
    """
    # No-op: Certificates are generated on-demand with current learner name
    # No need to regenerate or delete old files since nothing is stored
    pass


@login_required
def edit_learner(request, reg_id: int):
    """
    Edit a learner's name/email from the registrations screen.

    Permissions:
    - Superusers: may edit any learner.
    - Partners: may edit only if the registration belongs to their business
                AND the learner profile is not locked (is_profile_locked=False).

    Behavior:
    - If the learner's name changes, all already-issued certificates for that
      learner are regenerated so downloads show the new name.
    """
    reg = get_object_or_404(
        LearnerRegistration.objects.select_related("learner", "business", "course"),
        pk=reg_id,
    )
    # Partners can only edit learners registered by their own business,
    # and only if the Superadmin hasn't locked the profile.
    if (
        hasattr(request.user, "has_role")
        and request.user.has_role(Role.Names.PARTNER)
        and not request.user.is_superuser
    ):
        if not Business.objects.filter(
            pk=reg.business_id, email__iexact=request.user.email
        ).exists():
            messages.error(request, "You are not allowed to edit this learner.")
            # Business/Partner always goes back to registered learners
            return redirect("superadmin:registered_learners", course_id=reg.course_id)

        if getattr(reg.learner, "is_profile_locked", False):
            messages.error(request, "This learner's profile is locked by Superadmin — you can't edit it.")
            # Business/Partner always goes back to registered learners
            return redirect("superadmin:registered_learners", course_id=reg.course_id)


    user_obj = reg.learner

    # Local import to avoid any circulars; uses the form you added earlier.
    from .forms import LearnerEditForm

    form = LearnerEditForm(request.POST or None, instance=user_obj, request_user=request.user)

    if request.method == "POST" and form.is_valid():
        before_name = user_obj.full_name or ""
        saved_user = form.save()

        from django.db import transaction

        if (saved_user.full_name or "") != before_name:
            saved_user.refresh_from_db(fields=["full_name", "email"])
            user_id = saved_user.id
            transaction.on_commit(
                lambda: regenerate_certificates_for_user(CustomUser.objects.get(pk=user_id))
            )


        messages.success(request, "Learner details updated.")
        # Determine redirect URL based on user type
        if request.user.is_superuser:
            # Superadmin goes back to learners list
            return redirect("superadmin:learners_list")
        else:
            # Business/Partner goes back to registered learners for the course
            return redirect("superadmin:registered_learners", course_id=reg.course_id)

    # Determine back URL based on user type
    if request.user.is_superuser:
        # Superadmin goes back to learners list
        back_url = reverse("superadmin:learners_list")
    else:
        # Business/Partner goes back to registered learners for the course
        back_url = reverse("superadmin:registered_learners", args=[reg.course_id])

    # Reuse the same simple edit template for both superadmin and partner
    return render(
        request,
        "superadmin/edit_user.html",
        {
            "form": form,
            "page_title": "Edit Learner",
            "user_obj": user_obj,
            "course_id": reg.course_id,
            "back_url": back_url,
        },
    )


@login_required
def learners_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    q = (request.GET.get("q") or "").strip()

    learners = (
        CustomUser.objects
        .filter(roles__name=Role.Names.LEARNER)
        .annotate(
            issued_total=Count(
                "course_registrations",
                filter=Q(course_registrations__certificate_issued_at__isnull=False),
                distinct=True,
            )
        )
        .order_by("full_name", "email")
    )

    if q:
        learners = learners.filter(Q(full_name__icontains=q) | Q(email__icontains=q))

    # Get the most recent issued registration for each learner
    from superadmin.models import LearnerRegistration
    learners_with_regs = []
    for learner in learners:
        most_recent_reg = (
            LearnerRegistration.objects
            .filter(learner=learner, certificate_issued_at__isnull=False)
            .order_by("-certificate_issued_at")
            .first()
        )
        learners_with_regs.append({
            'learner': learner,
            'most_recent_reg_id': most_recent_reg.id if most_recent_reg else None,
        })

    return render(request, "superadmin/learners_list.html", {
        "learners_with_regs": learners_with_regs,
        "learners": learners,  # Keep for backward compatibility
        "q": q,
    })


@login_required
def assign_courses_to_learner(request, learner_id: int):
    """
    Allow superadmin to assign courses to a learner.
    Shows all courses and allows selecting a business for each course assignment.
    """
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can assign courses to learners.")

    learner = get_object_or_404(CustomUser, pk=learner_id)
    
    # Ensure learner has learner role
    learner_role, _ = Role.objects.get_or_create(name=Role.Names.LEARNER)
    learner.roles.add(learner_role)

    # Search filter
    q = (request.GET.get("q") or "").strip()

    # Get all courses
    courses_qs = Course.objects.all()
    if q:
        courses_qs = courses_qs.filter(
            Q(title__icontains=q) |
            Q(course_number__icontains=q) |
            Q(category__icontains=q)
        )

    courses_qs = courses_qs.order_by("title")

    # Get all businesses for selection
    businesses = Business.objects.all().order_by("business_name", "name")

    if request.method == "POST":
        # Get course-business pairs from form
        course_ids = request.POST.getlist("course_ids")
        business_ids = request.POST.getlist("business_ids")
        
        if not course_ids:
            messages.warning(request, "Please select at least one course to assign.")
            return redirect(reverse("superadmin:assign_courses_to_learner", args=[learner.id]))

        # Validate that we have business for each course
        if len(course_ids) != len(business_ids):
            messages.error(request, "Please select a business for each course.")
            return redirect(reverse("superadmin:assign_courses_to_learner", args=[learner.id]))

        # Create registrations
        created_count = 0
        existing_count = 0
        skipped_count = 0
        
        for course_id, business_id in zip(course_ids, business_ids):
            if not business_id:
                skipped_count += 1
                continue
                
            try:
                course = Course.objects.get(pk=course_id)
                business = Business.objects.get(pk=business_id)
                
                # Check if course is assigned to this business
                if not business.courses.filter(pk=course.id).exists():
                    messages.warning(
                        request,
                        f"Course '{course.title}' is not assigned to business '{business.business_name or business.name}'. "
                        f"Please assign the course to the business first."
                    )
                    skipped_count += 1
                    continue
                
                # Create registration (get_or_create to avoid duplicates)
                registration, created = LearnerRegistration.objects.get_or_create(
                    course=course,
                    learner=learner,
                    business=business,
                )
                
                if created:
                    created_count += 1
                else:
                    existing_count += 1
                    
            except (Course.DoesNotExist, Business.DoesNotExist):
                skipped_count += 1
                continue

        if created_count > 0:
            messages.success(
                request,
                f"Successfully assigned {created_count} course(s) to {learner.full_name or learner.email}."
            )
        if existing_count > 0:
            messages.info(
                request,
                f"{existing_count} course(s) were already assigned to this learner."
            )
        if skipped_count > 0:
            messages.warning(
                request,
                f"{skipped_count} course(s) were skipped due to missing business selection or invalid data."
            )

        return redirect(reverse("superadmin:learners_list"))

    # Get existing registrations for this learner
    existing_registrations = LearnerRegistration.objects.filter(learner=learner).select_related('course', 'business')
    existing_course_business_pairs = {(reg.course_id, reg.business_id) for reg in existing_registrations}

    return render(
        request,
        "superadmin/assign_courses_to_learner.html",
        {
            "learner": learner,
            "courses": list(courses_qs),
            "businesses": businesses,
            "existing_registrations": existing_registrations,
            "existing_course_business_pairs": existing_course_business_pairs,
            "q": q,
        },
    )


@login_required
def edit_user(request, user_id: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    user_obj = get_object_or_404(CustomUser, pk=user_id)


    # Determine a safe "Back" link:
    # - If ?course_id=123 is passed, go back to that course's registrations
    # - Otherwise, fall back to the learners list
    course_id_qs = request.GET.get("course_id")
    if course_id_qs and course_id_qs.isdigit():
        back_url = reverse("superadmin:registered_learners", args=[int(course_id_qs)])
    else:
        back_url = reverse("superadmin:learners_list")


    form = LearnerEditForm(request.POST or None, instance=user_obj, request_user=request.user)
    if request.method == "POST" and form.is_valid():
        name_changed = ("full_name" in form.changed_data)
        user_saved = form.save()

        if name_changed:
            user_saved.refresh_from_db(fields=["full_name", "email"])
            uid = user_saved.id
            transaction.on_commit(
                lambda uid=uid: regenerate_certificates_for_user(CustomUser.objects.get(pk=uid))
            )

        messages.success(request, "User updated.")
        return redirect(back_url)

    return render(request, "superadmin/edit_user.html", {
        "form": form,
        "user_obj": user_obj,
        "back_url": back_url,
    })



@login_required
@require_POST
def toggle_profile_lock(request, user_id: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")
    u = get_object_or_404(CustomUser, pk=user_id)
    u.is_profile_locked = not u.is_profile_locked
    u.save(update_fields=["is_profile_locked"])
    messages.success(
        request,
        f'Profile {"LOCKED" if u.is_profile_locked else "UNLOCKED"} for {u.full_name or u.email}.'
    )
    return redirect("superadmin:learners_list")


@login_required
@require_POST
def bulk_toggle_profile_lock(request):
    """
    Bulk lock/unlock multiple learner profiles.
    Accepts user_ids list and action ('lock' or 'unlock').
    """
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")
    
    user_ids = request.POST.getlist("user_ids")
    action = request.POST.get("action", "").lower()
    
    if not user_ids:
        messages.error(request, "No learners selected.")
        return redirect("superadmin:learners_list")
    
    if action not in ["lock", "unlock"]:
        messages.error(request, "Invalid action. Use 'lock' or 'unlock'.")
        return redirect("superadmin:learners_list")
    
    try:
        user_ids = [int(x) for x in user_ids if str(x).isdigit()]
    except Exception:
        messages.error(request, "Invalid user IDs.")
        return redirect("superadmin:learners_list")
    
    users = CustomUser.objects.filter(
        id__in=user_ids,
        roles__name=Role.Names.LEARNER
    )
    
    if action == "lock":
        users.update(is_profile_locked=True)
        count = users.count()
        messages.success(request, f"Locked {count} learner profile(s).")
    else:  # unlock
        users.update(is_profile_locked=False)
        count = users.count()
        messages.success(request, f"Unlocked {count} learner profile(s).")
    
    return redirect("superadmin:learners_list")


@login_required
def learner_specific(request, user_id: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    user_obj = get_object_or_404(CustomUser, pk=user_id)

    regs = (
        LearnerRegistration.objects
        .select_related("course", "business")
        .filter(learner=user_obj)
        .order_by("-created_at")
    )

    return render(
        request,
        "superadmin/learner_specific.html",
        {
            "user_obj": user_obj,
            "registrations": regs,
            "back_url": reverse("superadmin:learners_list"),
        },
    )


@login_required
@require_POST
def toggle_revoke_registration(request, reg_id: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    reg = get_object_or_404(LearnerRegistration, pk=reg_id)

    # Only meaningful if issued; allow toggle regardless, but UI already hides when not issued.
    reg.is_revoked = not reg.is_revoked
    reg.save(update_fields=["is_revoked"])

    messages.success(request, "Certificate revoked." if reg.is_revoked else "Certificate unrevoked.")
    next_url = request.POST.get("next") or reverse("superadmin:learner_specific", args=[reg.learner_id])
    return redirect(next_url)


def _is_superuser(user):
    return user.is_authenticated and user.is_superuser

@login_required
@user_passes_test(_is_superuser)
def toggle_advance_payment(request, business_id):
    """
    Toggle advance_payment field for a business.
    Only superusers can perform this action.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    
    business = get_object_or_404(Business, pk=business_id)
    
    # Toggle the advance_payment field
    business.advance_payment = not business.advance_payment
    business.save(update_fields=["advance_payment"])
    
    # Set success message
    status = "enabled" if business.advance_payment else "disabled"
    messages.success(request, f"Advance payment {status} for {business.business_name or business.name}")
    
    # Redirect back to business list
    return redirect("superadmin:business_list")


@login_required
@user_passes_test(_is_superuser)
def business_discounts(request):
    """
    List all businesses with their discount settings.
    Superuser can view and manage discounts for all businesses.
    Supports search (q) and has_discount filter.
    """
    from .models import BusinessDiscount, BusinessCourseDiscount
    
    # Get all businesses with their discount information
    businesses = (
        Business.objects
        .select_related('discount')
        .prefetch_related('courses', 'course_discounts')
        .all()
    )
    
    # Search filter
    q = request.GET.get("q", "").strip()
    if q:
        businesses = businesses.filter(
            Q(business_name__icontains=q) |
            Q(name__icontains=q) |
            Q(email__icontains=q)
        )
    
    # Discount filter
    has_discount = request.GET.get("has_discount", "").strip()
    if has_discount == "yes":
        # Businesses that have at least one discount (legacy or per-course)
        businesses = businesses.filter(Q(discount__isnull=False) | Q(course_discounts__isnull=False)).distinct()
    elif has_discount == "no":
        # Businesses that don't have any discount (legacy or per-course)
        businesses = businesses.filter(discount__isnull=True, course_discounts__isnull=True)
    
    businesses = businesses.order_by('business_name', 'name')
    
    # Add discount info to each business
    for business in businesses:
        assigned_courses_count = len(list(business.courses.all()))
        business.assigned_courses_count = assigned_courses_count

        course_discounts = list(business.course_discounts.all())
        business.affiliate_course_discount_count = sum(
            1 for d in course_discounts if d.affiliate_discount_percentage and d.affiliate_discount_percentage > 0
        )
        business.learner_course_discount_count = sum(
            1 for d in course_discounts if d.learner_discount_percentage and d.learner_discount_percentage > 0
        )

        # Legacy fallbacks (kept for compatibility)
        if getattr(business, 'discount', None):
            business.affiliate_discount = business.discount.affiliate_discount_percentage
            business.learner_discount = business.discount.learner_discount_percentage
            legacy_updated = business.discount.updated_at
        else:
            business.affiliate_discount = Decimal("0.00")
            business.learner_discount = Decimal("0.00")
            legacy_updated = None

        # Totals for display
        if course_discounts:
            business.affiliate_total_discount = sum(
                (d.affiliate_discount_percentage for d in course_discounts if d.affiliate_discount_percentage and d.affiliate_discount_percentage > 0),
                Decimal("0.00"),
            )
            business.learner_total_discount = sum(
                (d.learner_discount_percentage for d in course_discounts if d.learner_discount_percentage and d.learner_discount_percentage > 0),
                Decimal("0.00"),
            )
        else:
            business.affiliate_total_discount = business.affiliate_discount
            business.learner_total_discount = business.learner_discount

        latest_course_discount = course_discounts[0] if course_discounts else None
        if latest_course_discount:
            latest_course_discount = max(course_discounts, key=lambda d: d.updated_at)
        business.latest_discount_updated_at = (
            latest_course_discount.updated_at if latest_course_discount else legacy_updated
        )
        business.has_any_discount = bool(
            (business.affiliate_course_discount_count or business.learner_course_discount_count) or legacy_updated
        )
    
    return render(request, "superadmin/business_discounts.html", {
        "businesses": businesses,
        "q": q,
        "has_discount": has_discount,
    })


@login_required
@user_passes_test(_is_superuser)
def edit_business_discount(request, business_id):
    """
    Edit discount settings for a specific business.
    """
    from .models import BusinessCourseDiscount, BusinessDiscount

    business = get_object_or_404(Business, pk=business_id)

    courses = business.courses.all().order_by('title')
    existing = {
        d.course_id: d
        for d in BusinessCourseDiscount.objects.filter(business=business, course__in=courses)
    }

    if request.method == "POST":
        errors = []
        updated = 0
        deleted = 0

        aff_raw = (request.POST.get("affiliate_all") or "0").strip()
        lea_raw = (request.POST.get("learner_all") or "0").strip()

        try:
            aff_pct = Decimal(aff_raw) if aff_raw else Decimal("0.00")
            lea_pct = Decimal(lea_raw) if lea_raw else Decimal("0.00")
        except Exception:
            errors.append("Invalid discount value. Please enter valid numbers.")
            aff_pct = lea_pct = Decimal("0.00")

        if aff_pct < 0 or aff_pct > 100 or lea_pct < 0 or lea_pct > 100:
            errors.append("Discount percentages must be between 0 and 100.")

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            with transaction.atomic():
                # Save business-wide discount (legacy/global)
                BusinessDiscount.objects.update_or_create(
                    business=business,
                    defaults={
                        "affiliate_discount_percentage": aff_pct,
                        "learner_discount_percentage": lea_pct,
                    },
                )

                # Apply the same discount to every assigned course
                for course in courses:
                    if aff_pct == 0 and lea_pct == 0:
                        if course.id in existing:
                            existing[course.id].delete()
                            deleted += 1
                        continue

                    BusinessCourseDiscount.objects.update_or_create(
                        business=business,
                        course=course,
                        defaults={
                            'affiliate_discount_percentage': aff_pct,
                            'learner_discount_percentage': lea_pct,
                            'created_by': request.user,
                        }
                    )
                    updated += 1

            msg = f"Saved global discount for all courses for {business.business_name or business.name}."
            if updated or deleted:
                msg = f"Saved global discount: {updated} course(s) updated, {deleted} reset."
            messages.success(request, msg)
            return redirect("superadmin:business_discounts")

    # Defaults for the form from existing global discount (if any)
    existing_discount = BusinessDiscount.objects.filter(business=business).first()
    default_affiliate = existing_discount.affiliate_discount_percentage if existing_discount else Decimal("0.00")
    default_learner = existing_discount.learner_discount_percentage if existing_discount else Decimal("0.00")

    return render(request, "superadmin/edit_business_discount.html", {
        "business": business,
        "assigned_courses_count": courses.count(),
        "default_affiliate_discount": default_affiliate,
        "default_learner_discount": default_learner,
    })


@login_required
@user_passes_test(_is_superuser)
def delete_business_discount(request, business_id):
    """
    Delete discount settings for a business (reset to 0%).
    """
    from .models import BusinessDiscount
    
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    
    business = get_object_or_404(Business, pk=business_id)
    
    deleted_any = False
    deleted_count, _ = BusinessCourseDiscount.objects.filter(business=business).delete()
    if deleted_count:
        deleted_any = True
    try:
        discount = BusinessDiscount.objects.get(business=business)
        discount.delete()
        deleted_any = True
    except BusinessDiscount.DoesNotExist:
        pass

    if deleted_any:
        messages.success(request, f"Discount settings removed for {business.business_name or business.name}")
    else:
        messages.info(request, f"No discount settings found for {business.business_name or business.name}")
    
    return redirect("superadmin:business_discounts")


@login_required
def business_pricing(request):
    """
    Show applicable pricing for the current business user.
    This includes base pricing and any applicable discounts.
    """
    from .models import BusinessDiscount
    from pricing.models import CoursePricing
    
    # Get the business associated with the current user
    businesses = Business.objects.filter(email__iexact=request.user.email)
    if not businesses.exists():
        messages.error(request, "No business associated with your account.")
        return redirect("superadmin:business_dashboard")
    
    business = businesses.first()
    
    # Get legacy business-wide discount (fallback)
    try:
        discount = BusinessDiscount.objects.get(business=business)
    except BusinessDiscount.DoesNotExist:
        discount = None
    
    # Get all courses assigned to this business with their pricing
    courses = business.courses.all().order_by('title')
    
    # Get pricing for each course and calculate final prices
    course_pricing = []
    course_discounts = {
        d.course_id: d
        for d in BusinessCourseDiscount.objects.filter(business=business, course__in=courses)
    }
    use_legacy_fallback = not bool(course_discounts)

    for course in courses:
        try:
            pricing = CoursePricing.objects.get(course=course)
            
            # Calculate final prices with discount
            final_affiliate_price = pricing.affiliate_price
            cd = course_discounts.get(course.id)
            discount_percentage = Decimal("0.00")
            if cd and cd.affiliate_discount_percentage and cd.affiliate_discount_percentage > 0:
                discount_percentage = cd.affiliate_discount_percentage
                discount_amount = (pricing.affiliate_price * cd.affiliate_discount_percentage) / 100
                final_affiliate_price = max(Decimal("0.00"), pricing.affiliate_price - discount_amount)
            elif discount and use_legacy_fallback:
                discount_percentage = discount.affiliate_discount_percentage
                final_affiliate_price = discount.get_discounted_affiliate_price(pricing.affiliate_price)
            
            course_pricing.append({
                'course': course,
                'pricing': pricing,
                'final_affiliate_price': final_affiliate_price,
                'discount_percentage': discount_percentage,
                'has_discount': bool(discount_percentage and discount_percentage > 0),
            })
        except CoursePricing.DoesNotExist:
            # Course has no pricing set
            course_pricing.append({
                'course': course,
                'pricing': None,
                'final_affiliate_price': Decimal("0.00"),
                'discount_percentage': Decimal("0.00"),
                'has_discount': False
            })

    assigned_courses_count = courses.count()
    discounted_courses_count = sum(1 for item in course_pricing if item.get('has_discount'))
    max_discount_percentage = max(
        (item.get('discount_percentage') or Decimal("0.00") for item in course_pricing),
        default=Decimal("0.00"),
    )
    special_pricing_active = bool(discounted_courses_count > 0)
    
    return render(request, "superadmin/business_pricing.html", {
        "business": business,
        "discount": discount,
        "course_pricing": course_pricing,
        "special_pricing_active": special_pricing_active,
        "discounted_courses_count": discounted_courses_count,
        "assigned_courses_count": assigned_courses_count,
        "max_discount_percentage": max_discount_percentage,
    })








def _add_years_safe(d: date, years: int) -> date:
    """Add years to a date safely (handles Feb 29)."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        # Feb 29 -> Feb 28 on non-leap years
        return d.replace(month=2, day=28, year=d.year + years)





def _can_access_cert(request_user, cert):
    """
    Superusers, or the partner that issued this certificate, may access.
    Adjust as needed for your auth model.
    """
    if request_user.is_superuser:
        return True
    try:
        # Partner user belongs to issuer business?  Adjust if you store differently.
        return hasattr(request_user, "business") and request_user.business_id == cert.issuer_business_id
    except Exception:
        return False


def _load_font(size=36):
    """
    Try a TrueType font (nicer). Fallback to default if not found.
    Tweak the path to your server font if you want a specific face.
    """
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # typical Linux
        "/Library/Fonts/Arial.ttf",                        # macOS
        "C:/Windows/Fonts/arial.ttf",                      # Windows
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()



def _open_image_from_field(filefield):
    """
    Storage-agnostic image open (works for local path or S3).
    Supports PNG/JPG out of the box and SVG via CairoSVG (if installed).
    Returns a PIL RGBA image or None on failure.
    """
    try:
        if not filefield:
            return None

        # Read bytes directly from storage (works on S3; doesn't rely on .path)
        filefield.open("rb")
        data = filefield.read()
        filefield.close()

        name = getattr(filefield, "name", "") or ""
        ext = os.path.splitext(name.lower())[1]

        # SVG → rasterize with CairoSVG
        if ext == ".svg":
            if cairosvg is None:
                return None
            png_bytes = cairosvg.svg2png(bytestring=data)
            img = Image.open(BytesIO(png_bytes))
            return img.convert("RGBA")

        # Raster formats
        img = Image.open(BytesIO(data))
        return img.convert("RGBA")

    except Exception:
        # Local dev fallback
        try:
            return Image.open(filefield.path).convert("RGBA")
        except Exception:
            return None




def _parse_color(val, default=(17, 24, 39)):
    """
    Accepts '#RRGGBB', 'rgb(r,g,b)', or (r,g,b) tuple. Returns (r,g,b).
    """
    if isinstance(val, (tuple, list)) and len(val) == 3:
        try:
            return (int(val[0]), int(val[1]), int(val[2]))
        except Exception:
            return default
    if isinstance(val, str):
        s = val.strip()
        try:
            if s.startswith("#") and len(s) == 7:
                return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
            if s.lower().startswith("rgb(") and s.endswith(")"):
                r, g, b = [int(p.strip()) for p in s[4:-1].split(",")]
                return (r, g, b)
        except Exception:
            return default
    return default



# Helper
def _is_superuser(user):
    return user.is_superuser





@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_POST
def delete_business(request, pk):
    """
    Deletes a Business and its associated partner account (CustomUser with matching email).
    Safeguards:
      - If learner registrations or issued ISO certs exist, block deletion and inform the admin.
      - Does NOT delete learner accounts or certificates.
    """
    business = get_object_or_404(Business, pk=pk)

    # Hard safety checks to avoid cascading deletions of historical records
    reg_count = LearnerRegistration.objects.filter(business=business).count()

    if reg_count:
        messages.error(
            request,
            (
                "Cannot delete this business because it has linked data: "
                f"{reg_count} learner registration(s). "
                "Please revoke/transfer or archive records if needed before deleting."
            ),
        )
        return redirect("superadmin:business_list")

    # Delete the partner account (if any) using the same email
    CustomUser.objects.filter(email__iexact=business.email).delete()

    # Delete the business
    business.delete()

    messages.success(request, "Business and associated account were deleted successfully.")
    return redirect("superadmin:business_list")


# Payment Views
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from datetime import datetime

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def create_payment_session(request, course_id: int):
    """
    Create a Stripe payment session for advance payment businesses
    """
    # Only partners can use this page
    if not (hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER)):
        raise PermissionDenied("Only Partner users can make payments.")
    
    # Check if Stripe is properly configured
    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Payment system is not configured. Please contact support.")
        return redirect("superadmin:business_dashboard")
    
    # Get the business
    business = Business.objects.filter(email__iexact=request.user.email).first()
    if not business:
        messages.error(request, "No business found for your account.")
        return redirect("superadmin:business_dashboard")
    
    # Check if advance payment is required
    if not business.advance_payment:
        messages.error(request, "Advance payment is not required for your business.")
        return redirect("superadmin:business_courses")
    
    course = get_object_or_404(Course, pk=course_id)
    
    # Get number of learners from session (set during registration)
    number_of_learners = request.session.get(f'pending_learners_{course_id}', 0)
    if number_of_learners == 0:
        messages.error(request, "No learners to register. Please register learners first.")
        return redirect("superadmin:register_learners", course_id=course_id)
    
    # Get pricing with discount
    from pricing.views import get_discounted_price
    final_price, base_price, discount_percentage, currency = get_discounted_price(business, course, 'affiliate')
    
    # Calculate total amount
    total_amount = final_price * number_of_learners
    
    try:
        # Build URLs
        success_url = request.build_absolute_uri('/superadmin/payment/success/') + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = request.build_absolute_uri(f'/superadmin/payment/cancel/{course_id}/')
        
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': currency.lower(),
                    'product_data': {
                        'name': f'{course.title} - {number_of_learners} Learner(s)',
                        'description': f'Registration for {number_of_learners} learner(s) in {course.title}',
                    },
                    'unit_amount': int(final_price * 100),  # Convert to cents
                },
                'quantity': number_of_learners,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'business_id': str(business.id),
                'course_id': str(course.id),
                'number_of_learners': str(number_of_learners),
                'unit_price': str(final_price),
                'discount_percentage': str(discount_percentage),
            }
        )
        
        # Create payment session record
        payment_session = PaymentSession.objects.create(
            business=business,
            course=course,
            stripe_session_id=checkout_session.id,
            amount=total_amount,
            currency=currency,
            number_of_learners=number_of_learners,
            unit_price=final_price,
            discount_percentage=discount_percentage,
        )
        
        # Store payment session ID in session for later use
        request.session[f'payment_session_{course_id}'] = payment_session.id
        
        return redirect(checkout_session.url)
        
    except stripe.StripeError as e:
        messages.error(request, f"Payment error: {str(e)}")
        return redirect("superadmin:register_learners", course_id=course_id)
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("superadmin:register_learners", course_id=course_id)


@login_required
def payment_success(request):
    """
    Handle successful payment
    """
    # Get session_id from query parameters
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, "No session ID provided.")
        return redirect("superadmin:business_dashboard")
    
    try:
        # Retrieve the checkout session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Get the payment session from our database
        payment_session = PaymentSession.objects.get(stripe_session_id=session_id)
        
        # Update payment session status
        from django.utils import timezone
        payment_session.status = 'completed'
        payment_session.completed_at = timezone.now()
        payment_session.stripe_payment_intent_id = checkout_session.payment_intent
        payment_session.save()
        
        # Get the pending learners from session
        course_id = payment_session.course.id
        pending_learners_data = request.session.get(f'pending_learners_data_{course_id}', [])
        
        if pending_learners_data:
            # Create learner registrations
            learner_role, _ = Role.objects.get_or_create(name=Role.Names.LEARNER)
            processed_registrations = []
            new_registrations = 0
            
            for learner_data in pending_learners_data:
                # Create or get user
                user, user_created = CustomUser.objects.get_or_create(
                    email=learner_data['email'],
                    defaults={
                        'full_name': learner_data['name'],
                        'password': get_random_string(12),
                        'is_active': True,
                    }
                )
                
                if user_created:
                    user.set_password(get_random_string(12))
                    user.save()
                
                # Ensure learner role
                user.roles.add(learner_role)
                
                # Create or get existing registration (allow same learner for same course under different businesses)
                registration, registration_created = LearnerRegistration.objects.get_or_create(
                    course=payment_session.course,
                    learner=user,
                    business=payment_session.business,
                )
                
                if registration_created:
                    new_registrations += 1
                
                # Link registration to payment (if not already linked)
                LearnerRegistrationPayment.objects.get_or_create(
                    payment_session=payment_session,
                    registration=registration,
                )
                
                processed_registrations.append(registration)
            
            # Create invoice record for the payment
            from pricing.models import InvoicePayment, InvoicedItem
            from django.utils import timezone
            
            # Create invoice payment record
            invoice = InvoicePayment.objects.create(
                business=payment_session.business,
                period_start=timezone.now() - timezone.timedelta(days=1),
                period_end=timezone.now(),
                invoice_no=f"INV-{payment_session.id}-{timezone.now().strftime('%Y%m%d')}",
                status='paid',
                marked_paid_at=timezone.now(),
                uploaded_at=timezone.now(),
            )
            
            # Create invoiced items for each registration
            for registration in processed_registrations:
                InvoicedItem.objects.create(
                    invoice=invoice,
                    registration=registration,
                    currency=payment_session.currency,
                    unit_fee=payment_session.unit_price,
                    course_title_snapshot=registration.course.title,
                )
            
            # Clear session data
            request.session.pop(f'pending_learners_{course_id}', None)
            request.session.pop(f'pending_learners_data_{course_id}', None)
            request.session.pop(f'payment_session_{course_id}', None)
            
            # Create appropriate success message
            if new_registrations > 0:
                messages.success(
                    request, 
                    f"Payment successful! {new_registrations} new learner(s) registered for {payment_session.course.title}. Invoice #{invoice.invoice_no} has been generated."
                )
            else:
                messages.success(
                    request, 
                    f"Payment successful! All learners were already registered for {payment_session.course.title}. Invoice #{invoice.invoice_no} has been generated."
                )
            
            return redirect("superadmin:registered_learners", course_id=course_id)
        else:
            messages.error(request, "No learner data found. Please contact support.")
            return redirect("superadmin:business_courses")
            
    except PaymentSession.DoesNotExist:
        messages.error(request, "Payment session not found.")
        return redirect("superadmin:business_dashboard")
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("superadmin:business_dashboard")


@login_required
def payment_cancel(request, course_id):
    """
    Handle cancelled payment
    """
    # Clear session data
    request.session.pop(f'pending_learners_{course_id}', None)
    request.session.pop(f'pending_learners_data_{course_id}', None)
    request.session.pop(f'payment_session_{course_id}', None)
    
    messages.info(request, "Payment was cancelled. You can try again anytime.")
    return redirect("superadmin:register_learners", course_id=course_id)




@csrf_exempt
def stripe_webhook(request):
    """
    Handle Stripe webhooks for payment status updates
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return JsonResponse({'error': 'Invalid payload'}, status=400)
    except stripe.SignatureVerificationError:
        return JsonResponse({'error': 'Invalid signature'}, status=400)
    
    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        try:
            from django.utils import timezone
            payment_session = PaymentSession.objects.get(stripe_session_id=session['id'])
            payment_session.status = 'completed'
            payment_session.completed_at = timezone.now()
            payment_session.stripe_payment_intent_id = session['payment_intent']
            payment_session.save()
        except PaymentSession.DoesNotExist:
            pass
    
    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        try:
            payment_session = PaymentSession.objects.get(stripe_payment_intent_id=payment_intent['id'])
            payment_session.status = 'failed'
            payment_session.failure_reason = payment_intent.get('last_payment_error', {}).get('message', 'Payment failed')
            payment_session.save()
        except PaymentSession.DoesNotExist:
            pass
    
    return JsonResponse({'status': 'success'})


@login_required
def pay_invoice_stripe(request, invoice_id: int):
    """
    Create a Stripe payment session for an existing invoice
    """
    # Only partners can use this page
    if not (hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER)):
        raise PermissionDenied("Only Partner users can make payments.")
    
    # Check if Stripe is properly configured
    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Payment system is not configured. Please contact support.")
        return redirect("pricing:business_invoices_list")
    
    # Get the business
    business = Business.objects.filter(email__iexact=request.user.email).first()
    if not business:
        messages.error(request, "No business found for your account.")
        return redirect("superadmin:business_dashboard")
    
    # Get the invoice
    from pricing.models import InvoicePayment
    invoice = get_object_or_404(InvoicePayment, pk=invoice_id, business=business)
    
    # Check if invoice is already paid
    if invoice.status == 'paid':
        messages.info(request, "This invoice has already been paid.")
        return redirect("pricing:business_invoices_list")
    
    # Calculate total amount and get currency from first item
    learner_items = invoice.items.all()
    
    learner_total = sum((item.unit_fee for item in learner_items), Decimal("0.00"))
    total_amount = learner_total
    
    # Get currency from first available item
    currency = 'USD'  # default
    if learner_items:
        currency = learner_items.first().currency
    
    try:
        # Build URLs
        success_url = request.build_absolute_uri('/superadmin/invoice/payment/success/') + '?session_id={CHECKOUT_SESSION_ID}'
        cancel_url = request.build_absolute_uri('/pricing/invoices/my/')
        
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': currency.lower(),
                    'product_data': {
                        'name': f'Invoice #{invoice.invoice_no}',
                        'description': f'Payment for {learner_items.count()} learner registration(s)',
                    },
                    'unit_amount': int(total_amount * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'invoice_id': str(invoice.id),
                'business_id': str(business.id),
            }
        )
        
        # Store payment session info
        request.session[f'invoice_payment_session_{invoice_id}'] = checkout_session.id
        
        return redirect(checkout_session.url)
        
    except stripe.StripeError as e:
        messages.error(request, f"Payment error: {str(e)}")
        return redirect("pricing:business_invoices_list")
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("pricing:business_invoices_list")


@login_required
def invoice_payment_success(request):
    """
    Handle successful invoice payment
    """
    session_id = request.GET.get('session_id')
    if not session_id:
        messages.error(request, "Invalid payment session.")
        return redirect("pricing:business_invoices_list")
    
    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Get invoice ID from metadata
        invoice_id = session.metadata.get('invoice_id')
        if not invoice_id:
            messages.error(request, "Invalid payment session.")
            return redirect("pricing:business_invoices_list")
        
        # Get the invoice
        from pricing.models import InvoicePayment
        invoice = get_object_or_404(InvoicePayment, pk=invoice_id)
        
        # Update invoice status
        invoice.status = 'paid'
        invoice.marked_paid_at = timezone.now()
        invoice.uploaded_at = timezone.now()
        invoice.save()
        
        # Clear session data
        request.session.pop(f'invoice_payment_session_{invoice_id}', None)
        
        messages.success(
            request, 
            f"Payment successful! Invoice #{invoice.invoice_no} has been marked as paid."
        )
        
        return redirect("pricing:business_invoices_list")
        
    except stripe.StripeError as e:
        messages.error(request, f"Payment verification error: {str(e)}")
        return redirect("pricing:business_invoices_list")
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect("pricing:business_invoices_list")