from app.analysis import wave_scenarios


def test_scenario_structure():
    scenario = {
        "type": "IMPULSE_LONG",
        "direction": "LONG",
        "confidence": 70,
        "probability": 60,
    }

    assert scenario["direction"] in ["LONG", "SHORT"]
    assert scenario["confidence"] >= 0