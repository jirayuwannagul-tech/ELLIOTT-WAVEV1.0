import sys
from dotenv import load_dotenv
load_dotenv()
from app.scheduler.daily_wave_scheduler import (
    start_scheduler_loop,
    run_daily_wave_job,
)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        print("Manual Run Mode...")
        run_daily_wave_job()
    else:
        start_scheduler_loop()