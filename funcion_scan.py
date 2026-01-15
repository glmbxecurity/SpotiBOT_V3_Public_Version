import spotipy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import statistics
import config
from utils import extract_playlist_id, get_back_button
from spotify_helper import sp

INPUT_SCAN_LINK, SELECT_LIMIT = range(2)
# sp = ... (ELIMINADO: Usamos la instancia global de spotify_helper)

# Función de salida forzada
async def cancel_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: 
        await query.answer()
        try: await query.delete_message()
        except: pass

    # Forzamos vuelta al menú
    from comandos_basicos import start
    await start(update, context)
    return ConversationHandler.END

async def start_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[get_back_button()]]
    await update.message.reply_text(
        "📡 **Radar de Popularidad**\nEnvíame el link de la playlist.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return INPUT_SCAN_LINK

async def receive_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    pl_id = extract_playlist_id(url)
    
    if not pl_id:
        await update.message.reply_text("❌ Link inválido.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return INPUT_SCAN_LINK
    
    context.user_data['scan_id'] = pl_id
    
    keyboard = [
        [InlineKeyboardButton("Top 5", callback_data='limit_5'), InlineKeyboardButton("Top 10", callback_data='limit_10')],
        [InlineKeyboardButton("Top 15", callback_data='limit_15'), InlineKeyboardButton("Ver Todas", callback_data='limit_100')],
        [get_back_button()]
    ]
    await update.message.reply_text("📊 **¿Cuántas canciones analizo?**", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_LIMIT

async def process_scan_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'return_menu': return await cancel_scan(update, context)

    limit = int(query.data.replace('limit_', ''))
    pl_id = context.user_data.get('scan_id')
    
    await query.edit_message_text("🔍 **Escaneando...**")

    try:
        pl_data = sp.playlist(pl_id)
        results = sp.playlist_tracks(pl_id, limit=100)
        items = results['items']
        
        if results['next'] and limit >= 100:
             results2 = sp.next(results)
             items.extend(results2['items'])

        tracks = [item['track'] for item in items if item.get('track') and item['track'].get('id')]
        tracks = tracks[:100] 

        if not tracks:
            await query.message.edit_text("❌ Lista vacía o privada.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
            return ConversationHandler.END

        sorted_tracks = sorted(tracks, key=lambda x: x['popularity'], reverse=True)
        avg_pop = statistics.mean([t['popularity'] for t in tracks])

        top_text = ""
        display_limit = min(limit, len(sorted_tracks))
        
        for i in range(display_limit):
            t = sorted_tracks[i]
            icon = "🔥" if i < 3 else "🎵"
            top_text += f"{i+1}. {icon} **{t['name']}** - {t['artists'][0]['name']} ({t['popularity']})\n"

        bottom_tracks = sorted_tracks[-5:]
        bottom_tracks.reverse()
        gem_text = ""
        for t in bottom_tracks:
            gem_text += f"💎 **{t['name']}** - {t['artists'][0]['name']} ({t['popularity']})\n"

        vibe = "🌍 Mainstream" if avg_pop > 70 else "😎 Equilibrada" if avg_pop > 40 else "🕵️‍♂️ Underground"

        report = (
            f"📡 **REPORTE: {pl_data['name']}**\n"
            f"📊 Media: **{int(avg_pop)}/100** ({vibe})\n\n"
            f"🏆 **TOP {display_limit} POPULARES:**\n"
            f"{top_text}\n"
            f"🤫 **JOYAS OCULTAS:**\n"
            f"{gem_text}\n"
            "✅ **Acción completada.**" # <--- AÑADIDO
        )
        if len(report) > 4000: report = report[:4000] + "..."
        
        await query.message.edit_text(report, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))

    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))

    return ConversationHandler.END
