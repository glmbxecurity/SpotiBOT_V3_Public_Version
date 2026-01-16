import yaml
import re
from telegram import InlineKeyboardButton

def load_presets(path="presets.yaml"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        presets = {}
        if not data: return presets

        for item in data:
            genre = item.get('genre')
            name = item.get('name')
            url = item.get('url')
            
            if genre and url:
                if genre not in presets:
                    presets[genre] = []
                presets[genre].append({'name': name, 'url': url})
        return presets
    except Exception as e:
        print(f"❌ Error presets: {e}")
        return {}

def extract_playlist_id(url):
    match = re.search(r"playlist/([a-zA-Z0-9_-]+)", url)
    return match.group(1) if match else None

def get_back_button():
    """Botón universal de retorno"""
    # CAMBIO: Texto y ID nuevos
    return InlineKeyboardButton("🏠 Menú Principal", callback_data='return_menu')
