
# Starbear

[Documentation](https://starbear.readthedocs.io/en/latest/)

[Tutorial](https://starbear.readthedocs.io/en/latest/tutorial.html#tutorial)

Starbear allow creating interactive local web applications in Python very easily.

* The entire app is a single async function.
* Call Python functions from JS, call JS functions from Python.
* No subroutes: starbear automatically creates the endpoints you need.

**Be careful about using this in production:** Starbear is a beta, experimental framework. It is not highly efficient and may not scale very well, therefore you should use this for small apps that you want to run locally or that don't need high uptime and reliability.


## Install

```bash
pip install starbear
```


## Example


```python
from hrepr import H
from pathlib import Path
from starbear import bear, Queue

@bear
async def app(page):
    # Events coming from the webpage will be added to this Queue
    q = Queue()

    # You can print to any part of the page using a CSS selector, for
    # example we can add stuff to the <head> element:
    page["head"].print(
        # Use H.xyz to create a <xyz> node
        H.title("Clicking game!"),
        # If you give a Path object, Starbear will serve the corresponding
        # file for you.
        H.link(rel="stylesheet", href=Path("path/to/style.css"))
    )

    # page.print prints to <body> by default
    page.print(
        # If you give a Queue as an onclick handler, the events will be
        # accumulated in that queue. You can also give a Python function
        # as a handler.
        H.button("Click me!", onclick=q),
        H.div(
            # This is the span we want to update, so we put it in a variable
            target := H.span("0", id=True),
            " clicks"
        )
    )

    i = 0
    # And now we can simply loop over the event queue. Be careful to use *async* for,
    # which will yield to the event loop between each iteration.
    async for event in q:
        i += 1
        # We can index the page using any node we created and set its contents
        # to whatever we desire.
        page[target].set(str(i))
```
