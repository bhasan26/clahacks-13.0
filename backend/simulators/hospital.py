"""Independent simulated hospital API. All records are synthetic."""

from fastapi import FastAPI
from simulators.common import local_admin

app = FastAPI(title="SIMULATED Hospital API")
app.middleware("http")(local_admin)


def synthetic_claims():
    records = []
    insurers = [
        ("uhc", "UnitedHealthcare (SIMULATED)", "DEMO-UHC-PPO"),
        ("aetna", "Aetna (SIMULATED)", "DEMO-AETNA-PPO"),
        (
            "bcbs-anthem-ca",
            "Anthem Blue Cross California (SIMULATED)",
            "DEMO-ANTHEM-CA-PPO",
        ),
        ("cms", "Original Medicare (SIMULATED)", "DEMO-MEDICARE"),
    ]
    for number in range(40):
        insurer, name, plan = insurers[number // 10]
        records.append(
            dict(
                case_id=f"H-{number + 1:03d}",
                insurer_id=insurer,
                insurer_name=name,
                plan_id=plan,
                member_ref=f"SYNTHETIC-MEMBER-{number + 1:03d}",
                jurisdiction="CA",
                policy_environment="demo",
                is_synthetic=True,
                service_date="2026-10-28" if number % 10 < 2 else "2026-11-10",
                specialty="Orthopedics",
                items=[
                    {
                        "type": "procedure",
                        "code": "27447",
                        "code_system": "CPT",
                        "name": "Total knee arthroplasty",
                    }
                ]
                + (
                    [
                        {
                            "type": "drug",
                            "code": "J1234",
                            "code_system": "HCPCS",
                            "name": "Synthetic adjunct therapy",
                        }
                    ]
                    if number == 2
                    else []
                ),
                documents=[],
                prior_approval_ref=None,
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
