#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
    common elasticsearch database setup
    also adds defaults for most methods
"""

import sys
import logging
import certifi
from . import ponymailconfig

try:
    from elasticsearch import Elasticsearch, helpers, AsyncElasticsearch
    from elasticsearch import VERSION as ES_VERSION
    from elasticsearch import ConnectionError as ES_ConnectionError
except ImportError as e:
    sys.exit(
        "Sorry, you need to install the elasticsearch module from pip first. (%s)"
        % str(e)
    )


class Elastic:
    db_mbox:            str
    db_source:          str
    db_attachment:      str
    db_account:         str
    db_session:         str
    db_notification:    str
    db_auditlog:        str
    dbname:             str

    def __init__(self, logger_level=None, trace_level=None, is_async=False):
        # Fetch config
        config = ponymailconfig.PonymailConfig()

        # Set default names for all indices we use
        dbname = config.get('elasticsearch', 'dbname', fallback='ponymail')
        self.dbname = dbname
        self.db_mbox = dbname + '-mbox'
        self.db_source = dbname + '-source'
        self.db_account = dbname + '-account'
        self.db_attachment = dbname + '-attachment'
        self.db_session = dbname + '-session'
        self.db_notification = dbname + '-notification'
        self.db_auditlog = dbname + '-auditlog'
        self.db_version = 0
        self.db_distribution = None
        self.is_async = is_async

        dburl = config.get('elasticsearch', 'dburl', fallback=None)
        if not dburl:
            ssl = config.get('elasticsearch', 'ssl', fallback=False)
            uri = config.get('elasticsearch', 'uri', fallback='')
            auth = None
            if config.has_option('elasticsearch', 'user'):
                auth = (
                    config.get('elasticsearch', 'user'),
                    config.get('elasticsearch', 'password')
                )
            dburl = {
                "host": config.get('elasticsearch', 'hostname', fallback='localhost'),
                "port": config.get('elasticsearch', 'port', fallback=9200),
                "use_ssl": ssl,
                "url_prefix": uri,
                "auth": auth,
                "ca_certs": certifi.where(),
            }

        # Always allow this to be set; will be replaced as necessary by wait_for_active_shards
        self.consistency = config.get("elasticsearch", "write", fallback="quorum")

        if logger_level:
            eslog = logging.getLogger("elasticsearch")
            eslog.setLevel(logger_level)
            eslog.addHandler(logging.StreamHandler())
        else:
            # elasticsearch logs lots of warnings on retries/connection failure
            logging.getLogger("elasticsearch").setLevel(logging.ERROR)

        if trace_level:
            trace = logging.getLogger("elasticsearch.trace")
            trace.setLevel(trace_level)
            trace.addHandler(logging.StreamHandler())
        if self.is_async:
            self.es = AsyncElasticsearch(
                [
                dburl
                ],
                max_retries=5,
                retry_on_timeout=True,
            )
        else:
            self.es = Elasticsearch(
                [
                    dburl
                ],
                max_retries=5,
                retry_on_timeout=True,
            )
            # This won't work with async, so for now we'll ignore it there...
            es_engine_major = self.engineMajor()
            # OpenSearch (any major) implements the ES 7.x API this client uses
            if es_engine_major in [7, 8] or self.engineDistribution() == "opensearch":
                self.wait_for_active_shards = config.get("elasticsearch", "wait", fallback=1)
            else:
                raise ValueError("Unexpected elasticsearch version ", es_engine_major)



        # Mimic ES hierarchy: es.indices.xyz()
        self.indices = _indices_wrap(self)

    # convert index type to index name
    def index_name(self, index):
        return self.dbname + "-" + index

    @staticmethod
    def libraryVersion():
        return ES_VERSION

    @staticmethod
    def libraryMajor():
        return ES_VERSION[0]

    def engineVersion(self):
        if not self.db_version:
            try:
                self.db_version = self.es.info()["version"]["number"]
            except ES_ConnectionError:
                # default if cannot connect; allows retry
                return "0.0.0"
        return self.db_version

    def engineMajor(self):
        return int(self.engineVersion().split(".")[0])

    def engineDistribution(self):
        if not self.db_distribution:
            try:
                self.db_distribution = self.es.info()["version"].get("distribution", "elasticsearch")
            except ES_ConnectionError:
                # default if cannot connect; allows retry
                return "unknown"
        return self.db_distribution

    def search(self, **kwargs):
        return self.es.search(**kwargs)

    def index(self, **kwargs):
        kwargs["wait_for_active_shards"] = self.wait_for_active_shards
        kwargs["doc_type"] = "_doc"
        return self.es.index(**kwargs)

    def create(self, **kwargs):
        return self.es.create(**kwargs)

    def info(self, **kwargs):
        return self.es.info(**kwargs)

    def update(self, **kwargs):
        return self.es.update(**kwargs)

    # TODO: is this used? Does it make sense for ES7 ?
    def scan(self, scroll="3m", size=100, **kwargs):
        return self.es.search(
            search_type="scan", size=size, scroll=scroll, **kwargs
        )

    def get(self, **kwargs):
        return self.es.get(**kwargs)

    def scroll(self, **kwargs):
        return self.es.scroll(**kwargs)

    def bulk(self, actions, **kwargs):
        return helpers.bulk(self.es, actions, **kwargs)

    def streaming_bulk(self, actions, **kwargs):
        return helpers.streaming_bulk(self.es, actions, **kwargs)

    def clear_scroll(self, *args, **kwargs):
        """
            Call this to release the scroll id and its resources

            It looks like the Python library already releases the SID
            if the caller scrolls to the end of the results, so only need to call this
            when terminating scrolling early.
        """
        return self.es.clear_scroll(*args, **kwargs)
class _indices_wrap:
    """
        Wrapper for the ES indices methods we use
    """

    def __init__(self, parent):
        self.es = parent.es

    def exists(self, *args, **kwargs):
        return self.es.indices.exists(*args, **kwargs)

    def create(self, *args, **kwargs):
        return self.es.indices.create(*args, **kwargs)

    def get_mapping(self, **kwargs):
        return self.es.indices.get_mapping(**kwargs)

    def put_mapping(self, **kwargs):
        return self.es.indices.put_mapping(**kwargs)
