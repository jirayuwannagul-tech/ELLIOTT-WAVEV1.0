import sys
from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from app.scheduler.daily_wave_scheduler import run_daily_wave_job

app = Flask(__name__)

@app.route("/")
def health():
    return "OK", 200


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        print("Manual Run Mode...")
        run_daily_wave_job()
    else:
        # Railway ต้องการ HTTP server สำหรับ healthcheck
        app.run(host="0.0.0.0", port=8080)