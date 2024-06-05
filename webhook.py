from flask import Flask, request, abort
import hmac
import hashlib
import os
import subprocess
from dotenv import load_dotenv
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/hello', methods=['GET'])
def hello():
    return 'Hello, World!', 200

@app.route('/webhook', methods=['POST'])
def webhook():
    load_dotenv()
    GITHUB_SECRET = os.getenv('github_secret')
    app.logger.debug("Request received")
    app.logger.debug(request.headers)
    app.logger.debug(request.data)
    
    if request.method == 'POST':
        # Verify the request signature
        signature = request.headers.get('X-Hub-Signature-256')
        if signature is None:
            app.logger.error("No signature found.")
            abort(403)
        
        sha_name, signature = signature.split('=')
        if sha_name != 'sha256':
            app.logger.error("Signature method is not sha256.")
            abort(403)
        
        mac = hmac.new(bytes(GITHUB_SECRET, 'utf-8'), msg=request.data, digestmod=hashlib.sha256)
        if not hmac.compare_digest(mac.hexdigest(), signature):
            app.logger.error("Signature verification failed.")
            abort(403)

        app.logger.info("Signature verified successfully.")
        
        # Uncomment these lines if you want to perform the git pull and script restart
        # subprocess.call(['git', 'pull'])
        # subprocess.call(['pkill', '-f', 'funding_bot.py'])
        # subprocess.Popen(['python3', 'funding_bot.py'])

        return 'Success', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
