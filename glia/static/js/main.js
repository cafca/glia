/*
    Glia Javascript Ressources
    ~~~~~

    Define UI behavior

    :copyright: (c) 2015 by Vincent Ahrend.
*/

var socket;

$(document).ready(function(){
    PNotify.desktop.permission();
    $('#rk-chat-more-button').button('loading');
    console.log("Connecting " + 'http://' + document.domain + ':' + location.port + '/movements')
    socket = io.connect('http://' + document.domain + ':' + location.port + '/movements');
    socket.on('connect', function() {
        $('#rk-chat-meta').addClass('rk-chat-connected');
        socket.emit('joined', {'room_id': window.room_id});
        load_more_chatlines(update_last=true);
        $('#rk-chat-submit').prop('disabled', false);
    });

    socket.on('status', function (msg) {
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
        new PNotify({
            title: 'RKTIK Error',
            text: e ? e : 'A unknown error occurred',
            desktop: {
                desktop: true
            }
        });
    });

    socket.on('message', function(data) {
        append_timeline(data.username, data.msg, data.star_id, data.vote_count);
        $("#rk-chat-parent").val(data.star_id);
    });

    socket.on('comment', function(data) {
        insert_reply(data.parent_id, data.msg);
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
            $('#rk-chat-lines .oneup').click(function () {request_upvote(this.dataset.id); return false;});

        }
        scroll();
    }

    function insert_reply(parent_id, rendered_content) {
        $(".rk-star-"+parent_id+" > .rk-replies").prepend(rendered_content);
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

    function notification(title, message) {
        new PNotify({
            title: 'RKTIK ' + title,
            text: message,
            desktop: {
                desktop: true
            }
        });
    }

    function load_more_chatlines(update_last) {
        $('#rk-chat-more-button').button('loading');
        $.ajax($('#rk-chat-more-button').attr('href'))
            .done(function(data) {
                $('#rk-chat-more').after(data['html']);

                if (update_last == true) {
                    $("#rk-chat-parent").val(data["last_id"]);
                }

                if (data['end_reached'] == true) {
                    $('#rk-chat-more-button').remove();
                } else {
                    $('#rk-chat-more-button').attr('href', data['next_url']);
                }
                $('#rk-chat-more').ready(function() {
                    scroll(0);
                    $('#rk-chat-more-button').button('reset');
                    $(".oneup").unbind("click");
                    $(".oneup").click(function () {request_upvote(this.dataset.id); return false;});
                });
            });
    }

    $(function () {
        //
        // UPVOTE BUTTON
        //

        $(".oneup").click(function () {request_upvote(this.dataset.id); return false;});

        //
        // CHAT BEHAVIOR
        //

        $('.rk-create').submit(function () {
            var $btn = $(this).find('.rk-create-submit');
            var $text = $(this).find('.rk-create-text').val();
            var $parent = $(this).find('.rk-create-parent').val();

            $btn.button('loading');
            socket.emit('text', {
                    'msg': $text,
                    'room_id': window.room_id,
                    'map_id': window.map_id,
                    'parent_id': $parent
                }, function(data) {
                    $btn.button('reset');
            });
            clear();
            return false;
        });

        $(".rk-create-display-toggle").click(function() {
            var $form = $(".rk-star-"+$(this).data("id")+" .rk-create");
            $form.css("display", "block");
            $form.find("textarea").focus();
            return false;
        });

        $('#rk-chat-more-button').click(function() {
            var $top_line = $('#rk-chat-lines li:nth-child(2)');
            data = load_more_chatlines();
            $('#rk-chat-lines').scrollTop($top_line.offset().top - 150);
            return false;
        })

        function clear () {
            $('.rk-create-text').val('').focus();
        }

        //
        // GROUP META
        //

        $("#rk-movement-follower").click(function() {
            $(this).button('loading');
            $.post($("#rk-movement-follower").data("href"))
                .done(function (data) {
                    location.reload();
                })
        });

        $("#rk-movement-member").click(function() {
            $(this).button('loading');
            $.post($("#rk-movement-member").data("href"))
                .done(function (data) {
                    location.reload();
                })
        });

        //
        // REPOST
        //

        $('#rk-repost').on('show.bs.modal', function (event) {
            var button = $(event.relatedTarget);
            var id = button.data('star-id');
            var text = button.data('star-text');

            var modal = $(this)
            modal.find('#rk-repost-username').text(window.user_name);
            modal.find('#rk-repost-text').text(text);
            modal.find('.rk-create-parent').val(id);
        });

        $('.rk-repost-form').submit(function (event) {
            event.preventDefault();
            var $btn = $(this).find(":button");
            var $map = $btn.data("starmap-id");
            var $text = $('#rk-repost').find('.rk-create-text').val();
            var $parent = $('#rk-repost').find('.rk-create-parent').val();

            $btn.button('loading');
            socket.emit('repost', {
                'parent_id': $parent,
                'text': $text,
                'room_id': window.room_id,
                'map_id': $map,
            }, function(data) {
                if (data.status == "success") {
                    notification("Repost", data.message);
                }
            });
            $btn.button('success');
            $btn.prop('disabled', true);
        });
    });
});
