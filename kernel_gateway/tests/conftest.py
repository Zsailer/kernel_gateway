# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
import asyncio
import importlib
import io
import logging
import os
import re
import shutil
import urllib.parse
from binascii import hexlify

import jupyter_core.paths

import nbformat
import tornado
import tornado.testing
from jupyter_server._version import version_info
from jupyter_server.auth import Authorizer
from jupyter_server.extension import serverextension
from kernel_gateway.gatewayapp import KernelGatewayApp
from jupyter_server.utils import url_path_join
from tornado.escape import url_escape
from tornado.httpclient import HTTPClientError
from tornado.websocket import WebSocketHandler
from traitlets.config import Config
import pytest

pytest_plugins = ["pytest_jupyter.jupyter_core", "pytest_jupyter.jupyter_server"]

#
# @pytest.fixture
# def jp_server_config():
#     """Allows tests to setup their specific configuration values."""
#     config = {}
#     return Config(config)


@pytest.fixture(scope="function")
def jp_configurable_serverapp(
    jp_nbconvert_templates,  # this fixture must preceed jp_environ
    jp_environ,
    jp_server_config,
    jp_argv,
    jp_http_port,
    jp_base_url,
    tmp_path,
    jp_root_dir,
    jp_logging_stream,
    jp_asyncio_loop,
    io_loop,
):
    """Starts a Jupyter Server instance based on
    the provided configuration values.
    The fixture is a factory; it can be called like
    a function inside a unit test. Here's a basic
    example of how use this fixture:

    .. code-block:: python

      def my_test(jp_configurable_serverapp):
         app = jp_configurable_serverapp(...)
         ...
    """
    KernelGatewayApp.clear_instance()

    def _configurable_serverapp(
        config=jp_server_config,
        base_url=jp_base_url,
        argv=jp_argv,
        environ=jp_environ,
        http_port=jp_http_port,
        tmp_path=tmp_path,
        io_loop=io_loop,
        root_dir=jp_root_dir,
        **kwargs,
    ):
        app = KernelGatewayApp.instance(
            # Set the log level to debug for testing purposes
            log_level="DEBUG",
            port=jp_http_port,
            port_retries=0,
            base_url=base_url,
            config=config,
            **kwargs,
        )
        app.init_signal = lambda: None
        app.log.propagate = True
        app.log.handlers = []
        # Initialize app without httpserver
        if jp_asyncio_loop.is_running():
            app.initialize(argv=argv, new_httpserver=False)
        else:

            async def initialize_app():
                app.initialize(argv=argv, new_httpserver=False)

            jp_asyncio_loop.run_until_complete(initialize_app())
        # Reroute all logging StreamHandlers away from stdin/stdout since pytest hijacks
        # these streams and closes them at unfortunate times.
        stream_handlers = [h for h in app.log.handlers if isinstance(h, logging.StreamHandler)]
        for handler in stream_handlers:
            handler.setStream(jp_logging_stream)
        app.log.propagate = True
        app.log.handlers = []
        app.start_app()
        return app

    return _configurable_serverapp


@pytest.fixture(autouse=True)
def jp_server_cleanup(jp_asyncio_loop):
    yield
    app: KernelGatewayApp = KernelGatewayApp.instance()
    try:
        jp_asyncio_loop.run_until_complete(app.async_shutdown())
    except (RuntimeError, SystemExit) as e:
        print("ignoring cleanup error", e)
    if hasattr(app, "kernel_manager"):
        app.kernel_manager.context.destroy()
    KernelGatewayApp.clear_instance()

#
# @pytest.fixture(autouse=True)
# def jp_server_cleanup(io_loop):
#     yield
#     app: ServerApp = ServerApp.instance()
#     loop = io_loop.asyncio_loop
#     loop.run_until_complete(app._cleanup())
#     ServerApp.clear_instance()


@pytest.fixture
def jp_auth_header(jp_serverapp):
    """Configures an authorization header using the token from the serverapp fixture."""
    # if not is_v2:
    #     return {"Authorization": f"token {jp_serverapp.token}"}
    # return {"Authorization": f"token {jp_serverapp.identity_provider.token}"}
    return {"Authorization": f"token FIXME"}


@pytest.fixture
def kg_delay():
    yield asyncio.sleep(1.0)
