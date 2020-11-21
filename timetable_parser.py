import os
import re
import traceback

import yaml


# TODO Хранить расписания для каждой беседы ВРЕМЕННО.
#      При неактивности удалять из памяти и подгружать по необходимости.
global class_ordinals, classes


# Таблица номеров дней недели (0..6) к их названию на русском.
WEEKDAYS_RU = {
    0: 'Понедельник',
    1: 'Вторник',
    2: 'Среда',
    3: 'Четверг',
    4: 'Пятница',
    5: 'Суббота',
    6: 'Воскресенье',
}

TIMETABLE_FILE_EXT = '.yml'
CLASS_ORDINALS_TIME_REGEX = r'^(\d{2}\.\d{2})-(\d{2}\.\d{2})$'  # HH.mm-HH.mm; выделяет время начала и время конца


def load_all():
    global class_ordinals, classes

    class_ordinals = {}
    classes = {}

    for file in os.listdir('timetables'):
        if file.endswith(TIMETABLE_FILE_EXT):
            with open('timetables/' + file, 'r', encoding='UTF-8') as fstream:
                try:
                    owner_chat_id = int(file[:-len(TIMETABLE_FILE_EXT)])
                    timetable_yml = yaml.safe_load(fstream)

                    # noinspection PyBroadException
                    try:
                        __parse_all(owner_chat_id, timetable_yml)
                        print('Loaded timetable file for chat %i' % owner_chat_id)
                    except Exception:
                        print('Failed to parse file %s (invalid syntax). Skipping it. '
                              'Timetables will not function for chat %i. Details:' % (file, owner_chat_id))
                        traceback.print_exc()
                except ValueError:
                    print('Skipped file with invalid name %s: '
                          'expected CHAT_ID_INT%s' % (file, TIMETABLE_FILE_EXT))
                except yaml.YAMLError:
                    print('Failed to read file %s. Skipping it. '
                          'Timetables will not function for chat %i. Details:' % (file, owner_chat_id))
                    traceback.print_exc()


def __parse_all(chat, yml):
    __parse_class_ordinals(chat, yml)
    __parse_timetables(chat, yml)


def __parse_timetables(chat, yml):
    global classes
    classes[chat] = {}

    for section in yml.keys():
        if section in WEEKDAYS_RU.values():
            __parse_timetable(chat, yml, section)
        elif section != 'Нумерация':
            raise SyntaxError('недопустимый раздел "%s"; обратите внимание, что дни недели должны '
                              'быть записаны по-русски с заглавной буквы (например, "Понедельник")'
                              % section)


def __parse_timetable(chat, yml, weekday):
    global classes
    classes[chat][weekday] = []

    for time_str in yml[weekday].keys():
        time_groups = re.search(CLASS_ORDINALS_TIME_REGEX, time_str)

        if time_groups is None:
            raise SyntaxError('некорректно указано время проведения пары в день "%s": "%s"; формат: "ЧЧ.мм-ЧЧ.мм"; '
                              'обратите внимание, что задавать время как "8.00" недопустимо — нужно писать "08.00"'
                              % (weekday, time_str))

        start_tstr = time_groups.group(1)
        end_tstr = time_groups.group(2)

        for class_name in yml[weekday][time_str].keys():
            class_data = yml[weekday][time_str][class_name]

            try:
                host = class_data['Преподаватель']
            except KeyError:
                raise SyntaxError('для пары "%s", проходящей в %s-%s в день %s, '
                                  'отсутствует обязательное поле "Преподаватель"'
                                  % (class_name, start_tstr, end_tstr, weekday))

            try:
                aud = class_data['Аудитория']
            except KeyError:
                raise SyntaxError('для пары "%s", проходящей в %s-%s в день %s, '
                                  'отсутствует обязательное поле "Аудитория"'
                                  % (class_name, start_tstr, end_tstr, weekday))

            week = class_data.get('Неделя', None)
            target_groups = class_data.get('Группы', None)

            classes[chat][weekday].append(ClassData(
                start_tstr, end_tstr, class_name, host, aud, week, target_groups))


def __parse_class_ordinals(chat, yml):
    global class_ordinals
    class_ordinals[chat] = {}

    try:
        ordinals = yml['Нумерация']
    except KeyError:
        raise SyntaxError('отсутствует обязательный раздел "Нумерация"')

    if len(ordinals) == 0:
        raise SyntaxError('раздел "Нумерация" не может быть пустым')

    for time_str in ordinals.keys():
        time_groups = re.search(CLASS_ORDINALS_TIME_REGEX, time_str)

        if time_groups is None:
            raise SyntaxError('некорректно указано время проведения пары в нумерации: "%s"; формат: "ЧЧ.мм-ЧЧ.мм"; '
                              'обратите внимание, что задавать время как "8.00" недопустимо — нужно писать "08.00"'
                              % time_str)

        start_tstr = time_groups.group(1)
        end_tstr = time_groups.group(2)
        ordinal_str = ordinals[time_str]

        try:
            ordinal = float(ordinal_str)
        except ValueError:
            raise SyntaxError('некорректно указан номер пары ("%s"), проходящей во временной промежуток "%s" — '
                              'ожидалось целое число или десятичная дробь (например, 3.5 — через точку!)'
                              % (ordinal_str, time_str))

        for _start_tstr, _end_tstr in class_ordinals[chat].keys():
            if class_ordinals[chat][(_start_tstr, _end_tstr)] == ordinal:
                raise SyntaxError('пары, проходящие в разное время ("%s-%s" и "%s-%s"), '
                                  'имеют одинаковый порядковый номер %s'
                                  % (_start_tstr, _end_tstr, start_tstr, end_tstr, ordinal))

        class_ordinals[chat][(start_tstr, end_tstr)] = ordinal


class ClassData:
    """
    Объект для хранения данных о парах.
    """

    def __init__(self, start_tstr, end_tstr, name, host, aud, week, target_groups):
        """
        Создаёт новый объект данных о паре.
        """
        self.start_tstr = start_tstr
        self.end_tstr = end_tstr
        self.name = name
        self.host = host
        self.aud = aud
        self.week = week
        self.target_groups = target_groups

    def __str__(self):
        return '%s в ауд. %s (%s)' % (self.name, self.aud, self.host)


load_all()