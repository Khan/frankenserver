#!/usr/bin/env python
#
# Copyright 2009 Google Inc.
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
import logging
import os
import wsgiref.handlers

from google.appengine.api import mail
from google.appengine.api import memcache
from google.appengine.api import users
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template


def require_admin(handler_method):
  """Decorator that requires the requesting user to be an admin."""
  def decorate(myself, *args, **kwargs):
    if ('HTTP_X_APPENGINE_TASKNAME' in os.environ
        or users.is_current_user_admin()):
      handler_method(myself, *args, **kwargs)
    elif users.get_current_user() is None:
      myself.redirect(users.create_login_url(myself.request.url))
    else:
      myself.response.set_status(401)
  return decorate

################################################################################
# Send emails

class MailHandler(webapp.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if not user:
      self.redirect(users.create_login_url(self.request.path))
      return
    self.response.out.write(
        template.render('mail.html', {
            'email': user.email()
        }))

  def post(self):
    taskqueue.add(
        url='/worker/email',
        params={'to': users.get_current_user().email()})
    self.redirect('/mail')


class MailWorker(webapp.RequestHandler):
  @require_admin
  def post(self):
    mail.send_mail(
      'user@example.com',
      self.request.get('to'),
      'A special message to you',
      'This is a test of the task queue')

################################################################################
# Schema migration

class FirstUserKind(db.Model):
  name = db.StringProperty()


class SecondUserKind(db.Model):
  first = db.StringProperty()
  last = db.StringProperty()


class NamesHandler(webapp.RequestHandler):
  def get(self):
    self.response.out.write(
        template.render('names.html', {
            'first_users': list(FirstUserKind.all()),
            'second_users': list(SecondUserKind.all()),
        }))

  def post(self):
    name = self.request.get('name')
    kind = self.request.get('kind')
    if kind == 'first':
      FirstUserKind(name=name).put()
    elif kind == 'second':
      first, last = (name.split(' ') + [''])[:2]
      SecondUserKind(
          first=first, last=last).put()
    self.redirect('/names')


def second_from_first(first_user):
  first, last = (first_user.name.split(' ') + [''])[:2]
  return SecondUserKind(
      first=first, last=last)


def first_from_second(second_user):
  return FirstUserKind(
      name='%s %s' % (
      second_user.first, second_user.last))


class MigrationStartHandler(webapp.RequestHandler):
  def post(self):
    taskqueue.add(
        url='/worker/migration',
        params=dict(
            kind=self.request.get('kind')))
    self.redirect('/names')


class MigrationWorker(webapp.RequestHandler):
  @require_admin
  def post(self):
    start = self.request.get('start')
    kind = self.request.get('kind')

    if kind == 'second':
      to_kind = SecondUserKind
      from_kind = FirstUserKind
      migrate = second_from_first
    else:
      to_kind = FirstUserKind
      from_kind = SecondUserKind
      migrate = first_from_second

    query = from_kind.all()
    if start:
      query.filter('__key__ >', db.Key(start))
    old = query.fetch(3)
    if not old:
      logging.info('All done!')
      return

    last_key = old[-1].key()
    new = [migrate(x) for x in old]
    db.put(new)
    db.delete(old)

    taskqueue.add(
        url='/worker/migration',
        params=dict(
            start=last_key,
            kind=kind))

################################################################################
# Write-behind counters.

class Counter(db.Model):
  count = db.IntegerProperty(indexed=False)


class CounterHandler(webapp.RequestHandler):
  def get(self):
    self.response.out.write(
        template.render('counters.html', {
          'counters': list(Counter.all())
        }))

  def post(self):
    key = self.request.get('key')
    if memcache.incr(key) is None:
      memcache.add(key, 1)
    if memcache.add(key + '_dirty', 1):
      taskqueue.add(
          url='/worker/write_behind',
          params={'key': key})
    self.redirect('/counters')


class WriteBehindWorker(webapp.RequestHandler):
  @require_admin
  def post(self):
    key = self.request.get('key')
    memcache.delete(key + '_dirty')
    value = memcache.get(key)
    if value is None:
      logging.error('Failure for %s', key)
      return
    Counter(key_name=key, count=value).put()

################################################################################

def main():
  application = webapp.WSGIApplication([
      (r'/mail', MailHandler),
      (r'/worker/email', MailWorker),
      (r'/names', NamesHandler),
      (r'/start_migration', MigrationStartHandler),
      (r'/worker/migration', MigrationWorker),
      (r'/counters', CounterHandler),
      (r'/worker/write_behind', WriteBehindWorker),
  ], debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
