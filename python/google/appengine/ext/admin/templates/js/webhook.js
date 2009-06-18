// Copyright 2009 Google Inc.  All Rights Reserved.

function Webhook(formId) {
  this.formId = formId;
  this.action = null;
  this.headers = {};
  this.method = null;
  this.payload = null;
};

Webhook.prototype.HEADER_KEY = 'header:';

Webhook.prototype.parse = function() {
  var form = document.getElementById(this.formId);
  if (form == null) {
    return 'could not find form with id "' + this.formId + '"';
  };
  this.action = form.action;
  this.method = form.method;
  for (var i = 0, n = form.elements.length; i < n; i++) {
    var currentElement = form.elements[i];
    if (currentElement.tagName != 'INPUT' ||
        currentElement.type.toUpperCase() != 'HIDDEN') {
      continue;
    }
    var key = currentElement.name;
    var value = currentElement.value;
    var headerIndex = key.indexOf(this.HEADER_KEY);
    if (headerIndex == 0) {
      var header = key.substr(this.HEADER_KEY.length);
      this.headers[header] = value;
    } else if (key == 'payload') {
      this.payload = value;
    }
  }
  
  if (this.action == '') {
    return 'action not found';
  }
  if (this.method == '') {
    return 'method not found';
  }
  return '';
};

Webhook.prototype.send = function(callback) {
  var req = null;
  if (window.XMLHttpRequest) {
    req = new XMLHttpRequest();
  } else if (window.ActiveXObject) {
    req = new ActiveXObject('MSXML2.XMLHTTP.3.0');
  }

  try {
    req.open(this.method, this.action, false);
    for (var key in this.headers) {
      req.setRequestHeader(key, this.headers[key]);
    };
    req.send(this.payload);
  } catch (e) {
    callback(this, req, e);
    return;
  }
  callback(this, req, null);
};

Webhook.prototype.run = function(callback) {
  var error = this.parse();
  if (error != '') {
    callback(this, null, error);
  } else {
    this.send(callback);
  }
};
