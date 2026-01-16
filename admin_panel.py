import yaml
import os
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from functools import wraps
import logging

import config
import cleaner
from utils import load_presets, get_back_button, extract_playlist_id
from spotify_helper import sp
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# STATES
ADMIN_MENU, EDIT_YAML_MENU, ADD_PLAYLIST_NAME, ADD_PLAYLIST_GENRE, ADD_PLAYLIST_URL, REMOVE_PLAYLIST_USELECT, AUTH_INPUT_URL = range(7)

ADMIN_ID = config.ADMIN_ID

def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ADMIN_ID:
            await update.effective_message.reply_text("⛔ Acceso denegado.")
            return ConversationHandler.END
        return await func(update, context, *args, **kwargs)
    return wrapped

@admin_only
async def admin_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Si viene de botón (Callback), respondemos y editamos o mandamos nuevo
    if update.callback_query:
        await update.callback_query.answer()
        # Si queremos que sea un menu nuevo limpio:
        # await update.callback_query.message.reply_text...
        # Pero mejor editamos si es posible, o mandamos mensaje fresco para que no borre el start
        # Para evitar problemas de "message not modified", mandamos uno nuevo si es admin command
        # Pero si es callback (boton start), mandamos nuevo mensaje
        pass
    return await show_admin_menu(update, context)

async def show_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Editar Playlists (YAML)", callback_data='admin_yaml')],
        [InlineKeyboardButton("🧹 Limpiar Listas Ahora", callback_data='admin_clean')],
        [InlineKeyboardButton("🕵️ Diagnóstico Avanzado", callback_data='admin_diag')],
        [InlineKeyboardButton("🔄 Reiniciar Servicio", callback_data='admin_restart')],
        [InlineKeyboardButton("🔑 Autenticar Spotify", callback_data='admin_auth')],
        [InlineKeyboardButton("❌ Salir", callback_data='admin_exit')]
    ]
    
    text = "🛡️ **PANEL DE ADMINISTRACIÓN**\nSelecciona una opción:"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    return ADMIN_MENU

async def admin_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.delete_message()
    return ConversationHandler.END

# --- SERVICE RESTART ---
async def admin_restart_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔄 Intentando reiniciar servicio 'spotibot'...")
    
    try:
        # Intenta ejecutar el comando de Alpine
        subprocess.run(["service", "spotibot", "restart"], check=True)
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Comando enviado. Si el bot muere aquí, es que funcionó.")
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error al reiniciar: {e}")
        # Volver al menú si falló (si funcionó, el bot morirá antes de poder volver)
        return await show_admin_menu(update, context)
        
    return ConversationHandler.END

# --- CLEANER ---
async def admin_run_cleaner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("☠️ **Ejecutando LIMPIEZA FORZADA...**\n(Borrando sesion del bot sin esperar 90 dias)")
    
    try:
        report = cleaner.run_cleanup_report(force=True) # Force True por petición del admin
        # Cortar reporte si es muy largo
        if len(report) > 4000:
            report = report[:4000] + "\n...(cortado)"
            
        await context.bot.send_message(chat_id=update.effective_chat.id, text=report)
    except Exception as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Error limpieza: {e}")
        
    return await show_admin_menu(update, context)

# --- DIAGNOSTICS ---
async def admin_diagnostics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("🕵️ **Analizando catálogo...**\n(Esto puede tardar unos segundos)")
    
    presets = load_presets()
    if not presets:
        await query.edit_message_text("❌ El catálogo está vacío.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return ADMIN_MENU # O volver con boton

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
                    pl_details = sp.playlist(pid, fields="tracks.total")
                    total = pl_details['tracks']['total']
                    
                    if total > 0:
                        # 1. Miramos las primeras 5 (TOP)
                        res_top = sp.playlist_tracks(pid, limit=5, offset=0)
                        items_check = res_top['items']
                        
                        # 2. Miramos las últimas 5 (BOTTOM) por si añaden al final
                        if total > 5:
                            offset_bottom = max(0, total - 5)
                            res_bottom = sp.playlist_tracks(pid, limit=5, offset=offset_bottom)
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
                    status_icon = "⚠️"
                    date_str = "Error acceso"
            
            report += f"   {status_icon} **{name}:** {date_str}\n"
        report += "\n"

    report += "🟢 <30 días | 🟠 <3 meses | 🔴 >3 meses"
    
    if len(report) > 4000:
        report = report[:4000] + "\n...(cortado)"

    # Mostramos y damos opcion de volver
    keyboard = [[InlineKeyboardButton("🔙 Volver al Admin", callback_data='return_admin')]]
    await query.edit_message_text(report, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Nos quedamos en un estado donde 'return_admin' funcione.
    # Como 'return_admin' está en ADMIN_MENU -> admin_panel.show_admin_menu, si devolvemos ADMIN_MENU,
    # necesitamos que ADMIN_MENU maneje 'return_admin'.
    # Actualmente ADMIN_MENU maneja: admin_yaml, admin_clean, admin_restart, admin_auth, admin_exit.
    # Necesitamos añadir 'return_admin' handler en main.py para el estado ADMIN_MENU o añadirlo aqui.
    # O simplemente reutilizar show_admin_menu como handler de 'return_admin'.
    
    return ADMIN_MENU

# --- YAML EDITING ---
async def admin_yaml_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    presets = load_presets()
    total_playlists = sum(len(items) for items in presets.values())
    
    text = (
        f"📝 **EDITOR DE PRESETS**\n"
        f"Playlists actuales: {total_playlists}\n\n"
        "Elige acción:"
    )
    
    keyboard = [
        [InlineKeyboardButton("➕ Añadir Nueva", callback_data='yaml_add')],
        [InlineKeyboardButton("➖ Eliminar Existente", callback_data='yaml_remove')],
        [InlineKeyboardButton("🔙 Volver", callback_data='return_admin')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return EDIT_YAML_MENU

# ADD FLOW
async def yaml_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("1️⃣ Escribe el **NOMBRE** de la playlist:", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
    return ADD_PLAYLIST_NAME

async def yaml_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['new_pl_name'] = text
    await update.message.reply_text("2️⃣ Escribe el **GÉNERO/ESTILO** (Tal cual aparece en el menú):", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
    return ADD_PLAYLIST_GENRE

async def yaml_add_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data['new_pl_genre'] = text
    await update.message.reply_text("3️⃣ Pega el **LINK** de Spotify:", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
    return ADD_PLAYLIST_URL

async def yaml_add_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "https://" not in url:
        await update.message.reply_text("❌ URL inválida. Intenta de nuevo:", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return ADD_PLAYLIST_URL
        
    name = context.user_data['new_pl_name']
    genre = context.user_data['new_pl_genre']
    
    new_entry = {'name': name, 'genre': genre, 'url': url}
    
    # Cargar, añadir y guardar
    file_path = os.path.join(config.BASE_DIR, 'presets.yaml')
    try:
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f) or []
            
        data.append(new_entry)
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, sort_keys=False, allow_unicode=True)
            
        await update.message.reply_text(f"✅ ¡Añadida!\n**{name}** ({genre})")
    except Exception as e:
        await update.message.reply_text(f"❌ Error guardando YAML: {e}")
        
    return await show_admin_menu(update, context)

# REMOVE FLOW
async def yaml_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    presets = load_presets()
    keyboard = []
    
    # Aplanamos la lista para mostrar botones
    flat_list = []
    for genre, items in presets.items():
        for item in items:
            flat_list.append(item)
            
    # Paginación simplificada (solo mostramos primeros 50 para no reventar telegram)
    # Una mejora sería paginar real, pero para admin rápido vale
    for idx, item in enumerate(flat_list[:40]):
        btn_text = f"🗑 {item['name'][:20]}..."
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"del_{idx}")])
        
    keyboard.append([InlineKeyboardButton("🔙 Cancelar", callback_data='return_admin')])
    
    await query.edit_message_text("Selecciona para **ELIMINAR**:", reply_markup=InlineKeyboardMarkup(keyboard))
    return REMOVE_PLAYLIST_USELECT

async def yaml_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'return_admin': return await show_admin_menu(update, context)
    
    try:
        idx = int(query.data.replace("del_", ""))
        
        # Recargamos para asegurar índices
        file_path = os.path.join(config.BASE_DIR, 'presets.yaml')
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f) or []
            
        flat_list = data # Asumimos que el yaml es una lista plana de dicts
        # Nota: load_presets devuelve dict agrupado, pero el yaml original es una lista.
        # Check presets.yaml format: is a list of dicts. Correct.
        
        if 0 <= idx < len(data):
            removed = data.pop(idx)
            with open(file_path, 'w') as f:
                yaml.dump(data, f, sort_keys=False, allow_unicode=True)
            await query.edit_message_text(f"🗑️ Eliminada: **{removed['name']}**")
        else:
            await query.edit_message_text("❌ Índice inválido.")
            
    except Exception as e:
        await query.edit_message_text(f"❌ Error borrando: {e}")
        
    # Espera un poco y vuelve
    return await show_admin_menu(update, context)


# --- AUTH FLOW ---
async def admin_auth_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Generar URL de auth manualmente
    auth_manager = sp.auth_manager
    auth_url = auth_manager.get_authorize_url()
    
    msg = (
        "🔑 **AUTENTICACIÓN MANUAL**\n\n"
        "1. Haz clic en este [LINK DE AUTENTICACIÓN]({}).\n"
        "2. Acepta y serás redirigido a una página (puede dar error, no importa).\n"
        "3. Copia el **LINK ENTERO** de la barra de direcciones de esa página (o el código `?code=...`).\n"
        "4. Pégalo aquí abajo 👇"
    ).format(auth_url)
    
    await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
    return AUTH_INPUT_URL

async def admin_auth_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Extraer código si pegaron la URL entera
    code = text
    if "code=" in text:
        try:
            code = text.split("code=")[1].split("&")[0]
        except:
            pass
            
    try:
        auth_manager = sp.auth_manager
        auth_manager.get_access_token(code)
        await update.message.reply_text("✅ **¡Token Refrescado!** Spotify listo.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error al canjear código: {e}")
        
    return await show_admin_menu(update, context)

