from __future__ import annotations

from copy import deepcopy

from uvicorn.config import LOGGING_CONFIG

ACCESS_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S %z"


def uvicorn_log_config() -> dict:
    config = deepcopy(LOGGING_CONFIG)
    config["formatters"]["default"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    config["formatters"]["default"]["datefmt"] = ACCESS_TIMESTAMP_FMT
    config["formatters"]["access"]["fmt"] = (
        '%(asctime)s %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    config["formatters"]["access"]["datefmt"] = ACCESS_TIMESTAMP_FMT
    return config
