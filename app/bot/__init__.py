from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers.activar import activar
from app.bot.handlers.agregar import (
    ASKING_SEARCH,
    CONFIRMING_OWNERSHIP,
    SELECTING_PLACE,
    agregar,
    cancel_agregar,
    handle_ownership_confirm,
    handle_place_select,
    handle_search,
)
from app.bot.handlers.config import config_handler, handle_config_callback
from app.bot.handlers.estado import estado
from app.bot.handlers.pausa import handle_pause_callback, pausa, reanudar
from app.bot.handlers.reenviar import reenviar
from app.bot.handlers.resenas import handle_resenas_callback, resenas
from app.bot.handlers.responder import handle_responder_callback, responder
from app.bot.handlers.start import handle_start_callback, start
from app.bot.handlers.suscribir import handle_subscribe_callback, suscribir

_application: Application | None = None


def get_application() -> Application:
    assert _application is not None, "Bot application not initialized"
    return _application


def create_application(token: str) -> Application:
    global _application

    _application = Application.builder().token(token).build()

    agregar_conv = ConversationHandler(
        entry_points=[CommandHandler("agregar", agregar)],
        states={
            ASKING_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search)],
            SELECTING_PLACE: [CallbackQueryHandler(handle_place_select, pattern="^place_")],
            CONFIRMING_OWNERSHIP: [CallbackQueryHandler(handle_ownership_confirm, pattern="^owner_")],
        },
        fallbacks=[CommandHandler("cancelar", cancel_agregar)],
    )

    _application.add_handler(CommandHandler("start", start))
    _application.add_handler(CommandHandler("activar", activar))
    _application.add_handler(CommandHandler("reenviar", reenviar))
    _application.add_handler(CommandHandler("suscribir", suscribir))
    _application.add_handler(CommandHandler("config", config_handler))
    _application.add_handler(CommandHandler("pausa", pausa))
    _application.add_handler(CommandHandler("reanudar", reanudar))
    _application.add_handler(CommandHandler("estado", estado))
    _application.add_handler(CommandHandler("resenas", resenas))
    _application.add_handler(CommandHandler("responder", responder))
    _application.add_handler(agregar_conv)
    _application.add_handler(CallbackQueryHandler(handle_subscribe_callback, pattern="^subscribe_"))
    _application.add_handler(CallbackQueryHandler(handle_pause_callback, pattern="^(pause|resume)_"))
    _application.add_handler(CallbackQueryHandler(handle_resenas_callback, pattern="^resenas_"))
    _application.add_handler(CallbackQueryHandler(handle_responder_callback, pattern="^resp_"))
    _application.add_handler(CallbackQueryHandler(handle_config_callback, pattern="^cfg_"))
    _application.add_handler(CallbackQueryHandler(handle_start_callback, pattern="^signup_"))

    return _application
