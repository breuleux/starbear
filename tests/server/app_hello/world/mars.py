from starbear import H, bear


@bear
async def __app__(page):
    """Planet Mars"""
    page.print(H.h1("MARS!"))
