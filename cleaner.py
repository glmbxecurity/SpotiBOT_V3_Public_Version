import spotipy
# from spotipy.oauth2 import SpotifyOAuth (ELIMINADO)
import logging
import time
from datetime import datetime, timezone
import config
from spotify_helper import sp # Importamos el cliente seguro

# CONFIGURACIÓN
SAFE_PREFIX = "SpotiSession"  # Solo tocamos las listas del bot
DAYS_TO_EXPIRE = 90           # Días de vida de la playlist

# Configuración de Logs
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("cleaner.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Cleaner")

def get_spotify_client():
    return sp # Usamos la instancia global segura

def run_cleanup():
    sp = get_spotify_client()
    try:
        user_id = sp.me()['id']
    except Exception as e:
        logger.error(f"❌ Error conectando con Spotify: {e}")
        return

    logger.info("⏳ Iniciando escaneo de caducidad (90 días)...")
    
    offset = 0
    batch_size = 50
    deleted_count = 0
    scanned_count = 0
    
    now = datetime.now(timezone.utc)

    while True:
        try:
            results = sp.current_user_playlists(limit=batch_size, offset=offset)
            if not results['items']:
                break
            
            for item in results['items']:
                # 1. FILTRO DE SEGURIDAD: Nombre + Dueño
                if item['name'].startswith(SAFE_PREFIX) and item['owner']['id'] == user_id:
                    scanned_count += 1
                    
                    try:
                        # Necesitamos detalles para ver followers y tracks
                        pl_id = item['id']
                        full_pl = sp.playlist(pl_id)
                        followers = full_pl['followers']['total']
                        
                        # 2. REGLA DE ORO: Si alguien la sigue, SE SALVA.
                        if followers > 0:
                            continue 
                        
                        # 3. CHEQUEO DE FECHA
                        # Miramos cuándo se añadió la primera canción para estimar la edad
                        if full_pl['tracks']['total'] > 0:
                            first_track = full_pl['tracks']['items'][0]
                            if first_track.get('added_at'):
                                added_at = datetime.fromisoformat(first_track['added_at'].replace('Z', '+00:00'))
                                age_days = (now - added_at).days
                                
                                if age_days >= DAYS_TO_EXPIRE:
                                    logger.info(f"🗑️ BORRANDO: '{item['name']}' (Edad: {age_days} días, Followers: 0)")
                                    sp.current_user_unfollow_playlist(pl_id)
                                    deleted_count += 1
                                    time.sleep(0.5) # Pausa para no saturar la API
                            
                    except Exception as e:
                        logger.error(f"Error analizando {item['id']}: {e}")

            offset += batch_size
            
        except Exception as e:
            logger.error(f"Error en paginación: {e}")
            break

    logger.info(f"🏁 Limpieza finalizada. Escaneadas: {scanned_count} | Borradas: {deleted_count}")

if __name__ == "__main__":
    run_cleanup()
