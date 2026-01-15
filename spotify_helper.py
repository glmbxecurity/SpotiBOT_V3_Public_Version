import spotipy
from spotipy.oauth2 import SpotifyOAuth
import config
import logging
import time

# Configurar logger para este módulo
logger = logging.getLogger(__name__)

class SilentAuthManager(SpotifyOAuth):
    """
    Gestor de autenticación que PROHIBE terminantemente abrir el navegador 
    o pedir input por consola. Si el token caduca y no se puede refrescar 
    automáticamente, lanza un error en lugar de bloquear el bot.
    """
    def get_authorization_code(self, response_type):
        # Esta función es la que Spotipy llama cuando necesita que el usuario
        # haga clic en una URL. La sobreescribimos para evitar el bloqueo.
        logger.error("🛑 CRÍTICO: SpotiBOT intentó pedir autenticación manual en segundo plano.")
        raise Exception(
            "CRITICAL: Token caducado y no se pudo refrescar automáticamente. "
            "El bot requiere mantenimiento manual (correr generate_token.py localmente)."
        )

def get_spotify_client():
    """
    Retorna una instancia singleton de Spotify segura para entornos desatendidos.
    Usa el archivo .cache_spotibot existente para renovar el token infinitamente.
    """
    scope_full = "playlist-modify-public playlist-modify-private playlist-read-private ugc-image-upload"
    
    # Usamos nuestra clase personalizada que bloquea el input
    auth_manager = SilentAuthManager(
        client_id=config.SPOTIPY_CLIENT_ID,
        client_secret=config.SPOTIPY_CLIENT_SECRET,
        redirect_uri=config.SPOTIPY_REDIRECT_URI,
        scope=scope_full,
        cache_path=config.CACHE_PATH,
        open_browser=False # Redundante con nuestra clase, pero por seguridad
    )

    # Creamos el cliente
    sp = spotipy.Spotify(auth_manager=auth_manager)
    
    return sp

# Instancia global para importar desde otros módulos
sp = get_spotify_client()
