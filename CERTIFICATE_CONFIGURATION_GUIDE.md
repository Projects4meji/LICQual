# ICTQUAL Certificate Configuration Guide

This document explains how to adjust the positioning and styling of elements on your ICTQUAL certificates.

## Overview

The certificate generation system uses two configuration dictionaries:
- `PAGE1_CONFIG`: Controls page 1 (general information)
- `PAGE2_CONFIG`: Controls page 2+ (sections with units)

These are defined at the top of `superadmin/views.py` starting around line 2024.

## Page 1 Configuration (`PAGE1_CONFIG`)

Page 1 displays general qualification information using template `static/images/1.jpg`.

### Configurable Elements

Each element has these properties:
- `x`, `y`: Position in pixels from top-left corner
- `font`: Font file path (e.g., `FONT_CORBEL_REGULAR`, `FONT_RALEWAY`)
- `size`: Font size in pixels
- `color`: RGB tuple, e.g., `(0, 0, 0)` for black
- `align`: Text alignment - `"left"`, `"center"`, or `"right"` (optional)

### Example Configuration

```python
PAGE1_CONFIG = {
    "learner_number": {
        "x": 100,  # 100 pixels from left
        "y": 100,  # 100 pixels from top
        "font": FONT_CORBEL_REGULAR,
        "size": 16,
        "color": (0, 0, 0)  # Black
    },
    "learner_name": {
        "x": 400,
        "y": 300,
        "font": FONT_RALEWAY,
        "size": 48,
        "color": (0, 0, 0),
        "align": "center"  # Centered horizontally
    },
    # ... more elements
}
```

### Page 1 Elements

1. **learner_number** - Displays "Learner Number: {id}" (Corbel font)
2. **certificate_number** - Displays "Certificate Number: {number}" (Corbel font)
3. **qualification_number** - Displays "Qualification Number: {code}" (Corbel font)
4. **this_is_to_certify** - Static text "This is to certify that" (Raleway font)
5. **learner_name** - Learner's full name (Raleway font, large, bold)
6. **has_completed_text** - Static text "has successfully completed the" (Raleway font)
7. **qualification_title** - Qualification title (Raleway font, large, bold)
8. **delivered_by_text** - Static text "This qualification was delivered and assessed by" (Raleway font)
9. **business_name** - Business/centre name (Raleway font, bold)
10. **qr_code** - QR code for verification (has `x`, `y`, and `size` properties)

## Page 2+ Configuration (`PAGE2_CONFIG`)

Page 2 and beyond display sections with units using template `static/images/2.jpg`.

### Configurable Elements

Similar to Page 1, but also includes:
- `unit_table_start_y`: Y position where the unit table begins
- `unit_row_height`: Height of each unit row in pixels

### Example Configuration

```python
PAGE2_CONFIG = {
    "section_title": {
        "x": 400,
        "y": 100,
        "font": FONT_RALEWAY,
        "size": 28,
        "color": (0, 0, 0),
        "align": "center"
    },
    "unit_table_start_y": 220,  # Table starts here
    "unit_row_height": 35,       # Each unit gets 35 pixels
    "unit_ref": {
        "x": 50,  # Column position for unit reference
        "font": FONT_CORBEL_REGULAR,
        "size": 14,
        "color": (0, 0, 0)
    },
    # ... more elements
}
```

### Page 2+ Elements

1. **section_title** - Section heading (e.g., "Year 1: Foundational Knowledge") (Raleway font)
2. **learner_name** - Learner's name (Raleway font)
3. **unit_ref** - Unit reference code (Corbel font)
4. **unit_title** - Unit title text (Corbel font)
5. **remarks** - Remarks/grade (Candara font)
6. **awarded_date** - "Awarded Date: {date}" (Candara font)
7. **duration** - "Duration: TQT/GLH/Credits" (Candara font)
8. **location** - "Location: {centre name}" (Candara font)
9. **qr_code** - QR code for verification

## Font Paths

Fonts are defined at the top of the configuration:

```python
FONT_CORBEL_REGULAR = "static/fonts/Corbel-Regular.ttf"
FONT_CORBEL_BOLD = "static/fonts/Corbel-Bold.ttf"
FONT_RALEWAY = "static/fonts/Raleway-VariableFont.ttf"
FONT_CANDARA_REGULAR = "static/fonts/Candara-Regular.ttf"
FONT_CANDARA_BOLD = "static/fonts/Candara-Bold.ttf"
```

Ensure these font files exist in the specified paths.

## How to Adjust Positioning

1. Open `superadmin/views.py`
2. Find `PAGE1_CONFIG` or `PAGE2_CONFIG` (around line 2024)
3. Modify the `x` and `y` values for the element you want to move:
   - Increase `x` to move right
   - Decrease `x` to move left
   - Increase `y` to move down
   - Decrease `y` to move up
4. Save the file
5. Restart your Django server
6. Test by issuing a new certificate

## Example: Moving Learner Name

To move the learner name on Page 1:

```python
"learner_name": {
    "x": 400,   # Change this to move left/right
    "y": 300,   # Change this to move up/down
    "font": FONT_RALEWAY,
    "size": 48,  # Change this to make text bigger/smaller
    "color": (0, 0, 0),  # Change for different color: (R, G, B)
    "align": "center"
},
```

## Color Format

Colors use RGB tuples where each value is 0-255:
- Black: `(0, 0, 0)`
- White: `(255, 255, 255)`
- Red: `(255, 0, 0)`
- Navy Blue: `(30, 58, 138)`
- etc.

## Tips

- Always work with a backup copy of your configuration
- Test with a single certificate before issuing in bulk
- Use a PDF viewer or image editor to measure pixel positions on your templates
- Remember: (0, 0) is the top-left corner of the image
- For centered text, use `"align": "center"` and set `x` to half the image width

