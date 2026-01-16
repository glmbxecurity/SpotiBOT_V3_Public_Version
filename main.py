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
import admin_panel

# MÓDULOS
from comandos_basicos import start, help_command, info_command, view_catalog

from funcion_create import (
    start_create, handle_mode_selection, handle_links, handle_catalog_single,
    handle_multi_selection, ask_algorithm, handle_algorithm, ask_duration, 
    process_creation, cancel_create,
    SELECT_MODE, INPUT_LINKS, SELECT_CATALOG_SINGLE, SELECT_CATALOG_MULTI, 
    SELECT_ALGORITHM, SELECT_DURATION
)
from funcion_scan import (
    start_scan, receive_link, process_scan_result, cancel_scan, 
    INPUT_SCAN_LINK, SELECT_LIMIT
)
from funcion_scan import (
    start_scan, receive_link, process_scan_result, cancel_scan, 
    INPUT_SCAN_LINK, SELECT_LIMIT
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
async def quiet_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return ConversationHandler.END

if __name__ == '__main__':
    print("🔥 SpotiBOT v3.5 ONLINE")
    
    application = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    
    # 1. HANDLERS GLOBALES
    application.add_handler(CallbackQueryHandler(return_to_menu, pattern='^return_menu$'))
    application.add_handler(CallbackQueryHandler(view_catalog, pattern='^view_catalog$'))

    # 2. COMANDOS BÁSICOS
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('info', info_command))
    
    # 3. CREATE HANDLER (ACTUALIZADO - FLUJO NUEVO)
    # Estados: SELECT_MODE -> [INPUT_LINKS | SELECT_CATALOG_SINGLE | SELECT_CATALOG_MULTI] -> SELECT_ALGORITHM -> SELECT_DURATION
    create_handler = ConversationHandler(
        entry_points=[CommandHandler('create', create_entry_point)],
        states={
            # Paso 1: Modo
            SELECT_MODE: [
                CallbackQueryHandler(handle_mode_selection, pattern='^mode_'), 
                CallbackQueryHandler(cancel_create, pattern='^return_menu$')
            ],
            # Paso 2: Fuentes
            INPUT_LINKS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_links), 
                CallbackQueryHandler(cancel_create, pattern='^return_menu$')
            ],
            SELECT_CATALOG_SINGLE: [
                CallbackQueryHandler(handle_catalog_single, pattern='^cat_'), 
                CallbackQueryHandler(cancel_create, pattern='^return_menu$')
            ],
            SELECT_CATALOG_MULTI: [
                CallbackQueryHandler(handle_multi_selection, pattern='^multi_'), 
                CallbackQueryHandler(cancel_create, pattern='^return_menu$')
            ],
            # Paso 3: Algoritmo
            SELECT_ALGORITHM: [
                CallbackQueryHandler(handle_algorithm, pattern='^algo_'), 
                CallbackQueryHandler(cancel_create, pattern='^return_menu$')
            ],
            # Paso 4: Duración
            SELECT_DURATION: [
                CallbackQueryHandler(process_creation, pattern='^dur_'), 
                CallbackQueryHandler(cancel_create, pattern='^return_menu$')
            ],
        },
        fallbacks=[
            CommandHandler('cancel', cancel_create), 
            CallbackQueryHandler(cancel_create, pattern='^return_menu$'),
            # Interrupciones:
            CommandHandler('scan', quiet_cancel),
            CommandHandler('admin', quiet_cancel)
        ],
        per_message=False
    )
    application.add_handler(create_handler, group=1)

    # 4. SCAN HANDLER (LEGACY)
    scan_handler = ConversationHandler(
        entry_points=[CommandHandler('scan', scan_entry_point)],
        states={
            INPUT_SCAN_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_link), CallbackQueryHandler(cancel_scan, pattern='^return_menu$')],
            SELECT_LIMIT: [CallbackQueryHandler(process_scan_result, pattern='^limit_'), CallbackQueryHandler(cancel_scan, pattern='^return_menu$')]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_scan), 
            CallbackQueryHandler(cancel_scan, pattern='^return_menu$'),
            CommandHandler('create', quiet_cancel),
            CommandHandler('start', quiet_cancel)
        ],
        per_message=False
    )
    application.add_handler(scan_handler, group=2)


    
    # 6. ADMIN HANDLER (NUEVO)
    admin_handler = ConversationHandler(
        entry_points=[
            CommandHandler('admin', admin_panel.admin_entry_point),
            CallbackQueryHandler(admin_panel.admin_entry_point, pattern='^admin_entry$')
        ],
        states={
            admin_panel.ADMIN_MENU: [
                CallbackQueryHandler(admin_panel.admin_yaml_menu, pattern='^admin_yaml$'),
                CallbackQueryHandler(admin_panel.admin_run_cleaner, pattern='^admin_clean$'),
                CallbackQueryHandler(admin_panel.admin_diagnostics, pattern='^admin_diag$'),
                CallbackQueryHandler(admin_panel.admin_restart_service, pattern='^admin_restart$'),
                CallbackQueryHandler(admin_panel.admin_auth_start, pattern='^admin_auth$'),
                CallbackQueryHandler(admin_panel.admin_exit, pattern='^admin_exit$'),
                CallbackQueryHandler(admin_panel.show_admin_menu, pattern='^return_admin$')
            ],
            # YAML SUB-FLOW
            admin_panel.EDIT_YAML_MENU: [
                CallbackQueryHandler(admin_panel.yaml_add_start, pattern='^yaml_add$'),
                CallbackQueryHandler(admin_panel.yaml_remove_start, pattern='^yaml_remove$'),
                CallbackQueryHandler(admin_panel.show_admin_menu, pattern='^return_admin$')
            ],
            admin_panel.ADD_PLAYLIST_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel.yaml_add_name)],
            admin_panel.ADD_PLAYLIST_GENRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel.yaml_add_genre)],
            admin_panel.ADD_PLAYLIST_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel.yaml_add_url)],
            admin_panel.REMOVE_PLAYLIST_USELECT: [
                CallbackQueryHandler(admin_panel.yaml_remove_confirm, pattern='^del_'),
                CallbackQueryHandler(admin_panel.show_admin_menu, pattern='^return_admin$')
            ],
            # AUTH SUB-FLOW
            admin_panel.AUTH_INPUT_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_panel.admin_auth_complete)]
        },
        fallbacks=[CommandHandler('cancel', admin_panel.admin_exit), CallbackQueryHandler(admin_panel.admin_exit, pattern='^admin_exit$')],
        per_message=False
    )
    application.add_handler(admin_handler, group=99) 
    
    application.run_polling()
