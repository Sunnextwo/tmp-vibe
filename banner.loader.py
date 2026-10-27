import asyncio
import io
import re
import types

import aiohttp

from .. import loader


class Banner:
    """
    Один загруженный баннер. Создаётся библиотекой: BannerLoaderLib.load_banner(url).

    Что можно узнать у баннера:
        banner.title            название (из "# meta name" или имя файла)
        banner.developer        автор (из "# meta dev") или None
        banner.preview_url      ссылка на превью (из "# meta preview") или None
        banner.theme_names      имена тем, например ["dark", "light"]
        banner.color_names      имена цветов, которые можно менять в теме custom
        banner.mode_names       имена режимов (пустой список, если режимов нет)
        banner.option_names     имена опций-переключателей
    """

    def __init__(self, lib, url, banner_module, meta):
        self.lib = lib
        self.url = url
        self.module = banner_module

        file_name = url.rsplit("/", 1)[-1].removesuffix(".py")
        self.title = meta.get("name") or file_name
        self.developer = meta.get("dev")
        self.preview_url = meta.get("preview")

        self.themes = banner_module.themes
        self.theme_names = list(banner_module.themes)
        self.color_names = list(banner_module.themes[self.theme_names[0]])
        self.mode_names = list(getattr(banner_module, "modes", []))
        self.option_defaults = dict(getattr(banner_module, "options", {}))
        self.option_names = list(self.option_defaults)

    # ------------------------------------------------------------------
    # Данные для рендера
    # ------------------------------------------------------------------

    def get_colors(self, theme_name, custom_pairs=None):
        """
        Цвета выбранной темы.

        Для темы "custom" берётся первая (базовая) тема баннера, а поверх неё
        применяются цвета из custom_pairs, например ["background_color:#1A1A2E"].
        Если такой темы нет, тоже берётся базовая.
        """
        if theme_name in self.themes:
            return dict(self.themes[theme_name])

        colors = dict(self.themes[self.theme_names[0]])
        custom_colors = self.lib.parse_pairs(custom_pairs)
        for color_name, color_value in custom_colors.items():
            if color_name in colors and self.lib.is_color(color_value):
                colors[color_name] = color_value
        return colors

    def get_options(self, option_pairs=None):
        """Опции баннера: значения по умолчанию, поверх них пары вида ["show_cover:false"]."""
        options = dict(self.option_defaults)
        chosen_options = self.lib.parse_pairs(option_pairs)
        for option_name, option_value in chosen_options.items():
            if option_name in options and self.lib.is_flag(option_value):
                options[option_name] = self.lib.flag_words[option_value.lower()]
        return options

    def pick_mode(self, mode_name):
        """Режим для рендера: запрошенный, если он есть у баннера, иначе первый. Нет режимов: None."""
        if not self.mode_names:
            return None
        if mode_name in self.mode_names:
            return mode_name
        return self.mode_names[0]

    def has_activity(self, data):
        """Есть ли в данных что показать. Спрашивает функцию has_activity у баннера; нет функции: True."""
        check = getattr(self.module, "has_activity", None)
        if check is None:
            return True
        return check(data)

    def find_config_problems(self, theme_name, custom_pairs=None, option_pairs=None):
        """Список проблем в настройках пользователя (неизвестные ключи, неверные значения)."""
        problems = []
        if theme_name == "custom":
            problems += self.lib.find_pair_problems(
                custom_pairs, self.color_names, self.lib.is_color, "#RGB или #RRGGBB"
            )
        problems += self.lib.find_pair_problems(
            option_pairs, self.option_names, self.lib.is_flag, "true или false"
        )
        return problems

    async def render(
        self,
        data,
        theme_name,
        custom_pairs=None,
        mode_name=None,
        option_pairs=None,
        font_url=None,
    ):
        """
        Рисует баннер. Возвращает io.BytesIO с PNG или None, если рисовать нечего.
        Ошибки внутри баннера не скрываются: их покажет сам юзербот.

        data:          данные для баннера (ответ Lanyard)
        theme_name:    имя темы или "custom"
        custom_pairs:  ["background_color:#1A1A2E", ...] цвета для темы "custom"
        mode_name:     имя режима (если у баннера есть режимы)
        option_pairs:  ["show_cover:false", ...] опции баннера
        font_url:      ссылка на свой шрифт .ttf (нет: баннер берёт свои шрифты)
        """
        font_bytes = None
        if font_url:
            font_bytes = await self.lib.fetch_font(font_url)

        settings = {
            "colors": self.get_colors(theme_name, custom_pairs),
            "mode": self.pick_mode(mode_name),
            "options": self.get_options(option_pairs),
            "fetch_bytes": self.lib.fetch_bytes,
            "fetch_font": self.lib.fetch_font,
        }

        result = await self.module.render(settings, data, font_bytes)

        if isinstance(result, bytes):
            result = io.BytesIO(result)
        if result is not None and not getattr(result, "name", None):
            result.name = "banner.png"
        return result



class BannerLoaderLib(loader.Library):
    """
    Загрузчик PIL-баннеров для модулей.

    Что делает:
      - скачивает .py файл баннера, проверяет его по правилам ниже и отдаёт объект Banner;
      - собирает цвета выбранной темы (в том числе пользовательской custom);
      - рисует баннер через Banner.render.

    Кнопки в конфиге модуля (автор, превью) делает отдельная библиотека config_buttons.

    =====================================================================
    ПРАВИЛА НАПИСАНИЯ БАННЕРА (обычный .py файл)
    =====================================================================

    1. Мета-теги. Все необязательные:

           # meta dev: @username          автор (модуль может показать его кнопкой)
           # meta name: Название баннера  так баннер называется в конфиге (иначе имя файла)
           # meta preview: https://...    картинка-превью (модуль может показать её кнопкой)

    2. Цветовые схемы (обязательно). Словарь themes:

           themes = {
               "dark":  {"background_color": "#2C2D32", "text_color": "#FFFFFF"},
               "light": {"background_color": "#F2F3F5", "text_color": "#060607"},
           }

       - минимум одна тема;
       - имя "custom" занято: так называется тема пользователя;
       - все ключи оканчиваются на _color, значения вида "#RGB" или "#RRGGBB";
       - во всех темах одинаковый набор ключей;
       - первая тема считается базовой: custom-тема пользователя меняет
         только те цвета, которые он задал, остальные берутся из базовой.

    3. Режимы (необязательно). Список строк, первый используется по умолчанию:

           modes = ["card", "compact"]

       Выбранный режим приходит в render как settings["mode"]
       (если режимов нет, там будет None).

    4. Опции-переключатели (необязательно). Словарь "имя: включено ли по умолчанию",
       значения только True или False:

           options = {"show_cover": True, "show_status": True}

       Итоговые значения приходят в render как settings["options"]
       (всегда со всеми ключами из options).

    5. Функция отрисовки (обязательно):

           async def render(settings, data, font_bytes):
               ...
               return io.BytesIO(...) или bytes (PNG), либо None, если рисовать нечего

       settings["colors"]       словарь цветов выбранной темы
       settings["mode"]         имя режима или None
       settings["options"]      словарь опций
       settings["fetch_bytes"]  async функция: await fetch_bytes(url) даёт bytes или None (картинки и т.п.)
       settings["fetch_font"]   async функция: await fetch_font(url) даёт bytes или None (с кэшем)
       data                     данные, которые передал модуль (например, ответ Lanyard)
       font_bytes               байты шрифта, который выбрал пользователь, или None;
                                если None, баннер берёт свои шрифты через fetch_font

       Библиотеки (PIL, cairosvg и т.д.) баннер импортирует сам: модуль, который его
       использует, должен указать их в "# requires:".

    6. Проверка данных (необязательно):

           def has_activity(data):
               return True или False

       Модуль спрашивает это через banner.has_activity(data) до рендера, чтобы
       ответить "нечего показывать", а не получить пустой результат. Без этой функции
       has_activity всегда возвращает True.

    ВНИМАНИЕ: файл баннера выполняется как обычный Python-код со всеми правами
    юзербота. Загружай баннеры только из источников, которым доверяешь.

    =====================================================================
    ИСПОЛЬЗОВАНИЕ В МОДУЛЕ
    =====================================================================

        banner = await self.banner_lib.load_banner("https://.../banner.py")

        banner.title, banner.developer, banner.preview_url   данные из мета-тегов
        banner.theme_names, banner.color_names               темы и ключи цветов

        if banner.has_activity(data):
            image = await banner.render(data, theme_name="dark")
    """

    developer = "@SunnexGB"

    def __init__(self):
        # Шаблоны для разбора текста
        self.meta_parse = re.compile(r"^#\s*meta\s+(\w+):\s*(.+)$")           # "# meta dev: @name"
        self.pair_parse = re.compile(r"^\s*([\w-]+)\s*[:=]\s*(\S.*?)\s*$")    # "ключ:значение"
        self.color_parse = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")  # "#RGB" или "#RRGGBB"
        self.flag_words = {
            "true": True, "false": False,
            "yes": True, "no": False,
            "on": True, "off": False,
            "1": True, "0": False,
        }

        # Состояние
        self.session = None
        self.font_cache = {}

    async def init(self):
        """Создаёт сетевую сессию."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))

    async def close(self):
        """Закрывает сетевую сессию."""
        if self.session is not None:
            await self.session.close()
            self.session = None

    # ------------------------------------------------------------------
    # Разбор текста
    # ------------------------------------------------------------------

    def is_color(self, value):
        """Цвет вида #RGB или #RRGGBB."""
        return bool(self.color_parse.match(value))

    def is_flag(self, value):
        """Значение true или false (также yes/no, on/off, 1/0)."""
        return value.lower() in self.flag_words

    def parse_meta(self, source):
        """Читает строки "# meta ключ: значение" из исходника баннера. Возвращает словарь."""
        matches = [self.meta_parse.match(line.strip()) for line in source.split("\n")]
        return {match.group(1): match.group(2).strip() for match in matches if match}

    def parse_pairs(self, pairs):
        """
        Превращает список строк "ключ:значение" (или "ключ=значение") в словарь.
        Строки неверного формата пропускаются.
        """
        matches = [self.pair_parse.match(str(pair)) for pair in pairs or []]
        return {match.group(1): match.group(2) for match in matches if match}

    def find_pair_problems(self, pairs, allowed_names, value_is_valid, value_hint):
        """Проверяет пары из конфига. По одной строке на каждую найденную проблему."""
        for pair in pairs or []:
            if not self.pair_parse.match(str(pair)):
                yield f"«{pair}» не похоже на ключ:значение"

        for name, value in self.parse_pairs(pairs).items():
            if name not in allowed_names:
                yield f"неизвестный ключ {name}"
            elif not value_is_valid(value):
                yield f"{name}: {value} (нужно {value_hint})"

    # ------------------------------------------------------------------
    # Загрузка и проверка баннеров
    # ------------------------------------------------------------------

    async def load_banner(self, url):
        """Скачивает баннер по ссылке. Возвращает Banner или бросает ValueError."""
        source_bytes = await self.fetch_bytes(url)
        if source_bytes is None:
            raise ValueError(f"Не удалось скачать баннер: {url}")
        return self.load_banner_source(source_bytes.decode("utf-8"), url)

    def load_banner_source(self, source, origin):
        """
        Выполняет код баннера и проверяет правила. Возвращает Banner.
        Если правила нарушены, бросает ValueError со списком проблем.
        """
        banner_module = types.ModuleType("banner")
        exec(compile(source, origin, "exec"), banner_module.__dict__)

        problems = list(self.find_banner_problems(banner_module))
        if problems:
            problem_lines = "\n".join(f"- {problem}" for problem in problems)
            raise ValueError(f"Баннер {origin} нарушает правила:\n{problem_lines}")

        return Banner(self, origin, banner_module, self.parse_meta(source))

    def find_banner_problems(self, banner_module):
        """Проверяет баннер по правилам. По одной строке на каждую найденную проблему."""
        themes = getattr(banner_module, "themes", None)
        if not isinstance(themes, dict) or not themes:
            yield "нет словаря themes (нужна хотя бы одна тема)"
        else:
            yield from self.find_theme_problems(themes)

        if not asyncio.iscoroutinefunction(getattr(banner_module, "render", None)):
            yield "нет async функции render(settings, data, font_bytes)"

        modes = getattr(banner_module, "modes", None)
        if modes is not None:
            modes_are_strings = isinstance(modes, list) and all(isinstance(mode, str) for mode in modes)
            if not modes_are_strings or not modes:
                yield "modes должен быть непустым списком строк"

        options = getattr(banner_module, "options", None)
        if options is not None:
            options_are_flags = isinstance(options, dict) and all(isinstance(value, bool) for value in options.values())
            if not options_are_flags:
                yield "options должен быть словарём с True или False"

    def find_theme_problems(self, themes):
        """Проверяет словарь themes. По одной строке на каждую найденную проблему."""
        if "custom" in themes:
            yield 'имя темы "custom" зарезервировано'

        first_theme_name = next(iter(themes))
        first_theme = themes[first_theme_name]
        first_color_names = set(first_theme) if isinstance(first_theme, dict) else set()

        for theme_name, colors in themes.items():
            if not isinstance(colors, dict):
                yield f"тема {theme_name}: должна быть словарём цветов"
                continue

            if set(colors) != first_color_names:
                yield f"тема {theme_name}: набор ключей отличается от темы {first_theme_name}"

            for color_name, color_value in colors.items():
                if not color_name.endswith("_color"):
                    yield f"тема {theme_name}: ключ {color_name} должен оканчиваться на _color"
                if not self.is_color(str(color_value)):
                    yield f"тема {theme_name}: {color_name} = {color_value} (нужен #RGB или #RRGGBB)"

    # ------------------------------------------------------------------
    # Сеть
    # ------------------------------------------------------------------

    async def fetch_bytes(self, url):
        """Скачивает файл. Возвращает bytes или None, если не получилось."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.read()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        return None

    async def fetch_json(self, url):
        """Скачивает JSON. Возвращает данные или None, если не получилось."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            pass
        return None

    async def fetch_font(self, url):
        """Скачивает шрифт и запоминает его, повторно по сети не ходит."""
        if url not in self.font_cache:
            font_bytes = await self.fetch_bytes(url)
            if font_bytes is None:
                return None
            self.font_cache[url] = font_bytes
        return self.font_cache[url]