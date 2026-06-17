import logging

from config import load_config


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    load_config()
    print("Hello from python-directives!")


if __name__ == "__main__":
    main()
