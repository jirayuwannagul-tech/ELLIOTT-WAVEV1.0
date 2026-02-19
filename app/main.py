import sys
import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request
from app.scheduler.daily_wave_scheduler import run_daily_wave_job, run_trend_watch_job

app = Flask(__name__)

@app.route("/")
def health():
    return "OK", 200

@app.route("/trend-watch", methods=["POST"])
def trend_watch():
    run_trend_watch_job(min_conf=65.0)
    return "OK", 200

@app.route("/run-daily", methods=["POST"])
def run_daily():
    expected = (os.getenv("CRON_TOKEN") or "").strip()
    got = (request.headers.get("X-CRON-TOKEN") or "").strip()
    if expected and got != expected:
        return "FORBIDDEN", 403

    run_daily_wave_job()
    return "OK", 200

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        print("Manual Run Mode...")
        run_daily_wave_job()
    else:
        app.run(host="0.0.0.0", port=8080)