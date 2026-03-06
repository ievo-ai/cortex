"""Update version in cortex/version.py with CalVer timestamp."""

import datetime
from pathlib import Path

version = datetime.datetime.now(datetime.UTC).strftime("%Y.%m.%d.%H%M")[2:]

version_file = Path(__file__).parent.parent / "src" / "cortex" / "version.py"
version_file.write_text(f'"""Define the version of the cortex package."""\n\n__version__ = "{version}"\n')

print(f"Version updated to {version}")  # noqa: T201
