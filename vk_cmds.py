import re
import threading
from datetime import datetime
from enum import Enum, auto

import schedule

import groupsmgr
import timetable
import vk_api
import os
import time
import requests

import timetable_parser
from kristybot import GetVkSession
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

vk_session = GetVkSession()
vk_upload = vk_api.upload.VkUpload(vk_session)
vk = vk_session.get_api()

# Запрещено создавать группы с этими названиями.
FORBIDDEN_NAMES = ['all', 'все', 'online', 'онлайн', 'здесь', 'here', 'тут']
MAX_MSG_LEN = 4096


def __run_classes_notifier():
    print('Running scheduled classes notifier. Current time: ' + str(datetime.now().time()))
    all_chats = groupsmgr.get_all_chats()

    for chat in all_chats:
        classes = timetable_parser.classes.get(chat, None)

        if classes is not None:
            todays_classes = classes[timetable.weekday_ru()]

            for class_data in todays_classes:
                time_left = timetable.time_left_raw(chat, class_data.start_tstr)

                if time_left is not None:
                    hours_left = time_left[0]
                    minutes_left = time_left[1]

                    # TODO удалить через несколько дней (если всё будет работать нормально)
                    if hours_left == 0 and chat == 1:
                        print(class_data)
                        print('mins = ' + str(minutes_left))
                        print(' ')

                    if hours_left == 0 and minutes_left == 15:
                        if class_data.target_groups is None:
                            mention = '@all'
                        else:
                            mention = pings_str(chat, class_data.target_groups)

                        send(chat + 2E9, '📚 Через 15 минут начнётся пара: %s\n\n%s' % (class_data, mention))


def __start_classes_notifier():
    print('Starting scheduled classes notifier in thread ' + threading.current_thread().getName())
    schedule.every().minute.at(':00').do(__run_classes_notifier)

    while True:
        schedule.run_pending()
        time.sleep(0.49)


class Rank(Enum):
    """
    Описание рангов:
    GOVNO     - Не может использовать бота, мне жалко этого человека будет
    WORKER    - Может подключаться и отключаться от групп, также просматривать все группы, свои группы и участников
                группы, может использовать префикс вложений бота, может просматривать ранги участников беседы,
                может использовать расписание и всё с ним связанное
    USER      - Может тегать по группам, может делать рассылки, а также добавлять сообщения в почту беседы
    PRO       - Может добавлять новые вложения в группе, может делать случайный выбор
                нескольких людей или играть в русскую рулетку
    MODERATOR - Может подключать и отключать участников от групп, а также удалять группы, которые не создавал, переименовывать группы,
                может менять ранги других
    ADMIN     - По сути это как король, только король 1, админов может быть несколько
    KING      - Абсолютная власть над чатом
    """
    GOVNO = auto()
    WORKER = auto()
    USER = auto()
    PRO = auto()
    MODERATOR = auto()
    ADMIN = auto()
    KING = auto()


def send(peer, msg, attachment=None, keyboard=None):
    """
    Отправляет указанное сообщение в указанный чат. Если длина сообщения превышает
    максимальную (MAX_MSG_LEN), то сообщение будет разбито на части и отправлено,
    соответственно, частями.

    :param peer: Куда отправить сообщение (peer_id).
    :param msg: Текст сообщения.
    :param attachment: Вложения
    :param keyboard: Клавиатура

    TODO: сделать разбиение на части более "дружелюбным" - стараться разбивать по строкам или хотя бы по пробелам.
    """
    if len(msg) <= MAX_MSG_LEN:
        vk.messages.send(peer_id=peer, message=msg,
                         attachment=attachment, random_id=int(vk_api.utils.get_random_id()),
                         keyboard=keyboard)
    else:
        chunks = (msg[k:k + MAX_MSG_LEN] for k in range(0, len(msg), MAX_MSG_LEN))

        for chunk in chunks:
            vk.messages.send(peer_id=peer, message=chunk, random_id=int(vk_api.utils.get_random_id()))


timetable_parser.load_all(send)


def get_list_attachments(attachments, peer):
    """
    Преобразует attachments ВКашный в нормальный, чтобы можно было обращаться через send
    """
    array_attachments = []
    for attachment in list(attachments):
        if attachment['type'] == 'photo':
            max_photo_url = ""
            max_width = 0
            for photo in attachment['photo']['sizes']:
                if max_width < photo['width']:
                    max_width = photo['width']
                    max_photo_url = photo['url']
            img_data = requests.get(max_photo_url).content
            time_now = time.time()
            with open(os.path.dirname(__file__) + os.path.sep + 'image{0}.jpg'.format(time_now), 'wb') as handler:
                handler.write(img_data)
            uploads = vk_upload.photo_messages(photos=os.path.dirname(__file__) + os.path.sep + 'image{0}.jpg'.format(time_now))[0]
            os.remove(os.path.dirname(__file__) + os.path.sep + 'image{0}.jpg'.format(time_now))
            array_attachments.append('photo{0}_{1}'.format(uploads["owner_id"], uploads["id"]))
        elif attachment['type'] == 'video':
            array_attachments.append('video{0}_{1}_{2}'.format(attachment['video']['owner_id'], attachment['video']['id'], attachment['video']['access_key']))
        elif attachment['type'] == 'audio':
            array_attachments.append('audio{0}_{1}'.format(attachment['audio']['owner_id'], attachment['audio']["id"]))
        elif attachment['type'] == 'wall':
            if not attachment['wall']['from']['is_closed']:
                array_attachments.append('wall{0}_{1}'.format(attachment['wall']['to_id'], attachment['wall']['id']))
        elif attachment['type'] == 'doc':
            file_name = attachment['doc']['title']
            url_doc = attachment['doc']['url']
            doc_data = requests.get(url_doc).content
            with open(os.path.dirname(__file__) + os.path.sep + file_name, 'wb') as handler:  # TODO возможность одинаковых файлов, почтинить в будущем
                handler.write(doc_data)
            upload = vk_upload.document_message(doc=os.path.dirname(__file__) + os.path.sep + file_name, peer_id=peer, title=file_name)
            os.remove(os.path.dirname(__file__) + os.path.sep + file_name)
            array_attachments.append('doc{0}_{1}'.format(upload['doc']["owner_id"], upload['doc']["id"]))
    return array_attachments


def start_keyboard(chat):
    keyboard = VkKeyboard()
    keyboard.add_button("Почта",
                        payload={"action": "почта_выбор_тег", "chat_id": chat, "args": [0]},
                        color=VkKeyboardColor.PRIMARY
                        )
    keyboard.add_line()
    keyboard.add_button("Подключиться",
                        payload={"action": "подключиться_выбор", "chat_id": chat, "args": [0]},
                        color=VkKeyboardColor.POSITIVE
                        )
    keyboard.add_button("Отключиться",
                        payload={"action": "отключиться_выбор", "chat_id": chat, "args": [0]},
                        color=VkKeyboardColor.NEGATIVE
                        )
    keyboard.add_line()
    keyboard.add_button("Все группы",
                        payload={"action": "все_группы", "chat_id": chat}
                        )
    keyboard.add_button("Мои группы",
                        payload={"action": "мои_группы", "chat_id": chat}
                        )
    keyboard.add_button("Состав",
                        payload={"action": "состав_группы_выбор", "chat_id": chat, "args": [0]}
                        )
    keyboard.add_line()
    keyboard.add_button("Развлечение",
                        payload={"action": "развлечение", "chat_id": chat}
                        )
    keyboard.add_button("Настройки",
                        payload={"action": "настройки_выбор", "chat_id": chat}
                        )
    return keyboard.get_keyboard()


def join_keyboard(chat, peer, sender, page):
    existing = groupsmgr.get_all_groups(chat)
    sender_groups = groupsmgr.get_user_groups(chat, sender)
    groups = list(set(existing) - set(sender_groups))
    groups.sort()
    if not groups:
        return "Вы уже состоите во всех группах", start_keyboard(chat)
    max_groups = 6
    if page > (len(groups) - 1) // max_groups:
        page = 0
    elif page < 0:
        page = (len(groups) - 1) // max_groups
    keyboard = VkKeyboard()
    for number, group in enumerate(groups[page * max_groups:(page * max_groups + max_groups) if page * max_groups + max_groups <= len(groups) else len(groups)]):
        if number % 2 == 0 and number != 0:
            keyboard.add_line()
        keyboard.add_button(group,
                            payload={'action': 'подключиться', 'chat_id': chat, 'args': [group, page]})
    keyboard.add_line()
    response = "Выберите группу для подключения \n"
    if max_groups < len(groups):
        response += 'Cтр. ' + str(page + 1)
        keyboard.add_button('Назад',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'подключиться_выбор', 'chat_id': chat, 'args': [page - 1]})
    keyboard.add_button('Выход',
                        color=VkKeyboardColor.NEGATIVE,
                        payload={'action': 'стартовая_клавиатура', 'chat_id': chat})
    if max_groups < len(groups):
        keyboard.add_button('Далее',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'подключиться_выбор', 'chat_id': chat, 'args': [page + 1]})
    return response, keyboard.get_keyboard()


def left_keyboard(chat, peer, sender, page):
    sender_groups = groupsmgr.get_user_groups(chat, sender).sort()
    if not sender_groups:
        return "Вас нет ни в одной группе", start_keyboard(chat)
    max_groups = 6
    if page > (len(sender_groups) - 1) // max_groups:
        page = 0
    elif page < 0:
        page = (len(sender_groups) - 1) // max_groups
    keyboard = VkKeyboard()
    for number, group in enumerate(sender_groups[page * max_groups:(page * max_groups + max_groups) if page * max_groups + max_groups <= len(sender_groups) else len(sender_groups)]):
        if number % 2 == 0 and number != 0:
            keyboard.add_line()
        keyboard.add_button(group,
                            payload={'action': 'отключиться', 'chat_id': chat, 'args': [group, page]})
    keyboard.add_line()
    response = "Выберите группу для отключения \n"
    if max_groups < len(sender_groups):
        response += 'Cтр. ' + str(page + 1)
        keyboard.add_button('Назад',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'отключиться_выбор', 'chat_id': chat, 'args': [page - 1]})
    keyboard.add_button('Выход',
                        color=VkKeyboardColor.NEGATIVE,
                        payload={'action': 'стартовая_клавиатура', 'chat_id': chat})
    if max_groups < len(sender_groups):
        keyboard.add_button('Далее',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'отключиться_выбор', 'chat_id': chat, 'args': [page + 1]})
    return response, keyboard.get_keyboard()


def exec_next_class(cmd, chat, peer, sender):
    """
    !пара
    """
    sender_groups = groupsmgr.get_user_groups(chat, sender)
    next_class = timetable.next_class(chat, sender_groups)

    if next_class is None:
        send(peer, '🛌 На сегодня всё. Иди поспи, что ли.')
    else:
        time_left = timetable.time_left(chat, next_class.start_tstr)
        time_left_str = 'До начала ' + time_left + '.' if time_left is not None else 'Занятие вот-вот начнётся!'
        send(peer, '📚 Следующая пара: %s. %s' % (next_class, time_left_str))


def exec_create(cmd, chat, peer, sender, args):
    """
    !создать
    """
    existing = groupsmgr.get_all_groups(chat)

    created = []
    bad_names = []
    already_existed = []

    for group in args:
        if 2 <= len(group) <= 30 and re.match(r'[a-zA-Zа-яА-ЯёЁ0-9_]', group) and group not in FORBIDDEN_NAMES:
            if group not in existing:
                groupsmgr.create_group(chat, group, sender)
                created.append(group)
            else:
                already_existed.append(group)
        else:
            bad_names.append(group)

    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    if created:
        response += 'Я зарегистрировала эти группы: \n➕ '
        response += ' \n➕ '.join(created)
        response += ' \n'

    if already_existed:
        response += 'Эти группы уже существуют: \n✔ '
        response += ' \n✔ '.join(already_existed)
        response += ' \n'

    if bad_names:
        response += 'Названия этих групп недопустимы: \n🚫 '
        response += ' \n🚫 '.join(bad_names)
        response += ' \n'

    send(peer, response)


def exec_delete(cmd, chat, peer, sender, args):
    """
    !удалить
    """
    deleted = []
    not_found = []
    not_creator = []

    rank_user = groupsmgr.get_rank_user(chat, sender)
    existing = groupsmgr.get_all_groups(chat)
    sender_created_groups = groupsmgr.get_groups_created_user(chat, sender)

    for group in args:
        if group in existing:
            if group in sender_created_groups or Rank[rank_user].value >= Rank.MODERATOR.value:
                deleted.append(group)
                groupsmgr.delete_group(chat, group)
            else:
                not_creator.append(group)
        else:
            not_found.append(group)

    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    if deleted:
        response += 'Я удалила эти группы: \n✖ '
        response += ' \n✖ '.join(deleted)
        response += ' \n'

    if not_found:
        response += 'Этих групп и так нет в беседе: \n⛔ '
        response += ' \n⛔ '.join(not_found)
        response += ' \n'

    if not_creator:
        response += 'У вас нет прав, чтобы удалить эти группы: \n🚫 '
        response += ' \n🚫 '.join(not_creator)
        response += ' \n'

    send(peer, response)


def exec_join(cmd, chat, peer, sender, args):
    """
    !подключиться
    """
    group = args[0]
    page = args[1]
    sender_groups = groupsmgr.get_user_groups(chat, sender)
    existing = groupsmgr.get_all_groups(chat)

    if group in sender_groups:
        send(peer, 'Вы уже состоите в этой группе', [], join_keyboard(chat, peer, sender, page))
    if group not in existing:
        send(peer, 'Такой группы нет', [], join_keyboard(chat, peer, sender, page))
    groupsmgr.join_group(chat, group, sender)
    response = 'Добавила вас в группу - ' + group
    text, keyboard = join_keyboard(chat, peer, sender, page)

    send(peer, response, [], keyboard)


def exec_left(cmd, chat, peer, sender, args):
    """
    !отключиться
    """
    group = args[0]
    page = args[1]
    sender_groups = groupsmgr.get_user_groups(chat, sender)
    existing = groupsmgr.get_all_groups(chat)

    if group not in sender_groups:
        send(peer, 'Вас нет в этой группе', [], left_keyboard(chat, peer, sender, page))
    if group not in existing:
        send(peer, 'Такой группы нет', [], left_keyboard(chat, peer, sender, page))
    groupsmgr.left_group(chat, group, sender)
    response = 'Отключила вас от группы - ' + group
    text, keyboard = left_keyboard(chat, peer, sender, page)

    send(peer, response, [], keyboard)


def exec_join_members(cmd, chat, peer, sender, args):
    """
    !подключить
    """
    if '>' not in args or args.count('>') > 1:
        cmd.print_usage(peer)
        return
    users = re.findall(r'\[id(\d+)\|[^]]+\]', ' '.join(args[:args.index('>')]))
    groups = list(filter(re.compile(
        r'[a-zA-Zа-яА-ЯёЁ0-9_]').match,
                         args[args.index('>') + 1:] if len(args) - 1 > args.index('>') else []))
    if not users or not groups:
        cmd.print_usage(peer)
        return

    users = [int(user) for user in users]
    existing_groups = groupsmgr.get_all_groups(chat)
    existing_users = groupsmgr.get_all_users(chat)

    not_found = []
    joined = {}
    for user in users:
        if user in existing_users:
            joined.update({user: []})
            sender_groups = groupsmgr.get_user_groups(chat, user)
            for group in groups:
                if group in existing_groups and group not in sender_groups:
                    groupsmgr.join_group(chat, group, user)
                    joined[user].append(group)
            if not joined[user]:
                del joined[user]
        else:
            not_found.append(user)

    all_users_vk = vk.users.get(user_ids=users)
    first_names_joined = ""
    first_names_not_found = ""
    for user_vk in all_users_vk:  # хрен его знает, мб потом переделаем
        if user_vk["id"] in joined:
            first_names_joined += "{0} > {1} \n".format("{0} {1}".format(user_vk["first_name"], user_vk["last_name"]),
                                                        ' '.join(joined[user_vk["id"]]))
        if user_vk["id"] in not_found:
            first_names_not_found += "{0} {1} \n".format(user_vk["first_name"], user_vk["last_name"])

    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    if first_names_joined:
        response += 'Добавила: \n'
        response += first_names_joined

    if first_names_not_found:
        response += 'Данных пользователей нет в базе данных: \n'
        response += first_names_not_found

    if not first_names_not_found and not first_names_joined:
        response += 'Никто никуда не добавлен'

    send(peer, response)


def exec_left_members(cmd, chat, peer, sender, args):
    """
    !отключить
    """
    if '>' not in args or args.count('>') > 1:
        cmd.print_usage(peer)
        return
    users = re.findall(r'\[id(\d+)\|[^]]+\]', ' '.join(args[:args.index('>')]))
    groups = list(filter(re.compile(
        r'[a-zA-Zа-яА-ЯёЁ0-9_]').match,
                         args[args.index('>') + 1:] if len(args) - 1 > args.index('>') else []))
    if not users or not groups:
        cmd.print_usage(peer)
        return

    users = [int(user) for user in users]
    existing_groups = groupsmgr.get_all_groups(chat)
    existing_users = groupsmgr.get_all_users(chat)

    not_found = []
    left = {}
    for user in users:
        if user in existing_users:
            left.update({user: []})
            sender_groups = groupsmgr.get_user_groups(chat, user)
            for group in groups:
                if group in existing_groups and group in sender_groups:
                    groupsmgr.left_group(chat, group, user)
                    left[user].append(group)
            if not left[user]:
                del left[user]
        else:
            not_found.append(user)

    all_users_vk = vk.users.get(user_ids=users)
    first_names_left = ""
    first_names_not_found = ""
    for user_vk in all_users_vk:  # хрен его знает, мб потом переделаем
        if user_vk["id"] in left:
            first_names_left += "{0} > {1} \n".format("{0} {1}".format(user_vk["first_name"], user_vk["last_name"]),
                                                      ' '.join(left[user_vk["id"]]))
        if user_vk["id"] in not_found:
            first_names_not_found += "{0} {1} \n".format(user_vk["first_name"], user_vk["last_name"])

    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    if first_names_left:
        response += 'Отключила: \n'
        response += first_names_left

    if first_names_not_found:
        response += 'Данных пользователей нет в базе данных: \n'
        response += first_names_not_found

    if not first_names_not_found and not first_names_left:
        response += 'Никого не отключила'

    send(peer, response)


def exec_rename(cmd, chat, peer, sender, args):
    """
    !переименовать
    """
    name_old = args[0]
    name_new = args[1]

    if name_new in FORBIDDEN_NAMES or len(name_new) < 2 or len(name_new) > 30 or not re.match(r'[a-zA-Zа-яА-ЯёЁ0-9_]',
                                                                                              name_new):
        send(peer, "Новое название группы является недопустимым: " + name_new)
        return

    existing = groupsmgr.get_all_groups(chat)

    if name_old not in existing:
        send(peer, "Такой группы нет в базе данных: " + name_old)
        return
    if name_new in existing:
        send(peer, "Такая группа уже есть в базе данных: " + name_new)
        return

    groupsmgr.rename_group(chat, name_old, name_new)

    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    response += 'Успешно установила новое название группы: ' + name_new
    send(peer, response)


def exec_change_rank(cmd, chat, peer, sender, args):
    """
    Команда, для изменения ранга
    TODO Антоша обязательно сделает, у него в голове норм идея
    """
    change_to_this_rank = args[0].upper()  # название переделать FIX PLS
    sender_rank = groupsmgr.get_rank_user(chat, sender)
    if change_to_this_rank not in Rank.__members__:
        send(peer, 'Не найден такой ранг')
        return
    if Rank[sender_rank].value < Rank[change_to_this_rank].value:
        send(peer, 'У вас нет прав на этот ранг')
        return
    users = re.findall(r'\[id(\d+)\|[^]]+\]', ' '.join(args[1:]))
    if not users:
        cmd.print_usage(peer)
        return
    users_up = []
    users_down = []
    users_eq = []
    users_error = []
    existing_users = groupsmgr.get_all_users(chat)
    users = [int(user) for user in users]

    for user in users:
        if user in existing_users:
            user_rank = groupsmgr.get_rank_user(chat, user)
            if Rank[change_to_this_rank].value > Rank[user_rank].value:
                groupsmgr.change_rank(chat, user, change_to_this_rank)
                users_up.append(user)
            elif Rank[change_to_this_rank].value < Rank[user_rank].value < Rank[sender_rank].value:
                groupsmgr.change_rank(chat, user, change_to_this_rank)
                users_down.append(user)
            else:
                users_eq.append(user)
        else:
            users_error.append(user)
    all_users_vk = vk.users.get(user_ids=users)
    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''
    # дальше можно описать одним словом: помогите
    if users_up:
        response += "Повышены в ранге до {0}: \n".format(change_to_this_rank)
        for user in users_up:
            for user_vk in all_users_vk:  # да бред, потом чё-нибудь придумаю
                if user == user_vk["id"]:
                    response += "🔼 {0} {1} \n".format(user_vk["first_name"], user_vk["last_name"])

    if users_down:
        response += "Понижены в ранге до {0}: \n".format(change_to_this_rank)
        for user in users_down:
            for user_vk in all_users_vk:  # да бред, потом чё-нибудь придумаю
                if user == user_vk["id"]:
                    response += "🔽 {0} {1} \n".format(user_vk["first_name"], user_vk["last_name"])

    if users_eq:
        response += "Ранг не изменён: \n"
        for user in users_eq:
            for user_vk in all_users_vk:  # да бред, потом чё-нибудь придумаю
                if user == user_vk["id"]:
                    response += "▶ {0} {1} \n".format(user_vk["first_name"], user_vk["last_name"])

    if users_error:
        response += "Пользователи не найдёны: \n"
        for user in users_error:
            for user_vk in all_users_vk:  # да бред, потом чё-нибудь придумаю
                if user == user_vk["id"]:
                    response += "❌ {0} {1} \n".format(user_vk["first_name"], user_vk["last_name"])

    send(peer, response)


def exec_week(cmd, chat, peer, sender):
    """
    !неделя
    """
    week = timetable.get_week(chat)
    if not week:
        if int(time.strftime("%W", time.gmtime(time.time() + 2 * 60 * 60))) % 2:
            week = 'нижняя'
        else:
            week = 'верхняя'
    emoji = '☝' if week == 'верхняя' else '👇'
    send(peer, str("Сейчас %s %s %s неделя" % (emoji, week, emoji)).upper())


def exec_roulette(cmd, chat, peer, sender):
    response = "Играем в русскую рулетку. И проиграл у нас: "
    users = groupsmgr.get_all_users(chat)
    random_user = users[os.urandom(1)[0] % len(users)]
    try:
        user_photo = vk.users.get(user_id=random_user, fields=["photo_id"])
        send(peer, response, "photo" + user_photo[0]["photo_id"])
    except:
        send(1 + 2E9, str(user_photo))


def exec_use_attachment(chat, peer, tag):
    """
    ? - отправляет вложения + текст
    """
    attachment = groupsmgr.get_attachment(chat, tag)
    if attachment:
        send(peer, attachment["message"], attachment["attachments"])


def exec_add_one_attachment(cmd, chat, peer, sender, args, attachments):
    tag = args[0].lower()
    message = args[1:] if len(args) > 1 else []
    message = ' '.join(message)

    if not message and not attachments:
        cmd.print_usage(peer)
        return
    if groupsmgr.get_attachment(chat, tag):
        send(peer, "Данный тег используется")
        return

    list_attachments = get_list_attachments(attachments, peer)

    if not list_attachments and not message:
        send(peer, "Не удалось добавить")
        return

    groupsmgr.add_attachment(chat, tag, message, list_attachments)
    send(peer, "Успешно установила вложение")


def exec_add_many_attachments(cmd, chat, peer, sender, args, attachments):
    tags = args
    created = []
    already_existed = []
    if not attachments or len(tags) > 4:
        cmd.print_usage(peer)
        return

    for number, tag in enumerate(tags):
        tag = tag.lower()
        if groupsmgr.get_attachment(chat, tag):
            already_existed.append(tag)
        else:
            if number + 1 > len(attachments):
                break
            attachment = get_list_attachments([attachments[number]], peer)

            if not attachment:
                continue
            created.append(tag)
            groupsmgr.add_attachment(chat, tag, '', attachment)

    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    if created:
        response += 'Добавила новые теги для вложений: \n➕ '
        response += ' \n➕ '.join(created)
        response += ' \n'

    if already_existed:
        response += 'Эти теги уже используются: \n✔ '
        response += ' \n✔ '.join(already_existed)
        response += ' \n'

    send(peer, response)


def exec_edit_attachment(cmd, chat, peer, sender, args, attachments):
    tag = args[0].lower()
    message = args[1:] if len(args) > 1 else []
    message = ' '.join(message)

    if not message and not attachments:
        cmd.print_usage(peer)
        return
    if not groupsmgr.get_attachment(chat, tag):
        send(peer, "Данный тег не найден")
        return

    list_attachments = get_list_attachments(attachments, peer)

    if not list_attachments and not message:
        send(peer, "Не удалось изменить")
        return

    groupsmgr.edit_attachment(chat, tag, message, list_attachments)
    send(peer, "Успешно изменила вложение")


def exec_remove_attachment(cmd, chat, peer, sender, args):
    tags = args
    deleted = []
    not_found = []

    for tag in tags:
        tag = tag.lower()
        if groupsmgr.get_attachment(chat, tag):
            deleted.append(tag)
            groupsmgr.remove_attachment(chat, tag)
        else:
            not_found.append(tag)

    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    if deleted:
        response += 'Удалила теги для вложений: \n➕ '
        response += ' \n✖ '.join(deleted)
        response += ' \n'

    if not_found:
        response += 'Не найдены эти теги: \n✔ '
        response += ' \n⛔ '.join(not_found)
        response += ' \n'

    send(peer, response)


def exec_change_name_chat(cmd, chat, peer, sender, args):
    """
    системная команда
    !name - меняет название беседы
    """
    new_name = args[0]
    if new_name in groupsmgr.get_names_chats():
        send(peer, "Данное имя используется")
        return
    if new_name.isdigit():
        send(peer, "Новое название не должно состоять только из цифр")
        return
    groupsmgr.change_name_chat(chat, new_name)
    send(peer, "Успешно обновила имя беседы")


def exec_ruslan(cmd, chat, peer, sender):
    """
    !руслан - просто Руслан (шар судьбы)
    """
    answers = ["Беспорно", "Предрешено", "Никаких сомнений", "Определённо да", "Можешь быть уверен в этом",
               "Мне кажется - «да»", "Вероятнее всего", "Хорошие перспективы", "Знаки говорят - «да»", "Да",
               "Пока не ясно, попробуй снова", "Спроси позже", "Лучше не рассказывать", "Сейчас нельзя предсказать", "Сконцентрируйся и спроси опять",
               "Даже не думай", "Мой ответ — «нет»", "По моим данным — «нет»", "Перспективы не очень хорошие", "Весьма сомнительно"]
    final_answer = answers[os.urandom(1)[0] % 20]
    send(peer, final_answer)


def exec_choose(cmd, chat, peer, sender, args):
    """
    !выбор - выбирает случайных участников беседы
    """
    number = args[0]

    if not str(number).isdigit() or not int(number) > 0:
        cmd.print_usage(peer)
        return

    response = "Случайно были выбраны: \n"

    users = groupsmgr.get_all_users(chat)
    count = len(users) - int(number)

    for i in range(count):
        users.remove(users[os.urandom(1)[0] % len(users)])
    users_vk = vk.users.get(user_ids=users)
    for number, user in enumerate(users_vk):
        response += str(number + 1) + ". " + user["first_name"] + " " + user[
            "last_name"] + " \n"
    send(peer, response)


def exec_gate(cmd, chat, peer, sender):  # пока так, дальше посмотрим
    """
    !ворота
    """
    format_time = '%H:%S'
    timezone = 2 * 60 * 60  # +2 часа
    time_open_gate = [
        ['08:30', '09:00'],
        ['13:00', '14:00'],
        ['17:00', '18:30']
    ]
    time_open_gate.sort()
    time_now_struct = time.gmtime(time.time() + timezone)
    time_now = time_now_struct.tm_hour * 3600 + time_now_struct.tm_min * 60 + time_now_struct.tm_sec

    for number, time_gate in enumerate(time_open_gate):
        # я искал легче путь, но я обожаю время ☻
        time_start_now = time.strptime(time_gate[0], format_time).tm_hour * 60 * 60 + time.strptime(time_gate[0], format_time).tm_min * 60
        time_end_now = time.strptime(time_gate[1], format_time).tm_hour * 60 * 60 + time.strptime(time_gate[1], format_time).tm_min * 60
        time_start_next = time.strptime(time_open_gate[(number + 1) % len(time_open_gate)][0], format_time).tm_hour * 60 * 60 + time.strptime(time_open_gate[(number + 1) % len(time_open_gate)][0], format_time).tm_min * 60
        if time_start_now <= time_now <= time_end_now:
            response = "Ворота открыты. До закрытия "
            time_closing = time_end_now - time_now
            response += timetable.time_left_ru(
                time_closing // (60 * 60),
                time_closing % (60 * 60) // 60,
                time_closing % (60 * 60) % 60
            )
            send(peer, response)
            return
        elif time_end_now < time_now < time_start_next:
            response = "Ворота закрыты. До открытия "
            time_opening = time_start_next - time_now
            response += timetable.time_left_ru(
                time_opening // (60 * 60),
                time_opening % (60 * 60) // 60,
                time_opening % (60 * 60) % 60
            )
            send(peer, response)
            return
        elif (number + 1) == len(time_open_gate) and (time_end_now < time_now or time_now < time_start_next):
            response = "Ворота закрыты. До открытия "
            time_opening = (time_start_next - time_now) if time_start_next > time_now else (24 * 60 * 60 - time_now + time_start_next)
            response += timetable.time_left_ru(
                time_opening // (60 * 60),
                time_opening % (60 * 60) // 60,
                time_opening % (60 * 60) % 60
            )
            send(peer, response)
            return
    send(peer, "Нету времени")


def exec_bfu(cmd, chat, peer, sender):
    """
    !бфу - отображает каеф в БФУ
    """
    send(peer, "", ["photo-199300529_457239023"])


def exec_create_emails(cmd, chat, peer, sender, args):
    tags = args
    all_tags = groupsmgr.get_all_emails(chat)
    created = []
    already_existed = []
    bad_names = []
    for tag in tags:
        tag = tag.lower()
        if tag in all_tags:
            already_existed.append(tag)
        elif re.match(r'[a-zA-Zа-яА-ЯёЁ0-9_]', tag):
            created.append(tag)
            groupsmgr.create_email(chat, tag)
        else:
            bad_names.append(tag)
    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''
    if created:
        response += 'Добавила новые теги для почты: \n➕ '
        response += ' \n➕ '.join(created)
        response += ' \n'

    if already_existed:
        response += 'Эти теги уже используются: \n✔ '
        response += ' \n✔ '.join(already_existed)
        response += ' \n'

    if bad_names:
        response += 'Недопустимые названия: \n⛔ '
        response += ' \n⛔ '.join(bad_names)
        response += ' \n'
    send(peer, response)

def exec_delete_emails(cmd, chat, peer, sender, args):
    tags = args
    all_tags = groupsmgr.get_all_emails(chat)
    deleted = []
    not_found = []
    for tag in tags:
        tag = tag.lower()
        if tag in all_tags:
            deleted.append(tag)
            groupsmgr.delete_email(chat, tag)
        else:
            not_found.append(tag)
    if peer > 2E9:
        name_data = vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''
    if deleted:
        response += 'Успешно удалила теги для почты: \n✖ '
        response += ' \n✖ '.join(deleted)
        response += ' \n'

    if not_found:
        response += 'Не нашла вот эти теги: \n⛔ '
        response += ' \n⛔ '.join(not_found)
        response += ' \n'

    send(peer, response)


def exec_add_event_to_email(cmd, chat, peer, sender, args, attachments):
    format_date_time = "%d.%m:%H.%M"
    format_date = "%d.%m"
    format_date_string = "ДД.ММ"
    timezone = 2 * 60 * 60  # +2 часа
    tag = args[0].lower()

    all_tags = groupsmgr.get_all_emails(chat)
    if tag not in all_tags:
        send(peer, "Данная почта не создана")
        return

    date_string = args[1]
    message = args[2:] if len(args) > 2 else []
    message = ' '.join(message)

    try:
        date_event = time.strptime(date_string, format_date_time)
        time_now_struct = time.gmtime(time.time() + timezone)
        if date_event.tm_mon > time_now_struct.tm_mon or (date_event.tm_mon == time_now_struct.tm_mon and date_event.tm_mday > time_now_struct.tm_mday
        ) or (date_event.tm_mon == time_now_struct.tm_mon and date_event.tm_mday == time_now_struct.tm_mday and date_event.tm_hour > time_now_struct.tm_hour
        ) or (date_event.tm_mon == time_now_struct.tm_mon and date_event.tm_mday == time_now_struct.tm_mday and date_event.tm_hour == time_now_struct.tm_hour and date_event.tm_min >= time_now_struct.tm_min):
            date_to_db = '.'.join([str(date_event.tm_mday).rjust(2, '0'), str(date_event.tm_mon).rjust(2, '0'), str(time_now_struct.tm_year)]) + ' ' + ':'.join([str(date_event.tm_hour).rjust(2, '0'), str(date_event.tm_min).rjust(2, '0')])
        else:
            date_to_db = '.'.join([str(date_event.tm_mday).rjust(2, '0'), str(date_event.tm_mon).rjust(2, '0'), str(time_now_struct.tm_year + 1)]) + ' ' + ':'.join([str(date_event.tm_hour).rjust(2, '0'), str(date_event.tm_min).rjust(2, '0')])
    except ValueError:
        try:
            date_event = time.strptime(date_string, format_date)
            time_now_struct = time.gmtime(time.time() + timezone)
            if date_event.tm_mon > time_now_struct.tm_mon or (date_event.tm_mon == time_now_struct.tm_mon and date_event.tm_mday >= time_now_struct.tm_mday):
                date_to_db = '.'.join([str(date_event.tm_mday).rjust(2, '0'), str(date_event.tm_mon).rjust(2, '0'), str(time_now_struct.tm_year)]) + ' ' + ':'.join([str(time_now_struct.tm_hour).rjust(2, '0'), str(time_now_struct.tm_min).rjust(2, '0')])
            else:
                date_to_db = '.'.join([str(date_event.tm_mday).rjust(2, '0'), str(date_event.tm_mon).rjust(2, '0'), str(time_now_struct.tm_year + 1)]) + ' ' + ':'.join([str(time_now_struct.tm_hour).rjust(2, '0'), str(time_now_struct.tm_min).rjust(2, '0')])
        except ValueError:
            send(peer, "Неверный формат даты. Формат: " + format_date_string)
            return
    if not message and not attachments:
        cmd.print_usage(peer)
        return

    list_attachments = get_list_attachments(attachments, peer)

    if not list_attachments and not message:
        send(peer, "Не удалось создать")
        return

    event_id = groupsmgr.create_event(chat, tag, date_to_db, message, list_attachments)

    send(peer, "Успешно добавлено новое событие " + str(event_id))


def exec_choose_chat_keyboard(cmd, chat, peer, sender, args):
    chats_sender = groupsmgr.get_chats_user(sender)
    if not chats_sender:
        send(peer, "Вас нет ни в одной беседе")
        return
    page = args[0]
    max_chats = 6
    if page > (len(chats_sender) - 1) // max_chats:
        page = 0
    elif page < 0:
        page = (len(chats_sender) - 1) // max_chats
    keyboard = VkKeyboard()
    for number, chat_number in enumerate(chats_sender[page * max_chats:(page * max_chats + max_chats) if page * max_chats + max_chats <= len(chats_sender) else len(chats_sender)]):
        if number % 2 == 0 and number != 0:
            keyboard.add_line()
        keyboard.add_button(chat_number['name'],
                            payload={'action': 'стартовая_клавиатура', 'chat_id': chat_number['chat_id']})
    if max_chats < len(chats_sender) or chat != -1:
        keyboard.add_line()
    response = "Выберите беседу \n"

    if max_chats < len(chats_sender):
        response += 'Cтр. ' + str(page + 1)
        keyboard.add_button('Назад',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'выбор_беседы', 'chat_id': chat, 'args': [page - 1]})
    if chat != -1:
        keyboard.add_button('Выход',
                            color=VkKeyboardColor.NEGATIVE,
                            payload={'action': 'настройки_выбор', 'chat_id': chat})
    if max_chats < len(chats_sender):
        keyboard.add_button('Далее',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'выбор_беседы', 'chat_id': chat, 'args': [page + 1]})
    send(peer, response, [], keyboard.get_keyboard())


def exec_choose_members_group(cmd, chat, peer, sender, args):
    existing = groupsmgr.get_all_groups(chat)
    if not existing:
        send(peer, "Групп не найдено", [], start_keyboard(chat))
        return
    page = args[0]
    max_groups = 6
    if page > (len(existing) - 1) // max_groups:
        page = 0
    elif page < 0:
        page = (len(existing) - 1) // max_groups
    keyboard = VkKeyboard()
    for number, group in enumerate(existing[page * max_groups:(page * max_groups + max_groups) if page * max_groups + max_groups <= len(existing) else len(existing)]):
        if number % 2 == 0 and number != 0:
            keyboard.add_line()
        keyboard.add_button(group,
                            payload={'action': 'состав_группы', 'chat_id': chat, 'args': [group]})
    keyboard.add_line()
    response = "Выберите группу \n"
    if max_groups < len(existing):
        response += 'Cтр. ' + str(page + 1)
        keyboard.add_button('Назад',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'состав_группы_выбор', 'chat_id': chat, 'args': [page - 1]})
    keyboard.add_button('Выход',
                        color=VkKeyboardColor.NEGATIVE,
                        payload={'action': 'стартовая_клавиатура', 'chat_id': chat})
    if max_groups < len(existing):
        keyboard.add_button('Далее',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'состав_группы_выбор', 'chat_id': chat, 'args': [page + 1]})

    send(peer, response, [], keyboard.get_keyboard())


def exec_choose_tag_email(cmd, chat, peer, sender, args):
    tags = groupsmgr.get_all_emails(chat)
    if not tags:
        send(peer, "Теги почты не найдены", [], start_keyboard(chat))
        return
    page = args[0]
    max_tags = 6
    if page > (len(tags) - 1) // max_tags:
        page = 0
    elif page < 0:
        page = (len(tags) - 1) // max_tags
    keyboard = VkKeyboard()
    for number, tag in enumerate(tags[page * max_tags:(page * max_tags + max_tags) if page * max_tags + max_tags <= len(tags) else len(tags)]):
        if number % 2 == 0 and number != 0:
            keyboard.add_line()
        keyboard.add_button(tag,
                            payload={'action': 'почта_выбор_события', 'chat_id': chat, 'args': [tag, 0]})
    keyboard.add_line()
    response = "Выберите тег почты \n"
    if max_tags < len(tags):
        response += 'Cтр. ' + str(page + 1)
        keyboard.add_button('Назад',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'почта_выбор_тег', 'chat_id': chat, 'args': [page - 1]})
    keyboard.add_button('Выход',
                        color=VkKeyboardColor.NEGATIVE,
                        payload={'action': 'стартовая_клавиатура', 'chat_id': chat})
    if max_tags < len(tags):
        keyboard.add_button('Далее',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'почта_выбор_тег', 'chat_id': chat, 'args': [page + 1]})

    send(peer, response, [], keyboard.get_keyboard())


def exec_choose_events_email(cmd, chat, peer, sender, args):
    tag = args[0]
    events = groupsmgr.get_events_for_email(chat, tag)
    events.reverse()
    if not events:
        send(peer, "События не найдёны", [], start_keyboard(chat))
        return
    page = args[1]
    max_events = 6
    if page > (len(events) - 1) // max_events:
        page = 0
    elif page < 0:
        page = (len(events) - 1) // max_events
    keyboard = VkKeyboard()
    for number, event in enumerate(events[page * max_events:(page * max_events + max_events) if page * max_events + max_events <= len(events) else len(events)]):
        if number % 2 == 0 and number != 0:
            keyboard.add_line()
        keyboard.add_button(event['date'],
                            payload={'action': 'событие', 'chat_id': chat, 'args': [tag, event['id']]})
    keyboard.add_line()
    response = "Выберите дату и время события \n"
    if max_events < len(events):
        response += 'Cтр. ' + str(page + 1)
        keyboard.add_button('Назад',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'почта_выбор_события', 'chat_id': chat, 'args': [tag, page - 1]})
    keyboard.add_button('Выход',
                        color=VkKeyboardColor.NEGATIVE,
                        payload={'action': 'почта_выбор_тег', 'chat_id': chat, 'args': [0]})
    if max_events < len(events):
        keyboard.add_button('Далее',
                            color=VkKeyboardColor.PRIMARY,
                            payload={'action': 'почта_выбор_события', 'chat_id': chat, 'args': [tag, page + 1]})

    send(peer, response, [], keyboard.get_keyboard())


def exec_choose_join_group(cmd, chat, peer, sender, args):
    response, keyboard = join_keyboard(chat, peer, sender, args[0])
    send(peer, response, [], keyboard)


def exec_choose_left_group(cmd, chat, peer, sender, args):
    response, keyboard = left_keyboard(chat, peer, sender, args[0])
    send(peer, response, [], keyboard)


def exec_choose_settings(cmd, chat, peer, sender):
    keyboard = VkKeyboard()
    keyboard.add_button('Выбор активной беседы',
                        color=VkKeyboardColor.PRIMARY,
                        payload={'action': 'выбор_беседы', 'chat_id': chat, 'args': [0]})
    keyboard.add_line()
    keyboard.add_button('Выход',
                        color=VkKeyboardColor.NEGATIVE,
                        payload={'action': 'стартовая_клавиатура', 'chat_id': chat})
    response = 'Выберите настройки'
    send(peer, response, [], keyboard.get_keyboard())


def exec_send_start_keyboard(cmd, chat, peer, sender):
    send(peer, 'Стартовое меню', [], start_keyboard(chat))


def exec_all_groups(cmd, chat, peer, sender):
    existing = groupsmgr.get_all_groups(chat)
    response = 'Все группы: \n'
    for number, group in enumerate(existing):
        response += str(number + 1) + '. ' + group + ' \n'
    if existing:
        send(peer, response, [], start_keyboard(chat))
    else:
        send(peer, 'Не нашла групп в беседе', [], start_keyboard(chat))


def exec_my_groups(cmd, chat, peer, sender):
    sender_groups = groupsmgr.get_user_groups(chat, sender)
    response = 'Ваши группы: \n'
    for number, group in enumerate(sender_groups):
        response += str(number + 1) + '. ' + group + ' \n'
    if sender_groups:
        send(peer, response, [], start_keyboard(chat))
    else:
        send(peer, 'Вы не состоите не в какой из групп', [], start_keyboard(chat))


def exec_members_group(cmd, chat, peer, sender, args):
    group = args[0]
    existing = groupsmgr.get_all_groups(chat)
    if group not in existing:
        send(peer, 'Такой группы нет', [], start_keyboard(chat))

    members = groupsmgr.get_members_group(chat, group)

    if members:
        response = 'Участники: \n'
        users_vk = vk.users.get(user_ids=members)
        for number, user in enumerate(users_vk):
            response += str(number + 1) + ". " + user["first_name"] + " " + user[
                "last_name"] + " \n"
        send(peer, response, [], start_keyboard(chat))
    else:
        send(peer, 'Эта группа пуста', [], start_keyboard(chat))


def exec_event_email(cmd, chat, peer, sender, args):
    tag = args[0]
    event_id = args[1]

    events = groupsmgr.get_events_for_email(chat, tag)
    for event in events:
        if event["id"] == event_id:
            response = 'Номер события: ' + str(event["id"]) + ' \n'
            send(peer, response + event['message'], event['attachments'], start_keyboard(chat))
            return
    send(peer, "Не найдено событие (возможно удалено)", [], start_keyboard(chat))


def pings_str(chat, groups, sender=None):
    ping_list = []
    for group in groups:
        users = groupsmgr.get_members_group(chat, group)
        for user in users:
            if user not in ping_list and user != sender:
                ping_list.append(user)
    users_vk = vk.users.get(user_ids=ping_list)
    response = ''
    for user_vk in users_vk:
        response += '[id{}|{}] '.format(user_vk['id'], user_vk['first_name'])
    return response


def exec_ping_groups(chat, peer, sender, groups):
    ping_string = pings_str(chat, groups, sender)
    if ping_string:
        user_vk = vk.users.get(user_id=sender)
        response = user_vk[0]['first_name'] + ' ' + user_vk[0]['last_name'] + ' хочет сообщить важную новость! \n☝☝☝☝☝☝☝☝☝☝ \n' + ping_string + '\n☝☝☝☝☝☝☝☝☝☝ \n'
        send(peer, response)


def exec_sending_messages(chat, peer, sender, groups, message, attachments):
    sending_list = []
    for group in groups:
        users = groupsmgr.get_members_group(chat, group)
        for user in users:
            if user not in sending_list:  # добавил, что себе сообщение тоже отправляется
                sending_list.append(user)
    if sending_list:
        user_vk = vk.users.get(user_id=sender, name_case='ins')
        message = re.sub(r'(?:\s|^)@([a-zA-Zа-яА-ЯёЁ0-9_]+)\+(?=[\s .,:;?()!]|$)', '', message)
        chat_name = groupsmgr.get_name_chat(chat)
        response = "Отправлено" + " {0} {1} ".format(user_vk[0]["first_name"], user_vk[0]["last_name"]) + 'из беседы - ' + chat_name + ': \n' + message
        error_send = []
        list_attachments = get_list_attachments(attachments, peer)
        for user in sending_list:
            try:
                send(user, response, list_attachments)
            except:
                error_send.append(user)
                pass
        if error_send:
            response = 'Не удалось отправить этим людям, так как они со мной даже не общались(((: \n'
            users_vk = vk.users.get(user_ids=error_send)
            for number, user_vk in enumerate(users_vk):
                response += str(number + 1) + '. {0} {1}'.format(user_vk[0]["first_name"], user_vk[0]["last_name"]) + '\n'
            send(peer, response)
        else:
            response = 'Успешно сделала рассылку'
            send(peer, response)


def exec_impostor_track(chat, sender):
    groupsmgr.add_all_user(chat, sender)


def exec_check_user_in_chat(chat, sender):
    if sender not in groupsmgr.get_all_users(chat):
        groupsmgr.add_user_to_chat(chat, sender)
