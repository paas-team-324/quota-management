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

        # read pod token
        pod_token_file_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        try:
            with open(pod_token_file_path, 'r') as pod_token_file:
                self.pod_token = pod_token_file.read()
        except FileNotFoundError:
            config_logger.critical("pod token file not found at '{}'".format(self.pod_token_file_path))

        # parse environment vars
        try:
            self.name = "quota-manager"
            self.quota_scheme_path = os.environ["QUOTA_SCHEME_FILE"]
            self.users_path = os.environ["USERS_FILE"]
            self.managed_project_label = os.environ["MANAGED_NAMESPACE_LABEL"]
        except KeyError as error:
            config_logger.critical("one of the environment variables is not defined: {}".format(error))

        config_logger.info("environment variables parsed")

        # load and validate quota scheme
        try:
            with open(self.quota_scheme_path, 'r') as quota_scheme_file:
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
                            "required": [ "name", "units", "regex", "regex_description" ],
                            "properties": {
                                "name": { "type": "string" },
                                "units": { "type": "string" },
                                "regex": { "type": "string" },
                                "regex_description": { "type": "string" }
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

        # load quota management users
        try:
            with open(self.users_path, 'r') as users_file:
                self.quota_users = json.loads(users_file.read())

            # users JSON file is just an array of strings
            schema = \
            {
                "type": "array",
                "additionalItems": False,
                "items": {
                    "type": "string"
                }
            }

            # validate against schema
            jsonschema.validate(instance=self.quota_users, schema=schema)

        except FileNotFoundError:
            config_logger.critical("quota users file not found at '{}'".format(self.users_path))
        except json.JSONDecodeError as error:
            config_logger.critical("could not parse quota users JSON file at '{}': {}".format(self.users_path, error))
        except jsonschema.ValidationError as error:
            config_logger.critical("quota users file does not conform to schema: {}".format(error))

        config_logger.info("quota management users file validated")

config = Config()
logger = getLogger(config.name)
app = flask.Flask(config.name)

def abort(message, code):
    logger.debug(message)
    flask.abort(flask.make_response({ "message": message }, code ))

def apiRequest(method, uri, token=config.pod_token, json=None):

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
        abort(error.response.json()['message'], error.response.status_code)

    # error during the request itself
    except requests.exceptions.RequestException as error:
        logger.error(error)
        abort(error.strerror, 500)

    return response

def validateParams(request_args, args):

    # abort request if one of the args was not provided
    for arg in args:
        if arg not in request_args:
            abort("missing '{}' query parameter".format(arg), 400)

def validateQuotaManager(username, project=None):

    # make sure user can manage quota
    if username not in config.quota_users:
        abort("user '{}' is not allowed to manage project quota".format(username), 401)

    # make sure target namespace is managed
    if project != None and project not in getProjectList()["projects"]:
        abort("project '{}' is not managed".format(project), 400)

def getProjectList():

    # query API
    response = apiRequest("GET",
                          "/api/v1/namespaces?labelSelector={}".format(config.managed_project_label))

    # return project names
    return {
        "projects": [ namespace["metadata"]["name"] for namespace in response.json()["items"] ]
    }

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, PUT'
    return response

def getUsername(token):

    # review user token
    review_result = apiRequest( "POST",
                                "/apis/authentication.k8s.io/v1/tokenreviews",
                                json=\
                                    {
                                        "kind": "TokenReview",
                                        "apiVersion": "authentication.k8s.io/v1",
                                        "spec": {
                                            "token": token
                                        }
                                    }).json()

    # return username from review
    try:
        return review_result["status"]["user"]["username"]
    except KeyError:
        abort("invalid user token", 400)

@app.route("/projects", methods=["GET"])
def getProjects():

    # validate arguments
    validateParams(flask.request.args, [ "token" ])

    # validate quota manager
    validateQuotaManager(getUsername(flask.request.args["token"]))

    # return jsonified project names
    return flask.jsonify(getProjectList())

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
    validateParams(flask.request.args, [ "token", "project" ])

    # get username and validate
    username = getUsername(flask.request.args["token"])
    validateQuotaManager(username, project=flask.request.args["project"])

    # get user quota scheme (throws 400 on error)
    user_scheme = flask.request.get_json(force=True)

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
        abort("key was not found in user provided scheme: {}".format(error), 400)

    except (AssertionError, TypeError) as error:
        abort("user provided scheme is invalid: {}".format(error), 400)

    # update each quota object separately
    for quota in quotas:
        apiRequest("PUT",
                    "/api/v1/namespaces/{}/resourcequotas/{}".format(flask.request.args["project"], quota["metadata"]["name"]),
                    json=quota)
        logger.info("user '{}' has updated the following quota: {}".format(username, quota))

    return flask.jsonify({ "message": "quota updated successfully for project '{}'".format(flask.request.args["project"]) }), 200

if __name__ == "__main__":
    listener = ( "0.0.0.0", 5000 )
    api_logger = getLogger("api")
    api_logger.info("listening on {}:{}".format(listener[0], listener[1]))
    WSGIServer(listener, app, log=api_logger).serve_forever()