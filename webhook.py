from flask import Flask, request, abort
import hmac
import hashlib
import os
import subprocess

app = Flask(__name__)

GITHUB_SECRET = 'your_github_secret_here'

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        # Verify the request signature
        signature = request.headers.get('X-Hub-Signature-256')
        if signature is None:
            abort(403)
        
        sha_name, signature = signature.split('=')
        if sha_name != 'sha256':
            abort(403)
        
        mac = hmac.new(bytes(GITHUB_SECRET, 'utf-8'), msg=request.data, digestmod=hashlib.sha256)
        if not hmac.compare_digest(mac.hexdigest(), signature):
            abort(403)

        # Pull the latest changes from GitHub
        subprocess.call(['git', 'pull'])

        # Stop the running script
        subprocess.call(['pkill', '-f', 'your_script.py'])

        # Restart the script
        subprocess.Popen(['python3', 'your_script.py'])

        return 'Success', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
