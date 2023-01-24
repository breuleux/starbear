
Tutorial
========

Creating a Starbear application is simple. All you need to do is write an async function that has the ``@bear`` decorator:

.. code-block:: python

    from starbear import bear

    @bear
    async def app(page):
        page.print("hello world!")

Assuming you wrote this code in ``hello.py``, you can run the application with ``uvicorn``:

.. code-block:: bash

    uvicorn --reload hello:app

The ``--reload`` flag will restart the server when you change a source file, to ease development. You will still need to refresh the page.


Producing HTML
--------------

Use the ``H`` constructor to construct HTML elements, and then use ``page.print`` to send them to the browser.

``page.print`` simply appends stuff to the ``<body>`` tag of the page:


.. code-block:: python

    @bear
    async def app(page):
        page.print(
            H.h1("Hello world!"),
            H.p(
                "The world is certainly very round!",
                style={
                    "color": "red",
                    "text-align": "center",
                }
            ),
            H.a("Visit my webpage!", href="http://breuleux.net")
        )

The syntax for ``H`` is ``H.tag[*classes](*children, **attributes)``.

For example, ``H.span["zebra"]("yak", xi=wow, van=True)`` produces ``<span class="zebra" xi="wow" van>b</span>``.

.. tip::
    It is possible to curry arguments to ``H``, meaning that ``H.div(a, b, c=d)`` is equivalent to ``H.div(a)(b)(c=d)``. That can come in handy if you simply want to set an attribute to an existing element.


.. .. list-table::
..    :widths: 50 50
..    :header-rows: 1

..    * - Expression
..      - HTML
..    * - ``H.div["big"]("The Earth", id="earth")``
..      - ``<div class="big" id="earth">The Earth</div>``
..    * - ``H.div["big", "#earth"]("Earth")``
..      - ``<div class="big" id="earth">The Earth</div>``
..    * - ``H.div("The")(id="earth")(" Earth")["big"]``
..      - ``<div class="big" id="earth">The Earth</div>``


Raw HTML
++++++++

If you have HTML in a string and you want to embed it as-is, use ``H.raw(html)``. For example: ``page.print(H.raw("<b>hello world!<b>"))``.


Title and style
+++++++++++++++

* Use ``page["head"].print`` to add tags to the ``<head>`` of the page.
* Use ``Path("path/to/file")`` to include files from the filesystem.

.. code-block:: python

    from pathlib import Path

    @bear
    async def app(page):
        page["head"].print(
            H.title("My great page!"),
            H.link(
                rel="stylesheet",
                href=Path("./style.css"),
            )
        )
        page.print(H.p("What is the coolest animal? Do you know?"))

.. note::
    Whenever ``Path(p)`` is found in an outbound element, Starbear creates an endpoint for the parent directory of ``p``. This means that there is no way for the client to access a file unless the server either wrapped it with ``Path(p)``, or wrapped a file in one of the parent directories. (The reason why the whole parent directory is whitelisted is simply to enable relative imports in JavaScript modules.)

    If you want to refer to an external website, a CDN, or a route on the server that is not controlled by Starbear, use a string, do not use ``Path``.


Updating the page
-----------------

Now let's get to something more interesting. How do we update the page over time? Well, here is a very simple app that counts down from 10:

.. code-block:: python

    import asyncio

    @bear
    async def app(page):
        page.print(
            "Counting down: ",
            H.span(id="count")
        )
        for i in range(10, -1, -1):
            await asyncio.sleep(1)
            page["#count"].set(str(i))

By indexing ``page`` with a selector, we obtain an object with methods that let us set the contents of the appropriate elements. The selector is not limited to ids. As we will see later ``page["head"].print`` is how we can set a title for the page, add stylesheets, etc.

Using autoid
++++++++++++

It can be a bit annoying to set explicit ids for elements we want to refer to, so there is an easier way:

.. code-block:: python

    @bear
    async def app(page):
        page.print(
            "Counting down: ",
            count := H.span().autoid()
        )
        for i in range(10, -1, -1):
            await asyncio.sleep(1)
            page[count].set(str(i))

In the above, we use ``autoid()`` to give an automatically generated id to the ``<span>`` and then we set ``page[count]`` directly.


Listening to events
-------------------

So far we've only made passive pages. Here is how to process a button click from the user:

.. code-block:: python

    @bear
    async def app(page):
        nclicks = 0
        def increment(event):
            nonlocal nclicks
            nclicks += 1
            page[clickspan].set(str(nclicks))

        page.print(
            H.div(
                H.button("Click me!"),
                onclick=increment,
            ),
            H.div(
                "You clicked ",
                clickspan := H.span(nclicks).autoid(),
                " times."
            )
        )

It's very straightforward: when the user clicks, it sends the click event to the ``increment`` function on the server, which increments the current count and puts it in the ``clickspan`` element.


Using queues
++++++++++++

There is another way to process events: queues. With queues, you can loop over the events using ``async for``. Here is the exact same example as above, remade using a queue:


.. code-block:: python

    from starbear import Queue

    @bear
    async def app(page):
        queue = Queue()
        nclicks = 0

        page.print(
            H.div(
                H.button("Click me!"),
                onclick=queue,
            ),
            H.div(
                "You clicked ",
                clickspan := H.span(nclicks).autoid(),
                " times."
            )
        )

        async for event in queue:
            nclicks += 1
            page[clickspan].set(str(nclicks))


The same queue can be given to multiple handlers.

.. tip::
    To best distinguish which data corresponds to which handler, you can write ``onclick=queue.tag("button1")`` instead of ``onclick=queue`` and the corresponding element in the queue will be ``["button1", event]`` instead of ``event``.


Debouncing/throttling
+++++++++++++++++++++

Sometimes you may want to limit the frequency at which an event is fired, ideally on the browser side, to minimize useless communication. ``ClientWrap`` can achieve this (and other things).

This example evaluates an input as Python, but only after 0.3 seconds have elapsed without data entry:

.. code-block:: python

    from starbear import ClientWrap

    @bear
    async def app(page):
        queue = ClientWrap(Queue(), debounce=0.3)

        page.print(
            H.div(
                H.input(oninput=queue),
            ),
            result := H.div().autoid(),
            error := H.div(style={"color": "red"}).autoid()
        )

        async for event in queue:
            try:
                page[result].set(eval(event["value"]))
                page[error].clear()
            except Exception as exc:
                page[result].clear()
                page[error].set(str(exc))


Forms
-----

Starbear acknowledges ``<form>`` elements and will stash the form values in the ``form`` field of submit events:

.. code-block:: python

    @bear
    async def app(page):
        queue = Queue()

        page.print(
            H.form(
                "What is your name?",
                H.input(name="name"),
                "What is your quest?",
                H.input(name="quest"),
                "What is your favourite color?",
                H.input(name="color"),
                H.button("Submit"),
                onsubmit=queue
            ),
            target := H.div().autoid()
        )

        async for event in queue:
            answers = event["form"]
            name = answers["name"]
            quest = answers["quest"]
            color = answers["color"]
            page[target].set(f"Hi {name}! You seek {quest} and you like {color}!")

Live forms
++++++++++

``ClientWrap(handler, form=True)`` transforms an event handler into one that takes the form values of the element's closest enclosing form. You can set this on other events than ``onsubmit``, for example ``oninput`` which is triggered on every change:

.. code-block:: python

    @bear
    async def app(page):
        queue = Queue()
        debounced = ClientWrap(queue, debounce=0.3, form=True)

        page.print(
            H.form(
                "What is your name?",
                H.input(name="name", oninput=debounced),
                "What is your quest?",
                H.input(name="quest", oninput=debounced),
                "What is your favourite color?",
                H.input(name="color", oninput=debounced),
                H.button("Submit"),
                onsubmit=queue
            ),
            target := H.div().autoid()
        )

        async for answers in queue:
            # Unlike the previous example, answers is not an event object
            name = answers["name"]
            quest = answers["quest"]
            color = answers["color"]
            mark = "!" if answers["$submit"] else "?"
            page[target].set(f"Hi {name}{mark} You seek {quest} and you like {color}{mark}")

The special field ``$submit`` contains ``True`` if the triggering event was a submit event.

.. note::
    In the code above, we use a debounced function for the ``oninput`` events, so the event is delayed, but we give the queue directly to ``onsubmit`` so that it submits the form without delay.

    Naively, this could be problematic, because later events could arrive after earlier events, but in fact Starbear will make sure that the ``onsubmit`` event cancels all outstanding timers for that queue.


Using libraries
---------------

With all that has been mentioned so far, you can already kind of do whatever you want by printing the appropriate script tags. *But there is a better way.*

.. Any HTML element can be given the ``__constructor`` attribute, which lets you load any script or ES6 module and then automatically call either its default export or a function of your choice, passing the newly-constructed element as an argument along with a dict of options.

.. Not only that, Starbear also makes it possible to call JavaScript methods, from Python, on whatever object that function returns.

For example, let's display a mathematical equation using Katex. Looking at the `installation instructions <https://katex.org/docs/browser.html>`_ and the `api instructions <https://katex.org/docs/api.html>`_, we can easily port this for use with Starbear:

.. code-block:: python

    @bear
    async def app(page):
        page.print(
            H.div(
                __constructor = {
                    "script": "https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.js",
                    "symbol": "katex.render",
                    "arguments": ["c = \\pm\\sqrt{a^2 + b^2}", H.self()],
                    "stylesheet": "https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.css",
                }
            )
        )

Here is what Starbear does when this structure is printed to the page:

1. Append the ``script`` and ``stylesheet`` to ``<head>``, unless it has already been done,  and load them.
2. Create a ``<div>`` with an auto-generated ID. Let us say it is in the ``element`` variable.
3. Serialize ``arguments`` and send them over. ``H.self()`` resolves to a reference to ``element``.
4. Call: ``katex.render("c = \\pm\\sqrt{a^2 + b^2}", element)``
5. Stash the returned object in the element, in case we want to call methods on it later.

.. tip::

    The ``arguments`` can contain any JSON-serializable data, but also any element that has an ID, a Python function, or a Queue!

.. note::

    As explained in the title and style section, you may use ``pathlib.Path`` to refer to local files. For example, if you want to load the katex script from the server's local filesystem instead of going through a CDN: ``"script": Path("./assets/katex.js")``.


.. EcmaScript Modules
.. ++++++++++++++++++

.. You can also use the ESM version of Katex by setting ``module`` instead of ``script``:

.. .. code-block:: python

..     page.print(
..         H.div(
..             ZZZZZ__constructor = {
..                 "module": "https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.mjs",
..                 "symbol": "default.render",
..                 "arguments": ["c = \\pm\\sqrt{a^2 + b^2}", H.self()],
..                 "stylesheet": "https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.css",
..             }
..         )
..     )


.. The value of ``symbol`` is used to determine how to import the functionality:

.. * ``symbol=None`` (the default if left out): ``import constructor from 'module'; constructor(...)``
.. * ``symbol="render"``: ``import {render} from 'module'; render(...)``
.. * ``symbol="x.y.z"``: ``import {x} from 'module'; x.y.z(...)``
.. * ``symbol="default.y.z"``: ``import dflt from 'module'; dflt.y.z(...)``

.. The documentation for how to use the ESM version of a library is not always the best, but it's preferable if you can make it work, because it does not pollute the global namespace. You also don't need to specify the ``symbol`` key if the default export is the right constructor to use.
