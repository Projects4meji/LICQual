from decimal import Decimal
from django.db import models
from superadmin.models import Course, IsoCertification
from django.db import models
from django.conf import settings
from superadmin.models import Business


class CoursePricing(models.Model):
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name="pricing"
    )
    currency = models.CharField(max_length=3, default="USD")  # e.g., USD, GBP, EUR
    affiliate_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("20.00"))
    learner_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("40.00"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Course Pricing"
        verbose_name_plural = "Course Pricing"

    def __str__(self):
        return f"{self.course.title} — {self.currency} {self.affiliate_price}/{self.learner_price}"


class IsoPricing(models.Model):
    iso_certification = models.OneToOneField(
        IsoCertification,
        on_delete=models.CASCADE,
        related_name="pricing"
    )
    currency = models.CharField(max_length=3, default="USD")  # e.g., USD, GBP, EUR
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("250.00"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "ISO Pricing"
        verbose_name_plural = "ISO Pricing"

    def __str__(self):
        return f"{self.iso_certification.standard} — {self.currency} {self.base_price}"


class InvoicePayment(models.Model):
    """
    Stores a single payment proof per business and invoice window.
    Invoice is identified by:
      - business (FK)
      - period_end (the invoice 'issue' moment, exclusive end of the window)
    """
    STATUS = (
        ("unpaid", "Unpaid"),
        ("paid", "Paid"),
    )

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="invoice_payments")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    invoice_no = models.CharField(max_length=64, db_index=True)

    proof_file = models.FileField(upload_to="invoice_proofs/", blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS, default="unpaid")

    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_at = models.DateTimeField(blank=True, null=True)

    marked_paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="marked_paid_invoices")
    marked_paid_at = models.DateTimeField(blank=True, null=True)
    issued_at = models.DateTimeField(auto_now_add=True)  

    class Meta:
        unique_together = ("business", "period_end")  # one record per invoice window per business
        ordering = ["-period_end"]

    def __str__(self):
        return f"{self.invoice_no} ({self.business.business_name or self.business.name})"


from django.db import models

class InvoicedItem(models.Model):
    invoice = models.ForeignKey(
        'pricing.InvoicePayment',
        related_name='items',
        on_delete=models.CASCADE,
    )
    registration = models.OneToOneField(              # 1 registration → 1 invoice
        'superadmin.LearnerRegistration',
        related_name='invoiced_item',
        on_delete=models.PROTECT,
    )
    # SNAPSHOTS captured at invoice issuance time
    currency = models.CharField(max_length=10, default='USD')
    unit_fee = models.DecimalField(max_digits=9, decimal_places=2)
    course_title_snapshot = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=['invoice']),
            models.Index(fields=['registration']),
        ]


class IsoInvoicedItem(models.Model):
    """
    Invoice items for ISO certifications
    """
    invoice = models.ForeignKey(
        'pricing.InvoicePayment',
        related_name='iso_items',
        on_delete=models.CASCADE,
    )
    certificate = models.OneToOneField(              # 1 certificate → 1 invoice
        'superadmin.IsoIssuedCertificate',
        related_name='invoiced_item',
        on_delete=models.PROTECT,
    )
    # SNAPSHOTS captured at invoice issuance time
    currency = models.CharField(max_length=10, default='USD')
    unit_fee = models.DecimalField(max_digits=9, decimal_places=2)
    iso_standard_snapshot = models.CharField(max_length=255)
    management_system_snapshot = models.CharField(max_length=255)
    certificate_number = models.CharField(max_length=50)

    class Meta:
        indexes = [
            models.Index(fields=['invoice']),
            models.Index(fields=['certificate']),
        ]
