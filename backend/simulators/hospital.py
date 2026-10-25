"""Independent simulated hospital API. All records are synthetic."""

from fastapi import FastAPI
from simulators.common import local_admin

app = FastAPI(title="SIMULATED Hospital API")
app.middleware("http")(local_admin)


INSURERS = [
    ("uhc", "UnitedHealthcare (SIMULATED)", "DEMO-UHC-PPO"),
    ("aetna", "Aetna (SIMULATED)", "DEMO-AETNA-PPO"),
    ("bcbs-anthem-ca", "Anthem Blue Cross California (SIMULATED)", "DEMO-ANTHEM-CA-PPO"),
    ("cms", "Original Medicare (SIMULATED)", "DEMO-MEDICARE"),
]
KNEE = ("procedure", "27447", "CPT", "Total knee arthroplasty", "Orthopedics")

# Claims 11-40 cover a mix of procedures, medicines and outcomes against the simulated rules.
# (item type, code, code system, name, specialty, prior authorization ref, documents, diagnosis)
VARIED = {
    11: (*KNEE, None, [], None),
    12: (*KNEE, None, [], None),
    13: ("procedure", "72148", "CPT", "MRI lumbar spine without contrast", "Radiology", "PA-AET-1013", [], None),
    14: ("procedure", "72148", "CPT", "MRI lumbar spine without contrast", "Radiology", None, [], None),
    15: ("procedure", "97110", "CPT", "Physical therapy, therapeutic exercise", "Physical Therapy", None, ["Physician referral"], None),
    16: ("procedure", "97110", "CPT", "Physical therapy, therapeutic exercise", "Physical Therapy", None, [], None),
    17: ("drug", "J9271", "HCPCS", "Pembrolizumab injection", "Oncology", None, [], None),
    18: ("procedure", "15823", "CPT", "Upper eyelid blepharoplasty", "Ophthalmology", None, [], None),
    19: ("procedure", "99213", "CPT", "Office visit, established patient", "Primary Care", None, [], None),
    20: ("procedure", "45378", "CPT", "Diagnostic colonoscopy", "Gastroenterology", None, [], None),
    21: (*KNEE, None, [], None),
    22: (*KNEE, None, [], None),
    23: ("procedure", "70553", "CPT", "MRI brain with and without contrast", "Neurology", "PA-ANT-1023", [], None),
    24: ("procedure", "70553", "CPT", "MRI brain with and without contrast", "Neurology", None, [], None),
    25: ("procedure", "43644", "CPT", "Laparoscopic gastric bypass", "Bariatric Surgery", None, ["BMI documentation"], None),
    26: ("procedure", "43644", "CPT", "Laparoscopic gastric bypass", "Bariatric Surgery", None, ["BMI documentation", "Nutrition evaluation"], None),
    27: ("procedure", "93306", "CPT", "Echocardiogram, complete", "Cardiology", None, [], None),
    28: ("procedure", "15823", "CPT", "Upper eyelid blepharoplasty", "Ophthalmology", None, [], None),
    29: ("procedure", "99213", "CPT", "Office visit, established patient", "Primary Care", None, [], None),
    30: (*KNEE, None, [], None),
    31: (*KNEE, None, [], None),
    32: (*KNEE, None, [], None),
    33: ("service", "E0601", "HCPCS", "CPAP device", "Sleep Medicine", None, [], None),
    34: ("service", "E0601", "HCPCS", "CPAP device", "Sleep Medicine", None, ["Sleep study report"], None),
    35: ("procedure", "G0105", "HCPCS", "Screening colonoscopy, high risk", "Gastroenterology", None, [], None),
    36: ("drug", "J0897", "HCPCS", "Denosumab injection", "Endocrinology", None, [], None),
    37: ("procedure", "29877", "CPT", "Arthroscopic knee debridement", "Orthopedics", None, [], ("M17.11", "Primary osteoarthritis, right knee")),
    38: ("procedure", "29877", "CPT", "Arthroscopic knee debridement", "Orthopedics", None, [], ("S83.211A", "Bucket-handle tear of medial meniscus, right knee")),
    39: ("procedure", "99213", "CPT", "Office visit, established patient", "Primary Care", None, [], None),
    40: (*KNEE, None, [], None),
}


def item(item_type, code, code_system, name):
    return {"type": item_type, "code": code, "code_system": code_system, "name": name}


def synthetic_claims():
    records = []
    for number in range(1, 41):
        insurer, name, plan = INSURERS[(number - 1) // 10]
        if number <= 10:
            # The UHC knee claims drive the restriction/delay demonstration.
            items = [item(*KNEE[:4])] + ([item("drug", "J1234", "HCPCS", "Synthetic adjunct therapy")] if number == 3 else [])
            specialty, authorization, documents, diagnosis = "Orthopedics", None, [], None
        else:
            item_type, code, code_system, item_name, specialty, authorization, documents, diagnosis = VARIED[number]
            items = [item(item_type, code, code_system, item_name)]
        records.append(
            dict(
                case_id=f"H-{number:03d}",
                insurer_id=insurer,
                insurer_name=name,
                plan_id=plan,
                member_ref=f"SYNTHETIC-MEMBER-{number:03d}",
                jurisdiction="CA",
                policy_environment="demo",
                is_synthetic=True,
                service_date="2026-10-28" if (number - 1) % 10 < 2 else "2026-11-10",
                specialty=specialty,
                items=items,
                diagnoses=[{"code": diagnosis[0], "description": diagnosis[1]}] if diagnosis else [],
                documents=documents,
                prior_approval_ref=authorization,
            )
        )
    return records


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "SIMULATED hospital",
        "synthetic_only": True,
    }


@app.get("/pending-claims")
def pending_claims():
    return {"simulation": True, "claims": synthetic_claims()}
