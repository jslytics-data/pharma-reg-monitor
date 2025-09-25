import os
import logging

if "K_SERVICE" in os.environ:
    import google.cloud.logging
    client = google.cloud.logging.Client()
    client.setup_logging()
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

from flask import Flask, jsonify, request
from dotenv import load_dotenv

from src.manager import run_all_checks_and_notify

load_dotenv()
app = Flask(__name__)

@app.route("/")
def health_check():
    return jsonify({"status": "ok"}), 200

@app.route("/run-all-checks", methods=["POST"])
def trigger_all_checks():
    expected_api_key = os.environ.get("INTERNAL_API_KEY")
    provided_api_key = request.headers.get("X-API-Key")

    if not expected_api_key:
        logging.error("FATAL: INTERNAL_API_KEY is not configured on the server.")
        return jsonify({"status": "error", "message": "Internal server configuration error."}), 500

    if expected_api_key != provided_api_key:
        logging.warning("Unauthorized access attempt to /run-all-checks endpoint.")
        return jsonify({"status": "error", "message": "Forbidden: Invalid API Key."}), 403
    
    try:
        logging.info("Authorized request received. Starting PharmaReg monitor process.")
        success = run_all_checks_and_notify()
        
        if success:
            logging.info("Endpoint: Process completed successfully.")
            return jsonify({"status": "success", "message": "Process triggered and completed successfully."}), 200
        else:
            logging.error("Endpoint: Process was halted due to a failure. See logs for details.")
            return jsonify({"status": "error", "message": "Process halted due to an internal failure."}), 500
            
    except Exception as e:
        logging.critical(f"An unhandled exception occurred in the main process: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "An unexpected critical error occurred."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)