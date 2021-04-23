#!/usr/bin/env python3

import flask
import requests
import logging
import json
import os
import jsonschema
from gevent.pywsgi import WSGIServer

def getLogger(name):

    class ExitOnExceptionHandler(logging.StreamHandler):
        def emit(self, record):
            super().emit(record)
            if record.levelno is logging.CRITICAL:
                raise SystemExit(-1)

    # set up handler with formatting
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
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

        config_logger.info("all environment variables parsed successfully")

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
                            "required": [ "name", "description", "units" ],
                            "properties": {
                                "name": { "type": "string" },
                                "description": { "type": "string" },
                                "units": { "type": "string" }
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

def apiRequest(method, uri, token):

    # make request
    try:
        response = requests.request(method, "https://kubernetes.default.svc" + uri, headers={
            "Authorization": "Bearer {}".format(token)
        }, verify="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")
        response.raise_for_status()

    # error received from the API
    except requests.exceptions.HTTPError as error:
        logger.debug(error)
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
            logger.error("'{}' argument was not provided".format(arg))
            flask.abort(400)

def getProjectList(token):

    # query API
    response = apiRequest("GET",
                          "/api/v1/namespaces?labelSelector={}".format(config.managed_project_label),
                          token)

    # return project names
    return {
        "projects": [ namespace["metadata"]["name"] for namespace in response.json()["items"] ]
    }

@app.route("/projects", methods=["GET"])
def getProjects():

    # validate arguments
    validateRequest(flask.request.args, [ "token" ])

    # return jsonified project names
    return flask.jsonify(getProjectList(flask.request.args["token"]))

@app.route("/scheme", methods=["GET"])
def getScheme():
    return flask.jsonify(config.quota_scheme)

# TODO
@app.route("/quota", methods=["GET"])
def getQuota():
    return "", 501

# TODO
@app.route("/quota", methods=["PUT"])
def setQuota():
    return "", 501

if __name__ == "__main__":
    listener = ( "0.0.0.0", 5000 )
    api_logger = getLogger("api")
    api_logger.info("listening on {}:{}".format(listener[0], listener[1]))
    WSGIServer(listener, app, log=api_logger).serve_forever()