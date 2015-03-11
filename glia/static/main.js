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
        $('#chat').addClass('connected');
        socket.emit('joined', {'room_id': window.room_id});
        scroll();
    });

    socket.on('status', function (msg) {
        $('#lines').append($('<p>').append($('<em>').text(msg['msg'])));
        scroll();
    });

    socket.on('nicknames', function (nicknames) {
        $('#nicknames').empty().append($('<span>Online: </span>'));
        for (var i in nicknames) {
          $('#nicknames').append($('<b>').text(nicknames[i]));
        }
    });

    socket.on('msg_to_room', append_timeline);

    socket.on('reconnect', function () {
        $('#lines').remove();
        append_timeline('System', 'Reconnected to the server');
    });

    socket.on('reconnecting', function () {
        append_timeline('System', 'Attempting to re-connect to the server');
    });

    socket.on('error', function (e) {
        append_timeline('System', e ? e : 'A unknown error occurred');
    });

    socket.on('message', function(data) {
        append_timeline(data.username, data.msg);
    });

    function append_timeline (from, msg) {
        $('#lines').append($('<p>').append($('<span>').text(from), msg));
        scroll();
    }

    function scroll() {
        $('#lines').get(0).scrollTop = 10000000;
    }

    // DOM manipulation
    $(function () {
        $('#send-message').submit(function () {
            socket.emit('text', {'msg': $('#message').val(), 'room_id': window.room_id});
            clear();
            return false;
        });

        function clear () {
            $('#message').val('').focus();
        }
    });
});
