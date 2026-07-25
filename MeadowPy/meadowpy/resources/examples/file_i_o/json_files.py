# JSON Files
# JSON is a popular format for structured data.
# Python dicts and lists map perfectly to JSON.

import json

# Some data to save
game_save = {
    "player": "Hero123",
    "level": 7,
    "health": 85,
    "inventory": ["sword", "shield", "potion"],
    "position": {"x": 42, "y": 108}
}

# === Save to JSON file ===
with open("savegame.json", "w") as f:
    # indent=2 makes the file human-readable
    json.dump(game_save, f, indent=2)
print("Game saved!")

# === Load from JSON file ===
with open("savegame.json", "r") as f:
    loaded = json.load(f)

print(f"\nLoaded save for: {loaded['player']}")
print(f"Level: {loaded['level']}")
print(f"Health: {loaded['health']}")
print(f"Items: {', '.join(loaded['inventory'])}")
print(f"Position: ({loaded['position']['x']}, {loaded['position']['y']})")

# === Convert to/from JSON strings ===
data = {"name": "Alice", "scores": [95, 87, 92]}
json_string = json.dumps(data)  # Dict -> JSON string
print(f"\nJSON string: {json_string}")

back_to_dict = json.loads(json_string)  # JSON string -> Dict
print(f"Back to dict: {back_to_dict}")
