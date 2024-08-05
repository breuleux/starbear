from pathlib import Path


def asset_getter(file):
    here = Path(file)
    locations = [here.parent / "common_assets", here.parent / (here.stem + "_assets")]

    def get(name):
        for location in locations:
            candidate = location / name
            if candidate.exists():
                return candidate
        else:
            raise FileNotFoundError(name)

    return get
