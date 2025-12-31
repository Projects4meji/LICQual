# Qualification System Guide

## Overview
The system now supports multi-page certificates with structured qualifications containing sections (Years/Levels) and units.

## Database Structure

### Models Created
1. **Course** (existing) - Main qualification info
   - Title
   - Qualification Number  
   - Description
   
2. **QualificationSection** (new) - Represents Year 1, Year 2, etc.
   - Section Title (e.g., "Year 1: Foundational Knowledge")
   - Order (1, 2, 3...)
   - Credits (e.g., 120)
   - TQT Hours (Total Qualification Time)
   - GLH Hours (Guided Learning Hours)
   - Remarks (e.g., "Grade Pass")

3. **QualificationUnit** (new) - Individual units within each section
   - Unit Reference (e.g., "AGE0001-1")
   - Unit Title (e.g., "Introduction to Agricultural Engineering")
   - Order

## Certificate Templates

**Location**: 
- Page 1 template: `static/images/1.png`
- Page 2 template: `static/images/2.png`

These templates are used for ALL qualifications (no need to upload per qualification).

## Certificate Pages Structure

### Page 1 (1.jpg) - Main Certificate
**Dynamic Data**:
- Learner Number
- Certificate Number  
- Qualification Number
- Learner Name
- Qualification Title (full title from Course)
- Business Name (who delivered/assessed)
- QR Code

### Page 2+ (2.jpg) - Unit Details
Each section creates a separate page with:
**Dynamic Data**:
- Section Title (optional heading, e.g., "Year 1: Foundational Knowledge")
- Learner Name
- Unit Reference and Title pairs (multiple rows)
- Remarks (e.g., "Grade Pass | TQT 1200 Hours | GLH 600 Hours")
- Awarded Date
- Credits (e.g., "120 Credits")
- Business Name
- QR Code (same as page 1)

## Adding a Qualification

1. Go to **Superadmin Dashboard** → **Add Qualification**

2. **Fill Basic Information**:
   - Qualification Title
   - Qualification Number
   - Description (optional)

3. **Add Sections** (Click "+ Add Section"):
   - Enter section title (optional, e.g., "Year 1: Foundational Knowledge")
   - Set Credits, TQT Hours, GLH Hours
   - Enter Remarks

4. **Add Units** to each section (Click "+ Add Unit"):
   - Enter Unit Reference (e.g., "AGE0001-1")
   - Enter Unit Title
   - Set display order

5. **Save Qualification**

## Editing a Qualification

1. Go to **Course List** → Click **Edit** on qualification
2. Modify basic info, sections, or units
3. Add new sections/units as needed
4. Remove sections/units (will be deleted from database)
5. Save changes

## Admin Interface

Access Django Admin to manage qualifications with inline editing:
- Navigate to: `/admin/`
- **Courses**: View all qualifications
  - Inline sections management
- **Qualification Sections**: Manage sections separately
  - Inline units management
- **Qualification Units**: Manage individual units

## Next Steps (Certificate Generation)

### TODO: Update Certificate Generation Logic

The certificate generation code needs to be updated to:

1. **Generate Page 1** using `static/images/1.png`:
   - Overlay learner number, cert number, qual number
   - Overlay learner name (formatted with title: MR/MS)
   - Overlay qualification title
   - Overlay business name
   - Generate and overlay QR code

2. **Generate Page 2+** for each section using `static/images/2.png`:
   - Overlay section title (if provided)
   - Overlay learner name
   - Loop through section.units and overlay:
     - Unit reference (left column)
     - Unit title (right column)
   - Overlay remarks with TQT, GLH
   - Overlay awarded date
   - Overlay credits
   - Overlay business name
   - Overlay same QR code as page 1

3. **Combine all pages** into a single PDF

### File Locations to Update:
- Certificate generation view: `superadmin/views.py` (issue_certificate, download_certificate functions)
- Look for references to `course.certificate_template` - replace with `static/images/1.png` and `static/images/2.png`

## Example Qualification

**Title**: ICTQual Level 6 Diploma in Agriculture Engineering
**Number**: AGE0001
**Sections**: 3 (Year 1, Year 2, Year 3)
**Total Units**: 36 (12 per year)

This would generate 4 certificate pages:
- 1 × Page 1 (main certificate)
- 3 × Page 2 (one for each year/section)

## Database Migration

Migration file created: `superadmin/migrations/0037_qualificationsection_qualificationunit.py`

Status: ✅ Applied successfully

## Testing

To test the system:
1. Create a sample qualification with 1-2 sections
2. Add 3-5 units per section
3. Verify data appears correctly in admin
4. Test editing and deleting sections/units
5. Once certificate generation is updated, test PDF output

---

**Last Updated**: October 26, 2025

