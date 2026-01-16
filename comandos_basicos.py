import spotipy
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from datetime import datetime, timezone
import dateutil.parser 

# IMPORTS LOCALES
import config
import stats
from utils import load_presets, get_back_button
from spotify_helper import sp as sp_info

# --- SETUP SPOTIFY (Para Info y Chequeo) ---
# sp_info = ... (ELIMINADO: Usamos la instancia global de spotify_helper)

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
        "👇 **MENÚ PRINCIPAL**\n"
        "⚡ /create - **Crear Sesión**\n"
        "📡 /scan - **Escanear Playlist**\n"
        "📊 /info - **Mi Estado**\n"
        "❓ /help - **Ayuda**"
    )
    
    keyboard = []
    
    # Botón de ADMIN si corresponde
    if user.id == config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Panel Admin", callback_data='admin_entry')])

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📚 **GUÍA RÁPIDA**\n\n"
        "**1. Crear Sesión nueva (/create)**\n"
        "• **Pega tus propias playlist**: Usa tus links de Spotify (Listas, Álbumes, Radar Novedades, Daily Mix... ¡Todo vale!).\n"
        "• **Estilos del Bot**: Elige una categoría de nuestro catálogo.\n"
        "• **Mezcla de Estilos**: Fusiona varios géneros. El bot equilibrará los estilos (50/50, 33/33...) para que ninguno domine sobre otro.\n"
        "• **Random Mix**: El bot elige 3 géneros al azar y crea una mezcla equilibrada sorpresa.\n\n"
        
        "**2. Algoritmos de Selección**\n"
        "• **⚡ Max Energy**: Prioriza canciones con energía alta (ideal Gym/Correr).\n"
        "• **🔥 Temas Populares**: Selecciona los hits más famosos y bailables de la fuente.\n"
        "• **🔭 Discovery**: Prioriza novedades (<30 días) y joyas ocultas.\n"
        "• **🎲 Random**: Selección totalmente aleatoria (cualquier canción puede salir).\n\n"
        
        "**3. Caducidad**\n"
        "Las playlists duran **90 días**. Si te gusta una, dale a **'Seguir'** en Spotify para guardarla siempre."
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
        limit_safe = 10000 # Límite aprox de Spotify
        free_slots = limit_safe - current_playlists
        status_emoji = "🟢" if free_slots > 1000 else "🟠" if free_slots > 200 else "🔴"
    except:
        status_emoji = "⚠️"

    dev = config.DEV_INFO
    msg = (
        "📊 **ESTADO DEL SISTEMA**\n\n"
        f"👥 **Usuarios Activos:** {internal_data['users']}\n"
        f"💿 **Playlists Creadas:** {internal_data['generated']}\n\n"
        f"🚦 **Salud de la Cuenta:** {status_emoji}\n"
        f"📦 **Capacidad Restante:** {free_slots} playlists aprox.\n\n"
        "👨‍💻 **Créditos**\n"
        f"By **{dev['name']}**"
    )
    
    keyboard = [
        [InlineKeyboardButton("📂 Ver Catálogo de Estilos", callback_data='view_catalog')],
        [get_back_button()]
    ]

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=msg,
        parse_mode="Markdown", 
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def view_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    presets = load_presets()
    text = "📂 **CATÁLOGO DISPONIBLE**\n"
    
    if presets:
        for genre, items in presets.items():
            text += f"\n🔹 **{genre}**\n"
            for item in items:
                text += f"   ▪️ {item['name']}\n"
    else:
        text += "❌ (Vacío)"
        
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))


