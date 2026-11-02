"""
Discord Rich Presence баннер на Pillow — скелет с режимами и темами.

Режимы:
    0 Playing, 1 Streaming, 2 Listening, 3 Watching  (Discord activity type)
    4 Watch Together                                  (отдельный режим)
Темы:
    "dark", "light"

Данные активностей (BannerConfig.activities) в том же формате, что отдаёт Lanyard:
    type, name, details, state, application_id, assets{large_image, small_image},
    timestamps{start, end} (в мс)

Установка (Pillow 9.1+):
    pip install pillow cairosvg aiohttp

Использование:
    config = BannerConfig(mode=2, theme="light")
    asyncio.run(create_banner(config))
"""
import asyncio
import io
import time
from collections import defaultdict
from pathlib import Path

import aiohttp
import cairosvg
from PIL import Image, ImageDraw, ImageFont, ImageOps

now_ms = int(time.time() * 1000)   # нужен только для примеров timestamps в activities

# ------------------------------------------------------------------
# Иконки активности (цвет не важен — красятся в accent_color)
# ------------------------------------------------------------------

# Playing — геймпад из макета
gamepad_icon_svg = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="418 344 42 36">
  <path fill-rule="evenodd" clip-rule="evenodd" d="M456.125 348.012C456.125 348.352 456.277 348.673 456.583 348.824C457.633 349.353 458.301 350.374 458.568 351.507C459.141 353.85 460 358.498 460 364.903V374.18C459.996 375.492 459.545 376.765 458.721 377.792C457.896 378.82 456.746 379.543 455.455 379.844C454.165 380.145 452.809 380.008 451.608 379.453C450.406 378.898 449.428 377.959 448.832 376.787L445.472 370.155C445.255 369.747 444.905 369.422 444.479 369.234C444.054 369.045 443.576 369.004 443.124 369.116C442.035 369.362 440.527 369.626 439 369.626C437.473 369.626 435.945 369.362 434.876 369.116C433.941 368.908 432.967 369.305 432.528 370.155L429.168 376.787C428.572 377.959 427.594 378.898 426.392 379.453C425.191 380.008 423.835 380.145 422.545 379.844C421.254 379.543 420.104 378.82 419.279 377.792C418.455 376.765 418.004 375.492 418 374.18V364.903C418 358.517 418.878 353.85 419.432 351.488C419.718 350.355 420.367 349.353 421.417 348.843C421.565 348.762 421.687 348.64 421.768 348.493C421.849 348.346 421.886 348.179 421.875 348.012C421.875 346.689 422.792 345.518 424.166 345.234L429.76 344.063C430.715 343.874 431.669 344.176 432.356 344.819C433.025 345.461 433.845 346.16 434.8 346.104C437.598 345.96 440.402 345.96 443.2 346.104C444.155 346.16 444.975 345.461 445.644 344.8C446.312 344.176 447.285 343.855 448.24 344.063L453.853 345.234C455.189 345.518 456.125 346.708 456.125 348.012ZM454.273 354.511C454.273 355.263 453.971 355.984 453.434 356.515C452.897 357.047 452.169 357.345 451.409 357.345C450.65 357.345 449.921 357.047 449.384 356.515C448.847 355.984 448.545 355.263 448.545 354.511C448.545 353.76 448.847 353.039 449.384 352.507C449.921 351.976 450.65 351.677 451.409 351.677C452.169 351.677 452.897 351.976 453.434 352.507C453.971 353.039 454.273 353.76 454.273 354.511ZM445.682 363.013C446.441 363.013 447.17 362.715 447.707 362.183C448.244 361.652 448.545 360.931 448.545 360.179C448.545 359.428 448.244 358.707 447.707 358.175C447.17 357.644 446.441 357.345 445.682 357.345C444.922 357.345 444.194 357.644 443.657 358.175C443.12 358.707 442.818 359.428 442.818 360.179C442.818 360.931 443.12 361.652 443.657 362.183C444.194 362.715 444.922 363.013 445.682 363.013ZM425.636 353.567C425.636 353.066 425.837 352.585 426.196 352.231C426.554 351.876 427.039 351.677 427.545 351.677C428.052 351.677 428.537 351.876 428.895 352.231C429.253 352.585 429.455 353.066 429.455 353.567V355.456H431.364C431.87 355.456 432.356 355.655 432.714 356.009C433.072 356.364 433.273 356.844 433.273 357.345C433.273 357.846 433.072 358.327 432.714 358.681C432.356 359.036 431.87 359.235 431.364 359.235H429.455V361.124C429.455 361.625 429.253 362.106 428.895 362.46C428.537 362.814 428.052 363.013 427.545 363.013C427.039 363.013 426.554 362.814 426.196 362.46C425.837 362.106 425.636 361.625 425.636 361.124V359.235H423.727C423.221 359.235 422.735 359.036 422.377 358.681C422.019 358.327 421.818 357.846 421.818 357.345C421.818 356.844 422.019 356.364 422.377 356.009C422.735 355.655 423.221 355.456 423.727 355.456H425.636V353.567Z"/>
</svg>
"""

# Streaming — «эфир» (в макетах иконки нет, нарисована по аналогии)
broadcast_icon_svg = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36">
  <circle cx="18" cy="18" r="5"/>
  <path d="M10.5 10.5A10.6 10.6 0 0 0 10.5 25.5" fill="none" stroke="#000" stroke-width="3" stroke-linecap="round"/>
  <path d="M25.5 10.5A10.6 10.6 0 0 1 25.5 25.5" fill="none" stroke="#000" stroke-width="3" stroke-linecap="round"/>
  <path d="M5.5 5.5A17 17 0 0 0 5.5 30.5" fill="none" stroke="#000" stroke-width="3" stroke-linecap="round"/>
  <path d="M30.5 5.5A17 17 0 0 1 30.5 30.5" fill="none" stroke="#000" stroke-width="3" stroke-linecap="round"/>
</svg>
"""

# Watching без прогресса — экран с кнопкой play (в макетах иконки нет, нарисована по аналогии)
screen_icon_svg = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36">
  <path fill-rule="evenodd" clip-rule="evenodd" d="M7 5H29A5 5 0 0 1 34 10V22A5 5 0 0 1 29 27H7A5 5 0 0 1 2 22V10A5 5 0 0 1 7 5ZM14.5 11V21L23 16Z"/>
  <rect x="10" y="30" width="16" height="3.6" rx="1.8"/>
</svg>
"""

# Watch Together — четыре квадрата с плюсом из макета
apps_icon_svg = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 36">
  <rect x="19.8" y="19.8" width="16.2" height="16.2" rx="5.4"/>
  <rect x="0"    y="19.8" width="16.2" height="16.2" rx="5.4"/>
  <rect x="0"    y="0"    width="16.2" height="16.2" rx="5.4"/>
  <rect x="19.8" y="6.3"  width="16.2" height="3.6"  rx="1.8"/>
  <rect x="26.1" y="0"    width="3.6"  height="16.2" rx="1.8"/>
</svg>
"""


class BannerConfig:
    """Все настройки баннера. Меняй значения здесь или передавай при создании:
    BannerConfig(mode=2, theme="light")
    """

    # --- Режим и тема ---
    mode = 0                  # 0 Playing, 1 Streaming, 2 Listening, 3 Watching, 4 Watch Together
    theme = "dark"            # "dark" или "light"
    output_path = "banner.png"

    mode_names = {0: "playing", 1: "streaming", 2: "listening", 3: "watching", 4: "watch_together"}

    # --- Активности: формат Lanyard (data.activities[...]) ---
    # assets: ссылка, путь к файлу, id ассета приложения или значение из Discord
    # ("mp:external/...", "spotify:...")
    activities = {
        "playing": {
            "type": 0,
            "application_id": "782685898163617802",
            "name": "Code",
            "details": "Idling",
            "assets": {
                "large_image": "mp:external/ByjawWsm2QtMAOa2doThD3bIfP42xs9pmNqRE9rs1X4/https/raw.githubusercontent.com/LeonardSSH/vscord/main/assets/icons/idle-vscode.png",
                "small_image": "mp:external/Y6xAhARpHfRM8Bkdw0a1ZkbTAIXqKJFmrSAvHjKs6B0/https/raw.githubusercontent.com/LeonardSSH/vscord/main/assets/icons/idle.png",
            },
            "timestamps": {"start": now_ms - 5436 * 1000},
        },
        "streaming": {
            "type": 1,
            "name": "Twitch",
            "details": "Late night coding",
            "state": "Just Chatting",
            "assets": {},
            "timestamps": {"start": now_ms - 2710 * 1000},
        },
        "listening": {
            "type": 2,
            "application_id": "1362867487795970270",
            "name": "Dotify",
            "details": "Холодно",
            "state": "LXNER, lil 17th",
            "assets": {
                "large_image": "mp:external/LRNNReSbLBoT1Hf7NVlNE7Zd9SSCCG2hbl_S-g8BI6Y/https/i.scdn.co/image/ab67616d0000b27373dfbf9ae15a35177ad870b6",
                "small_image": "1442949726394781817",
            },
            "timestamps": {"start": now_ms - 79 * 1000, "end": now_ms + 130 * 1000},
        },
        "watching": {
            "type": 3,
            "application_id": "880218394199220334",
            "name": "YouTube",
            "details": "Lofi Hip Hop Radio",
            "state": "Lofi Girl",
            "assets": {"large_image": "881026601624694814"},
            "timestamps": {"start": now_ms - 754 * 1000, "end": now_ms + 1646 * 1000},
        },
        "watch_together": {
            "type": 3,
            "application_id": "880218394199220334",
            "name": "Watch Together",
            "details": "Adding videos",
            "assets": {"large_image": "881026601624694814"},
            "timestamps": {"start": now_ms - 5436 * 1000},
        },
    }

    # --- Темы (hex) ---
    themes = {
        "dark": {
            "background_color": "#2C2D32",
            "text_color": "#FFFFFF",              # activity, заголовок, прогресс и ползунок
            "secondary_text_color": "#EFEFF1",    # подзаголовок и время трека
            "accent_color": "#5EB479",            # иконка + таймер
            "cover_placeholder_color": "#464750", # если обложки нет
            "progress_track_color": "#3F4045",    # незаполненная часть прогресса
        },
        "light": {
            "background_color": "#F2F3F5",
            "text_color": "#060607",
            "secondary_text_color": "#4E5058",
            "accent_color": "#248046",
            "cover_placeholder_color": "#DCDEE3",
            "progress_track_color": "#D4D7DC",
        },
    }

    # --- Раскладка режимов ---
    # activity / title / subtitle: шаблоны, поля берутся из активности ({name}, {details}, {state})
    # footer: "elapsed" (иконка + таймер) или "progress" (полоса прогресса)
    layouts = {
        "playing": {
            "activity": "Playing", "activity_baseline": 79,
            "title": "{name}", "subtitle": "{details}",
            "footer": "elapsed", "footer_baseline": 376.5,
            "icon_box": (418, 344, 460, 380), "icon_svg": gamepad_icon_svg,
        },
        "streaming": {
            "activity": "Streaming on {name}", "activity_baseline": 79,
            "title": "{details}", "subtitle": "{state}",
            "footer": "elapsed", "footer_baseline": 376.5,
            "icon_box": (418, 344, 460, 380), "icon_svg": broadcast_icon_svg,
        },
        "listening": {
            "activity": "Listening to {name}", "activity_baseline": 86,
            "title": "{details}", "subtitle": "{state}",
            "footer": "progress", "footer_baseline": 375.5,
            "icon_box": None, "icon_svg": None,
        },
        "watching": {
            # прогресс, если есть timestamps.end, иначе иконка + таймер
            "activity": "Watching {name}", "activity_baseline": 86,
            "title": "{details}", "subtitle": "{state}",
            "footer": "progress", "footer_baseline": 375.5,
            "icon_box": (418, 344, 460, 380), "icon_svg": screen_icon_svg,
        },
        "watch_together": {
            "activity": "Playing", "activity_baseline": 79,
            "title": "Watching {name}", "subtitle": None,
            "footer": "elapsed", "footer_baseline": 324.6,
            "icon_box": (418, 292, 454, 328), "icon_svg": apps_icon_svg,
        },
    }

    icon_svg_source = None    # raw-ссылка на .svg: заменяет иконку любого режима

    # --- Шрифты ---
    font_bold_path = "NotoSans-Bold.ttf"        # activity и заголовок
    font_regular_path = "NotoSans-Regular.ttf"  # подзаголовок и время

    activity_font_size = 36
    title_font_size = 45
    text_font_size = 38
    letter_spacing_em = 0.2   # межбуквенный интервал времени (0.2 * размер шрифта)

    # --- Разметка: боксы (left, top, right, bottom), позиции (x, y) ---
    banner_size = (1479, 523)

    cover_box = (23, 122, 389, 486)
    cover_corner_radius = 25

    small_image_box = (280, 375, 392, 486)   # круглая картинка
    cutout_center = (336, 430.5)             # вырез в обложке под неё
    cutout_radius = 69

    activity_left = 23
    text_left = 418                          # заголовок, подзаголовок, текущее время
    title_baseline = 252
    subtitle_baseline = 306
    footer_text_left = 476                   # таймер справа от иконки

    progress_bar_y = (358, 365)              # верх и низ полосы прогресса
    progress_gap = 25                        # отступ полосы от текущего и полного времени
    total_time_right = 1440                  # правый край полного времени
    knob_size = (22, 43)

    # Рисуем в N раз крупнее, затем уменьшаем — края получаются гладкими
    render_scale = 4

    def __init__(self, **overrides):
        for key, value in overrides.items():
            if not hasattr(self, key):
                raise AttributeError(f"Неизвестная настройка: {key}")
            setattr(self, key, value)

    def get_mode_name(self):
        return self.mode_names.get(self.mode, self.mode)

    def get_activity(self):
        return self.activities[self.get_mode_name()]

    def get_layout(self):
        return self.layouts[self.get_mode_name()]

    def get_colors(self):
        return self.themes[self.theme]


def format_time(seconds, pad_minutes=False):
    """5436 -> 1:30:36 (таймер), 79 -> 01:19 (время трека, pad_minutes=True)"""
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    if pad_minutes:
        return f"{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


def get_image_url(asset, application_id=None):
    """assets.large_image / small_image из Lanyard -> ссылка на картинку."""
    if not asset:
        return None
    if asset.startswith("mp:external/"):
        return "https://media.discordapp.net/external/" + asset[len("mp:external/"):]
    if asset.startswith("spotify:"):
        return "https://i.scdn.co/image/" + asset[len("spotify:"):]
    if asset.isdigit():
        return f"https://cdn.discordapp.com/app-assets/{application_id}/{asset}.png"
    return asset   # уже ссылка или путь к файлу


async def read_bytes(source, session):
    """Читает файл по ссылке (http/https) или с диска. Нет источника — None."""
    if not source:
        return None
    if source.startswith(("http://", "https://")):
        async with session.get(source) as response:
            response.raise_for_status()
            return await response.read()
    return await asyncio.to_thread(Path(source).read_bytes)


def render_banner(config, cover_bytes, small_bytes, icon_bytes):
    """Синхронная отрисовка (чистый Pillow). Принимает уже загруженные байты."""
    colors = config.get_colors()
    layout = config.get_layout()
    activity = config.get_activity()
    resample = Image.Resampling.LANCZOS
    letter_spacing = config.text_font_size * config.letter_spacing_em

    def upscale(value):
        return round(value * config.render_scale)

    def upscale_values(values):
        return tuple(upscale(value) for value in values)

    banner = Image.new("RGBA", upscale_values(config.banner_size), colors["background_color"])
    draw = ImageDraw.Draw(banner)

    activity_font = ImageFont.truetype(config.font_bold_path, upscale(config.activity_font_size))
    title_font = ImageFont.truetype(config.font_bold_path, upscale(config.title_font_size))
    text_font = ImageFont.truetype(config.font_regular_path, upscale(config.text_font_size))

    def draw_text(position, text, font, color):
        draw.text(upscale_values(position), text, font=font, fill=color, anchor="ls")

    def get_spaced_width(text):
        advances = sum(text_font.getlength(character) for character in text)
        return advances / config.render_scale + letter_spacing * (len(text) - 1)

    def draw_spaced_text(position, text, color):
        """Текст с letter-spacing (в Pillow его нет — рисуем по символам)."""
        x_position, y_position = position
        for character in text:
            draw.text((upscale(x_position), upscale(y_position)), character,
                      font=text_font, fill=color, anchor="ls")
            x_position += text_font.getlength(character) / config.render_scale + letter_spacing

    def paste_image(image_bytes, box, corner_radius):
        """Картинка как CSS cover: заполняет бокс, лишнее обрезается, углы скруглены."""
        left, top, right, bottom = upscale_values(box)
        size = (right - left, bottom - top)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        image = ImageOps.fit(image, size, resample)
        mask = Image.new("L", size)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, *size), radius=upscale(corner_radius), fill=255)
        banner.paste(image, (left, top), mask)

    def paste_icon(svg_bytes, box, color):
        """SVG вписывается в бокс с сохранением пропорций и красится в color."""
        left, top, right, bottom = upscale_values(box)
        size = (right - left, bottom - top)
        icon_png = cairosvg.svg2png(bytestring=svg_bytes, output_width=size[0])
        icon = Image.open(io.BytesIO(icon_png)).convert("RGBA")
        icon = ImageOps.contain(icon, size, resample)
        position = (left + (size[0] - icon.width) // 2, top + (size[1] - icon.height) // 2)
        banner.paste(color, position, icon.getchannel("A"))

    # --- Обложка (или заглушка) ---
    if cover_bytes:
        paste_image(cover_bytes, config.cover_box, config.cover_corner_radius)
    else:
        draw.rounded_rectangle(
            upscale_values(config.cover_box),
            radius=upscale(config.cover_corner_radius),
            fill=colors["cover_placeholder_color"],
        )

    # --- Маленькая круглая картинка с вырезом в обложке ---
    if small_bytes:
        center_x, center_y = config.cutout_center
        radius = config.cutout_radius
        draw.ellipse(
            upscale_values((center_x - radius, center_y - radius,
                            center_x + radius, center_y + radius)),
            fill=colors["background_color"],
        )
        small_left, small_top, small_right, small_bottom = config.small_image_box
        paste_image(small_bytes, config.small_image_box,
                    min(small_right - small_left, small_bottom - small_top) / 2 - 0.5)

    # --- Тексты ---
    fields = defaultdict(str, activity)   # отсутствующие поля превращаются в ""

    draw_text((config.activity_left, layout["activity_baseline"]),
              layout["activity"].format_map(fields), activity_font, colors["text_color"])
    draw_text((config.text_left, config.title_baseline),
              layout["title"].format_map(fields), title_font, colors["text_color"])
    if layout["subtitle"]:
        draw_text((config.text_left, config.subtitle_baseline),
                  layout["subtitle"].format_map(fields), text_font, colors["secondary_text_color"])

    # --- Нижняя строка: время из timestamps (мс) ---
    timestamps = activity.get("timestamps", {})
    start = timestamps.get("start")
    end = timestamps.get("end")

    footer = layout["footer"]
    if footer == "progress" and not (start and end):
        footer = "elapsed"
    if not start:
        footer = None   # без timestamps нижней строки нет

    footer_baseline = layout["footer_baseline"]
    elapsed = (time.time() * 1000 - start) / 1000 if start else 0

    if footer == "elapsed":
        if icon_bytes:
            paste_icon(icon_bytes, layout["icon_box"], colors["accent_color"])
        draw_spaced_text((config.footer_text_left, footer_baseline),
                         format_time(elapsed), colors["accent_color"])

    if footer == "progress":
        duration = (end - start) / 1000
        position = min(elapsed, duration)
        current_time = format_time(position, pad_minutes=True)
        total_time = format_time(duration, pad_minutes=True)
        current_width = get_spaced_width(current_time)
        total_width = get_spaced_width(total_time)

        draw_spaced_text((config.text_left, footer_baseline), current_time,
                         colors["secondary_text_color"])
        draw_spaced_text((config.total_time_right - total_width, footer_baseline), total_time,
                         colors["secondary_text_color"])

        # полоса занимает всё место между текущим и полным временем
        bar_top, bar_bottom = config.progress_bar_y
        bar_left = config.text_left + current_width + config.progress_gap
        bar_right = config.total_time_right - total_width - config.progress_gap
        bar_height = bar_bottom - bar_top
        bar_center_y = (bar_top + bar_bottom) / 2

        knob_x = bar_left + (position / duration) * (bar_right - bar_left)
        knob_width, knob_height = config.knob_size

        draw.rounded_rectangle(
            upscale_values((bar_left, bar_top, bar_right, bar_bottom)),
            radius=upscale(bar_height / 2), fill=colors["progress_track_color"])
        draw.rounded_rectangle(
            upscale_values((bar_left, bar_top, max(knob_x, bar_left + bar_height), bar_bottom)),
            radius=upscale(bar_height / 2), fill=colors["text_color"])
        draw.rounded_rectangle(
            upscale_values((knob_x - knob_width / 2, bar_center_y - knob_height / 2,
                            knob_x + knob_width / 2, bar_center_y + knob_height / 2)),
            radius=upscale(knob_width / 2), fill=colors["text_color"])

    banner = banner.resize(config.banner_size, resample)
    banner.save(config.output_path)
    return config.output_path


async def create_banner(config=None):
    config = config or BannerConfig()
    activity = config.get_activity()
    layout = config.get_layout()

    assets = activity.get("assets", {})
    application_id = activity.get("application_id")
    cover_url = get_image_url(assets.get("large_image"), application_id)
    small_url = get_image_url(assets.get("small_image"), application_id)

    # Загрузка картинок (async, параллельно)
    async with aiohttp.ClientSession() as session:
        cover_bytes, small_bytes, icon_bytes = await asyncio.gather(
            read_bytes(cover_url, session),
            read_bytes(small_url, session),
            read_bytes(config.icon_svg_source, session),
        )

    if icon_bytes is None and layout["icon_svg"]:
        icon_bytes = layout["icon_svg"].encode()

    # Отрисовка — в отдельном потоке, чтобы не блокировать event loop
    return await asyncio.to_thread(render_banner, config, cover_bytes, small_bytes, icon_bytes)


if __name__ == "__main__":
    print("Сохранено:", asyncio.run(create_banner(BannerConfig())))
