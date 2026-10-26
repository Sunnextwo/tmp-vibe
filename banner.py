# meta dev: @SunnexGB
# meta name: Discordo Card
# meta preview: https://raw.githubusercontent.com/.../discordo_preview.png

"""
Discord Rich Presence баннер на Pillow (данные берутся из Lanyard).

Режимы (modes):
    auto            сам выбирает активность по приоритету: listening, streaming, playing,
                    watch_together, watching
    playing         Playing (activity type 0)
    streaming       Streaming (type 1)
    listening       Listening (type 2, в том числе Spotify и Dotify)
    watching        Watching (type 3)
    watch_together  Watch Together (type 3 с именем «Watch Together»)

Если выбранной активности нет в данных, режим подбирается как в auto.
Если нет вообще никакой поддерживаемой активности, баннер не рисуется (render возвращает None);
проверить это заранее можно функцией has_activity(data).
Кастомный статус (type 4) и Competing (type 5) не показываются.

Зависимости: pillow, cairosvg (иконки; без неё баннер рисуется без иконок).
"""
import asyncio
import io
import time
from collections import defaultdict

from PIL import Image, ImageDraw, ImageFont, ImageOps

try:
    import cairosvg
except (ImportError, OSError):  # нет cairosvg или системной libcairo
    cairosvg = None

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

themes = {
    "dark": {
        "background_color": "#2C2D32",
        "text_color": "#FFFFFF",              # label, заголовок, прогресс и ползунок
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

modes = ["auto", "playing", "streaming", "listening", "watching", "watch_together"]

options = {
    "show_label": True,         # надпись сверху («Listening to Spotify»)
    "show_small_image": True,   # круглая картинка на обложке
    "show_footer": True,        # нижняя строка: таймер или полоса прогресса
}

# Шрифты по умолчанию. Если пользователь указал свой шрифт, он заменяет оба.
default_font_urls = {
    "bold": "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSans/full/ttf/NotoSans-Bold.ttf",
    "regular": "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSans/full/ttf/NotoSans-Regular.ttf",
}

mode_by_activity_type = {0: "playing", 1: "streaming", 2: "listening", 3: "watching"}
auto_priority = ["listening", "streaming", "playing", "watch_together", "watching"]


class BannerConfig:
    """Раскладка баннера: размеры, позиции, шаблоны текста для каждого режима."""

    # --- Раскладка режимов ---
    # label / title / subtitle: шаблоны, {name}, {details}, {state}, {status} берутся из активности
    # footer: "elapsed" (иконка + таймер), "progress" (полоса прогресса) или None
    layouts = {
        "playing": {
            "label": "Playing", "label_baseline": 79,
            "title": "{name}", "subtitle": "{details}",
            "footer": "elapsed", "footer_baseline": 376.5,
            "icon_box": (418, 344, 460, 380), "icon_svg": gamepad_icon_svg,
        },
        "streaming": {
            "label": "Streaming on {name}", "label_baseline": 79,
            "title": "{details}", "subtitle": "{state}",
            "footer": "elapsed", "footer_baseline": 376.5,
            "icon_box": (418, 344, 460, 380), "icon_svg": broadcast_icon_svg,
        },
        "listening": {
            "label": "Listening to {name}", "label_baseline": 86,
            "title": "{details}", "subtitle": "{state}",
            "footer": "progress", "footer_baseline": 375.5,
            "icon_box": None, "icon_svg": None,
        },
        "watching": {
            # прогресс, если в активности есть конец (end), иначе иконка + таймер
            "label": "Watching {name}", "label_baseline": 86,
            "title": "{details}", "subtitle": "{state}",
            "footer": "progress", "footer_baseline": 375.5,
            "icon_box": (418, 344, 460, 380), "icon_svg": screen_icon_svg,
        },
        "watch_together": {
            "label": "Playing", "label_baseline": 79,
            "title": "Watching {name}", "subtitle": None,
            "footer": "elapsed", "footer_baseline": 324.6,
            "icon_box": (418, 292, 454, 328), "icon_svg": apps_icon_svg,
        },
    }

    # --- Шрифты ---
    label_font_size = 36
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

    label_left = 23
    text_left = 418                          # заголовок, подзаголовок, текущее время
    title_baseline = 252
    subtitle_baseline = 306
    footer_text_left = 476                   # таймер справа от иконки

    progress_bar_y = (358, 365)              # верх и низ полосы прогресса
    progress_gap = 25                        # отступ полосы от текущего и полного времени
    total_time_right = 1440                  # правый край полного времени
    knob_size = (22, 43)

    # Рисуем в N раз крупнее, затем уменьшаем: края получаются гладкими
    render_scale = 4


def format_time(seconds, pad_minutes=False):
    """5436 -> 1:30:36 (таймер), 79 -> 01:19 (время трека, pad_minutes=True)"""
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    if pad_minutes:
        return f"{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


# ------------------------------------------------------------------
# Данные Lanyard -> поля баннера
# ------------------------------------------------------------------

def get_mode_name(activity):
    """Режим, которому соответствует активность Lanyard. None, если активность не поддерживается."""
    if activity.get("type") == 3 and activity.get("name") == "Watch Together":
        return "watch_together"
    return mode_by_activity_type.get(activity.get("type"))


def find_activity(data, mode_name):
    """
    Выбирает активность для баннера. Возвращает (имя режима, активность) или (None, None).
    Если режим задан и такая активность есть, берётся она, иначе выбор по auto_priority.
    """
    found = {}
    for activity in data.get("activities", []):
        found.setdefault(get_mode_name(activity), activity)

    if mode_name in found:
        return mode_name, found[mode_name]
    for name in auto_priority:
        if name in found:
            return name, found[name]
    return None, None


def has_activity(data):
    """Есть ли в данных активность, которую умеет рисовать баннер (модуль спрашивает это перед рендером)."""
    return find_activity(data, "auto")[1] is not None


def find_image_url(activity, asset_name):
    """Превращает assets.large_image / small_image из Discord в ссылку на картинку."""
    image = activity.get("assets", {}).get(asset_name, "")
    application_id = activity.get("application_id")

    if image.startswith("mp:external/"):
        return "https://media.discordapp.net/" + image[len("mp:"):]
    if image.startswith("spotify:"):
        return "https://i.scdn.co/image/" + image[len("spotify:"):]
    if image.startswith("twitch:"):
        return f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{image[len('twitch:'):]}-1280x720.jpg"
    if image.startswith("youtube:"):
        return f"https://i.ytimg.com/vi/{image[len('youtube:'):]}/maxresdefault_live.jpg"
    if image and ":" not in image and application_id:
        return f"https://cdn.discordapp.com/app-assets/{application_id}/{image}.png"
    return None


def build_fields(activity, now):
    """Поля для шаблонов раскладки и время активности (в секундах)."""
    fields = defaultdict(str)
    for field_name in ("name", "details", "state"):
        fields[field_name] = activity.get(field_name, "")

    timestamps = activity.get("timestamps", {})
    start = timestamps.get("start")
    end = timestamps.get("end")

    if start:
        elapsed = max(0, now - start / 1000)
        fields["elapsed_seconds"] = elapsed
        if end:
            duration = (end - start) / 1000
            fields["duration_seconds"] = duration
            fields["position_seconds"] = min(elapsed, duration)

    return fields


async def fetch_optional(fetch_bytes, url):
    """Скачивает файл, если ссылка есть."""
    return await fetch_bytes(url) if url else None


# ------------------------------------------------------------------
# Рендер
# ------------------------------------------------------------------

async def render(settings, data, font_bytes):
    """Рисует баннер по данным Lanyard."""
    config = BannerConfig()

    mode_name, activity = find_activity(data, settings["mode"])
    if activity is None:
        return None

    layout = config.layouts[mode_name]
    fields = build_fields(activity, time.time())
    cover_url = find_image_url(activity, "large_image")
    small_url = find_image_url(activity, "small_image")

    fetch_bytes = settings["fetch_bytes"]
    bold_bytes = font_bytes or await settings["fetch_font"](default_font_urls["bold"])
    regular_bytes = font_bytes or await settings["fetch_font"](default_font_urls["regular"])
    if not bold_bytes or not regular_bytes:
        return None

    cover_bytes, small_bytes = await asyncio.gather(
        fetch_optional(fetch_bytes, cover_url),
        fetch_optional(fetch_bytes, small_url),
    )
    icon_bytes = layout["icon_svg"].encode() if layout["icon_svg"] else None

    # Отрисовка в отдельном потоке, чтобы не блокировать event loop
    return await asyncio.to_thread(
        render_banner,
        config,
        settings["colors"],
        settings["options"],
        layout,
        fields,
        {"cover": cover_bytes, "small": small_bytes, "icon": icon_bytes},
        {"bold": bold_bytes, "regular": regular_bytes},
    )


def render_banner(config, colors, enabled, layout, fields, images, fonts):
    """Синхронная отрисовка (чистый Pillow). Возвращает io.BytesIO с PNG."""
    resample = Image.Resampling.LANCZOS
    letter_spacing = config.text_font_size * config.letter_spacing_em

    def upscale(value):
        return round(value * config.render_scale)

    def upscale_values(values):
        return tuple(upscale(value) for value in values)

    banner = Image.new("RGBA", upscale_values(config.banner_size), colors["background_color"])
    draw = ImageDraw.Draw(banner)

    label_font = ImageFont.truetype(io.BytesIO(fonts["bold"]), upscale(config.label_font_size))
    title_font = ImageFont.truetype(io.BytesIO(fonts["bold"]), upscale(config.title_font_size))
    text_font = ImageFont.truetype(io.BytesIO(fonts["regular"]), upscale(config.text_font_size))

    def draw_text(position, text, font, color):
        draw.text(upscale_values(position), text, font=font, fill=color, anchor="ls")

    def get_spaced_width(text):
        advances = sum(text_font.getlength(character) for character in text)
        return advances / config.render_scale + letter_spacing * (len(text) - 1)

    def draw_spaced_text(position, text, color):
        """Текст с letter-spacing (в Pillow его нет: рисуем по символам)."""
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
        if cairosvg is None:
            return
        left, top, right, bottom = upscale_values(box)
        size = (right - left, bottom - top)
        icon_png = cairosvg.svg2png(bytestring=svg_bytes, output_width=size[0])
        icon = Image.open(io.BytesIO(icon_png)).convert("RGBA")
        icon = ImageOps.contain(icon, size, resample)
        position = (left + (size[0] - icon.width) // 2, top + (size[1] - icon.height) // 2)
        banner.paste(color, position, icon.getchannel("A"))

    # --- Обложка (или заглушка) ---
    cover_drawn = False
    if images["cover"]:
        try:
            paste_image(images["cover"], config.cover_box, config.cover_corner_radius)
            cover_drawn = True
        except OSError:  # скачалось не изображение
            pass
    if not cover_drawn:
        draw.rounded_rectangle(
            upscale_values(config.cover_box),
            radius=upscale(config.cover_corner_radius),
            fill=colors["cover_placeholder_color"],
        )

    # --- Маленькая круглая картинка с вырезом в обложке ---
    if images["small"] and enabled["show_small_image"]:
        center_x, center_y = config.cutout_center
        radius = config.cutout_radius
        draw.ellipse(
            upscale_values((center_x - radius, center_y - radius,
                            center_x + radius, center_y + radius)),
            fill=colors["background_color"],
        )
        small_left, small_top, small_right, small_bottom = config.small_image_box
        try:
            paste_image(images["small"], config.small_image_box,
                        min(small_right - small_left, small_bottom - small_top) / 2 - 0.5)
        except OSError:
            pass

    # --- Тексты ---
    if enabled["show_label"]:
        draw_text((config.label_left, layout["label_baseline"]),
                  layout["label"].format_map(fields), label_font, colors["text_color"])
    draw_text((config.text_left, config.title_baseline),
              layout["title"].format_map(fields), title_font, colors["text_color"])
    if layout["subtitle"]:
        draw_text((config.text_left, config.subtitle_baseline),
                  layout["subtitle"].format_map(fields), text_font, colors["secondary_text_color"])

    # --- Нижняя строка ---
    footer = layout["footer"]
    footer_baseline = layout["footer_baseline"]
    if footer == "progress" and not fields.get("duration_seconds"):
        footer = "elapsed"
    if footer == "elapsed" and fields.get("elapsed_seconds") is None:
        footer = None
    if not enabled["show_footer"]:
        footer = None

    if footer == "elapsed":
        if images["icon"]:
            paste_icon(images["icon"], layout["icon_box"], colors["accent_color"])
        draw_spaced_text((config.footer_text_left, footer_baseline),
                         format_time(fields["elapsed_seconds"]), colors["accent_color"])

    if footer == "progress":
        position = fields["position_seconds"]
        duration = fields["duration_seconds"]
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

        fraction = min(max(position / duration, 0), 1)
        knob_x = bar_left + fraction * (bar_right - bar_left)
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
    output = io.BytesIO()
    banner.save(output, format="PNG")
    output.seek(0)
    output.name = "discordo.png"
    return output
