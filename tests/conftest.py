def pytest_addoption(parser):
    parser.addoption(
        "--reload-pause",
        action="store",
        default="0.5",
        type=float,
        help="How long to pause in reload tests",
    )
