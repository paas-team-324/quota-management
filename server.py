#!/usr/bin/env python3

import flask
import requests
import logging
import json
import os

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
        config_logger = getLogger("config_loader")

        # parse environment vars
        try:
            self.name = "quota_manager"
            self.quota_params_path = os.environ["QUOTA_PARAMS_FILE_PATH"]
            self.managed_project_label = os.environ["MANAGED_PROJECT_LABEL"]
        except KeyError as error:
            config_logger.critical("one of the environment variables is not defined: {}".format(error))

        # load quota parameters
        try:
            with open(self.quota_params_path) as quota_params_file:
                self.quota_params = json.loads(quota_params_file.read())
        except FileNotFoundError:
            config_logger.critical("quota parameters file not found at '{}'".format(self.quota_params_path))
        except json.JSONDecodeError as error:
            config_logger.critical("could not parse quota parameters JSON file at '{}': {}".format(self.quota_params_path, error))

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

    # error during the request itself
    except requests.RequestException as error:
        logger.error(error)
        flask.abort(500)

    # error received from the API
    except requests.HTTPError as error:
        logger.warn(error)
        flask.abort(error.response.status_code)

    return response

def validateRequest(request_args, args):

    # abort request if not one of the args was not provided
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

# TODO
@app.route("/quota", methods=["GET"])
def getQuota():
    return "", 500

# TODO
@app.route("/quota", methods=["PUT"])
def setQuota():
    return "", 500

if __name__ == "__main__":
    app.run()