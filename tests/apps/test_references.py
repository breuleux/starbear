from dataclasses import dataclass

from hrepr import H

from starbear import Queue, Reference, bear

from .utils import asset_getter

asset = asset_getter(__file__)


@dataclass
class Person:
    name: str
    job: str
    toggle: bool = True


people = [
    Person(name="Olivier", job="Programmer"),
    Person(name="Balthazar", job="Mage"),
    Person(name="Elizabeth", job="Queen"),
]


@bear
async def __app__(page):
    q = Queue()
    for person in people:
        page.print(
            H.div[person.name](
                H.div["toggle-area"](person.name, cls=[person.name]),
                H.button("Toggle", onclick=q.wrap(refs=True)),
                __ref=Reference(person),
            )
        )

    async for event in q:
        person = event.obj
        person.toggle = not person.toggle
        page[event.ref, ".toggle-area"].set(person.name if person.toggle else person.job)


def test_toggles(app):
    def check(name, expected):
        assert app.locator(f".{name} .toggle-area").inner_text() == expected

    check("Olivier", "Olivier")
    check("Balthazar", "Balthazar")
    check("Elizabeth", "Elizabeth")

    app.locator(".Balthazar button").click()
    check("Olivier", "Olivier")
    check("Balthazar", "Mage")
    check("Elizabeth", "Elizabeth")

    app.locator(".Balthazar button").click()
    check("Balthazar", "Balthazar")

    app.locator(".Olivier button").click()
    app.locator(".Balthazar button").click()
    app.locator(".Elizabeth button").click()
    check("Olivier", "Programmer")
    check("Balthazar", "Mage")
    check("Elizabeth", "Queen")
