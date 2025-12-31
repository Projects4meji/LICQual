# Certificate Generation Requirements Checklist

This document lists **ALL** information required for successful certificate generation. If any of these fields are missing or empty, certificate generation will fail.

---

## 📋 **1. QUALIFICATION/COURSE INFORMATION** (Required when adding a qualification)

### Basic Course Fields:
- ✅ **Qualification Title** (`course.title`)
  - **Required**: YES
  - **Example**: "LICQual Level 6 Diploma in Agriculture Engineering"
  - **Where to add**: Add Qualification page → Basic Information section

- ✅ **Qualification Number** (`course.course_number`)
  - **Required**: YES
  - **Example**: "AGE0001"
  - **Where to add**: Add Qualification page → Basic Information section

- ⚠️ **Category** (`course.category`)
  - **Required**: NO (optional)
  - **Example**: "Engineering, Health & Safety, Business Management"

- ⚠️ **Duration** (`course.duration`)
  - **Required**: NO (optional)
  - **Example**: "3 Days, 2 Years, 6 Months"

- ⚠️ **Credit Hours** (`course.credit_hours`)
  - **Required**: NO (optional, defaults to 0)
  - **Example**: 1.5, 2.0

---

## 📋 **2. QUALIFICATION SECTIONS** (Required - At least ONE section must exist)

Each qualification **MUST** have at least one section. Sections represent different years/levels of the qualification.

### Section Fields (per section):
- ⚠️ **Section Title** (`section.section_title`)
  - **Required**: NO (optional, will default to "Section 1", "Section 2", etc.)
  - **Example**: "Year 1: Foundational Knowledge"
  - **Where to add**: Add Qualification page → Sections → Section Title field

- ✅ **Credits** (`section.credits`)
  - **Required**: YES (defaults to 120 if not provided)
  - **Type**: Number (integer)
  - **Example**: 120, 60, 30
  - **Where to add**: Add Qualification page → Sections → Credits field

- ✅ **TQT Hours** (`section.tqt_hours`)
  - **Required**: YES (defaults to 1200 if not provided)
  - **Type**: Number (integer)
  - **Example**: 1200, 600, 300
  - **Full Name**: Total Qualification Time (TQT) Hours
  - **Where to add**: Add Qualification page → Sections → TQT Hours field

- ✅ **GLH Hours** (`section.glh_hours`)
  - **Required**: YES (defaults to 600 if not provided)
  - **Type**: Number (integer)
  - **Example**: 600, 300, 150
  - **Full Name**: Guided Learning Hours (GLH) Hours
  - **Where to add**: Add Qualification page → Sections → GLH Hours field

- ✅ **Remarks** (`section.remarks`)
  - **Required**: YES (defaults to "Grade Pass" if not provided)
  - **Type**: Text (string)
  - **Example**: "Grade Pass", "Distinction", "Merit"
  - **Where to add**: Add Qualification page → Sections → Remarks field

---

## 📋 **3. QUALIFICATION UNITS** (Required - At least ONE unit per section)

Each section **MUST** have at least one unit. Units represent individual learning modules within a section.

### Unit Fields (per unit):
- ✅ **Unit Ref** (`unit.unit_ref`)
  - **Required**: YES
  - **Type**: Text (string) - alphanumeric code
  - **Example**: "AGE0001-1", "AGE0001-2", "HS001-1"
  - **Where to add**: Add Qualification page → Sections → Units → Unit Ref field
  - **⚠️ WARNING**: This field cannot be empty or None

- ✅ **Unit Title** (`unit.unit_title`)
  - **Required**: YES
  - **Type**: Text (string) - descriptive title
  - **Example**: "Introduction to Agricultural Engineering", "Advanced Crop Management", "Soil Science Fundamentals"
  - **Where to add**: Add Qualification page → Sections → Units → Unit Title field
  - **⚠️ WARNING**: This field cannot be empty or None

- ✅ **Order** (`unit.order`)
  - **Required**: YES (auto-generated if not provided)
  - **Type**: Number (integer)
  - **Example**: 1, 2, 3
  - **Purpose**: Determines the display order of units within a section

---

## 📋 **4. LEARNER INFORMATION** (Required when registering a learner)

### Learner User Account Fields:
- ✅ **Full Name** (`learner.full_name`)
  - **Required**: YES
  - **Type**: Text (string)
  - **Example**: "John Smith", "Jane Doe"
  - **Where to add**: Register Learners page → Learner Name field
  - **⚠️ WARNING**: If missing, certificate will use email address as fallback

- ✅ **Email** (`learner.email`)
  - **Required**: YES
  - **Type**: Email address
  - **Example**: "john.smith@example.com"
  - **Where to add**: Register Learners page → Learner Email field
  - **Purpose**: Used as fallback if full_name is missing, and for email notifications

---

## 📋 **5. BUSINESS INFORMATION** (Required when creating a business)

### Business Fields:
- ✅ **Business Name** (`business.business_name` OR `business.name`)
  - **Required**: YES (at least one must exist)
  - **Type**: Text (string)
  - **Example**: "ABC Training Ltd", "XYZ Education Services"
  - **Where to add**: Add Business page → Business Name field
  - **⚠️ WARNING**: Certificate will show "Business" as fallback if both are missing

---

## 📋 **6. REGISTRATION INFORMATION** (Auto-generated or optional)

### Registration Fields:
- ✅ **Certificate Number** (`reg.certificate_number`)
  - **Required**: YES (auto-generated when certificate is issued)
  - **Format**: "ICTQ" + 6 digits (e.g., "ICTQ265788")
  - **Auto-generated**: YES (generated automatically when certificate is issued)

- ✅ **Learner Number** (`reg.learner_number`)
  - **Required**: YES (auto-generated when registration is created)
  - **Format**: 6-digit number (e.g., "256001" to "999999")
  - **Auto-generated**: YES (generated automatically when registration is saved)

- ⚠️ **Awarded Date** (`reg.awarded_date`)
  - **Required**: NO (optional)
  - **Type**: Date
  - **Purpose**: Date displayed on certificate as "Awarded Date"
  - **Fallback**: Uses `certificate_issued_at` date if not provided, or current date

- ⚠️ **Certificate Issued At** (`reg.certificate_issued_at`)
  - **Required**: NO (set automatically when certificate is issued)
  - **Type**: DateTime
  - **Purpose**: Tracks when the certificate was actually issued

---

## 🔍 **COMMON ISSUES & SOLUTIONS**

### Issue 1: "Missing required data. Error: expected string or bytes-like object, got 'NoneType'"
**Cause**: One or more required fields are `None` or empty.

**Solution**: Check the following:
1. ✅ Does the course have at least ONE section?
2. ✅ Does each section have at least ONE unit?
3. ✅ Is `unit_ref` filled for ALL units? (Cannot be empty)
4. ✅ Is `unit_title` filled for ALL units? (Cannot be empty)
5. ✅ Does the learner have a `full_name` or `email`?
6. ✅ Does the business have a `business_name` or `name`?
7. ✅ Does the course have a `title` and `course_number`?

### Issue 2: "Course has no sections"
**Cause**: The qualification was created without any sections.

**Solution**: 
- Go to Edit Qualification page
- Add at least ONE section with:
  - Credits (number)
  - TQT Hours (number)
  - GLH Hours (number)
  - Remarks (text)
  - At least ONE unit with Unit Ref and Unit Title

### Issue 3: "Section has no units"
**Cause**: A section exists but has no units added to it.

**Solution**:
- Go to Edit Qualification page
- For each section, add at least ONE unit with:
  - Unit Ref (text, e.g., "AGE0001-1")
  - Unit Title (text, e.g., "Introduction to Agricultural Engineering")

---

## ✅ **PRE-FLIGHT CHECKLIST** (Before Issuing Certificate)

Before clicking "Issue Certificate", verify:

### Qualification Setup:
- [ ] Qualification has a Title
- [ ] Qualification has a Qualification Number
- [ ] Qualification has at least ONE section
- [ ] Each section has:
  - [ ] Credits (number)
  - [ ] TQT Hours (number)
  - [ ] GLH Hours (number)
  - [ ] Remarks (text)
  - [ ] At least ONE unit with:
    - [ ] Unit Ref (text, not empty)
    - [ ] Unit Title (text, not empty)

### Learner Setup:
- [ ] Learner has Full Name OR Email
- [ ] Learner is registered for the course
- [ ] Learner is associated with a business

### Business Setup:
- [ ] Business has Business Name OR Name

---

## 📝 **QUICK REFERENCE**

| Field | Required | Type | Example |
|-------|----------|------|---------|
| **Course Title** | ✅ YES | Text | "LICQual Level 6 Diploma..." |
| **Course Number** | ✅ YES | Text | "AGE0001" |
| **Section Credits** | ✅ YES | Number | 120 |
| **Section TQT Hours** | ✅ YES | Number | 1200 |
| **Section GLH Hours** | ✅ YES | Number | 600 |
| **Section Remarks** | ✅ YES | Text | "Grade Pass" |
| **Unit Ref** | ✅ YES | Text | "AGE0001-1" |
| **Unit Title** | ✅ YES | Text | "Introduction to..." |
| **Learner Full Name** | ✅ YES | Text | "John Smith" |
| **Learner Email** | ✅ YES | Email | "john@example.com" |
| **Business Name** | ✅ YES | Text | "ABC Training Ltd" |

---

## 🎯 **SUMMARY**

**Minimum Requirements for Certificate Generation:**
1. Course with Title and Number
2. At least ONE section with Credits, TQT Hours, GLH Hours, Remarks
3. At least ONE unit per section with Unit Ref and Unit Title
4. Learner with Full Name or Email
5. Business with Business Name or Name

**Most Common Missing Fields:**
- Unit Ref (empty or None)
- Unit Title (empty or None)
- Section has no units
- Course has no sections

---

*Last Updated: Based on certificate generation code in `superadmin/views.py` function `generate_and_attach_certificate()`*

