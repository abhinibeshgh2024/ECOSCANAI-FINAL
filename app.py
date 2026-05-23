import os
import json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Eco-Scan AI Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "db.json"
MASTER_FILE = "master_data.json"

def load_json(filepath, default_structure):
    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            json.dump(default_structure, f, indent=4)
        return default_structure
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            if "items" not in data and filepath == MASTER_FILE:
                return default_structure
            return data
    except Exception:
        return default_structure

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)

load_json(DB_FILE, {})
load_json(MASTER_FILE, {"items": {"canteen": [], "nescafe": []}})

class MasterItemModel(BaseModel):
    source: str
    name: str
    carbon: float
    price: Optional[float] = 0.0
    efficiency: Optional[int] = 100
    swap: Optional[str] = ""
    impact: Optional[str] = ""

class PolicyPayload(BaseModel):
    scenario: str
    stats: str

@app.get("/api/master")
def get_master_schema():
    return load_json(MASTER_FILE, {"items": {"canteen": [], "nescafe": []}})

@app.get("/api/db")
def get_current_dashboard_state():
    return load_json(DB_FILE, {})

@app.post("/api/add-master")
def extend_master_database(item: MasterItemModel):
    store = load_json(MASTER_FILE, {"items": {"canteen": [], "nescafe": []}})
    if "items" not in store:
        store = {"items": {"canteen": [], "nescafe": []}}
        
    store["items"][item.source] = [
        existing for existing in store["items"][item.source]
        if existing.get("name", "").lower() != item.name.lower()
    ]
    
    store["items"][item.source].append(item.dict())
    save_json(MASTER_FILE, store)
    return {"status": "success", "message": f"Successfully injected {item.name}."}

@app.post("/api/analyze")
async def analyze_and_log_transaction(
    date: str = Form(...),
    source: str = Form(...),
    name: Optional[str] = Form(""),
    qty: Optional[int] = Form(1),
    file: Optional[UploadFile] = File(None)
):
    db = load_json(DB_FILE, {})
    master = load_json(MASTER_FILE, {"items": {"canteen": [], "nescafe": []}})
    
    if date not in db:
        db[date] = {"canteen": [], "nescafe": []}

    target_name = name.strip() if name else ""
    carbon_weight = 0.45 

    # Dynamic OCR parser mocking
    if file:
        if source == "canteen":
            target_name = "OCR Veg Thali Scanned"
            carbon_weight = 1.20
        else:
            target_name = "OCR Nescafe Cappuccino"
            carbon_weight = 0.75
    elif not target_name:
        target_name = "Generic Unnamed Item"

    source_items = master.get("items", {}).get(source, [])
    match = next((item for item in source_items if item.get("name", "").lower() == target_name.lower()), None)

    # CRITICAL EDIT: If the scanned/typed item isn't in master_data.json, auto-save it!
    if not match:
        new_master_item = {
            "source": source,
            "name": target_name,
            "carbon": carbon_weight,
            "price": 0.0,
            "efficiency": 100,
            "swap": "Plant-Based Alternative" if source == "canteen" else "Oat Milk Substitution",
            "impact": "Auto-generated baseline from diagnostic receipt scan profiles."
        }
        if source not in master["items"]:
            master["items"][source] = []
        master["items"][source].append(new_master_item)
        save_json(MASTER_FILE, master)
        print(f"--> Auto-Registered unknown item into Master: {target_name}")

    else:
        carbon_weight = match["carbon"]

    calculated_carbon = carbon_weight * float(qty)

    log_entry = {
        "name": target_name,
        "source": source,
        "carbon": calculated_carbon,
        "qty": qty,
        "energy_kwh": calculated_carbon * 2.5,
        "bulb_hours": int(calculated_carbon * 12),
        "time": datetime.now().strftime("%H:%M")
    }

    db[date][source].append(log_entry)
    save_json(DB_FILE, db)
    return {"status": "success", "logged": log_entry}

@app.post("/api/simulate")
def run_predictive_policy_engine(payload: PolicyPayload):
    simulated_impact_ratio = "45%"
    if "oat" in payload.scenario.lower() or "plant" in payload.scenario.lower():
        simulated_impact_ratio = "65%"

    prediction_response = (
        f"Based on current operational parameters tracking an index of {payload.stats} kg CO2e, "
        f"implementing the proposed strategy ('{payload.scenario}') would lead to an estimated reduction "
        f"of {simulated_impact_ratio} across point-source logistics."
    )
    return {"prediction": prediction_response}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
    
