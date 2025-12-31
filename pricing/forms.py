from django import forms
from .models import CoursePricing, IsoPricing

class CoursePricingForm(forms.ModelForm):
    class Meta:
        model = CoursePricing
        fields = ["currency", "affiliate_price", "learner_price"]
        widgets = {
            "currency": forms.TextInput(attrs={"class": "rounded-md border px-3 py-2 w-24"}),
            "affiliate_price": forms.NumberInput(attrs={"class": "rounded-md border px-3 py-2 w-32", "step": "0.01", "min": "0"}),
            "learner_price": forms.NumberInput(attrs={"class": "rounded-md border px-3 py-2 w-32", "step": "0.01", "min": "0"}),
        }


class IsoPricingForm(forms.ModelForm):
    class Meta:
        model = IsoPricing
        fields = ["currency", "base_price"]
        widgets = {
            "currency": forms.TextInput(attrs={"class": "rounded-md border px-3 py-2 w-24"}),
            "base_price": forms.NumberInput(attrs={"class": "rounded-md border px-3 py-2 w-32", "step": "0.01", "min": "0"}),
        }
