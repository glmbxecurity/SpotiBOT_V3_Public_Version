import os
# --- RUTAS ABSOLUTAS (Para que no se pierda en el VPS) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, '.cache_spotibot')

# CREDENCIALES DE LA CUENTA "SPOTIbot" (PÚBLICA)
# CREDENCIALES DE LA CUENTA "SPOTIbot" (PÚBLICA)
SPOTIPY_CLIENT_ID = 'TU_CLIENT_ID_AQUI'
SPOTIPY_CLIENT_SECRET = 'TU_CLIENT_SECRET_AQUI'
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback' # O la que hayas puesto en el dashboard

# TOKEN TELEGRAM
TELEGRAM_TOKEN = 'TU_TELEGRAM_TOKEN_AQUI'

# INFO DEL DEVELOPER (Para comando /info)
DEV_INFO = {
    "name": "Edward Herrera Galamba", # Pon aquí tu nombre o alias
    "github": "https://github.com/glmbxecurity",
    "linkedin": "https://linkedin.com/in/edward-herrera-galamba",
    "email": "eddygalamba@hotmail.com"
}

# SETUP CARPETAS
# Asegúrate de crear estas carpetas en tu proyecto
DIRS = {
    "images": "images/pool", # Aquí meterás las fotos genéricas
    "data": "data"
}
COOLDOWN_SECONDS = 10
