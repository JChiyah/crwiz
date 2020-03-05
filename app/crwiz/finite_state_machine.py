
"""
finite_state_machine
--------------------

Finite State Machine that controls the dialogue states in each active room.
Dialogue states are loaded at initialisation in self._load_states()

Author: Javier Chiyah, Heriot-Watt University, 2019
"""

import os
import random
from typing import Dict, Tuple

import numpy.random

from .. import db

from ..models.log import get_user_logs_for_event
from ..models.state_history import StateHistory, get_user_states, \
	check_used_state

from . import logger_crwiz, dialogue_state, fake_actions
from .utils import helper, constants, dialogue_utils
from .active_room import ActiveRoom, Subtask


MIN_TRANSITION_UTTERANCES = 1
INITIAL_STATE = 'start'


class FiniteStateMachine(object):

	def __init__(self):
		# users with limited actions (e.g. must wait for an operator answer)
		self._limited_users = {}
		self.states: Dict[str, dialogue_state.DialogueState] = {}
		self._load_states()
		logger_crwiz.debug(
			f"Finite State Machine: {len(self.states.keys())} states loaded")

	def _load_states(self):
		"""
		Loads the dialogue states into the FiniteStateMachine

		:return: None
		"""
		root_folder = os.path.join(os.path.split(
			os.path.abspath(__file__))[0], "..", "..")

		states_folder_path = os.path.join(
			root_folder, 'knowledge_base', 'dialogue_states')
		self.states = dialogue_state.load_dialogue_states(states_folder_path)

		self.fixed_states = [
			state.name for state in self.states.values() if state.is_fixed]

	def get_state_utterances(
		self, state_name: str, user_id=None, keep_formulations: bool = True) -> list:
		# return [
		# 	{'utterance': utt, 'state_name': state_name}
		# 	for utt in self.get_state(state_name).utterances
		# ]
		# only get 1 of the state paraphrases
		state = self.states[state_name]
		if state and len(state.formulations) > 0 \
			and state.formulations[0] != state_name:

			formulation = None
			if keep_formulations and user_id:
				# get the last formulation of the state
				formulation = get_last_state_formulation(user_id, state)

			return [{
					'utterance': formulation if formulation is not None
					else random.choice(state.formulations),
					'state_name': state_name
				}]
		else:
			logger_crwiz.warning(f"Cannot get state utterances for '{state_name}'")
			return []

	def get_states_utterances(self, state_names: list, user_id=None) -> list:
		utterances = []
		for state_name in state_names:
			# there can be more than 1 utterance for the same transition
			# (e.g. alternative ways of saying it)
			# for now, we just get 1 of them
			utterances.extend(self.get_state_utterances(state_name, user_id))

		return utterances

	def get_state_transition_probabilities(
		self, state_name, filter_fixed: bool = True) -> Dict[str, float]:
		state = self.states[state_name]
		if not state.transition_probabilities and not state.transitions:
			return {}
		else:
			final_result = {}
			try:
				# build probabilities based on number of transitions for those missing
				for transition, probability in state.transition_probabilities:
					if not filter_fixed or not self.states[transition].is_fixed:
						final_result[transition] = probability

				# normalise the result, so the probabilities sum to 1
				sum_prob = sum(final_result.values())
				# logger_crwiz.debug(f"Prob sum for {state_name} is {sum_prob}")
				if sum_prob != 1:
					for key, val in final_result.items():
						final_result[key] = val / sum_prob
					# if the sum value is still not 1, add the remainder to a prob
					sum_prob = sum(final_result.values())
					if sum_prob != 1:
						key = random.choice(final_result.keys())
						final_result[key] = final_result[key] + (1 - sum_prob)
				logger_crwiz.debug(
					f"Hint for {state_name} computed to {final_result} "
					f"({sum(final_result.values())}/1.0)")
			except Exception as e:
				print(f"Exception! {e}")

			return final_result

	def get_additional_utterances(self, active_room: ActiveRoom) -> list:
		additional_utterances = []
		user_states = get_user_states(active_room.wizard_id)

		if user_states and len(user_states) > 0:
			# remove latest state (because it already doesn't have enough utterances)
			current_state = user_states.pop(0)

			while len(user_states) > 0:
				# get state
				this_state = user_states[0].current_state
				# get transition states for that state
				state_transitions = self.states[this_state].transitions

				# filter those that do not correspond to current subtask
				state_transitions = self.filter_transitions_by_subtask(
					state_transitions, active_room.current_subtask)

				# get the utterances for those transition states in a list
				state_utterances = self.get_states_utterances(
					state_transitions, active_room.wizard_id)

				# filter utterances by those already used
				state_utterances = filter_used_transitions(
					active_room.wizard_id, state_utterances)
				if len(state_utterances) > 0:
					# add them to the list of additional utterances
					additional_utterances.extend(state_utterances)
					# break the loop if we found 1 state with possible transitions
					break
				else:
					# keep looping until no more states or state with transitions
					user_states.pop(0)

			if len(additional_utterances) > 0:
				logger_crwiz.debug(
					f"Adding extra utterances at state "
					f"'{current_state.current_state}': "
					f"{[utt['state_name'] for utt in additional_utterances]}")
		# return additional_utterances[:utterances_needed]
		return additional_utterances

	def filter_transitions_by_subtask(self, transitions: list, subtask: Subtask):
		filtered_transitions = []
		for transition in transitions:
			if self.states[transition].subtask is None \
				or subtask.name == self.states[transition].subtask:
				filtered_transitions.append(transition)

		return filtered_transitions

	@staticmethod
	def post_process_utterances(utterance_list: list) -> list:
		result = []
		for choice in utterance_list:
			choice['utterance'] = choice['utterance'].strip()
			# capitalise only the first letter (so capitalize() is not suitable)
			choice['utterance'] = \
				choice['utterance'][:1].upper() + choice['utterance'][1:]
			result.append(choice)

		# order by importance here if needed

		return result

	def initialise_room_fsa(self, active_room: ActiveRoom):
		self.submit_dialogue_choice(active_room, INITIAL_STATE, '')

	def get_current_state_utterances(self, active_room: ActiveRoom) -> dict:
		transitions = self.states[active_room.current_state].transitions

		# filter those that do not correspond to current subtask
		transitions = self.filter_transitions_by_subtask(
			transitions, active_room.current_subtask)

		# get the utterances for those transition states
		transition_utterances = self.get_states_utterances(
			transitions, active_room.wizard_id)

		# add a few more transition formulations if there are not enough
		if len(transition_utterances) < MIN_TRANSITION_UTTERANCES:
			transition_utterances.extend(
				self.get_additional_utterances(active_room))

		# remove duplicated
		tmp_utterances = []
		for utterance in transition_utterances:
			for utt in tmp_utterances:
				if utt['state_name'] == utterance['state_name']:
					break
			else:
				tmp_utterances.append(utterance)
		transition_utterances = tmp_utterances

		final_utterances = self.post_process_utterances(transition_utterances)

		active_room.log_user_event(constants.EVENT_FSM_GET_TRANSITIONS, {
			'current_state': active_room.current_state,
			'possible_utterances': final_utterances
		})

		response = {
			'choice_selection': {
				'allow_free_text': True,
				'show_static_utterances': True,
				'elements': final_utterances
			}
		}

		if fake_actions.state_contains_action(active_room.current_state):
			fake_actions.emit_action(active_room)

		return response

	def submit_dialogue_choice(self, active_room: ActiveRoom, state_name, text):
		if state_name not in self.states.keys():
			print(self.states)

			raise ValueError(f"State '{state_name}' not found in self.states")

		active_room.current_state = state_name
		db.session.add(StateHistory(
			user_id=active_room.wizard_id,
			previous_state=active_room.previous_state,
			utterance=text,
			current_state=state_name
		))

		active_room.log_user_event(constants.EVENT_FSM_CHANGE_STATE, {
			'previous_state': active_room.previous_state,
			'utterance': text,
			'current_state': state_name
		})
		db.session.commit()

		response = {}

		return response

	def get_task_hint(self, active_room: ActiveRoom) -> Tuple[dict, dict]:
		# only give hint if not requested for the same state before
		# or if we are in a limiting state
		if active_room.current_state_hint is None:
			probabilities = self.get_state_transition_probabilities(
				active_room.current_state)
			state_utterances = self.get_current_state_utterances(active_room)
			utterances = [
				utt['state_name']
				for utt in state_utterances['choice_selection']['elements']]

			# compute hint
			hint = None
			if len(probabilities) > 0:
				try:
					for _ in range(1000):
						tmp_hint = numpy.random.choice(
							list(probabilities.keys()), 1,
							p=list(probabilities.values()))[0]
						if tmp_hint in utterances:
							hint = tmp_hint
							break
				except ValueError:
					pass

			if hint is None:
				hint = random.choice(utterances)
				logger_crwiz.debug(f"Selected random hint {hint} from {utterances}")

			state_name = [
				state['state_name']
				for state in state_utterances['choice_selection']['elements']
				if state['state_name'] == hint][0]

			# utterance_id is more useful than state_name for the interface
			response = {
				'utterance_id': state_name,
				# 'state_name': hint,
				'probability': probabilities[hint] if hint in probabilities else 0,
			}

			active_room.log_user_event("fsa_request_task_hint", {
					'current_state': active_room.current_state,
					**response
				})
		else:
			response = active_room.current_state_hint
			state_utterances = self.get_current_state_utterances(active_room)

			active_room.log_user_event("fsa_request_task_hint_again", {
					'current_state': active_room.current_state,
					**response
				})

		db.session.commit()

		return response, state_utterances


def get_last_state_formulation(user_id, state: dialogue_state.DialogueState):
	"""
	Get the last formulation used for a given state. It will
	only get this formulation if the dialogue state has not
	changed since the last get_state_utterance and if it exists.

	:param user_id: id of the wizard
	:param state: dialogue state
	:return: str with formulation or None
	"""
	logs = get_user_logs_for_event(user_id, constants.EVENT_FSM_GET_TRANSITIONS)
	if len(logs) == 0 or logs[0]['data']['current_state'] != \
		dialogue_utils.get_user_dialogue_state(user_id):
		# this does not apply if there are not previous formulations at this state
		return None

	else:
		last_utterances = logs[0]['data']['possible_utterances']
		for utterance in last_utterances:
			if utterance['state_name'] == state.name:
				for formulation in state.formulations:
					if helper.match_utterance_to_state_formulation(
						utterance['utterance'], formulation):
						return formulation

	return None


def filter_used_transitions(user_id, state_utterances: list) -> list:
	filtered_transitions = []

	for state_utterance in state_utterances:
		# avoid adding states that trigger gazebo
		if not check_used_state(user_id, state_utterance['state_name']):
			# state not used before
			filtered_transitions.append(state_utterance)

	return filtered_transitions
