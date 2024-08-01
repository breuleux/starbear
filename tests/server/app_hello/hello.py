from starbear import H, bear


@bear
async def __app__(page):
    page.print(H.h1("HELLO"))
