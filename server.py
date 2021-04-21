#!/usr/bin/env python3

import flask
import requests
import logging
import json
import os

def getExitOnExceptionHandler():

    class ExitOnExceptionHandler(logging.StreamHandler):
        def emit(self, record):
            super().emit(record)
            if record.levelno is logging.CRITICAL:
                raise SystemExit(-1)

    exit_on_exception_handler = ExitOnExceptionHandler()
    exit_on_exception_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    return exit_on_exception_handler

class Config:
    
    def __init__(self):

        # config loader logger
        config_logger = logging.getLogger("config_loader")
        config_logger.addHandler(getExitOnExceptionHandler())

        # parse environment vars
        try:
            self.name = "quota_manager"
            self.quota_params_path = os.environ["QUOTA_PARAMS_FILE_PATH"]
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

class Global:
    config = Config()
    logger = logging.getLogger(config.name)
    app = flask.Flask(config.name)

# TODO
@Global.app.route("/projects", methods=["GET"])
def projects():
    return "", 500

# TODO
@Global.app.route("/quota", methods=["GET"])
def getQuota():
    return "", 500

# TODO
@Global.app.route("/quota", methods=["PUT"])
def setQuota():
    return "", 500

if __name__ == "__main__":
    Global.app.run()