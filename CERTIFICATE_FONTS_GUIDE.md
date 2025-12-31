# Certificate Fonts Guide

## Fonts Installed

The following fonts have been installed for certificate generation:

### 1. **Corbel** (Microsoft Font)
- **Files**: 
  - `static/fonts/Corbel-Regular.ttf`
  - `static/fonts/Corbel-Bold.ttf`
- **Used For**:
  - Learner Number
  - Certificate Number
  - Qualification Number
  - Unit Reference (e.g., AGE0001-1)
  - Unit Title (e.g., "Introduction to Agricultural Engineering")

### 2. **Raleway** (Google Font)
- **File**: `static/fonts/Raleway-VariableFont.ttf`
- **Used For**:
  - Learner Name (e.g., "MR BABAR ALI KHAN")
  - Qualification Title (e.g., "ICTQual Level 6 Diploma...")
  - "Delivered and assessed by" text
  - Section titles (e.g., "Year 1: Foundational Knowledge")

### 3. **Candara** (Microsoft Font)
- **Files**:
  - `static/fonts/Candara-Regular.ttf`
  - `static/fonts/Candara-Bold.ttf`
- **Used For**:
  - Awarded Date (e.g., "16th October 2025")
  - Duration/Credits (e.g., "120 Credits")
  - Location/Business Name
  - Remarks (e.g., "Grade Pass | TQT 1200 Hours | GLH 600 Hours")

## Font Configuration Module

A font configuration module has been created: `superadmin/certificate_fonts.py`

This module provides:
- Centralized font definitions
- Helper functions to load fonts for PIL/Pillow
- Helper functions to register fonts for ReportLab
- Default font sizes for each certificate element

## Usage in Certificate Generation

### Using with PIL/Pillow (Image-based certificates)

```python
from PIL import Image, ImageDraw
from superadmin.certificate_fonts import load_font_for_pil

# Open certificate template
template = Image.open('static/images/1.png')
draw = ImageDraw.Draw(template)

# Draw learner name (Raleway)
name_font = load_font_for_pil('learner_name', size=48)
draw.text((500, 400), "MR BABAR ALI KHAN", font=name_font, fill='#000000')

# Draw certificate number (Corbel)
cert_font = load_font_for_pil('certificate_number', size=16)
draw.text((100, 100), "ICTQ6530", font=cert_font, fill='#000000')

# Draw qualification title (Raleway)
qual_font = load_font_for_pil('qualification_title', size=32)
draw.text((400, 500), "ICTQual Level 6 Diploma...", font=qual_font, fill='#000000')

# Save
template.save('output.png')
```

### Using with ReportLab (PDF generation)

```python
from reportlab.pdfgen import canvas
from superadmin.certificate_fonts import load_font_for_reportlab

c = canvas.Canvas("certificate.pdf")

# Learner name (Raleway)
font_family, font_size = load_font_for_reportlab('learner_name')
c.setFont(font_family, 48)
c.drawString(100, 700, "MR BABAR ALI KHAN")

# Certificate number (Corbel)
font_family, font_size = load_font_for_reportlab('certificate_number')
c.setFont(font_family, 16)
c.drawString(100, 650, "ICTQ6530")

c.save()
```

## Font Mapping for Certificate Elements

### Page 1 (Main Certificate - 1.png)

| Element | Font | Font Key | Default Size |
|---------|------|----------|--------------|
| Learner Number | Corbel | `learner_number` | 16pt |
| Certificate Number | Corbel | `certificate_number` | 16pt |
| Qualification Number | Corbel | `qualification_number` | 16pt |
| Learner Name | Raleway | `learner_name` | 48pt |
| Qualification Title | Raleway | `qualification_title` | 32pt |
| "Delivered and assessed by" | Raleway | `delivered_by` | 18pt |
| Business Name | Raleway | `location` | 18pt |

### Page 2+ (Units Pages - 2.png)

| Element | Font | Font Key | Default Size |
|---------|------|----------|--------------|
| Section Title | Raleway | `section_title` | 24pt |
| Learner Name | Raleway | `learner_name` | 24pt |
| Unit Reference | Corbel | `unit_ref` | 14pt |
| Unit Title | Corbel | `unit_title` | 14pt |
| Remarks | Candara | `remarks` | 12pt |
| Awarded Date | Candara | `awarded_date` | 14pt |
| Credits/Duration | Candara | `duration` | 14pt |
| Location/Business | Candara | `location` | 14pt |

## Next Steps: Update Certificate Generation

You need to update the certificate generation code in `superadmin/views.py` to use these fonts.

### Key Functions to Update:

1. **`issue_certificate` function** - Generates certificates when issuing
2. **`download_certificate` function** - Re-generates certificates for download
3. Any PIL/Pillow image drawing code
4. Any ReportLab PDF generation code

### Example Update Pattern:

**Before:**
```python
from PIL import ImageFont

font = ImageFont.truetype("arial.ttf", 32)
draw.text((x, y), text, font=font, fill='#000000')
```

**After:**
```python
from superadmin.certificate_fonts import load_font_for_pil

font = load_font_for_pil('learner_name')  # Uses configured font and size
draw.text((x, y), text, font=font, fill='#000000')
```

## Testing Fonts

To verify fonts are working correctly, you can run:

```python
from superadmin.certificate_fonts import get_font_config, get_font_path

# Check all fonts are accessible
for font_key in ['learner_number', 'certificate_number', 'learner_name', 
                  'qualification_title', 'unit_ref', 'awarded_date']:
    try:
        path = get_font_path(font_key)
        print(f"✓ {font_key}: {path}")
    except Exception as e:
        print(f"✗ {font_key}: {e}")
```

## Font Licensing

- **Corbel & Candara**: Microsoft fonts included with Windows. Usage rights are governed by Windows license.
- **Raleway**: Open source font (OFL license) from Google Fonts. Free for commercial use.

## Troubleshooting

### Font Not Found Error

If you get a "Font file not found" error:

1. Check fonts are in `static/fonts/` directory
2. Verify file names match:
   - `Corbel-Regular.ttf`
   - `Raleway-VariableFont.ttf`
   - `Candara-Regular.ttf`

### Re-copying Windows Fonts

If fonts need to be re-copied from Windows:

```powershell
Copy-Item "C:\Windows\Fonts\corbel.ttf" "static/fonts/Corbel-Regular.ttf"
Copy-Item "C:\Windows\Fonts\corbelb.ttf" "static/fonts/Corbel-Bold.ttf"
Copy-Item "C:\Windows\Fonts\Candara.ttf" "static/fonts/Candara-Regular.ttf"
Copy-Item "C:\Windows\Fonts\Candarab.ttf" "static/fonts/Candara-Bold.ttf"
```

---

**Last Updated**: October 26, 2025

