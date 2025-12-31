#!/usr/bin/env python
"""
Add test units to existing sections to verify database functionality.
Run: python fix_missing_units.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from superadmin.models import Course, QualificationSection, QualificationUnit

def add_test_units():
    """Add test units to existing sections."""
    print("="*70)
    print("Adding Test Units to Existing Sections")
    print("="*70)
    print()
    
    sections = QualificationSection.objects.all()
    
    if not sections.exists():
        print("No sections found. Please create a qualification with sections first.")
        return
    
    for section in sections:
        print(f"Section {section.order}: {section.section_title or '(No title)'}")
        print(f"  Course: {section.course.title}")
        print(f"  Current units: {section.units.count()}")
        
        # Add 3 test units to this section
        if section.units.count() == 0:
            print(f"  Adding 3 test units...")
            
            for i in range(1, 4):
                unit = QualificationUnit.objects.create(
                    section=section,
                    unit_ref=f"{section.course.course_number}-{section.order}-{i}",
                    unit_title=f"Test Unit {i} for Section {section.order}",
                    order=i
                )
                print(f"    Created: {unit.unit_ref} - {unit.unit_title}")
        else:
            print(f"  Section already has units, skipping...")
        
        print()
    
    # Verify
    print("="*70)
    print("Verification:")
    print("="*70)
    
    courses = Course.objects.prefetch_related('sections__units').all()
    for course in courses:
        print(f"\nCourse: {course.title}")
        for section in course.sections.all():
            print(f"  Section {section.order}: {section.units.count()} units")
            for unit in section.units.all():
                print(f"    - {unit.unit_ref}: {unit.unit_title}")

if __name__ == '__main__':
    add_test_units()

