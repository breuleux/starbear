from starbear import H, bear


@bear
async def __app__(page):
    """Planet Venus"""
    page.print(H.h1("VENUS!"))
