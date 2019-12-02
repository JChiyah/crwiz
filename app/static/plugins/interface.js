
// console.log("Interface script loaded");

const SHOW_INSTRUCTIONS_ON_START = true;


/** Constants for certain classes and IDs **/

const ID_POPUP_MODAL_INSTRUCTIONS = "popup-modal-instructions";
const ID_FREE_TEXT_UTTERANCE = "utterance-free-text";
const ID_BTN_HINT = "btn-hint";
const ID_INPUT_QUIZ_ANSWER = "quiz-answer";
const ID_FORM_QUIZ_SUBMIT = "quiz-submit";

/** Templates for the interface **/

const TEMPLATE_TASK_PROGRESS = `
	<div>
		<h6>Game progress:</h6>
		<div class="progress">
			<div class="milestone-outer">
				<div class="milestone" data-width="30">
					<span>1. Identify</span>
				</div>
				<div class="milestone" data-width="60">
					<span>2. Resolve</span>
				</div>
				<div class="milestone" data-width="90">
					<span>3. Assess</span>
				</div>
				<div class="milestone milestone-final" data-width="100">
					<span>Finish</span>
				</div>
			</div>
			<div class="progress-bar" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100"></div>
		</div>
	</div>`;

const TEMPLATE_LAYOUT_WIZARD = `
	<div class="row" id="commands-st">
		<div class="col-sm-12">
			${TEMPLATE_TASK_PROGRESS}
			<p>Select an option from below:</p>
			<ul class="list-group" id="list-utterances">
				<li class="list-group-item list-header">Dialogue Options</li>
			</ul>
			<ul class="list-group" id="list-utterances-general">
				<li class="list-group-item list-header">General Dialogue</li>
			</ul>
			<div class="row" style="margin: 0;">
				<div class="helper-div"></div>
				<button type="submit" id="type-submit" class="btn btn-primary">
					<i class="fa fa-paper-plane" aria-hidden="true"></i> Send
				</button>
				<div class="helper-div" style="flex: 3">
					<button type="button" id="${ID_BTN_HINT}" class="btn btn-info"
						disabled data-toggle="tooltip" data-placement="top"
						title="You only have a limited amount of hints, use wisely!">
						I need a hint!</button>
				</div>
			</div>
			<div id="typing"></div>
		</div>
	</div>`;

// these are now DialogueStates in the back-end
const GENERAL_DIALOGUE_OPTIONS = {
	"holdon2seconds": "Hold on, 2 seconds",
	"yes": "Yes",
	"no": "No",
	"actionperformed": "Action performed",
	"okay": "Okay",
	"sorrycanyourepeatthat": "Sorry, can you repeat that?",
	"idonthavethatinformationatthemoment": "Don't know"
	// "repeat": "",
	// "ack_misunderstood": "",
	// "info_not_available": "",
	// "UNK": "", // free text
};

const FREE_TEXT_STATE_NAME = "UNK";

const TEMPLATE_GENERAL_DIALOGUE_OPTION = `
	<li class="list-group-item custom-control custom-radio utterance-option" data-state="{state_name}">
		<input class="custom-control-input" type="radio" name="dialogueOption" id="dialogueOption{option_id}" value="{option_id}">
		<label class="custom-control-label" for="dialogueOption{option_id}">
			{text}
		</label>
	</li>`;

const TEMPLATE_DIALOGUE_OPTION = TEMPLATE_GENERAL_DIALOGUE_OPTION
	.replace(/utterance-option/g, "utterance-option utterance-option-dynamic");

const TEMPLATE_DIALOGUE_FREE_TEXT = TEMPLATE_DIALOGUE_OPTION
	.replace(/data-state="{state_name}/, `id="${ID_FREE_TEXT_UTTERANCE}"`)
	.replace(/{text}/g, "<button type=\"button\" class=\"btn btn-light btn-sm\">Click to enter your own text</button>");

const TEMPLATE_LAYOUT_OPERATOR = `
	<div class="row" id="commands-st">
		<div class="col-sm-12" style="display: flex; flex-direction: column;">
			${TEMPLATE_TASK_PROGRESS}
			<h5>Game Information</h5>

			<div class="row">
				<div class="col-sm-4">
					<h6>Offshore processing facility map:</h6>
					<img src="static/media/scenario_above.png" class="facility-map" />
				</div>
				<div class="col-sm-8">
				</div>
			</div>

			<div id="typing"></div>
		</div>
	</div>`;

const TEMPLATE_INSTRUCTIONS_IMPORTANT = `
	<hr/>
	<p><strong>Important!</strong> Upon finishing the game, you will be given a code in the chat. You must enter this code back in the Amazon Mechanical Turk questionnaire to get paid. Do not reload or close this window until you have entered the code to avoid any issues.</p>
	<p>You can read these instructions again using the button at the top-right corner of the window.</p>`;
const TEMPLATE_INSTRUCTIONS_OPERATOR = `
	<div class=\"container\">
		<p>Welcome to the Emergency Response Game! You are the operator... etc.</p>
		${TEMPLATE_INSTRUCTIONS_IMPORTANT}
	</div>`;
const TEMPLATE_INSTRUCTIONS_WIZARD = `
	<div class=\"container\">
		<p>Welcome to the Emergency Response Game! You are the Wizard... etc.</p>
		${TEMPLATE_INSTRUCTIONS_IMPORTANT}
	</div>`;

const TEMPLATE_FREE_TEXT_INPUT = "<input type=\"text\" class=\"form-control form-control-sm\" placeholder=\"Enter your message here\" autocomplete=\"off\">";


/**
 * Checks if the current user's room is a task room
 *
 * @return {Boolean} true if current room is as task room
 */
function isTaskRoom() {
	return self_room !== undefined && self_room.startsWith("wizard_task");
}

function formatString(stringToFormat, dataObject) {
	Object.keys(dataObject).forEach(function (key) {
		stringToFormat = stringToFormat
			.replace(new RegExp(`{${key}}`, "g"), dataObject[key]);
	});
	return stringToFormat;
}

function buildDialogueOption(template, dataObject) {
	dataObject['option_id'] = dataObject.state_name !== undefined ?
		dataObject.state_name : dataObject.text.replace(/(\s|'|\?)+/g, "");
	return formatString(template, dataObject);
}

function preloadImages(arrayOfImages) {
	$(arrayOfImages).each(function () {
		$('<img />').attr('src',this).appendTo('body').css('display','none');
	});
}

function applyOperatorLayout() {
	if (!isTaskRoom())
		return;

	$("#type-area").show();

	let sidebar = $("#sidebar");
	sidebar.addClass("task-layout");
	sidebar.append(TEMPLATE_LAYOUT_OPERATOR);

	$("#" + ID_POPUP_MODAL_INSTRUCTIONS)
		.find(".modal-body")
		.html(TEMPLATE_INSTRUCTIONS_OPERATOR);
}

function applyWizardLayout() {
	$("fieldset").children().remove();
	adjustWindowHeight();

	if (!isTaskRoom())
		return;

	let sidebar = $("#sidebar");
	sidebar.addClass("task-layout");
	sidebar.append(TEMPLATE_LAYOUT_WIZARD);

	let uttList = $("#list-utterances-general");
	Object.keys(GENERAL_DIALOGUE_OPTIONS).forEach(function (key) {
		uttList.append(buildDialogueOption(
			TEMPLATE_GENERAL_DIALOGUE_OPTION,
			{text: GENERAL_DIALOGUE_OPTIONS[key], state_name: key}
		));
	});

	$(`#${ID_POPUP_MODAL_INSTRUCTIONS}`)
		.find(".modal-body")
		.html(TEMPLATE_INSTRUCTIONS_WIZARD);
}

function modifyLayoutByRole() {

	// enable/disable user chat depending on the room type
	// if (self_room_read_only || self_room === "waiting_room") {
	// 	disableUserChat();
	// 	// enableUserChat();
	// } else {
	// 	// disableUserChat();
	// }

	if (isTaskRoom() && !self_room_read_only) {
		// choose which layout to show
		if (isWizard()) {
			applyWizardLayout();
		} else {
			applyOperatorLayout();
		}

		if (SHOW_INSTRUCTIONS_ON_START)
			$("#popup-modal-instructions").modal("show");
		$(".navbar .container-fluid .row button").show();

	} else {
		disableUserChat();
		$(".navbar .container-fluid .row button").hide();
		$("#type-area").hide();
	}

	adjustWindowHeight();

	// preload GIF so they are shown instantly in the chat
	setTimeout(() => preloadImages([
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-husky-move-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-husky-inspect_before-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-husky-inspect_after-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-husky-extinguish_before-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-husky-extinguish_after-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-husky-assess-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-quadcopter-move-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-quadcopter-inspect_before-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-quadcopter-inspect_after-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-quadcopter-extinguish_before-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-quadcopter-extinguish_after-360.gif",
		"http://www2.macs.hw.ac.uk/orca-slurk/media/transitions/orca_study-quadcopter-assess-360.gif",
	]), 2000);
}


function adjustWindowHeight() {
	// set the height of the outer content to be equal to the maximum size of the window minus the height of the header
	let outerHeight = $(window).height() - $("header").height();
	$(".content-outer").css("height", outerHeight + "px");

	// set the height of the inner content to be equal to the maximum size available minus the height of the #type-area
	let innerHeight = outerHeight;
	if ($("#type-area").is(":visible")) {
		// only substract the height of #type-area if it is visible
		innerHeight -= $("#type-area").outerHeight();
	}
	$(".content-inner").css("height", innerHeight + "px");

	// scroll
	let content = $("#content");
	content.animate({ scrollTop: content.prop("scrollHeight") }, 0);
}
