
import random
import string


def _generate_random_sequence(sequence_length=6) -> str:
	"""
	Generates a random string of letters and digits.

	From https://pynative.com/python-generate-random-string/

	:param sequence_length: length of the output string
	"""
	sequence_options = string.ascii_letters + string.digits
	return ''.join(
		random.choice(sequence_options) for _ in range(sequence_length)
	).upper()


def generate_token() -> str:
	"""
	Generates a game token to confirm that the
	participant has finished the task.

	:return: game token
	"""
	game_token = _generate_random_sequence(8)
	# logger_orca.debug(f"Game token generated: {game_token}")
	return game_token
