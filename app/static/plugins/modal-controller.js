
// console.log("Modal-controller script loaded");


const TEMPLATE_MODAL_FINISH_AVAILABLE = {
	title: "Finish Game",
	body: "You can now finish the game by confirming below. " +
		"The HelperBot will provide you with a code in the chat to submit to " +
		"the Amazon survey. We hope that you enjoyed the game!" +
		"<br/><br/>Please note that you will only be given the bonus if " +
		"you completed all the objectives successfully.",
	confirmBtn: "Finish Game",
	cancelBtn: "Keep Playing",
	successCallback: undefined,
	cancelCallback: undefined,
	callbackArguments: undefined
};

const TEMPLATE_MODAL_FINISH_NOT_AVAILABLE = {
	title: "Finish Game",
	body: "<img src=\"https://media.giphy.com/media/y3QOvy7xxMwKI/giphy.gif\"" +
		" style=\"width: 80%; margin-left: 10%\"/><br/><br/>" +
		"Hmmm... It looks like you haven't spent enough time playing." +
		"<br/>Play a bit longer before finishing the game!",
	confirmBtn: undefined,
	cancelBtn: "Keep Playing",
	successCallback: undefined,
	cancelCallback: undefined,
	callbackArguments: undefined
};

const TEMPLATE_MODAL_PERFORM_ACTION = {
	title: "Action",
	body: "We think that you may want to perform the following action. " +
		"Please select one option depending on what the operator instructed.",
	confirmBtn: undefined,
	cancelBtn: undefined,
	successCallback: performActionCallback,
	cancelCallback: performActionCallback,
	callbackArguments: undefined
};


const ID_POPUP_MODAL = "popup-modal";


function modifyModalContent(modalTemplate) {
	let modalElem = $("#" + ID_POPUP_MODAL);
	modalElem.find(".modal-title").text(modalTemplate.title);
	modalElem.find(".modal-body").html(modalTemplate.body);

	if (modalTemplate.confirmBtn !== undefined)
		modalElem.find(".btn-success").text(modalTemplate.confirmBtn).show();
	else
		modalElem.find(".btn-success").hide();

	if (modalTemplate.cancelBtn !== undefined)
		modalElem.find(".btn-secondary").text(modalTemplate.cancelBtn).show();
	else
		modalElem.find(".btn-secondary").hide();

	// remove previous callbacks
	// success callback
	$(document).off("click", `#${ID_POPUP_MODAL} .btn-success`);
	$(document).one("click", `#${ID_POPUP_MODAL} .btn-success`, function() {
		if (modalTemplate.successCallback !== undefined) {
			if (modalTemplate.callbackArguments !== undefined)
				modalTemplate.successCallback(true, modalTemplate.callbackArguments);
			else
				modalTemplate.successCallback(true);
		}

		$("#" + ID_POPUP_MODAL).modal("hide");
	});
	// cancel callback
	$(document).off("click", `#${ID_POPUP_MODAL} .btn-secondary`);
	$(document).one("click", `#${ID_POPUP_MODAL} .btn-secondary`, function() {
		if (modalTemplate.cancelCallback !== undefined) {
			if (modalTemplate.callbackArguments !== undefined)
				modalTemplate.cancelCallback(false, modalTemplate.callbackArguments);
			else
				modalTemplate.cancelCallback(false);
		}

		$("#" + ID_POPUP_MODAL).modal("hide");
	});
	// for when clicking outside the modal, call the cancel callback too
	$(document).off("hidden.bs.modal", `#${ID_POPUP_MODAL}`);
	$(document).one("hidden.bs.modal", `#${ID_POPUP_MODAL}`, function () {
		if (modalTemplate.cancelCallback !== undefined) {
			if (modalTemplate.callbackArguments !== undefined)
				modalTemplate.cancelCallback(false, modalTemplate.callbackArguments);
			else
				modalTemplate.cancelCallback(false);
		}
	});
}


/**
 * performActionModal
 *
 * Opens a modal to perform an action with the values in data.
 *
 * @param 	{Object}	data
 */
function performActionModal(data) {
	if (isWizard()) {
		let modalTemplate = { ...TEMPLATE_MODAL_PERFORM_ACTION, ...data };
		modalTemplate.callbackArguments = {
			action_name: data.action_name,
			frontend_callback: data.frontend_callback
		};
		modifyModalContent(modalTemplate);
		setTimeout(() => $("#popup-modal").modal("show"), 750);
	}
}


/**
 * performActionCallback
 *
 * Submits the result from the perform action modal.
 *
 * @param 	{boolean} 	callbackResult
 * @param 	{Object}	callbackArguments
 * @returns {Promise<void>}
 */
async function performActionCallback(callbackResult, callbackArguments) {
	let uri = location.protocol + '//' + document.domain + ':' + location.port + "/api/v2";
	let request = $.ajax({
		type: "POST",
		url: uri + "/submit_perform_action/" + self_user.id,
		beforeSend: headers,
		data: JSON.stringify({
			action_name: callbackArguments.action_name,
			result: callbackResult
		}),
		dataType: "json",
		contentType: "application/json; charset=utf-8"
	});
	await request;

	if (callbackArguments.hasOwnProperty("frontend_callback") &&
		callbackArguments.frontend_callback !== null) {
		if ((callbackResult && callbackArguments.frontend_callback.hasOwnProperty("on_confirm"))
			|| (!callbackResult && callbackArguments.frontend_callback.hasOwnProperty("on_cancel"))) {
			// get data inside the callback
			let callbackData = callbackResult ?
				callbackArguments.frontend_callback.on_confirm :
				callbackArguments.frontend_callback.on_cancel;
			callbackData = {
				...callbackData, ...callbackArguments.frontend_callback.on_result};

			if (callbackData.hasOwnProperty("automatic_state_transition")) {
				callbackData.choice_selection.elements.some(function(choiceElem) {
					if (choiceElem.utterance_id.slice(0, -2) === callbackData.automatic_state_transition) {
						// console.log("yes!!");
						submitDialogueChoice(choiceElem.utterance, choiceElem.utterance_id);
						sendChatMessage(choiceElem.utterance);
						return true;
					}
				});
			}

		}
	}
}


$(document).ready(function() {

});
