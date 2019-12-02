import os
import sys
import signal
from gevent import monkey, subprocess


DATABASE_FILE = "logs/data-dump.sql"


monkey.patch_all(subprocess=True)


from app import app, socketio, stop_bots, close_rooms
from logging import getLogger


def shut_down(signal_r=None, frame_r=None):
	getLogger("crwiz").info("Shutting down the server...")
	stop_bots()
	close_rooms()

	getLogger("crwiz").info("All done - exit!")

	sys.exit(0)


signal.signal(signal.SIGTERM, shut_down)


if __name__ == '__main__':
	host = os.environ.get('HOST', '0.0.0.0')
	port = int(os.environ.get('PORT', 5000))

	try:
		socketio.run(app, host, port, extra_files=[
			"app/templates",
			"app/static/js",
			"app/static/css",
			"app/static/layouts"
		])
	except KeyboardInterrupt:
		pass
	except Exception as ex:
		getLogger("crwiz").exception(
			f"There was an unexpected exception: {ex}")
	finally:
		shut_down()
