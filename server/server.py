#!/usr/bin/env python3

import flask
import requests
import logging
import json
import os
import jsonschema
import re
import shutil
import glob
import bisect
from datetime import datetime
from logging.handlers import RotatingFileHandler, BaseRotatingHandler
from flask import g as request_context
from kubernetes.utils.quantity import parse_quantity
from gevent.pywsgi import WSGIServer, WSGIHandler
from werkzeug.exceptions import BadRequest

# constants
QUOTA_LOGFORMATTER = logging.Formatter('[%(asctime)s] - %(name)s - %(levelname)s - %(message)s')
INFRA_PROJECTS_REGEX = r"(^openshift-|^kube-|^openshift$|^default$)"

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
    log_handler.setFormatter(QUOTA_LOGFORMATTER)
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

class QuotaLogFileHandler(RotatingFileHandler):

    def __init__(self, log_dir, maxBytes=(1024 * 1024), encoding=None):
        
        # slightly edited version of the super method
        # original method can be seen here:
        # https://github.com/python/cpython/blob/4560c7e605887fda3af63f8ce157abf94954d4d2/Lib/logging/handlers.py#L124

        self.originalFileName = os.path.join(log_dir, "quota.log")
        self.maxBytes = maxBytes
        self.setFormatter(QUOTA_LOGFORMATTER)

        self.free_disk_space()
        BaseRotatingHandler.__init__(self, self.get_new_filename(), 'a', encoding, False)

    def doRollover(self):
        
        # slightly edited version of the super method
        # original method can be seen here:
        # https://github.com/python/cpython/blob/4560c7e605887fda3af63f8ce157abf94954d4d2/Lib/logging/handlers.py#L158

        if self.stream:
            self.stream.close()
            self.stream = None

        # record is always logged to path stored in "baseFilename"
        # the original RotatingFileHandler would rename and therefore store current file aside
        # here we just overwrite the current "baseFilename" to the new file name
        self.baseFilename = self.get_new_filename()
        self.free_disk_space()

        self.stream = self._open()

    def get_new_filename(self):
        return f"{self.originalFileName}_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S-%f')}"

    def free_disk_space(self):

        # calculate max amount of log files
        total_disk_space, _, _ = shutil.disk_usage(os.path.dirname(self.originalFileName))
        maxFiles = int(total_disk_space / self.maxBytes) - 1
        
        # fetch all of the existing log files, sorted by creation time
        existing_log_files = sorted(glob.glob(f"{self.originalFileName}*"), key=os.path.getctime)

        # if max amount of log files reached - delete oldest log file
        while len(existing_log_files) >= maxFiles:

            if len(existing_log_files) == 0:
                raise Exception("not enough disk space for an additional log file")

            os.remove(existing_log_files.pop(0))

class Config:

    class Schema:

            # list of valid quantity units
            _valid_units = [ "", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "n", "u", "m", "k", "M", "G", "T", "P", "E" ]

            # cluster credentials file
            cluster_file = \
            {
                "type": "object",
                "additionalProperties": False,
                "required": [ "displayName", "api", "production", "scheme", "token" ],
                "properties": {
                    "displayName": { "type": "string" },
                    "api": { "type": "string" },
                    "production": { "type": "boolean" },
                    "scheme": { "type": "string" },
                    "token": { "type": "string" }
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

            # valid data types for quota params
            data_types = \
            {
                "int" : "^\\d+$",
                "float": "^\\d+(\\.\\d+)?$"
            }

            # this is how a quota scheme should look like
            scheme_file = \
            {

                "type": "object",
                "additionalProperties": False,
                "required": [ "labels", "quota" ],
                "properties": {
                    "labels": {
                        "type": "object",
                        "additionalProperties": False,
                        "patternProperties": { 
                            "^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9]){,63}$": { "type": "string" }
                        },
                    },
                    "quota": {
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
                                    "required": [ "name", "units", "type" ],
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
                                        "type": { "type": "string", "enum": list(data_types.keys()) },
                                    }
                                }
                            }
                        }
                    }
                }
            }

            def __init__(self, name, quota, quota_name):

                # schema logger
                schema_logger = get_logger(f"{name}-{quota_name}-schema")

                try:

                    # validate against schema
                    jsonschema.validate(instance=quota, schema=self.scheme_file)

                except jsonschema.ValidationError as error:
                    schema_logger.critical(f"quota scheme file does not conform to schema: {error}")

                schema_logger.info("quota scheme validated")

                # generate label schema based on input
                label_schema = \
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {}
                }

                # iterate label names
                for label_name in quota["labels"].keys():

                    # set current label as required, provide value constraints
                    label_schema["required"].append(label_name)
                    label_schema["properties"][label_name] = { "type": "string", "pattern": "^(([A-Za-z0-9][-A-Za-z0-9_.]*)?[A-Za-z0-9])?$" }

                # generate quota schema based on input
                quota_schema = \
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [],
                    "properties": {}
                }

                # iterate quota objects
                for quota_object_name in quota["quota"].keys():

                    # set current quota object as required, forbid any other keys
                    quota_schema["required"].append(quota_object_name)
                    quota_schema["properties"][quota_object_name] = \
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [],
                        "properties": {},
                    }

                    # iterate quota parameters
                    for quota_parameter_name in quota["quota"][quota_object_name].keys():

                        valid_units = quota["quota"][quota_object_name][quota_parameter_name]["units"]

                        # set current 'hard' quota parameter as required, forbid any other keys
                        quota_schema["properties"][quota_object_name]["required"].append(quota_parameter_name)
                        quota_schema["properties"][quota_object_name]["properties"][quota_parameter_name] = \
                        {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [ "value", "units" ],
                            "properties": {
                                "value": { "type": "string", "pattern":  self.data_types[quota["quota"][quota_object_name][quota_parameter_name]["type"]] },
                                "units": { "type": "string", "enum": valid_units if isinstance(valid_units, list) else [ valid_units ] }
                            }
                        }

                # combine schemas into a single user input validation schema
                self.quota_schema = \
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [ "labels", "quota" ],
                    "properties": {
                        "labels": label_schema,
                        "quota": quota_schema
                    }
                }

                # store original quota scheme
                self.quota = quota

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
            self.oauth_client_id = f'system:serviceaccount:{os.environ["SERVICEACCOUNT_NAMESPACE"]}:{os.environ["SERVICEACCOUNT_NAME"]}'
            self.quota_schemes_dir = os.environ["QUOTA_SCHEMES_DIR"]
            self.clusters_dir = os.environ["CLUSTERS_DIR"]
            self.quota_managers_group = os.environ["QUOTA_MANAGERS_GROUP"]
            self.insecure_requests = os.environ["INSECURE_REQUESTS"]
        except KeyError as error:
            config_logger.critical(f"one of the environment variables is not defined: {error}")

        config_logger.info("environment variables parsed")

        # ensure schemes dir exists
        if not os.path.exists(self.quota_schemes_dir):
            config_logger.critical(f"schemes directory is not present at '{self.quota_schemes_dir}'")

        # parse schemes
        self.schemes = {}
        for scheme in os.listdir(self.quota_schemes_dir):

            # ignore hidden files
            if not scheme.startswith("."):

                try:
                    with open(os.path.join(self.quota_schemes_dir, scheme)) as scheme_file:
                        
                        # read, validate and store
                        scheme_json = json.loads(scheme_file.read())
                        self.schemes[scheme] = self.Schema(config_logger.name, scheme_json, scheme)

                except json.JSONDecodeError as error:
                    config_logger.critical(f"could not parse '{scheme}' scheme file: {error}")

        config_logger.info(f"{len(self.schemes)} schemes registered")

        # ensure clusters dir exists
        if not os.path.exists(self.clusters_dir):
            config_logger.critical(f"clusters directory is not present at '{self.clusters_dir}'")

        # parse clusters
        self.clusters = {}
        for cluster in os.listdir(self.clusters_dir):

            # ignore hidden files
            if not cluster.startswith("."):

                try:
                    with open(os.path.join(self.clusters_dir, cluster)) as cluster_file:
                        
                        # read, validate
                        cluster_json = json.loads(cluster_file.read())
                        jsonschema.validate(instance=cluster_json, schema=self.Schema.cluster_file)

                        # make sure requested scheme is present
                        if cluster_json["scheme"] not in list(self.schemes.keys()):
                            config_logger.critical(f"'{cluster}' cluster file: '{cluster_json['scheme']}' scheme is not one of: {list(self.schemes.keys())}")

                        # store cluster
                        self.clusters[cluster] = cluster_json

                except json.JSONDecodeError as error:
                    config_logger.critical(f"could not parse '{cluster}' cluster file: {error}")
                except jsonschema.ValidationError as error:
                    config_logger.critical(f"'{cluster}' cluster file does not conform to schema: {error}")

        # make sure there is at least one cluster provided
        if len(self.clusters) < 1:
            config_logger.critical(f"no clusters were provided")

        config_logger.info(f"{len(self.clusters)} clusters registered")

        # parse insecure requests setting
        if self.insecure_requests.lower() == "true":
            config_logger.warning("running in insecure requests mode, remote cluster certificates won't be checked!")
            requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
            self.insecure_requests = True
        else:
            self.insecure_requests = False

        # get public authentication endpoint from cluster
        self.oauth_endpoint = self.api_request( "GET",
                                                "/.well-known/oauth-authorization-server",
                                                local=True).json()["authorization_endpoint"]

        config_logger.info("fetched authentication endpoint from cluster")

        # prepare general logger
        self.logger = get_logger(self.name)

        # configure persistent logging if specified
        if os.environ.get("LOG_STORAGE", default=False):

            quota_log_handler = QuotaLogFileHandler(os.environ["LOG_STORAGE"])
            quota_log_handler.setFormatter(QUOTA_LOGFORMATTER)
            self.logger.addHandler(quota_log_handler)

            config_logger.info(f"persistent logs configured to be stored in '{os.environ['LOG_STORAGE']}'")

    
    def api_request(self, method, uri, params={}, json=None, contentType="application/json", dry_run=False, local=False):

        # distinguish between local and remote request
        if local:
            api = "https://openshift.default.svc:443"
            token = self.pod_token
        else:
            api = self.clusters[request_context.cluster]['api']
            token = self.clusters[request_context.cluster]['token']

        # make request
        try:
            response = requests.request(method, api + uri, headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": contentType,
                "Accept": "application/json",
                "Connection": "close"
            },
            timeout=60,
            verify=(False if self.insecure_requests else "/etc/ssl/certs/ca-certificates.crt"),
            json=json,
            params={ **params, **( { "dryRun": "All" } if dry_run else {} ) })

            response.raise_for_status()

        # error received from the API
        except requests.exceptions.HTTPError as error:
            abort(error.response.json()['message'], 502)

        # error during the request itself
        except requests.exceptions.RequestException as error:
            self.logger.error(error)
            abort("an unexpected error has occurred", 500)

        return response


config = None
app = flask.Flask(__name__, static_folder=None, template_folder='../ui/templates')
disable_auth_for_routes = []
disable_logging_for_routes = []

def route_to_path(route):

    # iterate app rules map and return matching path
    for rule in app.url_map.iter_rules():
        if rule.endpoint == route:
            return rule.rule

    return None

def normalize_decimal(decimal):

    # strip trailing zeroes and format as float
    return '{:f}'.format(decimal.normalize())

def format_response(message):
    return { "message": message[0].upper() + message[1:] }

def abort(message, code):
    config.logger.debug(f"responded to client: {message}")
    flask.abort(flask.make_response(format_response(message), code ))

def validate_params(request_args, args):

    # abort request if one of the args was not provided
    for arg in args:
        if arg not in request_args:
            abort(f"missing '{arg}' parameter", 400)

def validate_quota_manager(username):

    # fetch list of quota managers
    managers_list = config.api_request( "GET",
                                        f"/apis/user.openshift.io/v1/groups/{config.quota_managers_group}", local=True).json()["users"]

    # make sure user can manage quota
    if type(managers_list) != list or username not in managers_list:
        abort(f"user '{username}' is not allowed to manage project quota", 401)

def validate_cluster(cluster):

    if cluster not in config.clusters.keys():
        abort(f"cluster '{cluster}' is not a valid cluster", 400)

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
    response = config.api_request(  "GET",
                                    "/api/v1/resourcequotas")

    # prepare unique list of projects with quota objects
    projects = []
    for resourcequota in response.json()["items"]:
        if resourcequota["metadata"]["namespace"] not in projects and not re.match(INFRA_PROJECTS_REGEX, resourcequota["metadata"]["namespace"]):
            projects.append(resourcequota["metadata"]["namespace"])

    # return project names
    return {
        "projects": projects
    }

def get_label_list():
    
    # query API
    response = config.api_request(  "GET",
                                    "/api/v1/namespaces")

    # init return value
    labels = { label:[] for label in request_context.cluster_quota_scheme["labels"].keys() }

    for namespace in response.json()["items"]:
        
        # filter infra projects
        if not re.match(INFRA_PROJECTS_REGEX, namespace["metadata"]["name"]):

            for label in request_context.cluster_quota_scheme["labels"].keys():

                # get label value from current namespace
                label_value = namespace["metadata"].get("labels", {}).get(label, "")

                # if value is valid and is not yet in the list
                if label_value and label_value not in labels[label]:
                    
                    # insert into list and keep it sorted
                    bisect.insort(labels[label], label_value)

    return labels

@app.before_request
def check_authorization():

    # do not check public routes
    if flask.request.endpoint in disable_auth_for_routes:
        return

    # make sure cluster query param present
    validate_params(flask.request.args, [ "cluster" ])

    # make sure authentication token header is present
    validate_params(flask.request.headers, [ "Token" ])

    # make sure user is a quota manager
    username = get_username(flask.request.headers["Token"])
    validate_quota_manager(username)

    # make sure cluster is valid
    cluster = flask.request.args["cluster"]
    validate_cluster(cluster)

    # add quota manager's username, cluster and cluster quota scheme shortcut to current request context
    request_context.username = username
    request_context.cluster = cluster
    request_context.cluster_quota_scheme = config.schemes[config.clusters[cluster]["scheme"]].quota

@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Methods'] = 'GET, PUT, POST'
    return response

@app.errorhandler(500)
def internal_server_error(error):
    config.logger.error(error.original_exception)
    return flask.jsonify(format_response(error.description)), 500

def do_not_authenticate(route):
    disable_auth_for_routes.append(route.__name__)
    return route

def do_not_log(route):
    disable_logging_for_routes.append(route.__name__)
    return route

def get_username(token):

    # review user token
    review_result = config.api_request( "POST",
                                        "/apis/authentication.k8s.io/v1/tokenreviews",
                                        local=True,
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

def get_quota(project):

    # fetch quota objects for given project
    quota_objects = config.api_request( "GET",
                                        f"/api/v1/namespaces/{project}/resourcequotas").json()

    return { quota_object['metadata']['name']:quota_object for quota_object in quota_objects['items'] }

def get_labels(project):

    # fetch namespace object
    namespace = config.api_request( "GET",
                                    f"/api/v1/namespaces/{project}").json()

    return { label:namespace["metadata"].get("labels", {}).get(label, "") for label in request_context.cluster_quota_scheme["labels"].keys() }

def patch_quota(user_scheme, project, username, dry_run=False):

    # validate user quota scheme
    try:
        jsonschema.validate(instance=user_scheme, schema=config.schemes[config.clusters[request_context.cluster]["scheme"]].quota_schema)
    except jsonschema.ValidationError as error:
        abort(f"user provided scheme is invalid: {error.message}", 400)

    # patch project namespace with labels (if labeling is enabled)
    if user_scheme["labels"]:

        config.api_request( "PATCH",
                            f"/api/v1/namespaces/{project}",
                            json=\
                            {
                                "metadata": {
                                    "labels": user_scheme["labels"]
                                }
                            },
                            contentType="application/strategic-merge-patch+json",
                            dry_run=dry_run)

        config.logger.info(f"user '{username}' has updated the labels for project '{project}' on cluster '{request_context.cluster}': '{user_scheme['labels']}'")

    # fetch quota objects for given project
    quota_objects = get_quota(project)

    patches = []
        
    # iterate quota objects
    for quota_object_name in request_context.cluster_quota_scheme["quota"].keys():

        parameters = {}

        # store currently used quota for current resource quota object
        quota_used = quota_objects[quota_object_name]['status']['used']

        # iterate quota parameters
        for quota_parameter_name in request_context.cluster_quota_scheme["quota"][quota_object_name].keys():

            # parameter might not exist in 'used' fields which might be a sign of misconfiguration of project template quota or quota scheme
            if quota_parameter_name in quota_used:
                used_value = quota_used[quota_parameter_name]
            else:
                config.logger.warning(f"'{quota_parameter_name}' not found in '.status.used' of '{quota_object_name}' resource quota object in project '{project}'")
                used_value = "0"

            used_value_decimal = parse_quantity(used_value)

            new_value = f"{user_scheme['quota'][quota_object_name][quota_parameter_name]['value']}{user_scheme['quota'][quota_object_name][quota_parameter_name]['units']}"

            # check if new quota value is smaller than currently used
            if parse_quantity(new_value).compare(used_value_decimal) == -1:
                abort(f"new '{ request_context.cluster_quota_scheme['quota'][quota_object_name][quota_parameter_name]['name']}' quota value is smaller than currently used - new: '{new_value}', used: '{normalize_decimal(used_value_decimal)}'", 400)

            # append parameter
            parameters[quota_parameter_name] = new_value

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
        config.api_request( "PATCH",
                            f"/api/v1/namespaces/{project}/resourcequotas/{patch['name']}",
                            json=patch["data"],
                            contentType="application/strategic-merge-patch+json",
                            dry_run=dry_run)
        if not dry_run:
            config.logger.info(f"user '{username}' has updated the '{patch['name']}' quota for project '{project}' on cluster '{request_context.cluster}': {patch['data']['spec']['hard']}")

# ========== UI ==========

@app.route("/static/<path:filename>", methods=["GET"])
@do_not_authenticate
def r_get_static(filename):
    return flask.send_from_directory('../ui/static', filename)

@app.route("/<any('',favicon.ico):element>", methods=["GET"])
@do_not_authenticate
def r_get_ui(element):
    return flask.send_from_directory('../ui', element or 'index.html')

@app.route("/env.js", methods=["GET"])
@do_not_authenticate
def r_get_env():
    return flask.Response(flask.render_template('env.js', oauth_endpoint=config.oauth_endpoint, oauth_client_id=config.oauth_client_id), mimetype="text/javascript")

# ========== API =========

@app.route("/validation/project", methods=["GET"])
def r_get_validation_project():
    return flask.jsonify(config.Schema.namespace)

@app.route("/validation/username", methods=["GET"])
def r_get_validation_username():
    return flask.jsonify(config.Schema.username)

@app.route("/validation/scheme", methods=["GET"])
def r_get_validation_quota():
    return flask.jsonify(config.schemes[config.clusters[request_context.cluster]["scheme"]].quota_schema)

@app.route("/username", methods=["GET"])
@do_not_authenticate
def r_get_username():
    validate_params(flask.request.headers, [ "Token" ])
    return get_username(flask.request.headers["Token"]), 200

@app.route("/clusters", methods=["GET"])
@do_not_authenticate
def r_get_clusters():

    # return jsonified cluster names with relevant info
    return { name: { 
                "displayName": cluster["displayName"],
                "production": cluster["production"]
            } for name, cluster in config.clusters.items() }

@app.route("/labels", methods=["GET"])
def r_get_labels():

    # return jsonified labels
    return flask.jsonify(get_label_list())

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
        jsonschema.validate(instance=flask.request.args["admin"], schema=config.Schema.username)
        jsonschema.validate(instance=flask.request.args["project"], schema=config.Schema.namespace)
    except jsonschema.ValidationError as error:
        abort(f"'{error.instance}' is invalid: {error.message}", 400)

    # helper variables
    admin_user_name = flask.request.args["admin"]
    new_project = flask.request.args["project"]

    # request project creation
    config.api_request( "POST",
                        "/apis/project.openshift.io/v1/projectrequests",
                        json={
                            "kind": "ProjectRequest",
                            "apiVersion": "project.openshift.io/v1",
                            "metadata": {
                                "name": new_project
                            }
                        })

    config.logger.info(f"user '{request_context.username}' has created a project called '{new_project}' on cluster '{request_context.cluster}'")

    # patch new project's quota
    patch_quota(get_request_json(flask.request), new_project, request_context.username, dry_run=False)

    # assign admin to project
    config.api_request( "POST",
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

    config.logger.info(f"user '{request_context.username}' has assigned '{admin_user_name}' as admin of project '{new_project}' on cluster '{request_context.cluster}'")

    return flask.jsonify(format_response(f"project '{new_project}' has been successfully created on cluster '{config.clusters[request_context.cluster]['displayName']}'")), 200

@app.route("/healthz", methods=["GET"])
@do_not_authenticate
@do_not_log
def healthz():
    return "OK", 200

@app.route("/scheme", methods=["GET"])
def r_get_scheme():
    return flask.jsonify(request_context.cluster_quota_scheme)

@app.route("/quota", methods=["GET"])
def r_get_quota():

    # validate arguments
    validate_params(flask.request.args, [ "project" ])

    # make sure project is managed
    validate_namespace(flask.request.args['project'])

    # fetch quota objects and labels for given project
    quota_objects = get_quota(flask.request.args['project'])
    labels = get_labels(flask.request.args['project'])

    # prepare project quota JSON to be returned
    project_quota = \
    {
        "labels": labels,
        "quota": {}
    }

    # iterate quota objects
    for quota_object_name in request_context.cluster_quota_scheme["quota"].keys():

        project_quota["quota"][quota_object_name] = {}

        # store current quota object
        quota_object = quota_objects[quota_object_name]

        # iterate quota parameters
        for quota_parameter_name in request_context.cluster_quota_scheme["quota"][quota_object_name].keys():

            # get current value
            try:
                value_decimal = parse_quantity(quota_object["spec"]["hard"][quota_parameter_name])
            except KeyError:
                abort(f"quota parameter '{quota_parameter_name}' is not defined in '{quota_object_name}' resource quota in project '{flask.request.args['project']}'", 502)

            # get desired units
            config_units = request_context.cluster_quota_scheme["quota"][quota_object_name][quota_parameter_name]["units"]
            units = config_units[0] if isinstance(config_units, list) else config_units

            # convert to desired quantity based on units
            value_decimal /= parse_quantity(f"1{units}")

            # strip trailing zeroes, format as float and set in return JSON
            project_quota["quota"][quota_object_name][quota_parameter_name] = {
                "value": normalize_decimal(value_decimal),
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

    return flask.jsonify(format_response(f"quota updated successfully for project '{flask.request.args['project']}' on cluster '{config.clusters[request_context.cluster]['displayName']}'")), 200

if __name__ == "__main__":

    # instantiate global objects
    config = Config("quota-manager")

    # disable dictionary sorting on flask.jsonify()
    # this way the quota scheme fields stay in the same order on client
    app.config['JSON_SORT_KEYS'] = False

    # WSGIServer related variables
    listener = ( "0.0.0.0", 5000 )
    api_logger = get_logger(f"{config.name}-api")

    # notify of specific endpoint behaviour
    api_logger.info(f"disabling authorization for the following endpoints: {[ route_to_path(route) for route in disable_auth_for_routes ]}")
    api_logger.info(f"disabling request logging for the following endpoints: {[ route_to_path(route) for route in disable_logging_for_routes ]}")

    # start server
    api_logger.info(f"listening on {listener[0]}:{listener[1]}")
    WSGIServer(listener, app, log=api_logger, handler_class=CustomWSGIHandler).serve_forever()