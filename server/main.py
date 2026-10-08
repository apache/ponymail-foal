#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Apache Pony Mail, Codename Foal - A Python variant of Pony Mail"""
import argparse
import asyncio
import importlib
import json
import os
import sys
import traceback
import typing

import aiohttp.web
import yaml
import uuid

import plugins.background
import plugins.configuration
import plugins.database
import plugins.formdata
import plugins.offloader
import plugins.server
import plugins.session

from server_version import PONYMAIL_SERVER_VERSION
PONYMAIL_FOAL_VERSION = "0.1.0"


# Certain environments such as MinGW-w64 will not register as a TTY and uses buffered output.
# In such cases, we need to force a flush of each print, or nothing will show.
if not sys.stdout.buffer.isatty():
    import functools
    print = functools.partial(print, flush=True) # pylint: disable=redefined-builtin


class Server(plugins.server.BaseServer):
    """Main server class, responsible for handling requests and scheduling offloader threads """

    def _load_endpoint(self, subdir):
        for endpoint_file in sorted(os.listdir(subdir)):
            if endpoint_file.endswith(".py"):
                endpoint = endpoint_file[:-3]
                m = importlib.import_module(f"{subdir}.{endpoint}")
                if hasattr(m, "register"):
                    self.handlers[endpoint] = m.__getattribute__("register")(self)
                    print(f"Registered endpoint /api/{endpoint}")
                else:
                    print(
                        f"Could not find entry point 'register()' in {endpoint_file}, skipping!"
                    )

    def __init__(self, args: argparse.Namespace):
        print(
            "==== Apache Pony Mail (Foal v/%s ~%s) starting... ====" % (PONYMAIL_FOAL_VERSION, PONYMAIL_SERVER_VERSION)
        )
        # Load configuration
        yml = yaml.safe_load(open(args.config))
        self.config = plugins.configuration.Configuration(yml)
        self.data = plugins.configuration.InterData()
        self.handlers = dict()
        self.dbpool = asyncio.Queue()
        self.runners = plugins.offloader.ExecutorPool()
        self.server = None
        self.streamlock = asyncio.Lock()
        self.api_logger = None
        self.foal_version = PONYMAIL_FOAL_VERSION
        self.server_version = PONYMAIL_SERVER_VERSION
        self.stoppable = False # allow remote stop for tests
        self.background_event = asyncio.Event() # for background task to wait on

        # Make a pool of database connections for async queries
        pool_size = self.config.database.pool_size
        if pool_size < 1:
            raise ValueError(f"pool_size {pool_size} must be > 0")
        for _ in range(0, pool_size): # stop value is exclusive
            self.dbpool.put_nowait(plugins.database.Database(self.config.database))

        # Load each URL endpoint
        if args.testendpoints:
            print("** Loading additional testing endpoints **")
            self._load_endpoint("testendpoints")
            print()
        self._load_endpoint("endpoints")

        if args.logger:
            import logging
            es_logger = logging.getLogger('elasticsearch')
            es_logger.setLevel(args.logger)
            es_logger.addHandler(logging.StreamHandler())
        if args.trace:
            import logging
            es_trace_logger = logging.getLogger('elasticsearch.trace')
            es_trace_logger.setLevel(args.trace)
            es_trace_logger.addHandler(logging.StreamHandler())
        if args.apilog:
            import logging
            self.api_logger = logging.getLogger('ponymail.apilog')
            self.api_logger.setLevel(args.apilog)
            self.api_logger.addHandler(logging.StreamHandler())
        self.stoppable = args.stoppable
        self.refreshable = args.refreshable

    async def handle_request(
        self, request: aiohttp.web.BaseRequest
    ) -> typing.Union[aiohttp.web.Response, aiohttp.web.StreamResponse]:
        """Generic handler for all incoming HTTP requests"""

        # Define response headers first...
        headers = {
            "Server": "Apache Pony Mail (Foal/%s ~%s)" % (PONYMAIL_FOAL_VERSION, PONYMAIL_SERVER_VERSION),
        }

        if self.api_logger:
            self.api_logger.info(request.raw_path)

        # Figure out who is going to handle this request, if any
        # We are backwards compatible with the old Lua interface URLs
        body_type = "form"
        # Support URLs of form /api/handler/extra?query
        parts = request.path.split("/")
        if len(parts) < 3:
            return aiohttp.web.Response(
                headers=headers, status=404, text="API Endpoint not found!"
            )
        handler = parts[2]
        # handle test requests
        if self.stoppable and handler == 'stop':
            self.background_event.set()
            return aiohttp.web.Response(headers=headers, status=200, text='Stop requested\n')
        if self.refreshable and handler == 'refresh':
            await plugins.background.get_data(self)
            return aiohttp.web.Response(headers=headers, status=200, text='Refresh performed\n')

        if handler.endswith(".lua"):
            body_type = "form"
            handler = handler[:-4]
        if handler.endswith(".json"):
            body_type = "json"
            handler = handler[:-5]

        # Parse form data if any
        try:
            indata = await plugins.formdata.parse_formdata(body_type, request)
            if self.api_logger:
                self.api_logger.info(indata)
        except ValueError as e:
            return aiohttp.web.Response(headers=headers, status=400, text=str(e))

        # Find a handler, or 404
        if handler in self.handlers:
            session = await plugins.session.get_session(self, request)
            try:
                # Wait for endpoint response. This is typically JSON in case of success,
                # but could be an exception (that needs a traceback) OR
                # it could be a custom response, which we just pass along to the client.
                xhandler = self.handlers[handler]
                # Fail-safe: a session token is refused unless the endpoint explicitly allows it
                if session.token and not xhandler.token_allowed:
                    output = aiohttp.web.Response(
                        headers=headers, status=403, text="Session tokens cannot be used with this endpoint."
                    )
                elif isinstance(xhandler, plugins.server.StreamingEndpoint):
                    output = await xhandler.exec(self, request, session, indata)
                else:  # plugins.server.Endpoint
                    output = await xhandler.exec(self, session, indata)
                if session.database:
                    self.dbpool.put_nowait(session.database)
                    self.dbpool.task_done()
                    session.database = None
                if isinstance(output, aiohttp.web.Response) or isinstance(output, aiohttp.web.StreamResponse):
                    return output
                if output:
                    jsout = await self.runners.run(json.dumps, output, indent=2)
                    headers["content-type"] = "application/json"
                    headers["Content-Length"] = str(len(jsout))
                    return aiohttp.web.Response(headers=headers, status=200, text=jsout)
                return aiohttp.web.Response(
                    headers=headers, status=404, text="Content not found"
                )
            # If a handler hit an exception, we need to print that exception somewhere,
            # either to the web client or stderr:
            except Exception: # TODO: narrow exception
                if session.database:
                    self.dbpool.put_nowait(session.database)
                    self.dbpool.task_done()
                    session.database = None
                exc_type, exc_value, exc_traceback = sys.exc_info()
                err = "\n".join(
                    traceback.format_exception(exc_type, exc_value, exc_traceback)
                )
                # By default, we print the traceback to the user, for easy debugging.
                if self.config.ui.traceback:
                    return aiohttp.web.Response(
                        headers=headers, status=500, text="API error occurred: \n" + err
                    )
                # If client traceback is disabled, we print it to stderr instead, but leave an
                # error ID for the client to report back to the admin. Every line of the traceback
                # will have this error ID at the beginning of the line, for easy grepping.
                # We only need a short ID here, let's pick 18 chars.
                eid = str(uuid.uuid4())[:18]
                sys.stderr.write("API Endpoint %s got into trouble (%s): \n" % (request.path, eid))
                for line in err.split("\n"):
                    sys.stderr.write("%s: %s\n" % (eid, line))
                return aiohttp.web.Response(
                    headers=headers, status=500, text="API error occurred. The application journal will have "
                                                      "information. Error ID: %s" % eid
                )
        else:
            return aiohttp.web.Response(
                headers=headers, status=404, text="API Endpoint not found!"
            )

    async def server_loop(self):
        self.server = aiohttp.web.Server(self.handle_request)
        runner = aiohttp.web.ServerRunner(self.server)
        await runner.setup()
        site = aiohttp.web.TCPSite(
            runner, self.config.server.ip, self.config.server.port
        )
        await site.start()
        print(
            "==== Serving up Pony goodness at %s:%s ===="
            % (self.config.server.ip, self.config.server.port)
        )
        await plugins.background.run_tasks(self)
        await self.cleanup()
        await site.stop() # try to clean up

    async def cleanup(self):
        while not self.dbpool.empty():
            await self.dbpool.get_nowait().client.close()

    def run(self):
        # get_event_loop is deprecated in 3.10, but the replacment new_event_loop
        # does not seem to work properly in earlier versions
        if sys.version_info.minor < 10:
            loop = asyncio.get_event_loop()
        else:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.server_loop())
        except KeyboardInterrupt:
            self.background_event.set()
            loop.run_until_complete(self.cleanup())
        loop.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        help="Configuration file to load (default: ponymail.yaml)",
        default="ponymail.yaml",
    )
    parser.add_argument(
        "--logger",
        help="elasticsearch level (e.g. INFO or DEBUG)",
    )
    parser.add_argument(
        "--trace",
        help="elasticsearch.trace level (e.g. INFO or DEBUG)",
    )
    parser.add_argument(
        "--apilog",
        help="api log level (e.g. INFO or DEBUG)",
    )
    parser.add_argument(
        "--stoppable",
        action='store_true',
        help="Allow remote stop for testing",
    )
    parser.add_argument(
        "--refreshable",
        action='store_true',
        help="Allow remote refresh for testing",
    )
    parser.add_argument(
        "--testendpoints",
        action='store_true',
        help="Enable test endpoints",
    )
    cliargs = parser.parse_args()
    Server(cliargs).run()
