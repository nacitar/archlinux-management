import logging
import sys

from .application import main as application_main

# with our logging setup this suffix will suppress console output
logger_file_only = logging.getLogger(f"{__name__}.file_only")


def main() -> None:
    try:
        sys.exit(application_main())
    except Exception as e:
        logger_file_only.exception(e)
        raise


if __name__ == "__main__":
    main()
