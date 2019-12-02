
import re
import time
# import calendar
# import datetime
from logging import getLogger


def get_unix_timestamp() -> float:
	# return calendar.timegm(datetime.datetime.now().timetuple())
	return time.time()


def match_utterance_to_state_formulation(utterance, state_formulation) -> bool:
	regex1 = re.compile(r"\[.*\]+", re.IGNORECASE)
	regex2 = re.compile(r"{[^}]+}", re.IGNORECASE)
	regex3 = re.compile(r"\s*<[^>]+>\s*", re.IGNORECASE)

	state_formulation = re.sub(regex1, r".*", state_formulation)
	state_formulation = re.sub(r"{area}", r".*", state_formulation)
	state_formulation = re.sub(r"{robot.name}", r"([^\\s]*|.*[0-9])", state_formulation)
	state_formulation = re.sub(regex2, r"[^\\s]*", state_formulation)
	state_formulation = re.sub(regex3, r".*", state_formulation)
	state_formulation = state_formulation.replace("?", r"\?")

	if re.match(regex2, state_formulation) or re.match(regex3, state_formulation):
		getLogger("orca-slurk").warning(
			f"Issue matching instances: {state_formulation} vs {utterance}")

	# print(f"matching {state_formulation} to {utterance}")
	try:
		return bool(re.match(
			f"^{state_formulation.strip()}$", utterance.strip(), re.IGNORECASE))
	except Exception as ex:
		getLogger("orca-slurk").exception(
			f"Exception when trying to match '{state_formulation}' "
			f"to '{utterance}: {ex}")
