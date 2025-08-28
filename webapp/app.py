# webapp/app.py
from flask import Flask, render_template, jsonify, request
import threading, time, queue, os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import joblib

app = Flask(__name__)
alerts_q = queue.Queue()
observer = None
monitor_thread = None

# sliding window similar to detector
EVENT_KEYS = ("created","modified","deleted","moved")

class SlidingWindowCounter:
    def __init__(self, window_seconds=60):
        from collections import deque
        self.window = window_seconds
        self.events = {k: deque() for k in EVENT_KEYS}

    def add(self, event_key, ts):
        if event_key not in self.events: return
        dq = self.events[event_key]
        dq.append(ts)
        cutoff = ts - self.window
        while dq and dq[0] < cutoff:
            dq.popleft()

    def counts(self, now):
        cutoff = now - self.window
        for k in EVENT_KEYS:
            dq = self.events[k]
            while dq and dq[0] < cutoff:
                dq.popleft()
        return {k: len(self.events[k]) for k in EVENT_KEYS}

class FileMonitor(FileSystemEventHandler):
    def __init__(self, model=None, threshold=None, window_seconds=60, cooldown=5):
        self.counter = SlidingWindowCounter(window_seconds)
        self.model = model
        self.threshold = threshold or {"deleted":60, "moved":80}
        self.cooldown = cooldown
        self._last_alert = 0

    def _maybe_alert(self, features, path):
        now = time.time()
        rule_flag = any(features[k] >= self.threshold.get(k, float("inf")) for k in EVENT_KEYS)
        ml_flag = False
        if self.model is not None:
            try:
                pred = self.model.predict([[features["modified"], features["moved"], features["deleted"], features["created"]]])[0]
                ml_flag = int(pred) == 1
            except Exception as e:
                print("Model predict error:", e)

        if (rule_flag or ml_flag) and (now - self._last_alert > self.cooldown):
            self._last_alert = now
            alerts_q.put({
                "timestamp": now,
                "path": path,
                "features": features,
                "by_rule": bool(rule_flag),
                "by_model": bool(ml_flag)
            })

    def _handle(self, event, kind):
        now = time.time()
        self.counter.add(kind, now)
        features = self.counter.counts(now)
        path = getattr(event, "src_path", "") or getattr(event, "dest_path", "")
        self._maybe_alert(features, path)

    def on_created(self, event):  self._handle(event, "created")
    def on_modified(self, event): self._handle(event, "modified")
    def on_deleted(self, event):  self._handle(event, "deleted")
    def on_moved(self, event):    self._handle(event, "moved")

def load_model_path():
    # model at project/data/model.joblib (webapp folder is webapp/)
    root = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(root, "data", "model.joblib")
    return path if os.path.exists(path) else None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start", methods=["POST"])
def start_monitor():
    global observer
    if observer and observer.is_alive():
        return jsonify({"status":"already running"})
    content = request.get_json() or {}
    folder = content.get("folder", "./sandbox")
    window = content.get("window", 60)

    model_path = load_model_path()
    model = joblib.load(model_path) if model_path else None

    handler = FileMonitor(model=model, window_seconds=int(window))
    observer = Observer()
    observer.schedule(handler, folder, recursive=True)
    observer.start()
    return jsonify({"status": f"started on {folder}", "model_loaded": bool(model_path)})

@app.route("/stop", methods=["POST"])
def stop_monitor():
    global observer
    if observer:
        observer.stop()
        observer.join()
        observer = None
        return jsonify({"status":"stopped"})
    return jsonify({"status":"not running"})

@app.route("/alerts", methods=["GET"])
def get_alerts():
    out = []
    while not alerts_q.empty():
        out.append(alerts_q.get())
    return jsonify(out)

if __name__ == "__main__":
    app.run(debug=True)