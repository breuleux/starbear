
# Starbear

[Documentation](https://breuleux.github.io/starbear)

Starbear allow creating interactive local web applications in Python very easily.

* The entire app is a single async function.
* Call Python functions from JS, call JS functions from Python.
* No subroutes: starbear automatically creates the endpoints you need.

**Do not use this in production:** Starbear is not highly efficient and it leaks memory easily (because it would basically require a distributed garbage collector not to). Use this for small apps that you want to run locally or that don't need high uptime and reliability.

Also the error reporting is not the best right now. Check the developer console in your browser.


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
    q = Queue()

    page["head"].print(
        H.title("Clicking game!"),
        H.link(rel="stylesheet", href=Path("path/to/style.css"))
    )

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

Unpacking the example:

1. The `app` function receives a `page` parameter that represents the app.
2. `page` can be indexed with any CSS selector to represent elements on the page.
3. We print a stylesheet to the `<head>` section of the page with `page["head"].print(...)`
  * `H.link` creates a `<link>` element.
  * By providing a `Path` object to `href`, Starbear will automatically make its parent directory available under a mangled route.
4. `page.print` appends an element to `<body>`.
5. `H.span(...).autoid()` creates a `span` with an auto-generated id. This will allow us to find and modify it later.
6. We pass a Queue to the `onclick` attribute of the button
7. We loop asynchronously on the queue to get the stream of clicks
8. `page[target].set` replaces the content of `target`, using the id that was auto-generated for it.
