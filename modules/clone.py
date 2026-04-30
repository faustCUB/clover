import asyncio
import json
import mimetypes
import os

from telethon import functions
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest, GetUserPhotosRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import InputPhoto

from modules.base import BaseModule
from utils import logger


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
CLONE_DIR = os.path.join(MODULE_DIR, "clone_me")


async def _clone(event):
    await event.delete()

    raw = event.raw_text.strip().split(maxsplit=1)
    username = raw[1] if len(raw) > 1 else None

    user = None
    if username:
        try:
            user = await event.client.get_entity(username)
        except Exception as e:
            await event.respond(f"❌ Пользователь не найден: {str(e)}")
            return
    elif event.is_reply:
        reply = await event.get_reply_message()
        user = await reply.get_sender()
    else:
        await event.respond("❌ Укажите @username или ответьте на сообщение пользователя")
        return

    try:
        full = await event.client(GetFullUserRequest(user.id))

        name = (user.first_name or "")[:64] or "."
        last = (user.last_name or "")[:64]
        about = (full.full_user.about or "")[:70]

        await event.client(functions.account.UpdateProfileRequest(
            first_name=name,
            last_name=last,
            about=about
        ))

        photos = await event.client.get_profile_photos(user.id, limit=10)
        uploaded = 0

        for i, photo in enumerate(reversed(photos)):
            try:
                file_path = f"profile_clone_{i}"
                downloaded_file = await _download_media_with_extension(event.client, photo, file_path)

                if downloaded_file and os.path.exists(downloaded_file):
                    success = await _upload_profile_media(event.client, downloaded_file)
                    if success:
                        uploaded += 1
                    if os.path.exists(downloaded_file):
                        os.remove(downloaded_file)
                    await asyncio.sleep(1.5)

            except Exception as e:
                logger.error(f"Ошибка обработки аватарки {i}: {e}")
                continue

        await event.respond(f"🍀 Профиль успешно скопирован. Аватарок загружено: {uploaded}")
        logger.success(f"Профиль скопирован ({uploaded} аватарок)")

    except Exception as e:
        logger.error(f"Ошибка клонирования: {e}")
        await event.respond(f"❌ Ошибка клонирования профиля.\nПричина: {str(e)[:200]}")


async def _cloneme(event):
    await event.delete()

    os.makedirs(CLONE_DIR, exist_ok=True)

    try:
        me = await event.client.get_me()
        full = await event.client(GetFullUserRequest(me.id))

        profile_data = {
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "username": me.username or "",
            "about": full.full_user.about or "",
            "user_id": me.id
        }

        with open(os.path.join(CLONE_DIR, "profile.json"), "w", encoding="utf-8") as f:
            json.dump(profile_data, f, ensure_ascii=False, indent=2)

        photos = await event.client.get_profile_photos(me.id, limit=5)
        saved_photos = 0

        for i, photo in enumerate(photos):
            try:
                file_ext = ".mp4" if getattr(photo, 'video_sizes', None) else ".jpg"
                file_path = os.path.join(CLONE_DIR, f"avatar_{i}{file_ext}")

                downloaded_file = await _download_media_with_extension(event.client, photo, file_path)
                if downloaded_file and os.path.exists(downloaded_file):
                    saved_photos += 1

            except Exception as e:
                logger.error(f"Ошибка сохранения аватарки {i}: {e}")
                continue

        await event.respond(f"🍀 Текущий профиль сохранён в папку clone_me. Аватарок: {saved_photos}")
        logger.success(f"Профиль сохранён ({saved_photos} аватарок)")

    except Exception as e:
        logger.error(f"Ошибка сохранения профиля: {e}")
        await event.respond(f"❌ Не удалось сохранить профиль.\nПричина: {str(e)[:200]}")


async def _setme(event):
    await event.delete()

    if not os.path.exists(CLONE_DIR):
        await event.respond("❌ Папка clone_me не найдена рядом с модулем")
        return

    json_path = os.path.join(CLONE_DIR, "profile.json")
    if not os.path.exists(json_path):
        await event.respond("❌ Файл profile.json не найден в папке clone_me")
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            profile_data = json.load(f)

        await event.client(functions.account.UpdateProfileRequest(
            first_name=profile_data.get("first_name", ""),
            last_name=profile_data.get("last_name", ""),
            about=profile_data.get("about", "")
        ))

        current_photos = await event.client(GetUserPhotosRequest(
            user_id="me", offset=0, max_id=0, limit=100
        ))

        if current_photos.photos:
            input_photos = [
                InputPhoto(id=p.id, access_hash=p.access_hash, file_reference=p.file_reference)
                for p in current_photos.photos
            ]
            await event.client(DeletePhotosRequest(id=input_photos))
            logger.info(f"Удалено {len(input_photos)} аватарок")

        uploaded_photos = 0
        avatar_files = sorted([
            f for f in os.listdir(CLONE_DIR)
            if f.startswith("avatar_") and f.endswith((".jpg", ".mp4"))
        ])

        for file_name in avatar_files:
            try:
                file_path = os.path.join(CLONE_DIR, file_name)
                success = await _upload_profile_media(event.client, file_path)
                if success:
                    uploaded_photos += 1
                await asyncio.sleep(1.5)
            except Exception as e:
                logger.error(f"Ошибка загрузки {file_name}: {e}")
                continue

        await event.respond(f"🍀 Профиль успешно восстановлен. Аватарок: {uploaded_photos}")
        logger.success(f"Профиль восстановлен ({uploaded_photos} аватарок)")

    except Exception as e:
        logger.error(f"Ошибка восстановления профиля: {e}")
        await event.respond(f"❌ Не удалось восстановить профиль.\nПричина: {str(e)[:200]}")


async def _download_media_with_extension(client, media, file_path):
    try:
        return await client.download_media(media, file=file_path)
    except Exception as e:
        logger.error(f"Ошибка скачивания медиа: {e}")
        return None


async def _upload_profile_media(client, file_path):
    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type and mime_type.startswith('video/'):
            await client(UploadProfilePhotoRequest(
                video=await client.upload_file(file_path)
            ))
        else:
            await client(UploadProfilePhotoRequest(
                file=await client.upload_file(file_path)
            ))
        return True
    except Exception as e:
        logger.error(f"Ошибка загрузки медиа в профиль: {e}")
        return False


def setup() -> BaseModule:
    return BaseModule(
        name="Clone",
        version="1.0",
        description="Клонирование профилей",
        commands={
            "clone": _clone,
            "cloneme": _cloneme,
            "setme": _setme,
        },
        examples=[
            "`.clone` – клонировать профиль по реплаю",
            "`.clone @username` – клонировать профиль по юзернейму",
            "`.cloneme` – сохранить свой текущий профиль в папку clone_me",
            "`.setme` – восстановить профиль из папки clone_me"
        ],
    )