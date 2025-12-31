from django.contrib import admin
from .models import CoursePricing

@admin.register(CoursePricing)
class CoursePricingAdmin(admin.ModelAdmin):
    list_display = ("course", "currency", "affiliate_price", "learner_price", "updated_at")
    search_fields = ("course__title",)
