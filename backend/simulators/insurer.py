"""Independent read-only policy API and separate local fixture-publication controls."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from simulators.common import SimulatorState, local_admin

app = FastAPI(title="SIMULATED Insurer Rules API — no insurer affiliation")
app.middleware("http")(local_admin)


PLANS = {
    "uhc": ("UnitedHealthcare (SIMULATED)", "DEMO-UHC-PPO"),
    "aetna": ("Aetna (SIMULATED)", "DEMO-AETNA-PPO"),
    "bcbs-anthem-ca": ("Anthem California (SIMULATED)", "DEMO-ANTHEM-CA-PPO"),
    "cms": ("Medicare (SIMULATED)", "DEMO-MEDICARE"),
}

# Fictional rules using real billing-code formats. They are not any insurer's actual policy.
# (policy_id, insurer, item type, code, code system, name, effect, conditions)
VARIED_RULES = [
    ("DEMO-AETNA-MRI-LSPINE", "aetna", "procedure", "72148", "CPT", "MRI lumbar spine without contrast",
     "requires_prior_approval", {"requires_prior_approval": True}),
    ("DEMO-AETNA-PT", "aetna", "procedure", "97110", "CPT", "Physical therapy, therapeutic exercise",
     "requires_documents", {"required_documents": ["Physician referral"]}),
    ("DEMO-AETNA-PEMBROLIZUMAB", "aetna", "drug", "J9271", "HCPCS", "Pembrolizumab injection",
     "requires_prior_approval", {"requires_prior_approval": True}),
    ("DEMO-AETNA-BLEPHAROPLASTY", "aetna", "procedure", "15823", "CPT", "Upper eyelid blepharoplasty",
     "excluded", None),
    ("DEMO-AETNA-COLONOSCOPY", "aetna", "procedure", "45378", "CPT", "Diagnostic colonoscopy",
     "covered", None),
    ("DEMO-ANTHEM-MRI-BRAIN", "bcbs-anthem-ca", "procedure", "70553", "CPT", "MRI brain with and without contrast",
     "requires_prior_approval", {"requires_prior_approval": True}),
    ("DEMO-ANTHEM-BARIATRIC", "bcbs-anthem-ca", "procedure", "43644", "CPT", "Laparoscopic gastric bypass",
     "requires_documents", {"required_documents": ["BMI documentation", "Nutrition evaluation"]}),
    ("DEMO-ANTHEM-ECHO", "bcbs-anthem-ca", "procedure", "93306", "CPT", "Echocardiogram, complete",
     "covered", None),
    ("DEMO-ANTHEM-BLEPHAROPLASTY", "bcbs-anthem-ca", "procedure", "15823", "CPT", "Upper eyelid blepharoplasty",
     "excluded", None),
    ("DEMO-CMS-CPAP", "cms", "service", "E0601", "HCPCS", "CPAP device",
     "requires_documents", {"required_documents": ["Sleep study report"]}),
    ("DEMO-CMS-SCREENING-COLONOSCOPY", "cms", "procedure", "G0105", "HCPCS", "Screening colonoscopy, high risk",
     "covered", None),
    ("DEMO-CMS-DENOSUMAB", "cms", "drug", "J0897", "HCPCS", "Denosumab injection",
     "covered", None),
    ("DEMO-CMS-KNEE-DEBRIDEMENT", "cms", "procedure", "29877", "CPT", "Arthroscopic knee debridement",
     "excluded", {"applies_to_diagnosis_prefixes": ["M17"]}),
]


def rule(policy_id, insurer, target_type, code, code_system, name, effect, conditions):
    insurer_name, plan = PLANS[insurer]
    return dict(
        policy_id=policy_id,
        insurer_id=insurer,
        insurer_name=insurer_name,
        plan_ids=[plan],
        jurisdictions=["CA"],
        target_type=target_type,
        target_code=code,
        code_system=code_system,
        target_name=name,
        proposed_effect=effect,
        effective_from="2026-01-01",
        version=1,
        change_type="new_rule",
        conditions=conditions,
    )


def baseline():
    policies = {}
    for insurer in PLANS:
        pid = f"DEMO-{insurer.upper()}-KNEE"
        policies[pid] = [
            rule(pid, insurer, "procedure", "27447", "CPT", "Total knee arthroplasty", "covered", None)
        ]
    policies["DEMO-UHC-AUTH"] = [
        rule("DEMO-UHC-AUTH", "uhc", "drug", "J1234", "HCPCS", "Synthetic adjunct therapy",
             "requires_prior_approval", {"requires_prior_approval": True})
    ]
    for row in VARIED_RULES:
        policies[row[0]] = [rule(*row)]
    return {"policies": policies}


state = SimulatorState("insurer_simulator", baseline)


def document(record):
    result = dict(record)
    conditions = record.get("conditions") or {}
    extra = ""
    if conditions.get("required_documents"):
        extra += f" Required documents: {', '.join(conditions['required_documents'])}."
    if conditions.get("applies_to_diagnosis_prefixes"):
        extra += f" Applies to diagnoses {', '.join(conditions['applies_to_diagnosis_prefixes'])}."
    result["supporting_quote"] = (
        f"SIMULATED policy {record['policy_id']} v{record['version']}: {record['insurer_name']}, plan {record['plan_ids'][0]}, CA, {record['target_type']} {record['target_code']} is {record['proposed_effect']} effective {record['effective_from']}.{extra}"
    )
    result["policy_title"] = f"SIMULATED {record['target_name']} policy"
    result["policy_reference"] = record["policy_id"]
    return result


@app.get("/health")
def health():
    return {"status": "healthy", "service": "SIMULATED insurer", "synthetic_only": True}


@app.get("/policies")
def policies():
    return {
        "simulation": True,
        "policies": [
            dict(document(versions[-1]), document_path=f"/policies/{pid}")
            for pid, versions in state.read()["policies"].items()
        ],
    }


@app.get("/policies/{policy_id}")
def policy(policy_id: str):
    versions = state.read()["policies"].get(policy_id)
    if not versions:
        raise HTTPException(404, "Synthetic policy not found.")
    return {
        "simulation": True,
        "rules": [document(versions[-1])],
        "history": [document(r) for r in versions],
    }


class Publication(BaseModel):
    scenario: str


@app.post("/admin/publish")
def publish(payload: Publication):
    if payload.scenario not in {"restriction", "delay"}:
        raise HTTPException(422, "Choose restriction or delay.")
    data = state.read()
    versions = data["policies"]["DEMO-UHC-KNEE"]
    desired = 2 if payload.scenario == "restriction" else 3
    if versions[-1]["version"] >= desired:
        return {
            "simulation": True,
            "changed": False,
            "version": versions[-1]["version"],
        }
    if desired == 3 and versions[-1]["version"] != 2:
        raise HTTPException(409, "Publish the restriction before the delay.")
    record = {
        **versions[-1],
        "version": desired,
        "proposed_effect": "excluded",
        "effective_from": "2026-11-01" if desired == 2 else "2026-12-01",
        "change_type": "modification" if desired == 2 else "delayed",
    }
    versions.append(record)
    state.write(data)
    return {"simulation": True, "changed": True, "version": desired}


@app.post("/admin/reset")
def reset():
    state.write(baseline())
    return {"simulation": True, "reset": True}
