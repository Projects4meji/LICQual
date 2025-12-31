#!/usr/bin/env python
"""
Renumber all qualification sections to be sequential (1, 2, 3, ...).
Run: python renumber_sections.py
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()

from superadmin.models import Course

def renumber_all_sections():
    """Renumber all sections for all qualifications."""
    print("="*70)
    print("Renumbering Qualification Sections")
    print("="*70)
    print()
    
    courses = Course.objects.all()
    
    if not courses.exists():
        print("No qualifications found in the database.")
        return
    
    for course in courses:
        print(f"Qualification: {course.title}")
        print(f"  Number: {course.course_number}")
        
        sections = course.sections.all().order_by('order')
        print(f"  Sections: {sections.count()}")
        
        if sections.exists():
            renumbered = False
            for index, section in enumerate(sections, start=1):
                old_order = section.order
                if section.order != index:
                    section.order = index
                    section.save(update_fields=['order'])
                    print(f"    Section {old_order} -> Section {index}: {section.section_title or '(No title)'}")
                    renumbered = True
                else:
                    print(f"    Section {index}: {section.section_title or '(No title)'} (no change)")
            
            if not renumbered:
                print(f"    All sections already numbered correctly!")
        else:
            print("    No sections to renumber.")
        
        print()
    
    print("="*70)
    print("Renumbering complete!")
    print("="*70)

if __name__ == '__main__':
    renumber_all_sections()

