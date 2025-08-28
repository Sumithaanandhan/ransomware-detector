# logger.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time, csv, argparse, os

class CSVLogger(FileSystemEventHandler):
    def __init__(self, out_csv):
        os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
        self.out_csv = out_csv
        self._fh = open(out_csv, "a", newline="")
        self._w = csv.writer(self._fh)

    def close(self): 
        try:
            self._fh.close()
        except:
            pass

    def _log(self, event_type, path):
        self._w.writerow([event_type, path, time.time()])
        self._fh.flush()

    def on_created(self, e): self._log("created", e.src_path)
    def on_modified(self, e): self._log("modified", e.src_path)
    def on_deleted(self, e): self._log("deleted", e.src_path)
    def on_moved(self, e):   self._log("moved", getattr(e, "src_path", ""))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="Folder to monitor")
    ap.add_argument("--out", default="data/normal_logs.csv")
    args = ap.parse_args()

    handler = CSVLogger(args.out)
    observer = Observer()
    observer.schedule(handler, args.path, recursive=True)
    observer.start()
    print(f"Logging events in {args.path} -> {args.out}. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
    handler.close()