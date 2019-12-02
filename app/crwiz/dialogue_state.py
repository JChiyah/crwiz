
import os
import yaml
import shutil
from typing import List, Dict

from . import logger_crwiz


STATES_TO_IGNORE = []


class DialogueState:

	def __init__(
		self, name: str, formulations: List[str], transition_states: List[str],
		transition_probabilities: Dict[str, float],
		subtask: str = None, slots: list = None):
		self._name = name
		self._formulations = formulations
		self._transition_states = transition_states
		self._transition_probabilities = transition_probabilities

		# make sure that all transitions have a probability
		diff_elem = list(set(
			self.transition_probabilities.keys()).difference(self.transitions))
		for elem in diff_elem:
			self._transition_probabilities[elem] = 0

		if sum(self.transition_probabilities.values()) == 0:
			for transition in self.transition_probabilities.keys():
				self._transition_probabilities[transition] = \
					1 / len(self.transition_probabilities.keys())

		self._subtask = subtask
		self._slots = slots

		if not self.formulations:
			logger_crwiz.warning(f'No formulations found in state \'{self.name}\'')

	@property
	def name(self) -> str:
		return self._name

	@property
	def formulations(self) -> List[str]:
		return self._formulations

	@property
	def transitions(self) -> List[str]:
		return [
			transition for transition in self._transition_states
			if transition not in STATES_TO_IGNORE]

	@property
	def transition_probabilities(self) -> Dict[str, float]:
		return self._transition_probabilities

	@property
	def subtask(self):
		return self._subtask

	@property
	def slots(self) -> list:
		return self._slots

	@property
	def is_fixed(self) -> bool:
		return False

	@classmethod
	def from_yaml_file(cls, yaml_file: str):
		"""
		Creates a new DialogueState from a file with state properties.

		:param yaml_file: file path to open
		:return: DialogueState
		"""
		state_properties = yaml.safe_load(open(yaml_file).read())

		return cls(
			state_properties['name'], state_properties['formulations']
			if 'formulations' in state_properties else [],
			state_properties['transition_states']
			if 'transition_states' in state_properties else [],
			state_properties['transition_probabilities']
			if 'transition_probabilities' in state_properties else [],
			state_properties['subtask'] if 'subtask' in state_properties else None,
			state_properties['slots'] if 'slots' in state_properties else []
		)

	def get_transition_probability(self, state_name: str) -> float:
		"""
		Gets the transition probability from this state to another one.
		Returns 0 if there is no probability for that state.

		:param state_name: name of the following state
		:return: float, 0 if not found
		"""
		# if state_name in self._transition_probabilities:
		return self._transition_probabilities[state_name]
		# else:
		# 	return 0


class FixedDialogueState(DialogueState):

	def __init__(self, name: str, formulation: str):
		super().__init__(name, [formulation], [], {})

	@property
	def is_fixed(self) -> bool:
		return True

	@classmethod
	def from_yaml_file(cls, yaml_file: str):
		"""
		Creates a list of FixedDialogueStates from a file.

		:param yaml_file: file path to open
		:return: Dict[str, FixedDialogueState]
		"""
		file_properties = yaml.safe_load(open(yaml_file).read())
		states = {}
		for name, formulation in file_properties.items():
			states[name] = cls(name, formulation)

		return states


def load_dialogue_states(folder_path: str) -> Dict[str, DialogueState]:
	"""
	Loads the YAML files in the folder to a dict of DialogueStates.

	:param folder_path: folder with YAML files
	:return: dict of DialogueStates
	"""
	# copy files in the folder to a secure location
	load_path = os.getcwd() + os.sep + 'loaded_states'
	_prepare_load_folder(load_path, folder_path)

	# load states
	loaded_states = {}
	for file in os.listdir(load_path):
		if file.endswith('.yaml'):
			file_path = load_path + os.sep + file
			if file.startswith('fixed_states'):
				loaded_states = {
					**loaded_states,
					**FixedDialogueState.from_yaml_file(file_path)}
			else:
				# transform file if needed
				_preprocess_yaml_file(file_path)

				tmp_state = DialogueState.from_yaml_file(file_path)
				if tmp_state.name in loaded_states:
					logger_orca.warning(f'Overwriting state \'{tmp_state.name}\'')
				loaded_states[tmp_state.name] = tmp_state

	return loaded_states


def _prepare_load_folder(load_path: str, folder_path: str):
	"""
	Prepares the load folder with a copy of the YAML files to load the states.

	:param load_path: folder path to copy dialogue files to.
		WARNING: all its contents will be deleted on load
	:param folder_path: folder with the original dialogue state files
	:return: None
	"""
	try:
		# remove folder
		shutil.rmtree(load_path)
	except FileNotFoundError:
		pass
	os.makedirs(load_path, exist_ok=True)

	for file in os.listdir(folder_path):
		if file.endswith('.yaml'):
			shutil.copy(f'{folder_path}{os.sep}{file}', f'{load_path}{os.sep}{file}')


def _preprocess_yaml_file(file_path: str):
	"""
	Preprocess a file and changes it so it can be loaded as a dialogue state.

	:param file_path: full path to file
	:return: None
	"""
	properties = yaml.safe_load(open(file_path).read())

	if 'transition_probabilities' not in properties:
		properties['transition_probabilities'] = {}

	yaml.dump(properties, open(file_path, mode='w'), sort_keys=False)
