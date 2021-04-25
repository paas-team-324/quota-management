#!/usr/bin/env python3

import flask
import requests
import logging
import json
import os
import jsonschema
import re
from gevent.pywsgi import WSGIServer

def getLogger(name):

    class ExitOnExceptionHandler(logging.StreamHandler):
        def emit(self, record):
            super().emit(record)
            if record.levelno is logging.CRITICAL:
                raise SystemExit(-1)

    # set up handler with formatting
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    log_handler = ExitOnExceptionHandler()
    log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(log_handler)

    return logger

class Config:
    
    def __init__(self):

        # config loader logger
        config_logger = getLogger("config-loader")

        # parse environment vars
        try:
            self.name = "quota-manager"
            self.quota_scheme_path = os.environ["QUOTA_SCHEME_FILE"]
            self.managed_project_label = os.environ["MANAGED_NAMESPACE_LABEL"]
        except KeyError as error:
            config_logger.critical("one of the environment variables is not defined: {}".format(error))

        config_logger.info("environment variables parsed")

        # load and validate quota scheme
        try:
            with open(self.quota_scheme_path) as quota_scheme_file:
                self.quota_scheme = json.loads(quota_scheme_file.read())

            # this is how a quota scheme should look like
            schema = \
            {
                "type": "object",
                "minProperties": 1,
                "additionalProperties": False,
                "patternProperties": {
                    "^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$": {
                        "type": "object",
                        "minProperties": 1,
                        "additionalProperties": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [ "name", "description", "units", "regex" ],
                            "properties": {
                                "name": { "type": "string" },
                                "description": { "type": "string" },
                                "units": { "type": "string" },
                                "regex": { "type": "string" }
                            }
                        }
                    }
                }
            }

            # validate against schema
            jsonschema.validate(instance=self.quota_scheme, schema=schema)

        except FileNotFoundError:
            config_logger.critical("quota scheme file not found at '{}'".format(self.quota_scheme_path))
        except json.JSONDecodeError as error:
            config_logger.critical("could not parse quota scheme JSON file at '{}': {}".format(self.quota_scheme_path, error))
        except jsonschema.ValidationError as error:
            config_logger.critical("quota scheme file does not conform to schema: {}".format(error))

        config_logger.info("quota scheme validated")

config = Config()
logger = getLogger(config.name)
app = flask.Flask(config.name)

def apiRequest(method, uri, token, json=None):

    # make request
    try:
        response = requests.request(method, "https://kubernetes.default.svc" + uri, headers={
            "Authorization": "Bearer {}".format(token),
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Connection": "close"
        }, verify="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt", json=json)
        response.raise_for_status()

    # error received from the API
    except requests.exceptions.HTTPError as error:
        logger.debug("{}: {}".format(error, error.response.text))
        flask.abort(error.response.status_code)

    # error during the request itself
    except requests.exceptions.RequestException as error:
        logger.error(error)
        flask.abort(500)

    return response

def validateRequest(request_args, args):

    # abort request if one of the args was not provided
    for arg in args:
        if arg not in request_args:
            logger.debug("'{}' argument was not provided".format(arg))
            return False

    return True

def getProjectList(token):

    # query API
    response = apiRequest("GET",
                          "/api/v1/namespaces?labelSelector={}".format(config.managed_project_label),
                          token)

    # return project names
    return {
        "projects": [ namespace["metadata"]["name"] for namespace in response.json()["items"] ]
    }

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

@app.route("/projects", methods=["GET"])
def getProjects():

    # validate arguments
    if not validateRequest(flask.request.args, [ "token" ]):
        flask.abort(400)

    # return jsonified project names
    return flask.jsonify(getProjectList(flask.request.args["token"]))

@app.route("/healthz", methods=["GET"])
def healthz():
    return "OK", 200

@app.route("/scheme", methods=["GET"])
def getScheme():
    return flask.jsonify(config.quota_scheme)

# TODO
@app.route("/quota", methods=["GET"])
def getQuota():
    return "", 501

@app.route("/quota", methods=["PUT"])
def setQuota():

    # validate arguments
    if not validateRequest(flask.request.args, [ "token", "project" ]):
        flask.abort(400)

    # get user quota scheme (throws 400 on error)
    user_scheme = flask.request.get_json(force=True)

    # make sure target namespace is managed
    if flask.request.args["project"] not in getProjectList(flask.request.args["token"])["projects"]:
        flask.abort(401)

    quotas = []

    try:
        
        # iterate quota objects
        for quota_object_name in config.quota_scheme.keys():

            parameters = {}

            # iterate quota parameters
            for quota_parameter_name in config.quota_scheme[quota_object_name].keys():

                # store value
                value = user_scheme[quota_object_name][quota_parameter_name]
                regex = config.quota_scheme[quota_object_name][quota_parameter_name]["regex"]

                # assert regex match and append units
                assert bool(re.match(regex, value)), "value '{}' for parameter '{}' does not match regex '{}'".format(value, quota_parameter_name, regex)
                parameters[quota_parameter_name] = "{}{}".format(value, config.quota_scheme[quota_object_name][quota_parameter_name]["units"])

            # build new quota object
            quotas.append({
                "apiVersion": "v1",
                "kind": "ResourceQuota",
                "metadata": {
                    "name": quota_object_name,
                    "namespace": flask.request.args["project"]
                },
                "spec": {
                    "hard": parameters
                }
            })

    except KeyError as error:
        logger.debug("key was not found in user provided scheme: {}".format(error))
        flask.abort(400)

    except (AssertionError, TypeError) as error:
        logger.debug("user provided scheme is invalid: {}".format(error))
        flask.abort(400)

    # update each quota object separately
    for quota in quotas:
        logger.info("attempting to update the following quota: {}".format(quota))
        apiRequest("PUT",
                    "/api/v1/namespaces/{}/resourcequotas/{}".format(flask.request.args["project"], quota["metadata"]["name"]),
                    flask.request.args["token"],
                    json=quota)

    return "", 200

if __name__ == "__main__":
    listener = ( "0.0.0.0", 5000 )
    api_logger = getLogger("api")
    api_logger.info("listening on {}:{}".format(listener[0], listener[1]))
    WSGIServer(listener, app, log=api_logger).serve_forever()