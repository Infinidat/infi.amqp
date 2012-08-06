from __future__ import absolute_import
from amqplib import client_0_8 as amqp
import time
import socket
import errno
import sys
from functools import partial
from logging import getLogger

logger = getLogger('amqp')

class AMQP(object):
    def __init__(self, host, port=5672, vhost='/', username=None, password=None,
                 reconnection_initial_delay=2, reconnection_delay_increment=2, reconnection_max_delay=30):
        self._host, self._port, self._vhost, self._username, self._password = \
                host, port, vhost, username, password
        self._reconn_initial, self._reconn_inc, self._reconn_max = \
                reconnection_initial_delay, reconnection_delay_increment, reconnection_max_delay
        self._connection = self._channel = None
        self._exchanges = []
        self._queues = []
        self._consuming = False
    def add_exchange(self, exchange):
        assert isinstance(exchange, Exchange)
        self._exchanges.append(exchange)
    def add_queue(self, queue):
        assert isinstance(queue, Queue)
        self._queues.append(queue)
    def connect(self):
        if not self._connection:
            self.reconnect()
    def reconnect(self):
        self.close()
        logger.info('Connecting to AMQP broker...')
        delay = self._reconn_initial
        while True:
            try:
                self._connection = amqp.Connection(
                    host='{}:{}'.format(self._host, self._port),
                    virtual_host=self._vhost,
                    userid=self._username,
                    password=self._password,
                    )
                break
            except (socket.error, IOError) as e:
                check_interrupted(e)
                logger.error('Failed to connect to AMQP broker%s, trying again in %d seconds...',
                             format_exception_message(e, ' ({})'), delay)
                logger.debug('', exc_info=1)
                time.sleep(delay)
                delay = min(delay + self._reconn_inc, self._reconn_max)
        self._channel = self._connection.channel()
        for exchange in self._exchanges:
            exchange._declare(self._channel)
        for queue in self._queues:
            queue._declare_and_bind(self._channel)
    def _invoke_channel(self, method_name, *args, **kwargs):
        if self._connection is None:
            self.reconnect()
        while True:
            try:
                method = getattr(self._channel, method_name)
                method(*args, **kwargs)
                break
            except (socket.error, IOError) as e:
                check_interrupted(e)
                logger.error('Lost connection to AMQP broker%s', format_exception_message(e, ': {}'))
                logger.debug('', exc_info=1)
                self.reconnect()
    def publish(self, body, exchange='', routing_key='', content_type=None, delivery_mode=1):
        ''' Publish message.
        @param delivery_mode: 1 for transient, 2 for persistent
        Note regarding keyboard interrupts: if the process is interrupted
        during publishing, a Python KeyboardInterrupt will be raised. If a
        signal handler for SIGINT has been defined, then an AMQPInterrupted
        exception will be raised. '''
        if not isinstance(body, basestring):
            body = str(body)
        logger.debug('Publishing message (exchange=%r, routing_key=%r): %r', exchange, routing_key, body)
        self._invoke_channel(
                'basic_publish',
                amqp.Message(
                    body,
                    content_type=content_type or 'text/plain',
                    delivery_mode=delivery_mode,
                    ),
                exchange=exchange,
                routing_key=routing_key,
                )
    def consume(self, callback, queue='', consumer_tag='', no_local=False,
                no_ack=False, exclusive=False, nowait=False, ticket=None,
                limit=None):
        ''' Start consuming messages. Upon arrival of each message, invoke the
        callback method.
        @param callback: A callback method with one argument
        @param limit: Maximum amount of messages to consume
        (amqplib.client_0_8.Message). The method should return either True or
        False, meaning whether or not to acknowledge the message. '''
        limit = limit or None
        self._invoke_channel('basic_consume',
                callback=partial(self._consumer_callback, callback),
                queue=queue, consumer_tag=consumer_tag, no_local=no_local,
                no_ack=no_ack, exclusive=exclusive, nowait=nowait, ticket=ticket)
        self._consuming = True
        try:
            while self._consuming and (limit is None or limit > 0):
                self._invoke_channel('wait')
                if limit is not None:
                    limit -= 1
        except AMQPInterrupted:
            pass
        except MessageProcessingError as e:
            logger.error(str(e))
        finally:
            self._consuming = False
    def stop_consuming(self):
        self._consuming = False
    def _consumer_callback(self, user_callback, message):
        tag = message.delivery_info['delivery_tag']
        logger.debug('Received message %r', tag)
        try:
            should_ack = user_callback(message)
        except:
            e = sys.exc_info()[1]
            logger.debug('Error during message processing: {}'.format(e), exc_info=True)
            raise MessageProcessingError('Error during message processing: {}'.format(e))
        if should_ack:
            logger.debug('Acknowledging message %r', tag)
            self._invoke_channel('basic_ack', delivery_tag=tag)
    def close(self):
        if self._connection:
            try: self._connection.close()
            except: pass
            self._connection = self._channel = None

class Queue(object):
    def __init__(self, queue='', durable=False, exclusive=False, auto_delete=True,
                 nowait=False, arguments=None, ticket=None):
        self._declaration = dict(queue=queue, durable=durable, exclusive=exclusive, auto_delete=auto_delete,
                                 nowait=nowait, arguments=arguments, ticket=ticket)
        self._bindings = []
        self.name = queue
    def bind(self, exchange, routing_key='', nowait=False, arguments=None, ticket=None):
        if isinstance(exchange, Exchange):
            exchange = exchange._declaration['exchange']
        self._bindings.append(dict(exchange=exchange, routing_key=routing_key,
            nowait=nowait, arguments=arguments, ticket=ticket))
    def _declare_and_bind(self, channel):
        logger.debug('Declaring queue: %r', self._declaration)
        response = channel.queue_declare(**self._declaration)
        self.name = response[0]
        for binding in self._bindings:
            logger.debug('Binding queue: %r', binding)
            channel.queue_bind(queue=self.name, **binding)

class Exchange(object):
    def __init__(self, exchange, type, durable=False, auto_delete=False,
                 internal=False, nowait=False, arguments=None, ticket=None):
        self._declaration = dict(exchange=exchange, type=type, durable=durable, auto_delete=auto_delete,
                                 internal=internal, nowait=nowait, arguments=arguments, ticket=ticket)
    def _declare(self, channel):
        logger.debug('Declaring exchange: %r', self._declaration)
        channel.exchange_declare(**self._declaration)


### UTILITIES ###

def check_interrupted(e):
    if hasattr(e, 'errno') and e.errno == errno.EINTR:
        raise AMQPInterrupted

def format_exception_message(e, template='{}'):
    msg = str(e)
    if msg:
        msg = template.format(msg)
    return msg

### EXCEPTIONS ###

class AMQPError(Exception):
    pass
class AMQPInterrupted(AMQPError):
    pass
class MessageProcessingError(AMQPError):
    pass
