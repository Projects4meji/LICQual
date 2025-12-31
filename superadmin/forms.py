# superadmin/forms.py
from django import forms
from django.utils.html import strip_tags
from .models import Business, Course, IsoIssuedCertificate, IsoCertification, BusinessDiscount
import re
from users.models import CustomUser
from decimal import Decimal, InvalidOperation
from django.utils.html import strip_tags as _strip_tags
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator
import json

def _sanitize(text: str) -> str:
    return strip_tags(text or "").strip()



def max_lines_validator(max_lines: int):
    def _validator(value: str):
        lines = (value or "").splitlines()
        if len(lines) > max_lines:
            raise ValidationError(f"Scope must be at most {max_lines} lines. You entered {len(lines)}.")
    return _validator


class BusinessForm(forms.ModelForm):
    class Meta:
        model = Business
        fields = [
            "name",
            "email",
            "business_name",
            "personnel_certifications_allowed",
            "iso_certification_allowed",
            "country",
            "advance_payment",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "w-full border rounded-md px-3 py-2 focus:outline-none focus:ring",
                "placeholder": "Full name",
                "maxlength": "255",
                "autocomplete": "name",
            }),
            "email": forms.EmailInput(attrs={
                "class": "w-full border rounded-md px-3 py-2 focus:outline-none focus:ring",
                "placeholder": "user@example.com",
                "autocomplete": "email",
            }),
            "business_name": forms.TextInput(attrs={
                "class": "w-full border rounded-md px-3 py-2 focus:outline-none focus:ring",
                "placeholder": "Business name",
                "maxlength": "255",
                "autocomplete": "organization",
            }),
            "personnel_certifications_allowed": forms.CheckboxInput(attrs={"class": "h-4 w-4"}),
            "iso_certification_allowed": forms.CheckboxInput(attrs={"class": "h-4 w-4"}),
            "advance_payment": forms.CheckboxInput(attrs={"class": "h-4 w-4"}),
            "country": forms.TextInput(attrs={
                "class": "w-full border rounded-md px-3 py-2 focus:outline-none focus:ring",
                "placeholder": "Country",
                "maxlength": "100",
                "autocomplete": "country-name",
            }),
        }

    # sanitize text inputs
    def clean_name(self):
        return _sanitize(self.cleaned_data.get("name"))

    def clean_business_name(self):
        return _sanitize(self.cleaned_data.get("business_name"))

    def clean_country(self):
        return _sanitize(self.cleaned_data.get("country"))

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()



def _strip_tags(value: str) -> str:
    # Ensure value is a string, not None
    if value is None:
        return ""
    if not value:
        return ""
    # Convert to string in case it's not already
    value = str(value)
    # lightweight HTML tag stripper (no external deps)
    return re.sub(r"<[^>]+>", "", value).strip()

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = [
            "title",
            "course_number",
            "certificate_template",
            "certificate_sample",
            "businesses",
        ]

        widgets = {
            "title": forms.TextInput(attrs={
                "class": "block w-full rounded-md border-2 border-gray-300 shadow-sm text-base px-4 py-2",
                "placeholder": "Qualification Title",
                "onfocus": "this.style.borderColor='#0B2545';",
                "onblur": "this.style.borderColor='#ccc';",
                "style": "outline-color:#0B2545; border-color:#ccc;"
            }),
            "course_number": forms.TextInput(attrs={
                "class": "block w-full rounded-md border-2 border-gray-300 shadow-sm text-base px-4 py-2",
                "placeholder": "e.g., QUAL-001",
                "onfocus": "this.style.borderColor='#0B2545';",
                "onblur": "this.style.borderColor='#ccc';",
                "style": "outline-color:#0B2545; border-color:#ccc;"
            }),
            "businesses": forms.SelectMultiple(attrs={
                "class": "block w-full rounded-md border-2 border-gray-300 shadow-sm text-base px-4 py-2",
                "size": "6",
                "style": "outline-color:#0B2545; border-color:#ccc;"
            }),

            "certificate_template": forms.ClearableFileInput(attrs={
                "accept": "image/png,image/jpeg,image/svg+xml,.png,.jpg,.jpeg,.svg",
                "class": "block w-full rounded-md border-2 border-gray-300 shadow-sm text-base px-4 py-2",
            }),

            "certificate_sample": forms.ClearableFileInput(attrs={
                "accept": "application/pdf,.pdf",
                "class": "block w-full rounded-md border-2 border-gray-300 shadow-sm text-base px-4 py-2",
            }),
        }

    # Simple sanitization
    def clean_title(self):
        return _strip_tags(self.cleaned_data.get("title", ""))

    def clean_course_number(self):
        return _strip_tags(self.cleaned_data.get("course_number", ""))




class LearnerEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["full_name", "email", "is_profile_locked"]  # include lock only for superadmin

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("request_user", None)  # pass request.user from the view if you want
        super().__init__(*args, **kwargs)

        # add CSS classes
        self.fields["full_name"].widget.attrs.update({"class": "form-input"})
        self.fields["email"].widget.attrs.update({"class": "form-input"})

        # hide lock field for non-superusers, but style it for superusers
        if user is not None and not getattr(user, "is_superuser", False):
            self.fields.pop("is_profile_locked", None)
        elif "is_profile_locked" in self.fields:
            # Add styling for the checkbox when superuser is editing
            self.fields["is_profile_locked"].widget.attrs.update({"class": "toggle-checkbox"})



class IsoCertificationForm(forms.ModelForm):
    class Meta:
        model = IsoCertification
        fields = ["standard", "management_system", "iascb_accreditation_no", "template_image"]
        labels = {
            "standard": "ISO Standard",
            "management_system": "Management System",
            "iascb_accreditation_no": "IASCB Accreditation No",
            "template_image": "ISO Template (PNG)",
        }
        widgets = {
            "standard": forms.TextInput(attrs={"class": "w-full", "placeholder": "e.g., ISO 45001:2018"}),
            "management_system": forms.TextInput(attrs={"class": "w-full", "placeholder": "e.g., OHS Mgt system"}),
            "iascb_accreditation_no": forms.TextInput(attrs={"class": "w-full", "placeholder": "e.g., IASCB-12345"}),
            "template_image": forms.ClearableFileInput(attrs={"class": "w-full", "accept": "image/png"}),
        }



class IsoIssueForm(forms.ModelForm):
    # Limits
    MAX_ADDR_CHARS = 160            # your example string is 82 chars long
    MAX_SCOPE_CHARS = 650            # limit scope to 650 Chars long

    class Meta:
        model = IsoIssuedCertificate
        fields = ["certified_business_name", "certified_business_address", "scope_text", "recipient_email"]
        labels = {
            "certified_business_name": "Business Name",
            "certified_business_address": "Address of the business",
            "scope_text": "Scope of Certification",
            "recipient_email": "Email of ISO certificate recipient (optional)",
        }
        widgets = {
            "certified_business_name": forms.TextInput(
                attrs={"class": "w-full", "placeholder": "e.g., ABC Manufacturing Ltd."}
            ),
            # Add maxlength=82 to enforce in the browser too
            "certified_business_address": forms.Textarea(
                attrs={
                    "class": "w-full",
                    "rows": 3,
                    "maxlength": "160",

                    "placeholder": "Street, City, State/Province, Country (max 160 chars)",
                }
            ),
            # Make scope 5 rows tall and tag it with data-max-lines=5 for front-end limiting
            "scope_text": forms.Textarea(
                attrs={
                    "class": "w-full",
                    "rows": 5,
                    "placeholder": "Enter the scope (max 650 characters; line breaks are preserved).",
                    "maxlength": "650",             # ← browser stops at 650
                    "data-max-chars": "650",        # ← used by the live counter script
                }
            ),

            "recipient_email": forms.EmailInput(
                attrs={"class": "w-full", "placeholder": "optional@email.com"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Address: browser hint + server validator
        self.fields["certified_business_address"].widget.attrs["maxlength"] = str(self.MAX_ADDR_CHARS)
        self.fields["certified_business_address"].validators.append(
            MaxLengthValidator(self.MAX_ADDR_CHARS, message=f"Address must be at most {self.MAX_ADDR_CHARS} characters.")
        )

        # Scope: 650-char cap (browser + server)
        self.fields["scope_text"].widget.attrs["rows"] = 5
        self.fields["scope_text"].widget.attrs["maxlength"] = str(self.MAX_SCOPE_CHARS)
        self.fields["scope_text"].widget.attrs["data-max-chars"] = str(self.MAX_SCOPE_CHARS)
        self.fields["scope_text"].validators.append(
            MaxLengthValidator(self.MAX_SCOPE_CHARS, message=f"Scope must be at most {self.MAX_SCOPE_CHARS} characters.")
        )


    def clean_certified_business_address(self):
        addr = (self.cleaned_data.get("certified_business_address") or "").replace("\r\n", "\n").strip()
        if len(addr) > self.MAX_ADDR_CHARS:
            raise ValidationError(f"Address must be at most {self.MAX_ADDR_CHARS} characters.")
        return addr


    def clean_scope_text(self):
        text = (self.cleaned_data.get("scope_text") or "").replace("\r\n", "\n")
        return text.rstrip()



class AtpTemplateUploadForm(forms.Form):
    auth_cert_template = forms.ImageField(
        required=True,
        label="Base Certificate Image (PNG/JPG)",
        help_text="Upload the base certificate image (PNG/JPG) used for all ATP certificates (unless a Business overrides it).",
    )
    auth_cert_layout = forms.CharField(
        required=False,
        label="Layout JSON (optional, global)",
        help_text='Relative coordinates 0..1 (e.g. {"name":{"x":0.5,"y":0.42,"fs":72},"number":{"x":0.5,"y":0.52,"fs":48},"date":{"x":0.5,"y":0.60,"fs":36},"qrcode":{"x":0.85,"y":0.80,"size":260}})',
        widget=forms.Textarea(attrs={"rows": 8}),
    )

    def clean_auth_cert_layout(self):
        raw = (self.cleaned_data.get("auth_cert_layout") or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception as e:
            raise forms.ValidationError(f"Invalid JSON: {e}")
        if not isinstance(data, dict):
            raise forms.ValidationError("Layout must be a JSON object.")
        return data
    
class AtpGlobalTemplateForm(forms.Form):
    template_png = forms.ImageField(
        required=True,
        label="ATP Authorization Template (PNG)",
        help_text="Upload a single PNG image that will be used for all ATP certificates."
    )


class CentreApplicationApprovalForm(forms.Form):
    advance_payment = forms.BooleanField(
        required=False,
        label="Advance Payment Required",
        help_text="Check if this business requires advance payment for services",
        widget=forms.CheckboxInput(attrs={"class": "h-4 w-4"})
    )


class BusinessDiscountForm(forms.ModelForm):
    class Meta:
        model = BusinessDiscount
        fields = ["affiliate_discount_percentage", "learner_discount_percentage"]
        widgets = {
            "affiliate_discount_percentage": forms.NumberInput(attrs={
                "class": "w-full border rounded-md px-3 py-2 focus:outline-none focus:ring",
                "step": "0.01",
                "min": "0",
                "max": "100",
                "placeholder": "0.00"
            }),
            "learner_discount_percentage": forms.NumberInput(attrs={
                "class": "w-full border rounded-md px-3 py-2 focus:outline-none focus:ring",
                "step": "0.01",
                "min": "0",
                "max": "100",
                "placeholder": "0.00"
            }),
        }

    def clean_affiliate_discount_percentage(self):
        value = self.cleaned_data.get("affiliate_discount_percentage")
        if value is not None and (value < 0 or value > 100):
            raise forms.ValidationError("Discount percentage must be between 0 and 100.")
        return value

    def clean_learner_discount_percentage(self):
        value = self.cleaned_data.get("learner_discount_percentage")
        if value is not None and (value < 0 or value > 100):
            raise forms.ValidationError("Discount percentage must be between 0 and 100.")
        return value


class AwardedDateForm(forms.Form):
    """Form for inputting awarded date when issuing certificates."""
    awarded_date = forms.DateField(
        required=True,
        label="Awarded Date",
        help_text="The date to display on the certificate (max 60 days in the past, no future dates)",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'w-full border rounded-md px-3 py-2 focus:outline-none focus:ring',
            'max': '',  # Will be set via JavaScript
            'min': '',   # Will be set via JavaScript
        })
    )

    def clean_awarded_date(self):
        from django.utils import timezone
        from datetime import timedelta
        
        awarded_date = self.cleaned_data.get('awarded_date')
        if not awarded_date:
            return awarded_date
        
        today = timezone.now().date()
        max_past_date = today - timedelta(days=60)
        
        if awarded_date > today:
            raise ValidationError("Awarded date cannot be in the future.")
        
        if awarded_date < max_past_date:
            raise ValidationError(f"Awarded date cannot be more than 60 days in the past. Minimum date: {max_past_date.strftime('%Y-%m-%d')}.")
        
        return awarded_date