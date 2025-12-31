#!/usr/bin/env python
"""
Test script to verify all certificate fonts are properly installed and accessible.
Run: python test_fonts.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from pathlib import Path
from superadmin.certificate_fonts import (
    CERTIFICATE_FONTS, 
    get_font_path, 
    get_font_config,
    FONTS_DIR
)

def test_fonts():
    """Test all certificate fonts are accessible."""
    print("="*60)
    print("Certificate Fonts Installation Test")
    print("="*60)
    print()
    
    # Check fonts directory
    print(f"Fonts Directory: {FONTS_DIR}")
    print(f"Exists: {FONTS_DIR.exists()}")
    print()
    
    # List all font files
    print("Available Font Files:")
    print("-" * 60)
    if FONTS_DIR.exists():
        for font_file in sorted(FONTS_DIR.glob("*.ttf")):
            size_kb = font_file.stat().st_size / 1024
            print(f"  [OK] {font_file.name} ({size_kb:.1f} KB)")
    print()
    
    # Test each configured font
    print("Certificate Font Configuration:")
    print("-" * 60)
    
    all_ok = True
    font_groups = {
        "Page 1 - Numbers": ['learner_number', 'certificate_number', 'qualification_number'],
        "Page 1 - Text": ['learner_name', 'qualification_title', 'delivered_by'],
        "Page 2 - Headers": ['section_title'],
        "Page 2 - Units": ['unit_ref', 'unit_title'],
        "Page 2 - Metadata": ['awarded_date', 'duration', 'location', 'remarks'],
    }
    
    for group_name, font_keys in font_groups.items():
        print(f"\n{group_name}:")
        for font_key in font_keys:
            try:
                config = get_font_config(font_key)
                path = Path(config['path'])
                
                if path.exists():
                    status = "[OK]"
                    size_kb = path.stat().st_size / 1024
                    size_info = f"({size_kb:.1f} KB)"
                else:
                    status = "[FAIL]"
                    size_info = "(FILE NOT FOUND)"
                    all_ok = False
                
                print(f"  {status} {font_key:20s} -> {config['family']:15s} "
                      f"{config['size']:3d}pt  {path.name} {size_info}")
                
            except Exception as e:
                print(f"  [FAIL] {font_key:20s} -> ERROR: {e}")
                all_ok = False
    
    print()
    print("="*60)
    
    # Try loading fonts with PIL
    print("\nTesting Font Loading (PIL/Pillow):")
    print("-" * 60)
    try:
        from PIL import ImageFont
        from superadmin.certificate_fonts import load_font_for_pil
        
        test_fonts_sample = ['learner_name', 'certificate_number', 'awarded_date']
        for font_key in test_fonts_sample:
            try:
                font = load_font_for_pil(font_key)
                print(f"  [OK] {font_key:20s} -> Loaded successfully")
            except Exception as e:
                print(f"  [FAIL] {font_key:20s} -> {e}")
                all_ok = False
                
    except ImportError:
        print("  [SKIP] Pillow not installed - skipping PIL tests")
        print("  Install with: pip install Pillow")
    
    # Try registering fonts with ReportLab
    print("\nTesting Font Registration (ReportLab):")
    print("-" * 60)
    try:
        from reportlab.pdfbase import pdfmetrics
        from superadmin.certificate_fonts import load_font_for_reportlab
        
        test_fonts_sample = ['learner_name', 'certificate_number', 'awarded_date']
        for font_key in test_fonts_sample:
            try:
                family, size = load_font_for_reportlab(font_key)
                print(f"  [OK] {font_key:20s} -> Registered as '{family}'")
            except Exception as e:
                print(f"  [FAIL] {font_key:20s} -> {e}")
                all_ok = False
                
    except ImportError:
        print("  [SKIP] ReportLab not installed - skipping ReportLab tests")
        print("  Install with: pip install reportlab")
    
    print()
    print("="*60)
    
    if all_ok:
        print("[SUCCESS] All fonts installed and accessible!")
        print("[SUCCESS] Certificate generation is ready to use the configured fonts.")
        return 0
    else:
        print("[ERROR] Some fonts are missing or inaccessible.")
        print("\nTo fix missing fonts:")
        print("  1. Ensure fonts are in: static/fonts/")
        print("  2. For Windows fonts (Corbel, Candara), copy from C:\\Windows\\Fonts\\")
        print("  3. Run: Copy-Item C:\\Windows\\Fonts\\corbel.ttf static/fonts/Corbel-Regular.ttf")
        return 1

if __name__ == '__main__':
    sys.exit(test_fonts())

