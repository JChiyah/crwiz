let socket;
let users = {};

let self_user = undefined;
let self_room = undefined;
let self_room_read_only = false;

var finishTask;

function apply_user_permissions(permissions) {
    // self_user['permissions'] = permissions;
    let canSendMessage = permissions.message.text || permissions.message.image || permissions.message.command;
    $("#text").prop("readonly", !canSendMessage);
    if (canSendMessage && self_room != "waiting_room")
        enableUserChat();
    else
        disableUserChat();
}

function apply_room_properties(room) {
    self_room_read_only = room.read_only;
    $("#type-area").hide();

    if (self_room_read_only) {
        $("#text").prop("readonly", true).prop("placeholder", "This room is read-only");
        $("#type-area fieldset").children().remove();
        closeRoom();
    } else {
        $("#text").prop("readonly", false).prop("placeholder", "Enter your message here!");
    }

    $("#user-list").fadeTo(null, room.show_users);
    $("#latency").fadeTo(null, room.show_latency);
}

function apply_layout(layout) {
    if (!layout)
    return;
    if (layout.html !== "") {
        $("#sidebar").html(layout.html);
    } else {
        $("#sidebar").empty();
    }
    if (layout.css !== "") {
        $("#custom-styles").html(layout.css);
    } else {
        $("#custom-styles").empty();
    }
    if (layout.script !== "") {
        window.eval(layout.script);
    }
    if (layout.title !== "") {
        document.title = layout.title;
    } else {
        document.title = 'Slurk';
    }

    $("#title").text(document.title);
    $("#subtitle").text(layout.subtitle);

    initialisation();
    // setTimeout(() => initialisation(), 250);
}

function verify_query(success, message) {
    if (!success) {
        if (message === "invalid session id") {
            // Reload page if user is not logged in
            window.location.reload();
        } else {
            console.error(message)
        }
        return false;
    }
    return true;
}

function updateUsers() {
    let current_users = "";
    for (let user_id in users) {
        current_users += users[user_id] + ', ';
    }
    $('#current-users').text(current_users + "You");
}

function headers(xhr) {
    xhr.setRequestHeader ("Authorization", "Token " + TOKEN);
}

$(document).ready(() => {
    let uri = location.protocol + '//' + document.domain + ':' + location.port + "/api/v2";
    socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

    socket.on("pong", (data) => {
        $("#ping").text(data);
    });

    async function joined_room(data) {
        // console.log("joining room: ");
        // console.log(data);
        self_room = data['room'];

        let room_request = $.get({ url: uri + "/room/" + data['room'], beforeSend: headers });
        let user_request = $.get({ url: uri + "/user/" + data['user'], beforeSend: headers });
        let layout = $.get({ url: uri + "/room/" + data['room'] + "/layout", beforeSend: headers });
        let history = $.get({ url: uri + "/user/" + data['user'] + "/logs", beforeSend: headers });

        let room = await room_request;
        apply_room_properties(room);

        let user = await user_request;
        self_user = {
            id: user.id,
            name: user.name,
            role_id: user.role_id,
            token: user.token,
            user_turns: true,
            current_turn: false,
            input_enabled: true
        };
        let token = $.get({ url: uri + "/token/" + user.token, beforeSend: headers });

        users = {};
        for (let user_id in room.current_users) {
            if (Number(user_id) !== self_user.id)
            users[user_id] = room.current_users[user_id];
        }

        updateUsers();
        apply_layout(await layout);
        // $("#chat-area").empty();

        history = await history;
        if (typeof print_history !== "undefined" && history !== undefined) {
            if (history[room.name] === undefined) {
                // console.log("gonna have error!!");
                history = await $.get({ url: uri + "/user/" + data['user'] + "/logs", beforeSend: headers });
            }
            print_history(history[room.name]);
        }

        apply_user_permissions((await token).permissions);
    }

    async function left_room(data) {}

    socket.on('joined_room', joined_room);
    socket.on('left_room', left_room);

    socket.on('status', function (data) {
        if (typeof self_user === "undefined")
            return;
        // console.log("status coming... ");
        // console.log(data);
        // console.log("----");
        switch (data.type) {
        case "join":
            users[data.user.id] = data.user.name;
            updateUsers();
            break;
        case "leave":
            delete users[data.user.id];
            updateUsers();
            break;
        }
    });

    socket.on('update_room_properties', function (data) {
        if (data !== undefined && data['read_only'] !== undefined) {
            self_room_read_only = data['read_only'];
            if (self_room_read_only) {
                closeRoom();
                // setTimeout(() => closeRoom(), 500);
                // disableUserChat();
            } else {
                // setTimeout(() => enableUserChat(), 500);
            }
        }
    });

    async function updateUserPermissions(data) {
        if (self_user !== undefined) {
            let token = $.get({url: uri + "/token/" + self_user.token, beforeSend: headers});
            apply_user_permissions((await token).permissions);
        }
    }

    socket.on("update_user_permissions", updateUserPermissions);

    socket.on("status_update", function (data) {
        // console.log("status_update");
        // console.log(data);
        setTaskTimer(data['remaining_seconds'], data['start_time']);
		if (self_user === undefined) {
			return;
		}
        let before_turns = self_user.user_turns;
        let before_current_turn = self_user.current_turn;
        self_user.user_turns = data['user_turns'];
        self_user.current_turn = data['turn_user_id'] === self_user.id;

        if (before_turns !== self_user.user_turns || before_current_turn !== self_user.current_turn)
            controlUserTurn();

		if (data.hasOwnProperty("can_finish_task")) {
			if (self_user.can_finish_task === undefined
				|| self_user.can_finish_task != data.can_finish_task) {
				self_user.can_finish_task = data.can_finish_task
				if (self_user.can_finish_task)
					$("#btn-finish-task").removeClass("btn-outline-light").addClass("btn-success");
				else
					$("#btn-finish-task").addClass("btn-outline-light").removeClass("btn-success");
			}
		}

		// iterate through all the values given by the status_update and
		// update values in the interface as needed
		Object.keys(data).forEach(function (key) {
			let elements = $(`.${key}-value`);
			// make sure that the elements exist and that data[key] is not an object
			if (elements !== undefined && elements.length > 0 && data[key] !== Object(data[key])) {
				elements.text(data[key]);
			}
		});
		// console.log(data);

		if (data.hasOwnProperty("task_progress")) {
			updateProgressBar(data.task_progress);
		}

		if (data.hasOwnProperty("users") && Object.keys(users).length < 2) {
			users = data.users;
			delete users[self_user.id];
			updateUsers();
		}

		if (!isWizard()) {
			if (data.hasOwnProperty("operator_wait")) {
				$("#text").prop("readonly", true).prop("placeholder", data.operator_wait.reason);
			} else {
				$("#text").prop("readonly", false);
			}
		}
    });

	socket.on("dialogue_choices", function (data) {
		if (isWizard()) {
			handleDialogueChoicesData(data);
		}
	});

	socket.on("wait_for_wizard", function (data) {
		if (!isWizard()) {
			// TODO
		}
	});

	socket.on("perform_action", function (data) {
		performActionModal(data);
	});

	/**
	 * finishTask
	 *
	 * Called when the user confirms the modal to finish the task/game.
	 *
	 * @return {[type]} null
	 */
	finishTask = function (callbackResult) {
		if (callbackResult) {
			console.log("sending finish task");
			socket.emit("user_finish_task", {user_id: self_user.id, room_name: self_room});
		}
	};

    socket.emit("ready");
});
