import asyncio
import io
import logging
import re
import types

import aiohttp

from .. import loader

logger = logging.getLogger(__name__)


class Banner:
    """
    Загруженный баннер. Его отдаёт BannerLoaderLib.load_banner(url).

    banner.url, banner.title, banner.author_name, banner.author_url, banner.preview_url
    banner.theme_names, banner.color_names, banner.option_names
    """

    def __init__(self, lib, url, mod_w_banner, meta):
        self.lib = lib
        self.url = url
        self.module = mod_w_banner

        self.title = meta.get("name") or url.rsplit("/", 1)[-1]
        self.author_name, self.author_url = lib.get_author(meta.get("dev"))
        self.preview_url = meta.get("preview")

        self.themes = mod_w_banner.themes
        self.theme_names = list(self.themes)
        self.color_names = list(self.themes[self.theme_names[0]])
        self.option_defaults = dict(getattr(mod_w_banner, "options", {}))
        self.option_names = list(self.option_defaults)

    def get_colors(self, theme_name, custom_colors=None):
        """Цвета темы. Для "custom": базовая (первая) тема, поверх неё валидные цвета пользователя."""
        if theme_name in self.themes:
            return dict(self.themes[theme_name])

        colors = dict(self.themes[self.theme_names[0]])
        for color_name, color_value in (custom_colors or {}).items():
            if color_name in colors and self.lib.color_type(str(color_value)):
                colors[color_name] = color_value
        return colors

    def get_options(self, option_values=None):
        """Опции баннера: значения по умолчанию, поверх них option_values."""
        options = dict(self.option_defaults)
        for option_name, option_value in (option_values or {}).items():
            if option_name in options:
                options[option_name] = bool(option_value)
        return options

    def fetch_cfg_error_syntax(self, theme_name, custom_colors=None):
        """Ошибки в цветах пользователя. Проверяются только при теме "custom"."""
        if theme_name != "custom":
            return []
        return list(self.lib.allowed_color_syntax(custom_colors, self.color_names))

    async def render(
        self,
        data,
        theme_name,
        custom_colors=None,
        option_values=None,
        font_url=None,
    ):
        """
        Рисует баннер. Возвращает io.BytesIO с PNG, None если рисовать нечего.

        data:           данные для баннера (ответ Lanyard)
        theme_name:     имя темы или "custom"
        custom_colors:  {"ключ цвета": "#RRGGBB"} для темы "custom"
        option_values:  {"имя опции": True или False}
        font_url:       свой шрифт (не указан: баннер берёт свои)
        """
        font_bytes = await self.lib.dl_font(font_url) if font_url else None

        settings = {
            "colors": self.get_colors(theme_name, custom_colors),
            "options": self.get_options(option_values),
            "dl_bytes": self.lib.dl_bytes,
            "dl_json": self.lib.dl_json,
            "dl_font": self.lib.dl_font,
        }

        result = await self.module.render(settings, data, font_bytes)

        if isinstance(result, bytes):
            result = io.BytesIO(result)
        if result is not None and not getattr(result, "name", None):
            result.name = "banner.png"
        return result


class BannerLoaderLib(loader.Library):
    """
    Загрузчик PIL-баннеров. Скачивает код баннера, проверяет по правилам и отдаёт Banner.

    Баннер это любой файл с кодом Python, который можно выполнить (расширение не важно).

    Правила баннера
    ===============

    1. Мета-теги, все необязательные:

           # meta name: Название      название в списках (иначе последняя часть ссылки)
           # meta dev: @username      автор: ссылка на t.me
           # meta dev: oleg | insta.com/oleg    автор со своей ссылкой
           # meta dev: oleg           автор без ссылки
           # meta preview: https://...          картинка-превью

    2. Цветовые схемы, обязательно. Ключи цветов автор задаёт сам:

           themes = {
               "dark":  {"background": "#2C2D32", "main": "#FFFFFF"},
               "light": {"background": "#F2F3F5", "main": "#060607"},
           }

       Минимум одна тема, имя "custom" занято. Во всех темах одинаковые ключи,
       значения вида "#RGB" или "#RRGGBB". Первая тема базовая: тема custom
       меняет только те цвета, которые задал пользователь.

    3. Опции, по желанию: options = {"show_cover": True}. Только True или False.

    4. Отрисовка, обязательно:

           async def render(settings, data, font_bytes):
               return io.BytesIO(...) или bytes (PNG), None если рисовать нечего

       settings["colors"]    цвета выбранной темы
       settings["options"]   опции
       settings["dl_bytes"]  async dl_bytes(url) даёт bytes или None
       settings["dl_json"]   async dl_json(url) даёт данные JSON или None
       settings["dl_font"]   async dl_font(url) даёт bytes или None (с кэшем)
       data                  данные модуля (например, ответ Lanyard)
       font_bytes            шрифт пользователя или None (тогда баннер берёт свои через dl_font)

    Библиотеки баннера (PIL и т.д.) указывает модуль в мета-теге "# requires:".
    Код баннера выполняется со всеми правами юзербота: грузи только то, чему доверяешь.

    Использование
    =============

        banner = await self.banner_lib.load_banner(url)    # None, если не получилось (причина в логе)
        image = await banner.render(data, theme_name="dark")
    """

    developer = "@SunnexGB"

    strings = {
        "log_download": "Banner {url} was not downloaded",
        "log_exec": "Banner {url} failed to run",
        "log_rules": "Banner {url} breaks the rules: {errors}",
        "log_no_themes": "no themes dict",
        "log_no_render": "no async render(settings, data, font_bytes) function",
        "log_options": "options must be a dict of True or False",
        "log_theme_custom": 'theme name "custom" is reserved',
        "log_theme_dict": "theme {theme}: a dict of colors is required",
        "log_theme_keys": "theme {theme}: keys differ from theme {first}",
        "log_theme_color": "theme {theme}: {key} = {value} (need #RGB or #RRGGBB)",
        "log_color_key": "unknown key {key}",
        "log_color_value": "{key}: {value} (need #RGB or #RRGGBB)",
    }

    strings_ru = {
        "log_download": "Баннер {url} не скачался",
        "log_exec": "Баннер {url} не выполнился",
        "log_rules": "Баннер {url} нарушает правила: {errors}",
        "log_no_themes": "нет словаря themes",
        "log_no_render": "нет async функции render(settings, data, font_bytes)",
        "log_options": "options должен быть словарём с True или False",
        "log_theme_custom": 'имя темы "custom" занято',
        "log_theme_dict": "тема {theme}: нужен словарь цветов",
        "log_theme_keys": "тема {theme}: ключи отличаются от темы {first}",
        "log_theme_color": "тема {theme}: {key} = {value} (нужен #RGB или #RRGGBB)",
        "log_color_key": "неизвестный ключ {key}",
        "log_color_value": "{key}: {value} (нужен #RGB или #RRGGBB)",
    }

    def __init__(self):
        self.meta_get = re.compile(r"^#\s*meta\s+(\w+):\s*(.+)$")
        self.color_get = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
        self.session = None
        self.font_cache = {}

    async def init(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))

    async def close(self):
        if self.session is not None:
            await self.session.close()
            self.session = None

    # ------------------------------------------------------------------
    # Информация о баннере
    # ------------------------------------------------------------------

    def color_type(self, value):
        """Цвет вида #RGB или #RRGGBB."""
        return bool(self.color_get.match(value))

    def get_meta(self, source):
        """Мета-теги "# meta ключ: значение" из кода баннера."""
        matches = [self.meta_get.match(line.strip()) for line in source.split("\n")]
        return {
            match.group(1): match.group(2).strip()
            for match in matches
            if match
        }

    def get_author(self, dev):
        """
        Автор из "# meta dev". Возвращает (имя, ссылка или None).
        "@user" даёт ссылку на t.me, "имя | ссылка" берёт ссылку, "имя" без ссылки.
        """
        if not dev:
            return None, None

        name, _, link = dev.partition("|")
        name, link = name.strip(), link.strip()

        if link:
            return name, (link if "://" in link else "https://" + link)
        if name.startswith("@"):
            return name, "https://t.me/" + name[1:]
        return name, None

    def allowed_color_syntax(self, colors, allowed_names):
        """Проверяет цвета пользователя: ключ должен быть у баннера, значение быть цветом. Отдаёт ошибки."""
        for color_name, color_value in (colors or {}).items():
            if color_name not in allowed_names:
                yield self.strings["log_color_key"].format(key=color_name)
            elif not self.color_type(str(color_value)):
                yield self.strings["log_color_value"].format(key=color_name, value=color_value)

    # ------------------------------------------------------------------
    # Загрузка и проверка
    # ------------------------------------------------------------------

    async def load_banner(self, url):
        """Скачивает баннер. Возвращает Banner или None (причина в логе)."""
        source_bytes = await self.dl_bytes(url)
        if source_bytes is None:
            logger.error(self.strings["log_download"].format(url=url))
            return None

        return self.load_banner_source(source_bytes.decode("utf-8", errors="replace"), url)

    def load_banner_source(self, source, origin):
        """Выполняет код баннера и проверяет правила. Возвращает Banner или None (причина в логе)."""
        mod_w_banner = types.ModuleType("banner")
        try:
            exec(compile(source, origin, "exec"), mod_w_banner.__dict__)
        except Exception:
            logger.exception(self.strings["log_exec"].format(url=origin))
            return None

        error_syntax = list(self.fetch_error_syntax(mod_w_banner))
        if error_syntax:
            logger.error(self.strings["log_rules"].format(url=origin, errors="; ".join(error_syntax)))
            return None

        return Banner(self, origin, mod_w_banner, self.get_meta(source))

    def fetch_error_syntax(self, mod_w_banner):
        """Проверяет баннер по правилам. Отдаёт ошибки."""
        themes = getattr(mod_w_banner, "themes", None)
        if not isinstance(themes, dict) or not themes:
            yield self.strings["log_no_themes"]
        else:
            yield from self.fetch_theme_error_syntax(themes)

        if not asyncio.iscoroutinefunction(getattr(mod_w_banner, "render", None)):
            yield self.strings["log_no_render"]

        options = getattr(mod_w_banner, "options", None)
        if options is not None:
            is_dict = isinstance(options, dict)
            if not is_dict or not all(isinstance(value, bool) for value in options.values()):
                yield self.strings["log_options"]

    def fetch_theme_error_syntax(self, themes):
        """Проверяет themes: имя custom, одинаковые ключи, значения-цвета. Отдаёт ошибки."""
        if "custom" in themes:
            yield self.strings["log_theme_custom"]

        first_name = next(iter(themes))
        first_keys = set(themes[first_name]) if isinstance(themes[first_name], dict) else set()

        for theme_name, colors in themes.items():
            if not isinstance(colors, dict):
                yield self.strings["log_theme_dict"].format(theme=theme_name)
                continue

            if set(colors) != first_keys:
                yield self.strings["log_theme_keys"].format(theme=theme_name, first=first_name)

            for color_name, color_value in colors.items():
                if not self.color_type(str(color_value)):
                    yield self.strings["log_theme_color"].format(
                        theme=theme_name,
                        key=color_name,
                        value=color_value,
                    )

    # ------------------------------------------------------------------
    # Сеть
    # ------------------------------------------------------------------

    async def dl_bytes(self, url):
        """Скачивает файл. Возвращает bytes или None."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.read()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        return None

    async def dl_json(self, url):
        """Скачивает JSON. Возвращает данные или None."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            pass
        return None

    async def dl_font(self, url):
        """Скачивает шрифт один раз, дальше берёт из памяти."""
        if url not in self.font_cache:
            font_bytes = await self.dl_bytes(url)
            if font_bytes is None:
                return None
            self.font_cache[url] = font_bytes
        return self.font_cache[url]
