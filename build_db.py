import json
import random

def generate_static_db():
    db = {"metadata": {"canteen_count": 235, "nescafe_count": 56}, "items": {"canteen": [], "nescafe": []}}
    
    # Categories for variety
    canteen_types = ["Rice Bowl", "Pasta", "Salad", "Sandwich", "Curry", "Burger", "Soup"]
    nescafe_types = ["Espresso", "Latte", "Cappuccino", "Muffin", "Cookie", "Cold Brew"]

    # Generate 235 Canteen Items
    for i in range(1, 236):
        name = f"{random.choice(canteen_types)} {i}"
        carbon = round(random.uniform(0.5, 4.5), 2)  # kg CO2e
        db["items"]["canteen"].append({
            "id": f"C-{i:03}",
            "name": name,
            "carbon": carbon,
            "solution": "Switch to locally sourced seasonal ingredients to reduce transport emissions.",
            "pkg": random.choice(["Compostable Tray", "Reusable Plate", "Recycled Paper"]),
            "saving": round(carbon * 0.2, 2),
            "efficiency": random.randint(60, 95)
        })

    # Generate 56 Nescafe Items
    for i in range(1, 57):
        name = f"{random.choice(nescafe_types)} {i}"
        carbon = round(random.uniform(0.2, 1.2), 2)
        db["items"]["nescafe"].append({
            "id": f"N-{i:03}",
            "name": name,
            "carbon": carbon,
            "solution": "Encourage use of personal reusable tumblers via a discount incentive.",
            "pkg": random.choice(["Paper Cup", "Plastic Lid", "Aluminum Can"]),
            "saving": round(carbon * 0.15, 2),
            "efficiency": random.randint(70, 98)
        })

    with open("university_sustainability_master.json", "w") as f:
        json.dump(db, f, indent=4)
    print("Database built with 291 items.")

if __name__ == "__main__":
    generate_static_db()