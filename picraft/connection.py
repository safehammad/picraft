# vim: set et sw=4 sts=4 fileencoding=utf-8:
#
# An alternate Python Minecraft library for the Rasperry-Pi
# Copyright (c) 2013-2015 Dave Jones <dave@waveform.org.uk>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the copyright holder nor the
#       names of its contributors may be used to endorse or promote products
#       derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division,
    )
str = type('')


import socket
import logging
import select

from .exc import ConnectionError, BatchStarted, BatchNotStarted


class Connection(object):
    """
    Represents the connection to the Minecraft server.

    The *host* parameter specifies the hostname or IP address of the Minecraft
    server, while *port* specifies the port to connect to (these typically take
    the values "127.0.0.1" and 4711 respectively).

    The *timeout* parameter specifies the maximum time that the client will
    wait after sending a command before assuming that the command has succeeded
    (see the :ref:`protocol` section for more information). If *ignore_errors*
    is ``True`` (the default is ``False``), act like the official reference
    implementation and ignore all errors for commands which do not return data.

    Users will rarely need to construct a :class:`Connection` object
    themselves. An instance of this class is constructed by :class:`Game` to
    handle communication with the game server (:attr:`Game.connection`).

    The most important aspect of this class is its ability to "batch"
    transmissions together. Typically, the :meth:`send` method is used to
    transmit requests to the Minecraft server. When this is called normally
    (outside of a batch), it immediately transmits the requested data. However,
    if :meth:`batch_start` has been called first, the data is *not* sent
    immediately, but merely appended to the batch. The :meth:`batch_send`
    method can then be used to transmit all requests simultaneously (or
    alternatively, :meth:`batch_forget` can be used to discard the list). See
    the docs of these methods for more information.
    """

    def __init__(
            self, host, port, timeout=0.2, ignore_errors=False,
            encoding='ascii'):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((host, port))
        self._rfile = self._socket.makefile('rb', -1)
        self._wfile = self._socket.makefile('wb', 0) # no buffering for writes
        self._batch = None
        self.timeout = timeout
        self.ignore_errors = ignore_errors
        self.encoding = encoding

    def close(self):
        """
        Closes the connection.

        This method can be used to close down the connection to the game
        server. It is typically called from :meth:`Game.close` rather
        than being called directly.
        """
        try:
            self.batch_forget()
        except BatchNotStarted:
            pass
        if self._rfile:
            self._rfile.close()
            self._rfile = None
        if self._wfile:
            self._wfile.close()
            self._wfile = None
        if self._socket:
            self._socket.close()
            self._socket = None

    def _readable(self, timeout):
        """
        Determines whether the socket is readable within the given timeout.
        """
        return bool(select.select([self._socket], [], [], timeout)[0])

    def _drain(self):
        """
        Drain all data from the readable end of the socket. This is typically
        used to ensure that any "Fail" messages are removed prior to executing
        something for which we expect a result.
        """
        while True:
            if not self._readable(0):
                break
            data = self._socket.recv(1500)

    def _send(self, buf):
        """
        Write *buf* (suitably encoded) to the socket.
        """
        if not buf.endswith('\n'):
            buf += '\n'
        buf = buf.encode(self.encoding)
        if self.ignore_errors:
            self._drain()
        self._wfile.write(buf)
        logging.debug('picraft >: %r' % buf)

    def _receive(self, required=False):
        """
        Read a line from the socket. If required is True, block until a
        line becomes available. Otherwise, return after the timeout. If the
        line read is "Fail", raise a :exc:`ConnectionError` exception.
        """
        if not required:
            if not self._readable(self.timeout):
                return
        result = self._rfile.readline().decode(self.encoding)
        logging.debug('picraft <: %r' % result)
        result = result.rstrip('\n')
        if result == 'Fail':
            raise ConnectionError('an error occurred')
        return result

    def send(self, buf):
        """
        Transmits the contents of *buf* to the connected server.

        If no batch has been initiated (with :meth:`batch_start`), this method
        immediately communicates the contents of *buf* to the connected
        Minecraft server. If *buf* is a unicode string, the method attempts
        to encode the content in a byte-encoding prior to transmission (the
        encoding used is the :attr:`encoding` attribute of the class which
        defaults to "ascii").

        If a batch has been initiated, the contents of *buf* are appended to
        the latest batch that was started (batches can be nested; see
        :meth:`batch_start` for more information).
        """
        if self._batch is not None:
            self._batch.append(buf)
        else:
            self._send(buf)
            if not self.ignore_errors:
                self._receive()

    def transact(self, buf):
        """
        Transmits the contents of *buf*, and returns the reply string.

        This method immediately communicates the contents of *buf* to the
        connected server, then reads a line of data in reply and returns it.

        .. note::

            This method ignores the batch mechanism entirely as transmission
            is required in order to obtain the response. As this method
            is typically used to implement "getters", this is not usually an
            issue but it is worth bearing in mind.
        """
        self._send(buf)
        return self._receive(required=True)

    def batch_start(self):
        """
        Starts a new batch transmission.

        When called, this method starts a new batch transmission. All
        subsequent calls to :meth:`send` will append data to the batch buffer
        instead of actually sending the data.

        To terminate the batch transmission, call :meth:`batch_send` or
        :meth:`batch_forget`. If a batch has already been started, a
        :exc:`BatchStarted` exception is raised.

        .. note::

            This method can be used as a context manager
            (:ref:`the-with-statement`) which will cause a batch to be started,
            and implicitly terminated with :meth:`batch_send` or
            :meth:`batch_forget` depending on whether an exception is raised
            within the enclosed block.
        """
        if self._batch is not None:
            raise BatchStarted('batch already started')
        self._batch = []
        return self

    def batch_send(self):
        """
        Sends the batch transmission.

        This method is called after :meth:`batch_start` and :meth:`send` have
        been used to build up a list of batch commands. All the commands will
        be combined and sent to the server as a single transmission.

        If no batch is currently in progress, a :exc:`BatchNotStarted`
        exception will be raised.
        """
        if self._batch is None:
            raise BatchNotStarted('no batch in progress')
        buf = '\n'.join(self._batch)
        self._batch = None
        self._send(buf)
        try:
            if not self.ignore_errors:
                self._receive()
        finally:
            self._drain()

    def batch_forget(self):
        """
        Terminates a batch transmission without sending anything.

        This method is called after :meth:`batch_start` and :meth:`send`
        have been used to build up a list of batch commands. All commands in
        the batch will be cleared without sending anything to the server.

        If no batch is currently in progress, a :exc:`BatchNotStarted`
        exception will be raised.
        """
        if self._batch is None:
            raise BatchNotStarted('no batch in progress')
        self._batch = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_type is None:
            self.batch_send()
        else:
            self.batch_forget()

