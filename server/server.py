#!/usr/bin/env python3

import flask
import requests
import logging
import json
import os
import jsonschema
from kubernetes.utils.quantity import parse_quantity
from gevent.pywsgi import WSGIServer

def get_logger(name):

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

        # user object name validation
        username = \
        {
            "type": "string",
            "pattern": "^[^/%\s]+$"
        }

        # namespace name validation
        namespace = \
        {
            "type": "string",
            "pattern": "(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?"
        }

        def __init__(self, quota):

            # schema logger
            schema_logger = get_logger("schema")

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
        config_logger = get_logger("config-loader")

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
            self.dry_run_namespace = os.environ["DRY_RUN_NAMESPACE"]
            self.username_formatting = os.environ["USERNAME_FORMATTING"]
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

    def format_username(self, username):
        return self.username_formatting.format(username)

config = Config()
logger = get_logger(config.name)
app = flask.Flask(config.name)
public_routes = []

def abort(message, code):
    logger.debug(message)
    flask.abort(flask.make_response({ "message": message }, code ))

def api_request(method, uri, token=config.pod_token, json=None, contentType="application/json"):

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

def validate_params(request_args, args):

    # abort request if one of the args was not provided
    for arg in args:
        if arg not in request_args:
            abort("missing '{}' query parameter".format(arg), 400)

def validate_quota_manager(username, project=None):

    # fetch list of quota managers
    managers_list = api_request("GET",
                                "/apis/user.openshift.io/v1/groups/{}".format(config.quota_managers_group)).json()["users"]

    # make sure user can manage quota
    if type(managers_list) != list or username not in managers_list:
        abort("user '{}' is not allowed to manage project quota".format(username), 401)

    # make sure target namespace is managed
    if project != None and project not in get_project_list()["projects"]:
        abort("project '{}' is not managed".format(project), 400)

def get_project_list():

    # query API
    response = api_request( "GET",
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
    validate_params(flask.request.args, [ "token" ])

    # validate quota manager and optional project
    username = get_username(flask.request.args["token"])
    project = flask.request.args["project"] if "project" in flask.request.args else None
    validate_quota_manager(username, project=project)

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, PUT, POST'
    return response

def authorization_not_required(route):
    public_routes.append(route.__name__)
    return route

def get_username(token):

    # review user token
    review_result = api_request("POST",
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

def patch_quota(user_scheme, project, username, dry_run=False):

    # validate user quota scheme
    jsonschema.validate(instance=user_scheme, schema=config.schemas.quota)

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
        api_request("PATCH",
                    "/api/v1/namespaces/{}/resourcequotas/{}{}".format(project, patch["name"], "?dryRun=All" if dry_run else ""),
                    json=patch["data"],
                    contentType="application/strategic-merge-patch+json")
        if not dry_run:
            logger.info("user '{}' has updated the '{}' quota for project '{}': {}".format(username, patch["name"], project, patch["data"]["spec"]["hard"]))

@app.route("/username", methods=["GET"])
@authorization_not_required
def r_get_username():
    validate_params(flask.request.args, [ "token" ])
    return get_username(flask.request.args["token"]), 200

@app.route("/projects", methods=["GET"])
def r_get_projects():

    # return jsonified project names
    return flask.jsonify(get_project_list())

@app.route("/projects", methods=["POST"])
def r_post_projects():

    # disabled for now
    return "", 501

    # validate arguments
    validate_params(flask.request.args, [ "newproject", "admin" ])

    # ensure admin username and namespace name are valid
    try:
        jsonschema.validate(instance=flask.request.args["admin"], schema=config.schemas.username)
        jsonschema.validate(instance=flask.request.args["newproject"], schema=config.schemas.namespace)
    except jsonschema.ValidationError as error:
        abort("'{}' is invalid: {}".format(error.instance, error.message), 400)

    # helper variables
    user_name = get_username(flask.request.args["token"])
    admin_user_name = config.format_username(flask.request.args["admin"])
    new_project = flask.request.args["newproject"]

    # dry run project creation, then do actual creation if no errors occurred
    for dry_run in [
        True,
        False
    ]:

        # helper variables for current run
        run_project = config.dry_run_namespace if dry_run else new_project
        dry_run_query_param = "?dryRun=All" if dry_run else ""

        # as it turns out, you can't dryRun a projectRequest because OpenShift
        # therefore we only attempt creation when dryRun is false
        if not dry_run:

            # request project creation
            api_request("POST",
                        "/apis/project.openshift.io/v1/projectrequests",
                        json={
                            "kind": "ProjectRequest",
                            "apiVersion": "project.openshift.io/v1",
                            "metadata": {
                                "name": new_project
                            }
                        })

            logger.info("user '{}' has created a project called '{}'".format(user_name, new_project))

        # patch new project's quota
        try:
            patch_quota(flask.request.get_json(force=True), run_project, get_username(flask.request.args["token"]), dry_run=dry_run)
        except jsonschema.ValidationError as error:
            abort("user provided scheme is invalid: {}".format(error.message), 400)

        # label namespace with managed label
        api_request("PATCH",
                    "/api/v1/namespaces/{}{}".format( run_project, dry_run_query_param),
                    json={
                        "metadata": {
                            "labels": {
                                config.managed_project_label_name: config.managed_project_label_value
                            }
                        }
                    },
                    contentType="application/strategic-merge-patch+json")

        if not dry_run:
            logger.info("user '{}' has labeled project '{}' as managed".format(user_name, new_project))

        # assign admin to project
        api_request("POST",
                    "/apis/authorization.openshift.io/v1/namespaces/{}/rolebindings{}".format(run_project, dry_run_query_param),
                    json={
                        "kind": "RoleBinding",
                        "apiVersion": "authorization.openshift.io/v1",
                        "metadata": {
                            "name": "admin-{}".format(admin_user_name),
                            "namespace": run_project
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
                                "name": admin_user_name
                            }
                        ]
                    })

        if not dry_run:
            logger.info("user '{}' has assigned '{}' as admin of project '{}'".format(user_name, admin_user_name, new_project))

    return flask.jsonify({ "message": "project '{}' has been successfully created".format(new_project) }), 200

@app.route("/healthz", methods=["GET"])
@authorization_not_required
def healthz():
    return "OK", 200

@app.route("/scheme", methods=["GET"])
def r_get_scheme():
    return flask.jsonify(config.quota_scheme)

@app.route("/quota", methods=["GET"])
def r_get_quota():

    # validate arguments
    validate_params(flask.request.args, [ "project" ])

    # prepare project quota JSON to be returned
    project_quota = {}

    # iterate quota objects
    for quota_object_name in config.quota_scheme.keys():

        project_quota[quota_object_name] = {}

        # fetch quota object from project
        quota_object = api_request( "GET",
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
def r_put_quota():

    # validate arguments
    validate_params(flask.request.args, [ "project" ])

    # try patching quota
    try:
        patch_quota(flask.request.get_json(force=True), flask.request.args["project"], get_username(flask.request.args["token"]))
    except jsonschema.ValidationError as error:
        abort("user provided scheme is invalid: {}".format(error.message), 400)

    return flask.jsonify({ "message": "quota updated successfully for project '{}'".format(flask.request.args["project"]) }), 200

if __name__ == "__main__":
    listener = ( "0.0.0.0", 5000 )
    api_logger = get_logger("api")
    api_logger.info("listening on {}:{}".format(listener[0], listener[1]))
    WSGIServer(listener, app, log=api_logger).serve_forever()