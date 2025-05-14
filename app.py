from flask import Flask, jsonify, Response, request
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST, Histogram
import os
import json
import time

app = Flask(__name__)
counter = 0
checkpoint_file = os.getenv('CHECKPOINT_PATH', '/data/checkpoint.json')
env = os.getenv('ENVIRONMENT', 'dev')

# Prometheus metrics
prom_counter = Gauge('cell_counter', 'Gauge for Cell service', ['environment'])
checkpoint_counter = Counter('checkpoint_operations_total', 'Total number of checkpoint operations', ['environment'])
restore_counter = Counter('restore_operations_total', 'Total number of restore operations', ['environment'])
checkpoint_value_gauge = Gauge('checkpoint_counter_value', 'Counter value at checkpoint', ['environment'])
restore_value_gauge = Gauge('restore_counter_value', 'Counter value at restore', ['environment'])
endpoint_counter = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'http_status', 'environment'])
error_counter = Counter('http_errors_total', 'Total HTTP errors', ['endpoint', 'environment'])
request_latency = Histogram('http_request_latency_seconds', 'HTTP request latency in seconds', ['endpoint', 'environment'])

@app.before_request
def start_timer():
    request.start_time = time.time()

@app.after_request
def record_metrics(response):
    resp_time = time.time() - request.start_time
    endpoint = request.path
    method = request.method
    status = response.status_code

    prom_counter.labels(environment=env).set(counter)

    endpoint_counter.labels(method=method, endpoint=endpoint, http_status=status, environment=env).inc()

    if status >= 400:
        error_counter.labels(endpoint=endpoint, environment=env).inc()

    request_latency.labels(endpoint=endpoint, environment=env).observe(resp_time)

    return response

@app.route('/')
def index():
    global counter
    counter += 1
    prom_counter.labels(environment=env).set(counter)
    return jsonify({"counter": counter})

@app.route('/checkpoint', methods=['POST'])
def checkpoint():
    global counter
    try:
        with open(checkpoint_file, 'w') as f:
            json.dump({"counter": counter}, f)
            checkpoint_counter.labels(environment=env).inc()
            checkpoint_value_gauge.labels(environment=env).set(counter)
            prom_counter.labels(environment=env).set(counter)
        return jsonify({"status": "checkpoint saved", "counter": counter})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/restore', methods=['POST'])
def restore():
    global counter
    try:
        with open(checkpoint_file, 'r') as f:
            data = json.load(f)
            counter = data.get("counter", 0)
            restore_counter.labels(environment=env).inc()
            restore_value_gauge.labels(environment=env).set(counter)
            prom_counter.labels(environment=env).set(counter)
        return jsonify({"status": "restored", "counter": counter})
    except Exception as e:
        return jsonify({"status": "restore failed", "error": str(e)}), 500

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)