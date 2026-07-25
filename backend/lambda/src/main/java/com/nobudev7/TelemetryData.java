package com.nobudev7;

import java.time.ZonedDateTime;

/**
 * Generic telemetry data model representing a timestamped numeric value.
 */
public class TelemetryData {

    private final ZonedDateTime time;
    private final double value;

    public TelemetryData(ZonedDateTime time, double value) {
        this.time = time;
        this.value = value;
    }

    public ZonedDateTime getTime() {
        return time;
    }

    public double getValue() {
        return value;
    }
}
