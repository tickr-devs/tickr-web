"""Server files that must agree with each other (web/Dockerfile, ops/aws/web)."""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_image_user_is_the_server_account_that_owns_the_secrets():
    # The secrets file and the database password are mode 600, owned by the server's tickrweb
    # account, and bind-mounted into the app container: only the same uid can read them.
    dockerfile = (REPO / "web" / "Dockerfile").read_text()
    variables = (REPO / "ops" / "aws" / "web" / "variables.tf").read_text()
    image_user = re.search(r"^USER (\d+):(\d+)$", dockerfile, re.MULTILINE)
    service_uid = re.search(
        r'variable "service_uid" \{.*?default\s*=\s*(\d+)', variables, re.DOTALL
    )
    assert image_user is not None
    assert service_uid is not None
    assert image_user.group(1) == image_user.group(2) == service_uid.group(1)
