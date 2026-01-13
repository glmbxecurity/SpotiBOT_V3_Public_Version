import spotipy
from spotipy.oauth2 import SpotifyOAuth
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime, timezone
import dateutil.parser 

# IMPORTS LOCALES
import config
import stats
from utils import load_presets, get_back_button, extract_playlist_id

# --- SETUP SPOTIFY (Para Info y Chequeo) ---
sp_info = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=config.SPOTIPY_CLIENT_ID,
    client_secret=config.SPOTIPY_CLIENT_SECRET,
    redirect_uri=config.SPOTIPY_REDIRECT_URI,
    scope="playlist-read-private",
    open_browser=False,
    cache_path=config.CACHE_PATH
))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Nombre
    if user.username:
        nombre_mostrar = f"@{user.username}"
    else:
        nombre_mostrar = user.first_name

    msg = (
        f"🎧 **¡Hola {nombre_mostrar}!**\n"
        "**Bienvenido a SpotiBOT.**\n\n"
        "👇 **HERRAMIENTAS**\n"
        "⚡ /create - **Crear Sesión**\n"
        "🧬 /mix - **Mezclador**\n"
        "📡 /scan - **Analizar Playlist**\n"
        "📊 /info - **Estado y Catálogo**\n"
        "❓ /help - **Manual y Criterios**"
    )
    # USAMOS send_message PARA ASEGURAR QUE LLEGA SIEMPRE
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📚 **MANUAL DE INGENIERÍA SPOTIBOT**\n\n"
        "Aquí tienes los detalles técnicos de cómo proceso tu música:\n\n"
        
        "🧠 **MODOS Y ALGORITMOS**\n"
        "**1. ⚡ Max Energy (Gym/Entreno)**\n"
        "• **Objetivo:** Intensidad pura.\n"
        "• **Criterio:** 70% Energía / 30% Aleatoriedad.\n"
        "• Las baladas se eliminan. Prioriza BPM altos y potencia.\n\n"
        
        "**2. 🎉 Party Hype (Fiesta)**\n"
        "• **Objetivo:** Que todo el mundo cante y baile.\n"
        "• **Criterio:** 85% Fama+Baile / 15% Aleatoriedad.\n"
        "• Garantiza Hits conocidos. Muy poca variación para asegurar éxitos.\n\n"
        
        "**3. 🔭 Discovery (Novedades)**\n"
        "• **Objetivo:** Encontrar música fresca.\n"
        "• **Criterio:** Filtro de **30 días**.\n"
        "• Las canciones añadidas en el último mes tienen **prioridad absoluta**. El resto se usa solo de relleno.\n\n"
        
        "🎲 **FACTOR CAOS (JITTER)**\n"
        "Para evitar el *'Efecto Fotocopia'*, aplico una variación matemática a cada sesión. Si me pides la misma lista dos veces, **nunca será idéntica**. El orden cambiará y entrarán canciones que antes se quedaron fuera por poco.\n\n"
        
        "♻️ **POLÍTICA DE LIMPIEZA (AUTO-BORRADO)**\n"
        "Para mantener mi base de datos ágil, todas las playlists generadas **se autodestruyen a los 3 meses (90 días)**.\n"
        "📌 **¿Cómo evitarlo?** Simplemente dale a **'Seguir' (❤️)** o guarda la playlist en tu biblioteca de Spotify. Así pasará a ser tuya y yo no la tocaré."
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup([[get_back_button()]])
    )

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    internal_data = stats.get_stats_summary()
    status_emoji = "⚪"
    free_slots = "..."
    current_playlists = 0
    
    try:
        current_playlists = sp_info.current_user_playlists(limit=1)['total']
        limit_safe = 9000
        free_slots = limit_safe - current_playlists
        status_emoji = "🟢" if free_slots > 1000 else "🟠" if free_slots > 200 else "🔴"
    except:
        status_emoji = "⚠️"

    presets = load_presets()
    catalog_text = ""
    if presets:
        for genre, items in presets.items():
            catalog_text += f"\n📂 **{genre}**\n"
            for item in items:
                catalog_text += f"   ▪️ {item['name']}\n"
    else:
        catalog_text = "❌ Vacío."

    dev = config.DEV_INFO
    msg = (
        "📊 **PANEL DE CONTROL SPOTIBOT**\n\n"
        f"👥 **Usuarios:** {internal_data['users']}\n"
        f"🔨 **Generadas:** {internal_data['generated']}\n\n"
        f"🚦 **Estado:** {status_emoji} ({free_slots} huecos libres)\n\n"
        "📚 **Catálogo:**"
        f"{catalog_text}\n"
        "👨‍💻 **Developer**\n"
        f"Desarrollado por **{dev['name']}**.\n"
        f"🔗 [GitHub]({dev['github']}) | [LinkedIn]({dev['linkedin']})\n"
        f"📧 {dev['email']}" 
    )
    
    keyboard = [
        [InlineKeyboardButton("🕵️ Revisar Salud del Catálogo", callback_data='check_catalog')],
        [get_back_button()]
    ]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode="Markdown", 
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# --- FUNCIÓN CORREGIDA: CHEQUEO BIDIRECCIONAL ---
async def check_catalog_health(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🕵️ **Analizando fechas de actualización...**\n(Revisando inicio y final de las listas)")
    
    presets = load_presets()
    if not presets:
        await query.edit_message_text("❌ El catálogo está vacío.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return

    report = "🏥 **SALUD DEL CATÁLOGO**\n\n"
    now = datetime.now(timezone.utc)

    for genre, items in presets.items():
        report += f"📂 **{genre}**\n"
        for item in items:
            name = item['name']
            url = item['url']
            pid = extract_playlist_id(url)
            
            status_icon = "❓"
            date_str = "Error"
            
            if pid:
                try:
                    pl_details = sp_info.playlist(pid, fields="tracks.total")
                    total = pl_details['tracks']['total']
                    
                    if total > 0:
                        # 1. Miramos las primeras 5 (TOP)
                        res_top = sp_info.playlist_tracks(pid, limit=5, offset=0)
                        items_check = res_top['items']
                        
                        # 2. Miramos las últimas 5 (BOTTOM) por si añaden al final
                        if total > 5:
                            offset_bottom = max(0, total - 5)
                            res_bottom = sp_info.playlist_tracks(pid, limit=5, offset=offset_bottom)
                            items_check.extend(res_bottom['items']) # Unimos ambas listas
                        
                        # 3. Buscamos la fecha más reciente de entre todas esas
                        last_added = None
                        for track_item in items_check:
                            if track_item.get('added_at'):
                                try:
                                    dt = datetime.fromisoformat(track_item['added_at'].replace('Z', '+00:00'))
                                    if last_added is None or dt > last_added:
                                        last_added = dt
                                except: pass
                        
                        if last_added:
                            days_ago = (now - last_added).days
                            
                            if days_ago < 30: status_icon = "🟢" 
                            elif days_ago < 90: status_icon = "🟠" 
                            else: status_icon = "🔴" 
                            
                            date_str = f"Hace {days_ago} días"
                        else:
                            date_str = "Sin fechas"
                    else:
                        status_icon = "⚪"
                        date_str = "Vacía"

                except Exception as e:
                    # print(f"Error checking {name}: {e}") # Debug opcional
                    status_icon = "⚠️"
                    date_str = "Error acceso"
            
            report += f"   {status_icon} **{name}:** {date_str}\n"
        report += "\n"

    report += "🟢 <30 días | 🟠 <3 meses | 🔴 >3 meses"
    
    # Cortar si es muy largo para telegram
    if len(report) > 4000:
        report = report[:4000] + "\n...(cortado)"

    await query.edit_message_text(
        report, 
        parse_mode="Markdown", 
        reply_markup=InlineKeyboardMarkup([[get_back_button()]])
    )
