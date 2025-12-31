#!/usr/bin/env python
"""
Test script to check if qualification data (sections and units) is being saved correctly.
Run: python test_qualification_data.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from superadmin.models import Course, QualificationSection, QualificationUnit

def test_qualification_data():
    """Test if qualifications have sections and units."""
    print("="*70)
    print("Qualification Data Test")
    print("="*70)
    print()
    
    courses = Course.objects.all()
    
    if not courses.exists():
        print("No qualifications found in the database.")
        print("Please create a qualification first.")
        return
    
    print(f"Found {courses.count()} qualification(s) in the database:")
    print()
    
    for course in courses:
        print(f"Qualification: {course.title} (ID: {course.id})")
        print(f"  Number: {course.course_number}")
        print(f"  Created: {course.created_at}")
        
        # Get sections
        sections = course.sections.all()
        print(f"  Sections: {sections.count()}")
        
        if sections.exists():
            for section in sections:
                print(f"    - Section {section.order}: {section.section_title or '(No title)'}")
                print(f"      Credits: {section.credits}, TQT: {section.tqt_hours}, GLH: {section.glh_hours}")
                
                # Get units
                units = section.units.all()
                print(f"      Units: {units.count()}")
                
                if units.exists():
                    for unit in units:
                        print(f"        {unit.order}. {unit.unit_ref}: {unit.unit_title}")
                else:
                    print(f"        [WARNING] No units found for this section!")
        else:
            print("    [WARNING] No sections found for this qualification!")
        
        print()
    
    # Test prefetch_related
    print("-"*70)
    print("Testing prefetch_related query:")
    print("-"*70)
    
    course_with_prefetch = Course.objects.prefetch_related('sections__units').first()
    if course_with_prefetch:
        print(f"Course: {course_with_prefetch.title}")
        print(f"Sections via prefetch: {course_with_prefetch.sections.all().count()}")
        
        for section in course_with_prefetch.sections.all():
            print(f"  Section {section.order}: {section.units.all().count()} units")
            for unit in section.units.all():
                print(f"    - {unit.unit_ref}: {unit.unit_title}")
    
    print()
    print("="*70)

if __name__ == '__main__':
    test_qualification_data()

