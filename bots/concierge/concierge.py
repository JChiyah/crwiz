
import signal
import requests
import sys
import os
import argparse
import threading
import logging.config
from logging import getLogger

from uuid import uuid1
from socketIO_client import SocketIO, BaseNamespace


DEBUG = False


root_folder = os.path.join(os.path.split(
    os.path.abspath(__file__))[0], "..", "..")
sys.path.insert(0, os.path.join(root_folder, "app", "crwiz", "utils"))
sys.path.insert(0, os.path.join(root_folder, "app"))
import log_utils

logging.config.fileConfig(
    fname=os.path.join(root_folder, "bots", "logging.conf"),
    disable_existing_loggers=False,
    defaults={'logfilename': os.path.join(
        root_folder, "logs", "app", "conciergebot.log")}
)

# import enum to change role of user - let's not mix packages...
# from app.models.user import UserRole
ROLE_OPERATOR = 2
ROLE_WIZARD = 3

# how often to send a message to the database to avoid timeout, in seconds
DB_TIMER = 5 * 60
USER_WAIT_TIMER = 3 * 60
USER_WAIT_INTERVAL = 30


uri = None
token = None
header = None
bot_name = "ConciergeBot"
logger = getLogger(bot_name.lower())


def message_response(success, error=None):
    if not success:
        logger.warning(f"Could not send message:", error)
        sys.exit(2)
    logger.debug("message sent successfully")


# Define the namespace
class ChatNamespace(BaseNamespace):
    tasks = {}

    # Called when connected
    def __init__(self, io, path):
        super().__init__(io, path)
        # handle SIGTERM signals to disconnect the chatbot gracefully
        # signal.signal(signal.SIGINT, self.terminate)
        signal.signal(signal.SIGTERM, self.terminate)
        self.terminated = False
        self.timer_thread = None
        self.user_wait_timer = None
        self.start_timer()

    def terminate(self, term_signal, frame):
        if not self.terminated:
            self.disconnect()

    def on_disconnect(self):
        if self.terminated:
            return
        else:
            self.terminated = True
            self.timer_thread.cancel()
            try:
                logger.info("Disconnecting")
            except NameError:
                # There is a Python bug that happens if we try
                # to log at shutdown (eg. after SIGTERM signal),
                # see https://bugs.python.org/issue26789
                pass

    def start_timer(self):
        logger.info("Sending control message to avoid DB timeout")
        log_utils.get_room_logs(uri, token, "waiting_room")
        self.timer_thread = threading.Timer(DB_TIMER, self.start_timer)
        self.timer_thread.start()

    @staticmethod
    def get_user_task(user):
        task = requests.get(f"{uri}/user/{user['id']}/task", headers=header)
        if not task.ok:
            logger.warning(f"Could not get user task")
            sys.exit(2)
        return task.json()

    @staticmethod
    def create_room(label, layout=None, read_only=False,
                    show_users=True, show_latency=False):
        name = '%s-%s' % (label, uuid1())
        room = requests.post(f"{uri}/room",
                             headers=header,
                             json=dict(
                                 name=name,
                                 label=label,
                                 layout=layout,
                                 read_only=read_only,
                                 show_users=show_users,
                                 show_latency=show_latency,
                                 static=False)
                             )
        if not room.ok:
            logger.warning(f"Could not create task room")
            sys.exit(3)
        return room.json()

    # Called on `status` events
    def on_status(self, status):
        if status['type'] == 'join':
            user = status['user']
            task = self.get_user_task(user)
            if task:
                self.user_task_join(user, task, status['room'])
        elif status['type'] == 'leave':
            user = status['user']
            task = self.get_user_task(user)
            if task:
                self.user_task_leave(user, task)

        self.move_users_to_task()

    def user_task_join(self, user, task, room):
        task_id = task['id']
        user_id = user['id']
        # user_name = user['name']

        if task_id not in self.tasks:
            self.tasks[task_id] = task
            self.tasks[task_id]['users'] = {}
        self.tasks[task_id]['users'][user_id] = room

        self.emit(
            "update_user_permissions",
            {'user_id': user_id, 'message_text': False},
            self.update_permissions_feedback)
        self.emit('text', {
                'msg': f'Hello! I am looking for a partner for you, it might '
                       f'take some time, so be patient, please... '
                       f'{user_id if DEBUG else ""}',
                'receiver_id': user_id,
                'room': room
            }, message_response)

    def move_users_to_task(self):
        if len(self.tasks) == 0:
            return
        task_id = list(self.tasks.keys())[0]
        task = self.tasks[task_id]

        if len(task['users']) >= task['num_users']:
            # cancel timers
            if self.user_wait_timer is not None:
                self.user_wait_timer.cancel()
                self.user_wait_timer = None

            users_to_move = list(task['users'].keys())[:2]
            # this is the first user, set its role as wizard
            self.emit(
                "set_user_role",
                {'user_id': users_to_move[0], 'role_id': ROLE_WIZARD},
                self.set_role_feedback)
            self.emit(
                "update_user_permissions",
                {'user_id': users_to_move[0], 'message_text': True},
                self.update_permissions_feedback)

            # this is the second user, set its role to operator
            self.emit(
                "set_user_role",
                {'user_id': users_to_move[1], 'role_id': ROLE_OPERATOR},
                self.set_role_feedback)

            new_room = self.create_room(task['name'], task['layout'])
            self.emit(
                "room_created", {
                    'room': new_room['name'],
                    'task': task_id,
                    'users': users_to_move
                }, self.room_created_feedback)

            logger.info(f"Created room: '{new_room}'")
            for user_id in users_to_move:
                # self.emit(
                #     "update_user_permissions",
                #     {'user_id': user_id, 'message_text': True},
                #     self.update_permissions_feedback)
                self.emit(
                    "leave_room",
                    {'user': user_id, 'room': task['users'][user_id]},
                    self.leave_room_feedback)
                self.emit(
                    "join_room", {'user': user_id, 'room': new_room['name']},
                    self.join_room_feedback)

                # remove user from the list of users from the task
                del task['users'][user_id]

            logger.info(f"Moved users {users_to_move} to {new_room['name']}")

        elif 0 < len(task['users']) <= task['num_users'] \
                and self.user_wait_timer is None:
            # we have some participant(s), but not enough
            # start the user_wait_timer
            self.user_wait_timer = threading.Timer(
                USER_WAIT_INTERVAL, self.user_wait_timeout,
                [task, USER_WAIT_INTERVAL])
            self.user_wait_timer.start()

    def user_wait_timeout(self, task, seconds_passed):
        """
        Triggered every USER_WAIT_INTERVAL whilst a participant
        waits for another one to join.

        :param seconds_passed:
        :return:
        """
        if seconds_passed >= USER_WAIT_TIMER:
            # wait for too long, give them a game token
            for user_id in task['users']:

                game_token = self.get_user_game_token(user_id)

                self.emit('text', {
                    'msg': "Unfortunately, I could not find a partner for you. "
                           "You can wait for someone to enter the game, but we "
                           "will only pay for the time you spent in the room "
                           "until now. You are still eligible to obtain the "
                           "payment bonuses if you decide to keep waiting. In "
                           "this case, another game token would be provided "
                           "after you finish the game with your partner.",
                    'receiver_id': user_id,
                    'room': "waiting_room"
                }, message_response)

                self.emit('text', {
                    'msg': "Please enter the following token into the Amazon"
                           " Turk webpage before closing this browser window.",
                    'receiver_id': user_id,
                    'room': "waiting_room"}, message_response)

                self.emit('text', {
                    'msg': f"Here is your Amazon Token: {game_token}",
                    'receiver_id': user_id,
                    'room': "waiting_room"
                }, message_response)

                log_utils.export_partner_not_found_log(user_id, game_token, seconds_passed)

            self.user_wait_timer = None

        else:
            # still waiting, give message
            for user_id in task['users']:
                self.emit('text', {
                    'msg': "I am still looking for a partner, please wait a "
                           "bit longer... Don't worry though, you will get "
                           "paid for the time you spend waiting.",
                    'receiver_id': user_id,
                    'room': "waiting_room"
                }, message_response)

            self.user_wait_timer = threading.Timer(
                USER_WAIT_INTERVAL, self.user_wait_timeout,
                [task, seconds_passed + USER_WAIT_INTERVAL])
            self.user_wait_timer.start()

    def user_task_leave(self, user, task):
        if not task:
            return

        task_id = task['id']
        user_id = user['id']
        if task_id in self.tasks and user_id in self.tasks[task_id]['users']:
            del self.tasks[task_id]['users'][user_id]

    @staticmethod
    def get_room_users(room_name, include_bot=False) -> dict:
        room = requests.get(f"{uri}/room/{room_name}", headers=header)
        if not room.ok:
            logger.warning(f"Could not get room users")

        room = room.json()
        if "current_users" not in room:
            return {}

        users = room['current_users']

        if not include_bot:
            users.pop(min(list(users.keys())), None)

        return users

    @staticmethod
    def get_user_game_token(user_id) -> str:
        response = requests.post(f"{uri}/user/{user_id}/game_token", headers=header)
        if not response.ok:
            logger.warning(f"Could not get game token for user {user_id} - {response.json()}")

        return response.json()['game_token']

    @staticmethod
    def join_room_feedback(success, error=None):
        if not success:
            logger.warning(f"Could not join room:", error)
            sys.exit(4)
        logger.debug("user joined room")
        sys.stdout.flush()

    @staticmethod
    def leave_room_feedback(success, error=None):
        if not success:
            logger.warning(f"Could not leave room:", error)
            sys.exit(5)
        logger.debug("user left room")
        sys.stdout.flush()

    @staticmethod
    def set_role_feedback(success, error=None):
        # we don't care much about this one
        if not success:
            logger.warning(f"Could not set new role:", error)
            sys.exit(4)
        logger.debug("User changed role")
        sys.stdout.flush()

    @staticmethod
    def update_permissions_feedback(success, error=None):
        # we don't care much about this one
        if not success:
            logger.warning(f"Could not update user permissions:", error)
            sys.exit(4)
        logger.debug("User permissions updated")
        sys.stdout.flush()

    @staticmethod
    def room_created_feedback(success, error=None):
        if not success:
            logger.warning(f"Could not create task room:", error)
            sys.exit(6)
        logger.debug("task room created")
        sys.stdout.flush()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run ConciergeBot')

    if 'TOKEN' in os.environ:
        token = {'default': os.environ['TOKEN']}
    else:
        token = {'required': True}

    if 'CHAT_HOST' in os.environ:
        chat_host = {'default': os.environ['CHAT_HOST']}
    else:
        chat_host = {'default': 'http://localhost'}

    if 'CHAT_PORT' in os.environ:
        chat_port = {'default': os.environ['CHAT_PORT']}
    else:
        chat_port = {'default': None}

    parser.add_argument('-t', '--token',
                        help='token for logging in as bot (see SERVURL/token)',
                        **token)
    parser.add_argument('-c', '--chat_host',
                        help='full URL (protocol, hostname; ending with /) of chat server',
                        **chat_host)
    parser.add_argument('-p', '--chat_port',
                        type=int,
                        help='port of chat server',
                        **chat_port)
    args = parser.parse_args()

    uri = args.chat_host
    if args.chat_port:
        uri += f":{args.chat_port}"

    logger.info(f"Running {bot_name} on {uri} with token {args.token}")

    uri += "/api/v2"
    token = args.token
    header = {'Authorization': f"Token {token}"}

    # We pass token and name in request header
    socketIO = SocketIO(args.chat_host, args.chat_port,
                        headers={'Authorization': args.token, 'Name': bot_name},
                        Namespace=ChatNamespace)
    try:
        socketIO.wait()
    except KeyboardInterrupt:
        pass
    except Exception as ex:
        logger.exception(
            f"There was an unexpected exception: {ex}")
    finally:
        socketIO.disconnect()
