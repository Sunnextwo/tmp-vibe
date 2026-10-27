import asyncio

from .. import loader
from ..inline.types import InlineMessage


class ConfigButtonsLib(loader.Library):
    """
    Добавляет свои кнопки на страницы конфига модуля (.cfg ИмяМодуля).

    Конфиг состоит из страниц: главная (список опций) и по странице на каждую опцию.
    Модуль говорит, какие кнопки нужны на какой странице, а библиотека следит
    за открытыми формами и держит эти кнопки на месте.

    =====================================================================
    ИСПОЛЬЗОВАНИЕ В МОДУЛЕ
    =====================================================================

        self.buttons_lib = await self.import_lib("https://.../config_buttons.py")
        self.buttons_lib.set_config_buttons(self.strings["name"], self.config_buttons)

        def config_buttons(self, option_name):
            # option_name: имя опции, страница которой открыта (None: главная страница)
            if option_name != "banners":
                return []
            return [[
                self.buttons_lib.author_button("Автор", "Автор: {developer}", "@username"),
                self.buttons_lib.preview_button("Превью", "https://.../preview.png"),
            ]]

    Функция возвращает список рядов, а ряд это список кнопок. Библиотека вызывает её
    раз в секунду: новые кнопки появляются, а пропавшие из списка убираются.
    Поэтому кнопки могут зависеть от настроек. None вместо кнопки и пустые ряды
    пропускаются.

    Кнопка это словарь {"text": ..., "callback": async функция(call, *args), "args": (...)}
    или {"text": ..., "url": ...}. Тексты кнопок одного модуля должны быть разными.

    Готовые кнопки:
        author_button(text, alert_text, developer)   всплывающее окно с автором
        preview_button(text, preview_url)            прикрепляет картинку к форме
    """

    developer = "@SunnexGB"

    def __init__(self):
        self.watcher = None
        self.button_providers = {}   # {имя модуля: функция, которая отдаёт кнопки}
        self.our_texts = {}          # {имя модуля: тексты кнопок, которые мы уже ставили}
        self.form_error = None       # последняя ошибка при обновлении формы (для отладки)

    async def init(self):
        """Запускает слежение за формами конфига."""
        self.watcher = asyncio.create_task(self.watch_forms())

    async def close(self):
        """Останавливает слежение."""
        if self.watcher is not None:
            self.watcher.cancel()
            self.watcher = None

    def set_config_buttons(self, module_name, provider):
        """
        Задаёт функцию, которая возвращает кнопки для страниц конфига модуля.
        Функция получает имя опции открытой страницы (или None для главной)
        и возвращает список рядов кнопок.
        """
        self.button_providers[module_name] = provider

    # ------------------------------------------------------------------
    # Готовые кнопки
    # ------------------------------------------------------------------

    def author_button(self, text, alert_text, developer):
        """
        Кнопка с именем автора. Автора нет: возвращает None.

        text:        надпись на кнопке
        alert_text:  текст всплывающего окна, в нём можно написать {developer}
        developer:   имя автора
        """
        if not developer:
            return None
        return {"text": text, "callback": self.show_author, "args": (alert_text, developer)}

    def preview_button(self, text, preview_url):
        """Кнопка, которая прикрепляет картинку к форме. Картинки нет: возвращает None."""
        if not preview_url:
            return None
        return {"text": text, "callback": self.show_preview, "args": (preview_url,)}

    async def show_author(self, call, alert_text, developer):
        """Нажатие на кнопку автора: всплывающее окно."""
        await call.answer(alert_text.format(developer=developer), show_alert=True)

    async def show_preview(self, call, preview_url):
        """
        Нажатие на кнопку превью: прикрепляет картинку к форме.
        Если Telegram или юзербот не дали прикрепить, показывает ссылку всплывающим окном.
        """
        form = call.form
        try:
            await call.edit(form["text"], reply_markup=form["buttons"], photo=preview_url)
        except Exception:
            await call.answer(preview_url, show_alert=True)

    # ------------------------------------------------------------------
    # Слежение за формами конфига
    # ------------------------------------------------------------------

    async def watch_forms(self):
        """Бесконечный цикл: проверяет формы сразу, а потом каждую секунду."""
        while True:
            try:
                await self.update_all_forms()
            except Exception as error:
                self.form_error = error
            await asyncio.sleep(1)

    async def update_all_forms(self):
        """Находит открытые формы конфига модулей, для которых заданы кнопки, и обновляет их."""
        inline_manager = self._client.heroku_inline

        for unit_id, unit in list(inline_manager._units.items()):
            module_name, option_name = self.get_form_page(unit)
            if module_name in self.button_providers:
                await self.update_form(unit_id, unit, module_name, option_name)

    def get_form_page(self, unit):
        """
        Что показывает форма. Возвращает (имя модуля, имя опции).

        Форма не от конфига: (None, None).
        Главная страница модуля (список опций): (имя модуля, None).
        Страница опции: (имя модуля, имя опции). У её кнопок в args первыми
        идут имя модуля и имя опции, например ("Discordo", "theme", ...).
        """
        buttons = [button for row in unit.get("buttons", []) for button in row]

        module_name = self.get_module_name(buttons)
        if module_name is None:
            return None, None

        for button in buttons:
            args = button.get("args") or ()
            if len(args) >= 2 and args[0] == module_name and isinstance(args[1], str):
                return module_name, args[1]

        return module_name, None

    def get_module_name(self, buttons):
        """
        Имя модуля, если среди кнопок есть кнопка конфига (её создал HerokuConfigMod).
        Иначе None. Имя берётся из параметров этой кнопки.
        """
        for button in buttons:
            owner = getattr(button.get("callback"), "__self__", None)
            if type(owner).__name__ != "HerokuConfigMod":
                continue

            keyword_args = button.get("kwargs") or {}
            positional_args = button.get("args") or ()

            if "mod" in keyword_args:
                return keyword_args["mod"]
            if positional_args and isinstance(positional_args[0], str):
                return positional_args[0]

        return None

    def describe_buttons(self, rows):
        """
        Список кнопок формы в виде, удобном для сравнения. Две формы с одинаковым
        описанием выглядят и работают одинаково, редактировать сообщение не нужно.
        """
        return [
            (button.get("text"), button.get("url"), button.get("callback"), button.get("args"))
            for row in rows
            for button in row
        ]

    async def update_form(self, unit_id, unit, module_name, option_name):
        """
        Ставит в форму кнопки, которые модуль хочет видеть на этой странице.

        Форма это список рядов, а ряд это список кнопок. В ней три вида рядов:
          1. ряды самого конфига (опции, значения, листание страниц), их делает HerokuConfigMod;
          2. наши ряды (автор, превью и т.п.);
          3. самый последний ряд формы ("Назад" и "Закрыть"), он тоже от HerokuConfigMod
             и должен остаться в самом низу.

        Что делаем: убираем из формы наши старые ряды, а актуальные вставляем
        между рядами конфига и последним рядом.
        """
        provided_rows = self.button_providers[module_name](option_name)
        wanted_rows = [[button for button in row if button] for row in provided_rows]
        wanted_rows = [row for row in wanted_rows if row]

        # Запоминаем тексты наших кнопок: по ним отличаем наши ряды от рядов конфига.
        # Кнопки, которых уже нет в списке, остаются в памяти, поэтому они тоже убираются.
        texts = self.our_texts.setdefault(module_name, set())
        texts.update(button["text"] for row in wanted_rows for button in row)

        current_rows = unit.get("buttons", [])
        config_rows = [
            row for row in current_rows
            if not all(button.get("text") in texts for button in row)
        ]
        if not config_rows:
            return

        navigation_row = config_rows[-1]          # последний ряд формы: "Назад" и "Закрыть"
        rows_above_navigation = config_rows[:-1]  # все ряды конфига выше него (всё, кроме последнего)

        new_rows = rows_above_navigation + wanted_rows + [navigation_row]

        # Ничего не изменилось: сообщение не трогаем (иначе Telegram будет ругаться
        # "message is not modified", и мы зря дёргали бы его каждую секунду)
        if self.describe_buttons(new_rows) == self.describe_buttons(current_rows):
            return

        inline_message = InlineMessage(
            self._client.heroku_inline, unit_id, unit.get("inline_message_id")
        )
        await inline_message.edit(unit.get("text"), reply_markup=new_rows)
        unit["buttons"] = new_rows