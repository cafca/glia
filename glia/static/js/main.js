/*
    Glia Javascript Ressources
    ~~~~~

    Define UI behavior

    :copyright: (c) 2015 by Vincent Ahrend.
*/

var socket;

$(document).ready(function(){
    console.log("Connecting " + 'http://' + document.domain + ':' + location.port + '/groups')
    socket = io.connect('http://' + document.domain + ':' + location.port + '/groups');
    socket.on('connect', function() {
        $('#lines').addClass('connected');
        socket.emit('joined', {'room_id': window.room_id});
        scroll();
    });

    socket.on('status', function (msg) {
        // $('#lines').append($('<p>').append($('<em>').text(msg['msg'])));
        append_timeline("System", msg['msg']);
    });

    socket.on('nicknames', function (data) {
        var nicknames = data['nicknames'];
        var ids = data['ids'];

        $('#nicknames').empty().append($('<span>Online: </span>'));
        for (var i in nicknames) {
          if (ids[i] == window.admin_id) {
            $('#nicknames').append($('<b>').text(nicknames[i] + " [a]"));
          } else {
            $('#nicknames').append($('<b>').text(nicknames[i]));
          }
        }
    });

    socket.on('msg_to_room', append_timeline);

    socket.on('reconnect', function () {
        // $('#lines').remove();
        append_timeline('System', 'Reconnected to the server');
    });

    socket.on('reconnecting', function () {
        append_timeline('System', 'Attempting to re-connect to the server');
    });

    socket.on('error', function (e) {
        append_timeline('System', e ? e : 'A unknown error occurred');
    });

    socket.on('message', function(data) {
        append_timeline(data.username, data.msg, data.star_id, data.vote_count);
    });

    socket.on('vote', function(data) {
        window.votedata = data;

        star_id = data.votes[0].star_id;
        author_id = data.votes[0].author_id;
        vote_count = data.votes[0].vote_count;
        console.log("Star "+star_id+" now has "+vote_count+" votes.");

        if (author_id == window.user_id) {
            $(".oneup-"+star_id).toggleClass("btn-primary");
            $(".oneup-"+star_id).toggleClass("btn-inverse");
        }

        $(".oneup-count-"+star_id).text(vote_count);
    });

    // DOM manipulation
    function append_timeline (from, msg, star_id, vote_count) {
        if (star_id === undefined) {
            $('#lines').append($('<p>').append($('<em>').text(msg)));
        } else {
            $('#lines').append(msg);
            $('.oneup').click(function () {request_upvote(this.dataset.id);});

        }
        scroll();
    }

    function scroll() {
        $('#lines').get(0).scrollTop = 10000000;
    }

    function request_upvote(star_id) {
        console.log("Voting Star "+star_id);
        socket.emit('vote_request', {'star_id': star_id, 'group_id': group_id});
    }

    $(function () {
        $('#send-message').submit(function () {
            socket.emit('text', {'msg': $('#message').val(), 'room_id': window.room_id});
            clear();
            return false;
        });

        function clear () {
            $('#message').val('').focus();
        }

        $(".oneup").click(function () {request_upvote(this.dataset.id)});
    });
});
