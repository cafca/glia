/*
    Glia Javascript Ressources
    ~~~~~

    Define UI behavior

    :copyright: (c) 2015 by Vincent Ahrend.
*/

var socket;

$(document).ready(function(){
    $('#rk-chat-more-button').button('loading');
    console.log("Connecting " + 'http://' + document.domain + ':' + location.port + '/groups')
    socket = io.connect('http://' + document.domain + ':' + location.port + '/groups');
    socket.on('connect', function() {
        $('#rk-chat-meta').addClass('rk-chat-connected');
        socket.emit('joined', {'room_id': window.room_id});
        load_more_chatlines();
    });

    socket.on('status', function (msg) {
        // $('#lines').append($('<p>').append($('<em>').text(msg['msg'])));
        append_timeline("System", msg['msg']);
    });

    socket.on('nicknames', function (data) {
        var nicknames = data['nicknames'];
        var ids = data['ids'];

        $('#rk-chat-nicknames').empty();
        for (var i in nicknames) {
          if (ids[i] == window.admin_id) {
            $('#rk-chat-nicknames').append($('<strong>').text(nicknames[i] + " [a]"));
          } else {
            $('#rk-chat-nicknames').append($('<strong>').text(nicknames[i]));
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
            $(".oneup-"+star_id).toggleClass("btn-default");
            $(".oneup-"+star_id).toggleClass("btn-inverse");
        }

        $(".oneup-count-"+star_id).text(vote_count);
    });

    // DOM manipulation
    function append_timeline (from, msg, star_id, vote_count) {
        if (star_id === undefined) {
            // Server message
            $('#rk-chat-lines').append($('<li class="list-group-item">').append($('<em>').text(msg)));
        } else {
            // Star post
            $('#rk-chat-lines').append(msg);
            $('.oneup').click(function () {request_upvote(this.dataset.id);});

        }
        scroll();
    }

    function get_chat_height() {
        var total_height = 0;
        $('#rk-chat-lines > li').each(function(i) {
            total_height += $(this).height();
        })
        return total_height;
    }

    function scroll(duration) {
        duration = typeof duration !== 'undefined' ? duration : (get_chat_height() / 2);

        $('#rk-chat-lines').animate({
            scrollTop: get_chat_height() * 1.5
        }, duration);
    }

    function request_upvote(star_id) {
        console.log("Voting Star "+star_id);
        socket.emit('vote_request', {'star_id': star_id});
    }

    function load_more_chatlines() {
        $('#rk-chat-more-button').button('loading');
        $.ajax($('#rk-chat-more-button').attr('href'))
            .done(function(data) {
                $('#rk-chat-more').after(data['html']);
                if (data['end_reached'] == true) {
                    $('#rk-chat-more-button').remove();
                } else {
                    $('#rk-chat-more-button').attr('href', data['next_url']);
                }
                $(document).ready(function() {
                    scroll(0);
                    $('#rk-chat-more-button').button('reset');
                    $(".oneup").click(function () {request_upvote(this.dataset.id); return false;});
                });
            });
    }

    $(function () {
        //
        // UPVOTE BUTTON
        //

        $(".oneup").click(function () {request_upvote(this.dataset.id)});

        //
        // CHAT BEHAVIOR
        //

        $('#send-message').submit(function () {
            var $btn = $('.rk-chat-button').button('loading');
            socket.emit('text', {'msg': $('#message').val(), 'room_id': window.room_id}, function() {
                $btn.button('reset');
            });
            clear();
            return false;
        });

        $('#rk-chat-more-button').click(function() {
            var $top_line = $('#rk-chat-lines li:nth-child(2)');
            data = load_more_chatlines();
            $('#rk-chat-lines').scrollTop($top_line.offset().top - 150);
            return false;
        })

        function clear () {
            $('#message').val('').focus();
        }

        //
        // GROUP META
        //

        $("#rk-group-follower").click(function() {
            $.post($("#rk-group-follower").data("href"))
                .done(function (data) {
                    location.reload();
                })
        });

        $("#rk-group-member").click(function() {
            $.post($("#rk-group-member").data("href"))
                .done(function (data) {
                    location.reload();
                })
        });
    });
});
