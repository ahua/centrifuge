Description
===========

.. _description:

Overview
~~~~~~~~

In this chapter I'll try to explain how Centrifuge actually works.

In a few words - clients from browsers connect to Centrifuge, after connecting clients
subscribe on channels. And every message which was published into channel will be sent
to all clients which are currently subscribed on this channel.

When you start Centrifuge instance you start Tornado instance on a certain port number.
That port number can be configured using command-line option ``--port`` . By default ``8000``.
You can also specify the address to bind to with the ``--address`` option. For example you
can specify ``localhost`` which is recommended if you want to keep Centrifuge behind a
proxy (e.g.: Nginx). The port and the address will eventually be used by Tornado's TCPServer.

In general you should provide path to JSON configuration file when starting Centrifuge instance
using ``--config`` option. You can start Centrifuge without configuration file but this is
not secure and must be used only during development. Configuration file must contain valid JSON.
But for now let's omit configuration file. By default Centrifuge will use insecure cookie secret,
no administrative password, local SQLite storage as structure database and Memory engine (more
about what is structure and what is engine later).

So the final command to start one instance of Centrifuge will be

.. code-block:: bash

    centrifuge --config=config.json

Or just

.. code-block:: bash

    centrifuge

You can run more instances of Centrifuge using Redis engine. But for most cases one instance is more
than enough.

Well, you started one instance of Centrifuge - clients from web browsers can start connecting
to it.

There are two endpoints for connections:
- ``/connection`` for SockJS connections
- ``/connection/websocket`` for pure Websocket connections

On browser side you now know the url to connect - for our simple case it is ``http://localhost:8000/connection``
in case of using SockJS library and ``ws://localhost:8000/connection/websocket`` in case of using
pure Websockets.

To communicate with Centrifuge from browser you should use javascript client which comes
with Centrifuge (find it `in its own repository <https://github.com/centrifugal/centrifuge-js>`_)
and provides simple API. Please, read a `chapter <https://centrifuge.readthedocs.org/en/latest/content/client_api.html>`_ about client API to get more information.

Sometimes you need to run more instances of Centrifuge and load balance clients between them.
As was mentioned above when you start default instance of Centrifuge - you start it with
Memory Engine. In this case Centrifuge holds all state in memory. But to run several Centrifuge
instances we must provide a way to share current state between instances. For this purpose Centrifuge
utilizes Redis. To run Centrifuge with Redis you should run Centrifuge with Redis Engine
instead of default Memory Engine.

First, install and run Redis (it's recommended to use Redis of version 2.6.9 or greater).

Now you can start several instances of Centrifuge. Let's start 2 instances.

Open terminal and run first instance:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --port=8000

I.e. you tell Centrifuge to use Redis Engine providing environment variable
``CENTRIGUGE_ENGINE`` when launching it.

Explore available command line options specific for Redis engine using ``--help``:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --help

``CENTRIFUGE_ENGINE`` can be ``memory``, ``redis`` or path to custom engine class
like ``path.to.custom.Engine``

Then open another terminal window and run second instance on another port:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --port=8001

Now two instances running and connected via Redis. Great!

But what is an url to connect from browser - ``http://localhost:8000/connection`` or
``http://localhost:8001/connection``?

None of them, because Centrifuge must be kept behind proper load balancer such as Nginx.
Nginx must be configured in a way to balance client connections from browser between our
two instances. You can find Nginx configuration example in repo.

New client can connect to any of running instances. If client sends message we must
send that message to other clients including those who connected to another instance
at this moment. This is why we need Redis PUB/SUB here. All instances listen to special
Redis channels and receive messages from those channels.

In Centrifuge you can create projects and namespaces in projects. This information
must be stored somewhere and shared between all running instances. To achieve this by
default Centrifuge uses SQLite database. If all your instances running on the
same machine - it's OK. But if you deploy Centrifuge on several machines
it is impossible to use SQLite database. In this case you can use `PostgreSQL backend <https://github.com/centrifugal/centrifuge-postgresql>`_ or
`MongoDB backend <https://github.com/centrifugal/centrifuge-mongodb>`_. You can also use
PostgeSQL or MongoDB backends if your web site already uses them.

To avoid making query to database on every request all structure information loaded into memory and then updated when something
in structure changed and periodically to avoid inconsistency. There is also an option
to set all structure in configuration file and go without any database (no database, no
dependencies - but structure can not be changed via API or web interface).

You can choose structure backend in the same way as engine - via environment variable
``CENTRIFUGE_STORAGE``:

.. code-block:: bash

    CENTRIFUGE_STORAGE=sqlite centrifuge --path=/tmp/centrifuge.db

Use default SQLite database.

Or:

.. code-block:: bash

    CENTRIFUGE_STORAGE=file centrifuge --port=8001 --file=/path/to/json/file/with/structure

Use structure from JSON file.

Or:

.. code-block:: bash

    CENTRIFUGE_STORAGE=centrifuge_mongodb.Storage centrifuge --mongodb_host=localhost

To use installed MongoDB backend.

Or:

.. code-block:: bash

    CENTRIFUGE_STORAGE=centrifuge_postgresql.Storage centrifuge

As in case of engine you can use ``--help`` to see available options for each of
structure storage backends.


Projects
~~~~~~~~

When you have running Centrifuge instance and want to create web application using it -
first you should do is to add your project into Centrifuge. It's very simple - just fill
the form in web interface.

**project name** - unique project name, must be written using ascii letters, numbers, underscores or hyphens.

**display name** - project's name in web interface.

**connection check** - turn on connection check mechanism. When clients connect to Centrifuge
they provide timestamp - the UNIX time when their token was created. Every connection in
project has connection lifetime (see below). This mechanism is disabled by default and
requires extra endpoint to be implemented in your application.

**connection lifetime in seconds** - this is a time interval in seconds for connection to expire.
Keep it as large as possible in your case.

**is watching** - publish messages into admin channel (messages will be visible in web interface).
Turn it off if you expect high load in channels.

**publish** - allow clients to publish messages in channels (your web application never receive those messages)

**anonymous access** - allow anonymous (with empty USER ID) clients to subscribe on channels

**presence** - enable/disable presence information

**history** - enable/disable history of messages

**history size** - Centrifuge keeps all history in memory. In process memory in case of using Memory Engine
and in Redis (which also in-memory store) in case of using Redis Engine. So it's very important to limit
maximum amount of messages in channel history. This setting is exactly for this.

**history expire** - as all history is storing in memory it is also very important to get rid of old history
data for unused (inactive for a long time) channels. This is interval in seconds to keep history for channel
after last publishing into it. If you set this setting to 0 - history will never expire but it is not
recommended due to design of Centrifuge.

**join/leave messages** - enable/disable sending join(leave) messages when client subscribes
on channel (unsubscribes from channel)

Channels
~~~~~~~~

The central part of Centrifuge is channels. Channel is a route for messages. Clients subscribe on
channels, messages are being published into channels, channels everywhere.

Channel is just a string - ``news``, ``comments`` are valid channel names.

BUT! You should remember several things.

First, channel name length is limited by 255 characters by default (can be changed via configuration file option ``max_channel_length``)

Second, ``:`` and ``#`` and ``$`` symbols has a special role in channel names!

``:`` - is a separator for namespace (see what is namespace below).

So if channel name is ``public:chat`` - then Centrifuge will search for namespace ``public``.

``#`` is a separator to create private channels for users without sending POST request to
your web application. For example if channel is ``news#user42`` then only user with id ``user42``
can subscribe on this channel.

Moreover you can provide several user IDs in channel name separated by comma: ``dialog#user42,user43`` -
in this case only ``user42`` and ``user43`` will be able to subscribe on this channel.

If channel starts with ``$`` (by default) then it's considered private. Read special
chapter in docs about private channel subscriptions.


Namespaces
~~~~~~~~~~

Centrifuge allows to configure channel's settings using namespaces.

You can create new namespace, configure its settings and after that every
channel which belongs to this namespace will have these settings. It's flexible and
provides a great control over channel behaviour. You can reduce the amount of messages
travelling around dramatically by configuring namespace (for example disable join/leave)
messages if you don't need them.

Namespace has several parameters - they are the same as project's settings. But with extra
one:

**namespace name** - unique namespace name: must consist of letters, numbers, underscores or hyphens

As was mentioned above if you want to attach channel to namespace - you must include namespace
name into channel name with ``:`` as separator:

For example:

``news:messages``

``gossips:messages``

Where ``news`` and ``gossips`` are namespace names.
