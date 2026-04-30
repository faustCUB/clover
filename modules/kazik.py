from telethon.tl.types import InputMediaDice
from modules.base import BaseModule
from utils import logger


async def _rigged_game(event):
    cmd = event.raw_text.strip().split(maxsplit=1)
    game = cmd[0][1:]
    target_arg = cmd[1].lower() if len(cmd) > 1 else None

    best_values = {"darts": 6, "footb": 4, "basket": 4, "boul": 6}
    emojis = {"darts": "🎯", "footb": "⚽", "basket": "🏀", "boul": "🎳", "slots": "🎰"}
    slot_targets = {"777": [64], "bar": [1], "лимон": [43], "виноград": [22]}

    emoji = emojis.get(game)
    if not emoji:
        return

    if game == "slots" and target_arg:
        if target_arg in slot_targets:
            target_values = slot_targets[target_arg]
        else:
            await event.edit(f"❌ Неизвестная цель. Доступны: `{', '.join(slot_targets.keys())}`")
            return
    else:
        target_values = [best_values.get(game)]

    await event.delete()
    attempts = 0
    while True:
        attempts += 1
        try:
            msg = await event.client.send_message(event.chat_id, file=InputMediaDice(emoji))
            value = msg.media.value
            
            if value in target_values:
                logger.success(f"{game.capitalize()} > Успех! Выпало {logger.accent(value)} за {attempts} попыток")
                break

            await msg.delete()
        except Exception as e:
            logger.error(f"Ошибка в игре {game}: {e}")
            break


async def _rigged_dice(event):
    logger.info(f"Команда {logger.accent('.dice')} вызвана")
    args = event.raw_text.strip().split(maxsplit=1)
    
    if len(args) < 2:
        await event.edit("❌ Укажи число от 1 до 6")
        return

    try:
        target = int(args[1])
        if not 1 <= target <= 6:
            await event.edit("❌ Число должно быть от 1 до 6")
            return

        await event.delete()
        attempts = 0
        while True:
            attempts += 1
            msg = await event.client.send_message(event.chat_id, file=InputMediaDice("🎲"))
            value = msg.media.value

            if value == target:
                logger.success(f"Кубик → Успех! Выпало {logger.accent(value)} за {attempts} попыток")
                break

            await msg.delete()
    except Exception as e:
        logger.error(f"Ошибка в кубике: {e}")


def setup() -> BaseModule:
    return BaseModule(
        name="KAZIK",
        version="1.0",
        description="Мини-игры (спам до победы)",
        commands={
            "darts": _rigged_game,
            "footb": _rigged_game,
            "basket": _rigged_game,
            "boul": _rigged_game,
            "slots": _rigged_game,
            "dice": _rigged_dice,
        },
        examples=[
            "`.darts` – попасть дротиком",
            "`.footb` – забить гол",
            "`.basket` – попасть в кольцо",
            "`.boul` – выбить страйк",
            "`.slots 777` – крутить до трех семерок",
            "`.slots bar` – крутить до BAR",
            "`.slots лимон` – крутить до лимонов",
            "`.slots виноград` – крутить до виноградов",
            "`.dice 6` – выкинуть шестерку на кубике (прикинь, цифру менять можно)"
        ],
    )
