"""
Script to convert PDF to PNG image for certificate template.
Requires: pip install pdf2image pillow

Usage: python convert_pdf_to_image.py "LICQual Diploma - Template E.pdf"
"""

import sys
from pdf2image import convert_from_path
from PIL import Image

def convert_pdf_to_png(pdf_path, output_path=None, dpi=300):
    """
    Convert PDF to PNG image.
    
    Args:
        pdf_path: Path to the PDF file
        output_path: Output PNG path (optional, defaults to same name as PDF)
        dpi: Resolution in DPI (default 300 for high quality)
    """
    try:
        # Convert PDF to images (returns list of images, one per page)
        print(f"Converting {pdf_path} to PNG at {dpi} DPI...")
        images = convert_from_path(pdf_path, dpi=dpi)
        
        if not images:
            print("Error: No pages found in PDF")
            return False
        
        # Use first page (assuming single page certificate)
        image = images[0]
        
        # Convert to RGBA (supports transparency)
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        # Generate output filename if not provided
        if not output_path:
            output_path = pdf_path.replace('.pdf', '.png')
        
        # Save as PNG
        image.save(output_path, 'PNG', quality=100)
        print(f"✓ Successfully converted to: {output_path}")
        print(f"  Image size: {image.size[0]}x{image.size[1]} pixels")
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure you have pdf2image installed:")
        print("  pip install pdf2image")
        print("\nOn Windows, you may also need poppler:")
        print("  Download from: https://github.com/oschwartz10612/poppler-windows/releases/")
        print("  Extract and add to PATH")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python convert_pdf_to_image.py <pdf_file> [output.png]")
        print("\nExample:")
        print("  python convert_pdf_to_image.py \"LICQual Diploma - Template E.pdf\"")
        sys.exit(1)
    
    pdf_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    convert_pdf_to_png(pdf_file, output_file)

