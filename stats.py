import json
import os

STATS_FILE = "stats.json"

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"unique_users": [], "total_generated": 0}
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"unique_users": [], "total_generated": 0}

def save_stats(data):
    with open(STATS_FILE, "w") as f:
        json.dump(data, f, indent=4)

def track_user(user_id):
    """Solo registra que un usuario ha usado el bot (sin sumar playlist)."""
    data = load_stats()
    if user_id not in data["unique_users"]:
        data["unique_users"].append(user_id)
        save_stats(data)

def count_new_playlist():
    """Suma +1 al contador de playlists generadas."""
    data = load_stats()
    data["total_generated"] += 1
    save_stats(data)

def get_stats_summary():
    data = load_stats()
    return {
        "users": len(data["unique_users"]),
        "generated": data["total_generated"]
    }
