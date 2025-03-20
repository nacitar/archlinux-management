import logging

from .application import main

LOG = logging.getLogger(__name__)

if __name__ == "__main__":
    import sys

    try:
        sys.exit(main())
    except Exception as e:
        LOG.exception(str(e))
        raise
