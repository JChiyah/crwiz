
import argparse
import logging.config
import os
import signal
import sys
import threading
from logging import getLogger

import requests
from socketIO_client import BaseNamespace, SocketIO


TIMER_DISCONNECTED_USER = 15  # how long to wait before closing the room in seconds

# import log_utils from crwiz using a relative path (to avoid issues in deployment)
root_folder = os.path.join(os.path.split(os.path.abspath(__file__))[0], "..", "..")
sys.path.insert(0, os.path.join(root_folder, "app", "crwiz", "utils"))
sys.path.insert(0, os.path.join(root_folder, "app"))
import log_utils

logging.config.fileConfig(
	fname=os.path.join(root_folder, "bots", "logging.conf"),
	disable_existing_loggers=False,
	defaults={'logfilename': os.path.join(root_folder, "logs", "app", "helperbot.log")}
)


uri = None
token = None
header = None
bot_name = "HelperBot"
logger = getLogger(bot_name.lower())


class StatusUpdateThread(threading.Thread):
	"""
	deprecated
	Thread to execute a function in an interval (e.g. every 1 second).

	Currently used to send a status_update every second to the
	front-end and synchronise timers.

	:param func: function to execute
	:param interval: seconds to wait between function calls as a
		float (1 second as default)
	"""

	def __init__(self, func, interval=1.0):
		super().__init__()
		self.func = func
		self.interval = interval
		self.stopped = threading.Event()

	def run(self):
		while not self.stopped.wait(self.interval):
			self.func()

	def terminate(self):
		self.stopped.set()


# Define the namespace
class ChatNamespace(BaseNamespace):

	# Called when connected
	def __init__(self, io, path):
		super().__init__(io, path)
		# handle SIGTERM signals to disconnect the chatbot gracefully
		# signal.signal(signal.SIGINT, self.terminate)
		signal.signal(signal.SIGTERM, self.terminate)
		self.terminated = False

		self.bot_id = 0
		self.bot = None

		self.disconnected_users = []

		self.on('user_connect', self.on_user_connect)
		self.on('user_disconnect', self.on_user_disconnect)
		self.on('close_room', self.on_close_room)
		self.on('user_finish_task', self.on_user_finish_task)
		self.emit("ready")

	def terminate(self, term_signal, frame):
		if not self.terminated:
			self.disconnect()

	def on_disconnect(self):
		# empty at this moment, but left in case is needed
		if self.terminated:
			return
		else:
			self.terminated = True

	def on_user_connect(self, data):
		"""
		Triggered when the bot receives an "user_connect" socket event.
		It sends messages to the other users in the room to let them know
		that one of them has reconnected.

		:param data: dict with information about user and room
		:return: None
		"""
		if data['user']['id'] in self.disconnected_users:
			self.disconnected_users.remove(data['user']['id'])

			# send messages to users
			for user_id in data['room']['users']:
				if user_id == data['user']['id']:
					# send msg to the user that reconnected
					self.emit('text', {
						'msg': f"You reconnected!",
						'receiver_id': user_id,
						'room': data['room']['name']
					}, self.message_response)
					pass
				elif user_id != self.bot_id:
					# send msg to the other user in the room
					self.emit('text', {
						'msg': f"{data['user']['name']} has reconnected!",
						'receiver_id': user_id,
						'room': data['room']['name']
					}, self.message_response)

	def on_user_disconnect(self, data):
		"""
		Triggered when the bot receives an "user_disconnect" socket event.
		It sends messages to the other users in the room to let them know
		that one of them has disconnected.

		:param data: dict with information about user and room
		:return: None
		"""
		if data['user']['id'] not in self.disconnected_users:
			self.disconnected_users.append(data['user']['id'])
			self.start_disconnected_user_timer(
				data['room']['name'], data['user']['id'])

		# send msg to the other user in the room (either operator or wizard)
		for user_id in data['room']['users']:
			if user_id != self.bot_id and user_id != data['user']['id']:
				self.emit('text', {
						'msg': f"It looks like {data['user']['name']} has "
								"disconnected. "
								"Please, wait for them to come back...",
						'receiver_id': user_id,
						'room': data['room']['name']
					}, self.message_response)
				break

	def on_joined_room(self, data):
		bot = requests.get(f"{uri}/user/{data['user']}", headers=header)
		self.bot = bot.json()
		self.bot_id = self.bot['id']

		if not bot.ok:
			logger.critical("Could not get bot")
			sys.exit(2)

		room_name = data['room']
		room = requests.get(f"{uri}/room/{room_name}", headers=header)
		if not room.ok:
			logger.critical("Could not get room")
			sys.exit(3)

		logger.info(f"{bot_name} joined '{room.json()['name']}'")

	# Called on `status` events
	def on_status(self, status):
		# logger.warning(status)
		if status['type'] == 'join':
			logger.debug(f"User {status['user']['id']} joined {status['room']}")
		elif status['type'] == 'leave':
			logger.debug(f"User {status['user']['id']} left {status['room']}")

	def on_new_task_room(self, data):
		room_name = data['room']

		self.emit("join_room", {'room': room_name}, self.join_room_feedback)

		self.emit(
			'text', {
				'msg': f"Welcome to the emergency response game! "
						"You can find the instructions on "
						"the right-hand side corner of this window.",
				'broadcast': True,
				'room': room_name
			}, self.message_response)

		self.emit(
			'text', {
				'msg': f"Do not reload or close this window until the game is "
						"finished. I will let you know when it finishes and give "
						"you your completion code.",
				'broadcast': True,
				'room': room_name
			}, self.message_response)

	# intercept messages and check them
	def on_text_message(self, data):
		# no need to do this anymore
		pass

	def on_close_room(self, data):
		"""
		Triggered when a close_room socket event is received.
		It finishes the task in the room and gives the
		game token to the participants.

		:param data: with 'room_name' in it
		:return: None
		"""
		logger.info(f"Task finished in room '{data.get('room_name')}'")

		# allow 1 second before sending the final messages
		# so user's messages do not get mixed
		threading.Timer(1, self.send_task_finished_messages, [data]).start()

	def send_task_finished_messages(self, data):
		room_name = data.get('room_name')

		if data.get('reason', None):
			self.emit('text', {
					'msg': data.get('reason'),
					'broadcast': True,
					'room': room_name}, self.message_response)

		self.emit('text', {
				'msg': "The game has finished. Thank you for participating!",
				'broadcast': True,
				'room': room_name}, self.message_response)

		self.emit('text', {
				'msg': "Please enter the following token into the Amazon "
						"Mechanical Turk webpage before closing this browser window.",
				'broadcast': True,
				'room': room_name}, self.message_response)

		# user_ids = list(self.get_room_users(room_name).keys())
		# send tokens to each user
		for user_id, user_data in data['participants'].items():
			self.emit('text', {
					'msg': f"Here is your Amazon Token: {user_data['game_token']}",
					'receiver_id': user_id,
					'room': room_name
				}, self.message_response)

		self.emit('text', {
				'msg': f"The chat room is now closed.",
				'broadcast': True,
				'room': room_name
			}, self.message_response)

		# wait a bit to leave the room so the users get these messages
		# before closing the room permanently
		threading.Timer(1, self.leave_task_room, [room_name]).start()

	def leave_task_room(self, room_name):
		self.emit("leave_room", {'room': room_name}, self.leave_room_feedback)

		log_utils.export_room_logs(uri, token, room_name)

		# report back to the server that the bot has finished with the room
		self.emit("close_room_feedback", {'room_name': room_name})

	def on_user_finish_task(self, data):
		"""
		Triggered when the user has decided to end the task.
		It sends a message to each user to let them know.

		:param data: data
		:return: None
		"""
		for user_id, user_name in data['participants'].items():
			if str(user_id) == str(data['user_id']):
				# this is the user who initiated the finish_task
				self.emit('text', {
					'msg': "You have decided to end the game. "
							"We hope you enjoyed it!",
					'receiver_id': user_id,
					'room': data['room_name']
				}, self.message_response)
			else:
				# this is the other participant
				self.emit('text', {
					'msg': f"{data['participants'][str(data['user_id'])]} "
							"has decided to end the game. "
							"We hope you enjoyed it!",
					'receiver_id': user_id,
					'room': data['room_name']
				}, self.message_response)

	def start_disconnected_user_timer(self, room_name, user_id):
		threading.Timer(
			TIMER_DISCONNECTED_USER,
			self.trigger_disconnected_user_timer, [room_name, user_id]).start()

	def trigger_disconnected_user_timer(self, room_name, user_id):
		if user_id in self.disconnected_users:
			# user still disconnected, so close room
			self.emit("close_room_on_disconnect", {
				'room_name': room_name,
				'disconnected_user_id': user_id
			})

	@staticmethod
	def post_log(user_id, data) -> bool:
		request = requests.post(
			f"{uri}/user/{user_id}/log", json=data, headers=header)
		if not request.ok:
			logger.warning(
				f"Error trying to log data for user {user_id} - "
				f"request: [{request}] - data: [{data}]")

		return request.ok

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
	def join_room_feedback(success, error=None):
		if not success:
			logger.warning(f"Could not join room:", error)
			sys.exit(4)

	@staticmethod
	def leave_room_feedback(success, error=None):
		if not success:
			logger.warning(f"Could not leave room:", error)
			sys.exit(4)

	@staticmethod
	def message_response(success, error=None):
		if not success:
			logger.warning(f"Could not send message:", error)
			sys.exit(4)

	@staticmethod
	def update_permissions_feedback(success, error=None):
		# we don't care much about this one
		if not success:
			logger.warning(f"Could not update user permissions: {error}")
			sys.exit(4)


if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='Run HelperBot')

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

	parser.add_argument(
		'-t', '--token',
		help='token for logging in as bot (see SERVURL/token)',
		**token)
	parser.add_argument(
		'-c', '--chat_host',
		help='full URL (protocol, hostname; ending with /) of chat server',
		**chat_host)
	parser.add_argument(
		'-p', '--chat_port',
		type=int,
		help='port of chat server',
		**chat_port)
	args = parser.parse_args()

	uri = args.chat_host
	if args.chat_port:
		uri += f":{args.chat_port}"

	logger.info(
		f"Running {bot_name} on {uri} with token {args.token}")
	uri += "/api/v2"
	token = args.token
	header = {'Authorization': f"Token {token}"}

	# We pass token and name in request header
	socketIO = SocketIO(
		args.chat_host, args.chat_port,
		headers={'Authorization': args.token, 'Name': 'HelperBot'},
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
