from django.conf import settings

def stripe_context(request):
    """
    Add Stripe configuration to template context
    """
    return {
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY,
        'STRIPE_DEBUG_MODE': settings.DEBUG,
    }

def business_sidebar_context(request):
    """
    Add recent courses for business partners to sidebar context
    """
    context = {}
    
    # Only add courses if user is a business partner
    if request.user.is_authenticated:
        from users.models import Role
        if hasattr(request.user, "has_role") and request.user.has_role(Role.Names.PARTNER):
            from superadmin.models import Business, Course
            
            # Get partner's businesses
            partner_businesses = Business.objects.filter(email__iexact=request.user.email)
            
            if partner_businesses.exists():
                # Get recent 3 courses assigned to the business, ordered by creation date (most recent first)
                recent_courses = Course.objects.filter(
                    businesses__in=partner_businesses,
                    businesses__is_restricted=False
                ).distinct().order_by('-created_at')[:3]
                
                context['recent_courses'] = recent_courses
    
    return context
