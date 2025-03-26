import logging
import sys

from .application import main as application_main

logger = logging.getLogger(__name__)


def main() -> None:
    try:
        sys.exit(application_main())
    except Exception as e:
        logger.exception(str(e))
        raise


if __name__ == "__main__":
    main()
