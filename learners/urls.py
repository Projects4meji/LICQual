# learners/urls.py
from django.urls import path
from . import views

app_name = "learners"

urlpatterns = [
    path("dashboard/", views.learner_dashboard, name="learner_dashboard"),
    path("certificates/", views.learner_certificates, name="certificates"),  # placeholder
    path("learning/", views.learner_learning, name="learning"),              # placeholder
     path("certificate/<int:reg_id>/", views.view_certificate, name="view_certificate"),
    path("share-certificate/<int:reg_id>/", views.share_certificate_email, name="share_certificate_email"),
    path("certificates/<int:cert_id>/edit/", views.edit_cert, name="edit_cert"),
    path("certificates/add/", views.add_cert, name="add_cert"),
    path("certificates/user/<int:cert_id>/", views.view_user_certificate, name="view_user_certificate"),
    path("certificates/<int:cert_id>/delete/", views.delete_cert, name="delete_cert"),

]

