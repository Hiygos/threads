"""Import the core from its single source, for the unit tests."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))

import threads_core  # noqa: E402,F401
