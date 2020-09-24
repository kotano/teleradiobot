import json
from pprint import pprint

import telebot

with open("config.json", 'r') as conf:
    config = json.load(conf)


bot = telebot.TeleBot(config["token"], parse_mode="Markdown")

COMMANDS = {
    "/help": "Get help.",
    "/authorize": "authorize yourself",
    "/tune": "Tune the radio.",
    "/detune": "Detune the radio.",
    "/broadcast": "Start broadcasting.",
    "/endbroadcast": "End broadcasting.",
    "/changepassword": "Change access password.",
}

broadcasting = False

main_types = [
    'audio', 'photo', 'voice', 'video', 'document',
    'text', 'location', 'contact', 'sticker']
"""List with all common message types."""


# @
def check_permissions(func):
    """Decorator. Check if the message sender has permissions."""

    def inner(message):
        uid = message.from_user.id
        if message.from_user.id in _get_admin_ids():
            func(message)
        else:
            bot.send_message(
                uid,
                "You are not allowed to do this. "
                "Please, /authorize")

    return inner


def make_keyboard(first, extra=[], width=1, last=''):
    """Add reply keyboard

        Parameters:
            replies(list): list of replies
            width(int): max width of rows
            cancel(bool): set to False if you don't want cancel btn to appear
    """
    keyb = telebot.types.ReplyKeyboardMarkup(row_width=width)
    first, *extra = extra
    keyb.row(first)
    if extra:
        keyb.add(*extra)
    if last:
        keyb.row(last)
    return keyb


K_MAIN = make_keyboard(['/broadcast'],)


def update_config():
    pprint(config)
    with open("config.json", 'w') as conf:
        json.dump(config, conf)


def _get_admin_names():
    admin_names = [aid for username, aid in config["admins"]]
    return admin_names


def _get_admin_ids():
    admin_ids = [aid for username, aid in config["admins"]]
    return admin_ids


def _get_receivers():
    return config["receivers"]


def _add_receiver(receiver_id):
    config["receivers"].append(receiver_id)
    update_config()


def _remove_receiver(receiver_index):
    config["receivers"].pop(receiver_index)
    update_config()


def _add_admin(username, uid):
    config["admins"].append([username, uid])
    update_config()


# COMMANDS
@bot.message_handler(commands=['help', 'start'])
def get_help(message):
    info = '\n'.join(
        ["{}: {}".format(command, description)
         for command, description in COMMANDS.items()])
    bot.reply_to(message, info)


# AUTHORIZATION
@bot.message_handler(commands=["authorize"])
def authorize(message):
    if not message.chat.type == "private":
        return bot.reply_to(message, "Let's find some private place.")
    msg = bot.reply_to(
        message, "Password: ")
    bot.register_next_step_handler(msg, grant_access)


def grant_access(message):
    """Add permission to user to broadcast"""
    cid = message.chat.id
    uid = message.from_user.id

    if uid in _get_admin_ids():
        return bot.reply_to(message, "You're already authorized.")

    if message.text == config["password"]:
        _add_admin(message.chat.username, message.chat.id)
        bot.send_message(
            cid,
            "User {} is now authorized.".format(message.chat.username))
    else:
        bot.send_message(cid, "Try again later.")
        # TODO: last_try_time


@bot.message_handler(commands=["changepassword"])
@check_permissions
def change_password(message):
    """Change access password using bot's token."""
    if message.text:
        pass


# BROADCASTING
@bot.message_handler(commands=["broadcast"])
@check_permissions
def start_broadcast(message):
    """Start broadcasting messages to all your receivers."""
    bot.send_message(message.chat.id, "Now everyone listens...")
    global broadcasting
    broadcasting = True


@bot.message_handler(commands=['endbroadcast'])
@check_permissions
def stop_broadcast(message):
    global broadcasting
    broadcasting = False
    bot.send_message(message.chat.id, "We are alone now.")


# RECEIVER
@bot.message_handler(commands=['tune'])
@check_permissions
def tune(message):
    """Add chat to the receivers group."""
    cid = message.chat.id
    if cid in _get_receivers():
        bot.send_message(cid, "Already on.")
        return
    _add_receiver(cid)
    bot.send_message(cid, 'Listening...')


@bot.message_handler(commands=["detune"])
@check_permissions
def detune(message):
    """Stop receiving messages from transmitter."""
    cid = message.chat.id
    try:
        # Look if chat.id is already in a list.
        receiver_index = config["receivers"].index(message.chat.id)
    except ValueError:
        bot.send_message(cid, "Already off.")
        return
    # Remove chat from receivers group.
    _remove_receiver(receiver_index)
    bot.send_message(
        cid,
        "You had your time, you had the power\n"
        "You've yet to have your finest hour\n"
        "Radioo")


@bot.message_handler(content_types=main_types)
def transmit(message):
    pprint(message.__dict__)
    pprint(message.chat)
    if any([
            not broadcasting,
            message.chat.type != 'private',
            message.from_user.id not in _get_admin_ids()]):
        return

    mtype = message.content_type
    func, content = None, None  # Made to avoid linter problems.
    if mtype == 'sticker':
        # f = bot.send_sticker(cid, message.sticker.file_id)
        func = bot.send_sticker
        content = message.sticker.file_id
    elif mtype == 'photo':
        # bot.send_photo(cid, message.photo[-1].file_id)
        func = bot.send_photo
        content = message.photo[-1].file_id
    elif mtype == 'document':
        pass
    else:
        # bot.send_message(cid, message.text)
        func = bot.send_message
        content = message.text

    def do(function, cid, content):
        return function(cid, content)

    for receiver_id in _get_receivers():
        do(func, receiver_id, content)


def main():
    bot.polling(none_stop=True)


if __name__ == "__main__":
    main()
