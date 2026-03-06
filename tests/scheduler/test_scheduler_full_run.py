from unittest.mock import patch

from app.scheduler.daily_wave_scheduler import run_daily_wave_job


@patch("app.scheduler.daily_wave_scheduler.analyze_symbol")
def test_scheduler_runs(mock_analyze):
    mock_analyze.return_value = {
        "symbol": "BTCUSDT",
        "scenarios": []
    }

    run_daily_wave_job()

    assert mock_analyze.called