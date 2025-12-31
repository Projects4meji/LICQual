from django import template

register = template.Library()

@register.filter
def url_if_exists(fieldfile):
    """
    Returns the file URL if it exists, otherwise returns an empty string.
    Prevents template errors when the S3/Spaces file is missing.
    """
    if not fieldfile:
        return ""
    try:
        return fieldfile.url
    except Exception:
        return ""
