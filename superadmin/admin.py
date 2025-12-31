from django.utils.html import format_html
from .models import Business, Course, IsoCertification, QualificationSection, QualificationUnit
from users.models import CustomUser
from django.contrib import admin

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "business_name",
        "personnel_certifications_allowed",
        "iso_certification_allowed",
        "country",
        "created_at",
    )
    search_fields = ("name", "email", "business_name", "country")
    list_filter = ("personnel_certifications_allowed", "iso_certification_allowed", "country")


class QualificationUnitInline(admin.TabularInline):
    model = QualificationUnit
    extra = 1
    fields = ('order', 'unit_ref', 'unit_title', 'credits', 'glh_hours')
    ordering = ['order']


class QualificationSectionInline(admin.StackedInline):
    model = QualificationSection
    extra = 1
    fields = ('order', 'section_title', 'credits', 'tqt_hours', 'glh_hours', 'remarks')
    ordering = ['order']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "course_number", "duration_days", "category", "created_at")
    search_fields = ("title", "course_number", "category")
    list_filter = ("category",)
    filter_horizontal = ("businesses",)
    inlines = [QualificationSectionInline]


@admin.register(QualificationSection)
class QualificationSectionAdmin(admin.ModelAdmin):
    list_display = ("course", "section_title", "order", "credits")
    list_filter = ("course",)
    inlines = [QualificationUnitInline]


@admin.register(QualificationUnit)
class QualificationUnitAdmin(admin.ModelAdmin):
    list_display = ("section", "unit_ref", "unit_title", "order", "credits", "glh_hours")
    list_filter = ("section__course",)
    search_fields = ("unit_ref", "unit_title")


@admin.register(IsoCertification)
class IsoCertificationAdmin(admin.ModelAdmin):
    list_display = ("standard", "management_system", "iascb_accreditation_no", "updated_at")
    search_fields = ("standard", "management_system", "iascb_accreditation_no")