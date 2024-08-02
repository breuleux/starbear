
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

You *can* add a title and a style with ``page["head"].print``, but it may cause some flickering, so there is a better way:

* Use ``@bear(title="xyz")`` to set the page's title from inception.
* Use ``page.add_resources(path_to_style, path_to_script, path_to_icon ...)`` to add resources. Starbear will wait until they are loaded to process further actions.

.. code-block:: python

    from pathlib import Path

    @bear(title="My great page!")
    async def app(page):
        page.add_resources(Path("./style.css"))
        page.print(H.p("What is the coolest animal? Do you know?"))

.. note::
    Whenever ``Path(p)`` is found in an outbound element, Starbear creates an endpoint for the parent directory of ``p``. This means that there is no way for the client to access a file unless the server either wrapped it with ``Path(p)``, or wrapped a file in one of the parent directories. (The reason why the whole parent directory is whitelisted is simply to enable relative imports in JavaScript modules.)

    If you want to refer to an external website, a CDN, or a route on the server that is not controlled by Starbear, use a string, do not use ``Path``.


Templating
++++++++++

You can use your own templates. For example:

.. code-block:: python

    from pathlib import Path

    @bear(template=Path("my-template.html"), template_params={"adjective": "awesome"})
    async def app(page):
        page.print("I think you're cute")
        page["#top"].print("Dear user,")

Then, you can define your template like this:

.. code-block:: html

    <!DOCTYPE html>
    <html>
        <head>
            <meta http-equiv="Content-type" content="text/html" charset="UTF-8" />
            <title>My {{adjective}} page</title>
            <link rel="stylesheet" href="{{asset:my-style.css}}" />
            {{bearlib}}
        </head>
        <body>
            {{dev}}
            <div id="top"></div>
        </body>
    </html>

* ``{{bearlib}}``: **must** be included somewhere in order for the app to work: otherwise ``page.print`` will do nothing.
* ``{{asset:file.css}}`` must be a path to a file and is relative to the template file.
* ``{{embed:file.html}}`` must be a path to another template, relative to the template file. The other template's contents will be inserted at that location.
* ``{{route}}`` is the route to this page, if that may be useful.
* ``{{dev}}`` is optional, it is code to inject in development mode (e.g. a button to restart server).

You can also use templates dynamically. For example, if you have a header in ``header.html``, this code would replace the contents of ``#top`` by the filled-in template.

.. code-block:: python

    page["#top"].template(
        Path("header.html"),
        email=user_email,
    )


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

By indexing ``page`` with a selector, we obtain an object with methods that let us set the contents of the appropriate elements. The selector is not limited to ids, you can use any valid CSS selector. For example, you can print to ``page["head"]``, or to ``page[".article div"]``. The latter would print to every single div inside any element that has the class ``article``.


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

    @bear(strongrefs=True)
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

The ``strongrefs=True`` argument to ``@bear`` serves the purpose of keeping the nested ``increment`` function alive after the function returns. Starbear normally keeps weak references to the handlers to limit memory leaks, but with the strongrefs parameters, it will keep the function alive for as long as the user is on the page.


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

References
++++++++++

It is possible to attach *references* to Python objects to various elements, and then to retrieve them. For example:

.. code-block:: python

    from dataclasses import dataclass
    from starbear import Queue, Reference

    @dataclass
    class Person:
        name: str
        age: int

    @bear
    async def app(page):
        q = Queue()
        persons = [Person("Alice", 29), Person("Barbara", 34)]
        page.print(
            H.div(
                [
                    H.button(person.name, __ref=Reference(person))
                    for person in persons
                ],
                onclick=q.wrap(refs=True)
            )
        )
        async for event in q:
            person = event.ref
            page.print(H.div(person.name, " is ", person.age, " years old."))

The ``__ref`` attribute (which is translated to ``--ref`` in HTML) is an automatically generated ID number that is exchanged back and forth.

``q.wrap(refs=True)`` packages the hierarchy of ``__ref`` attributes from whichever element is clicked; if there are none, no event is generated. ``event.ref`` will retrieve the closest ref in the hierarchy, but you can see the whole hierarchy in ``event.refs``.

.. note::
    Starbear only keeps weak references to these objects, therefore you must make sure you keep strong references yourself through the lifetime of the function.

    Objects that cannot have weak references are kept in a limited buffer of strong references. An error will be displayed if that limit is busted.

    Use ``@bear(strongrefs=True)`` to force Starbear to keep strong references across the board, but be aware that memory can leak easily this way if you do complex things, even if everything is ultimately reclaimed when the user disconnects.


Using libraries
---------------

With all that has been mentioned so far, you can already kind of do whatever you want by printing the appropriate script tags. *But there is a better way.*

For example, let's display a mathematical equation using Katex. Looking at the `installation instructions <https://katex.org/docs/browser.html>`_ and the `api instructions <https://katex.org/docs/api.html>`_, we can easily port this for use with Starbear:

.. code-block:: python

    from hrepr import J, H

    @bear
    async def app(page):
        katex = J(
            src="https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.js",
            stylesheet="https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.css"
        ).katex
        page.print(
            katex.render(
                "c = \\pm\\sqrt{a^2 + b^2}",
                returns(H.div()),
            )
        )

Here is what Starbear does when this structure is printed to the page:

1. Append the ``script`` and ``stylesheet`` to ``<head>``, unless it has already been done, and load them.
2. Call ``katex.render`` on the expression and a new div.
3. Insert the argument of ``returns(...)`` where the expression is located.
4. Stash the object returned by ``katex.render`` in the aforementioned element, in case we want to call methods on it later.

.. tip::

    The ``arguments`` can contain any JSON-serializable data, but also elements (dynamically constructed), existing elements through a selector (e.g. ``page[selector]``), Python function, or a Queue!

.. note::

    As explained in the title and style section, you may use ``pathlib.Path`` to refer to local files. For example, if you want to load the katex script from the server's local filesystem instead of going through a CDN: ``src=Path("./assets/katex.js")``.


EcmaScript Modules
++++++++++++++++++

You can also use the ESM version of Katex by setting ``module`` (for the default export) or ``namespace`` (for named exports) instead of ``src``:

.. code-block:: python

    katex = J(
        module="https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.mjs",
        stylesheet="https://cdn.jsdelivr.net/npm/katex@0.16.4/dist/katex.css"
    )
    page.print(
        katex.render(
            "c = \\pm\\sqrt{a^2 + b^2}",
            returns(H.div()),
        )
    )

Here are all the ways to use ``J``:

* ``J().fn`` is equivalent to using the global variable ``fn``
* ``J(src=X).fn`` will insert a ``<script src=X>`` tag and will fetch the ``fn`` global variable (assuming the script sets it).
* ``J(module=X).fn`` is equivalent to ``import tmp from X; tmp.fn``
* ``J(namespace=X).fn`` is equivalent to ``import {fn} from X``
* ``J(selector=X).fn`` is equivalent to ``document.querySelector(X).fn``
* ``J(object=X).fn`` is equivalent to ``(await document.querySelector(X).__object).fn``
