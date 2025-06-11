from flask import Flask, render_template, request, jsonify
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('preview.html')

@app.route('/verify', methods=['POST'])
def verify():
    data = request.json
    return jsonify({
        'success': True,
        'message': 'Verification application submitted successfully!'
    })

@app.route('/list', methods=['POST'])
def list_kamas():
    data = request.json
    return jsonify({
        'success': True,
        'message': 'Kamas listing created successfully!'
    })

if __name__ == '__main__':
    app.run(debug=True)
