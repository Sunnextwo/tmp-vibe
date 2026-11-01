# meta dev: @SunnexGB
# meta name: Discordo
# meta preview: https://r2.fakecrime.bio/uploads/7a768f15-8d2a-4851-bac6-76adb8705634.jpg

"""
Discord Rich Presence баннер на Pillow (данные из Lanyard).

Режим (раскладка) выбирается автоматически по активности в данных.
Главная активность определяется порядком auto_priority:
listening, streaming, playing, watch_together, watching.
Нет поддерживаемых активностей: render возвращает None.
Кастомный статус (type 4) и Competing (type 5) не показываются.
"""
import asyncio
import io
import time
from collections import defaultdict

import cairosvg
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageOps

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
        "main_color": "#FFFFFF",
        "desc_color": "#EFEFF1",
        "accent_color": "#5EB479",
        "cover_placeholder_color": "#464750",
        "progress_track_color": "#3F4045",
    },
    "light": {
        "background_color": "#F2F3F5",
        "main_color": "#060607",
        "desc_color": "#4E5058",
        "accent_color": "#248046",
        "cover_placeholder_color": "#DCDEE3",
        "progress_track_color": "#D4D7DC",
    },
}

# Режимы баннера, выбираются автоматически (читает только сам баннер)
modes = [
    "auto",
    "playing",
    "streaming",
    "listening",
    "watching",
    "watch_together",
]

options = {
    "show_head": True,
    "show_small_image": True,
    "show_footer": True,
}

default_font_urls = {
    "bold": "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSans/full/ttf/NotoSans-Bold.ttf",
    "regular": "https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts/NotoSans/full/ttf/NotoSans-Regular.ttf",
}

mode_by_type = {
    0: "playing",
    1: "streaming",
    2: "listening",
    3: "watching",
}

auto_priority = [
    "listening",
    "streaming",
    "playing",
    "watch_together",
    "watching",
]


class BannerCfg:
    """Размеры, позиции и шаблоны строк для каждого режима."""

    # head, title, subtitle: шаблоны с {name}, {details}, {state}
    # footer: "elapsed" (иконка и таймер), "progress" (полоса прогресса) или None
    layouts = {
        "playing": {
            "head": "Playing",
            "head_baseline": 79,
            "title": "{name}",
            "subtitle": "{details}",
            "footer": "elapsed",
            "footer_baseline": 376.5,
            "icon_box": (418, 344, 460, 380),
            "icon_svg": gamepad_icon_svg,
        },
        "streaming": {
            "head": "Streaming on {name}",
            "head_baseline": 79,
            "title": "{details}",
            "subtitle": "{state}",
            "footer": "elapsed",
            "footer_baseline": 376.5,
            "icon_box": (418, 344, 460, 380),
            "icon_svg": broadcast_icon_svg,
        },
        "listening": {
            "head": "Listening to {name}",
            "head_baseline": 86,
            "title": "{details}",
            "subtitle": "{state}",
            "footer": "progress",
            "footer_baseline": 375.5,
            "icon_box": None,
            "icon_svg": None,
        },
        "watching": {
            "head": "Watching {name}",
            "head_baseline": 86,
            "title": "{details}",
            "subtitle": "{state}",
            "footer": "progress",
            "footer_baseline": 375.5,
            "icon_box": (418, 344, 460, 380),
            "icon_svg": screen_icon_svg,
        },
        "watch_together": {
            "head": "Playing",
            "head_baseline": 79,
            "title": "Watching {name}",
            "subtitle": None,
            "footer": "elapsed",
            "footer_baseline": 324.6,
            "icon_box": (418, 292, 454, 328),
            "icon_svg": apps_icon_svg,
        },
    }

    head_font_size = 36
    title_font_size = 45
    desc_font_size = 38
    letter_spacing_em = 0.2

    banner_size = (1479, 523)

    cover_box = (23, 122, 389, 486)
    cover_corner_radius = 25

    small_image_box = (280, 375, 392, 486)
    cutout_center = (336, 430.5)
    cutout_radius = 69

    head_left = 23
    body_left = 418
    title_baseline = 252
    subtitle_baseline = 306
    footer_left = 476

    progress_bar_y = (358, 365)
    progress_gap = 25
    total_time_right = 1440
    knob_size = (22, 43)

    # На сколько px нижняя строка поднимается, если подзаголовка нет
    # (расстояние от заголовка до неё было 85px, станет 27px)
    no_subtitle_shift = 60

    # Рисуем в N раз крупнее, затем уменьшаем: края получаются гладкими
    render_scale = 4


def format_time(seconds, pad_minutes=False):
    """5436 даёт 1:30:36 (таймер), 79 даёт 01:19 (время трека, pad_minutes=True)"""
    hours, rest = divmod(int(seconds), 3600)
    minutes, seconds = divmod(rest, 60)

    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    if pad_minutes:
        return f"{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


# ------------------------------------------------------------------
# Данные Lanyard
# ------------------------------------------------------------------

def activity_mode(activity):
    """Режим, которому соответствует активность. Не поддерживается: None."""
    if activity.get("type") == 3 and activity.get("name") == "Watch Together":
        return "watch_together"
    return mode_by_type.get(activity.get("type"))


def fetch_activity(data):
    """Выбирает активность для баннера по auto_priority: (имя режима, активность) или (None, None)."""
    found = {}
    for activity in data.get("activities", []):
        name = activity_mode(activity)
        if name:
            found.setdefault(name, activity)

    for name in auto_priority:
        if name in found:
            return name, found[name]

    return None, None


def fetch_image_url(activity, asset_name):
    """
    Ссылка на картинку из assets.large_image / small_image.

    https://...                  полная ссылка, берём как есть
    mp:external/..., mp:...      прокси Discord: https://media.discordapp.net/...
    spotify:ID                   https://i.scdn.co/image/ID
    twitch:имя, youtube:ID       превью стрима
    881026601624694814 (id)      https://cdn.discordapp.com/app-assets/{application_id}/{id}.png
    """
    image = activity.get("assets", {}).get(asset_name, "")
    application_id = activity.get("application_id")

    if image.startswith(("http://", "https://")):
        return image
    if image.startswith("mp:"):
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


def fields(activity, now):
    """Значения для шаблонов раскладки и время активности (в секундах)."""
    values = defaultdict(str)
    for key in ("name", "details", "state"):
        values[key] = activity.get(key, "")

    stamps = activity.get("timestamps", {})
    start = stamps.get("start")
    end = stamps.get("end")

    if start:
        elapsed = max(0, now - start / 1000)
        values["elapsed_seconds"] = elapsed
        if end:
            duration = (end - start) / 1000
            values["duration_seconds"] = duration
            values["position_seconds"] = min(elapsed, duration)

    return values


def make_font(font_bytes, size):
    """Шрифт из скачанных байтов. Не скачался: встроенный шрифт Pillow."""
    if font_bytes:
        return ImageFont.truetype(io.BytesIO(font_bytes), size)
    return ImageFont.load_default(size)


async def dl_optional(dl_bytes, url):
    """Скачивает файл, если ссылка есть."""
    return await dl_bytes(url) if url else None


# ------------------------------------------------------------------
# Рендер
# ------------------------------------------------------------------

async def render(settings, data, font_bytes):
    cfg = BannerCfg()

    mode_name, activity = fetch_activity(data)
    if activity is None:
        return None

    bold_bytes = font_bytes or await settings["dl_font"](default_font_urls["bold"])
    regular_bytes = font_bytes or await settings["dl_font"](default_font_urls["regular"])

    cover_bytes, small_bytes = await asyncio.gather(
        dl_optional(settings["dl_bytes"], fetch_image_url(activity, "large_image")),
        dl_optional(settings["dl_bytes"], fetch_image_url(activity, "small_image")),
    )

    layout = cfg.layouts[mode_name]
    icon_bytes = layout["icon_svg"].encode() if layout["icon_svg"] else None

    # Отрисовка в отдельном потоке, чтобы не блокировать event loop
    return await asyncio.to_thread(
        render_banner,
        cfg,
        settings["colors"],
        settings["options"],
        layout,
        fields(activity, time.time()),
        {"cover": cover_bytes, "small": small_bytes, "icon": icon_bytes},
        {"bold": bold_bytes, "regular": regular_bytes},
    )


def render_banner(cfg, colors, enabled, layout, values, images, fonts):
    """Синхронная отрисовка (чистый Pillow). Возвращает io.BytesIO с PNG."""
    resample = Image.Resampling.LANCZOS
    spacing = cfg.desc_font_size * cfg.letter_spacing_em

    def up(value):
        return round(value * cfg.render_scale)

    def up_all(coords):
        return tuple(up(coord) for coord in coords)

    banner = Image.new("RGBA", up_all(cfg.banner_size), colors["background_color"])
    draw = ImageDraw.Draw(banner)

    head_font = make_font(fonts["bold"], up(cfg.head_font_size))
    title_font = make_font(fonts["bold"], up(cfg.title_font_size))
    desc_font = make_font(fonts["regular"], up(cfg.desc_font_size))

    def draw_str(position, value, font, color):
        draw.text(up_all(position), value, font=font, fill=color, anchor="ls")

    def spaced_width(value):
        advances = sum(desc_font.getlength(char) for char in value)
        return advances / cfg.render_scale + spacing * (len(value) - 1)

    def draw_spaced(position, value, color):
        """Строка с межбуквенным интервалом (в Pillow его нет: рисуем по символам)."""
        left, top = position
        for char in value:
            draw.text((up(left), up(top)), char, font=desc_font, fill=color, anchor="ls")
            left += desc_font.getlength(char) / cfg.render_scale + spacing

    def paste_image(image_bytes, box, corner_radius):
        """Картинка целиком вписывается в бокс (ничего не обрезается), углы бокса скруглены."""
        left, top, right, bottom = up_all(box)
        size = (right - left, bottom - top)

        image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        image = ImageOps.contain(image, size, resample)

        canvas = Image.new("RGBA", size, (0, 0, 0, 0))
        canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))

        mask = Image.new("L", size)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *size), radius=up(corner_radius), fill=255)

        banner.paste(canvas, (left, top), ImageChops.multiply(canvas.getchannel("A"), mask))

    def paste_icon(svg_bytes, box, color):
        """SVG вписывается в бокс с сохранением пропорций и красится в color."""
        left, top, right, bottom = up_all(box)
        size = (right - left, bottom - top)

        icon_png = cairosvg.svg2png(bytestring=svg_bytes, output_width=size[0])
        icon = Image.open(io.BytesIO(icon_png)).convert("RGBA")
        icon = ImageOps.contain(icon, size, resample)

        position = (left + (size[0] - icon.width) // 2, top + (size[1] - icon.height) // 2)
        banner.paste(color, position, icon.getchannel("A"))

    # --- Обложка: заглушка, поверх неё картинка ---
    draw.rounded_rectangle(
        up_all(cfg.cover_box),
        radius=up(cfg.cover_corner_radius),
        fill=colors["cover_placeholder_color"],
    )
    if images["cover"]:
        try:
            paste_image(images["cover"], cfg.cover_box, cfg.cover_corner_radius)
        except OSError:
            pass

    # --- Круглая картинка с вырезом в обложке ---
    if images["small"] and enabled["show_small_image"]:
        center_left, center_top = cfg.cutout_center
        radius = cfg.cutout_radius
        draw.ellipse(
            up_all((
                center_left - radius,
                center_top - radius,
                center_left + radius,
                center_top + radius,
            )),
            fill=colors["background_color"],
        )

        small_left, small_top, small_right, small_bottom = cfg.small_image_box
        small_radius = min(small_right - small_left, small_bottom - small_top) / 2 - 0.5
        try:
            paste_image(images["small"], cfg.small_image_box, small_radius)
        except OSError:
            pass

    # --- Строки ---
    if enabled["show_head"]:
        draw_str(
            (cfg.head_left, layout["head_baseline"]),
            layout["head"].format_map(values),
            head_font,
            colors["main_color"],
        )

    draw_str(
        (cfg.body_left, cfg.title_baseline),
        layout["title"].format_map(values),
        title_font,
        colors["main_color"],
    )

    sub_str = layout["subtitle"].format_map(values).strip() if layout["subtitle"] else ""
    if sub_str:
        draw_str(
            (cfg.body_left, cfg.subtitle_baseline),
            sub_str,
            desc_font,
            colors["desc_color"],
        )

    # Подзаголовок предусмотрен раскладкой, но Discord его не прислал (нет details или state):
    # нижняя строка поднимается, иначе между ней и заголовком остаётся пустое место
    footer_shift = 0
    if layout["subtitle"] and not sub_str:
        footer_shift = -cfg.no_subtitle_shift

    # --- Нижняя строка ---
    footer = layout["footer"]
    footer_baseline = layout["footer_baseline"] + footer_shift

    if footer == "progress" and not values.get("duration_seconds"):
        footer = "elapsed"
    if footer == "elapsed" and values.get("elapsed_seconds") is None:
        footer = None
    if not enabled["show_footer"]:
        footer = None

    if footer == "elapsed":
        if images["icon"]:
            icon_left, icon_top, icon_right, icon_bottom = layout["icon_box"]
            paste_icon(
                images["icon"],
                (icon_left, icon_top + footer_shift, icon_right, icon_bottom + footer_shift),
                colors["accent_color"],
            )
        draw_spaced(
            (cfg.footer_left, footer_baseline),
            format_time(values["elapsed_seconds"]),
            colors["accent_color"],
        )

    if footer == "progress":
        position = values["position_seconds"]
        duration = values["duration_seconds"]
        current_str = format_time(position, pad_minutes=True)
        total_str = format_time(duration, pad_minutes=True)

        draw_spaced((cfg.body_left, footer_baseline), current_str, colors["desc_color"])
        draw_spaced(
            (cfg.total_time_right - spaced_width(total_str), footer_baseline),
            total_str,
            colors["desc_color"],
        )

        # полоса занимает всё место между текущим и полным временем
        bar_top, bar_bottom = (edge + footer_shift for edge in cfg.progress_bar_y)
        bar_left = cfg.body_left + spaced_width(current_str) + cfg.progress_gap
        bar_right = cfg.total_time_right - spaced_width(total_str) - cfg.progress_gap
        bar_height = bar_bottom - bar_top
        bar_center = (bar_top + bar_bottom) / 2

        knob_x = bar_left + min(max(position / duration, 0), 1) * (bar_right - bar_left)
        knob_width, knob_height = cfg.knob_size

        draw.rounded_rectangle(
            up_all((bar_left, bar_top, bar_right, bar_bottom)),
            radius=up(bar_height / 2),
            fill=colors["progress_track_color"],
        )
        draw.rounded_rectangle(
            up_all((bar_left, bar_top, max(knob_x, bar_left + bar_height), bar_bottom)),
            radius=up(bar_height / 2),
            fill=colors["main_color"],
        )
        draw.rounded_rectangle(
            up_all((
                knob_x - knob_width / 2,
                bar_center - knob_height / 2,
                knob_x + knob_width / 2,
                bar_center + knob_height / 2,
            )),
            radius=up(knob_width / 2),
            fill=colors["main_color"],
        )

    banner = banner.resize(cfg.banner_size, resample)
    output = io.BytesIO()
    banner.save(output, format="PNG")
    output.seek(0)
    output.name = "banner.png"
    return output
