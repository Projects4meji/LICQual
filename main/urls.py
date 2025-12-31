# main/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.views import EmailLoginView
from superadmin.views import verify_certificate


urlpatterns = [
    path("", EmailLoginView.as_view(), name="login"),  # Login at root
    path("admin/", admin.site.urls),
    
    # Certificate Verification (Public)
    path("verify/", verify_certificate, name="verify_certificate_form"),
    path("verify/<str:code>/", verify_certificate, name="verify_certificate"),
    
    path("superadmin/", include(("superadmin.urls", "superadmin"), namespace="superadmin")),  
    path("users/", include(("users.urls", "users"), namespace="users")),
    path("learners/", include(("learners.urls", "learners"), namespace="learners")),  
    path("pricing/", include(("pricing.urls", "pricing"), namespace="pricing")),  
    path("captcha/", include("captcha.urls")),


]

# serve static/media in development + debug toolbar
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

