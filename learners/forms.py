# learners/forms.py
from django import forms
from .models import LearnerCertificate

class LearnerCertificateForm(forms.ModelForm):
    class Meta:
        model = LearnerCertificate
        fields = ["title", "issuing_body", "issue_date", "expiry_date", "file"]
        widgets = {
            "title": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter certificate or degree title"
            }),
            "issuing_body": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Enter issuing organization or institution"
            }),
            "issue_date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-input"
            }),
            "expiry_date": forms.DateInput(attrs={
                "type": "date",
                "class": "form-input"
            }),
            "file": forms.FileInput(attrs={
                "class": "file-input",
                "accept": "image/png,image/jpeg,image/jpg,application/pdf,.png,.jpg,.jpeg,.pdf"
            }),
        }
        labels = {
            "title": "Certificate/Degree Title",
            "issuing_body": "Issuing Body",
            "issue_date": "Issue Date",
            "expiry_date": "Expiry (if any)",
            "file": "Upload Certificate (PNG, JPG, PDF)",
        }
