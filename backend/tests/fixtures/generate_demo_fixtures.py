"""
Generates the 3 synthetic demo policy documents required for Phase 9:
1. Demo Document A: New Exclusion (DRUG-A excluded effective November 1, 2026)
2. Demo Document B: Delayed Exclusion (DRUG-A exclusion delayed to December 1, 2026)
3. Demo Document C: Prior Auth Requirement (PROC-1 requires prior auth from Dec 15, 2026)
"""

import os
from app.intelligence.document_processor import process_uploaded_document
from backend.tests.fixtures.make_pdf import create_simple_pdf

FIXTURES_DIR = os.path.dirname(__file__)

# -----------------------------------------------------------------------------
# Document A: New Exclusion Notice
# -----------------------------------------------------------------------------
DOC_A_LINES = [
    "# DEMO INSURANCE CO. — OFFICIAL POLICY BULLETIN",
    "## Bulletin Ref: 2026-1042-V2 | Date: October 24, 2026",
    "",
    "TO: In-Network Hospital Providers & Claims Administration",
    "FROM: Commercial Formulary Pharmacy & Therapeutics Committee",
    "SUBJECT: Coverage Exclusion for Drug A (DRUG-A)",
    "",
    "POLICY UPDATE NOTICE (SYNTHETIC TEST FIXTURE):",
    "Beginning November 1, 2026, PLAN-GOLD will no longer cover DRUG-A.",
    "This coverage exclusion applies to all outpatient hospital claims with date",
    "of service on or after November 1, 2026.",
    "",
    "AFFECTED BENEFITS:",
    "Insurer: Demo Insurance Co.",
    "Benefit Plan: PLAN-GOLD Commercial Comprehensive",
    "Target Drug: Drug A (HCPCS Code: DRUG-A)",
    "Prior Coverage Status: Covered",
    "New Coverage Status: Excluded / Non-Covered",
    "Effective Date: November 1, 2026",
    "",
    "CLAIMS ADJUDICATION INSTRUCTIONS:",
    "Claims submitted for DRUG-A on or after November 1, 2026 will be rejected",
    "under adjustment reason code CO-96 (Non-covered charge). Hospital claims",
    "officers should review with the ordering physician before submitting.",
    "",
    "Auth: Medical Director Dr. Sarah Jenkins, MD (MD-94021)",
]

# -----------------------------------------------------------------------------
# Document B: Delayed Exclusion Notice
# -----------------------------------------------------------------------------
DOC_B_LINES = [
    "# DEMO INSURANCE CO. — POLICY REVISION & POSTPONEMENT",
    "## Bulletin Ref: 2026-1042-DELAY | Date: October 26, 2026",
    "",
    "TO: Hospital Billing Departments & Clinical Claims Officers",
    "FROM: Office of the Chief Medical Officer",
    "SUBJECT: Temporary Delay of Coverage Exclusion for Drug A",
    "",
    "POLICY REVISION NOTICE (SYNTHETIC TEST FIXTURE):",
    "In response to provider network feedback and transitional care continuity,",
    "the previously announced coverage exclusion for DRUG-A is postponed until December 1, 2026.",
    "",
    "REVISED TERMS:",
    "Insurer: Demo Insurance Co.",
    "Benefit Plan: PLAN-GOLD",
    "Target Drug: Drug A (DRUG-A)",
    "Original Effective Date: November 1, 2026 (Superseded)",
    "New Delayed Effective Date: December 1, 2026",
    "",
    "INTERIM COVERAGE ADJUDICATION:",
    "Claims with service dates between November 1, 2026 and November 30, 2026 will",
    "continue to be covered under existing formulary terms. The non-coverage rule",
    "will take effect strictly on services rendered December 1, 2026 and onward.",
    "",
    "Auth: Pharmacy & Therapeutics Operations (Ref: DELAY-772)",
]

# -----------------------------------------------------------------------------
# Document C: New Prior Authorization Requirement
# -----------------------------------------------------------------------------
DOC_C_LINES = [
    "# DEMO INSURANCE CO. — MEDICAL MANAGEMENT CIRCULAR",
    "## Circular Ref: 2026-202-V2 | Date: October 24, 2026",
    "",
    "TO: Orthopedic Surgery Departments & Hospital Utilization Management",
    "FROM: Utilization Review & Precertification Committee",
    "SUBJECT: Mandatory Prior Authorization for Major Joint Procedures",
    "",
    "CLINICAL POLICY UPDATE (SYNTHETIC TEST FIXTURE):",
    "Prior authorization is mandatory for Major Joint Procedure (PROC-1) effective December 15, 2026.",
    "",
    "CLINICAL MANDATE DETAILS:",
    "Insurer: Demo Insurance Co.",
    "Applicable Plans: PLAN-GOLD",
    "Procedure Code: PROC-1 (Major Joint Procedure)",
    "New Requirement: Pre-service clinical authorization from insurer",
    "Effective Date: December 15, 2026",
    "",
    "REQUIRED DOCUMENTATION:",
    "1. Clinical notes documenting conservative therapy trial.",
    "2. Diagnostic radiology report (X-ray or MRI).",
    "3. Prior authorization confirmation reference code.",
    "",
    "Submissions without an approved authorization reference will be rejected",
    "under code CO-197 (Precertification absent).",
]


def generate_all():
    docs = [
        ("demo_document_A_new_exclusion", DOC_A_LINES),
        ("demo_document_B_delayed_exclusion", DOC_B_LINES),
        ("demo_document_C_prior_auth", DOC_C_LINES),
    ]

    for name, lines in docs:
        pdf_path = os.path.join(FIXTURES_DIR, f"{name}.pdf")
        txt_path = os.path.join(FIXTURES_DIR, f"{name}.txt")

        # Write text fixture
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        # Write PDF fixture
        pdf_bytes = create_simple_pdf(lines)
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        # Verify parsing
        result = process_uploaded_document(pdf_bytes, f"{name}.pdf")
        print(f"Generated {name}.pdf ({len(pdf_bytes)} bytes, {result['page_count']} pages, text length {len(result['raw_text'])})")


if __name__ == "__main__":
    generate_all()
