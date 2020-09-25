"""Teleradiobot

TODO:
    * Add logs
    * Add tests
    * Better keyboard
    * Handle exceptions
    * Add localization
"""

import json
from datetime import datetime, timedelta
from pprint import pprint

import telebot

with open("config.json", 'r') as conf:
    config = json.load(conf)


bot = telebot.TeleBot(config["token"], parse_mode="Markdown")

COMMANDS = {
    "help": "Get help.",
    "howto": "Get explanaition on how to use bot.",
    "authorize": "authorize yourself",
    "tune": "Tune the radio.",
    "detune": "Detune the radio.",
    "broadcast": "Start broadcasting.",
    "endbroadcast": "End broadcasting.",
    "changepassword": "Change access password.",
}


class Broadcast(object):
    def __init__(self) -> None:
        self.active = False
        self.start_date = datetime.now()
        self.timeout_date = datetime.now()
        self.time_limit = timedelta(minutes=10)

    def show_keyboard(self):
        if self.active:
            keyboard = make_keyboard(
                firstrow=[' ', '/endbroadcast'], width=2)
        else:
            keyboard = make_keyboard(['/broadcast', ' '])
        return keyboard

    def start(self):
        self.active = True
        self.start_date = datetime.now()
        self.timeout_date = self.start_date + self.time_limit

    def stop(self):
        self.active = False
        self.timeout_date = datetime.now()


broadcast = Broadcast()


# @


def check_receiver(func):
    """Decorator. Check if the message sender has permissions."""

    def inner(message):
        uid = message.from_user.id
        if message.from_user.id in _get_speakers_ids():
            func(message)
        else:
            bot.send_message(
                uid,
                "You are not allowed to do this. "
                "Please, /authorize")

    return inner


def check_admin(func):
    """Decorator. Check if the message sender is a group administrator."""
    def inner(message):
        if not message.chat.type == 'private':
            admins = bot.get_chat_administrators(message.chat.id)
            admin_ids = map(lambda a: a.user.id, admins)
            if message.from_user.id in admin_ids:
                func(message)
            else:
                bot.reply_to(message, "You need admin privileges to do this. ")
        else:
            func(message)

    return inner


def make_keyboard(firstrow=[], extra=[], width=1, last='/help', kwargs={}):
    """Add reply keyboard

        Parameters:
            replies(list): list of replies
            width(int): max width of rows
            cancel(bool): set to False if you don't want cancel btn to appear
    """
    keyb = telebot.types.ReplyKeyboardMarkup(row_width=width, **kwargs)
    if firstrow:
        keyb.row(*firstrow)
    if extra:
        keyb.add(*extra)
    if last:
        keyb.row(last)
    return keyb


K_MAIN = broadcast.show_keyboard()


def update_config():
    pprint(config)
    with open("config.json", 'w') as conf:
        json.dump(config, conf, indent=4)


def send_to_speakers(message, **kwargs):
    for uid in _get_speakers_ids():
        bot.send_message(uid, message, **kwargs)


def _get_speakers_names():
    admin_names = [aid for username, aid in config["speakers"]]
    return admin_names


def _get_speakers_ids():
    admin_ids = [aid for username, aid in config["speakers"]]
    return admin_ids


def _get_receivers():
    return config["receivers"]


def _stop_broadcast():
    broadcast.active = False


def _add_receiver(receiver_id):
    config["receivers"].append(receiver_id)
    update_config()


def _remove_receiver(receiver_index):
    config["receivers"].pop(receiver_index)
    update_config()


def _add_admin(username, uid):
    config["speakers"].append([username, uid])
    update_config()


# COMMANDS


@bot.message_handler(commands=['help', 'start'])
def get_help(message):
    info = '\n'.join(
        ["/{}: {}".format(command, description)
         for command, description in COMMANDS.items()])
    bot.reply_to(message, info, reply_markup=K_MAIN)


@bot.message_handler(commands=['howto'])
def command_how_to(message):
    instructions = "Here is how to"
    bot.send_message(message.from_user.id, instructions)


# AUTHORIZATION


@bot.message_handler(commands=["authorize"])
def authorize(message):
    if not message.chat.type == "private":
        return bot.reply_to(message, "Let's find some private place.")
    if message.from_user.id in _get_speakers_ids():
        bot.reply_to(message, "You're already authorized.")
        return
    msg = bot.reply_to(
        message, "Password: ")
    bot.register_next_step_handler(msg, grant_access)


def grant_access(message):
    """Add user permission to broadcast."""
    cid = message.chat.id

    if message.text == config["password"]:
        _add_admin(message.chat.username, message.chat.id)
        bot.send_message(
            cid,
            "User {} is now authorized.".format(message.chat.username))
    else:
        bot.send_message(cid, "Try again later.")
        # TODO: last_try_time


@bot.message_handler(commands=["changepassword"])
def change_password(message):
    """Change access password using bot's token."""
    force_reply = telebot.types.ForceReply()
    cid = message.chat.id

    def handle_new_password(token):
        if token.text == config["token"]:
            def change_password(new_password):
                send_to_speakers(
                    "Access password changed. Please, /authorize again.",
                    reply_markup=K_MAIN)
                config["speakers"] = []
                config["password"] = new_password.text  # TODO: Refactor
                update_config()

            msg = bot.send_message(
                cid, "Enter new password", reply_markup=force_reply)
            bot.register_next_step_handler(msg, change_password)
        else:
            return bot.reply_to(message, "Something went wrong.")

    reply = bot.reply_to(message, 'Bot token: ', reply_markup=force_reply)
    bot.register_next_step_handler(reply, handle_new_password)


# RECEIVER


@bot.message_handler(commands=['tune'])
@check_admin
def tune(message):
    """Add chat to the receivers group."""
    cid = message.chat.id
    if cid in _get_receivers():
        bot.send_message(cid, "Already on.")
        return
    _add_receiver(cid)
    bot.send_message(cid, 'Listening...')


@bot.message_handler(commands=["detune"])
@check_admin
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


# BROADCASTING


@bot.message_handler(commands=["broadcast"])
@check_receiver
def start_broadcast(message):
    """Start broadcasting messages to all your receivers."""
    broadcast.start()
    user = message.from_user.username
    send_to_speakers(
        "{} started broadcasting.".format(user),
        reply_markup=broadcast.show_keyboard(),
        disable_notification=True)


@bot.message_handler(commands=['endbroadcast'])
@check_receiver
def stop_broadcast(message):
    broadcast.stop()
    send_to_speakers(
        "Broadcast stopped.",
        reply_markup=broadcast.show_keyboard())


def check_broadcast():
    """Automatically stops broadcast after 10 minutes."""
    if datetime.now() > broadcast.timeout_date:
        broadcast.stop()
        send_to_speakers(
            "Broadcast timed out.",
            reply_markup=broadcast.show_keyboard())


main_content_types = [
    'audio', 'photo', 'voice', 'video', 'document',
    'text', 'location', 'contact', 'sticker', 'venue', 'poll']
"""List with all common message types."""


@bot.message_handler(content_types=main_content_types)
def transmit(message):
    pprint(message.__dict__)
    print()
    pprint(message.chat.__dict__)
    check_broadcast()
    if any([
            not broadcast.active,
            message.chat.type != 'private',
            message.from_user.id not in _get_speakers_ids()]):
        return

    mtype = message.content_type
    func, content = None, []  # Made to avoid linter problems.
    kwargs = {"disable_notification": True}
    if mtype == 'text':
        func = bot.send_message
        content = [message.text]
    elif mtype == 'sticker':
        func = bot.send_sticker
        content = [message.sticker.file_id]
    elif mtype == 'photo':
        func = bot.send_photo
        content = [message.photo[-1].file_id]
    elif mtype == 'audio':
        func = bot.send_audio
        content = [message.audio.file_id]
    elif mtype == 'voice':
        func = bot.send_voice
        content = [message.voice.file_id]
    elif mtype == 'document':
        func = bot.send_document
        content = [message.document.file_id]
    elif mtype == 'contact':
        func = bot.send_contact()
        content = [message.contact.phone_name, message.contact.first_name]
    elif mtype == 'poll':
        poll = message.poll
        func = bot.send_poll
        opts = list([option.text for option in poll.options])
        content = [poll.question, opts]
        kwargs = {**message.json['poll']}
        del kwargs['options'], kwargs['id'], kwargs['total_voter_count'], \
            kwargs['question']
    elif mtype == 'video':
        func = bot.send_video
        content = [message.video.file_id]
    elif mtype == 'video_note':
        func = bot.send_video_note
        content = [message.video_note]
    elif mtype == 'location':
        func = bot.send_location
        content = [message.location.latitude, message.location.longitude]
    elif mtype == 'venue':
        func = bot.send_venue
        ven = message.venue
        content = [
            ven.location.latitude, ven.location.longitude,
            ven.title, ven.address]
    elif mtype == 'action':
        pass
        # sendChatAction
        # action_string can be one of the following strings: 'typing',
        # 'upload_photo', 'record_video', 'upload_video',
        # 'record_audio', 'upload_audio', 'upload_document' or 'find_location'.
        # bot.send_chat_action(chat_id, action_string)
    else:
        bot.send_message('Unsupported message type {}'.format(mtype))

    def send(function, cid, content, kwargs):
        return function(cid, *content, **kwargs)

    for receiver_id in _get_receivers():
        send(func, receiver_id, content, kwargs)


def main():
    send_to_speakers("Bot restarted.", reply_markup=K_MAIN)
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        _stop_broadcast()
        send_to_speakers("Error occured: {}".format(e), reply_markup=K_MAIN)


if __name__ == "__main__":
    main()
