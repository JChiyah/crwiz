

# Events

EVENT_POST_TASK_ANALYSIS = 'post_task_analysis'
EVENT_START_TASK = 'start_task'
EVENT_END_TASK = 'end_task'
EVENT_USER_END_TASK = 'user_end_task'
EVENT_DISCONNECT_END_TASK = 'disconnect_end_task'

EVENT_STATUS_UPDATE = 'status_update'

EVENT_START_GAZEBO_STREAM = 'start_gazebo_stream'
EVENT_GAZEBO_STREAM_UPDATE = 'gazebo_stream_update'
EVENT_END_GAZEBO_STREAM = 'end_gazebo_stream'

EVENT_ADVANCE_SUBTASK = 'advance_subtask'

EVENT_QUIZ_TRIGGER = 'operator_quiz_trigger'
EVENT_QUIZ_RESPONSE = 'operator_quiz_response'
EVENT_QUIZ_TIMEOUT = 'operator_quiz_timeout'

EVENT_GENERATE_GAME_TOKEN = 'generate_game_token'

EVENT_FSM_GET_TRANSITIONS = 'fsa_get_state_transitions'
EVENT_FSM_CHANGE_STATE = 'fsa_state_change'


# Task End Type IDs
TASK_END_DIALOGUE = 'dialogue_completed'
TASK_END_TIME_OUT = 'time_out'
TASK_END_UNSPECIFIED = 'unspecified'
TASK_END_USER_TRIGGERED = 'user_triggered'
TASK_END_USER_DISCONNECTED = 'user_disconnected'


# State Constants

# states that are named one thing but appear
# as a different one as a probability file (state_name, probability_file)
STATES_WITH_PROBABILITY_MAPPING = {
	'inform_alert_emergency':   'inform_alert',
	'inform_robot_available':   'inform_robot',
	'inform_robot_battery':     'inform_battery_level',
	'inform_robot_eta':         'inform_eta',
	'inform_robot_location':    'inform_robot_status',
	'intro_hello':              'intro_state'
}
