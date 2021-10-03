#!/usr/bin/env python3

import flask
import requests
import logging
import json
import os
import jsonschema
from flask import g as request_context
from kubernetes.utils.quantity import parse_quantity
from gevent.pywsgi import WSGIServer, WSGIHandler
from werkzeug.exceptions import BadRequest

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
    log_handler.setFormatter(logging.Formatter('[%(asctime)s] - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(log_handler)

    return logger

class CustomWSGIHandler(WSGIHandler):

    def log_request(self):

        # do not log request for routes excluded from logging
        if self.path in [ route_to_path(route) for route in disable_logging_for_routes ]:
            return

        # log request as usual
        return super(CustomWSGIHandler, self).log_request()

    def format_request(self):

        # slightly edited version of the super method, minus the timestamp
        # original method can be seen here:
        # https://github.com/gevent/gevent/blob/4171bc513656d3916b8e4dfe4e8710431ab0d5d0/src/gevent/pywsgi.py#L910

        length = self.response_length or '-'
        if self.time_finish:
            delta = '%.6f' % (self.time_finish - self.time_start)
        else:
            delta = '-'
        client_address = self.client_address[0] if isinstance(self.client_address, tuple) else self.client_address
        return '%s - "%s" %s %s %s' % (
            client_address or '-',
            self.requestline or '',
            (self._orig_status or self.status or '000').split()[0],
            length,
            delta)

class Config:

    class _Schemas:

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
                "pattern": "^[a-z0-9]([-a-z0-9]*[a-z0-9])?$",
                "minLength": 2,
                "maxLength": 63
            }

            def __init__(self, name, quota):

                # schema logger
                schema_logger = get_logger(f"{name}-schema")

                try:

                    # validate against schema
                    jsonschema.validate(instance=quota, schema=self.scheme_file)

                except jsonschema.ValidationError as error:
                    schema_logger.critical(f"quota scheme file does not conform to schema: {error}")

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

    def __init__(self, name):

        # config loader logger
        config_logger = get_logger(f"{name}-config-loader")

        # read pod token
        pod_token_file_path = "/var/run/secrets/kubernetes.io/serviceaccount/token"
        try:
            with open(pod_token_file_path, 'r') as pod_token_file:
                self.pod_token = pod_token_file.read()
        except FileNotFoundError:
            config_logger.critical(f"pod token file not found at '{self.pod_token_file_path}'")

        # parse environment vars
        try:
            self.name = name
            self.oauth_endpoint = os.environ["OAUTH_ENDPOINT"]
            self.oauth_client_id = os.environ["OAUTH_CLIENT_ID"]
            self.quota_scheme_path = os.environ["QUOTA_SCHEME_FILE"]
            self.managed_project_label_name = os.environ["MANAGED_NAMESPACE_LABEL_NAME"]
            self.managed_project_label_value = os.environ["MANAGED_NAMESPACE_LABEL_VALUE"]
            self.quota_managers_group = os.environ["QUOTA_MANAGERS_GROUP"]
            self.username_formatting = os.environ["USERNAME_FORMATTING"]
        except KeyError as error:
            config_logger.critical(f"one of the environment variables is not defined: {error}")

        config_logger.info("environment variables parsed")

        # load quota scheme
        try:
            with open(self.quota_scheme_path, 'r') as quota_scheme_file:
                self.quota_scheme = json.loads(quota_scheme_file.read())

        except FileNotFoundError:
            config_logger.critical(f"quota scheme file not found at '{self.quota_scheme_path}'")
        except json.JSONDecodeError as error:
            config_logger.critical(f"could not parse quota scheme JSON file at '{self.quota_scheme_path}': {error}")

        # generate schemas object
        self.schemas = self._Schemas(config_logger.name, self.quota_scheme)

    def format_username(self, username):
        return self.username_formatting.format(username)

config = None
logger = None
app = flask.Flask(__name__, static_folder=None, template_folder='ui/templates')
disable_auth_for_routes = []
disable_logging_for_routes = []

def route_to_path(route):

    # iterate app rules map and return matching path
    for rule in app.url_map.iter_rules():
        if rule.endpoint == route:
            return rule.rule

    return None

def format_response(message):
    return { "message": message.capitalize() }

def abort(message, code):
    logger.debug(message)
    flask.abort(flask.make_response(format_response(message), code ))

def api_request(method, uri, params={}, json=None, contentType="application/json", dry_run=False):

    # make request
    try:
        response = requests.request(method, "https://kubernetes.default.svc" + uri, headers={
            "Authorization": f"Bearer {config.pod_token}",
            "Content-Type": contentType,
            "Accept": "application/json",
            "Connection": "close"
        }, verify="/var/run/secrets/kubernetes.io/serviceaccount/ca.crt", json=json, params={ **params, **( { "dryRun": "All" } if dry_run else {} ) })
        response.raise_for_status()

    # error received from the API
    except requests.exceptions.HTTPError as error:
        abort(error.response.json()['message'], 502)

    # error during the request itself
    except requests.exceptions.RequestException as error:
        logger.error(error)
        abort(error.strerror, 500)

    return response

def validate_params(request_args, args):

    # abort request if one of the args was not provided
    for arg in args:
        if arg not in request_args:
            abort(f"missing '{arg}' query parameter", 400)

def validate_quota_manager(username):

    # fetch list of quota managers
    managers_list = api_request("GET",
                                f"/apis/user.openshift.io/v1/groups/{config.quota_managers_group}").json()["users"]

    # make sure user can manage quota
    if type(managers_list) != list or username not in managers_list:
        abort(f"user '{username}' is not allowed to manage project quota", 401)

def validate_namespace(namespace):
    
    # make sure namespace has managed label
    if namespace not in get_project_list()["projects"]:
        abort(f"project '{namespace}' is not managed", 400)

def get_request_json(request):

    # try reading json body and take care of badrequest exception
    try:
        return request.get_json(force=True)
    except BadRequest:
        abort("invalid JSON data in request body", 400)

def get_project_list():

    # query API
    response = api_request( "GET",
                            "/api/v1/namespaces",
                            params={ "labelSelector": f"{config.managed_project_label_name}={config.managed_project_label_value}" })

    # return project names
    return {
        "projects": [ namespace["metadata"]["name"] for namespace in response.json()["items"] ]
    }

@app.before_request
def check_authorization():

    # do not check public routes
    if flask.request.endpoint in disable_auth_for_routes:
        return

    # make sure authentication token is present
    validate_params(flask.request.args, [ "token" ])

    # make sure user is a quota manager
    username = get_username(flask.request.args["token"])
    validate_quota_manager(username)

    # add quota manager's username to current request context
    request_context.username = username

@app.after_request
def after_request(response):
    # response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, PUT, POST'
    return response

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(error.original_exception)
    return flask.jsonify(format_response(error.description)), 500

def do_not_authorize(route):
    disable_auth_for_routes.append(route.__name__)
    return route

def do_not_log(route):
    disable_logging_for_routes.append(route.__name__)
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
    try:
        jsonschema.validate(instance=user_scheme, schema=config.schemas.quota)
    except jsonschema.ValidationError as error:
        abort(f"user provided scheme is invalid: {error.message}", 400)

    patches = []
        
    # iterate quota objects
    for quota_object_name in config.quota_scheme.keys():

        parameters = {}

        # iterate quota parameters
        for quota_parameter_name in config.quota_scheme[quota_object_name].keys():

            # append parameter
            parameters[quota_parameter_name] = f"{user_scheme[quota_object_name][quota_parameter_name]['value']}{user_scheme[quota_object_name][quota_parameter_name]['units']}"

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
                    f"/api/v1/namespaces/{project}/resourcequotas/{patch['name']}",
                    json=patch["data"],
                    contentType="application/strategic-merge-patch+json",
                    dry_run=dry_run)
        if not dry_run:
            logger.info(f"user '{username}' has updated the '{patch['name']}' quota for project '{project}': {patch['data']['spec']['hard']}")

# ========== UI ==========

@app.route("/static/<path:filename>", methods=["GET"])
@do_not_authorize
def r_get_static(filename):
    return flask.send_from_directory('ui/static', filename)

@app.route("/<any('',favicon.ico):element>", methods=["GET"])
@do_not_authorize
def r_get_ui(element):
    return flask.send_from_directory('ui', element or 'index.html')

@app.route("/env.js", methods=["GET"])
@do_not_authorize
def r_get_env():
    return flask.render_template('env.js', oauth_endpoint=config.oauth_endpoint, oauth_client_id=config.oauth_client_id)

# ========== API =========

@app.route("/validation/project", methods=["GET"])
def r_get_validation_project():
    return flask.jsonify(config.schemas.namespace)

@app.route("/validation/username", methods=["GET"])
def r_get_validation_username():
    return flask.jsonify(config.schemas.username)

@app.route("/username", methods=["GET"])
@do_not_authorize
def r_get_username():
    validate_params(flask.request.args, [ "token" ])
    return get_username(flask.request.args["token"]), 200

@app.route("/projects", methods=["GET"])
def r_get_projects():

    # return jsonified project names
    return flask.jsonify(get_project_list())

@app.route("/projects", methods=["POST"])
def r_post_projects():

    # validate arguments
    validate_params(flask.request.args, [ "project", "admin" ])

    # ensure admin username and namespace name are valid
    try:
        jsonschema.validate(instance=flask.request.args["admin"], schema=config.schemas.username)
        jsonschema.validate(instance=flask.request.args["project"], schema=config.schemas.namespace)
    except jsonschema.ValidationError as error:
        abort(f"'{error.instance}' is invalid: {error.message}", 400)

    # helper variables
    admin_user_name = config.format_username(flask.request.args["admin"])
    new_project = flask.request.args["project"]

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

    logger.info(f"user '{request_context.username}' has created a project called '{new_project}'")

    # patch new project's quota
    patch_quota(get_request_json(flask.request), new_project, request_context.username, dry_run=False)

    # label namespace with managed label
    api_request("PATCH",
                f"/api/v1/namespaces/{new_project}",
                json={
                    "metadata": {
                        "labels": {
                            config.managed_project_label_name: config.managed_project_label_value
                        }
                    }
                },
                contentType="application/strategic-merge-patch+json",
                dry_run=False)

    logger.info(f"user '{request_context.username}' has labeled project '{new_project}' as managed")

    # assign admin to project
    api_request("POST",
                f"/apis/authorization.openshift.io/v1/namespaces/{new_project}/rolebindings",
                dry_run=False,
                json={
                    "kind": "RoleBinding",
                    "apiVersion": "authorization.openshift.io/v1",
                    "metadata": {
                        "name": f"admin-{admin_user_name}",
                        "namespace": new_project
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

    logger.info(f"user '{request_context.username}' has assigned '{admin_user_name}' as admin of project '{new_project}'")

    return flask.jsonify(format_response(f"project '{new_project}' has been successfully created")), 200

@app.route("/healthz", methods=["GET"])
@do_not_authorize
@do_not_log
def healthz():
    return "OK", 200

@app.route("/scheme", methods=["GET"])
def r_get_scheme():
    return flask.jsonify(config.quota_scheme)

@app.route("/quota", methods=["GET"])
def r_get_quota():

    # validate arguments
    validate_params(flask.request.args, [ "project" ])

    # make sure project is managed
    validate_namespace(flask.request.args['project'])

    # prepare project quota JSON to be returned
    project_quota = {}

    # iterate quota objects
    for quota_object_name in config.quota_scheme.keys():

        project_quota[quota_object_name] = {}

        # fetch quota object from project
        quota_object = api_request( "GET",
                                    f"/api/v1/namespaces/{flask.request.args['project']}/resourcequotas/{quota_object_name}").json()

        # iterate quota parameters
        for quota_parameter_name in config.quota_scheme[quota_object_name].keys():

            # get current value
            try:
                value_decimal = parse_quantity(quota_object["spec"]["hard"][quota_parameter_name])
            except KeyError:
                abort(f"quota parameter '{quota_parameter_name}' is not defined in '{quota_object_name}' resource quota in project '{flask.request.args['project']}'", 502)

            # get desired units
            config_units = config.quota_scheme[quota_object_name][quota_parameter_name]["units"]
            units = config_units[0] if isinstance(config_units, list) else config_units

            # convert to desired quantity based on units
            value_decimal /= parse_quantity(f"1{units}")

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

    # make sure project is managed
    validate_namespace(flask.request.args['project'])

    # try patching quota
    patch_quota(get_request_json(flask.request), flask.request.args["project"], request_context.username)

    return flask.jsonify(format_response(f"quota updated successfully for project '{flask.request.args['project']}'")), 200

if __name__ == "__main__":

    # instantiate global objects
    config = Config("quota-manager")
    logger = get_logger(config.name)

    # WSGIServer related variables
    listener = ( "0.0.0.0", 5000 )
    api_logger = get_logger(f"{config.name}-api")

    # notify of specific endpoint behaviour
    api_logger.info(f"disabling authorization for the following endpoints: {[ route_to_path(route) for route in disable_auth_for_routes ]}")
    api_logger.info(f"disabling request logging for the following endpoints: {[ route_to_path(route) for route in disable_logging_for_routes ]}")

    # start server
    api_logger.info(f"listening on {listener[0]}:{listener[1]}")
    WSGIServer(listener, app, log=api_logger, handler_class=CustomWSGIHandler).serve_forever()