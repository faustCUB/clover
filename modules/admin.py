import asyncio

from telethon import functions
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import (
    ChatBannedRights,
    ChannelParticipantsBanned,
    InputPeerUser,
)
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError, FloodWaitError

from modules.base import BaseModule
from utils import logger


async def _list(event):
    await event.delete()
    try:
        chat = await event.get_chat()
        muted = []
        banned = []

        async for user in event.client.iter_participants(chat, filter=ChannelParticipantsBanned):
            try:
                p = await event.client(functions.channels.GetParticipantRequest(chat, user.id))
                rights = p.participant.banned_rights
                if isinstance(rights, ChatBannedRights):
                    label = f"{user.id} — {user.first_name or 'NoName'}"
                    if rights.send_messages:
                        muted.append(label)
                    else:
                        banned.append(label)
            except Exception:
                continue

        text = "🍀 **В муте:**\n"
        text += "\n".join(muted) if muted else "Нет"
        text += "\n\n**Забанены:**\n"
        text += "\n".join(banned) if banned else "Нет"
        await event.respond(text)

    except Exception as e:
        logger.error(f"Ошибка в команде list: {e}")
        await event.respond("❌ Не удалось получить список. Возможно, бот не является администратором.")


async def _mute(event):
    await event.delete()
    user, chat = await _resolve(event)
    if not user:
        return
    try:
        await event.client(EditBannedRequest(
            channel=chat,
            participant=await _peer(event, user.id),
            banned_rights=ChatBannedRights(send_messages=True, until_date=None),
        ))
        await event.respond(f"🍀 Замучен: {_label(user)}")
        logger.success(f"Замучен пользователь {user.id}")
    except ChatAdminRequiredError:
        await event.respond("❌ Ошибка: У меня нет прав администратора в этом чате.")
    except UserNotParticipantError:
        await event.respond("❌ Ошибка: Пользователь не является участником чата.")
    except Exception as e:
        logger.error(f"Ошибка в команде mute: {e}")
        await event.respond(f"❌ Не удалось замутить пользователя.\nПричина: {str(e)[:150]}")


async def _unmute(event):
    await event.delete()
    user, chat = await _resolve(event)
    if not user:
        return
    try:
        await event.client(EditBannedRequest(
            channel=chat,
            participant=await _peer(event, user.id),
            banned_rights=ChatBannedRights(send_messages=False, until_date=None),
        ))
        await event.respond(f"🍀 Размучен: {_label(user)}")
        logger.success(f"Размучен пользователь {user.id}")
    except ChatAdminRequiredError:
        await event.respond("❌ Ошибка: У меня нет прав администратора.")
    except Exception as e:
        logger.error(f"Ошибка в команде unmute: {e}")
        await event.respond(f"❌ Не удалось размутить.\nПричина: {str(e)[:150]}")


async def _ban(event):
    await event.delete()
    user, chat = await _resolve(event)
    if not user:
        return
    try:
        await event.client(EditBannedRequest(
            channel=chat,
            participant=await _peer(event, user.id),
            banned_rights=ChatBannedRights(view_messages=True, until_date=None),
        ))
        await event.respond(f"🍀 Забанен: {_label(user)}")
        logger.success(f"Забанен пользователь {user.id}")
    except ChatAdminRequiredError:
        await event.respond("❌ Ошибка: У меня нет прав администратора.")
    except UserNotParticipantError:
        await event.respond("❌ Ошибка: Пользователь не является участником чата.")
    except Exception as e:
        logger.error(f"Ошибка в команде ban: {e}")
        await event.respond(f"❌ Не удалось забанить пользователя.\nПричина: {str(e)[:150]}")


async def _unban(event):
    await event.delete()
    user, chat = await _resolve(event)
    if not user:
        return
    try:
        await event.client(EditBannedRequest(
            channel=chat,
            participant=await _peer(event, user.id),
            banned_rights=ChatBannedRights(view_messages=False, until_date=None),
        ))
        await event.respond(f"🍀 Разбанен: {_label(user)}")
        logger.success(f"Разбанен пользователь {user.id}")
    except ChatAdminRequiredError:
        await event.respond("❌ Ошибка: У меня нет прав администратора.")
    except Exception as e:
        logger.error(f"Ошибка в команде unban: {e}")
        await event.respond(f"❌ Не удалось разбанить.\nПричина: {str(e)[:150]}")


async def _kick(event):
    await event.delete()
    user, chat = await _resolve(event)
    if not user:
        return
    try:
        await event.client.kick_participant(chat, await _peer(event, user.id))
        await event.respond(f"🍀 Кикнут: {_label(user)}")
        logger.success(f"Кикнут пользователь {user.id}")
    except ChatAdminRequiredError:
        await event.respond("❌ Ошибка: У меня нет прав администратора.")
    except UserNotParticipantError:
        await event.respond("❌ Ошибка: Пользователь не является участником чата.")
    except Exception as e:
        logger.error(f"Ошибка в команде kick: {e}")
        await event.respond(f"❌ Не удалось кикнуть пользователя.\nПричина: {str(e)[:150]}")


async def _dmu(event):
    await event.delete()
    user, chat = await _resolve(event)
    if not user:
        return
    deleted = 0
    try:
        async for msg in event.client.iter_messages(chat, from_user=user.id):
            try:
                await msg.delete()
                deleted += 1
                await asyncio.sleep(0.01)
            except Exception:
                continue
        await event.respond(f"🍀 Удалено сообщений от {_label(user)}: {deleted}")
        logger.success(f"Удалено {deleted} сообщений от пользователя {user.id}")
    except Exception as e:
        logger.error(f"Ошибка в команде dmu: {e}")
        await event.respond(f"❌ Не удалось удалить сообщения.\nПричина: {str(e)[:150]}")


async def _delu(event):
    await event.delete()
    chat = await event.get_chat()
    removed = 0
    try:
        async for user in event.client.iter_participants(chat):
            if not getattr(user, "deleted", False):
                continue
            try:
                await event.client.kick_participant(chat, await _peer(event, user.id))
                removed += 1
                await asyncio.sleep(0.1)
            except Exception:
                continue
        await event.respond(f"🍀 Удалено удалённых аккаунтов: {removed}")
        logger.success(f"Удалено {removed} удалённых аккаунтов")
    except ChatAdminRequiredError:
        await event.respond("❌ Ошибка: У меня нет прав администратора.")
    except Exception as e:
        logger.error(f"Ошибка в команде delu: {e}")
        await event.respond(f"❌ Не удалось выполнить delu.\nПричина: {str(e)[:150]}")


async def _kill(event):
    await event.delete()
    chat = await event.get_chat()
    me = (await event.client.get_me()).id
    kicked = 0
    try:
        async for user in event.client.iter_participants(chat):
            if getattr(user, "bot", False) or user.id == me:
                continue
            try:
                await event.client.kick_participant(chat, await _peer(event, user.id))
                kicked += 1
                await asyncio.sleep(0.1)
            except Exception:
                continue
        await event.respond(f"🍀 Кикнуто участников: {kicked}")
        logger.success(f"Кикнуто {kicked} участников")
    except ChatAdminRequiredError:
        await event.respond("❌ Ошибка: У меня нет прав администратора.")
    except Exception as e:
        logger.error(f"Ошибка в команде kill: {e}")
        await event.respond(f"❌ Не удалось выполнить kill.\nПричина: {str(e)[:150]}")


async def _banan(event):
    await event.delete()
    chat = await event.get_chat()
    me = (await event.client.get_me()).id
    banned = 0
    try:
        async for user in event.client.iter_participants(chat):
            if getattr(user, "bot", False) or user.id == me:
                continue
            try:
                await event.client(EditBannedRequest(
                    channel=chat,
                    participant=await _peer(event, user.id),
                    banned_rights=ChatBannedRights(view_messages=True, until_date=None),
                ))
                banned += 1
                await asyncio.sleep(0.5)
            except Exception:
                continue
        await event.respond(f"🍀 Забанено участников: {banned}")
        logger.success(f"Забанено {banned} участников")
    except ChatAdminRequiredError:
        await event.respond("❌ Ошибка: У меня нет прав администратора.")
    except Exception as e:
        logger.error(f"Ошибка в команде banan: {e}")
        await event.respond(f"❌ Не удалось выполнить banan.\nПричина: {str(e)[:150]}")


async def _resolve(event):
    chat = await event.get_chat()
    text = event.raw_text.strip()
    parts = text.split(maxsplit=1)
    uid = parts[1] if len(parts) > 1 else None

    if uid:
        try:
            user = await event.client.get_entity(int(uid))
            return user, chat
        except Exception:
            await event.respond("❌ Пользователь с таким ID не найден.")
            return None, None

    if event.is_reply:
        reply = await event.get_reply_message()
        user = await reply.get_sender()
        return user, chat

    await event.respond("❌ Ответьте на сообщение или укажите ID пользователя.")
    return None, None


async def _peer(event, user_id: int):
    user = await event.client.get_entity(user_id)
    return InputPeerUser(user.id, user.access_hash)


def _label(user):
    name = getattr(user, "first_name", None) or "NoName"
    return f"{name} ({user.id})"


def setup() -> BaseModule:
    return BaseModule(
        name="Admin",
        version="1.0",
        description="Модерация и управление чатом",
        commands={
            "list": _list,
            "mute": _mute,
            "unmute": _unmute,
            "ban": _ban,
            "unban": _unban,
            "kick": _kick,
            "dmu": _dmu,
            "delu": _delu,
            "kill": _kill,
            "banan": _banan,
        },
        examples=[
            "`.list` — показать список в муте и бане",
            "`.mute` — замутить по реплаю",
            "`.mute 123456789` — замутить по ID",
            "`.unmute` — размутить (реплай / ID)",
            "`.ban` — забанить (реплай / ID)",
            "`.unban` — разбанить (реплай / ID)",
            "`.kick` — кикнуть (реплай / ID)",
            "`.dmu` — удалить все сообщения пользователя (реплай или ID)",
            "`.delu` — кикнуть все удалённые аккаунты",
            "`.kill` — кикнуть всех участников (кроме себя и ботов)",
            "`.banan` — забанить всех участников (кроме себя и ботов)"
        ],
    )