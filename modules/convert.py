import asyncio
import os
import random

from telethon.tl.types import (
    DocumentAttributeVideo,
    DocumentAttributeAudio,
    InputMediaUploadedDocument,
)
from telethon.tl.functions.messages import SendMediaRequest

from modules.base import BaseModule
from utils import logger


async def _run_ffmpeg(cmd: str) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return proc.returncode, stderr.decode(errors="replace")


async def _get_duration(path: str) -> int:
    try:
        probe = await asyncio.create_subprocess_shell(
            f'ffprobe -v quiet -show_entries format=duration -of csv=p=0 "{path}"',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await probe.communicate()
        if out:
            return int(float(out.decode().strip()))
    except Exception:
        pass
    return 0


async def _convert(event):
    await event.delete()

    mode = "video" if event.raw_text.strip().startswith(".video") else "voice"

    reply = await event.get_reply_message()
    if not reply or not reply.media:
        await event.respond("❌ Ответь на видео или аудиофайл")
        return

    status = await event.respond("🍀 Обрабатываю...")

    input_path = None
    output_path = None

    try:
        input_path = await event.client.download_media(reply, file="media_input")

        if mode == "video":
            output_path = "output.mp4"

            cmd = (
                f'ffmpeg -y -i "{input_path}" -t 59 '
                f'-vf "scale=\'if(gt(a,1),480,trunc(oh*a/2)*2)\':\'if(gt(a,1),trunc(ow/a/2)*2,480)\','
                f'pad=480:480:(480-iw)/2:(480-ih)/2:black,'
                f'crop=480:480" '
                f'-c:v libx264 -preset veryfast -crf 23 '
                f'-pix_fmt yuv420p '
                f'-c:a aac -b:a 64k -ar 48000 '
                f'-movflags +faststart '
                f'-map_metadata -1 '
                f'-avoid_negative_ts make_zero '
                f'"{output_path}"'
            )

            returncode, stderr = await _run_ffmpeg(cmd)

            if returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.warning(f"Первый проход ffmpeg упал (code {returncode}), пробую fallback...")

                intermediate = "intermediate.mp4"
                fallback_step1 = (
                    f'ffmpeg -y -i "{input_path}" '
                    f'-c:v libx264 -preset veryfast -crf 28 -pix_fmt yuv420p '
                    f'-c:a aac -ar 48000 -avoid_negative_ts make_zero '
                    f'"{intermediate}"'
                )
                rc1, _ = await _run_ffmpeg(fallback_step1)

                if rc1 == 0 and os.path.exists(intermediate) and os.path.getsize(intermediate) > 0:
                    fallback_step2 = (
                        f'ffmpeg -y -i "{intermediate}" -t 59 '
                        f'-vf "scale=\'if(gt(a,1),480,trunc(oh*a/2)*2)\':\'if(gt(a,1),trunc(ow/a/2)*2,480)\',' 
                        f'pad=480:480:(480-iw)/2:(480-ih)/2:black,crop=480:480" '
                        f'-c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p '
                        f'-c:a aac -b:a 64k -ar 48000 -movflags +faststart '
                        f'"{output_path}"'
                    )
                    returncode, stderr = await _run_ffmpeg(fallback_step2)

                if os.path.exists(intermediate):
                    os.remove(intermediate)

            if returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error(f"ffmpeg stderr: {stderr[-500:]}")
                await status.edit("❌ Не удалось конвертировать видео. Возможно, файл повреждён или неподдерживаемый формат.")
                return

            duration = await _get_duration(output_path)
            uploaded = await event.client.upload_file(output_path)

            attributes = [DocumentAttributeVideo(
                duration=min(duration, 59),
                w=480,
                h=480,
                round_message=True,
                supports_streaming=True,
            )]

            media = InputMediaUploadedDocument(
                file=uploaded,
                mime_type="video/mp4",
                attributes=attributes,
            )

        else:
            output_path = "output.ogg"
            cmd = (
                f'ffmpeg -y -i "{input_path}" '
                f'-vn -acodec libopus -ar 48000 -ac 1 -b:a 64k '
                f'-avoid_negative_ts make_zero '
                f'"{output_path}"'
            )
            returncode, stderr = await _run_ffmpeg(cmd)

            if returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                logger.error(f"ffmpeg stderr: {stderr[-500:]}")
                await status.edit("❌ Не удалось конвертировать аудио.")
                return

            duration = await _get_duration(output_path)
            uploaded = await event.client.upload_file(output_path)

            attributes = [DocumentAttributeAudio(
                duration=duration,
                voice=True,
            )]

            media = InputMediaUploadedDocument(
                file=uploaded,
                mime_type="audio/ogg",
                attributes=attributes,
            )

        await event.client(SendMediaRequest(
            peer=await event.get_input_chat(),
            media=media,
            message="",
            random_id=random.randint(-2**63, 2**63 - 1),
        ))

        await status.edit("🍀 Готово ✅")

    except Exception as e:
        logger.error(f"Ошибка конвертации: {e}")
        await status.edit(f"❌ Ошибка конвертации.\nПричина: {str(e)[:150]}")

    finally:
        for f in [input_path, output_path]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except Exception:
                    pass


def setup() -> BaseModule:
    return BaseModule(
        name="Convert",
        version="1.0",
        description="Конвертация медиа в кружки и голосовые",
        commands={
            "voice": _convert,
            "video": _convert,
        },
        examples=[
            "`.voice` – сделать голосовое сообщение (ответь на видео/аудио)",
            "`.video` – сделать кружок (ответь на видео)"
        ],
    )