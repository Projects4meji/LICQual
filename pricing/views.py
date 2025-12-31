from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from superadmin.models import Course, BusinessDiscount, BusinessCourseDiscount
from .models import CoursePricing, InvoicePayment, InvoicedItem
from .forms import CoursePricingForm
from datetime import timedelta
from django.utils import timezone
from superadmin.models import Business, LearnerRegistration
from collections import defaultdict
from datetime import datetime as dt, timedelta
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Prefetch

DEFAULT_CURRENCY = "USD"
DEFAULT_AFFILIATE = Decimal("20.00")
DEFAULT_LEARNER = Decimal("40.00")


def get_discounted_price(business, course, price_type='affiliate'):
    """
    Get the discounted price for a business and course.
    
    Args:
        business: Business instance
        course: Course instance
        price_type: 'affiliate' or 'learner'
    
    Returns:
        tuple: (final_price, base_price, discount_percentage, currency)
    """
    try:
        pricing = CoursePricing.objects.get(course=course)
        base_price = getattr(pricing, f"{price_type}_price")
        currency = pricing.currency
    except CoursePricing.DoesNotExist:
        base_price = DEFAULT_AFFILIATE if price_type == 'affiliate' else DEFAULT_LEARNER
        currency = DEFAULT_CURRENCY
    
    # Check for per-course business discount first
    discount_percentage = Decimal("0.00")
    final_price = base_price
    try:
        course_discount = BusinessCourseDiscount.objects.get(business=business, course=course)
        discount_percentage = (
            course_discount.affiliate_discount_percentage
            if price_type == 'affiliate'
            else course_discount.learner_discount_percentage
        )
    except BusinessCourseDiscount.DoesNotExist:
        # Fallback to legacy business-wide discount ONLY if the business has no per-course discounts at all.
        has_any_course_discount = BusinessCourseDiscount.objects.filter(business=business).exists()
        if not has_any_course_discount:
            try:
                discount = BusinessDiscount.objects.get(business=business)
                discount_percentage = (
                    discount.affiliate_discount_percentage
                    if price_type == 'affiliate'
                    else discount.learner_discount_percentage
                )
            except BusinessDiscount.DoesNotExist:
                discount_percentage = Decimal("0.00")

    if discount_percentage and discount_percentage > 0:
        discount_amount = (base_price * discount_percentage) / 100
        final_price = max(Decimal("0.00"), base_price - discount_amount)
    else:
        final_price = base_price
        discount_percentage = Decimal("0.00")
    
    return final_price, base_price, discount_percentage, currency


def _ensure_pricing_for_courses(courses):
    """
    Ensure every course has a CoursePricing row with defaults if missing.
    Returns a dict {course_id: pricing_instance}
    """
    existing = {p.course_id: p for p in CoursePricing.objects.filter(course__in=courses)}
    to_create = []
    for c in courses:
        if c.id not in existing:
            to_create.append(CoursePricing(course=c,
                                           currency=DEFAULT_CURRENCY,
                                           affiliate_price=DEFAULT_AFFILIATE,
                                           learner_price=DEFAULT_LEARNER))
    if to_create:
        CoursePricing.objects.bulk_create(to_create)
        # refresh map
        existing = {p.course_id: p for p in CoursePricing.objects.filter(course__in=courses)}
    return existing

@login_required
def pricing_list(request):
    # Restrict as you prefer. Here: superusers only.
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    courses = Course.objects.all().order_by("title")
    pricing_map = _ensure_pricing_for_courses(courses)

    # Build rows (course + pricing) for template
    rows = [(c, pricing_map.get(c.id)) for c in courses]

    return render(request, "pricing/pricing_list.html", {"rows": rows})


@login_required
def pricing_edit(request, course_id: int):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    course = get_object_or_404(Course, pk=course_id)
    pricing, _ = CoursePricing.objects.get_or_create(
        course=course,
        defaults={
            "currency": DEFAULT_CURRENCY,
            "affiliate_price": DEFAULT_AFFILIATE,
            "learner_price": DEFAULT_LEARNER,
        },
    )

    form = CoursePricingForm(request.POST or None, instance=pricing)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f'Pricing updated for "{course.title}".')
        return redirect("pricing:pricing_list")

    return render(request, "pricing/pricing_edit.html", {"course": course, "form": form})


@login_required
def invoices(request):
    """
    Superuser report: For each affiliate (Business), show an invoice for all
    certificates ISSUED in the last 24 hours aligned to midnight
    (yesterday 00:00 -> today 00:00). Optional ?date=YYYY-MM-DD to view that day.
    """
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    # Default window = the last 24h ending at today's midnight (local tz)
    now_local = timezone.localtime()
    today_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    start = today_midnight - timedelta(days=1)
    end = today_midnight

    # Optional query param to view a specific day's invoice window
    # (?date=2025-09-28 shows that day's midnight-to-midnight)
    date_str = (request.GET.get("date") or "").strip()
    if date_str:
        try:
            d = dt.strptime(date_str, "%Y-%m-%d").date()
            tz = timezone.get_current_timezone()
            start = timezone.make_aware(dt.combine(d, dt.min.time()), tz)
            end = start + timedelta(days=1)
        except Exception:
            # ignore parse errors; keep default window
            pass

    # Pull all registrations that were ISSUED within the window
    regs = (
        LearnerRegistration.objects
        .select_related("learner", "course", "business")
        .filter(
            certificate_issued_at__gte=start,
            certificate_issued_at__lt=end,
        )
        .order_by("business__business_name", "course__title", "learner__full_name", "learner__email")
    )

    # Group: Business -> Course -> [regs]
    grouped = defaultdict(lambda: defaultdict(list))
    for r in regs:
        grouped[r.business_id][r.course_id].append(r)

    invoices = []
    for biz_id, courses_map in grouped.items():
        # Get the Business instance from any reg in this group
        any_regs = next(iter(courses_map.values()))
        business = any_regs[0].business if any_regs else Business.objects.get(pk=biz_id)

        lines = []      # per-course invoice lines
        learners = []   # flattened list of all learners for this invoice (all courses)

        for course_id, reg_list in courses_map.items():
            course = reg_list[0].course
            count = len(reg_list)

            # Pricing: use discounted affiliate price
            final_price, base_price, discount_percentage, currency = get_discounted_price(business, course, 'affiliate')
            unit_fee = final_price
            amount = unit_fee * count

            lines.append({
                "course_title": course.title,
                "count": count,
                "unit_fee": unit_fee,
                "currency": currency,
                "amount": amount,
            })

            for r in reg_list:
                learners.append({
                    "learner_name": (r.learner.full_name or r.learner.email),
                    "registered_on": r.created_at,
                    "issued_on_date": r.certificate_issue_date,
                    "issued_on_time": (r.certificate_issued_at if (r.certificate_issued_at and not r.awarded_date) else None),
                    "course_title": course.title,
                })

        issue_date = end  # invoice is issued at the end of the window (midnight)
        invoice_no = f"INV-{issue_date.date().isoformat()}-{business.id}"

        invoices.append({
            "business": business,
            "invoice_no": invoice_no,
            "issue_date": issue_date,
            "lines": lines,
            "learners": learners,
        })

    context = {
        "invoices": invoices,                   # list of per-business invoices
        "start": start,
        "end": end - timedelta(seconds=1),      # inclusive end for display
        "selected_date": start.date().isoformat(),
    }
    return render(request, "pricing/invoices.html", context)

def _range_from_post(request):
    """
    Parse range/start/end from POST; same semantics as _range_from_request for GET.
    Returns (start_dt, end_dt_exclusive, key, start_param, end_param).
    """
    key = (request.POST.get("range") or "yesterday").lower()
    tz = timezone.get_current_timezone()
    now_local = timezone.localtime()
    today = now_local.date()
    start = end = None

    if key == "yesterday":
        end = timezone.make_aware(dt.combine(today, dt.min.time()), tz)
        start = end - timedelta(days=1)

    elif key == "week":
        monday = (today - timedelta(days=today.weekday()))
        start = timezone.make_aware(dt.combine(monday, dt.min.time()), tz)
        end = start + timedelta(days=7)

    elif key == "month":
        first = today.replace(day=1)
        start = timezone.make_aware(dt.combine(first, dt.min.time()), tz)
        nxt = dt(first.year + (1 if first.month == 12 else 0),
                 1 if first.month == 12 else first.month + 1, 1)
        end = timezone.make_aware(nxt, tz)

    elif key == "custom":
        s = (request.POST.get("start") or "").strip()
        e = (request.POST.get("end") or "").strip()
        try:
            if s:
                start = timezone.make_aware(dt.strptime(s, "%Y-%m-%d"), tz)
            if e:
                end = timezone.make_aware(dt.strptime(e, "%Y-%m-%d"), tz) + timedelta(days=1)  # exclusive
        except Exception:
            key = "yesterday"
            end = timezone.make_aware(dt.combine(today, dt.min.time()), tz)
            start = end - timedelta(days=1)
    else:
        key = "yesterday"
        end = timezone.make_aware(dt.combine(today, dt.min.time()), tz)
        start = end - timedelta(days=1)

    start_param = start.date().isoformat()
    end_param = (end - timedelta(seconds=1)).date().isoformat()
    return start, end, key, start_param, end_param




def _range_from_request(request):
    """
    Returns (start_dt, end_dt_exclusive, selected_key, start_param, end_param).
    supported keys: 'yesterday', 'week', 'month', 'custom'
    For custom, pass ?start=YYYY-MM-DD&end=YYYY-MM-DD (inclusive on end).
    """
    key = (request.GET.get("range") or "month").lower()
    tz = timezone.get_current_timezone()
    now_local = timezone.localtime()
    today = now_local.date()
    start = end = None

    if key == "yesterday":
        end = timezone.make_aware(dt.combine(today, dt.min.time()), tz)
        start = end - timedelta(days=1)

    elif key == "week":
        monday = (today - timedelta(days=today.weekday()))
        start = timezone.make_aware(dt.combine(monday, dt.min.time()), tz)
        end = start + timedelta(days=7)

    elif key == "month":
        first = today.replace(day=1)
        start = timezone.make_aware(dt.combine(first, dt.min.time()), tz)
        if first.month == 12:
            nxt = dt(first.year + 1, 1, 1)
        else:
            nxt = dt(first.year, first.month + 1, 1)
        end = timezone.make_aware(nxt, tz)

    elif key == "custom":
        s = (request.GET.get("start") or "").strip()
        e = (request.GET.get("end") or "").strip()
        try:
            if s:
                start = timezone.make_aware(dt.strptime(s, "%Y-%m-%d"), tz)
            if e:
                # end is exclusive → add 1 day
                end = timezone.make_aware(dt.strptime(e, "%Y-%m-%d"), tz) + timedelta(days=1)
        except Exception:
            key = "month"
            first = today.replace(day=1)
            start = timezone.make_aware(dt.combine(first, dt.min.time()), tz)
            if first.month == 12:
                nxt = dt(first.year + 1, 1, 1)
            else:
                nxt = dt(first.year, first.month + 1, 1)
            end = timezone.make_aware(nxt, tz)
    else:
        key = "month"
        first = today.replace(day=1)
        start = timezone.make_aware(dt.combine(first, dt.min.time()), tz)
        if first.month == 12:
            nxt = dt(first.year + 1, 1, 1)
        else:
            nxt = dt(first.year, first.month + 1, 1)
        end = timezone.make_aware(nxt, tz)

    start_param = start.date().isoformat() if start else ""
    end_param = (end - timedelta(seconds=1)).date().isoformat() if end else ""  # inclusive for display/links
    return start, end, key, start_param, end_param



@login_required
def invoices_list(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    start, end, selected, start_param, end_param = _range_from_request(request)

    # Clamp end to NOW
    now_local = timezone.localtime()
    if end > now_local:
        end = now_local
    if start >= end:
        start = end - timedelta(days=1)

    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Pull invoices that were issued (period_end) inside the window
    invoices = (
        InvoicePayment.objects
        .select_related("business")
        .prefetch_related(
            Prefetch("items", queryset=InvoicedItem.objects.select_related("registration__course"))
        )
        .filter(period_end__gte=start, period_end__lt=end)
    )
    
    # Apply search filter if provided
    if search_query:
        from django.db.models import Q
        invoices = invoices.filter(
            Q(business__business_name__icontains=search_query) |
            Q(business__name__icontains=search_query) |
            Q(invoice_no__icontains=search_query) |
            Q(status__icontains=search_query)
        )
    
    invoices = invoices.order_by("business__business_name", "business__name", "-issued_at")

    rows = []
    for inv in invoices:
        # Total = sum of snapshot unit fees (1 reg = 1 unit)
        learner_total = sum((it.unit_fee for it in inv.items.all()), Decimal("0.00"))
        total = learner_total
        
        # Get currency from items
        currency = DEFAULT_CURRENCY
        if inv.items.all():
            currency = inv.items.first().currency
            
        proof_url = inv.proof_file.url if getattr(inv, "proof_file", None) else ""

        rows.append({
            "id": inv.id,
            "business": inv.business,
            "invoice_no": inv.invoice_no,
            "issue_date": inv.period_end,  # consistent with your UI
            "amount": total,
            "currency": currency,
            "proof_url": proof_url,
            "status": inv.status or "pending",
            "start": start_param,
            "end": end_param,
        })

    back_url = reverse("superadmin:superadmin_dashboard")

    return render(
        request,
        "pricing/invoices_list.html",
        {
            "rows": rows,
            "selected": selected,
            "start": start,
            "end": end - timedelta(seconds=1),
            "start_param": start_param,
            "end_param": end_param,
            "back_url": back_url,
            "search_query": search_query,
        },
    )


@login_required
@require_POST
def toggle_invoice_status(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    # Check if this is a bulk operation
    invoice_ids = request.POST.getlist("invoice_ids")
    bulk_status = request.POST.get("bulk_status")

    if invoice_ids and bulk_status:
        # Bulk operation
        try:
            invoice_ids_int = [int(id) for id in invoice_ids]
        except ValueError:
            messages.error(request, "Invalid invoice IDs.")
            return redirect(request.META.get("HTTP_REFERER") or "pricing:invoices_list")

        invoices = InvoicePayment.objects.filter(pk__in=invoice_ids_int)
        updated_count = invoices.update(status=bulk_status)
        messages.success(request, f"Updated {updated_count} invoice(s) to {bulk_status.title()}.")
    else:
        # Single invoice operation (existing functionality)
        try:
            invoice_id = int(request.POST.get("invoice_id") or "0")
        except ValueError:
            messages.error(request, "Invalid invoice.")
            return redirect("pricing:invoices_list")

        inv = get_object_or_404(InvoicePayment, pk=invoice_id)
        inv.status = "paid" if (inv.status or "pending").lower() != "paid" else "pending"
        inv.save(update_fields=["status"])
        messages.success(request, f"Invoice status set to {inv.status.title()}.")

    return redirect(request.META.get("HTTP_REFERER") or "pricing:invoices_list")




@login_required
def invoice_detail(request):
    # superuser or partner
    is_super = request.user.is_superuser
    is_partner = hasattr(request.user, "has_role") and request.user.has_role("partner")
    if not (is_super or is_partner):
        raise PermissionDenied("Not allowed.")

    try:
        invoice_id = int(request.GET.get("invoice_id") or "0")
    except ValueError:
        raise PermissionDenied("Invalid invoice.")
    
    inv = (
        InvoicePayment.objects
        .select_related("business")
        .prefetch_related(
            Prefetch("items", queryset=InvoicedItem.objects.select_related("registration__course", "registration__learner"))
        )
        .filter(pk=invoice_id)
        .first()
    )
    if not inv:
        raise PermissionDenied("Invoice not found.")

    # Partner can see only their own invoice
    if is_partner and not is_super:
        if inv.business.email.lower() != (request.user.email or "").lower():
            raise PermissionDenied("You cannot view this invoice.")

    # Process learner registration invoice
    has_learner_items = inv.items.exists()
    
    lines = []
    learners = []
    currency = None
    total = Decimal("0.00")
    
    if has_learner_items:
        # Process learner registrations
        by_course = defaultdict(list)
        for it in inv.items.all():
            by_course[it.course_title_snapshot].append(it)

        for course_title, items in by_course.items():
            count = len(items)
            unit_fee = items[0].unit_fee
            cur = items[0].currency
            currency = currency or cur
            amount = unit_fee * count
            total += amount

            lines.append({
                "course_title": course_title,
                "count": count,
                "unit_fee": unit_fee,
                "currency": cur,
                "amount": amount,
            })

            for it in items:
                r = it.registration
                learners.append({
                    "learner_name": (r.learner.full_name or r.learner.email),
                    "registered_on": r.created_at,
                    "issued_on": r.certificate_issued_at,
                    "course_title": course_title,
                })

    back_url = reverse("superadmin:superadmin_dashboard") if request.user.is_superuser else reverse("superadmin:business_dashboard")

    context = {
        "invoices": [{
            "business": inv.business,
            "invoice_no": inv.invoice_no,
            "issue_date": inv.period_end,  # your UI uses period_end as issue date
            "lines": lines,
            "learners": learners,
            "total": total,
            "currency": currency or DEFAULT_CURRENCY,
            "status": inv.status or "pending",
            "has_learner_items": has_learner_items,
        }],
        "start": inv.period_start,
        "end": inv.period_end - timedelta(seconds=1),
        "selected_date": inv.period_start.date().isoformat(),
        "selected": "custom",
        "back_url": back_url,
    }
    
    # Use invoices template
    template_name = "pricing/invoices.html"
    
    return render(request, template_name, context)





@login_required
def business_invoices_list(request):
    # partner or superuser
    if hasattr(request.user, "has_role") and not request.user.has_role("partner") and not request.user.is_superuser:
        raise PermissionDenied("Not a partner.")

    # Businesses owned by this account
    businesses = Business.objects.filter(email__iexact=request.user.email)
    if not request.user.is_superuser and not businesses.exists():
        raise PermissionDenied("No business associated with your account.")

    start, end, selected, start_param, end_param = _range_from_request(request)

    # Clamp end to NOW
    now_local = timezone.localtime()
    if end > now_local:
        end = now_local
    if start >= end:
        start = end - timedelta(days=1)

    inv_qs = (
        InvoicePayment.objects
        .select_related("business")
        .prefetch_related("items")
        .filter(period_end__gte=start, period_end__lt=end)
        .order_by("-issued_at")
    )
    if not request.user.is_superuser:
        inv_qs = inv_qs.filter(business__in=businesses)

    rows = []
    for inv in inv_qs:
        # Calculate total from learner registrations
        learner_total = sum((it.unit_fee for it in inv.items.all()), Decimal("0.00"))
        total = learner_total
        
        # Get currency from items
        currency = DEFAULT_CURRENCY
        if inv.items.all():
            currency = inv.items.first().currency
            
        proof_url = inv.proof_file.url if getattr(inv, "proof_file", None) else ""
        rows.append({
            "id": inv.id,
            "business": inv.business,
            "invoice_no": inv.invoice_no,
            "issue_date": inv.period_end,
            "amount": total,
            "currency": currency,
            "status": inv.status or "pending",
            "has_proof": bool(proof_url),
            "proof_url": proof_url,
        })

    return render(
        request,
        "pricing/business_invoices_list.html",
        {
            "rows": rows,
            "selected": selected,
            "start": start,
            "end": end - timedelta(seconds=1),
            "start_param": start_param,
            "end_param": end_param,
        },
    )


@login_required
def upload_payment_proof(request):
    if request.method != "POST":
        return redirect("pricing:business_invoices_list")

    try:
        invoice_id = int(request.POST.get("invoice_id") or "0")
    except (TypeError, ValueError):
        messages.error(request, "Invalid invoice.")
        return redirect("pricing:business_invoices_list")

    inv = get_object_or_404(InvoicePayment, pk=invoice_id)

    # Permissions: partner can upload only for their business; superuser can upload any
    if hasattr(request.user, "has_role") and request.user.has_role("partner") and not request.user.is_superuser:
        if inv.business.email.lower() != (request.user.email or "").lower():
            raise PermissionDenied("You cannot upload proof for this invoice.")

    file = request.FILES.get("proof_file")
    if not file:
        messages.error(request, "Please select a PDF or image to upload.")
        return redirect(request.META.get("HTTP_REFERER") or "pricing:business_invoices_list")

    ctype = (file.content_type or "").lower()
    if not (ctype.startswith("image/") or ctype == "application/pdf"):
        messages.error(request, "Only images or PDF are allowed.")
        return redirect(request.META.get("HTTP_REFERER") or "pricing:business_invoices_list")

    inv.proof_file = file
    inv.uploaded_by = request.user
    inv.uploaded_at = timezone.now()
    inv.save(update_fields=["proof_file", "uploaded_by", "uploaded_at"])

    messages.success(request, "Payment proof uploaded.")
    return redirect(request.META.get("HTTP_REFERER") or "pricing:business_invoices_list")




@login_required
@require_POST
def issue_invoices_now(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Superuser only.")

    # Always use the user-selected visible window
    rng = (request.POST.get("range") or "custom").lower()
    request.GET = request.GET.copy()
    request.GET["range"] = rng
    request.GET["start"] = request.POST.get("start") or ""
    request.GET["end"] = request.POST.get("end") or ""

    start, end, _, start_param, end_param = _range_from_request(request)

    # Clamp end to NOW (include same-day issuances)
    now_local = timezone.localtime()
    if end > now_local:
        end = now_local
    if start >= end:
        start = end - timedelta(days=1)

    # Pull all businesses which have un-invoiced regs in the window
    regs_qs = (
        LearnerRegistration.objects
        .select_related("business", "course", "learner")
        .filter(
            certificate_issued_at__gte=start,
            certificate_issued_at__lt=end,
            status=LearnerRegistration.Status.ISSUED,
            invoiced_item__isnull=True,  # <- NOT already invoiced
        )
        .order_by("business_id")
    )

    if not regs_qs.exists():
        messages.info(request, "No pending items to invoice for the selected window (or invoices already exist).")
        url = (
            f"{reverse('pricing:invoices_list')}"
            f"?range=custom&start={start.date().isoformat()}&end={(end - timedelta(seconds=1)).date().isoformat()}"
        )
        return redirect(url)

    # Group regs by business_id, then create one **new** invoice per business
    created_count = 0
    with transaction.atomic():
        by_biz = defaultdict(list)
        for r in regs_qs:
            by_biz[r.business_id].append(r)

        for biz_id, reg_list in by_biz.items():
            business = reg_list[0].business

            # Create a NEW invoice every time (no get_or_create!)
            invoice = InvoicePayment.objects.create(
                business=business,
                period_start=start,
                period_end=end,
                status="pending",
                invoice_no="TEMP",  # set after we have an id
            )

            # Stable, non-colliding number: include pk
            invoice.invoice_no = f"INV-{invoice.issued_at:%Y%m%d}-{business.id}-{invoice.id}"
            invoice.save(update_fields=["invoice_no"])

            items = []
            for r in reg_list:
                final_price, base_price, discount_percentage, currency = get_discounted_price(business, r.course, 'affiliate')

                items.append(
                    InvoicedItem(
                        invoice=invoice,
                        registration=r,
                        currency=currency,
                        unit_fee=final_price,
                        course_title_snapshot=r.course.title,
                    )
                )

            InvoicedItem.objects.bulk_create(items)
            created_count += 1

    messages.success(request, f"Issued {created_count} invoice(s).")
    url = (
        f"{reverse('pricing:invoices_list')}"
        f"?range=custom&start={start.date().isoformat()}&end={(end - timedelta(seconds=1)).date().isoformat()}"
    )
    return redirect(url)