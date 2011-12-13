/**
 * Creates the tab interface for samples section on page load
 *
 * @author shakila@google.com (Shakila Sivakumar)
 */
$(document).ready(function() {
  // Creates tab interface with none selected
  // Tab content are displayed by 'click' event
  var tabs = $("div.tabpane > ul").tabs({event: 'click'});
  
  // Peform following when any tab is selected
  $(tabs).bind("select.ui-tabs", function(event, ui) {
    var panelId = $(ui.panel).attr("id");
    var defaultId = panelId.substring(0, panelId.indexOf('_')) + '_default';
    var panelContainer = $(ui.panel).parent();
    // Display of default message is toggled based on tab content display    
    $(panelContainer).children().each(function() {
      var currentId = $(this).attr("id");      
      if (currentId == defaultId) {
        if ($(ui.panel).css("display") == 'none') {
          $(this).hide();
        } else {
          $(this).show();
        } 
      }
    });   
  });
  
});

