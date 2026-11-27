"""Server files that must agree with each other.

The image's user and the server account that owns the secrets share one uid. The server account
is created by tickr-infra (ops/aws/web, variable service_uid); tickr-infra's CI compares that
value with this repo's web/Dockerfile, so here only the image side is checked.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_image_user_has_one_numeric_uid_and_gid():
    # The secrets file and the database password are mode 600, owned by the server's tickrweb
    # account, and bind-mounted into the app container: only the same uid can read them.
    dockerfile = (REPO / "web" / "Dockerfile").read_text()
    image_user = re.search(r"^USER (\d+):(\d+)$", dockerfile, re.MULTILINE)
    assert image_user is not None
    assert image_user.group(1) == image_user.group(2)
