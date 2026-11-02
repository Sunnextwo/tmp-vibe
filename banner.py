# requires: pillow cairosvg aiohttp

import contextlib
import json
import logging

from .. import loader, utils

logger = logging.getLogger(__name__)


@loader.tds
class Discordo(loader.Module):
    """Discord Rich Presence banner via Lanyard API"""

    strings = {
        "name": "Discordo",
        "banner_not_ready": "<b>Banner is not loaded.</b> See the logs for details.",
        "no_data": "<b>Could not get data from Lanyard.</b>",
        "nothing": "No activities at the moment...",
        "ctheme_usage": (
            '<b>Usage:</b> <code>.ctheme name {{"key": "value"}}</code>\n'
            "Pass colors in the command, as a reply to a message or to a .json file.\n"
            "Without a name the selected banner is used.\n\n"
            "<b>Banners:</b> {titles}\n"
            "<b>Keys of the selected banner:</b> {keys}"
        ),
        "ctheme_unknown_banner": "<b>No such banner.</b>\n<b>Banners:</b> {titles}",
        "ctheme_bad_json": '<b>Could not parse JSON.</b> Expected: <code>{"key": "value"}</code>',
        "ctheme_error": "<b>Colors were not saved.</b> See the logs for details.",
        "ctheme_saved": "<b>Custom theme colors saved:</b> {count}",
        "theme_btn": "{theme_name}",
        "theme_btn_selected": "{theme_name} <",
        "theme_chosen": "Theme: {theme_name}",
        "preview_show": "Show preview: {cursor}",
        "preview_hide": "Hide preview: {cursor}",
        "author_btn": "Author: {name}",
        "author_btn_cursor": "Author {cursor}: {name}",
        "user_id_doc": "Discord user ID (must be in Lanyard)",
        "banners_doc": "Selected banner",
        "user_banners_doc": "Your banners: links to the banner code (rules: see banner_loader.py)",
        "theme_doc": "Banner theme (the list comes from the selected banner, own colors: .ctheme command)",
        "font_url_doc": "Own .ttf font (empty: the banner uses its own fonts)",
        "log_preview": "Could not change the preview",
        "log_colors": "Invalid colors of the custom theme: {errors}",
    }

    strings_ru = {
        "_cls_doc": "Discord Rich Presence баннер через Lanyard API",
        "_cmd_doc_discordo": "Показать Discord Presence баннер",
        "_cmd_doc_ctheme": '<название> {"ключ": "значение"} - цвета темы custom для баннера (текстом, ответом на сообщение или .json файл)',
        "banner_not_ready": "<b>Баннер не загружен.</b> Подробности в логах.",
        "no_data": "<b>Не удалось получить данные из Lanyard.</b>",
        "nothing": "В данный момент активностий не наблюдается...",
        "ctheme_usage": (
            '<b>Использование:</b> <code>.ctheme название {{"ключ": "значение"}}</code>\n'
            "Цвета можно передать текстом команды, ответом на сообщение или на .json файл.\n"
            "Без названия берётся выбранный баннер.\n\n"
            "<b>Баннеры:</b> {titles}\n"
            "<b>Ключи выбранного баннера:</b> {keys}"
        ),
        "ctheme_unknown_banner": "<b>Нет такого баннера.</b>\n<b>Баннеры:</b> {titles}",
        "ctheme_bad_json": '<b>Не удалось разобрать JSON.</b> Нужен вид: <code>{"ключ": "значение"}</code>',
        "ctheme_error": "<b>Цвета не сохранены.</b> Подробности в логах.",
        "ctheme_saved": "<b>Цвета темы custom сохранены:</b> {count}",
        "theme_btn": "{theme_name}",
        "theme_btn_selected": "{theme_name} <",
        "theme_chosen": "Тема: {theme_name}",
        "preview_show": "Показать превью: {cursor}",
        "preview_hide": "Скрыть превью: {cursor}",
        "author_btn": "Автор: {name}",
        "author_btn_cursor": "Автор {cursor}: {name}",
        "user_id_doc": "Discord user ID (должен быть в Lanyard)",
        "banners_doc": "Выбранный баннер",
        "user_banners_doc": "Свои баннеры: ссылки на код баннера (правила: в banner_loader.py)",
        "theme_doc": "Тема баннера (список берётся из выбранного баннера, свои цвета: команда .ctheme)",
        "font_url_doc": "Свой шрифт .ttf (пусто: баннер использует свои шрифты)",
        "log_preview": "Не удалось изменить превью",
        "log_colors": "Неверные цвета темы custom: {errors}",
    }

    def __init__(self):
        # Встроенные баннеры, несколько можно перечислить через запятую.
        # Первый называется Core, остальные по "# meta name".
        self.default_banner_url = "https://ваш.сервер/pillow_banner.py"
        self.core_urls = [url.strip() for url in self.default_banner_url.split(",")]
        self.lanyard_api = "https://api.lanyard.rest/v1/users/"
        self.banner_lib = None
        self.btns_lib = None

        self.banners = {}          # {название: Banner} скачанные в этот запуск
        self.banner_info = {}      # {название: данные о баннере}, копия лежит в базе
        self.custom_themes = {}    # {название: {ключ цвета: цвет}}, задаются командой .ctheme

        # Списки для Choice: после загрузки баннеров заполняются на месте
        self.banner_titles = ["Core"]
        self.theme_names = ["dark", "light", "custom"]

        self.config = loader.ModuleConfig(
            loader.ConfigValue(
                "user_id",
                "1556425322256142468",
                lambda: self.strings["user_id_doc"],
                validator=loader.validators.String(),
            ),
            loader.ConfigValue(
                "banners",
                "Core",
                lambda: self.strings["banners_doc"],
                validator=loader.validators.Choice(self.banner_titles),
                on_change=self.on_banner_change,
            ),
            loader.ConfigValue(
                "user_banners",
                [],
                lambda: self.strings["user_banners_doc"],
                validator=loader.validators.Series(),
                on_change=self.reload_banners,
            ),
            loader.ConfigValue(
                "theme",
                "dark",
                lambda: self.strings["theme_doc"],
                validator=loader.validators.Choice(self.theme_names),
            ),
            loader.ConfigValue(
                "font_url",
                "",
                lambda: self.strings["font_url_doc"],
                validator=loader.validators.String(),
            ),
        )

    async def client_ready(self, client, db):
        self.custom_themes = self.get("custom_themes", {})

        self.banner_lib = await self.import_lib(
            "https://ваш.сервер/banner_loader.py",
            suspend_on_error=True,
        )
        self.btns_lib = await self.import_lib(
            "https://ваш.сервер/config_buttons.py",
            suspend_on_error=True,
        )

        # Кнопки ставятся на страницы опций: "Модуль опция". Просто "Модуль" это корень конфига
        name = self.strings["name"]
        self.btns_lib.set_cfg_btns(f"{name} theme", self.theme_btns, mod_option=True)
        self.btns_lib.set_cfg_btns(f"{name} banners", self.banners_btns)
        self.btns_lib.set_cfg_btns(f"{name} user_banners", self.user_banners_btns)

        await self.load_banners()
        self.restore_saved_choices()

    async def on_unload(self):
        self.btns_lib.rm_cfg_btns(self.strings["name"])

    # ------------------------------------------------------------------
    # Баннеры
    # ------------------------------------------------------------------

    async def load_banners(self):
        """Скачивает баннеры, запоминает данные о них в базе, обновляет списки выбора в конфиге."""
        cache = self.get("banner_cache", {})
        self.banners = {}
        self.banner_info = {}

        for url in self.core_urls + list(self.config["user_banners"]):
            banner = await self.banner_lib.load_banner(url)

            if banner is None:
                info = cache.get(url)   # не скачался: берём, что запомнили раньше
                if info:
                    title = self.pick_title(url, info["title"])
                    self.banner_info[title] = dict(info, title=title)
                continue

            title = self.pick_title(url, banner.title)
            self.banners[title] = banner
            self.banner_info[title] = {
                "url": url,
                "title": title,
                "author_name": banner.author_name,
                "author_url": banner.author_url,
                "preview": banner.preview_url,
                "theme_names": banner.theme_names,
                "color_names": banner.color_names,
            }

        self.set("banner_cache", {info["url"]: info for info in self.banner_info.values()})

        if self.banner_info:
            self.refresh_choice("banners", self.banner_titles, list(self.banner_info))
            self.refresh_banner_choices()

    def pick_title(self, url, banner_title):
        """Первый встроенный баннер всегда Core (значение по умолчанию остаётся допустимым). Повтор названия получает номер."""
        if url == self.core_urls[0]:
            return "Core"
        if banner_title in self.banner_info or banner_title == "Core":
            return f"{banner_title} ({len(self.banner_info) + 1})"
        return banner_title

    async def reload_banners(self):
        if self.banner_lib is not None:
            await self.load_banners()

    def current_banner(self):
        return self.banners.get(self.config["banners"])

    def current_info(self):
        return self.banner_info.get(self.config["banners"])

    # ------------------------------------------------------------------
    # Списки выбора в конфиге
    # ------------------------------------------------------------------

    async def on_banner_change(self):
        self.refresh_banner_choices()

    def refresh_banner_choices(self):
        """Темы в конфиге берутся из выбранного баннера (плюс custom)."""
        info = self.current_info()
        if info is not None:
            self.refresh_choice("theme", self.theme_names, info["theme_names"] + ["custom"])

    def refresh_choice(self, option_name, choice_list, new_values):
        """Заменяет значения списка на месте. Текущее значение пропало: берёт первое."""
        choice_list[:] = new_values
        if self.config[option_name] not in new_values:
            self.config[option_name] = new_values[0]

    def restore_saved_choices(self):
        """
        Конфиг читается из базы раньше, чем загружаются баннеры, поэтому сохранённые
        баннер и тема сбрасывались на значения по умолчанию. В базе они остались.
        """
        saved_config = self.get("__config__", {})

        with contextlib.suppress(loader.validators.ValidationError):
            self.config["banners"] = saved_config.get("banners", self.config["banners"])
        self.refresh_banner_choices()
        with contextlib.suppress(loader.validators.ValidationError):
            self.config["theme"] = saved_config.get("theme", self.config["theme"])

    # ------------------------------------------------------------------
    # Кнопки в конфиге
    # ------------------------------------------------------------------

    def theme_btns(self, form_id):
        """Страница theme: только темы выбранного баннера (страница заменяется целиком)."""
        return [[self.theme_btn(theme_name)] for theme_name in self.theme_names]

    def banners_btns(self, form_id):
        """Страница banners: превью и под ним автор выбранного баннера."""
        info = self.current_info()
        return [
            [self.preview_btn(form_id, info)],
            [self.author_btn(info, "author_btn")],
        ]

    def user_banners_btns(self, form_id):
        """Страница user_banners: превью и автор каждого добавленного пользовательского баннера."""
        kb = []
        for info in self.banner_info.values():
            if info["url"] in self.config["user_banners"]:
                kb += [
                    [self.preview_btn(form_id, info)],
                    [self.author_btn(info, "author_btn_cursor")],
                ]
        return kb

    def theme_btn(self, theme_name):
        text_key = "theme_btn_selected" if theme_name == self.config["theme"] else "theme_btn"
        return {
            "text": self.strings[text_key].format(theme_name=theme_name.capitalize()),
            "callback": self.choose_theme,
            "args": (theme_name,),
        }

    async def choose_theme(self, call, theme_name):
        self.config["theme"] = theme_name
        await call.answer(self.strings["theme_chosen"].format(theme_name=theme_name.capitalize()))

    def preview_link(self, url):
        """Скрытая ссылка в начале текста формы: Telegram показывает по ней предпросмотр картинки."""
        return f'<a href="{utils.escape_html(url)}">\u200b</a>'

    def preview_label(self, url, title, form_text):
        """Надпись кнопки: превью уже показано в форме (ссылка есть в её тексте) или нет."""
        text_key = "preview_hide" if self.preview_link(url) in form_text else "preview_show"
        return self.strings[text_key].format(cursor=title)

    def preview_btn(self, form_id, info):
        """Кнопка показать / скрыть превью баннера. Нет баннера или "# meta preview": None."""
        if not info or not info["preview"]:
            return None

        form_text = self.btns_lib.get_form(form_id).get("text", "")
        return {
            "text": self.preview_label(info["preview"], info["title"], form_text),
            "callback": self.toggle_preview,
            "args": (info["preview"], info["title"]),
        }

    async def toggle_preview(self, call, url, title):
        """
        Превью это предпросмотр ссылки: добавили скрытую ссылку в текст формы, он появился,
        убрали, он исчез. Прикреплённую картинку скрыть было бы нельзя: Telegram не убирает
        фото из сообщения. Одновременно в форме может быть превью только одного баннера.
        """
        form = call.form
        link = self.preview_link(url)
        is_shown = link in form["text"]

        text = form["text"]
        for info in self.banner_info.values():
            if info["preview"]:
                text = text.replace(self.preview_link(info["preview"]), "")
        if not is_shown:
            text = link + text

        # Надписи кнопок меняем в этой же правке: иначе библиотека перерисует форму
        # отдельной правкой, и Telegram уберёт предпросмотр
        for line in form["buttons"]:
            for btn in line:
                if btn.get("callback") == self.toggle_preview:
                    btn["text"] = self.preview_label(*btn["args"], text)

        # Состояние формы меняем до правки: библиотека проверяет форму по таймеру,
        # и не должна успеть перерисовать её по старому тексту
        old_text = form["text"]
        old_flag = form.get("disable_web_page_preview")
        form["text"] = text
        form["disable_web_page_preview"] = is_shown

        try:
            await call.edit(text, reply_markup=form["buttons"], disable_web_page_preview=is_shown)
        except Exception:
            logger.exception(self.strings["log_preview"])
            form["text"] = old_text
            form["disable_web_page_preview"] = old_flag
            await call.answer(url, show_alert=True)

    def author_btn(self, info, text_key):
        """Кнопка автора: со ссылкой, если она есть, иначе просто надпись. Нет "# meta dev": None."""
        if not info or not info["author_name"]:
            return None

        text = self.strings[text_key].format(name=info["author_name"], cursor=info["title"])
        if info["author_url"]:
            return {
                "text": text,
                "url": info["author_url"],
            }
        return {
            "text": text,
            "callback": self.ignore_press,
        }

    async def ignore_press(self, call):
        await call.answer()

    # ------------------------------------------------------------------
    # Команда .discordo
    # ------------------------------------------------------------------

    async def data_lanyard(self):
        """Данные пользователя из Lanyard или None."""
        response = await self.banner_lib.dl_json(self.lanyard_api + self.config["user_id"])
        if not response or not response.get("success"):
            return None
        return response.get("data")

    @loader.command()
    async def discordo(self, message):
        """Show the Discord Presence banner"""
        banner = self.current_banner()
        if banner is None:
            await utils.answer(message, self.strings["banner_not_ready"])
            return

        data = await self.data_lanyard()
        if not data:
            await utils.answer(message, self.strings["no_data"])
            return

        theme_name = self.config["theme"]
        custom_colors = self.custom_themes.get(self.config["banners"], {})

        error_syntax = banner.fetch_cfg_error_syntax(theme_name, custom_colors)
        if error_syntax:
            logger.error(self.strings["log_colors"].format(errors="; ".join(error_syntax)))

        image = await banner.render(
            data,
            theme_name=theme_name,
            custom_colors=custom_colors,
            font_url=self.config["font_url"],
        )
        if image is None:
            await utils.answer(message, self.strings["nothing"])
            return

        await utils.answer(message, "", file=image)

    # ------------------------------------------------------------------
    # Команда .ctheme
    # ------------------------------------------------------------------

    @loader.command()
    async def ctheme(self, message):
        """<name> {"key": "value"} - custom theme colors for a banner (in the command, as a reply to a message or to a .json file)"""
        args = utils.get_args_raw(message)

        # Название идёт до JSON, а JSON начинается с первой фигурной скобки
        json_start = args.find("{")
        if json_start == -1:
            title_str, json_str = args, ""
        else:
            title_str, json_str = args[:json_start], args[json_start:]

        title = self.fetch_title(title_str.strip())
        if title is None:
            await utils.answer(
                message,
                self.strings["ctheme_unknown_banner"].format(
                    titles=utils.escape_html(", ".join(self.banner_info)),
                ),
            )
            return

        await self.save_theme(message, title, json_str)

    def fetch_title(self, name):
        """Название баннера из команды без учёта регистра. Пусто: выбранный. Нет такого: None."""
        name = name or self.config["banners"]
        for title in self.banner_info:
            if title.lower() == name.lower():
                return title
        return None

    async def save_theme(self, message, title, json_str):
        """
        Читает цвета темы custom (из команды, а если их там нет, из сообщения или .json файла,
        на которое ответили), проверяет и записывает в базу.
        """
        reply = await message.get_reply_message()
        if not json_str and reply is not None:
            if reply.file:
                json_str = (await reply.download_media(bytes)).decode("utf-8", errors="ignore")
            else:
                json_str = reply.raw_text or ""

        info = self.banner_info[title]
        if not json_str.strip():
            await utils.answer(
                message,
                self.strings["ctheme_usage"].format(
                    titles=utils.escape_html(", ".join(self.banner_info)),
                    keys=utils.escape_html(", ".join(info["color_names"])),
                ),
            )
            return

        try:
            colors = json.loads(json_str)
        except ValueError:
            colors = None
        if not isinstance(colors, dict):
            await utils.answer(message, self.strings["ctheme_bad_json"])
            return

        error_syntax = list(self.banner_lib.allowed_color_syntax(colors, info["color_names"]))
        if error_syntax:
            logger.error(self.strings["log_colors"].format(errors="; ".join(error_syntax)))
            await utils.answer(message, self.strings["ctheme_error"])
            return

        self.custom_themes[title] = colors
        self.set("custom_themes", self.custom_themes)
        if title == self.config["banners"]:
            self.config["theme"] = "custom"

        await utils.answer(message, self.strings["ctheme_saved"].format(count=len(colors)))
