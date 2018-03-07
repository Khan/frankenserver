/**
 * @fileoverview Supporting Javascript for the xmpp page.
 */
$(document).ready(function() {
  $("#message-type-chat, #message-type-presence, #message-type-subscribe").change(function() {
    if ($("#message-type-chat").prop("checked")) {
      $("#chat-fields").show();
      $("#presence-fields").hide();
      $("#subscribe-fields").hide();
    } else if ($("#message-type-presence").prop("checked")) {
      $("#chat-fields").hide();
      $("#presence-fields").show();
      $("#subscribe-fields").hide();
    } else if ($("#message-type-subscribe").prop("checked")) {
      $("#chat-fields").hide();
      $("#presence-fields").hide();
      $("#subscribe-fields").show();
    }
  });

  $('#xmpp-form').submit(function() {
    var data = {'from': $('#from').val(), 'to': $('#to').val(),
                'xsrf_token': '{{ xsrf_token }}' };

    if ($("#message-type-chat").prop("checked")) {
      data['message_type'] = 'chat';
      data['chat'] = $('#chat').val();
    } else if ($("#message-type-presence").prop("checked")) {
      data['message_type'] = 'presence';
      if ($("#presence-online").prop("checked")) {
        data['presence'] =  "available";
      } else {
        data['presence'] =  "unavailable";
      }
    } else if ($("#message-type-subscribe").prop("checked")) {
      data['message_type'] = 'subscribe';
      if ($("#subscribe-subscribe").prop("checked")) {
        data['subscription_type'] =  "subscribe";
      } else if ($("#subscribe-subscribed").prop("checked")) {
        data['subscription_type'] =  "subscribed";
      } else if ($("#subscribe-unsubscribe").prop("checked")) {
        data['subscription_type'] =  "unsubscribe";
      } else {
        data['subscription_type'] =  "unsubscribed";
      }
    }

    var request = $.ajax({
      url: 'xmpp',
      type: 'POST',
      data: data
    })
    .done(function() {
      $('#xmpp-feedback').removeClass().addClass('messagebox').text(
          'Request succeeded!');
    })
    .fail(function(xhr, textStatus) {
      $('#xmpp-feedback').removeClass().addClass('errorbox').text(
          'Request failured with status: ' + request.status);
    });
    return false;
  });
});
