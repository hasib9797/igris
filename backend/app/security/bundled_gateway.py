from __future__ import annotations

import base64


_BUNDLED_GATEWAY_URL = "aHR0cHM6Ly9pZ3Jpcy1haS1wdWNlLnZlcmNlbC5hcHA="
_BUNDLED_GATEWAY_SECRET = "N2Y2eTIyelRTMG1PUnJ5NmRYT0w0cld2eGVVaTg3"


def bundled_gateway_url() -> str:
    return base64.b64decode(_BUNDLED_GATEWAY_URL.encode("ascii")).decode("utf-8")


def bundled_gateway_secret() -> str:
    return base64.b64decode(_BUNDLED_GATEWAY_SECRET.encode("ascii")).decode("utf-8")
