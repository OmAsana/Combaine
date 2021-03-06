#!/usr/bin/env python
import json
import re
import yaml
import collections
import urllib

import msgpack

from tornado.httpclient import AsyncHTTPClient
from tornado.httpclient import HTTPError
from tornado.httputil import HTTPHeaders
from tornado.ioloop import IOLoop

from cocaine.futures import chain
from cocaine.worker import Worker
from cocaine.logging import Logger


from helpers import helpers_globals

LEVELS = ("INFO", "WARN", "CRIT", "OK")

STATUSES = {0: "OK",
            3: "INFO",
            1: "WARN",
            2: "CRIT"}

DEFAULT_HEADERS = HTTPHeaders({"User-Agent": "Yandex/CombaineClient"})
DEFAULT_AGGREGATOR_KWARGS = {"ignore_nodata": 1}

REVERSE_STATUSES = dict((v, k) for k, v in STATUSES.iteritems())

HTTP_CLIENT = AsyncHTTPClient()

CHECK_CHECK = "http://{juggler}/api/checks/has_check?host_name={host}&\
service_name={service}&do=1"

LIST_CHILD = "http://{juggler}/api/checks/children_tree?host_name={host}&\
service_name={service}&do=1"

ADD_CHECK = "http://{juggler}/api/checks/set_check?host_name={host}&\
service_name={service}&description={description}&\
aggregator_kwargs={aggregator_kwargs}&\
aggregator={aggregator}&do=1"

ADD_CHILD = "http://{juggler}/api/checks/add_child?host_name={host}&\
service_name={service}&child={child}:{service}&do=1"

ADD_METHOD = "http://{juggler}/api/checks/add_methods?host_name={host}&\
service_name={service}&methods_list={methods}&do=1"

EMIT_EVENT = "http://{juggler_frontend}/juggler-fcgi.py?status={level}&\
description={description}&service={service}&instance=&host={host}"

CHECK_FLAP = "http://{juggler}/api/checks/flap?host_name={host}&s\
ervice_name={service}&do=1"

REMOVE_FLAP = "http://{juggler}/api/checks/flap?host_name={host}&\
service_name={service}&do=1"

ADD_FLAP = "http://{juggler}/api/checks/set_flap?host_name={host}&\
service_name={service}&flap_time={flap_time}&stable_time={stable_time}&\
critical_time={critical_time}&do=1"

DEFAULT_FLAP_TIME = 0
DEFAULT_STABLE_TIME = 600
DEFAULT_CRITICAL_TIME = 1200

log = Logger()


def filtered_by_end(k, ends):
    return any((k.endswith(i) for i in ends))


def extract_condition(inp):
    # ToDo: optimize
    left = len(inp)
    for sym in ("<", ">", "=", "!"):
        pos = inp.find(sym)
        if pos != -1 and pos < left:
            left = pos
    return inp[:left], inp[left:]


def upper_dict(dict_object):
    return dict((k.upper(), v) for (k, v) in dict_object.iteritems())


class WrappedLogger(object):
    def __init__(self, extra, logger):
        self.extra = extra
        self.log = logger

    def debug(self, data):
        self.log.debug("%s %s" % (self.extra, data))

    def info(self, data):
        self.log.info("%s %s" % (self.extra, data))

    def warn(self, data):
        self.log.warn("%s %s" % (self.extra, data))

    def error(self, data):
        self.log.error("%s %s" % (self.extra, data))


class Juggler(object):

    pattern = re.compile(r"\${\s*([^}\s]*)\s*}")

    def __init__(self, **cfg):
        # uppercase all keys
        cfg = upper_dict(cfg)
        ID = cfg.get("ID", "dummyID")
        self.log = WrappedLogger(ID, log)
        for level in LEVELS:
            setattr(self, level, cfg.get(level, []))

        self.checkname = cfg['CHECKNAME']
        self.Aggregator = cfg['AGGREGATOR']
        self.Host = cfg['HOST']
        # ugly hack for changes juggler API:
        # &methods_list=GOLEM,SMS to &methods_list=GOLEM&methods_list=SMS
        placeholder = "&methods_list="
        self.Method = placeholder.join(cfg['METHOD'].split(","))
        self.description = cfg.get('DESCRIPTION', "no description")
        self.juggler_hosts = cfg['JUGGLER_HOSTS']
        self.juggler_frontend = cfg['JUGGLER_FRONTEND']
        self.aggregator_kwargs = json.dumps(cfg.get('AGGREGATOR_KWARGS',
                                                    DEFAULT_AGGREGATOR_KWARGS))
        self.subgroup_notendswith_filters = cfg.get('FILTERS', [])
        self.flap = cfg.get('FLAP', None)
        if self.flap is not None:
            self.flap["flap_time"] = self.flap.get("flap_time", DEFAULT_FLAP_TIME)
            self.flap["stable_time"] = self.flap.get("stable_time", DEFAULT_STABLE_TIME)
            self.flap["critical_time"] = self.flap.get("critical_time", DEFAULT_CRITICAL_TIME)

        self.variables = dict()
        variables = cfg.get("VARIABLES", None)
        if variables is not None:
            for var, expr in variables.iteritems():
                try:
                    self.variables[var] = eval(expr, None, helpers_globals)
                except Exception as err:
                    self.log.error("unable to eval a variable %s %s: %s"
                                   % (var, expr, str(err)))
        self.variables.update(helpers_globals)
        self.log.debug("available vars: %s" % str(self.variables))

    def Do(self, data):
        packed = collections.defaultdict(dict)
        for aggname, subgroups in data.iteritems():
            for subgroup, value in subgroups.iteritems():
                packed[subgroup][aggname] = value

        generated = ((k, v) for k, v in packed.iteritems() if not filtered_by_end(k, self.subgroup_notendswith_filters))
        for subgroup, value in generated:
            self.log.debug("Habdling subgroup %s" % subgroup)
            if self.check(value, subgroup, "CRIT"):
                self.log.debug("CRIT")
            elif self.check(value, subgroup, "WARN"):
                self.log.debug("WARN")
            elif self.check(value, subgroup, "INFO"):
                self.log.debug("INFO")
            elif self.check(value, subgroup, "OK"):
                self.log.debug("OK")
            else:
                self.log.debug("Send ok manually")
                IOLoop.current().add_callback(self.send_point,
                                              "%s-%s" % (self.Host, subgroup),
                                              REVERSE_STATUSES["OK"])
        return True

    def on_resp(self, resp):
        self.log.info("RESP %s" % resp.code)

    def check(self, data, subgroup, level):
        checks = getattr(self, level, [])
        if len(checks) == 0:
            return False

        # Checks are coupled with OR logic.
        # Point will be sent
        # if even one of expressions is evaluated as True
        for check in checks:
            try:
                # prepare evaluation string
                # move to a separate function
                code = check
                for key, value in data.iteritems():
                    code, _ = re.subn(r"\${%s}" % key, str(value), code)

                self.log.debug("After substitution in %s %s" % (check,
                                                                code))
                # evaluate code
                # TBD: make it safer!!!
                res = eval(code, None, self.variables)

                self.log.debug("Evaluated result: %s %s" % (check, res))

                # if res looks like True
                # send point and return True
                if res:
                    condition, limit = extract_condition(code)
                    try:
                        ev_cond = "%s %s" % (eval(condition, None, self.variables),
                                             limit)
                    except Exception as err:
                        ev_cond = "<placeholder> " + limit
                    IOLoop.current().add_callback(self.send_point,
                                                  "%s-%s" % (self.Host,
                                                             subgroup),
                                                  REVERSE_STATUSES[level],
                                                  ev_cond)
                    return True
            except SyntaxError as err:
                self.log.error("SyntaxError in expression %s" % code)
            except Exception as err:
                self.log.error(repr(err))
        return False

    @chain.source
    def send_point(self, name, status, trigger_description=None):
        if trigger_description is None:
            trigger_description = "no trigger description"

        params = {"host": name,
                  "service": urllib.quote(self.checkname),
                  "description": urllib.quote(trigger_description),
                  "level": STATUSES[status]}

        child = name
        yield self.add_check_if_need(child)

        success = 0
        for jhost in self.juggler_frontend:
            try:
                params["juggler_frontend"] = jhost
                url = EMIT_EVENT.format(**params)
                self.log.info("Send event %s" % url)
                yield HTTP_CLIENT.fetch(url, headers=DEFAULT_HEADERS)
            except HTTPError as err:
                self.log.error(str(err))
                continue
            else:
                self.log.info("Event to %s: OK" % jhost)
                success += 1

        self.log.info("Event has been sent to %d/%d"
                      % (success, len(self.juggler_frontend)))
        yield success

    @chain.source
    def add_check_if_need(self, host):
        params = {"host": self.Host,
                  "service": urllib.quote(self.checkname),
                  "description": urllib.quote(self.description),
                  "methods": self.Method,
                  "child": host,
                  "aggregator": self.Aggregator,
                  "aggregator_kwargs": self.aggregator_kwargs}

        # Add checks
        for jhost in self.juggler_hosts:
            try:
                self.log.info("Work with %s" % jhost)
                params["juggler"] = jhost
                #Check existnace of service
                url = CHECK_CHECK.format(**params)
                self.log.info("Check %s" % url)
                response = yield HTTP_CLIENT.fetch(url,
                                                   headers=DEFAULT_HEADERS)

                # check doesn't exist
                if response.body == "false":
                    url = ADD_CHECK.format(**params)
                    self.log.info("Add check %s" % url)
                    yield HTTP_CLIENT.fetch(url, headers=DEFAULT_HEADERS)

                    url = ADD_CHILD.format(**params)
                    self.log.info("Add child %s" % url)
                    yield HTTP_CLIENT.fetch(url, headers=DEFAULT_HEADERS)

                    url = ADD_METHOD.format(**params)
                    self.log.info("Add method %s" % url)
                    yield HTTP_CLIENT.fetch(url, headers=DEFAULT_HEADERS)

                elif response.body == "true":
                    # check exists, but existance of child must be checked
                    url = LIST_CHILD.format(**params)
                    try:
                        resp = yield HTTP_CLIENT.fetch(url,
                                                       headers=DEFAULT_HEADERS)
                        childs_status = json.loads(resp.body)
                        key = "{child}:{service}".format(**params)

                        self.log.info("checking existance of %s child" % key)
                        if key not in childs_status:
                            # there's no given child for the current check
                            url = ADD_CHILD.format(**params)
                            self.log.info("Add child"
                                          " %s as it does'n exist" % url)
                            yield HTTP_CLIENT.fetch(url,
                                                    headers=DEFAULT_HEADERS)
                    except HTTPError as err:
                        self.log.error("unable to fetch the information"
                                       " about childs %s" % str(err))
                        continue
                    except ValueError as err:
                        self.log.error("unable to decode the information"
                                       " about childs %s" % str(err))
                        continue
                    except Exception as err:
                        self.log.error("unknown error related with the"
                                       " info about childs %s" % str(err))
                        continue
                else:
                    self.log.error("unexpected reply from `has_check`: %s" % response.body)

                if self.flap is not None:
                    url = CHECK_FLAP.format(**params)
                    self.log.info("Check flap %s" % url)
                    res_flap = yield HTTP_CLIENT.fetch(url,
                                                       headers=DEFAULT_HEADERS)
                    if res_flap.body == "null":
                        self.flap["juggler"] = params["juggler"]
                        self.flap["host"] = params["host"]
                        self.flap["service"] = params["service"]
                        url = ADD_FLAP.format(**self.flap)
                        self.log.info("Add flap: %s" % url)
                        yield HTTP_CLIENT.fetch(url, headers=DEFAULT_HEADERS)
                        self.log.info("Flap has been added successfully")
            except HTTPError as err:
                self.log.error(str(err))
                continue
            except Exception as err:
                self.log.error(str(err))
            else:
                break

        yield True


class JConfig(object):
    config = None
    CONFIG_PATH = "/etc/combaine/juggler.yaml"

    @classmethod
    def get_config(cls):
        return cls.config or cls.load_cfg()

    @classmethod
    def load_cfg(cls):
        with open(cls.CONFIG_PATH, 'r') as f:
            cls.config = yaml.load(f)
        return cls.config


def send(request, response):
    try:
        raw = yield request.read()
        task = msgpack.unpackb(raw)
        log.info("%s" % str(task))
        ID = task.get("Id", "MissingID")
        hosts = JConfig.get_config()
        juggler_config = task['Config']
        juggler_config.update(hosts)
        juggler_config['id'] = ID
        jc = Juggler(**juggler_config)

        jc.Do(task["Data"])
    except Exception as err:
        log.error("%s %s" % (ID, str(err)))
    else:
        response.write("Jugler done")
        log.info("%s Done" % ID)
    finally:
        response.close()

if __name__ == "__main__":
    W = Worker()
    W.run({"send": send})
