
# Starbear

Starbear allow creating interactive local web applications in Python very easily.

* The entire app is a single async function.
* Call Python functions from JS, call JS functions from Python.
* No routes: starbear automatically creates the endpoints you need.

**Do not use this in production:** Starbear is not highly efficient and it leaks memory easily (because it would basically require a distributed garbage collector not to). Use this for small apps that you want to run locally or that don't need high uptime and reliability.

Also the error reporting is not the best right now. Check the developer console in your browser.


## Install

```bash
pip install starbear
```


## Simple Starbear app


```python
from hrepr import H
from pathlib import Path
from starbear import bear

@bear
async def app(page):
    page["head"].print(
        H.link(rel="stylesheet", href=Path("path/to/style.css"))
    )

    n = 0
    def increment(event):
        nonlocal n
        n += 1
        page[target].set(str(n))

    page.print(
        H.button("Click me!", onclick=increment),
        H.div(
            target := H.span("0").autoid(),
            " clicks"
        )
    )
```


## Queues

Set an event handler to a `starbear.Queue` and they will be queued up when they happen. You can then run an async loop over the elements in the queue.


```python
from hrepr import H
from pathlib import Path
from starbear import bear, Queue

@bear
async def app(page):
    q = Queue()
    page.print(
        H.button("Click me!", onclick=q),
        H.div(
            target := H.span("0").autoid(),
            " clicks"
        )
    )
    i = 0
    async for event in q:
        i += 1
        page[target].set(str(i))
```
