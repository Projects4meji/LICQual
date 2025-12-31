from django.urls import path
from .views import superadmin_dashboard, delete_business, edit_business, edit_learner, bulk_issue_and_download, learner_specific, toggle_revoke_registration, learners_list, toggle_profile_lock, edit_user, business_performance, delete_registration, list_of_learners, all_registered_learners, toggle_business_restriction, register_learners, download_certificate, issue_certificate, issue_all_certificates, download_all_certificates, registered_learners, add_business, assign_courses, business_list, business_dashboard, add_course, course_list, edit_course, business_courses, assign_course, assignment, unassign_course_from_business, business_details, toggle_advance_payment, business_discounts, edit_business_discount, delete_business_discount, business_pricing, create_payment_session, payment_success, payment_cancel, stripe_webhook, pay_invoice_stripe, invoice_payment_success, bulk_toggle_profile_lock, assign_courses_to_learner, view_certificate_sample

app_name = "superadmin"

urlpatterns = [
    path("dashboard/", superadmin_dashboard, name="superadmin_dashboard"),
    path("businesses/add/", add_business, name="add_business"),
    path("businesses/<int:pk>/edit/", edit_business, name="edit_business"),
    path("businesses/", business_list, name="business_list"),  
    path("business/dashboard/", business_dashboard, name="business_dashboard"),
    path("business/pricing/", business_pricing, name="business_pricing"),
    path("courses/add/", add_course, name="add_course"),
    path("courses/", course_list, name="course_list"),
    path("courses/<int:pk>/edit/", edit_course, name="edit_course"),
    path("courses/<int:course_id>/certificate-sample/", view_certificate_sample, name="view_certificate_sample"),
    path("courses/<int:pk>/assign/", assign_course, name="assign_course"),
    path("courses/<int:pk>/assignment/", assignment, name="assignment"),
    path("business/<int:business_id>/", business_details, name="business_details"),
    path("business/<int:business_id>/unassign/<int:course_id>/", unassign_course_from_business, name="unassign_course_from_business"),
    path("business/courses/", business_courses, name="business_courses"),
    path("business/<int:business_id>/assign-courses/",assign_courses,name="assign_courses",),
    path("business/courses/<int:course_id>/register/", register_learners, name="register_learners"),
    path("business/courses/<int:course_id>/learners/", registered_learners, name="registered_learners"),
    path("business/courses/registration/<int:reg_id>/issue/", issue_certificate, name="issue_certificate"),
    path("business/courses/registration/<int:reg_id>/download/", download_certificate, name="download_certificate"),
    path("business/courses/<int:course_id>/issue-all/", issue_all_certificates, name="issue_all_certificates"),
    path("business/courses/<int:course_id>/download-all/", download_all_certificates, name="download_all_certificates"),
    path("business/performance/", business_performance, name="business_performance"),
    path("business/performance/learners/<int:business_id>/", list_of_learners, name="list_of_learners"),
    path("business/<int:business_id>/toggle-restriction/", toggle_business_restriction, name="toggle_business_restriction"),
    path("business/<int:business_id>/toggle-advance-payment/", toggle_advance_payment, name="toggle_advance_payment"),
    path("registrations/<int:reg_id>/delete/", delete_registration, name="delete_registration"),
    path("all-registered-learners/", all_registered_learners, name="all_registered_learners"),
    path("registered-learners/<int:reg_id>/edit/", edit_learner, name="edit_learner"),
    path("learners/", learners_list, name="learners_list"),
    path("learners/<int:learner_id>/assign-courses/", assign_courses_to_learner, name="assign_courses_to_learner"),
    path("learners/<int:user_id>/edit/", edit_user, name="edit_user"),
    path("learners/<int:user_id>/toggle-lock/", toggle_profile_lock, name="toggle_profile_lock"),
    path("learners/bulk-toggle-lock/", bulk_toggle_profile_lock, name="bulk_toggle_profile_lock"),
    path("learners/<int:user_id>/", learner_specific, name="learner_specific"),
    path("registrations/<int:reg_id>/toggle-revoke/", toggle_revoke_registration,name="toggle_revoke_registration",),
    path("business/courses/registrations/bulk-issue-download/", bulk_issue_and_download, name="bulk_issue_download"),
    path("business/<int:pk>/delete/", delete_business, name="delete_business"),
    path("discounts/", business_discounts, name="business_discounts"),
    path("discounts/<int:business_id>/edit/", edit_business_discount, name="edit_business_discount"),
    path("discounts/<int:business_id>/delete/", delete_business_discount, name="delete_business_discount"),
    
    # Payment URLs
    path("payment/<int:course_id>/create/", create_payment_session, name="create_payment_session"),
    path("payment/success/", payment_success, name="payment_success"),
    path("payment/cancel/<int:course_id>/", payment_cancel, name="payment_cancel"),
    path("stripe/webhook/", stripe_webhook, name="stripe_webhook"),
    
    # Invoice Payment URLs
    path("invoice/<int:invoice_id>/pay/", pay_invoice_stripe, name="pay_invoice_stripe"),
    path("invoice/payment/success/", invoice_payment_success, name="invoice_payment_success"),

    # …existing urls…
]

