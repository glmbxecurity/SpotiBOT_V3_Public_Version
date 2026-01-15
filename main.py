import logging
import time
import warnings
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, 
    ConversationHandler, CallbackQueryHandler, MessageHandler, filters
)
from telegram.warnings import PTBUserWarning

# SILENCIAR WARNINGS
warnings.filterwarnings("ignore", category=PTBUserWarning)

# IMPORTS LOCALES
import config
import stats

# MÓDULOS
from comandos_basicos import start, help_command, info_command, check_catalog_health

from funcion_create import (
    start_create, handle_source_selection, handle_preset_selection, 
    handle_user_links, save_algorithm, process_creation, cancel_create,
    ALGORITHM, SOURCE, SELECT_PRESET, INPUT_LINK, DURATION 
)
from funcion_scan import (
    start_scan, receive_link, process_scan_result, cancel_scan, 
    INPUT_SCAN_LINK, SELECT_LIMIT
)
from funcion_mix import (
    start_mix, process_mix, cancel_mix, INPUT_MIX_LINKS
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

user_cooldowns = {}

async def check_rate_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    current_time = time.time()
    last_time = user_cooldowns.get(user_id, 0)
    
    if current_time - last_time < config.COOLDOWN_SECONDS:
        remaining = int(config.COOLDOWN_SECONDS - (current_time - last_time))
        msg = await update.effective_message.reply_text(f"⚡ **Cargando pilas...** Espera {remaining}s.")
        return False
    
    user_cooldowns[user_id] = current_time
    stats.track_user(user_id)
    return True

# WRAPPERS
async def create_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_rate_limit(update, context): return await start_create(update, context)
    return ConversationHandler.END

async def scan_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_rate_limit(update, context): return await start_scan(update, context)
    return ConversationHandler.END

async def mix_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_rate_limit(update, context): return await start_mix(update, context)
    return ConversationHandler.END

# --- LÓGICA DEL BOTÓN MENÚ PRINCIPAL ---
# --- LÓGICA DEL BOTÓN MENÚ PRINCIPAL ---
async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        try: await query.delete_message()
        except: pass
    await start(update, context)
    return ConversationHandler.END

# --- INT ERRORES SILENCIOSOS (CROSS-CANCELLATION) ---
# Esta función simplemente termina la conversación actual sin decir nada.
# Se usa cuando otro comando "roba" el foco.
async def quiet_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

if __name__ == '__main__':
    print("🔥 SpotiBOT v1.0 ONLINE")
    
    application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    
    # 1. HANDLERS GLOBALES
    application.add_handler(CallbackQueryHandler(return_to_menu, pattern='^return_menu$'))
    application.add_handler(CallbackQueryHandler(check_catalog_health, pattern='^check_catalog$'))

    # 2. COMANDOS BÁSICOS
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('info', info_command))
    
    # 3. CREATE (GROUP 1)
    create_handler = ConversationHandler(
        entry_points=[CommandHandler('create', create_entry_point)],
        states={
            ALGORITHM: [CallbackQueryHandler(save_algorithm, pattern='^algo_'), CallbackQueryHandler(cancel_create, pattern='^return_menu$')],
            SOURCE: [CallbackQueryHandler(handle_source_selection, pattern='^src_'), CallbackQueryHandler(cancel_create, pattern='^return_menu$')],
            SELECT_PRESET: [CallbackQueryHandler(handle_preset_selection, pattern='^genre_'), CallbackQueryHandler(cancel_create, pattern='^return_menu$')],
            INPUT_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_links), CallbackQueryHandler(cancel_create, pattern='^return_menu$')],
            DURATION: [CallbackQueryHandler(process_creation, pattern='^dur_'), CallbackQueryHandler(cancel_create, pattern='^return_menu$')],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_create), 
            CallbackQueryHandler(cancel_create, pattern='^return_menu$'),
            # Interrupciones de otros comandos:
            CommandHandler('scan', quiet_cancel),
            CommandHandler('mix', quiet_cancel),
            CommandHandler('info', quiet_cancel),
            CommandHandler('help', quiet_cancel),
            CommandHandler('start', quiet_cancel)
        ],
        per_message=False
    )
    application.add_handler(create_handler, group=1)

    # 4. SCAN (GROUP 2)
    scan_handler = ConversationHandler(
        entry_points=[CommandHandler('scan', scan_entry_point)],
        states={
            INPUT_SCAN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link), CallbackQueryHandler(cancel_scan, pattern='^return_menu$')],
            SELECT_LIMIT: [CallbackQueryHandler(process_scan_result, pattern='^limit_'), CallbackQueryHandler(cancel_scan, pattern='^return_menu$')]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_scan), 
            CallbackQueryHandler(cancel_scan, pattern='^return_menu$'),
            # Interrupciones:
            CommandHandler('create', quiet_cancel),
            CommandHandler('mix', quiet_cancel),
            CommandHandler('info', quiet_cancel),
            CommandHandler('help', quiet_cancel),
            CommandHandler('start', quiet_cancel)
        ],
        per_message=False
    )
    application.add_handler(scan_handler, group=2)

    # 5. MIX (GROUP 3)
    mix_handler = ConversationHandler(
        entry_points=[CommandHandler('mix', mix_entry_point)],
        states={
            INPUT_MIX_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_mix), CallbackQueryHandler(cancel_mix, pattern='^return_menu$')]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_mix), 
            CallbackQueryHandler(cancel_mix, pattern='^return_menu$'),
            # Interrupciones:
            CommandHandler('create', quiet_cancel),
            CommandHandler('scan', quiet_cancel),
            CommandHandler('info', quiet_cancel),
            CommandHandler('help', quiet_cancel),
            CommandHandler('start', quiet_cancel)
        ],
        per_message=False
    )
    application.add_handler(mix_handler, group=3)
    
    application.run_polling()
