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




"""Python DB-API (PEP 249) interface to Speckle.

http://www.python.org/dev/peps/pep-0249/
"""


import collections
import datetime
import exceptions
import time
import types

from google.storage.speckle.proto import client_pb2
from google.storage.speckle.proto import jdbc_type
from google.storage.speckle.proto import sql_pb2
from google.storage.speckle.python import api
from google.storage.speckle.python.api import converters




__path__ = api.__path__







apilevel = '2.0'

threadsafety = 1



paramstyle = 'format'



version_info = (1, 2, 2, 'final', 0)







class Warning(StandardError, exceptions.Warning):
  pass

class Error(StandardError):
  pass

class InterfaceError(Error):
  pass

class DatabaseError(Error):
  pass

class DataError(DatabaseError):
  pass

class OperationalError(DatabaseError):
  pass

class IntegrityError(DatabaseError):
  pass

class InternalError(DatabaseError):
  pass

class ProgrammingError(DatabaseError):
  pass

class NotSupportedError(DatabaseError):
  pass

Blob = converters.Blob



def Date(year, month, day):
  return datetime.date(year, month, day)

def Time(hour, minute, second):
  return datetime.time(hour, minute, second)

def Timestamp(year, month, day, hour, minute, second):
  return datetime.datetime(year, month, day, hour, minute, second)

def DateFromTicks(ticks):
  return Date(*time.localtime(ticks)[:3])

def TimeFromTicks(ticks):
  return Time(*time.localtime(ticks)[3:6])

def TimestampFromTicks(ticks):
  return Timestamp(*time.localtime(ticks)[:6])

def Binary(string):
  return Blob(string)


STRING = unicode
BINARY = Blob
NUMBER = float
DATETIME = datetime.datetime
ROWID = int


_PYTHON_TYPE_TO_JDBC_TYPE = {
    types.IntType: jdbc_type.INTEGER,
    types.LongType: jdbc_type.INTEGER,
    types.FloatType: jdbc_type.DOUBLE,
    types.BooleanType: jdbc_type.BOOLEAN,
    types.StringType: jdbc_type.VARCHAR,
    types.UnicodeType: jdbc_type.VARCHAR,
    datetime.date: jdbc_type.DATE,
    datetime.datetime: jdbc_type.TIMESTAMP,
    datetime.time: jdbc_type.TIME,
    converters.Blob: jdbc_type.BLOB,
    }


def _ConvertFormatToQmark(statement, args):
  """Replaces '%s' with '?'.

  The server actually supports '?' for bind parameters, but the
  MySQLdb implementation of PEP 249 uses '%s'.  Most clients don't
  bother checking the paramstyle member and just hardcode '%s' in
  their statements.  This function converts a format-style statement
  into a qmark-style statement.

  Args:
    statement: A string, a SQL statement.

  Returns:
    The converted string.
  """
  if args:
    qmarks = tuple('?' * len(args))
    return statement % qmarks
  return statement


class Cursor(object):

  def __init__(self, conn):
    """Initializer.

    Args:
      conn: A Connection object.
    """
    self._conn = conn
    self._description = None
    self._rowcount = -1
    self.arraysize = 1
    self._open = True
    self.lastrowid = None

  @property
  def description(self):
    return self._description

  @property
  def rowcount(self):
    return self._rowcount

  def close(self):
    """Marks the cursor as unusable for further operations."""
    self._CheckOpen()
    self._open = False

  def _EncodeVariable(self, arg):
    """Converts a variable to a type and value.

    Args:
      arg: Any tuple, string, numeric, or datetime object.

    Returns:
      A (int, str) tuple, representing a JDBC type and encoded value.

    Raises:
      TypeError: The argument is not a recognized type.
    """
    jdbc_type = _PYTHON_TYPE_TO_JDBC_TYPE.get(type(arg))
    if jdbc_type is None:


      try:
        jdbc_type = _PYTHON_TYPE_TO_JDBC_TYPE[type(arg[0])]
      except (TypeError, KeyError):


        raise TypeError('unknown type')
    value = self._conn.conversions[type(arg)](arg, self._conn.conversions)
    return jdbc_type, value

  def _DecodeVariable(self, datatype, value):
    """Converts a type and value to a variable.

    Args:
      datatype: An integer.
      value: A string.

    Returns:
      An object of some appropriate type.

    Raises:
      InterfaceError: datatype is not a recognized JDBC type.
      ValueError: The value could not be parsed.
    """


    converter = self._conn.conversions.get(datatype)
    if converter is None:
      raise InterfaceError('unknown JDBC type %d' % datatype)
    return converter(value)

  def execute(self, statement, args=None):
    """Prepares and executes a database operation (query or command).

    Args:
      statement: A string, a SQL statement.
      args: A sequence of arguments matching the statement's bind variables,
        if any.

    Raises:
      InterfaceError: Unknown type used as a bind variable.
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self._CheckOpen()

    request = sql_pb2.ExecRequest()
    request.options.include_generated_keys = True
    if args is not None:

      if not hasattr(args, '__iter__'):
        args = [args]
      for i, arg in enumerate(args):
        bv = request.bind_variable.add()
        bv.position = i + 1
        if arg is None:
          bv.type = jdbc_type.NULL
        else:
          try:
            bv.type, bv.value = self._EncodeVariable(arg)
          except TypeError:
            raise InterfaceError('unknown type %s for arg %d' % (type(arg), i))
    request.statement = _ConvertFormatToQmark(statement, args)

    response = self._conn.MakeRequest('Exec', request)
    result = response.result
    if result.HasField('sql_exception'):
      raise DatabaseError(result.sql_exception.message)

    self._rows = collections.deque()
    if result.rows.columns:
      self._description = []
      for column in result.rows.columns:
        self._description.append(
            (column.name, column.type, column.display_size, None,
             column.precision, column.scale, column.nullable))
    else:
      self._description = None

    if result.rows.tuples:
      self._rowcount = len(result.rows.tuples)
      for tuple_proto in result.rows.tuples:
        row = []
        nulls = set(tuple_proto.nulls)
        value_index = 0
        for i, column_descr in enumerate(self._description):
          if i in nulls:
            row.append(None)
          else:
            row.append(self._DecodeVariable(column_descr[1],
                                            tuple_proto.values[value_index]))
            value_index += 1
        self._rows.append(tuple(row))
    else:
      self._rowcount = result.rows_updated

    if result.generated_keys:
      self.lastrowid = long(result.generated_keys[-1])

  def executemany(self, statement, seq_of_args):
    """Calls execute() for each value of seq_of_args.

    Args:
      statement: A string, a SQL statement.
      seq_of_args: A sequence, each entry of which is a sequence of arguments
        matching the statement's bind variables, if any.
    """
    self._CheckOpen()
    rowcount = 0
    for args in seq_of_args:
      self.execute(statement, args)
      rowcount += self.rowcount
    self._rowcount = rowcount

  def fetchone(self):
    """Fetches the next row of a query result set.

    Returns:
      A sequence, or None when no more data is available.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
    """
    self._CheckOpen()
    if self._rowcount == -1:
      raise InternalError('fetchone() called before execute')
    try:
      return self._rows.popleft()
    except IndexError:
      return None

  def fetchmany(self, size=None):
    """Fetches the next set of rows of a query result.

    Args:
      size: The maximum number of rows to return; by default, self.arraysize.

    Returns:
      A sequence of sequences, or an empty sequence when no more data is
      available.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
    """
    self._CheckOpen()
    if self._rowcount == -1:
      raise InternalError('fetchmany() called before execute')
    if size is None:
      size = self.arraysize
    if size >= len(self._rows):
      return self.fetchall()
    else:
      result = []
      for _ in xrange(size):
        result.append(self._rows.popleft())
      return tuple(result)

  def fetchall(self):
    """Fetches all remaining rows of a query result.

    Returns:
      A sequence of sequences, or an empty sequence when no more data is
      available.

    Raises:
      InternalError: The cursor has been closed, or no statement has been
        executed yet.
    """
    self._CheckOpen()
    if self._rowcount == -1:
      raise InternalError('fetchall() called before execute')
    rows = self._rows
    self._rows = collections.deque()
    return tuple(rows)

  def setinputsizes(self, unused_sizes):
    self._CheckOpen()


  def setoutputsize(self, unused_size, unused_column=None):
    self._CheckOpen()


  def _CheckOpen(self):
    self._conn.CheckOpen()
    if not self._open:
      raise InternalError('cursor has been closed')


class Connection(object):

  def __init__(self, dsn, instance, database=None, user='root', password=None,
               deadline_seconds=30.0, conv=None):
    """Creates a new Speckle connection.

    Args:
      dsn: A string, the Speckle BNS path or host:port.
        TODO(mshields): Support something else for App Engine.
      instance: A string, the Speckle instance name, often a username.
      database: A string, semantics defined by the backend.
      user: A string, database user name.
      password: A string, database password.
      deadline_seconds: A float, request deadline in seconds.
      conv: A dict, maps types to a conversion function. See converters.py.

    Raises:
      OperationalError: Transport failure.
      DatabaseError: Error from Speckle server.
    """
    self._dsn = dsn
    self._instance = instance
    self._database = database
    self._user = user
    self._password = password
    self._deadline_seconds = deadline_seconds
    self._connection_id = None
    self.conversions = conv or converters.conversions
    self.OpenConnection()

  def OpenConnection(self):
    raise InternalError('No transport defined. Try using rdbms_[transport]')

  def close(self):
    """Makes the connection and all its cursors unusable.

    The connection will be unusable from this point forward; an Error
    (or subclass) exception will be raised if any operation is attempted
    with the connection.
    """
    self.CheckOpen()
    request = sql_pb2.CloseConnectionRequest()
    self.MakeRequest('CloseConnection', request)
    self._connection_id = None

  def CheckOpen(self):
    if self._connection_id is None:
      raise InternalError('connection has been closed')

  def commit(self):
    """Commits any pending transaction to the database.

    Raises:
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self.CheckOpen()
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.COMMIT
    self.MakeRequest('ExecOp', request)

  def rollback(self):
    """Rolls back any pending transaction to the database.

    Raises:
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self.CheckOpen()
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.ROLLBACK
    self.MakeRequest('ExecOp', request)

  def autocommit(self, value):
    """Changes whether there is an implicit commit after each statement.

    By default, transactions must be explicitly committed.

    Args:
      value: A boolean.

    Raises:
      DatabaseError: A SQL exception occurred.
      OperationalError: RPC problem.
    """
    self.CheckOpen()
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.SET_AUTO_COMMIT
    request.op.auto_commit = value
    self.MakeRequest('ExecOp', request)

  def cursor(self):
    """Returns a cursor for the current connection."""
    return Cursor(self)

  def MakeRequest(self, stub_method, request):
    raise InternalError('No transport defined. Try using rdbms_[transport]')

  def get_server_info(self):
    """Returns a string that represents the server version number.

    Non-standard; Provided for API compatibility with MySQLdb.

    Returns:
      The server version number string.
    """
    self.CheckOpen()
    request = sql_pb2.MetadataRequest()
    request.metadata = client_pb2.METADATATYPE_DATABASE_METADATA_BASIC
    response = self.MakeRequest('GetMetadata', request)
    return response.jdbc_database_metadata.database_product_version

  def ping(self, reconnect=False):
    """Checks whether or not the connection to the server is working.

    If it has gone down, an automatic reconnection is attempted.

    This function can be used by clients that remain idle for a long while, to
    check whether or not the server has closed the connection and reconnect if
    necessary.

    Non-standard. You should assume that ping() performs an implicit rollback;
    use only when starting a new transaction.  You have been warned.

    Args:
      reconnect: Whether to perform an automatic reconnection.

    Raises:
      DatabaseError: The connection to the server is not working.
    """
    self.CheckOpen()
    request = sql_pb2.ExecOpRequest()
    request.op.type = client_pb2.OpProto.PING
    try:
      self.MakeRequest('ExecOp', request)
    except DatabaseError:
      if not reconnect:
        raise
      self.OpenConnection()




  Warning = Warning
  Error = Error
  InterfaceError = InterfaceError
  DatabaseError = DatabaseError
  DataError = DataError
  OperationalError = OperationalError
  IntegrityError = IntegrityError
  InternalError = InternalError
  ProgrammingError = ProgrammingError
  NotSupportedError = NotSupportedError

connect = Connection
