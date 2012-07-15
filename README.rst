Overview
========

*infi.amqp* is a simple AMQP client, based on `amqplib <http://pypi.python.org/pypi/amqplib/>`_. Its main features include::

  * Publishing messages.
  * Consuming messages.
  * Declaration and binding of exchanges and queues.
  * Auto-reconnection, redeclaration and rebinding.
  * AMQP publishing- and consuming-properties (more or less what amqplib features)

Basic Usage
===========

Usage is very simple::

  1. Create an AMQP instance.
  2. Create exchanges and queues, and bind them if necessary.
  3. Add exchanges and queues to AMQP.
  4. Connect and start working.

Exchanges and queues are declared upon reconnection. If the connection is lost while publishing or consuming messages, AMQP attempts to reconnect, redeclare everything, and perform the operation again.

Example usage::

  >>> from infi.amqp import AMQP, Exchange, Queue
  >>> amqp = AMQP('localhost')
  >>> # Declare exchanges, queues and bindings
  >>> exchange = Exchange('myexchange', 'fanout')
  >>> queue = Queue('myqueue')
  >>> queue.bind(exchange)
  >>> # Add declarations to AMQP; they will be redeclared upon reconnection
  >>> amqp.add_exchange(exchange)
  >>> amqp.add_queue(queue)
  >>> # Connect (and declare everything)
  >>> amqp.connect()
  >>> # Publish a message
  >>> amqp.publish('my message', exchange='myexchange', routing_key='myqueue')
  >>> # Consume messages (in a loop)
  >>> def consume_callback(message):
  ...     try:
  ...         print('Received a message: {}'.format(message.body))
  ...         # Acknowledge this message
  ...         return True
  ...     except:
  ...         # Do not acknowledge
  ...         return False
  >>> amqp.consume(consume_callback, 'myqueue')
