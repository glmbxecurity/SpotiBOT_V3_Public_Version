import random
import spotipy
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
from spotify_helper import sp # IMPORTAMOS EL CLIENTE SEGURO

# ESTADOS
ALGORITHM, SOURCE, SELECT_PRESET, INPUT_LINK, DURATION = range(5)

# SETUP SPOTIFY
# sp = ... (ELIMINADO: Usamos la instancia global de spotify_helper)

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
        
        context.user_data['source_tag'] = "Surprise Mix"
        context.user_data['source_desc'] = "Selección Aleatoria Global"
        
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
            
            context.user_data['source_tag'] = genre
            context.user_data['source_desc'] = f"Catálogo: {genre}"
            
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

    context.user_data['source_tag'] = "Custom Mix"
    
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

# 5. PROCESO FINAL (LÓGICA ROUND ROBIN IMPLEMENTADA)
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
        algo = context.user_data.get('algorithm')
        now = datetime.now(timezone.utc)
        
        # --- ESTRATEGIA ROUND ROBIN: PROCESAMOS CADA PLAYLIST POR SEPARADO ---
        playlists_buckets = [] # Aquí guardaremos listas de canciones ya ordenadas: [[A1, A2...], [B1, B2...]]
        real_playlist_names = []
        
        for url in source_urls:
            pid = extract_playlist_id(url)
            if not pid: continue
            
            # 1. Obtener Nombre (si es custom)
            if context.user_data.get('source_tag') == "Custom Mix":
                try:
                    pl_meta = sp.playlist(pid, fields="name")
                    real_playlist_names.append(pl_meta['name'])
                except:
                    real_playlist_names.append("Privada")

            # 2. Leer canciones de ESTA fuente
            this_pl_tracks = []
            try:
                res = sp.playlist_tracks(pid, limit=100) # Leemos 100 para tener margen de filtrado
                items = res['items']
                if res['next']: # Si hay más, leemos un poco más
                     res = sp.next(res)
                     items.extend(res['items'])
                
                for item in items:
                    if item.get('track') and item['track'].get('id'):
                        this_pl_tracks.append(item)
            except Exception as e:
                print(f"⚠️ Error leyendo {url}: {e}")
                continue
            
            if not this_pl_tracks: continue

            # 3. Obtener Audio Features de ESTE lote
            tids = list(set([t['track']['id'] for t in this_pl_tracks]))
            features_map = {}
            for i in range(0, len(tids), 100):
                try:
                    chunk = tids[i:i+100]
                    feats = sp.audio_features(chunk)
                    for f in feats:
                        if f: features_map[f['id']] = f
                except: pass

            # 4. Puntuar y Ordenar ESTE lote (Aplicar criterio Energy/Hype + Jitter)
            scored_tracks = []
            
            # Shuffle inicial para romper el orden de la lista original antes de puntuar
            random.shuffle(this_pl_tracks) 

            for item in this_pl_tracks:
                track = item['track']
                feat = features_map.get(track['id'])
                
                # --- FACTOR CAOS (JITTER) ---
                luck = random.randint(0, 100)
                score = 0
                
                if algo == 'algo_energy': 
                    energy_val = (feat['energy'] * 100) if feat else 50
                    score = (energy_val * 0.7) + (luck * 0.3)

                elif algo == 'algo_party': 
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
                                score = 500 + track['popularity'] + (luck * 2) 
                            else: 
                                score = (track['popularity'] * 0.5) + (luck * 0.5)
                        else:
                            score = (track['popularity'] * 0.5) + (luck * 0.5)
                    except: 
                        score = (track['popularity'] * 0.5) + (luck * 0.5)

                if score > 0:
                    scored_tracks.append({'uri': track['uri'], 'dur': track['duration_ms'], 'score': score})

            # Ordenamos este cubo por puntuación (Los mejores de ESTA lista arriba)
            scored_tracks.sort(key=lambda x: x['score'], reverse=True)
            
            if scored_tracks:
                playlists_buckets.append(scored_tracks)

        if not playlists_buckets:
            await msg.edit_text("❌ No pude obtener canciones válidas de ninguna lista.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
            return ConversationHandler.END

        # --- FASE DE MEZCLA: ROUND ROBIN ---
        final_uris = []
        curr_ms = 0
        seen_uris = set()
        
        # Iteramos mientras no alcancemos el tiempo y queden canciones
        keep_going = True
        while keep_going:
            keep_going = False # Asumimos que paramos a menos que añadamos algo
            
            # Recorremos cada cubo (playlist) y sacamos LA MEJOR que le quede
            for bucket in playlists_buckets:
                if not bucket: continue # Este cubo ya se vació
                
                # Comprobamos si nos pasamos de tiempo antes de añadir
                if curr_ms >= limit_ms:
                    keep_going = False
                    break
                
                # Sacamos la mejor canción restante (pop del principio)
                track = bucket.pop(0)
                
                if track['uri'] not in seen_uris:
                    final_uris.append(track['uri'])
                    seen_uris.add(track['uri'])
                    curr_ms += track['dur']
                    keep_going = True # Hemos añadido algo, seguimos otra vuelta

            if curr_ms >= limit_ms: break

        if not final_uris:
            await msg.edit_text("⚠️ No se generó la lista.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
            return ConversationHandler.END

        # --- CREACIÓN EN SPOTIFY ---
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
        
        # Descripción
        source_tag = context.user_data.get('source_tag', 'Mix')
        if source_tag == "Custom Mix" and real_playlist_names:
            names_str = ", ".join(real_playlist_names)
            if len(names_str) > 150: names_str = names_str[:147] + "..."
            source_desc = f"Mezcla equitativa de: {names_str}"
        else:
            source_desc = context.user_data.get('source_desc', 'Origen desconocido')

        playlist_name = f"SpotiSession: {source_tag} ({mode_str}) [{unique_suffix}]"
        
        final_description = (
            f"Creada por SpotiBOT para {user_ref}. "
            f"Modo: {mode_str}. "
            f"{source_desc}."
        )
        
        new_pl = sp.user_playlist_create(
            user=user_id, 
            name=playlist_name, 
            public=True, 
            description=final_description
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
            f"📝 **{source_desc}**\n\n"
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
