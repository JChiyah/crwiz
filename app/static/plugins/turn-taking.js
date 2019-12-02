
// console.log("Turn-taking script loaded");


const TEMPLATE_WAIT_FOR_TURN = "Please, wait for your turn...";
const TEMPLATE_ROOM_CLOSED = "This room is now closed.";


function controlUserTurn() {
	if (!self_room_read_only && self_user !== undefined && (!self.user_turns || (self_user.user_turns && self_user.current_turn))) {
		enableUserChat();
	} else {
		disableUserChat();
	}
}

function disableUserChat() {
	if (isWizard()) {
		disableDialogueChoices();
	} else {
		disableTextInput();
	}
	$("#type-submit").prop("disabled", true);
}

function enableUserChat() {
	if (!self_user.input_enabled) {
		return;
	}
	if (!self_room_read_only && self_user !== undefined && (!self_user.user_turns || (self_user.user_turns && self_user.current_turn))) {
		if (isWizard()) {
			enableDialogueChoices();
		} else {
			enableTextInput();
		}
		$("#type-submit").prop("disabled", false);
	}
}

function closeRoom() {
	if (self_room_read_only) {
		$("fieldset").children().remove();
		// disable the button to finish the task
		$("#btn-finish-task").prop("disabled", true);
		$(`#${ID_BTN_HINT}`).prop("disabled", true);

		disableUserChat();
		// only close room when the user is not undefined (everything has loaded correctly) to make sure the room closes
		let wizardLayout = $("#commands-st");
		if (self_user === undefined || (isWizard() && wizardLayout.length === 0)) {
			setTimeout(() => closeRoom(), 250);
			return;
		}

		// self_user is not undefined by now
		if (isWizard()) {
			wizardLayout.find("p").text(TEMPLATE_ROOM_CLOSED);
			let modalElem = $("#" + ID_POPUP_MODAL);
			modalElem.modal("hide");
			modalElem.remove();
			$(".utterance-option").remove();
			$(".modal-backdrop").remove();
		} else {
			$("#type-area fieldset").remove();
			$("#type-area").prepend("<p style='margin-bottom: 0'>" + TEMPLATE_ROOM_CLOSED + "</p>")
		}

		console.log("Room closed");
		adjustWindowHeight();
	}
}
