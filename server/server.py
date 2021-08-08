#!/usr/bin/env python3

import flask
import requests
import logging
import json
import os
import jsonschema
import re
from kubernetes.utils.quantity import parse_quantity
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

class Schemas:

        # list of valid quantity units
        _valid_units = [ "", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "n", "u", "m", "k", "M", "G", "T", "P", "E" ]

        # this is how a quota scheme should look like
        scheme_file = \
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
                            "units": {
                                "anyOf": [
                                    {
                                        "enum": _valid_units
                                    },
                                    {
                                        "type": "array",
                                        "minItems": 2,
                                        "uniqueItems": True,
                                        "items": { "enum": _valid_units }
                                    }
                                ]
                            },
                            "regex": { "type": "string" },
                            "regex_description": { "type": "string" }
                        }
                    }
                }
            }
        }

        def __init__(self, quota):

            # schema logger
            schema_logger = getLogger("schema")

            try:

                # validate against schema
                jsonschema.validate(instance=quota, schema=self.scheme_file)

            except jsonschema.ValidationError as error:
                schema_logger.critical("quota scheme file does not conform to schema: {}".format(error))

            schema_logger.info("quota scheme validated")

            # generate quota schema based on input
            self.quota = \
            {
                "type": "object",
                "additionalProperties": False,
                "required": [],
                "properties": {}
            }

            # iterate quota objects
            for quota_object_name in quota.keys():

                # set current quota object as required, forbid any other keys
                self.quota["required"].append(quota_object_name)
                self.quota["properties"][quota_object_name] = \
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {},
                }

                # iterate quota parameters
                for quota_parameter_name in quota[quota_object_name].keys():

                    valid_units = quota[quota_object_name][quota_parameter_name]["units"]

                    # set current 'hard' quota parameter as required, forbid any other keys
                    self.quota["properties"][quota_object_name]["required"].append(quota_parameter_name)
                    self.quota["properties"][quota_object_name]["properties"][quota_parameter_name] = \
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [ "value", "units" ],
                        "properties": {
                            "value": { "type": "string", "pattern": quota[quota_object_name][quota_parameter_name]["regex"] },
                            "units": { "type": "string", "enum": valid_units if isinstance(valid_units, list) else [ valid_units ] }
                        }
                    }

            schema_logger.info("user quota scheme generated")

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
            self.managed_project_label_name = os.environ["MANAGED_NAMESPACE_LABEL_NAME"]
            self.managed_project_label_value = os.environ["MANAGED_NAMESPACE_LABEL_VALUE"]
            self.quota_managers_group = os.environ["QUOTA_MANAGERS_GROUP"]
            self.namespace = os.environ["NAMESPACE"]
        except KeyError as error:
            config_logger.critical("one of the environment variables is not defined: {}".format(error))

        config_logger.info("environment variables parsed")

        # load quota scheme
        try:
            with open(self.quota_scheme_path, 'r') as quota_scheme_file:
                self.quota_scheme = json.loads(quota_scheme_file.read())

        except FileNotFoundError:
            config_logger.critical("quota scheme file not found at '{}'".format(self.quota_scheme_path))
        except json.JSONDecodeError as error:
            config_logger.critical("could not parse quota scheme JSON file at '{}': {}".format(self.quota_scheme_path, error))

        # generate schemas object
        self.schemas = Schemas(self.quota_scheme)

config = Config()
logger = getLogger(config.name)
app = flask.Flask(config.name)
public_routes = []

def abort(message, code):
    logger.debug(message)
    flask.abort(flask.make_response({ "message": message }, code ))

def apiRequest(method, uri, token=config.pod_token, json=None, contentType="application/json"):

    # make request
    try:
        response = requests.request(method, "https://kubernetes.default.svc" + uri, headers={
            "Authorization": "Bearer {}".format(token),
            "Content-Type": contentType,
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

    # fetch list of quota managers
    managers_list = apiRequest( "GET",
                                "/apis/user.openshift.io/v1/groups/{}".format(config.quota_managers_group)).json()["users"]

    # make sure user can manage quota
    if type(managers_list) != list or username not in managers_list:
        abort("user '{}' is not allowed to manage project quota".format(username), 401)

    # make sure target namespace is managed
    if project != None and project not in getProjectList()["projects"]:
        abort("project '{}' is not managed".format(project), 400)

def getProjectList():

    # query API
    response = apiRequest("GET",
                          "/api/v1/namespaces?labelSelector={}={}".format(config.managed_project_label_name, config.managed_project_label_value))

    # return project names
    return {
        "projects": [ namespace["metadata"]["name"] for namespace in response.json()["items"] ]
    }

@app.before_request
def check_authorization():

    # do not check public routes
    if flask.request.endpoint in public_routes:
        return

    # validate arguments
    validateParams(flask.request.args, [ "token" ])

    # validate quota manager and optional project
    username = getUsername(flask.request.args["token"])
    project = flask.request.args["project"] if "project" in flask.request.args else None
    validateQuotaManager(username, project=project)

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, PUT, POST'
    return response

def authorization_not_required(route):
    public_routes.append(route.__name__)
    return route

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

@app.route("/username", methods=["GET"])
@authorization_not_required
def getUsernameRoute():
    validateParams(flask.request.args, [ "token" ])
    return getUsername(flask.request.args["token"]), 200

@app.route("/projects", methods=["GET"])
def getProjects():

    # return jsonified project names
    return flask.jsonify(getProjectList())

@app.route("/projects", methods=["POST"])
def createProject():

    # validate arguments
    validateParams(flask.request.args, [ "newproject", "admin" ])

    # TODO try catch w message
    # get user quota scheme (throws 400 on error)
    user_scheme = flask.request.get_json(force=True)

    # ensure admin user conforms to regex

    # validate user quota scheme
    # try:
    #     jsonschema.validate(instance=user_scheme, schema=config.schemas.quota)
    # except jsonschema.ValidationError as error:
    #     abort("user provided scheme is invalid: {}".format(error.message), 400)

    for dry_run in [
        True
    ]:

        dry_run_project = config.namespace if dry_run else flask.request.args["newproject"]
        dry_run_query_param = "?dryRun=All" if dry_run else ""

        # as it turns out, you can't dryRun a projectRequest because OpenShift
        # therefore we only attempt creation when dryRun is false
        if not dry_run:

            # request project creation
            apiRequest( "POST",
                        "/apis/project.openshift.io/v1/projectrequests",
                        json={
                            "kind": "ProjectRequest",
                            "apiVersion": "project.openshift.io/v1",
                            "metadata": {
                                "name": flask.request.args["newproject"]
                            }
                        })

        # quota

        # label namespace with managed label
        apiRequest( "PATCH",
                    "/api/v1/namespaces/{}{}".format( dry_run_project, dry_run_query_param),
                    json={
                        "metadata": {
                            "labels": {
                                config.managed_project_label_name: config.managed_project_label_value
                            }
                        }
                    },
                    contentType="application/strategic-merge-patch+json")

        # assign admin to project
        apiRequest( "POST",
                    "/apis/authorization.openshift.io/v1/namespaces/{}/rolebindings{}".format(dry_run_project, dry_run_query_param),
                    json={
                        "kind": "RoleBinding",
                        "apiVersion": "authorization.openshift.io/v1",
                        "metadata": {
                            "name": "admin-{}".format(flask.request.args["admin"]),
                            "namespace": dry_run_project
                        },
                        "roleRef": {
                            "apiGroup": "rbac.authorization.k8s.io",
                            "kind": "ClusterRole",
                            "name": "admin"
                        },
                        "subjects": [
                            {
                                "apiGroup": "rbac.authorization.k8s.io",
                                "kind": "User",
                                "name": flask.request.args["admin"]
                            }
                        ]
                    })

    return flask.jsonify({ "message": "project '{}' has been successfully created".format(flask.request.args["project"]) }), 200

@app.route("/healthz", methods=["GET"])
@authorization_not_required
def healthz():
    return "OK", 200

@app.route("/scheme", methods=["GET"])
def getScheme():
    return flask.jsonify(config.quota_scheme)

@app.route("/quota", methods=["GET"])
def getQuota():

    # validate arguments
    validateParams(flask.request.args, [ "project" ])

    # prepare project quota JSON to be returned
    project_quota = {}

    # iterate quota objects
    for quota_object_name in config.quota_scheme.keys():

        project_quota[quota_object_name] = {}

        # fetch quota object from project
        quota_object = apiRequest(  "GET",
                                    "/api/v1/namespaces/{}/resourcequotas/{}".format(flask.request.args["project"], quota_object_name)).json()

        # iterate quota parameters
        for quota_parameter_name in config.quota_scheme[quota_object_name].keys():

            # get current value
            try:
                value_decimal = parse_quantity(quota_object["spec"]["hard"][quota_parameter_name])
            except KeyError:
                abort("quota parameter '{}' is not defined in '{}' resource quota in project '{}'".format(quota_parameter_name, quota_object_name, flask.request.args["project"]), 500)

            # get desired units
            config_units = config.quota_scheme[quota_object_name][quota_parameter_name]["units"]
            units = config_units[0] if isinstance(config_units, list) else config_units

            # convert to desired quantity based on units
            value_decimal /= parse_quantity("1{}".format(units))

            # strip trailing zeroes, format as float and set in return JSON
            project_quota[quota_object_name][quota_parameter_name] = {
                "value": '{:f}'.format(value_decimal.normalize()),
                "units": units
            }

    return flask.jsonify(project_quota), 200

@app.route("/quota", methods=["PUT"])
def setQuota():

    # validate arguments
    validateParams(flask.request.args, [ "project" ])

    # get username
    username = getUsername(flask.request.args["token"])

    # get user quota scheme (throws 400 on error)
    user_scheme = flask.request.get_json(force=True)

    # validate user quota scheme
    try:
        jsonschema.validate(instance=user_scheme, schema=config.schemas.quota)
    except jsonschema.ValidationError as error:
        abort("user provided scheme is invalid: {}".format(error.message), 400)

    patches = []
        
    # iterate quota objects
    for quota_object_name in config.quota_scheme.keys():

        parameters = {}

        # iterate quota parameters
        for quota_parameter_name in config.quota_scheme[quota_object_name].keys():

            # append parameter
            parameters[quota_parameter_name] = "{}{}".format(user_scheme[quota_object_name][quota_parameter_name]["value"], user_scheme[quota_object_name][quota_parameter_name]["units"])

        # build new patch object
        patches.append({
            "name": quota_object_name,
            "data": {
                "spec": {
                    "hard": parameters
                }
            }
        })

    # update each quota object separately
    for patch in patches:
        apiRequest( "PATCH",
                    "/api/v1/namespaces/{}/resourcequotas/{}".format(flask.request.args["project"], patch["name"]),
                    json=patch["data"],
                    contentType="application/strategic-merge-patch+json")
        logger.info("user '{}' has updated the following quota for project '{}': {}".format(username, flask.request.args["project"], patch))

    return flask.jsonify({ "message": "quota updated successfully for project '{}'".format(flask.request.args["project"]) }), 200

if __name__ == "__main__":
    listener = ( "0.0.0.0", 5000 )
    api_logger = getLogger("api")
    api_logger.info("listening on {}:{}".format(listener[0], listener[1]))
    WSGIServer(listener, app, log=api_logger).serve_forever()