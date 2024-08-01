from starbear import H, bear


@bear
async def __app__(page):
    """Planet Jupiter"""
    page.print(H.h1("JUPITER!"))
