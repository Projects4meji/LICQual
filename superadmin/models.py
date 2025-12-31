from django.db import models
from users.models import Role  
from django.conf import settings
from django.core.validators import FileExtensionValidator, MinValueValidator, RegexValidator
import random, string
from django.db.models import JSONField  
from users.storage_backends import CertTemplateStorage, CertSampleStorage, IsoTemplateStorage, CertOutputStorage
from decimal import Decimal



class Business(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    business_name = models.CharField(max_length=255, blank=True)
    personnel_certifications_allowed = models.BooleanField(default=True)
    iso_certification_allowed = models.BooleanField(default=False)
    country = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_restricted = models.BooleanField(default=False)
    atp_number = models.CharField(max_length=5, unique=True, blank=True, null=True, db_index=True, help_text="AA000 format.")
    atp_qr_image = models.ImageField(upload_to="atp_qr/", blank=True, null=True)
    advance_payment = models.BooleanField(default=False)

    # --- Authorization certificate (base template + optional sample + layout) ---
    auth_cert_template = models.FileField(
        storage=CertTemplateStorage(),
        upload_to="",
        blank=True, null=True,
        validators=[FileExtensionValidator(["png", "jpg", "jpeg"])],
        help_text="Upload base image (PNG/JPG) for the Authorization Certificate.",
    )
    
    auth_cert_layout = models.JSONField(
        blank=True,
        default=dict,
        help_text=(
            "Layout in relative positions (0..1). Keys:\n"
            '  - "name"   {"x":0.50,"y":0.45,"fs":64}\n'
            '  - "number" {"x":0.50,"y":0.55,"fs":40}\n'
            '  - "date"   {"x":0.50,"y":0.62,"fs":28}\n'
            '  - "qrcode" {"x":0.85,"y":0.85,"size":220}\n'
            "All coordinates are relative to the image width/height."
        ),
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.email})"


class Course(models.Model):  # singular is conventional in Django
    title = models.CharField(max_length=255)
    course_number = models.CharField(max_length=50)         # alphanumeric safe
    duration_days = models.PositiveIntegerField(default=1)  # "Days" (legacy field, use 'duration' instead)
    duration = models.CharField(max_length=100, blank=True, default='')  # Flexible duration text (e.g., "3 Days", "2 Years")
    category = models.CharField(max_length=100, blank=True)
    certificate_title_override = models.TextField(
    blank=True,
    help_text=(
        "Optional alternate title for certificate. "
        "Supports line breaks to split across multiple lines "
        "(e.g., 'ISO 9001:2015\\nLead Auditor Course')."
    ),
)

    STYLE_CHOICES = (
        ("lead", "Lead Auditor"),
        ("internal", "Internal Auditor"),
        ("other", "Other Certificates"),
        ("osha", "OSHA"),
    )

    certificate_style = models.CharField(max_length=20, choices=STYLE_CHOICES, default="lead", help_text="Select a layout preset. You can fine-tune positions in code presets.")
    course_description = models.TextField(blank=True,help_text="Short paragraph describing the course. Can be printed on certificates.")
    show_course_description_on_certificate = models.BooleanField(default=False,help_text="If enabled, the course_description will be printed on the certificate after the learner name.")
    iascb_course_number = models.CharField(max_length=20,blank=True,db_index=True, validators=[RegexValidator(r"^I-\d{3,6}$", "Use format I-#### (e.g., I-1547).")], help_text="IASCB Course No. (e.g., I-1547).",)
    credit_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0)],help_text="Total credit hours (e.g., 0.5, 1.6).")

    certificate_template = models.FileField(
        storage=CertTemplateStorage(),
        upload_to="",
        blank=True, null=True,
        validators=[FileExtensionValidator(["png", "jpg", "jpeg", "svg"])],
        help_text="Upload a certificate template (PNG, JPG, or SVG).",
    )
    certificate_sample = models.FileField(
        storage=CertSampleStorage(),
        upload_to="",
        blank=True, null=True,
        validators=[FileExtensionValidator(["pdf"])],
        help_text="Upload a sample learner certificate (PDF).",
    )


    businesses = models.ManyToManyField("superadmin.Business", related_name="courses", blank=True, help_text="Assign this course to one or more businesses.")
    created_at = models.DateTimeField(auto_now_add=True)

    certificate_layout = models.JSONField(
        blank=True,
        default=dict,
        help_text=(
            "Optional JSON layout (relative positions 0..1). Supported keys:\n"
            '  - "name"   (Learner Name)\n'
            '  - "course" (Course Title)\n'
            '  - "issued" (Certificate Issuance Date)\n'
            '  - "credit" (Credit Hours)\n'
            '  - "number" (Certificate Number)\n'
            '  - "qrcode" (QR code to verification URL)\n'
            "Example: "
            '{"name":{"x":0.50,"y":0.45,"fs":64,"color":"#0B2545","anchor":"mm"},'
            '"course":{"x":0.50,"y":0.55,"fs":40,"color":"#0B2545","anchor":"mm"},'
            '"issued":{"x":0.50,"y":0.62,"fs":28,"color":"#0B2545","anchor":"mm"},'
            '"credit":{"x":0.50,"y":0.68,"fs":24,"color":"#0B2545","anchor":"mm"},'
            '"number":{"x":0.88,"y":0.90,"fs":20,"color":"#111827","anchor":"rm"},'
            '"qrcode":{"x":0.12,"y":0.88,"size":220,"anchor":"lm"}}'
        ),
    )

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title


class QualificationSection(models.Model):
    """
    Represents a section/year of a qualification (e.g., Year 1, Year 2).
    Each section appears on a separate certificate page (page 2, 3, etc.)
    """
    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='sections')
    section_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional section heading (e.g., 'Year 1: Foundational Knowledge')"
    )
    order = models.PositiveIntegerField(
        default=1,
        help_text="Display order for this section"
    )
    credits = models.PositiveIntegerField(
        default=120,
        help_text="Credits for this section (e.g., 120)"
    )
    tqt_hours = models.PositiveIntegerField(
        default=1200,
        help_text="Total Qualification Time in hours (e.g., 1200)"
    )
    glh_hours = models.PositiveIntegerField(
        default=600,
        help_text="Guided Learning Hours (e.g., 600)"
    )
    remarks = models.CharField(
        max_length=255,
        default="Grade Pass",
        help_text="Remarks text (e.g., 'Grade Pass')"
    )
    
    class Meta:
        ordering = ['course', 'order']
        unique_together = ['course', 'order']
    
    def __str__(self):
        return f"{self.course.title} - {self.section_title or f'Section {self.order}'}"


class QualificationUnit(models.Model):
    """
    Represents an individual unit within a qualification section.
    """
    section = models.ForeignKey('QualificationSection', on_delete=models.CASCADE, related_name='units')
    unit_ref = models.CharField(
        max_length=50,
        help_text="Unit reference code (e.g., 'AGE0001-1')"
    )
    unit_title = models.CharField(
        max_length=500,
        help_text="Unit title (e.g., 'Introduction to Agricultural Engineering')"
    )
    order = models.PositiveIntegerField(
        default=1,
        help_text="Display order for this unit within the section"
    )

    credits = models.PositiveIntegerField(
        default=0,
        help_text="Credits for this unit (e.g., 10)"
    )
    glh_hours = models.PositiveIntegerField(
        default=0,
        help_text="Guided Learning Hours for this unit (e.g., 40)"
    )
    
    class Meta:
        ordering = ['section', 'order']
        unique_together = ['section', 'order']
    
    def __str__(self):
        return f"{self.unit_ref}: {self.unit_title}"


class LearnerRegistration(models.Model):
    class Status:
        PENDING = "pending"
        ISSUED = "issued"
        CHOICES = (
            (PENDING, "Pending"),
            (ISSUED, "Issued"),
        )

    course = models.ForeignKey('Course', on_delete=models.CASCADE, related_name='registrations')
    business = models.ForeignKey('Business', on_delete=models.CASCADE, related_name='registrations')
    learner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='course_registrations')
    created_at = models.DateTimeField(auto_now_add=True)
        # Training dates (From / To)
    training_from = models.DateField(blank=True, null=True, db_index=True)
    training_to = models.DateField(blank=True, null=True, db_index=True)

    is_revoked = models.BooleanField(default=False, db_index=True, help_text="If True, verification by code/QR should fail.")

    # Certificate fields
    certificate_file = models.FileField(upload_to='certificates/', blank=True, null=True)

    certificate_file = models.FileField(
        storage=CertOutputStorage(),
        upload_to="",
        blank=True, null=True
    )

    certificate_issued_at = models.DateTimeField(blank=True, null=True)
    certificate_number = models.CharField(max_length=50, unique=True, blank=True,null=True,db_index=True,help_text="Auto-generated certificate number (e.g., ATC265788) or legacy certificate number.",)
    learner_number = models.CharField(max_length=6, unique=True, blank=True, null=True, db_index=True, help_text="6-digit unique learner number (256001-999999)")
    certificate_shared_at = models.DateTimeField(blank=True, null=True, db_index=True)  
    certificate_expiry_date = models.DateField(blank=True, null=True, help_text="Certificate expiry date (for legacy certificates with expiry)")
    awarded_date = models.DateField(blank=True, null=True, help_text="Date to display on certificate as the awarded date (max 60 days in the past, no future dates)")

    # NEW: status (pending/issued)
    status = models.CharField(max_length=20,choices=Status.CHOICES,default=Status.PENDING,db_index=True,)

    class Meta:
        unique_together = ('course', 'learner', 'business')  # allow same learner for same course under different businesses



    def _generate_unique_learner_number(self) -> str:
        """
        Generate a unique 6-digit learner number between 256001 and 999999.
        Retries up to 50 times to avoid collisions.
        """
        for _ in range(50):
            number = str(random.randint(256001, 999999))
            if not LearnerRegistration.objects.filter(learner_number=number).exists():
                return number
        # Extremely unlikely fallback
        return str(random.randint(256001, 999999))

    def _generate_unique_certificate_number(self) -> str:
        """
        Generate a unique certificate number in the format ATC + 6 digits
        (e.g., ATC265788). Numbers range from 265001 to 999999.
        Retries up to 50 times to avoid collisions.
        """
        for _ in range(50):
            number = random.randint(265001, 999999)
            code = f"ATC{number}"
            if not LearnerRegistration.objects.filter(certificate_number=code).exists():
                return code
        # Extremely unlikely fallback
        return f"ATC{random.randint(265001, 999999)}"

    def __str__(self):
        return f"{self.learner.email} → {self.course.title}"
    
    def save(self, *args, **kwargs):
        # Generate learner number if not present
        if not self.learner_number:
            self.learner_number = self._generate_unique_learner_number()
        
        # Keep status consistent with certificate_issued_at
        if self.certificate_issued_at and self.status != self.Status.ISSUED:
            self.status = self.Status.ISSUED

        # If being issued (by date or status) and number is missing → generate
        if (self.certificate_issued_at or self.status == self.Status.ISSUED) and not self.certificate_number:
            self.certificate_number = self._generate_unique_certificate_number()

        super().save(*args, **kwargs)

    @property
    def certificate_issue_date(self):
        if self.awarded_date:
            return self.awarded_date
        if self.certificate_issued_at:
            return self.certificate_issued_at.date()
        return None




class IsoCertification(models.Model):
    standard = models.CharField(max_length=120, help_text="e.g., ISO 45001:2018")
    management_system = models.CharField(max_length=120, help_text="e.g., OHS Mgt system")
    iascb_accreditation_no = models.CharField("IASCB Accreditation No", max_length=120, blank=True)
    businesses = models.ManyToManyField("superadmin.Business", related_name="iso_certifications",blank=True)
    template_image = models.ImageField(
        storage=IsoTemplateStorage(),
        upload_to="",
        blank=True, null=True,
        validators=[FileExtensionValidator(allowed_extensions=["png"])],
        help_text="Upload a PNG base template for this ISO certificate.",
    )
    iso_pdf_layout = JSONField(default=dict, blank=True, help_text=(
        "Layout for ISO PDF (pixels or percents where noted). "
        "Examples: {"
        '"fs_business": 210, "fs_iso": 300, "fs_body": 102, "fs_small": 66,'
        '"y_start": 460, "gap_after_business": 52, "gap_after_addr": 250,'
        '"col_side_margin_px": 260, "col_gap_px": 24, "row_gap": 0.80,'
        '"qr_size": 520, "x_qr": 1680, "y_qr": 2700,'
        '"legal_start_pct": 0.70,'"}"
    ))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["standard"]
        verbose_name = "ISO Certification"
        verbose_name_plural = "ISO Certifications"

    def __str__(self):
        return f"{self.standard} — {self.management_system}"


# --- NEW: store issued ISO certificates ---
class IsoIssuedCertificate(models.Model):
    iso = models.ForeignKey("superadmin.IsoCertification", on_delete=models.CASCADE, related_name="issued_certs")
    issuer_business = models.ForeignKey("superadmin.Business", on_delete=models.CASCADE, related_name="issued_iso_certs", null=True, blank=True)

    certified_business_name = models.CharField(max_length=255)
    certified_business_address = models.TextField()
    scope_text = models.TextField(help_text="Line breaks will be preserved.")
    recipient_email = models.EmailField(blank=True)

    certificate_number = models.CharField(max_length=50, unique=True, db_index=True)  # format: AAA000 or ICTQUAL-XXX-XXX-XXXX
    issued_at = models.DateTimeField(auto_now_add=True)

    # Dates to display on verification page
    surveillance_1_date = models.DateField()
    surveillance_2_date = models.DateField()
    expiry_date = models.DateField()

    # Store generated QR image (optional but handy)
    qr_image = models.ImageField(upload_to="iso_qr/", blank=True, null=True)

    is_revoked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"{self.certificate_number} — {self.certified_business_name}"


class BusinessDiscount(models.Model):
    """
    Store discount percentages for specific businesses.
    This allows different pricing for different businesses while maintaining base pricing.
    """
    business = models.OneToOneField(
        Business, 
        on_delete=models.CASCADE, 
        related_name="discount"
    )
    affiliate_discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal("0.00"),
        help_text="Discount percentage for affiliate pricing (0-100)"
    )
    learner_discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal("0.00"),
        help_text="Discount percentage for learner pricing (0-100)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Superuser who created this discount"
    )

    class Meta:
        verbose_name = "Business Discount"
        verbose_name_plural = "Business Discounts"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.business.business_name or self.business.name} - {self.affiliate_discount_percentage}% / {self.learner_discount_percentage}%"

    def get_discounted_affiliate_price(self, base_price):
        """Calculate discounted affiliate price"""
        if not base_price:
            return Decimal("0.00")
        discount_amount = (base_price * self.affiliate_discount_percentage) / 100
        return max(Decimal("0.00"), base_price - discount_amount)

    def get_discounted_learner_price(self, base_price):
        """Calculate discounted learner price"""
        if not base_price:
            return Decimal("0.00")
        discount_amount = (base_price * self.learner_discount_percentage) / 100
        return max(Decimal("0.00"), base_price - discount_amount)


class BusinessCourseDiscount(models.Model):
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="course_discounts",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="business_course_discounts",
    )
    affiliate_discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Discount percentage for affiliate pricing (0-100)",
    )
    learner_discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Discount percentage for learner pricing (0-100)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        unique_together = ["business", "course"]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.business.business_name or self.business.name} — {self.course.title}"


class PaymentSession(models.Model):
    """
    Track Stripe payment sessions for advance payments
    """
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='payment_sessions')
    course = models.ForeignKey('Course', on_delete=models.CASCADE)
    stripe_session_id = models.CharField(max_length=255, unique=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    number_of_learners = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    failure_reason = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Payment Session"
        verbose_name_plural = "Payment Sessions"
    
    def __str__(self):
        return f"Payment for {self.business.business_name or self.business.name} - {self.course.title} - {self.status}"


class LearnerRegistrationPayment(models.Model):
    """
    Link learner registrations to payment sessions for advance payment tracking
    """
    payment_session = models.ForeignKey(PaymentSession, on_delete=models.CASCADE, related_name='registrations')
    registration = models.OneToOneField('LearnerRegistration', on_delete=models.CASCADE, related_name='payment')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Learner Registration Payment"
        verbose_name_plural = "Learner Registration Payments"
    
    def __str__(self):
        return f"Payment for {self.registration.learner.full_name} - {self.registration.course.title}"


class IsoPaymentSession(models.Model):
    """
    Payment session for ISO certifications (similar to PaymentSession for courses)
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='iso_payment_sessions')
    iso_certification = models.ForeignKey(IsoCertification, on_delete=models.CASCADE, related_name='payment_sessions')
    stripe_session_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    
    class Meta:
        verbose_name = "ISO Payment Session"
        verbose_name_plural = "ISO Payment Sessions"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"ISO Payment for {self.business.business_name or self.business.name} - {self.iso_certification.standard} - {self.status}"


class IsoIssuedCertificatePayment(models.Model):
    """
    Link issued ISO certificates to payment sessions for advance payment tracking
    """
    payment_session = models.ForeignKey(IsoPaymentSession, on_delete=models.CASCADE, related_name='certificates')
    certificate = models.OneToOneField('IsoIssuedCertificate', on_delete=models.CASCADE, related_name='payment')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "ISO Certificate Payment"
        verbose_name_plural = "ISO Certificate Payments"
    
    def __str__(self):
        return f"Payment for {self.certificate.certificate_number} - {self.certificate.iso.standard}"


