# pricing/urls.py
from django.urls import path
from . import views

app_name = "pricing"

urlpatterns = [
    path("", views.pricing_list, name="pricing_list"),
    path("edit/<int:course_id>/", views.pricing_edit, name="pricing_edit"),
    path("invoices/", views.invoices_list, name="invoices_list"),
    path("invoices/detail/", views.invoice_detail, name="invoice_detail"),
    path("invoices/my/", views.business_invoices_list, name="business_invoices_list"),
    path("invoices/proof/upload/", views.upload_payment_proof, name="upload_payment_proof"),
    path("invoices/toggle-status/", views.toggle_invoice_status, name="toggle_invoice_status"),  
    path("invoices/issue-now/", views.issue_invoices_now, name="issue_invoices_now"),


]
