import os
import sys
import enum
import logging
import uuid
from dataclasses import dataclass

import win32con
from typing import cast
import yaml
import yaml.parser
import yaml.scanner

import pygin
from pygin import far

sys.path.append(os.path.dirname(__file__))
from _version import __version__


def get_version():
    version = tuple(map(int, (__version__.split('.') + ['0'] * 3)[0:4]))
    return far.VersionInfo(*version, far.VersionStage.Release)


@enum.unique
class Lng(enum.IntEnum):
    """
    Идентификаторы сообщений
    """
    Title = 0

    Ok = 1
    Cancel = 2

    Footer = 3

    InsertQuestion = 4
    InsertShortcut = 5
    InsertGroup = 6

    Directory = 7
    Description = 8

    Group = 9

    DeleteShortcut = 10
    DeleteGroup = 11

    MenuFileName = 12
    LogLevel = 13
    LogFileName = 14


@dataclass
class MenuItem:
    """
    Базовый класс элемента меню
    """
    name: str


@dataclass
class GroupMenuItem(MenuItem):
    """
    Группа элементов меню
    """
    items: list[MenuItem]


@dataclass
class ShortcutMenuItem(MenuItem):
    """
    Переход по ссылке
    """
    shortcut: str


@dataclass
class KeyItem:
    """
    KeyItem
    """
    name: str
    key: tuple[int, int]


class DirHotListPlugin(pygin.Plugin):
    """
    DirHotList plugin
    """
    Title = "Directory HotList plugin"
    Author = "Andrew Andreenkov"
    Description = "Directory HotList plugin"
    Guid = uuid.UUID("{5964abf0-bbc4-11ec-8422-0242ac120002}")
    Version = get_version()

    cHistoryPrefix = 'DHL_'
    cHGroup = cHistoryPrefix + 'Group'
    cHDirectory = cHistoryPrefix + 'Directory'
    cHDescription = cHistoryPrefix + 'Description'

    menu_keys = (
        KeyItem('Edit', (win32con.VK_F4, 0)),
        KeyItem('Insert', (win32con.VK_INSERT, 0)),
        KeyItem('Delete', (win32con.VK_DELETE, 0)),
        KeyItem('MoveUp', (win32con.VK_UP, 8)),  # LEFT_CTRL_PRESSED
        KeyItem('MoveDown', (win32con.VK_DOWN, 8)),  # LEFT_CTRL_PRESSED
        KeyItem('Update', (win32con.VK_F5, 0)),
        KeyItem('Save', (win32con.VK_F2, 0)),
        KeyItem('MenuEdit', (win32con.VK_F4, 2)),  # LEFT_ALT_PRESSED
    )

    log_level = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET
    }

    def add_log(func):
        """
        Добавляет логирование при вызове функций

        :return:
        """

        def wrapper(self, *args, **kwargs):
            logging.debug(f"Function: {func.__name__}")
            exit_code = func(self, *args, **kwargs)
            logging.debug(f"Exit code '{func.__name__}': {exit_code}")
            return exit_code

        return wrapper

    def __init__(self):
        self.settings_file = os.path.expandvars(r'%FARLOCALPROFILE%\DirHotList\settings.yaml')
        self.menu_file = r'%FARLOCALPROFILE%\DirHotList\menu.yaml'
        self.log_file = r'%FARLOCALPROFILE%\DirHotList\DirHotList.log'
        self.log_level = logging.NOTSET
        if os.path.exists(self.settings_file):
            with open(self.settings_file, 'r', encoding="utf-8") as yaml_file:
                settings = yaml.load(yaml_file, Loader=yaml.FullLoader)
                if type(settings) is dict:
                    self.menu_file = settings.get('menu_file', self.menu_file)
                    self.log_file = settings.get('log_file', self.log_file)
                    self.log_level = DirHotListPlugin.log_level[settings.get('log_level', 'NOTSET')]
        self._set_log()
        logging.debug(f"Function: __init__")
        super().__init__()
        self._load()
        logging.debug(f"Exit code __init__': None")

    def _set_log(self):
        if self.log_level == logging.NOTSET:
            logger = logging.getLogger()
            for handler in logger.handlers.copy():
                try:
                    logger.removeHandler(handler)
                except ValueError:  # in case another thread has already removed it
                    pass
            logger.addHandler(logging.NullHandler())
            logger.propagate = False
        else:
            logging.basicConfig(
                filename=os.path.expandvars(self.log_file),
                encoding='utf-8',
                level=self.log_level,
                format='%(asctime)s|%(levelname)-10s|%(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

    @add_log
    def _load(self) -> None:
        """
        Загружает данные из файла меню

        :return:
        """

        def build_menu_items(items):
            result = []
            for item in items:
                key, value = item.popitem()
                if type(value) is list:
                    result.append(GroupMenuItem(key, build_menu_items(value)))
                else:
                    result.append(ShortcutMenuItem(key, value if value else None))
            return result

        menu_file = os.path.expandvars(self.menu_file)
        self.root = GroupMenuItem('\\', [])
        if os.path.exists(menu_file):
            error_message = ""
            error_fmt = "Ошибка чтения файла {}:\nСтрока {}, колонка {}:\n{}"
            with open(menu_file, 'r', encoding="utf-8") as yaml_file:
                try:
                    self.root.items = build_menu_items(
                        yaml.load(yaml_file, Loader=yaml.FullLoader))
                except yaml.scanner.ScannerError as e:
                    error_message = error_fmt.format(menu_file, e.problem_mark.line + 1, e.problem_mark.column + 1,
                                                     e.problem)
                except yaml.parser.ParserError as e:
                    error_message = error_fmt.format(menu_file, e.problem_mark.line + 1, e.problem_mark.column + 1,
                                                     e.problem)

            if error_message:
                self.Message(
                    uuid.uuid4(),
                    far.MessageFlags.Warning + far.MessageFlags.LeftAlign + far.MessageFlags.ButtonOk,
                    "",
                    self.GetMsg(Lng.Title),
                    error_message.split("\n"),
                    [])
                logging.error(error_message)

    @add_log
    def _save(self) -> None:
        """
        Записывает данные в файл меню

        :return:
        """

        def add_menu_items(menu_items: list[MenuItem]) -> list:
            items = []
            for menu_item in menu_items:
                match menu_item:
                    case GroupMenuItem():
                        items.append({menu_item.name: add_menu_items(cast(GroupMenuItem, menu_item).items)})
                    case ShortcutMenuItem():
                        items.append({menu_item.name: cast(ShortcutMenuItem, menu_item).shortcut})
            return items

        menu_file = os.path.expandvars(self.menu_file)
        with open(menu_file, 'w', encoding='utf-8') as yaml_file:
            yaml.SafeDumper.add_representer(
                type(None),
                lambda dumper, value: dumper.represent_scalar(u'tag:yaml.org,2002:null', '')
            )
            yaml.safe_dump(add_menu_items(self.root.items), yaml_file, encoding='utf-8', allow_unicode=True)

    @staticmethod
    def _get_menu_items(group: GroupMenuItem, item_id: int) -> list[MenuItem]:
        """
        Получает список элементов

        :param group: Группа элементов
        :param item_id:  Идентификатор выделенного элемента
        :return: Список элементов
        """

        def get_flags(item):
            flags = far.MenuItemFlags.Default
            if type(item) is GroupMenuItem:
                flags += far.MenuItemFlags.Checked + 0x25BA
            if item == selected_item:
                flags += far.MenuItemFlags.Selected
            return flags

        selected_item = group.items[item_id] if item_id is not None else None
        return [far.MenuItem(os.path.expandvars(item.name), get_flags(item)) for item in group.items]

    @add_log
    def _delete(self, group: GroupMenuItem, item_id: int) -> int:
        """
        Удаление элемента

        :param group: Группа элементов
        :param item_id:  Идентификатор удаляемого элемента
        :return: Новый идентификатор выделенного элемента
        """
        if item_id is not None:
            msg = {ShortcutMenuItem: Lng.DeleteShortcut, GroupMenuItem: Lng.DeleteGroup, MenuItem: None}
            if self.Message(
                    uuid.uuid4(),
                    far.MessageFlags.Warning + far.MessageFlags.ButtonOkCancel,
                    "",
                    self.GetMsg(Lng.Title),
                    [
                        self.GetMsg(msg[type(group.items[item_id])]),
                        group.items[item_id].name
                    ],
                    []) == 0:
                group.items.pop(item_id)
                if item_id == len(group.items):
                    item_id -= 1
                self._save()
        return item_id

    @add_log
    def _move(self, group: GroupMenuItem, item_id: int, move_up: bool) -> int:
        """
        Перемещение элемента

        :param group: Группа элементов
        :param item_id: Идентификатор выделенного элемента
        :param move_up: Перемещение вверх
        :return: Новый идентификатор выделенного элемента
        """
        if item_id is not None:
            if move_up:
                if item_id > 0:
                    group.items.insert(item_id - 1, group.items.pop(item_id))
                    self._save()
                    return item_id - 1
            else:
                if item_id < len(group.items) - 1:
                    group.items.insert(item_id + 1, group.items.pop(item_id))
                    self._save()
                    return item_id + 1
        return item_id

    @add_log
    def _edit_shortcut_dialog(self, description: str = '', directory: str = '') -> dict | None:
        """
        Отображает диалог с параметрами ссылки

        :param description: Описание
        :param directory: Ссылка
        :return: Словарь с описанием и ссылкой или None
        """
        size_x = 70
        size_y = 10
        left_side = 5
        directory = far.DialogEdit(left_side, 3, size_x - left_side - 1, directory, DirHotListPlugin.cHDirectory,
                                   far.DialogItemFlags.HISTORY)
        description = far.DialogEdit(left_side, 5, size_x - left_side - 1, description, DirHotListPlugin.cHDescription,
                                     far.DialogItemFlags.HISTORY)
        btn_ok = far.DialogButton(0, size_y - 3, self.GetMsg(Lng.Ok),
                                  far.DialogItemFlags.DEFAULTBUTTON + far.DialogItemFlags.CENTERGROUP)
        items = [
            far.DialogDoubleBox(left_side - 2, 1, size_x - left_side + 1, size_y - 2, self.GetMsg(Lng.Title)),
            far.DialogText(left_side, 2, -1, self.GetMsg(Lng.Directory)),
            directory,
            far.DialogText(left_side, 4, -1, self.GetMsg(Lng.Description)),
            description,
            far.DialogText(left_side - 1, size_y - 4, size_x - left_side, "", far.DialogItemFlags.SEPARATOR),
            btn_ok,
            far.DialogButton(0, size_y - 3, self.GetMsg(Lng.Cancel), far.DialogItemFlags.CENTERGROUP),
        ]
        result = self.DialogRun(uuid.uuid4(), -1, -1, size_x, size_y, "", items, 0)
        if result == items.index(btn_ok):
            return {'name': description.Data, 'shortcut': directory.Data}
        else:
            return None

    @add_log
    def _insert(self, group: GroupMenuItem, item_id: int) -> int:
        """
        Добавление элемента

        :param group: Группа элементов
        :param item_id: Идентификатор выделенного элемента
        :return: Новый идентификатор выделенного элемента
        """
        message_result = self.Message(
            uuid.uuid4(),
            far.MessageFlags.Default,
            "",
            self.GetMsg(Lng.Title),
            [self.GetMsg(Lng.InsertQuestion)],
            [self.GetMsg(Lng.InsertShortcut), self.GetMsg(Lng.InsertGroup)])
        if message_result is not None:
            if message_result == 0:
                response = self._edit_shortcut_dialog()
                if response is not None:
                    if item_id is None:
                        item_id = 0
                    group.items.insert(item_id, ShortcutMenuItem(**response))
                    self._save()
            else:
                response = self.InputBox(
                    uuid.uuid4(),
                    self.GetMsg(Lng.Title),
                    self.GetMsg(Lng.Group),
                    DirHotListPlugin.cHGroup,
                    "",
                    1024,
                    "Group",
                    far.InputBoxFlags.Buttons + far.InputBoxFlags.NoAmpersand)
                if response is not None:
                    if item_id is None:
                        item_id = 0
                    group.items.insert(item_id, GroupMenuItem(name=response, items=[]))
                    self._save()
        return item_id

    @add_log
    def _edit(self, group: GroupMenuItem, item_id: int) -> None:
        """
        Изменение выделенного элемента

        :param group: Группа элементов
        :param item_id: Идентификатор выделенного элемента
        :return:
        """
        if item_id is not None:
            match selected_item := group.items[item_id]:
                case GroupMenuItem():
                    response = self.InputBox(
                        uuid.uuid4(),
                        self.GetMsg(Lng.Title),
                        self.GetMsg(Lng.Group),
                        DirHotListPlugin.cHGroup,
                        selected_item.name,
                        1024,
                        "Group",
                        far.InputBoxFlags.Buttons + far.InputBoxFlags.NoAmpersand)
                    if response is not None:
                        selected_item.name = response
                        self._save()
                case ShortcutMenuItem():
                    response = self._edit_shortcut_dialog(selected_item.name, selected_item.shortcut)
                    if response is not None:
                        selected_item.name = response['name']
                        selected_item.shortcut = response['shortcut']
                        self._save()

    @add_log
    def _edit_menu(self) -> None:
        """
        Вызов редактора для изменения файла меню

        :return:
        """
        self.Editor(os.path.expandvars(self.menu_file), "", 0, 0, -1, -1, far.EditorFlags.CreateNew, -1, -1, 65001)
        self._load()

    @add_log
    def _menu(self, group: GroupMenuItem, is_root=False) -> int | None:
        """
        Вызов меню. Вызывается рекурсивно

        :param group: Группа элементов
        :param is_root: Это корневая группа
        :return: Код возврата. Если None, то выход из всех уровней вложенности
        """
        logging.debug(f"Group: {group.name}")
        item_id = None
        while True:
            break_code = [0]
            item_id = self.Menu(
                uuid.uuid4(),  # DirHotListPlugin.MenuGuid,
                -1,
                -1,
                0,
                far.MenuFlags.WrapMode,
                f'{self.GetMsg(Lng.Title)}: "{group.name}"',
                self.GetMsg(Lng.Footer),
                "DirectoryHotlist",
                [far.FarKey(*key.key) for key in DirHotListPlugin.menu_keys],
                break_code,
                self._get_menu_items(group, item_id))

            break_action = ""
            if len(break_code) > 0:
                logging.debug(f"break_code: {break_code[0]}, item_id: {item_id}")
                if break_code[0] < len(DirHotListPlugin.menu_keys):
                    break_action = DirHotListPlugin.menu_keys[break_code[0]].name if break_code[0] >= 0 else 'Exit'
                    logging.debug(f"break_action: {break_action}")

            match break_action:
                case 'Exit':  # enter, f10, esc
                    if item_id is None:
                        return None if is_root else -1
                    else:
                        match group.items[item_id]:
                            case ShortcutMenuItem():
                                selected_item = cast(ShortcutMenuItem, group.items[item_id])
                                panel_directory = far.PanelDirectory()
                                panel_directory.Name = os.path.expandvars(
                                    selected_item.name if selected_item.shortcut is None else selected_item.shortcut)
                                self.ActivePanel.PanelControl(far.FileControlCommands.SetPanelDirectory, 0,
                                                              panel_directory)
                                return None
                            case GroupMenuItem():
                                selected_item = cast(GroupMenuItem, group.items[item_id])
                                if self._menu(selected_item) is None:
                                    return None
                case 'Edit':
                    self._edit(group, item_id)
                case 'Insert':
                    item_id = self._insert(group, item_id)
                case 'Delete':
                    item_id = self._delete(group, item_id)
                case ('MoveUp' | 'MoveDown'):
                    item_id = self._move(group, item_id, break_action == 'MoveUp')
                case 'Update':
                    if is_root:
                        self._load()
                        return -1
                case 'Save':
                    self._save()
                case 'MenuEdit':
                    if is_root:
                        self._edit_menu()
                        return -1

    def GetPluginInfoW(self) -> pygin.PluginInfo:
        """
        Функция GetPluginInfoW вызывается Far Manager для получения дополнительной информации о плагине

        :return: Класс PluginInfo с заполненной информацией о плагине
        """
        info = far.PluginInfo()
        info.Flags = 0
        info.PluginMenuItems = [(self.GetMsg(Lng.Title), uuid.UUID("{a1c42e98-bbc4-11ec-8422-0242ac120002}"))]
        info.DiskMenuItems = []
        info.PluginConfigItems = [(self.GetMsg(Lng.Title), uuid.UUID("{44d52b43-f3be-4ece-90eb-ad4be561958e}"))]
        info.CommandPrefix = ""
        return info

    @add_log
    def OpenW(self, info: pygin.PluginInfo) -> None:
        """
        Функция OpenW вызывается Far Manager'ом для запуска плагина

        :param info: Класс PluginInfo с заполненной информацией о плагине
        :return:
        """
        while True:
            if self._menu(self.root, True) is None:
                break
        return None

    @add_log
    def ConfigureW(self, info: pygin.PluginInfo) -> int:
        """
        Функция ConfigureW вызывается Far Manager'ом для конфигурации плагина

        :param info: Класс PluginInfo с заполненной информацией о плагине
        :return:
        """
        size_x = 70
        size_y = 11
        left_side = 5
        combo_box_level = far.DialogComboBox(
            left_side + len(self.GetMsg(Lng.LogLevel)) + 1, 2,
            left_side + len(self.GetMsg(Lng.LogLevel)) + 1 + len(max(DirHotListPlugin.log_level.keys(), key=len)),
            [far.ListItem(x, far.ListItemFlags.SELECTED if DirHotListPlugin.log_level[x] == self.log_level else 0)
             for x in DirHotListPlugin.log_level.keys()], '', far.DialogItemFlags.DROPDOWNLIST
        )
        edit_log_file = far.DialogEdit(left_side, 4, size_x - left_side - 1, self.log_file)
        edit_menu_file = far.DialogEdit(left_side, 6, size_x - left_side - 1, self.menu_file)
        btn_ok = far.DialogButton(0, size_y - 3, self.GetMsg(Lng.Ok),
                                  far.DialogItemFlags.DEFAULTBUTTON + far.DialogItemFlags.CENTERGROUP)
        items = [
            far.DialogDoubleBox(left_side - 2, 1, size_x - left_side + 1, size_y - 2, self.GetMsg(Lng.Title)),
            far.DialogText(left_side, 2, -1, self.GetMsg(Lng.LogLevel)),
            combo_box_level,
            far.DialogText(left_side, 3, -1, self.GetMsg(Lng.LogFileName)),
            edit_log_file,
            far.DialogText(left_side, 5, -1, self.GetMsg(Lng.MenuFileName)),
            edit_menu_file,
            far.DialogText(left_side - 1, size_y - 4, size_x - left_side, "", far.DialogItemFlags.SEPARATOR),
            btn_ok,
            far.DialogButton(0, size_y - 3, self.GetMsg(Lng.Cancel), far.DialogItemFlags.CENTERGROUP),
        ]
        result = self.DialogRun(uuid.uuid4(), -1, -1, size_x, size_y, "", items, 0)
        if result == items.index(btn_ok):
            log_level = combo_box_level.Data
            if log_level not in DirHotListPlugin.log_level:
                log_level = 'NOTSET'
            self.log_level = DirHotListPlugin.log_level[log_level]
            self.log_file = edit_log_file.Data
            self.menu_file = edit_menu_file.Data
            self._set_log()
            self._load()
            with open(self.settings_file, 'w', encoding='utf-8') as yaml_file:
                settings = {
                    'menu_file': self.menu_file,
                    'log_file': self.log_file,
                    'log_level': log_level
                }
                yaml.SafeDumper.add_representer(
                    type(None),
                    lambda dumper, value: dumper.represent_scalar(u'tag:yaml.org,2002:null', '')
                )
                yaml.safe_dump(settings, yaml_file, encoding='utf-8', allow_unicode=True)
        return False


FarPluginClass = DirHotListPlugin
