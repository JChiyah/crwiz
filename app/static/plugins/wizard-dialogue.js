
// console.log("Wizard-dialogue script loaded");


var initialisationFinished = false;


/**
 * initialisation
 *
 * Initialises the layout and dialogue options once the user has an active socket connection with the server
 */
function initialisation() {
	// wait until self_user has been defined
	if (self_user === undefined) {
		setTimeout(() => initialisation(), 250);
		// console.log("waiting for init");
		return;
	}

	modifyLayoutByRole();
	initialisationFinished = true;

	if (self_room === "waiting_room") {
		$("#type-area").hide();
		adjustWindowHeight();

	} else {
		setTimeout(() => enableDialogueChoices(), 500);
	}

	// initialise all the tooltips
	$("[data-toggle=\"tooltip\"]").tooltip();
}

function disableDialogueChoices() {
	$("#list-utterances .utterance-option").hide();
	adjustWindowHeight();
}

function enableDialogueChoices() {
	// only do it if the initialisation is finished, the user is a wizard, the room is not read only and there are no
	// additional utterances to choose from (aside from fixed utterances)
	if (initialisationFinished &&
		isWizard() &&
		!self_room_read_only &&
		$("#list-utterances .utterance-option-dynamic").length === 0) {
		loadDialogueChoices();
	}
}

async function loadDialogueChoices(reload = false) {
	let uri = location.protocol + "//" + document.domain + ":" + location.port + "/api/v2";
	let dialogueRequest = $.ajax({
		type: "POST",
		url: uri + "/get_wizard_dialogue_choices/" + self_user.id,
		beforeSend: headers,
		contentType: "application/json; charset=utf-8"
	});

	let wizardDialogueChoices = (await dialogueRequest);

	handleDialogueChoicesData(wizardDialogueChoices);
}

var hintButtonTimeout = null;

/**
 * handleDialogueChoicesData
 *
 * Handles the data that comes after requesting the wizard dialogue
 * choices or when a socket event pushes new data
 *
 * @param  {Object} data data with dialogue choices
 */
function handleDialogueChoicesData(data) {
	// console.log(wizardDialogueChoices);
	if (data === undefined) {
		return;
	}

	if (data.hasOwnProperty("choice_selection")) {
		// code for handling choice_selection (as normal)
		setMultipleChoiceText("Select one of the following options:");
		displayMultipleChoice(data.choice_selection);
	}

	// activate the hint button after 5 seconds
	if (hintButtonTimeout != null) {
		clearTimeout(hintButtonTimeout);
		hintButtonTimeout = null;
	}
	hintButtonTimeout = setTimeout(() => {
		if (!self_room_read_only)
			$(`#${ID_BTN_HINT}`).prop("disabled", false);
		}, 5000);
}

/**
 * reloadDialogueChoices
 *
 * Forces a reload of the dialogue choices for the wizard
 * in case the state has changed
 */
function reloadDialogueChoices() {
	// console.log("Reloading");
	setTimeout(() => loadDialogueChoices(true), 500);
}

function disableTextInput() {
	$("#text").prop("readonly", true);
	$("#text").prop("placeholder", TEMPLATE_WAIT_FOR_TURN);
}

function enableTextInput() {
	if (!self_room_read_only) {
		$("#text").prop("readonly", false);
		$("#text").prop("placeholder", "Enter your message here!");
	}
}

function setMultipleChoiceText(text) {
	$("#commands-st p").text(text);
}

const TEMPLATE_DYNAMIC_UTTERANCE_VALUE =
	"<span class=\"dynamic-utt-value {class_value}-value\">{default_value}</span>";
const dynamicUttRegex = new RegExp(/\[.*_dynamic\(.*\)\]/);
const dynamicSpanRegex = new RegExp(/<span class="dynamic-utt-value .*<\/span>/);

/**
 * buildDynamicUtterance
 *
 * Processes a text utterance and builds a basic structure
 * for its dynamic values that need to be updated every so often.
 * This function is the opposite of clearDynamicUtterance().
 *
 * Example:
 * 		text = "We still have [time_left_dynamic(00:30)] before evacuation";
 * 		buildDynamicUtterance(text);
 * 		-> "We still have <span class="dynamic-utt-value time_left-value">{00:30}</span> before evacuation"
 *
 * Afterwards, you can update the dynamic value using something like:
 * 		$(".time_left").text("00:29");
 *
 * @param  {string} utteranceText text to process
 * @return {string}               processed text
 */
function buildDynamicUtterance(utteranceText) {
	var matches = utteranceText.match(dynamicUttRegex);

	if (matches !== null && matches.length > 0) {
		// iterate when we have a dynamic value in the utterance
		matches.forEach(function(matchedString) {
			let classValue = "";
			let defaultValue = "";
			try {
				// get the name of the class and the default value
				classValue = matchedString.match(/\[.*(?=_dynamic\()/)[0].slice(1);
				defaultValue = matchedString.match(/\(.*(?=\))/)[0].slice(1);
			} catch (Exception) {
				// ignore it
				console.error("There was an error with utterance: '" + matchedString + "'");
			}

			utteranceText = utteranceText.replace(matchedString,
				TEMPLATE_DYNAMIC_UTTERANCE_VALUE
					.replace("{class_value}", classValue)
					.replace("{default_value}", defaultValue)
			);
		});
	}

	return utteranceText;
}

/**
 * clearDynamicUtterance
 *
 * Processes a text utterance and removes the structure created around
 * dynamic values to send a clean text utterance to the back-end.
 * This function is the opposite of buildDynamicUtterance().
 *
 * Example:
 * 		text = "We still have <span class="dynamic-utt-value time_left-value">00:30</span> before evacuation";
 * 		clearDynamicUtterance(text);
 * 		-> "We still have 00:30 before evacuation"
 *
 * @param  {string} utteranceText text to process
 * @return {string}               processed text
 */
function clearDynamicUtterance(utteranceText) {
	var matches = utteranceText.match(dynamicSpanRegex);

	if (matches !== null && matches.length > 0) {
		// iterate when we have a dynamic value in the utterance
		matches.forEach(function(matchedString) {
			let currentValue = "";
			try {
				currentValue = matchedString.match(/>.*(?=<\/span>)/)[0].slice(1);
			} catch (Exception) {
				// ignore it
				console.error("There was an error with utterance: '" + matchedString + "'");
			}

			utteranceText = utteranceText.replace(matchedString, currentValue);
		});
	}

	return utteranceText;
}

function displayMultipleChoice(choiceObject) {
	// get state id of the selected utterance
	let selectedUtterance = getMultipleChoiceValue();
	removeDynamicMultipleChoiceUtterances();

	let targetContainer = $("#list-utterances");

	// add the utterances
	if (choiceObject.hasOwnProperty("elements")) {
		choiceObject.elements.forEach(function (choiceElem) {
			if (choiceElem !== undefined && choiceElem.utterance !== "") {
				targetContainer.append(buildDialogueOption(
					TEMPLATE_DIALOGUE_OPTION, {
						text: buildDynamicUtterance(choiceElem.utterance),
						state_name: choiceElem.state_name
					}));
			}
		});
	}

	// add the free text option
	if (choiceObject.hasOwnProperty("allow_free_text") && choiceObject.allow_free_text) {
		targetContainer.append(TEMPLATE_DIALOGUE_FREE_TEXT);
	}

	// check if static utterance should be hidden
	if (choiceObject.hasOwnProperty("show_static_utterances") && !choiceObject.show_static_utterances) {
		// only show dynamic
		// $(".utterance-option").hide();
		$(".utterance-option-dynamic").show();
	} else {
		// show all
		$(".utterance-option").show();
	}

	// if the user had an utterance selected from before,
	// set it as the selected one now too
	// if the state_name is not empty
	if (selectedUtterance.state_name != "") {
		$(`#list-utterances .utterance-option-dynamic[data-state=${selectedUtterance.state_name}]`).click();
	}
	// if the user was writing in the freeText input
	else if (selectedUtterance.hasOwnProperty("freeText")) {
		let freeText = $(`#${ID_FREE_TEXT_UTTERANCE}`);
		freeText.find("button").click();
		freeText.click();
		freeText.find("input").val(selectedUtterance.text);
	}
	// otherwise any other state with not-empty text
	else if (selectedUtterance.text != "") {
		$("#list-utterances .utterance-option").each(function () {
			if (clearDynamicUtterance($(this).text()) == selectedUtterance.text) {
				$(this).click();
				return false;
			}
		});
	}

	adjustWindowHeight();
	updateTaskTimer();
}

/**
 * sendChatMessage
 *
 * Sends a chat message to everyone in the room. It serves as a shortcut for the way that Slurk sends messages.
 *
 * @param {String} message message to send. It will be processed as an image if it starts with "image:<url>"
 */
function sendChatMessage(message) {
	let date = new Date();
	let time = date.getTime() - date.getTimezoneOffset() * 60000;

	if (!message.startsWith("image")) {
		// capitalise first letter of message
		message = message.charAt(0).toUpperCase() + message.slice(1);
	}
	keypress(self_room, self_user, time / 1000, message);
}

/**
 * isWizard
 *
 * Checks if the current user is a wizard
 *
 * @return {Boolean} true if user is a wizard
 */
function isWizard() {
	return self_user !== undefined && self_user.role_id === 3;
}

/**
 * isUserBot
 *
 * Checks if a user given by an ID is a bot
 *
 * @param  {[type]}		userId ID of the user to check
 * @return {Boolean}	true if the userId corresponds to a bot
 */
function isUserBot(userId) {
	return userId in users && users[userId] === "Bot";
}

function getMultipleChoiceValue() {
	let selectedChoice = $(".utterance-option-selected");
	if (selectedChoice.attr("id") === ID_FREE_TEXT_UTTERANCE) {
		selectedChoice = selectedChoice.find("input[type='text']");
		if (selectedChoice.length > 0)
			return {
				text: selectedChoice.val().trim(),
				state_name: FREE_TEXT_STATE_NAME, freeText: true
			};
		else
			return { text: "", state_name: "" };
	} else {
		return {
			text: clearDynamicUtterance(selectedChoice.text()).trim(),
			state_name: selectedChoice.data("state")
		};
	}
}

function clearMultipleChoiceValue() {
	$(".utterance-option-selected").removeClass("utterance-option-selected").find("input").prop("checked", false);
	let freeText = $("#utterance-free-text");
	if (freeText)
		freeText.val("");

}

function removeDynamicMultipleChoiceUtterances() {
	$(".utterance-option-dynamic").remove();
}

function showFreeTextInput() {
	// remove button
	$(`#${ID_FREE_TEXT_UTTERANCE} button`).remove();
	$("#utterance-free-text label").append(TEMPLATE_FREE_TEXT_INPUT);
}

const MISSION_MILESTONES = [30, 60, 90, 100];
function updateProgressBar(percentage) {
	let progressBar = $(".progress-bar");
	progressBar.css("width", `${percentage}%`);
	progressBar.prop("aria-valuenow", `${percentage}%`);

	if (percentage === 100) {
		$(progressBar).css("background-color", "#28a745");
		progressBar.css("border-radius", ".25rem");
	}

	MISSION_MILESTONES.some(function(val) {
		let elem = $(`.milestone[data-width="${val}"]`);
		if (percentage >= val && !elem.hasClass("completed")) {
			elem.removeClass("next").addClass("completed");
		} else if (percentage < val && !elem.hasClass("next") && $(".next").length === 0) {
			elem.addClass("next");
			return true;
		}
	});
}

async function submitDialogueChoice(text, stateName) {
	if (text === undefined || text === "") {
		return;
	}

	$(`#${ID_BTN_HINT}`).prop("disabled", true);
	let uri = location.protocol + "//" + document.domain + ":" + location.port + "/api/v2";
	let request = $.ajax({
		type: "POST",
		url: uri + "/submit_dialogue_choice/" + self_user.id,
		beforeSend: headers,
		data: JSON.stringify({
			text: text,
			state_name: stateName !== undefined ? stateName : ""
		}),
		dataType: "json",
		contentType: "application/json; charset=utf-8"
	});
	request = await request;

	if (request.hasOwnProperty("transition_media")) {
		sendChatMessage("image:" + request.transition_media);
	}
}

let taskTimer = undefined;
let taskRemainingSeconds = 0;

function setTaskTimer(remainingSeconds, running=true) {
	taskRemainingSeconds = remainingSeconds;

	updateTaskTimer();

	if (taskTimer !== undefined) {
		clearInterval(taskTimer);
	}

	if (running) {
		taskTimer = setInterval(function () {
			updateTaskTimer();
			taskRemainingSeconds -= 1;
		}, 1000);
	}
}

function updateTaskTimer() {
	if (taskRemainingSeconds >= 0) {

		let mins = Math.floor(taskRemainingSeconds / 60);
		let secs = taskRemainingSeconds % 60;

		$(".task-timer").text(mins + ":" + ("0" + secs).slice(-2));
		$(".time_left-value").text(mins + ":" + ("0" + secs).slice(-2));

	} else {
		clearInterval(taskTimer);
	}
}


async function requestTaskHint() {
	let uri = location.protocol + "//" + document.domain + ":" + location.port + "/api/v2";
	let hintRequest = $.ajax({
		type: "POST",
		url: uri + "/request_task_hint/" + self_user.id,
		beforeSend: headers,
		contentType: "application/json; charset=utf-8"
	});
	$(".tooltip").remove();

	hintRequest = await hintRequest;

	// setTimeout(function() {
	let utt = $(`.utterance-option[data-state="${hintRequest.state_name}"]`);
	if (utt.length > 0) {
		utt.animatedFlash()
	}
}

// https://stackoverflow.com/questions/275931/how-do-you-make-an-element-flash-in-jquery
$.fn.animatedFlash = function() {
	var fadeToDuration = 200;
	var fadeOpacity = 0.5;
	var revertDuration = 400;
	var revertOpacity = 1.0;

	this.fadeTo(fadeToDuration, fadeOpacity, function() {
		$(this).fadeTo(revertDuration, revertOpacity);
	});
};


$(document).ready(function() {

	let body = $("body");

	$("#btn-finish-task").click(function() {
		if (self_user.can_finish_task) {
			let modalTemplate = TEMPLATE_MODAL_FINISH_AVAILABLE;
			modalTemplate.successCallback = finishTask;
			modifyModalContent(modalTemplate);
		} else {
			modifyModalContent(TEMPLATE_MODAL_FINISH_NOT_AVAILABLE);
		}

		$("#popup-modal").modal("show");
	});

	// deprecated
	body.on("change", "fieldset label input", function () {
		$("fieldset label input").parent().removeClass("checked");
		$("fieldset label input:checked").parent().addClass("checked");
	});

	// deprecated
	body.on("click", "#input-free-text input[type=text]", function () {
		$("#input-free-text input[type=radio]").trigger("click");
	});

	/**
	 * Select utterance from the list when the user is a wizard
	 */
	body.on("click", ".utterance-option", function () {
		clearMultipleChoiceValue();
		// if ($(this).attr("id") !== ID_FREE_TEXT_UTTERANCE || $(this).find("input").length > 0) {
		$(this).addClass("utterance-option-selected");
		$(this).find("input").prop("checked", true);
		// }
	});

	/**
	 * Show free text input after pressing button in Wizard interface
	 */
	body.on("click", `#${ID_FREE_TEXT_UTTERANCE} button`, function () {
		showFreeTextInput();
		// give some time so the utterance-option-selected does not change the focus again
		setTimeout(() => $(`#${ID_FREE_TEXT_UTTERANCE} input[type='text']`).focus(), 100);
	});

	/**
	 * Show hint after button press (hint: make an utterance flash)
	 */
	body.on("click", `#${ID_BTN_HINT}`, function() {
		requestTaskHint();
	});

	body.on("keypress", `#${ID_FREE_TEXT_UTTERANCE} label input`, function(e) {
		let code = e.keyCode || e.which;
		// 13: RETURN key
		if (code === 13) {
			$("#type-submit").click();
		}
	});

	body.on("click", "#type-submit", function () {
		let textInput = $("#text");
		let dialogueText = "";

		if (isWizard()) {
			dialogueText = getMultipleChoiceValue();
			submitDialogueChoice(dialogueText.text, dialogueText.state_name);
			dialogueText = dialogueText.text;
		} else {
			dialogueText = textInput.val().trim();
		}

		if (dialogueText !== "" && !self_room_read_only) {
			// console.log("Sending \"" + dialogueText + "\"");

			sendChatMessage(dialogueText);

			// clear all the fields
			clearMultipleChoiceValue();
			textInput.val("");
			removeDynamicMultipleChoiceUtterances();

			if (isWizard() && !self_user.user_turns) {
				disableUserChat();
				setTimeout(() => { enableUserChat(); }, 1000);
			}

		}
	});

	// initialisation();
});
