import random
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
import qrcode
import os
import base64
import uuid
from io import BytesIO
from datetime import datetime, timezone

# IMPORTS LOCALES
import config
import stats
from utils import load_presets, extract_playlist_id, get_back_button

# ESTADOS
ALGORITHM, SOURCE, SELECT_PRESET, INPUT_LINK, DURATION = range(5)

# SETUP SPOTIFY
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=config.SPOTIPY_CLIENT_ID,
    client_secret=config.SPOTIPY_CLIENT_SECRET,
    redirect_uri=config.SPOTIPY_REDIRECT_URI,
    scope="playlist-modify-public playlist-modify-private playlist-read-private ugc-image-upload",
    cache_path=config.CACHE_PATH
))

# --- FUNCIÓN DE RETORNO AL MENÚ ---
async def cancel_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: 
        await query.answer()
        try: await query.delete_message()
        except: pass
            
    from comandos_basicos import start
    await start(update, context)
    return ConversationHandler.END

# 1. PUNTO DE ENTRADA
async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear() 
    
    keyboard = [
        [InlineKeyboardButton("⚡ Max Energy", callback_data='algo_energy')],
        [InlineKeyboardButton("🎉 Party Hype", callback_data='algo_party')],
        [InlineKeyboardButton("🔭 Discovery", callback_data='algo_discovery')],
        [get_back_button()]
    ]
    await update.message.reply_text("🧠 **PASO 1: Elige el estilo**", reply_markup=InlineKeyboardMarkup(keyboard))
    return ALGORITHM

# 2. GUARDAR ALGORITMO Y PREGUNTAR ORIGEN
async def save_algorithm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'return_menu': return await cancel_create(update, context)
    
    context.user_data['algorithm'] = query.data
    
    keyboard = [
        [InlineKeyboardButton("🔗 Mis Links", callback_data='src_links')],
        [InlineKeyboardButton("💿 Catálogo", callback_data='src_catalog')],
        [InlineKeyboardButton("🎲 Mix Sorpresa", callback_data='src_random')],
        [get_back_button()]
    ]
    await query.edit_message_text("🎧 **PASO 2: ¿Origen de la música?**", reply_markup=InlineKeyboardMarkup(keyboard))
    return SOURCE

# 3. MANEJAR SELECCIÓN DE ORIGEN
async def handle_source_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'return_menu': return await cancel_create(update, context)

    choice = query.data
    
    if choice == 'src_links':
        await query.edit_message_text("🔗 Pega tus links:", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return INPUT_LINK
    
    elif choice == 'src_catalog':
        presets = load_presets()
        keyboard = []
        for idx, genre in enumerate(presets.keys()):
            keyboard.append([InlineKeyboardButton(f"{genre}", callback_data=f"genre_{idx}")])
        keyboard.append([get_back_button()])
        await query.edit_message_text("💿 **Catálogo:**", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_PRESET
    
    elif choice == 'src_random':
        presets = load_presets()
        random_sources = []
        for genre, items in presets.items():
            if items:
                picked = random.choice(items)
                if isinstance(picked, dict):
                    random_sources.append(picked.get('url'))
                else:
                    random_sources.append(picked)
        context.user_data['source_urls'] = random_sources
        return await ask_duration(query, context)

# 4A. SI ELIGIÓ CATÁLOGO
async def handle_preset_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'return_menu': return await cancel_create(update, context)
    
    try:
        idx = int(query.data.replace("genre_", ""))
        presets = load_presets()
        all_genres = list(presets.keys())
        
        if 0 <= idx < len(all_genres):
            genre = all_genres[idx]
            context.user_data['source_urls'] = [item['url'] for item in presets.get(genre, [])]
        else:
            await query.edit_message_text("❌ Error: Género no encontrado.")
            return await cancel_create(update, context)

    except ValueError:
        await query.edit_message_text("❌ Error interno de índices.")
        return await cancel_create(update, context)
    
    return await ask_duration(query, context)

# 4B. SI ELIGIÓ LINKS
async def handle_user_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    urls = text.split()
    valid_urls = [u for u in urls if "http" in u]
    
    if not valid_urls:
        await update.message.reply_text("❌ Link malo.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return INPUT_LINK
        
    context.user_data['source_urls'] = valid_urls
    
    keyboard = [
        [InlineKeyboardButton("30 min", callback_data='dur_30'), InlineKeyboardButton("60 min", callback_data='dur_60')],
        [InlineKeyboardButton("90 min", callback_data='dur_90'), InlineKeyboardButton("120 min", callback_data='dur_120')],
        [InlineKeyboardButton("150 min", callback_data='dur_150')],
        [get_back_button()]
    ]
    await update.message.reply_text("⏱️ **PASO 3: Duración**", reply_markup=InlineKeyboardMarkup(keyboard))
    return DURATION

# AUXILIAR: PREGUNTAR DURACIÓN
async def ask_duration(query, context):
    keyboard = [
        [InlineKeyboardButton("30 min", callback_data='dur_30'), InlineKeyboardButton("60 min", callback_data='dur_60')],
        [InlineKeyboardButton("90 min", callback_data='dur_90'), InlineKeyboardButton("120 min", callback_data='dur_120')],
        [InlineKeyboardButton("150 min", callback_data='dur_150')],
        [get_back_button()]
    ]
    await query.edit_message_text("⏱️ **PASO 3: Duración**", reply_markup=InlineKeyboardMarkup(keyboard))
    return DURATION

# 5. PROCESO FINAL
async def process_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'return_menu': return await cancel_create(update, context)

    mins = int(query.data.replace("dur_", ""))
    limit_ms = mins * 60 * 1000
    msg = await query.edit_message_text(f"⏳ **Generando sesión de {mins} min...**")

    try:
        source_urls = context.user_data.get('source_urls', [])
        source_urls = [u for u in source_urls if u] 
        
        all_tracks = []
        for url in source_urls:
            pid = extract_playlist_id(url)
            if not pid: continue
            try:
                res = sp.playlist_tracks(pid, limit=100)
                items = res['items']
                if res['next']:
                     res = sp.next(res)
                     items.extend(res['items'])
                
                for item in items:
                    if item.get('track') and item['track'].get('id'):
                        all_tracks.append(item)
            except Exception as e:
                print(f"⚠️ Error menor leyendo fuente {url}: {e}") 

        if not all_tracks:
            await msg.edit_text("❌ No pude leer canciones válidas.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
            return ConversationHandler.END

        # MEZCLA PREVIA
        random.shuffle(all_tracks)

        tids = list(set([t['track']['id'] for t in all_tracks]))
        features_map = {}
        for i in range(0, len(tids), 100):
            try:
                chunk = tids[i:i+100]
                feats = sp.audio_features(chunk)
                for f in feats:
                    if f: features_map[f['id']] = f
            except: pass

        algo = context.user_data.get('algorithm')
        processed_tracks = []
        now = datetime.now(timezone.utc)
        
        seen_uris = set()

        for item in all_tracks:
            track = item['track']
            uri = track['uri']

            if uri in seen_uris: continue
            
            feat = features_map.get(track['id'])
            
            # --- FACTOR CAOS (PONDERADO) ---
            luck = random.randint(0, 100)
            score = 0
            
            if algo == 'algo_energy': 
                # 70% Energía / 30% Suerte (Para el gym/entreno la energía manda, pero variamos)
                energy_val = (feat['energy'] * 100) if feat else 50
                score = (energy_val * 0.7) + (luck * 0.3)

            elif algo == 'algo_party': 
                # --- CAMBIO APLICADO: 85% Hits / 15% Suerte ---
                # Queremos asegurar los hits conocidos.
                base_val = track['popularity']
                if feat: base_val += (feat['danceability'] * 100)
                base_val = base_val / 2
                score = (base_val * 0.85) + (luck * 0.15)

            elif algo == 'algo_discovery':
                try:
                    if item.get('added_at'):
                        added = datetime.fromisoformat(item['added_at'].replace('Z', '+00:00'))
                        days_old = (now - added).days
                        
                        if days_old <= 30: 
                            # Boost Masivo a lo nuevo + Suerte para rotar novedades
                            score = 500 + track['popularity'] + (luck * 2) 
                        else: 
                            # Si es vieja, la suerte influye más
                            score = (track['popularity'] * 0.5) + (luck * 0.5)
                    else:
                        score = (track['popularity'] * 0.5) + (luck * 0.5)
                except: 
                    score = (track['popularity'] * 0.5) + (luck * 0.5)

            if score > 0: 
                processed_tracks.append({'uri': uri, 'dur': track['duration_ms'], 'score': score})
                seen_uris.add(uri)

        processed_tracks.sort(key=lambda x: x['score'], reverse=True)
        
        if not processed_tracks and all_tracks:
             for t in all_tracks:
                 uri = t['track']['uri']
                 if uri not in seen_uris:
                     processed_tracks.append({'uri': uri, 'dur': t['track']['duration_ms'], 'score': 1})
                     seen_uris.add(uri)

        if not processed_tracks:
            await msg.edit_text("⚠️ No quedaron canciones tras el filtro.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
            return ConversationHandler.END

        final_uris = []
        curr_ms = 0
        for t in processed_tracks:
            if curr_ms + t['dur'] > limit_ms: break
            final_uris.append(t['uri'])
            curr_ms += t['dur']
            
        user_id = sp.me()['id']
        unique_suffix = uuid.uuid4().hex[:4].upper()
        tg_user = update.effective_user
        user_ref = f"@{tg_user.username}" if tg_user.username else tg_user.first_name
        
        mode_names = {
            'algo_energy': 'Max Energy',
            'algo_party': 'Party Hype',
            'algo_discovery': 'Discovery'
        }
        mode_str = mode_names.get(algo, 'Mix')
        
        playlist_name = f"SpotiSession {mode_str} [{unique_suffix}]"
        
        new_pl = sp.user_playlist_create(
            user=user_id, 
            name=playlist_name, 
            public=True, 
            description=f"Mezcla generada por SpotiBOT para {user_ref}. Modo: {mode_str}"
        )
        
        stats.count_new_playlist()
        
        for i in range(0, len(final_uris), 100):
            sp.playlist_add_items(new_pl['id'], final_uris[i:i+100])
        pl_url = new_pl['external_urls']['spotify']
        
        try:
            prefix_map = {'algo_energy': 'maxenergy', 'algo_party': 'partyhype', 'algo_discovery': 'discovery'}
            img_prefix = prefix_map.get(algo, 'spotimix')
            images_dir = os.path.join(config.BASE_DIR, 'images', 'pool')
            candidates = [f for f in os.listdir(images_dir) if f.startswith(img_prefix) and f.endswith(".jpg")]
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
        bio = BytesIO()
        qr.make_image().save(bio, 'PNG')
        bio.seek(0)
        
        await msg.delete()
        
        caption = (
            f"✅ **{playlist_name}**\n\n"
            f"⏱ **Duración:** {int(curr_ms/60000)} min\n"
            f"🔗 {pl_url}\n\n"
            "♻️ **Esta playlist se autodestruirá en 3 meses.**\n"
            "Si no quieres que esto ocurra, dale a **Seguir** y se conservará para siempre ❤️\n\n"
            "✅ **Acción completada.**"
        )
        
        await update.effective_message.reply_photo(
            photo=bio,
            caption=caption,
            reply_markup=InlineKeyboardMarkup([[get_back_button()]])
        )

    except Exception as e:
        print(f"Error fatal en proceso: {e}")
        await update.effective_message.reply_text(
            f"❌ Ocurrió un error: {e}", 
            reply_markup=InlineKeyboardMarkup([[get_back_button()]])
        )
    
    return ConversationHandler.END
