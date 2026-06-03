from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.models.business import Business


def subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Pro — 29€/mes", callback_data="subscribe_pro")],
        [InlineKeyboardButton("Multi — 59€/mes", callback_data="subscribe_multi")],
    ])


def pause_keyboard(businesses: list[Business]) -> InlineKeyboardMarkup:
    rows = []
    for b in businesses:
        label = f"▶ Reanudar {b.name}" if b.is_paused else f"⏸ Pausar {b.name}"
        action = "resume" if b.is_paused else "pause"
        rows.append([InlineKeyboardButton(label, callback_data=f"{action}_{b.id}")])
    return InlineKeyboardMarkup(rows)


def business_list_keyboard(businesses: list[Business]) -> InlineKeyboardMarkup:
    rows = []
    for b in businesses:
        status = "⏸" if b.is_paused else "▶"
        rows.append([InlineKeyboardButton(f"{status} {b.name}", callback_data=f"info_{b.id}")])
    return InlineKeyboardMarkup(rows)
