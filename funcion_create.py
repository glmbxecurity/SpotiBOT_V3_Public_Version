import random
import spotipy
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
from spotify_helper import sp

# ESTADOS NUEVOS (FLUJO: MODE -> SOURCE -> ALGO -> DURATION)
SELECT_MODE, INPUT_LINKS, SELECT_CATALOG_SINGLE, SELECT_CATALOG_MULTI, SELECT_ALGORITHM, SELECT_DURATION = range(6)

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

# 1. PUNTO DE ENTRADA: MENU PRINCIPAL DE CREACIÓN
async def start_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear() 
    
    keyboard = [
        [InlineKeyboardButton("🔗 Pega tus propias playlist", callback_data='mode_links')],
        [InlineKeyboardButton("💿 Elige entre los estilos del bot", callback_data='mode_catalog')],
        [InlineKeyboardButton("🧬 Mezcla de estilos del bot", callback_data='mode_mix')],
        [InlineKeyboardButton("🎲 Random mix (Mezcla estilos random del bot)", callback_data='mode_random')],
        [get_back_button()]
    ]
    
    text = (
        "🎧 **CREADOR DE SESIONES**\n"
        "Elige tu fuente de inspiración:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        
    return SELECT_MODE

# 2. MANEJADOR DE MODO
async def handle_mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'return_menu': return await cancel_create(update, context)
    
    mode = query.data
    context.user_data['creation_mode'] = mode
    
    # A. PEGAR LINKS
    if mode == 'mode_links':
        await query.edit_message_text("🔗 **Pega tus links de Spotify** (separados por espacio):", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return INPUT_LINKS
    
    # B. CATÁLOGO SIMPLE
    elif mode == 'mode_catalog':
        presets = load_presets()
        keyboard = []
        for idx, genre in enumerate(presets.keys()):
            keyboard.append([InlineKeyboardButton(f"{genre}", callback_data=f"cat_{idx}")])
        keyboard.append([get_back_button()])
        await query.edit_message_text("💿 **Elige un Estilo:**", reply_markup=InlineKeyboardMarkup(keyboard))
        return SELECT_CATALOG_SINGLE
        
    # C. MEZCLA DE ESTILOS (MULTI)
    elif mode == 'mode_mix':
        context.user_data['multi_selection'] = [] # Indices seleccionados
        return await show_multi_selection_menu(query, context)
        
    # D. RANDOM MIX
    elif mode == 'mode_random':
        presets = load_presets()
        genres = list(presets.keys())
        
        # Cogemos 3 GÉNEROS al azar
        picked_genres = random.sample(genres, min(3, len(genres)))
        
        final_urls = []
        url_genre_map = {}
        
        for g in picked_genres:
            for item in presets[g]:
                url = item['url']
                final_urls.append(url)
                url_genre_map[url] = g

        context.user_data['source_urls'] = final_urls
        context.user_data['source_tag'] = "Random Styles"
        context.user_data['source_desc'] = f"Mix Aleatorio: {', '.join(picked_genres)}"
        context.user_data['url_genre_map'] = url_genre_map
        
        # Saltamos directo a duración (o algoritmo, vamos a algoritmo para consistencia)
        return await ask_algorithm(query, context)

    return SELECT_MODE

# --- LOGICA MEZCLA ESTILOS (MULTI-SELECT) ---
async def show_multi_selection_menu(query, context):
    selected = context.user_data.get('multi_selection', [])
    presets = load_presets()
    genres = list(presets.keys())
    
    keyboard = []
    # Filas de 2 columnas
    row = []
    for idx, genre in enumerate(genres):
        status = "✅" if idx in selected else "⬜"
        btn_text = f"{status} {genre}"
        row.append(InlineKeyboardButton(btn_text, callback_data=f"multi_{idx}"))
        
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    
    # Botón Confirmar
    confirm_text = f"🚀 MEZCLAR ({len(selected)})" if selected else "Selecciona..."
    keyboard.append([InlineKeyboardButton(confirm_text, callback_data="multi_confirm")])
    keyboard.append([get_back_button()])
    
    msg = "🧬 **MEZCLADOR DE ESTILOS**\nToca para seleccionar/deseleccionar. Mínimo 2 recomendados."
    
    # Si venimos de un edit, editamos.
    try:
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    except:
        # A veces si el mensaje es igual da error, no importa
        pass
    return SELECT_CATALOG_MULTI

async def handle_multi_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'return_menu': return await cancel_create(update, context)
    
    data = query.data
    
    if data == "multi_confirm":
        selected = context.user_data.get('multi_selection', [])
        if not selected:
            await query.answer("⚠️ Selecciona al menos uno.", show_alert=True)
            return SELECT_CATALOG_MULTI
            
        # Procesar selección
        presets = load_presets()
        genres = list(presets.keys())
        final_urls = []
        names = []
        
        for idx in selected:
            if 0 <= idx < len(genres):
                genre = genres[idx]
                names.append(genre)
                # Añadimos TODAS las playlists de ese género
                for item in presets[genre]:
                    final_urls.append(item['url'])
        
        context.user_data['source_urls'] = final_urls
        context.user_data['source_tag'] = "Style Mashup"
        context.user_data['source_desc'] = f"Fusión de: {', '.join(names)}"
        
        # Mapeo URL -> Genero para balanceo
        url_genre_map = {}
        for idx in selected:
            if 0 <= idx < len(genres):
                g = genres[idx]
                for item in presets[g]:
                    url_genre_map[item['url']] = g
        context.user_data['url_genre_map'] = url_genre_map
        
        return await ask_algorithm(query, context)
        
    if data.startswith("multi_"):
        idx = int(data.replace("multi_", ""))
        selected = context.user_data.get('multi_selection', [])
        
        if idx in selected:
            selected.remove(idx)
        else:
            selected.append(idx)
            
        context.user_data['multi_selection'] = selected
        return await show_multi_selection_menu(query, context)
        
    return SELECT_CATALOG_MULTI

# --- HANDLERS PASO 2: FUENTES ---

async def handle_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    urls = text.split()
    valid_urls = [u for u in urls if "http" in u]
    
    if not valid_urls:
        await update.message.reply_text("❌ Sin links válidos.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
        return INPUT_LINKS
        
    context.user_data['source_urls'] = valid_urls
    context.user_data['source_tag'] = "Custom Links"
    context.user_data['source_desc'] = "Enlaces proporcionados por usuario"
    
    # Pasamos a algoritmo no con query sino prompt
    return await ask_algorithm_msg(update, context)

async def handle_catalog_single(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'return_menu': return await cancel_create(update, context)
    
    try:
        idx = int(query.data.replace("cat_", ""))
        presets = load_presets()
        genres = list(presets.keys())
        
        if 0 <= idx < len(genres):
            genre = genres[idx]
            context.user_data['source_urls'] = [item['url'] for item in presets[genre]]
            context.user_data['source_tag'] = genre
            context.user_data['source_desc'] = f"Catálogo: {genre}"
            
            # Map simple
            url_genre_map = {u: genre for u in context.user_data['source_urls']}
            context.user_data['url_genre_map'] = url_genre_map
            
            return await ask_algorithm(query, context)
    except: pass
    
    await query.edit_message_text("❌ Error.", reply_markup=InlineKeyboardMarkup([[get_back_button()]]))
    return ConversationHandler.END

# --- PASO 3: ALGORITMO ---

async def ask_algorithm(query, context):
    keyboard = [
        [InlineKeyboardButton("⚡ Max Energy (Gym)", callback_data='algo_energy')],
        [InlineKeyboardButton("🔥 Temas populares", callback_data='algo_party')],
        [InlineKeyboardButton("🔭 Discovery (Novedades)", callback_data='algo_discovery')],
        [InlineKeyboardButton("🎲 Random (Sorpréndeme)", callback_data='algo_random')],
        [get_back_button()]
    ]
    await query.edit_message_text("🧠 **PASO 2: Elige Algoritmo**", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_ALGORITHM

async def ask_algorithm_msg(update, context):
    keyboard = [
        [InlineKeyboardButton("⚡ Max Energy", callback_data='algo_energy')],
        [InlineKeyboardButton("🔥 Temas populares", callback_data='algo_party')],
        [InlineKeyboardButton("🔭 Discovery", callback_data='algo_discovery')],
        [InlineKeyboardButton("🎲 Random", callback_data='algo_random')],
        [get_back_button()]
    ]
    await update.message.reply_text("🧠 **PASO 2: Elige Algoritmo**", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_ALGORITHM

async def handle_algorithm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'return_menu': return await cancel_create(update, context)
    
    context.user_data['algorithm'] = query.data
    return await ask_duration(query, context)

# --- PASO 4: DURACIÓN ---

async def ask_duration(query, context):
    keyboard = [
        [InlineKeyboardButton("30 min", callback_data='dur_30'), InlineKeyboardButton("60 min", callback_data='dur_60')],
        [InlineKeyboardButton("90 min", callback_data='dur_90'), InlineKeyboardButton("120 min", callback_data='dur_120')],
        [get_back_button()]
    ]
    await query.edit_message_text("⏱️ **PASO 3: Duración Final**", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_DURATION

# --- PASO 5: PROCESO (REUTILIZAMOS LOGICA EXISTENTE) ---
# Copiaremos la funcion process_creation original pero adaptada minimamente si hace falta.
# La logica de shuffling y features es agnostica al origen, solo necesita 'source_urls' en user_data.

async def process_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'return_menu': return await cancel_create(update, context)

    mins = int(query.data.replace("dur_", ""))
    limit_ms = mins * 60 * 1000
    msg = await query.edit_message_text(f"⏳ **Generando sesión...**\n(Analizando audio features de múltiples fuentes)")

    # --- AQUI EMPIEZA LA LOGICA CORE DE GENERACION ---
    # Copiamos la lógica del archivo original para mantenerla consistente
    try:
        source_urls = context.user_data.get('source_urls', [])
        source_urls = [u for u in source_urls if u]
        algo = context.user_data.get('algorithm')
        now = datetime.now(timezone.utc)
        
        playlists_buckets = [] 
        real_playlist_names = []
        failed_stats = [] # To accumulate errors
        
        # PROCESO DE CARGA (Igual que antes)
        for url in source_urls:
            pid = extract_playlist_id(url)
            if not pid: continue
            
            # Solo buscar nombres si son links manuales para descripción
            if context.user_data.get('source_tag') == "Custom Links":
                try:
                    pl_meta = sp.playlist(pid, fields="name")
                    real_playlist_names.append(pl_meta['name'])
                except:
                    real_playlist_names.append("Priv")

            this_pl_tracks = []
            try:
                res = sp.playlist_tracks(pid, limit=100)
                items = res['items']
                if res['next']: 
                     res = sp.next(res) # Paginamos una vez mas para tener variedad
                     items.extend(res['items'])
                
                for item in items:
                    if item.get('track') and item['track'].get('id'):
                        this_pl_tracks.append(item)
            except Exception as e:
                failed_stats.append(f"{pid}: {str(e)[:50]}")
                continue
            
            if not this_pl_tracks: continue

            # Audio Features
            tids = list(set([t['track']['id'] for t in this_pl_tracks]))
            features_map = {}
            for i in range(0, len(tids), 100):
                try:
                    chunk = tids[i:i+100]
                    feats = sp.audio_features(chunk)
                    for f in feats:
                        if f: features_map[f['id']] = f
                except: pass

            # Puntuar
            scored_tracks = []
            random.shuffle(this_pl_tracks) 

            for item in this_pl_tracks:
                track = item['track']
                feat = features_map.get(track['id'])
                luck = random.randint(0, 100)
                score = 0
                
                if algo == 'algo_energy': 
                    energy_val = (feat['energy'] * 100) if feat else 50
                    score = (energy_val * 0.9) + (luck * 0.1)

                elif algo == 'algo_party': 
                    score = track['popularity'] 

                elif algo == 'algo_discovery':
                    try:
                        if item.get('added_at'):
                            added = datetime.fromisoformat(item['added_at'].replace('Z', '+00:00'))
                            days_old = (now - added).days
                            if days_old <= 30: 
                                score = track['popularity'] + 1 # Priorizamos popularidad dentro de los nuevos
                            else: 
                                score = 0 # Strict filtering: fuera
                        else: score = 0
                    except: score = 0

                elif algo == 'algo_random':
                    score = random.randint(1, 100) # Full random

                if score > 0:
                    scored_tracks.append({'uri': track['uri'], 'dur': track['duration_ms'], 'score': score})

            scored_tracks.sort(key=lambda x: x['score'], reverse=True)
            if scored_tracks:
                # Guardamos bucket con metadatos
                pl_genre = context.user_data.get('url_genre_map', {}).get(url, "Unknown")
                playlists_buckets.append({'genre': pl_genre, 'tracks': scored_tracks})

        if not playlists_buckets:
            error_details = "\n".join(failed_stats) if failed_stats else "No valid tracks"
            await msg.edit_text(f"❌ No se pudo extraer música válida.\n\nDetalles:\n{error_details}")
            return ConversationHandler.END

        # ROUND ROBIN MIX (POR GÉNERO)
        # 1. Agrupar buckets por género
        genre_pools = {}
        for bucket in playlists_buckets:
            g = bucket['genre']
            if g not in genre_pools: genre_pools[g] = []
            genre_pools[g].append(bucket['tracks'])
            
        genres_list = list(genre_pools.keys())
        random.shuffle(genres_list) # Mezclar orden de géneros inicial
        
        final_uris = []
        curr_ms = 0
        seen_uris = set()
        keep_going = True
        
        while keep_going:
            keep_going = False
            random.shuffle(genres_list) # Variar orden en cada ronda (opcional, pero da más sabor)
            
            for g in genres_list:
                # Obtenemos los buckets de este género
                buckets = genre_pools[g]
                if not buckets: continue # Si se acabaron todos los buckets de este genero
                
                # Cogemos del primer bucket disponible (Rotacion interna de playlists)
                # Para hacerlo simple: Cogemos del bucket 0, y luego rotamos ese bucket al final
                current_bucket_tracks = buckets[0]
                
                if current_bucket_tracks:
                    found_track = False
                    # Buscamos track no repetido en este bucket
                    while current_bucket_tracks:
                        track = current_bucket_tracks.pop(0) # El mejor puntudado
                        if track['uri'] not in seen_uris:
                            final_uris.append(track['uri'])
                            seen_uris.add(track['uri'])
                            curr_ms += track['dur']
                            found_track = True
                            keep_going = True # Seguimos vivos
                            break
                    
                    # Rotamos los buckets de este genero para que la proxima vez coja de la siguiente playlist
                    buckets.append(buckets.pop(0))
                else:
                    # Este bucket se vació, lo quitamos
                    buckets.pop(0)
                    if buckets: keep_going = True # Aun quedan otros buckets en este genero

                if curr_ms >= limit_ms: 
                    keep_going = False
                    break
            
            if curr_ms >= limit_ms: break

        if not final_uris:
            await msg.edit_text("⚠️ Fallo en generación.")
            return ConversationHandler.END

        # CREAR EN SPOTIFY
        user_id = sp.me()['id']
        unique = uuid.uuid4().hex[:4].upper()
        tg_user = update.effective_user
        user_ref = f"@{tg_user.username}" if tg_user.username else tg_user.first_name
        
        # Construir Nombre
        mode_names = {
            'algo_energy': 'Max Energy', 
            'algo_party': 'Temas Populares', 
            'algo_discovery': 'Discovery',
            'algo_random': 'Random Mode'
        }
        algo_str = mode_names.get(algo, 'Mix')
        tag = context.user_data.get('source_tag', 'Mix')
        
        pl_name = f"SpotiSession: {tag} ({algo_str}) [{unique}]"
        
        # Descripción inteligente
        desc_origin = context.user_data.get('source_desc', '')
        if tag == "Custom Links" and real_playlist_names:
            desc_origin = "Mezcla de: " + ", ".join(real_playlist_names)
            
        desc = f"Creada para {user_ref} | Modo: {algo_str} | {desc_origin}"
        if len(desc) > 300: desc = desc[:297] + "..."

        new_pl = sp.user_playlist_create(user=user_id, name=pl_name, public=True, description=desc)
        stats.count_new_playlist()
        
        # Añadir canciones
        for i in range(0, len(final_uris), 100):
            sp.playlist_add_items(new_pl['id'], final_uris[i:i+100])
        pl_url = new_pl['external_urls']['spotify']
        
        # PORTADA
        try:
            prefix_map = {
                'algo_energy': 'maxenergy', 
                'algo_party': 'partyhype', 
                'algo_discovery': 'discovery',
                'algo_random': 'spotimix' # Default fallback
            }
            img_prefix = prefix_map.get(algo, 'spotimix')
            images_dir = os.path.join(config.BASE_DIR, 'images', 'pool')
            candidates = [f for f in os.listdir(images_dir) if f.startswith(img_prefix) and f.endswith(".jpg")]
            if candidates:
                sel_img = random.choice(candidates)
                with open(os.path.join(images_dir, sel_img), "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                sp.playlist_upload_cover_image(new_pl['id'], b64)
        except Exception: pass

        # QR CODE
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(pl_url)
        qr.make(fit=True)
        bio = BytesIO()
        qr.make_image().save(bio, 'PNG')
        bio.seek(0)
        
        await msg.delete()
        caption = (
            f"✅ **{pl_name}**\n\n"
            f"📝 {desc_origin}\n"
            f"⏱ **Duración:** {int(curr_ms/60000)} min\n"
            f"🔗 {pl_url}\n\n"
            "♻️ **Caduca en 3 meses.** (Seguir para guardar)\n"
        )
        
        await update.effective_message.reply_photo(photo=bio, caption=caption, reply_markup=InlineKeyboardMarkup([[get_back_button()]]))

    except Exception as e:
        await query.message.reply_text(f"❌ Error al crear playlist: {e}")
        return ConversationHandler.END
