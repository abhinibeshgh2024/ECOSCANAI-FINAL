import json
import os
import uuid
import re
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from google import genai
from google.genai import types

app = FastAPI()

# Enable CORS for testing stability
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# --- Configuration ---
MASTER_JSON = "master_data.json"
LOG_PATH = "eco_logs.json"

API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyBaQSEC_FhOyAfj8LhdH9iOyjpFpqfctjA")
client = genai.Client(api_key=API_KEY)
MODEL_NAME = 'gemini-2.5-flash'

class SimRequest(BaseModel):
    scenario: str
    stats: str

# --- Serverless-Safe Database Helpers ---
def get_safe_path(path):
    if os.environ.get("VERCEL") or os.environ.get("NOW_REGION"):
        return os.path.join("/tmp", path)
    return path

def load_db(path):
    safe_path = get_safe_path(path)
    if not os.path.exists(safe_path):
        if "master" in path: 
            return {"items": {"canteen": [], "nescafe": []}}
        return {}
    with open(safe_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if "master" in path and "items" not in data:
                return {"items": {"canteen": [], "nescafe": []}}
            return data
        except json.JSONDecodeError:
            return {"items": {"canteen": [], "nescafe": []}} if "master" in path else {}

def save_db(path, data):
    safe_path = get_safe_path(path)
    with open(safe_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def calculate_metrics(item, qty=1.0):
    try:
        q = float(qty)
    except (ValueError, TypeError):
        q = 1.0
        
    eff = float(item.get('efficiency', 80)) / 100.0
    carbon_val = float(item.get('carbon', 0)) * q
    price_val = float(item.get('price', 0)) * q
    energy_kwh = (carbon_val * 1.2) / eff if carbon_val > 0 else 0
    
    return {
        "id": str(uuid.uuid4())[:8],
        "name": item['name'],
        "carbon": round(carbon_val, 2),
        "price": round(price_val, 2),
        "energy_kwh": round(energy_kwh, 2),
        "bulb_hours": round(energy_kwh * 85, 1),
        "swap": item.get('swap', 'Swap info pending'),
        "impact": item.get('impact', 'Impact data pending')
    }

# --- Serve UI Frontend at Base URL ---
@app.get("/", response_class=FileResponse)
async def serve_frontend():
    return FileResponse("index.html")

# --- API Endpoints ---
@app.get("/api/master")
async def get_master():
    return load_db(MASTER_JSON)

@app.get("/api/db")
async def fetch_db():
    return load_db(LOG_PATH)

@app.post("/api/analyze")
async def analyze(
    date: str = Form(...),
    source: str = Form(...),
    name: str = Form(None),
    qty: str = Form("1"),
    file: UploadFile = File(None)
):
    master = load_db(MASTER_JSON)
    if 'items' not in master:
        master = {"items": {"canteen": [], "nescafe": []}}
    if source not in master['items']:
        master['items'][source] = []
        
    source_items = master['items'].get(source, [])
    results = []
    db_needs_update = False

    try:
        if file:
            img_bytes = await file.read()
            prompt = "Extract food items from receipt. Return ONLY a JSON list: [{'name': 'item', 'qty': 1}]. If multiple items, list them all."
            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt, image_part]
            )          
            
            match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if match:
                found_items = json.loads(match.group(0))
                for f in found_items:
                    s_name = f['name'].strip()
                    m = next((x for x in source_items if s_name.lower() in x['name'].lower()), None)
        
                    if not m:
                        new_entry = {
                            "name": s_name,
                            "carbon": 0.15,  # Baseline allocation for auto-detected assets
                            "price": 0.0,
                            "efficiency": 80,
                            "swap": "Pending manual update",
                            "impact": "New item detected via OCR"
                        }
                        master['items'][source].append(new_entry)
                        m = new_entry
                        db_needs_update = True                  
                    
                    results.append(calculate_metrics(m, f.get('qty', 1)))
        else:
            m = next((x for x in source_items if x['name'].lower() == name.lower()), None)
            if m:
                results.append(calculate_metrics(m, qty))
            else:
                # Fallback item if manually typed but not yet in database
                fallback_entry = {
                    "name": name,
                    "carbon": 0.2,
                    "price": 0.0,
                    "efficiency": 80,
                    "swap": "Pending manual update",
                    "impact": "Manually logged item"
                }
                master['items'][source].append(fallback_entry)
                db_needs_update = True
                results.append(calculate_metrics(fallback_entry, qty))

        if db_needs_update:
            save_db(MASTER_JSON, master)

        if results:
            logs = load_db(LOG_PATH)
            if date not in logs:
                logs[date] = {"canteen": [], "nescafe": []}
            if source not in logs[date]:
                logs[date][source] = []
            
            for r in results:
                r.update({"source": source, "time": datetime.now().strftime("%H:%M")})
                logs[date][source].append(r)
                
            save_db(LOG_PATH, logs)
            return {"status": "success", "data": results, "new_items_added": db_needs_update}

        return {"status": "error", "message": "No valid items identified."}

    except Exception as e:
        return {"status": "error", "message": f"Server Error: {str(e)}"}

@app.post("/api/simulate")
async def simulate(req: SimRequest):
    try:
        prompt = (
            f"Current Data: {req.stats}. Scenario: {req.scenario}. "
            "As an expert sustainability architect, provide a percentage reduction "
            "and a clear 3-step action plan. WRITE ONLY ONE CONTINUOUS PARAGRAPH. "
            "Do not use bold text, do not use bullet points, do not use hyphens, and do not use asterisks. "
            "Use only plain text sentences."
        )
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        clean_response = response.text.replace("**", "").replace("*", "").replace("#", "").replace("- ", "").strip()
        return {"prediction": clean_response}
    except Exception as e:
        return {"prediction": f"Simulation Error: {str(e)}"}
    
class NewItem(BaseModel):
    source: str 
    name: str
    carbon: float
    price: float
    efficiency: int
    swap: str
    impact: str

@app.post("/api/add-master")
async def add_to_master(item: NewItem):
    try:
        master = load_db(MASTER_JSON)
        if 'items' not in master:
            master = {"items": {"canteen": [], "nescafe": []}}
            
        entry = {
            "name": item.name,
            "carbon": item.carbon,
            "price": item.price,
            "efficiency": item.efficiency,
            "swap": item.swap,
            "impact": item.impact
        }
        
        if item.source in master['items']:
            # Prevent duplicating identical names
            master['items'][item.source] = [x for x in master['items'][item.source] if x['name'].lower() != item.name.lower()]
            master['items'][item.source].append(entry)
            save_db(MASTER_JSON, master)
            return {"status": "success", "message": f"Added {item.name}"}
        return {"status": "error", "message": "Invalid source category"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    port_env = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port_env, reload=False)
