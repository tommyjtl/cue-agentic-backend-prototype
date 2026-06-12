from cue_server.logging_config import ACCESS_TIMESTAMP_FMT, uvicorn_log_config


def test_uvicorn_log_config_includes_timestamps():
    config = uvicorn_log_config()
    assert "%(asctime)s" in config["formatters"]["access"]["fmt"]
    assert config["formatters"]["access"]["datefmt"] == ACCESS_TIMESTAMP_FMT
    assert "%(asctime)s" in config["formatters"]["default"]["fmt"]
