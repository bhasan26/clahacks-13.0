"""Independent read-only policy API and separate local fixture-publication controls."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from simulators.common import SimulatorState, local_admin

app = FastAPI(title="SIMULATED Insurer Rules API — no insurer affiliation")
app.middleware("http")(local_admin)


def baseline():
    policies = {}
    for insurer, name, plan in [
        ("uhc", "UnitedHealthcare (SIMULATED)", "DEMO-UHC-PPO"),
        ("aetna", "Aetna (SIMULATED)", "DEMO-AETNA-PPO"),
        ("bcbs-anthem-ca", "Anthem California (SIMULATED)", "DEMO-ANTHEM-CA-PPO"),
        ("cms", "Medicare (SIMULATED)", "DEMO-MEDICARE"),
    ]:
        pid = f"DEMO-{insurer.upper()}-KNEE"
        policies[pid] = [
            dict(
                policy_id=pid,
                insurer_id=insurer,
                insurer_name=name,
                plan_ids=[plan],
                jurisdictions=["CA"],
                target_type="procedure",
                target_code="27447",
                code_system="CPT",
                target_name="Total knee arthroplasty",
                proposed_effect="covered",
                effective_from="2026-01-01",
                version=1,
                change_type="new_rule",
                conditions=None,
            )
        ]
    policies["DEMO-UHC-AUTH"] = [
        dict(
            policy_id="DEMO-UHC-AUTH",
            insurer_id="uhc",
            insurer_name="UnitedHealthcare (SIMULATED)",
            plan_ids=["DEMO-UHC-PPO"],
            jurisdictions=["CA"],
            target_type="drug",
            target_code="J1234",
            code_system="HCPCS",
            target_name="Synthetic adjunct therapy",
            proposed_effect="requires_prior_approval",
            effective_from="2026-01-01",
            version=1,
            change_type="new_rule",
            conditions={"requires_prior_approval": True},
        )
    ]
    return {"policies": policies}


state = SimulatorState("insurer_simulator", baseline)


def document(record):
    result = dict(record)
    result["supporting_quote"] = (
        f"SIMULATED policy {record['policy_id']} v{record['version']}: {record['insurer_name']}, plan {record['plan_ids'][0]}, CA, {record['target_type']} {record['target_code']} is {record['proposed_effect']} effective {record['effective_from']}."
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
