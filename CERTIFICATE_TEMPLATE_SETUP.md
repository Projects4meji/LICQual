# Certificate Template Setup

## Using PDF Template

The certificate generation now uses `LICQual Diploma -  Template E.pdf` as the template instead of image files.

## Required Library

To convert the PDF template to an image for drawing, you need to install one of these libraries:

### Option 1: PyMuPDF (Recommended - Easiest)

```bash
pip install PyMuPDF
```

**Pros:**
- Easy to install (no external dependencies)
- Fast and reliable
- Good quality output

### Option 2: pdf2image (Alternative)

```bash
pip install pdf2image
```

**Note:** This also requires `poppler` to be installed on your system:
- **Windows**: Download from [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) and add to PATH
- **Linux**: `sudo apt-get install poppler-utils`
- **Mac**: `brew install poppler`

## Installation Steps

1. **Install PyMuPDF (recommended)**:
   ```bash
   pip install PyMuPDF
   ```

2. **Restart your Django server**:
   ```bash
   python manage.py runserver
   ```

3. **Test certificate generation**:
   - Go to superadmin dashboard
   - Issue a certificate to a learner
   - The certificate should now use the PDF template format

## Template File Location

The template PDF should be located at:
```
static/images/LICQual Diploma -  Template E.pdf
```

## How It Works

1. The system loads the PDF template
2. Converts the PDF page to a high-resolution image (using PyMuPDF or pdf2image)
3. Draws learner information, course details, and units on the image
4. Saves the final result as a PDF

## Troubleshooting

### Error: "PyMuPDF (fitz) not installed"

**Solution**: Install PyMuPDF:
```bash
pip install PyMuPDF
```

### Error: "PDF template not found"

**Solution**: Make sure `LICQual Diploma -  Template E.pdf` exists in `static/images/` folder.

### Certificate looks blurry

**Solution**: The `CERTIFICATE_SCALE_FACTOR` in `superadmin/views.py` controls quality. It's currently set to 2.0. You can increase it to 3.0 for even higher quality (but larger file sizes).

---

**Note**: The PDF template will be used for all certificate pages. If your PDF has multiple pages, page 1 will be used for the first certificate page, page 2 for the second, etc.

