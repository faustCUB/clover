from modules.base import BaseModule


async def _cp(event):
    args = event.message.text.split(maxsplit=1)
    if len(args) < 2:
        await event.edit("Укажи число, например: `.cp 123`")
        return

    base = args[1].strip()
    await event.delete()

    for d in range(10):
        await event.respond(f"{base}{d}")


def setup() -> BaseModule:
    return BaseModule(
        name="CashPoint(Не спрашивайте для чего это и как это попало в релиз)",
        version="1.0.1",
        description="Перебор четвёртой цифры",
        commands={
            "cp": _cp,
        },
        examples=["`.cp 123`"],
    )
