/*
    Glia Javascript Ressources
    ~~~~~

    Define UI behavior

    :copyright: (c) 2015 by Vincent Ahrend.
*/

var socket;
var psocket;

$(document).ready(function(){
    PNotify.desktop.permission();
    $('#rk-chat-more-button').button('loading');

    $('body').tooltip({
        selector: '.rk-tooltip',
        delay: { show: 450, hide: 300 }
    });

    lightbox.option({
      'resizeDuration': 200
    })

    // Connect personal websocket
    console.log("Connecting " + 'http://' + document.domain + ':' + location.port + '/personas')
    psocket = io.connect('http://' + document.domain + ':' + location.port + '/personas');
    psocket.on('connect', function() {
        console.log("Receiving personal messages");
    })

    psocket.on('message', function(data) {
        notification(data.title, data.msg);
    })

    // Connect movement websocket
    console.log("Connecting " + 'http://' + document.domain + ':' + location.port + '/movements')
    socket = io.connect('http://' + document.domain + ':' + location.port + '/movements');
    socket.on('connect', function() {
        console.log("Receiving movement messages");
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
            $('#rk-chat-nicknames').append($('<strong>').text(nicknames[i] + " (Administrator)"));
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
        append_timeline(data.username, data.msg, data);
    });

    socket.on('comment', function(data) {
        insert_reply(data.parent_id, data.msg);
    });

    socket.on('vote', function(data) {
        window.votedata = data;

        thought_id = data.votes[0].thought_id;
        author_id = data.votes[0].author_id;
        vote_count = data.votes[0].vote_count;
        voting_done = data.votes[0].voting_done;
        console.log("Thought "+thought_id+" now has "+vote_count+" votes.");

        if (author_id == window.user_id) {
            $(".upvote-"+thought_id).toggleClass("btn-default");
            $(".upvote-"+thought_id).toggleClass("btn-primary");
        }

        if (voting_done != undefined) {
            $("#rk-promote-"+thought_id+" > span").animate({width: voting_done*100+"%"});
        }

        $(".upvote-count-"+thought_id).text(vote_count);
    });

    // DOM manipulation
    function append_timeline (from, msg, data) {
        if (typeof data == 'undefined') {
            data = {};
        }
        var thought_id = data.thought_id;
        var vote_count = data.vote_count;

        if (thought_id === undefined) {
            // Server message
            $('#rk-chat-lines').append($('<li class="list-group-item rk-system">').append($('<em>').text(msg)));
        } else {
            // Thought post
            $('#rk-chat-lines').append(msg);
            $('#rk-chat-lines .upvote').click(function () {request_upvote(this.dataset.id); return false;});

        }
        scroll();
    }

    function logged_in() {
        if (window.user_id == "None") {
            location.href = window.login_url;
            return false;
        }
        return true;
    }

    function insert_reply(parent_id, rendered_content) {
        var reply_box = $(".rk-thought-"+parent_id).siblings(".rk-replies").first();
        if (reply_box.length == 0) {
            $(".rk-thought-"+parent_id).after("<div><p>Additional replies hidden.</p></div>");
        } else {
            reply_box
                .prepend(rendered_content)
                .find(".upvote").click(function () {
                    request_upvote(this.dataset.id);
                    return false;
                });
        }
    }

    function show_reply_box(thought_id) {
        var $form = $(".rk-thought-"+thought_id+" .rk-create");
        $form.css("display", "block");
        $form.find("textarea").focus();
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

    function request_upvote(thought_id) {
        logged_in();
        console.log("Voting Thought "+thought_id);
        socket.emit('vote_request', {'thought_id': thought_id});
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

                if (data['end_reached'] == true) {
                    $('#rk-chat-more-button').remove();
                } else {
                    $('#rk-chat-more-button').attr('href', data['next_url']);
                }
                $('#rk-chat-more').ready(function() {
                    scroll(0);
                    $('#rk-chat-more-button').button('reset');
                    $(".upvote").unbind("click");
                    $(".upvote").click(function () {request_upvote(this.dataset.id); return false;});
                });
            });
    }



    $(function () {
        //
        // MISC UI
        //

        $(".upvote").click(function () {
            if (logged_in()) {
                request_upvote(this.dataset.id);
                return false;
            }
        });

        $(".rk-singleclick").click(function() {$(this).button("loading");});

        //
        // PROMOTE BUTTON
        //

        $('.rk-promote').click(function() {
            $(this).prop("disabled", true);
            $(this).button("loading");
            var data = {
                "thought_id": $(this).data("thought-id"),
            }
            $.post($(this).data("promote-url"), data)
              .done(function(data) {
                notification("Thought Promotion", data["message"]);
                $(".rk-promote").button("reset");
              })
              .error(function(data) {
                notification("Error promoting Thought", data["message"]);
                $(".rk-promote").button("reset");
              });
          });

        //
        // CREATE THOUGHT
        //

        $('.rk-create').click(function(event) {
          $(this).data('clicked',$(event.target))
        });

        $('.rk-create').submit(function(event) {
            logged_in();

            var $btn = $(this).find('.rk-create-submit');
            var $text = $(this).find('.rk-create-text').val();
            var $parent = $(this).find('.rk-create-parent').val();
            var $counter = $(this).find($(".rk-create-counter"));

            var $async = ($(this).data('clicked')[0] != $(this).find($(".rk-create-longform"))[0]);
            if ($counter.hasClass("safe") && $async) {
                $btn.button('loading');
                data = {
                    'msg': $text,
                    'room_id': window.room_id,
                    'map_id': window.map_id
                }

                if ($parent != undefined) {
                    data["parent_id"] = $parent;
                }

                socket.emit('text', data, function(data) {
                        $btn.button('reset');
                });
                clear();
                event.preventDefault();
            }
        });

        $('.rk-create-text').each(function(index, obj) {
            $(obj).simplyCountable({
                counter:            ":parent:parent .rk-create-counter",
                countType:          'characters',
                maxCount:           140,
                strictMax:          false,
                countDirection:     'down',
                safeClass:          'safe',
                overClass:          'over',
                thousandSeparator:  ',',
                onOverCount:        function(count, countable, counter){
                    form = countable.closest(".rk-create");
                    form.find(".rk-create-submit")
                        .prop("disabled", true)
                        .toggleClass("btn-primary")
                        .toggleClass("btn-default");
                    form.find(".rk-create-longform")
                        .toggleClass("btn-primary")
                        .toggleClass("btn-default");
                    form.find(".rk-create-extend").toggle("highlight");
                },
                onSafeCount:        function(count, countable, counter){
                    form = countable.closest(".rk-create");
                    form.find(".rk-create-submit")
                        .prop("disabled", false)
                        .toggleClass("btn-primary")
                        .toggleClass("btn-default");
                    form.find(".rk-create-longform")
                        .toggleClass("btn-primary")
                        .toggleClass("btn-default");
                    form.find(".rk-create-extend").toggle("highlight");
                },
                onMaxCount:         function(count, countable, counter){}
            });
        })

        //
        // CHAT BEHAVIOR
        //

        $(".rk-create-display-toggle").click(function() {
            logged_in();
            $(this).hide();
            show_reply_box($(this).data("id"));
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

        $("#rk-follower").click(function() {
            logged_in();
            $(this).button('loading');
            $.post($(this).data("href"))
                .done(function (data) {
                    location.reload();
                })
                .error(function(data) {
                    notification("Error", data.responseJSON["message"]);
                    $("#rk-follower").button('reset');
                })
        });

        $("#rk-movement-member").click(function() {
            logged_in();
            $(this).button('loading');
            $.post($("#rk-movement-member").data("href"))
                .done(function (data) {
                    location.reload();
                })
                .error(function(data) {
                    console.log(data);
                    notification("Error", data.responseJSON["message"]);
                    $("#rk-movement-member").button('reset');
                })
        });

        //
        // REPOST
        //

        $('#rk-repost').on('show.bs.modal', function (event) {
            var button = $(event.relatedTarget);
            var id = button.data('thought-id');
            var text = button.data('thought-text');

            var modal = $(this)
            modal.find('#rk-repost-username').text(window.user_name);
            modal.find('#rk-repost-text').text(text);
            modal.find('.rk-create-parent').val(id);
        });

        $('.rk-repost-form').submit(function (event) {
            event.preventDefault();
            var $btn = $(this).find(":button");
            var $map = $btn.data("mindset-id");
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
                    notification("Repost", data.responseJSON["message"]);
                }
            });
            $btn.button('success');
            $btn.prop('disabled', true);
        });

        // INTRO AND WELCOME

        $('#rk-welcome-show-login').click(function() {
            $('#rk-welcome-actions').slideUp({
                duration: 'fast',
                complete: function() {
                    $('#rk-welcome-login').slideDown('fast');
                }}
            );

        });
    });
});
