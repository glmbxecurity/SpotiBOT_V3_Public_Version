import spotipy
from spotipy.oauth2 import SpotifyOAuth
import config
import os

# Borramos caché antigua por si acaso no la borraste manual
if os.path.exists(config.CACHE_PATH):
    os.remove(config.CACHE_PATH)
    print("🗑️ Caché antigua borrada.")

print("🔑 Solicitando Token Maestro con TODOS los permisos (incluido portadas)...")

# AÑADIDO: 'ugc-image-upload' al final
SCOPE_FULL = "playlist-modify-public playlist-modify-private playlist-read-private ugc-image-upload"

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=config.SPOTIPY_CLIENT_ID,
    client_secret=config.SPOTIPY_CLIENT_SECRET,
    redirect_uri=config.SPOTIPY_REDIRECT_URI,
    scope=SCOPE_FULL,
    open_browser=False,
    cache_path=config.CACHE_PATH 
))

user = sp.me()
print(f"✅ ¡ÉXITO! Token renovado para: {user['display_name']}")
