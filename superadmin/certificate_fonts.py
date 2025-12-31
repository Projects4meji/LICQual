"""
Certificate Font Configuration
Defines fonts to be used for different certificate elements.
"""

from pathlib import Path
from django.conf import settings

# Font file paths
FONTS_DIR = Path(settings.BASE_DIR) / "static" / "fonts"

CERTIFICATE_FONTS = {
    # Page 1 Fonts
    "learner_number": {
        "path": FONTS_DIR / "Corbel-Regular.ttf",
        "family": "Corbel",
        "size": 16,  # Default size, can be overridden
    },
    "certificate_number": {
        "path": FONTS_DIR / "Corbel-Regular.ttf",
        "family": "Corbel",
        "size": 16,
    },
    "qualification_number": {
        "path": FONTS_DIR / "Corbel-Regular.ttf",
        "family": "Corbel",
        "size": 16,
    },
    "learner_name": {
        "path": FONTS_DIR / "bookantiquabolditalic.ttf",
        "family": "BookAntiquaBoldItalic",
        "size": 48,  # Larger for name
    },
    "qualification_title": {
        "path": FONTS_DIR / "Book Antiqua.ttf",
        "family": "BookAntiqua",
        "size": 32,
    },
    "delivered_by": {
        "path": FONTS_DIR / "Book Antiqua.ttf",
        "family": "BookAntiqua",
        "size": 18,
    },
    
    # Page 2 Fonts (Units)
    "section_title": {
        "path": FONTS_DIR / "Book Antiqua.ttf",
        "family": "BookAntiqua",
        "size": 24,
    },
    "unit_ref": {
        "path": FONTS_DIR / "Montserrat-Regular.ttf",
        "family": "Montserrat",
        "size": 14,
    },
    "unit_title": {
        "path": FONTS_DIR / "Montserrat-Regular.ttf",
        "family": "Montserrat",
        "size": 14,
    },
    "awarded_date": {
        "path": FONTS_DIR / "Candara-Regular.ttf",
        "family": "Candara",
        "size": 14,
    },
    "duration": {
        "path": FONTS_DIR / "Candara-Regular.ttf",
        "family": "Candara",
        "size": 14,
    },
    "location": {
        "path": FONTS_DIR / "Candara-Regular.ttf",
        "family": "Candara",
        "size": 14,
    },
    "remarks": {
        "path": FONTS_DIR / "Candara-Regular.ttf",
        "family": "Candara",
        "size": 12,
    },
}


def get_font_path(font_key):
    """
    Get the file path for a specific font.
    
    Args:
        font_key (str): Key from CERTIFICATE_FONTS dict
        
    Returns:
        Path: Absolute path to the font file
        
    Raises:
        KeyError: If font_key is not found
        FileNotFoundError: If font file doesn't exist
    """
    if font_key not in CERTIFICATE_FONTS:
        raise KeyError(f"Font key '{font_key}' not found in CERTIFICATE_FONTS")
    
    font_path = CERTIFICATE_FONTS[font_key]["path"]
    
    if not font_path.exists():
        raise FileNotFoundError(
            f"Font file not found: {font_path}\n"
            f"Please ensure all required fonts are in {FONTS_DIR}"
        )
    
    return str(font_path)


def get_font_config(font_key):
    """
    Get complete font configuration including path, family, and size.
    
    Args:
        font_key (str): Key from CERTIFICATE_FONTS dict
        
    Returns:
        dict: Font configuration with 'path', 'family', and 'size'
    """
    if font_key not in CERTIFICATE_FONTS:
        raise KeyError(f"Font key '{font_key}' not found in CERTIFICATE_FONTS")
    
    config = CERTIFICATE_FONTS[font_key].copy()
    config["path"] = str(config["path"])
    
    return config


def load_font_for_pil(font_key, size=None):
    """
    Load a font for use with PIL/Pillow ImageDraw.
    
    Args:
        font_key (str): Key from CERTIFICATE_FONTS dict
        size (int, optional): Font size. Uses default if None.
        
    Returns:
        PIL.ImageFont.FreeTypeFont: Loaded font object
    """
    from PIL import ImageFont
    
    config = get_font_config(font_key)
    font_size = size if size is not None else config["size"]
    
    return ImageFont.truetype(config["path"], font_size)


def load_font_for_reportlab(font_key):
    """
    Register and return font for use with ReportLab.
    
    Args:
        font_key (str): Key from CERTIFICATE_FONTS dict
        
    Returns:
        tuple: (font_family_name, font_size)
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    
    config = get_font_config(font_key)
    
    # Register font if not already registered
    try:
        pdfmetrics.getFont(config["family"])
    except KeyError:
        pdfmetrics.registerFont(TTFont(config["family"], config["path"]))
    
    return config["family"], config["size"]


# Font usage guide for certificate generation
FONT_USAGE_GUIDE = """
Certificate Font Usage Guide
============================

Page 1 (Main Certificate):
--------------------------
- Learner Number: Corbel (use 'learner_number')
- Certificate Number: Corbel (use 'certificate_number')
- Qualification Number: Corbel (use 'qualification_number')
- Learner Name: Raleway (use 'learner_name')
- Qualification Title: Raleway (use 'qualification_title')
- "Delivered and assessed by": Raleway (use 'delivered_by')

Page 2+ (Units Pages):
---------------------
- Section Title: Raleway (use 'section_title')
- Unit Reference: Corbel (use 'unit_ref')
- Unit Title: Corbel (use 'unit_title')
- Awarded Date: Candara (use 'awarded_date')
- Duration/Credits: Candara (use 'duration')
- Location/Business: Candara (use 'location')
- Remarks: Candara (use 'remarks')

Example Usage with PIL:
-----------------------
from superadmin.certificate_fonts import load_font_for_pil
from PIL import Image, ImageDraw

img = Image.open('certificate_template.png')
draw = ImageDraw.Draw(img)

# Draw learner name
name_font = load_font_for_pil('learner_name')
draw.text((500, 400), "JOHN DOE", font=name_font, fill='#000000')

# Draw certificate number
cert_num_font = load_font_for_pil('certificate_number')
draw.text((100, 100), "ICTQ12345", font=cert_num_font, fill='#000000')

Example Usage with ReportLab:
-----------------------------
from superadmin.certificate_fonts import load_font_for_reportlab
from reportlab.pdfgen import canvas

c = canvas.Canvas("certificate.pdf")

# Use learner name font
font_family, font_size = load_font_for_reportlab('learner_name')
c.setFont(font_family, font_size)
c.drawString(100, 700, "JOHN DOE")

c.save()
"""

