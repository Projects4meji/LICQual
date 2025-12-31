# learners/views.py
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from users.models import Role
from superadmin.models import LearnerRegistration
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.urls import reverse
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.utils.text import slugify
import io
from PIL import Image
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from superadmin.models import LearnerRegistration
from superadmin.views import generate_and_attach_certificate  # reuse generator
from .models import LearnerCertificate
from .forms import LearnerCertificateForm
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
import secrets
from django.core.files.storage import default_storage
from django.utils import timezone

def _ensure_learner(user):
    if not (hasattr(user, "has_role") and user.has_role(Role.Names.LEARNER)):
        raise PermissionDenied("Learner account required.")

@login_required
def learner_dashboard(request):
    _ensure_learner(request.user)
    
    # Determine active tab from query parameter
    active_tab = request.GET.get('tab', 'courses')
    
    # Get all registrations
    all_regs = (
        LearnerRegistration.objects
        .filter(learner=request.user)
        .select_related("course", "business")
        .order_by("-created_at")
    )
    
    # Filter based on active tab
    if active_tab == 'certificates':
        # Use the same logic as learner_certificates view
        # System-issued (ICTQUAL) - show all issued certificates (not just shared)
        regs = all_regs.filter(certificate_issued_at__isnull=False).select_related("course")
        
        # Learner-uploaded certificates
        from learners.models import LearnerCertificate
        uploads = LearnerCertificate.objects.filter(owner=request.user)
        
        # Build rows list with same structure as certificates page
        certificate_rows = []
        for r in regs:
            certificate_rows.append({
                "title": r.course.title,
                "issue_date": r.certificate_issue_date,
                "issued_by": "LICQual",
                "expiry": None,
                "status": "active",
                "view_url": reverse("learners:view_certificate", args=[r.id]),
                "kind": "system",
                "can_edit": False,
                "edit_url": None,
                "delete_url": None,
                "can_view": bool(getattr(r, "certificate_shared_at", None)),
            })
        
        for u in uploads:
            certificate_rows.append({
                "title": u.title,
                "issue_date": u.issue_date,
                "issued_by": u.issuing_body,
                "expiry": u.expiry_date,
                "status": "active" if u.is_active else "expired",
                "view_url": reverse("learners:view_user_certificate", args=[u.id]),
                "kind": "upload",
                "can_edit": True,
                "edit_url": reverse("learners:edit_cert", args=[u.id]),
                "delete_url": reverse("learners:delete_cert", args=[u.id]),
                "can_view": True,
            })
        
        # Sort by issue date (newest first, None dates last)
        certificate_rows.sort(key=lambda x: (x["issue_date"] is None, x["issue_date"]), reverse=True)
    else:
        regs = all_regs
        certificate_rows = None

    # NEW: only show the Business Dashboard button if the user is also a Partner
    show_business_btn = hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER)

    return render(request, "learners/learner_dashboard.html", {
        "active_tab": active_tab,
        "registrations": regs,
        "all_registrations": all_regs,  # For stats calculation
        "certificate_rows": certificate_rows,  # Structured certificate data
        "show_business_btn": show_business_btn,
    })



@login_required
def learner_certificates(request):
    """
    Show all certificates:
    - System-issued (ICTQUAL) from LearnerRegistration (issued only)
    - Learner-uploaded (LearnerCertificate)
    Columns: Sr#, Title, Issue Date, Issued By, Expiry Date, Status, Action
    Only learner-uploaded rows are editable.
    """
    _ensure_learner(request.user)
    from django.core.files.storage import default_storage  # (already imported at top in your file)

    # Introspect storage the Django 5.2 way
    _wrapper = default_storage
    _underlying = getattr(default_storage, "_wrapped", default_storage)

    print("DEFAULT STORAGE (wrapper) =", type(_wrapper).__name__)
    print("UNDERLYING STORAGE =", type(_underlying).__name__)
    print("USE_REMOTE_MEDIA =", getattr(settings, "USE_REMOTE_MEDIA", None))
    print("MEDIA_URL =", getattr(settings, "MEDIA_URL", None))
    print("AWS_STORAGE_BUCKET_NAME =", getattr(settings, "AWS_STORAGE_BUCKET_NAME", None))
    print("AWS_S3_CUSTOM_DOMAIN =", getattr(settings, "AWS_S3_CUSTOM_DOMAIN", None))
    print("AWS_S3_ENDPOINT_URL =", getattr(settings, "AWS_S3_ENDPOINT_URL", None))



    # System-issued (ICTQUAL)
    regs = (
        LearnerRegistration.objects
        .filter(learner=request.user, certificate_issued_at__isnull=False)
        .select_related("course")
    )

    # Learner-uploaded
    uploads = LearnerCertificate.objects.filter(owner=request.user)

    # Debug each upload object for verification (wrapper + underlying storage)
    _wrapped = getattr(default_storage, "_wrapped", default_storage)
    for _u in uploads:
        try:
            print(
                "UPLOAD DEBUG -> key:", _u.file.name,
                "| url:", _u.file.url,
                "| wrapper:", type(_u.file.storage).__name__,
                "| underlying:", type(_wrapped).__name__,
            )
        except Exception as e:
            print("UPLOAD DEBUG -> error obtaining url:", e)

    rows = []
    for r in regs:
        rows.append({
            "title": r.course.title,
            "issue_date": r.certificate_issue_date,
            "issued_by": "LICQual",
            "expiry": None,
            "status": "active",
            "view_url": reverse("learners:view_certificate", args=[r.id]),
            "kind": "system",
            "can_edit": False,
            "edit_url": None,
            "delete_url": None,   # NEW
            # NEW: Only allow viewing if the certificate has been SHARED
            "can_view": bool(getattr(r, "certificate_shared_at", None)),
        })



    for u in uploads:
        rows.append({
            "title": u.title,
            "issue_date": u.issue_date,
            "issued_by": u.issuing_body,
            "expiry": u.expiry_date,
            "status": "active" if u.is_active else "expired",
            "view_url": reverse("learners:view_user_certificate", args=[u.id]),
            "kind": "upload",
            "can_edit": True,
            "edit_url": reverse("learners:edit_cert", args=[u.id]),
            "delete_url": reverse("learners:delete_cert", args=[u.id]),   # NEW
            # Uploaded certificates are always viewable by the owner
            "can_view": True,
        })



    # Newest first (None dates last)
    rows.sort(key=lambda x: (x["issue_date"] is None, x["issue_date"]), reverse=True)

    return render(request, "learners/certificates.html", {"rows": rows})




@login_required
def learner_learning(request):
    _ensure_learner(request.user)
    # Placeholder section
    return render(request, "learners/learner_dashboard.html", {
        "active_tab": "learning",
        "registrations": [],
    })


@login_required
@never_cache
def view_certificate(request, reg_id: int):
    """
    Allow the logged-in learner to view their own certificate as a PDF.
    Generates the file on-demand if missing.
    """
    reg = get_object_or_404(
        LearnerRegistration.objects.select_related("learner", "course", "business"),
        pk=reg_id
    )


    # Read the latest learner name directly from DB to avoid stale relation cache
    from users.models import CustomUser
    db_alias = getattr(reg._state, "db", "default")
    fu = (CustomUser.objects.using(db_alias)
        .only("full_name", "email")
        .get(pk=reg.learner_id))
    name_root = (fu.full_name or fu.email) or "certificate"
    safe_name = slugify(name_root).replace("-", "_") or "certificate"



    # Must belong to the logged-in learner
    if reg.learner_id != request.user.id:
        raise PermissionDenied("You do not have access to this certificate.")

    # NEW: Must have been shared with this learner by an admin/partner
    if not reg.certificate_shared_at:
        raise PermissionDenied("This certificate hasn't been shared with you yet.")


    # Generate certificate PDF on-demand without saving to storage
    # Note: generate_certificate_pdf will use default template if course template is not set
    try:
        from superadmin.views import generate_certificate_pdf
        pdf_bytes = generate_certificate_pdf(reg)
        
        if not pdf_bytes or len(pdf_bytes) == 0:
            raise Http404("Certificate could not be generated.")
        
        # Return PDF inline
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{safe_name}.pdf"'
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"
        return response
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Certificate generation failed for registration {reg_id}: {e}")
        raise Http404("Certificate could not be generated.")


@login_required
def share_certificate_email(request, reg_id: int):
    """
    Email the learner their certificate as a PDF attachment.
    Allowed for superuser or Partner who owns the business registration.
    """
    reg = get_object_or_404(
        LearnerRegistration.objects.select_related("learner", "course", "business"),
        pk=reg_id
    )

    # Permission: superuser OR partner who owns this registration's business
    if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER) and not request.user.is_superuser:
        if reg.business.email.lower() != request.user.email.lower():
            raise PermissionDenied("You cannot share a certificate outside your business.")
    elif not request.user.is_superuser:
        # If not partner and not superuser, block (only admins/partners share)
        raise PermissionDenied("Not allowed.")

    # Helper function to get redirect URL
    def get_redirect_url():
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return next_url
        referer = request.META.get('HTTP_REFERER', '')
        if 'learners_list' in referer or '/learners/' in referer:
            return reverse("superadmin:learners_list")
        elif 'all-registered-learners' in referer:
            return reverse("superadmin:all_registered_learners")
        elif 'learner_specific' in referer or f'/learners/{reg.learner_id}/' in referer:
            return reverse("superadmin:learner_specific", args=[reg.learner_id])
        return reverse("superadmin:registered_learners", args=[reg.course_id])

    if request.method != "POST":
        # Redirect back politely
        return redirect(get_redirect_url())

    # Must be issued
    if not reg.certificate_issued_at:
        messages.error(request, "Certificate has not been issued yet.")
        return redirect(get_redirect_url())

    # Generate certificate PDF on-demand without saving
    # Note: generate_certificate_pdf will use default template if course template is not set
    try:
        from superadmin.views import generate_certificate_pdf
        pdf_bytes = generate_certificate_pdf(reg)
        if not pdf_bytes or len(pdf_bytes) == 0:
            messages.error(request, "Could not prepare the certificate PDF.")
            return redirect(get_redirect_url())
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Certificate generation failed for share email: {e}")
        messages.error(request, "Could not prepare the certificate PDF.")
        return redirect(get_redirect_url())


    # Compose email

    # Use the freshest learner name for the attachment filename
    from users.models import CustomUser
    db_alias = getattr(reg._state, "db", "default")
    fu = (CustomUser.objects.using(db_alias)
        .only("full_name", "email")
        .get(pk=reg.learner_id))
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

    import logging
    logger = logging.getLogger(__name__)

    # Logo handling (same as welcome email)
    logo_url = getattr(settings, "EMAIL_LOGO_URL", "") or None
    logo_cid = None
    logo_base64 = None
    img_bytes = None

    from django.contrib.staticfiles import finders
    import os
    import base64
    
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

    # Prefer CID when we have logo bytes (same approach as welcome email)
    if img_bytes and len(img_bytes) > 0:
        logo_cid = "licqual-logo"
        final_logo_url = ""
        logo_base64 = None
    else:
        final_logo_url = ""
        if logo_url and (logo_url.startswith("http://") or logo_url.startswith("https://") or logo_url.startswith("//")):
            final_logo_url = logo_url

        # If no hosted URL, fall back to base64 (no attachments)
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
        "logo_url": final_logo_url,  # Prioritize hosted URL
        "logo_cid": logo_cid if not final_logo_url else None,  # Only use CID if no URL
        "logo_base64": logo_base64 if not final_logo_url else None,  # Only use base64 if no URL
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
    
    # Only attach inline image if we're using CID (not hosted URL)
    # Hosted URLs don't need attachments - they're loaded directly from the web
    if logo_cid and img_bytes and not final_logo_url:
        try:
            from email.mime.image import MIMEImage
            if img_bytes.startswith(b'\xff\xd8'):
                img_type = "jpeg"
            elif img_bytes.startswith(b'\x89PNG'):
                img_type = "png"
            elif img_bytes.startswith(b'GIF'):
                img_type = "gif"
            else:
                img_type = "jpeg"
            
            img = MIMEImage(img_bytes, _subtype=img_type)
            img.add_header("Content-ID", f"<{logo_cid}>")
            img.add_header("Content-Disposition", "inline", filename="licqual-logo.jpg")
            msg.attach(img)
            logger.info("Attached logo as CID inline image")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not attach logo image to certificate email: {e}")
    elif final_logo_url:
        logger.info("Using hosted logo URL - no attachment needed")

    # safe_name was computed above using a fresh DB read
    filename = f"{safe_name}.pdf"
    msg.attach(filename, pdf_bytes, "application/pdf")
    try:
        msg.send(fail_silently=False)
    except Exception:
        messages.error(request, "Failed to send the email to the learner.")
        return redirect(get_redirect_url())

    # NEW: record that the certificate has been shared (only after successful email send)
    LearnerRegistration.objects.filter(pk=reg.pk).update(certificate_shared_at=timezone.now())


    messages.success(request, f"Certificate shared with {reg.learner.email}.")
    return redirect(get_redirect_url())


@login_required
def add_cert(request):
    """
    Form for learners to add their own certificate (title, issuing body, issue/expiry dates, file).
    """
    _ensure_learner(request.user)

    if request.method == "POST":
        form = LearnerCertificateForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.owner = request.user
            obj.save()

            # DEBUG: prove underlying storage really is S3Boto3Storage behind the DefaultStorage wrapper
            wrapped = getattr(default_storage, "_wrapped", default_storage)
            print("UNDERLYING STORAGE CLASS =", type(wrapped).__name__)

            print("SAVED TO STORAGE (wrapper):", type(obj.file.storage).__name__)
            print("OBJECT KEY (file.name):", obj.file.name)
            try:
                print("PUBLIC URL (file.url):", obj.file.url)
            except Exception as e:
                print("PUBLIC URL error:", e)



            # Debug: prove where it went
            print("SAVED TO STORAGE:", type(obj.file.storage).__name__)
            print("OBJECT KEY (file.name):", obj.file.name)
            try:
                print("PUBLIC URL (file.url):", obj.file.url)
            except Exception as e:
                print("PUBLIC URL error:", e)

            messages.success(request, "Certificate added successfully.")
            return redirect("learners:certificates")
    else:
        form = LearnerCertificateForm()

    return render(request, "learners/add_cert.html", {"form": form})



@login_required
def view_user_certificate(request, cert_id: int):
    """
    Stream the uploaded certificate (PDF inline). If the file is an image, convert to a one-page PDF on the fly.
    """
    cert = get_object_or_404(LearnerCertificate, pk=cert_id, owner=request.user)
    if not cert.file:
        raise Http404("Certificate file not found.")

    name_root = slugify((cert.title or "certificate")).replace("-", "_") or "certificate"
    stored_name = (cert.file.name or "").lower()

    try:
        if stored_name.endswith(".pdf"):
            with cert.file.open("rb") as f:
                data = f.read()
            resp = HttpResponse(data, content_type="application/pdf")
            resp["Content-Disposition"] = f'inline; filename="{name_root}.pdf"'
            return resp
        # Convert image to PDF
        with cert.file.open("rb") as f:
            img = Image.open(f).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="PDF", resolution=300.0)
            buf.seek(0)
        resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{name_root}.pdf"'
        return resp
    except Exception:
        raise Http404("Could not load or convert the certificate file.")


@login_required
def edit_cert(request, cert_id: int):
    """
    Allow a learner to edit details of their *own uploaded* certificate.
    """
    _ensure_learner(request.user)
    cert = get_object_or_404(LearnerCertificate, pk=cert_id, owner=request.user)

    if request.method == "POST":
        form = LearnerCertificateForm(request.POST, request.FILES, instance=cert)
        if form.is_valid():
            form.save()
            messages.success(request, "Certificate updated successfully.")
            return redirect("learners:certificates")
    else:
        form = LearnerCertificateForm(instance=cert)

    return render(request, "learners/edit_cert.html", {"form": form, "cert": cert})


@login_required
@require_POST
def delete_cert(request, cert_id: int):
    """
    Delete a learner's *own uploaded* certificate.
    System-issued (ICTQUAL) certificates are NOT handled here.
    """
    _ensure_learner(request.user)
    cert = get_object_or_404(LearnerCertificate, pk=cert_id, owner=request.user)

    # remove file from storage first (don't save model on file delete)
    if cert.file:
        cert.file.delete(save=False)

    cert.delete()
    messages.success(request, "Certificate deleted.")
    return redirect("learners:certificates")
