from climate_attention.live import _annotate_modis_ndvi_anomalies


def test_modis_ndvi_annotation_uses_uk_calendar_month_baseline():
    rows = [{"date": "2025-07-01", "value": 0.674}]

    result = _annotate_modis_ndvi_anomalies(rows)

    assert result[0]["baseline_start_year"] == 2001
    assert result[0]["baseline_end_year"] == 2020
    assert result[0]["anomaly"] is not None
    assert result[0]["standardized_anomaly"] is not None
    assert result[0]["metadata"]["anomaly_baseline"] == "calendar-month UK MODIS climatology"
