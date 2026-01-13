import spotipy
from spotipy.oauth2 import SpotifyOAuth
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import random
import qrcode
import os
import base64
import uuid
from io import BytesIO

import config
import stats
from utils import extract_playlist_id, get_back_button

INPUT_MIX_LINKS = 0

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=config.SPOTIPY_CLIENT_ID,
    client_secret=config.SPOTIPY_CLIENT_SECRET,
    redirect_uri=config.SPOTIPY_REDIRECT_URI,
    scope="playlist-modify-public playlist-modify-private playlist-read-private ugc-image-upload",
    cache_path=config.CACHE_PATH
))

# --- FUNCIÓN DE RETORNO AL MENÚ ---
async def cancel_mix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: 
        await query.answer()
        try: await query.delete_message()
        except: pass

    from comandos_basicos import start
    await start(update, context)
    return ConversationHandler.END

async def start_mix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[get_back_button()]]
    await update.message.reply_text(
        "🧬 **Mezclador**\nPega los links de las playlists a fusionar.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return INPUT_MIX_LINKS

async def process_mix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query: 
        return await cancel_mix(update, context)

    text = update.message.text
    urls = text.split()
    msg = await update.message.reply_text("⏳ **Cocinando la mezcla...**")

    all_uris = []
    try:
        for u in urls:
            pid = extract_playlist_id(u)
            if pid:
                tracks = sp.playlist_tracks(pid, limit=100)
                for item in tracks['items']:
                    if item.get('track') and item['track'].get('id'):
                        all_uris.append(item['track']['uri'])
    except Exception as e:
        await msg.edit_text(f"❌ Error leyendo links: {e}", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return ConversationHandler.END

    if not all_uris:
        await msg.edit_text("❌ No encontré canciones válidas.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return ConversationHandler.END

    random.shuffle(all_uris)
    final_uris = all_uris[:300]
    
    try:
        user_id = sp.me()['id']
        unique_suffix = uuid.uuid4().hex[:4].upper()
        name_pl = f"SpotiMix [{unique_suffix}]"
        
        tg_user = update.effective_user
        user_ref = f"@{tg_user.username}" if tg_user.username else tg_user.first_name
        desc_text = f"Mezcla generada por SpotiBOT para {user_ref}."

        new_pl = sp.user_playlist_create(
            user=user_id, 
            name=name_pl, 
            public=True,
            description=desc_text
        )
        
        stats.count_new_playlist()
        
        for i in range(0, len(final_uris), 100):
            sp.playlist_add_items(new_pl['id'], final_uris[i:i+100])
        pl_url = new_pl['external_urls']['spotify']

        try:
            images_dir = os.path.join(config.BASE_DIR, 'images', 'pool')
            candidates = [f for f in os.listdir(images_dir) if f.startswith("spotimix") and f.endswith(".jpg")]
            if candidates:
                selected_img = random.choice(candidates)
                img_path = os.path.join(images_dir, selected_img)
                with open(img_path, "rb") as img_file:
                    img_b64 = base64.b64encode(img_file.read()).decode('utf-8')
                sp.playlist_upload_cover_image(new_pl['id'], img_b64)
        except Exception as e:
            print(f"❌ Error subiendo portada: {e}")

        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(pl_url)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        bio = BytesIO()
        img_qr.save(bio, 'PNG')
        bio.seek(0)

        await msg.delete()
        caption = (
            f"🧬 **{name_pl}**\n\n"
            f"🔗 **Link:** {pl_url}\n\n"
            "♻️ **Esta playlist se autodestruirá en 3 meses.**\n"
            "Si no quieres que esto ocurra, dale a **Seguir** y se conservará para siempre ❤️\n"
            "✅ **Acción completada.**" # <--- AÑADIDO
        )
        await update.message.reply_photo(
            photo=bio, caption=caption, reply_markup=InlineKeyboardMarkup([[get_back_button()]])
        )

    except Exception as e:
        await update.message.reply_text(f"Error creando playlist: {e}")

    return ConversationHandler.END
