#!/opt/conda/bin/python3
import os
import sys
import json
import signal
import socket
import pymongo
import logging

from http.server import BaseHTTPRequestHandler, HTTPServer
from functools   import partial
from datetime    import datetime

import signal
import time

class GracefulKiller:
    def __init__(self, httpd, mongoClient):
        self.httpd = httpd
        self.mongoClient = mongoClient

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)
        signal.signal(signal.SIGINT, self.exit_gracefully)

    def exit_gracefully(self, *args):           
        logging.info("Stopping httpd...")
        self.httpd.server_close()
        logging.info("Done!")

        logging.info("Stopping mongoDB instance...")
        self.mongoClient.close()
        logging.info("Done!")

        sys.exit(0)

class S(BaseHTTPRequestHandler):
    def __init__(self, collections, allowed_paths, required_fields, field_datatypes, *args, **kwargs):
        self.collections = collections
        self.allowed_paths = allowed_paths
        self.required_fields = required_fields
        self.field_datatypes = field_datatypes

        # BaseHTTPRequestHandler calls do_GET **inside** __init__
        # So call super().__init__ after setting attributes.
        super().__init__(*args, **kwargs)
        
    def _response(self):
        self.send_header("Content-type", "text/html")
        self.end_headers()
           
    def _fail_response(self, response):
        self.send_response(response)
        self._response()

    def do_POST(self):
        # ---------------------------------------------------------------------
        # Look for specific requests
        # ---------------------------------------------------------------------
        if self.path not in self.allowed_paths:
            self._fail_response(403)
            error_msg = "POST Request to path `{}' not allowed".format(self.path)
            self.wfile.write(error_msg.encode("utf-8"))
            logging.error(error_msg)
            return
        
        # Parse request
        content_length = int(self.headers["Content-Length"])
        post_data      = self.rfile.read(content_length)

        # ---------------------------------------------------------------------
        # Load body into dictionary
        # ---------------------------------------------------------------------
        json_string = post_data.decode("utf-8").replace("'", "\"") # JSON expects double quotes
        try:
            request_json = json.loads(json_string)
        except:
            self._fail_response(400)
            error_msg = "POST Request body is not JSON"
            self.wfile.write(error_msg.encode("utf-8"))
            logging.error(error_msg)
            return
        
        # ---------------------------------------------------------------------
        # Check all keys are present that are required
        # ---------------------------------------------------------------------
        if not self.required_fields[self.path].issubset(request_json.keys()):
            self._fail_response(400)
            
            # Calculate the missing fields
            #  - The symmetric difference returns items not in BOTH sets
            #  - The intersection enures we only see missing items from the required_fields set
            missing_fields = self.required_fields[self.path[1:]].symmetric_difference(request_json.keys()).intersection(self.required_fields[self.path])
            error_msg = "JSON does not contain all required fields. Missing field(s): {}".format(missing_fields)
            self.wfile.write(error_msg.encode("utf-8"))
            logging.error(error_msg)
            return

        # ---------------------------------------------------------------------
        # Cast to datatypes for fields
        # ---------------------------------------------------------------------
        try:
            # For each field try and cast to the defined datatype
            for field in self.required_fields[self.path]:
                request_json.update({field : self.field_datatypes[self.path][field](request_json[field])})
        except:
            self._fail_response(400)
            error_msg = "JSON contains all required fields, but the datatypes are wrong"
            self.wfile.write(error_msg.encode("utf-8"))
            logging.error(error_msg)
            return
        
        # ---------------------------------------------------------------------
        # Check time string, and update JSON
        # ---------------------------------------------------------------------
        try:
            request_time = datetime.strptime(request_json["time"], "%Y-%m-%dT%H:%M:%SZ").replace(microsecond=0)
            request_json.update({"time" : request_time})
        except:
            self._fail_response(400)
            error_msg = "JSON time string is in the wrong format"
            self.wfile.write(error_msg.encode("utf-8"))
            logging.error(error_msg)
            return
        
        # ---------------------------------------------------------------------
        # Check ranges
        # ---------------------------------------------------------------------
        try:
            assert(request_json["temperature"] >= -40 and request_json["temperature"] <= 85) # C
            assert(request_json["pressure"] >= 300 and request_json["pressure"] <= 1100)  # hPa (milibar)
            assert(request_json["humidity"] >= 0 and request_json["humidity"] <= 100)     # %
        except:
            self._fail_response(400)
            error_msg = "Sensor ranges outside operational range.\nTemperature: -40 -> 85 C ({} C)\nPressure: 300 -> 1100 hPa ({} hPa)\nHumidity: 0 -> 100 % ({} %)".format(request_json["temperature"], request_json["pressure"], request_json["humidity"])
            self.wfile.write(error_msg.encode("utf-8"))
            logging.error(error_msg)
            return
        
        # ---------------------------------------------------------------------
        # Save to mongoDB
        # ---------------------------------------------------------------------
        try:
            self.collections[self.path].insert_one(request_json)
        except:
            self._fail_response(500)
            error_msg = "Failed to save to mongoDB"
            self.wfile.write(error_msg.encode("utf-8"))
            logging.error(error_msg)
            return

        # ---------------------------------------------------------------------
        # Let the client know all is received OK
        # ---------------------------------------------------------------------
        self.send_response(200)
        self._response()
        self.wfile.write("OK".encode("utf-8"))

def run(http_port, mongo_data, allowed_paths, server_class=HTTPServer, handler_class=S):
    logging.basicConfig(filename=os.path.join("..", "log", "postReceiver.log"),
                        filemode="a",
                        format="[%(asctime)s] %(name)s %(levelname)s: %(message)s",
                        datefmt="%d-%b-%Y %H:%M:%S",
                        level=logging.INFO)
    
    # Write to stdout as well as the file
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    
    # -------------------------------------------------------------------------
    # Welcome the user
    # -------------------------------------------------------------------------
    logging.info("="*60)
    logging.info(" Hello, world! Starting at {}".format(datetime.now().strftime("%d-%b-%Y %H:%M:%S")))
    logging.info("  MongoDB IP:        {}:{}".format(mongo_data["address"], mongo_data["port"]))
    logging.info("  Listening on port: {}".format(http_port))
    logging.info("  POST Routes:       {}".format(allowed_paths))
    logging.info("="*60)
    
    # -------------------------------------------------------------------------
    # Open mongoDB and specific collection(s)
    # -------------------------------------------------------------------------
    logging.info("Connecting to mongoDB...")
    mongoClient     = pymongo.MongoClient(mongo_data["address"], mongo_data["port"])
    collections     = {"/loftBMEData" : mongoClient.sensors.loft}
    required_fields = {"/loftBMEData" : {"time", "temperature", "pressure", "humidity", "gas"}}
    field_datatypes = {"/loftBMEData" : {"time" : str, "temperature" : float, "pressure" : float, "humidity" : float, "gas" : int}}
    logging.info("Done!")
    
    # -------------------------------------------------------------------------
    # Server definition
    # -------------------------------------------------------------------------
    server_address = ("", http_port)
    
    # Assign a partial application
    handler = partial(handler_class, collections, allowed_paths, required_fields, field_datatypes)
    httpd = server_class(server_address, handler)
    
    logging.info("Starting httpd...")
    
    # Catch kill signals
    GracefulKiller(httpd, mongoClient)

    httpd.serve_forever()
    
if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())
    from secrets import secrets
    # Add the POST route
    allowed_paths = []
    allowed_paths.append(secrets["post_server"]["path"])
    http_port     = secrets["post_server"]["port"]
    mongo_data    = secrets["mongo_server"] # contains "port" and "address" keys
    
    run(http_port, mongo_data, allowed_paths)
