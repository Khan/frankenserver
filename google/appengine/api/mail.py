#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""Sends email on behalf of application.

Provides functions for application developers to provide email services
for their applications.  Also provides a few utility methods.
"""





from email import MIMEBase
from email import MIMEMultipart
from email import MIMEText
import mimetypes
import types

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import mail_service_pb
from google.appengine.api import users
from google.appengine.api.mail_errors import *
from google.appengine.runtime import apiproxy_errors


ERROR_MAP = {
  mail_service_pb.MailServiceError.BAD_REQUEST:
    BadRequestError,

  mail_service_pb.MailServiceError.UNAUTHORIZED_SENDER:
    InvalidSenderError,

  mail_service_pb.MailServiceError.INVALID_ATTACHMENT_TYPE:
    InvalidAttachmentTypeError,
}


EXTENSION_WHITELIST = set([
  'bmp',
  'css',
  'csv',
  'gif',
  'html', 'htm',
  'jpeg', 'jpg', 'jpe',
  'pdf',
  'png',
  'rss',
  'text', 'txt', 'asc', 'diff', 'pot',
  'tiff', 'tif',
  'wbmp',
])


def invalid_email_reason(email_address, field):
  """Determine reason why email is invalid

  Args:
    email_address: Email to check.

  Returns:
    String indicating invalid email reason if there is one,
    else None.
  """
  if email_address is None:
    return 'None email address for %s.' % field

  if isinstance(email_address, users.User):
    email_address = email_address.email()
  if not isinstance(email_address, types.StringTypes):
    return 'Invalid email address type for %s.' % field
  stripped_address = email_address.strip()
  if not stripped_address:
    return 'Empty email address for %s.' % field
  return None

InvalidEmailReason = invalid_email_reason


def is_email_valid(email_address):
  """Determine if email is invalid.

  Args:
    email_address: Email to check.

  Returns:
    True if email is valid, else False.
  """
  return invalid_email_reason(email_address, '') is None

IsEmailValid = is_email_valid


def check_email_valid(email_address, field):
  """Check that email is valid

  Args:
    email_address: Email to check.

  Raises:
    InvalidEmailError if email_address is invalid.
  """
  reason = invalid_email_reason(email_address, field)
  if reason is not None:
    raise InvalidEmailError(reason)

CheckEmailValid = check_email_valid


def _email_check_and_list(emails, field):
  """Generate a list of emails.

  Args:
    emails: Single email or list of emails.

  Returns:
    Sequence of email addresses.

  Raises:
    InvalidEmailError if any email addresses are invalid.
  """
  if isinstance(emails, types.StringTypes):
    check_email_valid(value)
  else:
    for address in iter(emails):
      check_email_valid(address, field)


def _email_sequence(emails):
  """Forces email to be sequenceable type.

  Iterable values are returned as is.  This function really just wraps the case
  where there is a single email string.

  Args:
    emails: Emails (or email) to coerce to sequence.

  Returns:
    Single tuple with email in it if only one email string provided,
    else returns emails as is.
  """
  if isinstance(emails, types.StringTypes):
    return emails,
  return emails


def _attachment_sequence(attachments):
  """Forces attachments to be sequenceable type.

  Iterable values are returned as is.  This function really just wraps the case
  where there is a single attachment.

  Args:
    attachments: Attachments (or attachment) to coerce to sequence.

  Returns:
    Single tuple with attachment tuple in it if only one attachment provided,
    else returns attachments as is.
  """
  if len(attachments) == 2 and isinstance(attachments[0], types.StringTypes):
    return attachments,
  return attachments


def send_mail(sender,
              to,
              subject,
              body,
              make_sync_call=apiproxy_stub_map.MakeSyncCall,
              **kw):
  """Sends mail on behalf of application.

  Args:
    sender: Sender email address as appears in the 'from' email line.
    to: List of 'to' addresses or a single address.
    subject: Message subject string.
    body: Body of type text/plain.
    make_sync_call: Function used to make sync call to API proxy.
    kw: Keyword arguments compatible with EmailMessage keyword based
      constructor.

  Raises:
    InvalidEmailError when invalid email address provided.
  """
  kw['sender'] = sender
  kw['to'] = to
  kw['subject'] = subject
  kw['body'] = body
  message = EmailMessage(**kw)
  message.send(make_sync_call)

SendMail = send_mail


def send_mail_to_admins(sender,
                        subject,
                        body,
                        make_sync_call=apiproxy_stub_map.MakeSyncCall,
                        **kw):
  """Sends mail to admins on behalf of application.

  Args:
    sender: Sender email address as appears in the 'from' email line.
    subject: Message subject string.
    body: Body of type text/plain.
    make_sync_call: Function used to make sync call to API proxy.
    kw: Keyword arguments compatible with EmailMessage keyword based
      constructor.

  Raises:
    InvalidEmailError when invalid email address provided.
  """
  kw['sender'] = sender
  kw['subject'] = subject
  kw['body'] = body
  message = AdminEmailMessage(**kw)
  message.send(make_sync_call)

SendMailToAdmins = send_mail_to_admins


def mail_message_to_mime_message(protocol_message):
  """Generate a MIMEMultitype message from protocol buffer.

  Generates a complete MIME multi-part email object from a MailMessage
  protocol buffer.  The body fields are sent as individual alternatives
  if they are both present, otherwise, only one body part is sent.

  Multiple entry email fields such as 'To', 'Cc' and 'Bcc' are converted
  to a list of comma separated email addresses.

  Args:
    message: Message PB to convert to MIMEMultitype.

  Returns:
    MIMEMultitype representing the provided MailMessage.
  """
  parts = []
  if protocol_message.has_textbody():
    parts.append(MIMEText.MIMEText(protocol_message.textbody()))
  if protocol_message.has_htmlbody():
    parts.append(MIMEText.MIMEText(protocol_message.htmlbody(),
                                   _subtype='html'))

  if len(parts) == 1:
    payload = parts
  else:
    payload = [MIMEMultipart.MIMEMultipart('alternative', _subparts=parts)]

  result = MIMEMultipart.MIMEMultipart(_subparts=payload)
  for attachment in protocol_message.attachment_list():
    mime_type, encoding = mimetypes.guess_type(attachment.filename())
    assert mime_type is not None
    maintype, subtype = mime_type.split('/')
    mime_attachment = MIMEBase.MIMEBase(maintype, subtype)
    mime_attachment.add_header('Content-Disposition',
                               'attachment',
                               filename=attachment.filename())
    mime_attachment.set_charset(encoding)
    mime_attachment.set_payload(attachment.data())
    result.attach(mime_attachment)

  if protocol_message.to_size():
    result['To'] = ', '.join(protocol_message.to_list())
  if protocol_message.cc_size():
    result['Cc'] = ', '.join(protocol_message.cc_list())
  if protocol_message.bcc_size():
    result['Bcc'] = ', '.join(protocol_message.bcc_list())

  result['From'] = protocol_message.sender()
  result['ReplyTo'] = protocol_message.replyto()
  result['Subject'] = protocol_message.subject()

  return result

MailMessageToMIMEMessage = mail_message_to_mime_message


class _EmailMessageBase(object):
  """Base class for email API service objects.

  Subclasses must define a class variable called _API_CALL with the name
  of its underlying mail sending API call.
  """

  PROPERTIES = set([
    'sender',
    'reply_to',
    'subject',
    'body',
    'html',
    'attachments',
  ])

  def __init__(self, **kw):
    """Initialize Email message.

    Creates new MailMessage protocol buffer and initializes it with any
    keyword arguments.

    Args:
      kw: List of keyword properties as defined by PROPERTIES.
    """
    self.initialize(**kw)

  def initialize(self, **kw):
    """Keyword initialization.

    Used to set all fields of the email message using keyword arguments.

    Args:
      kw: List of keyword properties as defined by PROPERTIES.
    """
    for name, value in kw.iteritems():
      setattr(self, name, value)

  def Initialize(self, **kw):
    self.initialize(**kw)

  def check_initialized(self):
    """Check if EmailMessage is properly initialized.

    Test used to determine if EmailMessage meets basic requirements
    for being used with the mail API.  This means that the following
    fields must be set or have at least one value in the case of
    multi value fields:

      - Subject must be set.
      - A recipient must be specified.
      - Must contain a body.

    This check does not include determining if the sender is actually
    authorized to send email for the application.

    Raises:
      Appropriate exception for initialization failure.

        InvalidAttachmentTypeError: Use of incorrect attachment type.
        MissingRecipientsError:     No recipients specified in to, cc or bcc.
        MissingSenderError:         No sender specified.
        MissingSubjectError:        Subject is not specified.
        MissingBodyError:           No body specified.
    """
    if not hasattr(self, 'sender'):
      raise MissingSenderError()
    if not hasattr(self, 'subject'):
      raise MissingSubjectError()
    if not hasattr(self, 'body') and not hasattr(self, 'html'):
      raise MissingBodyError()
    if hasattr(self, 'attachments'):
      for filename, data in _attachment_sequence(self.attachments):
        split_filename = filename.split('.')
        if len(split_filename) < 2:
          raise InvalidAttachmentTypeError()
        if split_filename[-1] not in EXTENSION_WHITELIST:
          raise InvalidAttachmentTypeError()
        mime_type, encoding = mimetypes.guess_type(filename)
        if mime_type is None:
          raise InvalidAttachmentTypeError()

  def CheckInitialized(self):
    self.check_initialized()

  def is_initialized(self):
    """Determine if EmailMessage is properly initialized.

    Returns:
      True if message is properly initializes, otherwise False.
    """
    try:
      self.check_initialized()
      return True
    except Error:
      return False

  def IsInitialized(self):
    return self.is_initialized()

  def ToProto(self):
    self.check_initialized()
    message = mail_service_pb.MailMessage()
    message.set_sender(self.sender)

    if hasattr(self, 'reply_to'):
      message.set_replyto(self.reply_to)
    message.set_subject(self.subject)
    if hasattr(self, 'body'):
      message.set_textbody(self.body)
    if hasattr(self, 'html'):
      message.set_htmlbody(self.html)

    if hasattr(self, 'attachments'):
      for file_name, data in _attachment_sequence(self.attachments):
        attachment = message.add_attachment()
        attachment.set_filename(file_name)
        attachment.set_data(data)
    return message

  def to_mime_message(self):
    """Generate a MIMEMultitype message from EmailMessage.

    Calls MailMessageToMessage after converting self to protocol
    buffer.  Protocol buffer is better at handing corner cases
    than EmailMessage class.

    Returns:
      MIMEMultitype representing the provided MailMessage.

    Raises:
      Appropriate exception for initialization failure.

      InvalidAttachmentTypeError: Use of incorrect attachment type.
      MissingSenderError:         No sender specified.
      MissingSubjectError:        Subject is not specified.
      MissingBodyError:           No body specified.
  """
    return mail_message_to_mime_message(self.ToProto())

  def ToMIMEMessage(self):
    return self.to_mime_message()

  def send(self, make_sync_call=apiproxy_stub_map.MakeSyncCall):
    """Send email message.

    Send properly initialized email message via email API.

    Args:
      make_sync_call: Method which will make synchronous call to api proxy.

    Raises:
      Errors defined in this file above.
    """
    message = self.ToProto()
    response = api_base_pb.VoidProto()

    try:
      make_sync_call('mail', self._API_CALL, message, response)
    except apiproxy_errors.ApplicationError, e:
      if e.application_error in ERROR_MAP:
        raise ERROR_MAP[e.application_error]()
      raise e

  def Send(self, *args, **kwds):
    self.send(*args, **kwds)

  def _check_attachment(self, attachment):
    file_name, data = attachment
    if not (isinstance(file_name, types.StringTypes) or
            isinstance(data, types.StringTypes)):
      raise TypeError()

  def _check_attachments(self, attachments):
    """Checks values going to attachment field.

    Mainly used to check type safety of the values.  Each value of the list
    must be a pair of the form (file_name, data), and both values a string
    type.

    Args:
      attachments: Collection of attachment tuples.

    Raises:
      TypeError if values are not string type.
    """
    if len(attachments) == 2 and isinstance(attachments[0], types.StringTypes):
      self._check_attachment(attachments)
    else:
      for attachment in attachments:
        self._check_attachment(attachment)

  def __setattr__(self, attr, value):
    """Property setting access control.

    Controls write access to email fields.

    Args:
      attr: Attribute to access.
      value: New value for field.
    """
    if attr in ['sender', 'reply_to']:
      check_email_valid(value, attr)

    if not value:
      raise ValueError('May not set empty value for \'%s\'' % attr)

    if attr not in self.PROPERTIES:
      raise AttributeError('\'EmailMessage\' has no attribute \'%s\'' % attr)

    if attr == 'attachments':
      self._check_attachments(value)

    super(_EmailMessageBase, self).__setattr__(attr, value)


class EmailMessage(_EmailMessageBase):
  """Main interface to email API service.

  This class is used to programmatically build an email message to send via
  the Mail API.  The usage is to construct an instance, populate its fields
  and call Send().

  Example Usage:
    An EmailMessage can be built completely by the constructor.

      EmailMessage(sender='sender@nowhere.com',
                   to='recipient@nowhere.com',
                   subject='a subject',
                   body='This is an email to you').Send()

    It might be desirable for an application to build an email in different
    places throughout the code.  For this, EmailMessage is mutable.

      message = EmailMessage()
      message.sender = 'sender@nowhere.com'
      message.to = ['recipient1@nowhere.com', 'recipient2@nowhere.com']
      message.subject = 'a subject'
      message.body = 'This is an email to you')
      message.check_initialized()
      message.send()
  """

  _API_CALL = 'Send'
  PROPERTIES = _EmailMessageBase.PROPERTIES
  PROPERTIES.update(('to', 'cc', 'bcc'))

  def check_initialized(self):
    """Provide additional checks to ensure recipients have been specified.

    Raises:
      MissingRecipientError when no recipients specified in to, cc or bcc.
    """
    if (not hasattr(self, 'to') and
        not hasattr(self, 'cc') and
        not hasattr(self, 'bcc')):
      raise MissingRecipientsError()
    super(EmailMessage, self).check_initialized()

  def CheckInitialized(self):
    self.check_initialized()

  def ToProto(self):
    """Does addition conversion of recipient fields to protocol buffer.
    """
    message = super(EmailMessage, self).ToProto()

    for attribute, adder in (('to', message.add_to),
                             ('cc', message.add_cc),
                             ('bcc', message.add_bcc)):
      if hasattr(self, attribute):
        for address in _email_sequence(getattr(self, attribute)):
          adder(address)
    return message

  def __setattr__(self, attr, value):
    """Provides additional checks on recipient fields."""
    if attr in ['to', 'cc', 'bcc']:
      if isinstance(value, types.StringTypes):
        check_email_valid(value, attr)
      else:
        _email_check_and_list(value, attr)

    super(EmailMessage, self).__setattr__(attr, value)


class AdminEmailMessage(_EmailMessageBase):
  """Interface to sending email messages to all admins via the amil API.

  This class is used to programmatically build an admin email message to send
  via the Mail API.  The usage is to construct an instance, populate its fields
  and call Send().

  Unlike the normal email message, addresses in the recipient fields are
  ignored and not used for sending.

  Example Usage:
    An AdminEmailMessage can be built completely by the constructor.

      AdminEmailMessage(sender='sender@nowhere.com',
                        subject='a subject',
                        body='This is an email to you').Send()

    It might be desirable for an application to build an admin email in
    different places throughout the code.  For this, AdminEmailMessage is
    mutable.

      message = AdminEmailMessage()
      message.sender = 'sender@nowhere.com'
      message.subject = 'a subject'
      message.body = 'This is an email to you')
      message.check_initialized()
      message.send()
  """

  _API_CALL = 'SendToAdmins'
