#!/usr/bin/env python3
"""
Helper script to prepare CSV files for legacy certificate import.

This script helps you format your CSV files correctly for the import command.
"""

import csv
import sys
from pathlib import Path


def prepare_course_csv(input_file, output_file):
    """Prepare course certificates CSV with required columns"""
    print(f"Processing course certificates from: {input_file}")
    
    # Expected columns for course certificates
    required_columns = ['Learner Name', 'Certificate No', 'Course Title']
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=required_columns)
        writer.writeheader()
        
        processed = 0
        for row in reader:
            # Map your columns to the required format
            # Adjust these mappings based on your actual CSV structure
            processed_row = {
                'Learner Name': row.get('Learner Name', '').strip(),
                'Certificate No': row.get('Certificate No', '').strip(),
                'Course Title': row.get('Course Title', '').strip(),
            }
            
            # Skip empty rows
            if not any(processed_row.values()):
                continue
                
            writer.writerow(processed_row)
            processed += 1
    
    print(f"Processed {processed} course certificates")
    print(f"Output saved to: {output_file}")


def prepare_iso_csv(input_file, output_file):
    """Prepare ISO certificates CSV with required columns"""
    print(f"Processing ISO certificates from: {input_file}")
    
    # Expected columns for ISO certificates
    required_columns = [
        'Business', 'Scope', 'Address', 'Certificate No', 
        'IASCB Accreditation No', 'Management system', 'Issue Date', 'Expiry Date'
    ]
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=required_columns)
        writer.writeheader()
        
        processed = 0
        for row in reader:
            # Map your columns to the required format
            # Adjust these mappings based on your actual CSV structure
            processed_row = {
                'Business': row.get('Business', '').strip(),
                'Scope': row.get('Scope', '').strip(),
                'Address': row.get('Address', '').strip(),
                'Certificate No': row.get('Certificate No', '').strip(),
                'IASCB Accreditation No': row.get('IASCB Accreditation No', '').strip(),
                'Management system': row.get('Management system', '').strip(),
                'Issue Date': row.get('Issue Date', '').strip(),
                'Expiry Date': row.get('Expiry Date', '').strip(),
            }
            
            # Skip empty rows
            if not any(processed_row.values()):
                continue
                
            writer.writerow(processed_row)
            processed += 1
    
    print(f"Processed {processed} ISO certificates")
    print(f"Output saved to: {output_file}")


def main():
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python prepare_csv_import.py course <input.csv> <output.csv>")
        print("  python prepare_csv_import.py iso <input.csv> <output.csv>")
        print("\nThis script helps format your CSV files for the import command.")
        print("You may need to adjust the column mappings in the script based on your actual CSV structure.")
        sys.exit(1)
    
    cert_type = sys.argv[1].lower()
    input_file = sys.argv[2]
    output_file = sys.argv[3] if len(sys.argv) > 3 else f"formatted_{input_file}"
    
    if not Path(input_file).exists():
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)
    
    if cert_type == 'course':
        prepare_course_csv(input_file, output_file)
    elif cert_type == 'iso':
        prepare_iso_csv(input_file, output_file)
    else:
        print("Error: Certificate type must be 'course' or 'iso'")
        sys.exit(1)


if __name__ == '__main__':
    main()
