import logging
import sys

from .application import main as application_main

LOG = logging.getLogger(__name__)


def main() -> None:
    try:
        sys.exit(application_main())
    except Exception as e:
        LOG.exception(str(e))
        raise


if __name__ == "__main__":
    main()
