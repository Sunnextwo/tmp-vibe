import asyncio
import logging

from .. import loader
from ..inline.types import InlineMessage

logger = logging.getLogger(__name__)


class ConfigButtonsLib(loader.Library):
    """
    Добавляет свои кнопки на страницы конфига модуля (.cfg ИмяМодуля).
    Что за кнопки и что они делают, решает модуль, библиотека только держит их в форме.

    Использование. Куда поставить кнопки, задаёт первый аргумент:

        self.btns_lib = await self.import_lib("https://.../config_buttons.py")

        # просто имя модуля: кнопки в корне конфига (на странице со списком опций)
        self.btns_lib.set_cfg_btns("Discordo", self.root_btns)

        # имя модуля и опция через пробел: кнопки внутри страницы этой опции
        self.btns_lib.set_cfg_btns("Discordo font_url", self.font_btns)

        # mod_option=True: стандартные кнопки страницы (ввод, список значений, сброс) убираются
        self.btns_lib.set_cfg_btns("Discordo theme", self.theme_btns, mod_option=True)

        def font_btns(self, form_id):
            # form_id: номер открытой формы
            return [
                [{"text": "How to add", "url": "https://example.com/how_to_add"}],
                [{"text": "Ещё", "callback": self.on_press, "args": (form_id,)}],
            ]

    Функция возвращает клавиатуру: список рядов, ряд это список кнопок. None вместо кнопки
    и пустые ряды пропускаются. Её вызывают каждые interval секунд (настройка библиотеки):
    изменилась клавиатура, форма обновляется, нет, ничего не происходит.

    Кнопка: {"text": ..., "callback": async функция(call, *args), "args": (...)}
    или {"text": ..., "url": ...}. Тексты кнопок одного модуля должны быть разными.

    get_form(form_id) отдаёт форму (словарь с ключами "text", "buttons" и т.д.): модуль может
    читать текст формы. Если модуль положил в форму "disable_web_page_preview": False,
    библиотека правит эту форму с включённым предпросмотром ссылок (иначе при каждой правке
    кнопок предпросмотр пропал бы).
    """

    developer = "@SunnexGB"

    strings = {
        "interval_doc": "How often (in seconds) the library checks config forms",
        "log_forms": "Could not update config forms",
    }

    strings_ru = {
        "interval_doc": "Как часто (в секундах) библиотека проверяет формы конфига",
        "log_forms": "Не удалось обновить формы конфига",
    }

    def __init__(self):
        self.config = loader.LibraryConfig(
            loader.ConfigValue(
                "interval",
                1,
                lambda: self.strings["interval_doc"],
                validator=loader.validators.Integer(minimum=1),
            ),
        )
        self.watcher = None
        self.targets = {}    # {(модуль, опция или None): (функция с кнопками, заменять ли страницу)}
        self.mod_data = {}   # {(модуль, опция): надписи наших кнопок на заменяемой странице}
        self.btn_data = {}   # {модуль: надписи всех наших кнопок}

    async def init(self):
        self.watcher = asyncio.create_task(self.watch_forms())

    async def close(self):
        if self.watcher is not None:
            self.watcher.cancel()
            self.watcher = None

    def set_cfg_btns(self, target, btn_lists, mod_option=False):
        """
        Задаёт функцию btn_lists(form_id) с кнопками для страницы конфига.

        target:      "Модуль" это корень конфига, "Модуль опция" это страница опции
        mod_option:  True: стандартные кнопки страницы убираются, остаются только наши
        """
        module_name, _, option_name = target.partition(" ")
        self.targets[(module_name, option_name or None)] = (btn_lists, mod_option)

    def get_form(self, form_id):
        """Форма по номеру (словарь). Нет такой формы: пустой словарь."""
        return self._client.heroku_inline._units.get(form_id, {})

    def rm_cfg_btns(self, module_name):
        """Убирает все кнопки модуля (вызывай в on_unload)."""
        for page in [page for page in self.targets if page[0] == module_name]:
            del self.targets[page]
            self.mod_data.pop(page, None)
        self.btn_data.pop(module_name, None)

    # ------------------------------------------------------------------
    # Слежение за формами
    # ------------------------------------------------------------------

    async def watch_forms(self):
        while True:
            try:
                await self.update_forms()
            except Exception:
                logger.exception(self.strings["log_forms"])
            await asyncio.sleep(self.config["interval"])

    async def update_forms(self):
        for form_id, unit in list(self._client.heroku_inline._units.items()):
            page = self.get_form_page(unit)
            if page in self.targets:
                await self.update_form(form_id, unit, page)

    def get_form_page(self, unit):
        """
        Что показывает форма: (имя модуля, имя опции).
        Корень конфига модуля: (модуль, None). Не страница конфига модуля: (None, None).
        """
        btns = [btn for line in unit.get("buttons", []) for btn in line]

        # Страница заменена: стандартных кнопок на ней нет, узнаём по нашим кнопкам
        cur_data = {btn.get("text") for btn in btns}
        for page, data in self.mod_data.items():
            if cur_data & data:
                return page

        for btn in btns:
            if not self.is_cfg_btn(btn):
                continue

            args = btn.get("args") or ()
            kwargs = btn.get("kwargs") or {}

            # Страница опции: у её кнопок в args первыми идут модуль и опция
            if len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], str):
                return args[0], args[1]

            # Корень конфига: кнопки опций модуля. У списка модулей таких кнопок нет
            if getattr(btn["callback"], "__name__", "") == "inline__configure_option" and "mod" in kwargs:
                return kwargs["mod"], None

        return None, None

    def is_cfg_btn(self, btn):
        """Кнопку создал HerokuConfigMod."""
        owner = getattr(btn.get("callback"), "__self__", None)
        return type(owner).__name__ == "HerokuConfigMod"

    def describe(self, kb):
        """Кнопки клавиатуры в виде для сравнения: одинаковое описание, значит редактировать не нужно."""
        return [
            (btn.get("text"), btn.get("url"), btn.get("callback"), btn.get("args"))
            for line in kb
            for btn in line
        ]

    async def update_form(self, form_id, unit, page):
        """
        Клавиатура формы (kb) это список рядов, в ней три вида рядов:
          1. ряды конфига (опции, значения, листание), их делает HerokuConfigMod;
          2. наши ряды;
          3. последний ряд ("Назад" и "Закрыть"), он должен остаться внизу.
        Наши старые ряды убираем, актуальные ставим между рядами конфига и последним рядом.
        На заменяемой странице ряды конфига тоже убираются.
        """
        module_name = page[0]
        btn_lists, is_mod_option = self.targets[page]

        our_kb = [[btn for btn in line if btn] for line in btn_lists(form_id)]
        our_kb = [line for line in our_kb if line]
        our_data = {btn["text"] for line in our_kb for btn in line}

        # Надписи помним и для убранных кнопок: по ним отличаем наши ряды от рядов конфига
        all_data = self.btn_data.setdefault(module_name, set())
        all_data.update(our_data)
        if is_mod_option:
            self.mod_data.setdefault(page, set()).update(our_data)

        kb = unit.get("buttons", [])
        cfg_kb = [
            line for line in kb
            if not all(btn.get("text") in all_data for btn in line)
        ]
        if not cfg_kb:
            return

        back_line = cfg_kb[-1]
        above_kb = [] if is_mod_option else cfg_kb[:-1]
        new_kb = above_kb + our_kb + [back_line]

        if self.describe(new_kb) == self.describe(kb):
            return

        inline_message = InlineMessage(
            self._client.heroku_inline,
            form_id,
            unit.get("inline_message_id"),
        )
        edit_args = {}
        if unit.get("disable_web_page_preview") is False:
            edit_args["disable_web_page_preview"] = False

        await inline_message.edit(unit.get("text"), reply_markup=new_kb, **edit_args)
        unit["buttons"] = new_kb
