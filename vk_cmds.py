import re
from enum import Enum, auto
import groupsmgr
import timetable
import time
# Запрещено создавать группы с этими названиями.
FORBIDDEN_NAMES = ['all', 'все', 'online', 'онлайн', 'здесь', 'here', 'тут']


class Rank(Enum):
    """
    Описание рангов:
    GOVNO     - Не может использовать бота, мне жалко этого человека будет
    WORKER    - Может подключаться и отключаться от групп, также просматривать все группы, свои группы и участников
                группы, может использовать префикс вложений бота, может просматривать ранги участников беседы,
                может использовать расписание и всё с ним связанное
    USER      - Может тегать по группам, может делать рассылки, а также добавлять сообщения в почту группы
    PRO       - Может добавлять новые вложения в группе и переименовывать группы, может делать случайный выбор
                нескольких людей или играть в русскую рулетку
    MODERATOR - Может подключать и отключать участников от групп, а также удалять группы, которые не создавал
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

RANK_HOLOP = 0
RANK_ADMIN = 1
RANK_KING = 2

def exec_next_class(cmd, chat, peer, sender):
    """
    !пара
    """
    sender_groups = groupsmgr.get_user_groups(chat, sender)
    next_class = timetable.next_class(chat, sender_groups)

    if next_class is None:
        cmd.send(peer, '🚫 На сегодня всё. Иди поспи, что ли.')
    else:
        class_data = next_class[0]
        time_left = timetable.time_left(next_class[1])
        cmd.send(peer, '📚 Следующая пара: %s. До начала %s.' % (class_data, time_left))


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
        name_data = cmd.vk.users.get(user_id=sender)[0]
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

    cmd.send(peer, response)


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
            if group in sender_created_groups or rank_user > RANK_HOLOP:
                deleted.append(group)
                groupsmgr.delete_group(chat, group)
            else:
                not_creator.append(group)
        else:
            not_found.append(group)

    if peer > 2E9:
        name_data = cmd.vk.users.get(user_id=sender)[0]
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

    cmd.send(peer, response)


def exec_join(cmd, chat, peer, sender, args):
    """
    !подключиться
    """
    joined = []
    already_joined = []  # переименновать
    not_found = []

    sender_groups = groupsmgr.get_user_groups(chat, sender)
    existing = groupsmgr.get_all_groups(chat)

    for group in args:
        if group in existing:
            if group not in sender_groups:
                joined.append(group)
                groupsmgr.join_group(chat, group, sender)
            else:
                already_joined.append(group)
        else:
            not_found.append(group)

    if peer > 2E9:
        name_data = cmd.vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    if joined:
        response += 'Добавила вас в эти группы: \n➕ '
        response += ' \n➕ '.join(joined)
        response += ' \n'

    if already_joined:
        response += 'Вы уже состоите в этих группах: \n✔ '
        response += ' \n✔ '.join(already_joined)
        response += ' \n'

    if not_found:
        response += 'Эти группы я не нашла: \n🚫 '
        response += ' \n🚫 '.join(not_found)
        response += ' \n'

    cmd.send(peer, response)


def exec_left(cmd, chat, peer, sender, args):
    """
    !отключиться
    """
    left = []
    already_left = []
    not_found = []

    sender_groups = groupsmgr.get_user_groups(chat, sender)
    existing = groupsmgr.get_all_groups(chat)

    for group in args:
        if group in existing:
            if group in sender_groups:
                left.append(group)
                groupsmgr.left_group(chat, group, sender)
            else:
                already_left.append(group)
        else:
            not_found.append(group)

    if peer > 2E9:
        name_data = cmd.vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    if left:
        response += 'Успешно отключила вас от групп: \n✖ '
        response += ' \n✖ '.join(left)
        response += ' \n'

    if already_left:
        response += 'Вас и не было в этих группах: \n⛔ '
        response += ' \n⛔ '.join(already_left)
        response += ' \n'

    if not_found:
        response += 'Эти группы я не нашла: \n🚫 '
        response += ' \n🚫 '.join(not_found)
        response += ' \n'

    cmd.send(peer, response)


def exec_join_members(cmd, chat, peer, sender, args):
    """
    !подключить
    """
    rank_sender = groupsmgr.get_rank_user(chat, sender)
    if rank_sender == RANK_HOLOP:
        cmd.send(peer, "У вас нет прав")
        return
    if '>' not in args or args.count('>') > 1:
        cmd.print_usage(peer)
        return
    users = re.findall(r'\[id+(\d+)\|\W*\w+\]', ' '.join(args[:args.index('>')]))
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

    all_users_vk = cmd.vk.users.get(user_ids=users)
    first_names_joined = ""
    first_names_not_found = ""
    for user_vk in all_users_vk:  # хрен его знает, мб потом переделаем
        if user_vk["id"] in joined:
            first_names_joined += "{0} > {1} \n".format("[id{0}|{1}]".format(str(user_vk["id"]), user_vk["first_name"]),
                                                        ' '.join(joined[user_vk["id"]]))
        if user_vk["id"] in not_found:
            first_names_not_found += "[id{0}|{1}] \n".format(str(user_vk["id"]), user_vk["first_name"])

    if peer > 2E9:
        name_data = cmd.vk.users.get(user_id=sender)[0]
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

    cmd.send(peer, response)


def exec_left_members(cmd, chat, peer, sender, args):
    """
    !отключить
    """
    rank_sender = groupsmgr.get_rank_user(chat, sender)
    if rank_sender < RANK_KING:
        cmd.send(peer, "У вас нет прав")
        return
    if '>' not in args or args.count('>') > 1:
        cmd.print_usage(peer)
        return
    users = re.findall(r'\[id+(\d+)\|\W*\w+\]', ' '.join(args[:args.index('>')]))
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

    all_users_vk = cmd.vk.users.get(user_ids=users)
    first_names_left = ""
    first_names_not_found = ""
    for user_vk in all_users_vk:  # хрен его знает, мб потом переделаем
        if user_vk["id"] in left:
            first_names_left += "{0} > {1} \n".format("[id{0}|{1}]".format(str(user_vk["id"]), user_vk["first_name"]),
                                                      ' '.join(left[user_vk["id"]]))
        if user_vk["id"] in not_found:
            first_names_not_found += "[id{0}|{1}] \n".format(str(user_vk["id"]), user_vk["first_name"])

    if peer > 2E9:
        name_data = cmd.vk.users.get(user_id=sender)[0]
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

    cmd.send(peer, response)


def exec_rename(cmd, chat, peer, sender, args):
    name_old = args[0]
    name_new = args[1]
    rank_sender = groupsmgr.get_rank_user(chat, sender)
    if rank_sender == RANK_HOLOP:
        cmd.send(peer, "У вас нет прав")
        return

    if name_new in FORBIDDEN_NAMES or len(name_new) < 2 or len(name_new) > 30 or not re.match(r'[a-zA-Zа-яА-ЯёЁ0-9_]',
                                                                                              name_new):
        cmd.send(peer, "Новое название группы является недопустимым: " + name_new)
        return

    existing = groupsmgr.get_all_groups(chat)

    if name_old not in existing:
        cmd.send(peer, "Такой группы нет в базе данных: " + name_old)
        return
    if name_new in existing:
        cmd.send(peer, "Такая группа уже есть в базе данных: " + name_new)
        return

    groupsmgr.rename_group(chat, name_old, name_new)

    if peer > 2E9:
        name_data = cmd.vk.users.get(user_id=sender)[0]
        sender_name = name_data['first_name'] + ' ' + name_data['last_name']
        response = sender_name + '\n'
    else:
        response = ''

    response += 'Успешно установила новое название группы: ' + name_new
    cmd.send(peer, response)


def exec_change_rank(cmd, chat, peer, sender, args):
    """
    Команда, для изменения ранга
    TODO Антоша обязательно сделает, у него в голове норм идея
    """
    pass

def exec_week(cmd, chat, peer, sender):

    if int(time.strftime("%W", time.gmtime(time.time() + 2 * 60 * 60))) % 2 == 0:
        response = "нижняя неделя"
    else:
        response = "верхняя неделя"
    cmd.send(peer, response)
