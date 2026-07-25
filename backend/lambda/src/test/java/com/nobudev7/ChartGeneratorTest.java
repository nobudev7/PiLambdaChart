package com.nobudev7;

import org.junit.jupiter.api.Test;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

public class ChartGeneratorTest {

    private static final String OUTPUT_DIR = "target/test-output";
    private static final ZoneId ZONE_ID = ZoneId.of("America/New_York");

    @Test
    public void testGenerateLineChart_Success() throws IOException {
        Path outputPath = Paths.get(OUTPUT_DIR);
        if (!Files.exists(outputPath)) {
            Files.createDirectories(outputPath);
        }

        List<TelemetryData> data = new ArrayList<>();
        ZonedDateTime start = ZonedDateTime.of(LocalDate.of(2026, 7, 19), java.time.LocalTime.MIDNIGHT, ZONE_ID);
        
        // Populate 24 hours of simulated hourly data
        for (int h = 0; h < 24; h++) {
            data.add(new TelemetryData(start.plusHours(h), 20.0 + Math.sin(h * 0.5) * 5.0));
        }

        ChartGenerator generator = new ChartGenerator();
        String outputPathStr = OUTPUT_DIR + "/test-line-chart.png";
        
        // Generate Line Chart for temperature (metricId 1)
        generator.generateChart(data, "Test Room Temperature", "Temperature (°C)", "XYLineChart", 1, outputPathStr);

        File outputFile = new File(outputPathStr);
        assertTrue(outputFile.exists(), "Output chart image should be generated");
        assertTrue(outputFile.length() > 0, "Output chart image should not be empty");
    }

    @Test
    public void testGenerateAreaChart_Success() throws IOException {
        Path outputPath = Paths.get(OUTPUT_DIR);
        if (!Files.exists(outputPath)) {
            Files.createDirectories(outputPath);
        }

        List<TelemetryData> data = new ArrayList<>();
        ZonedDateTime start = ZonedDateTime.of(LocalDate.of(2026, 7, 19), java.time.LocalTime.MIDNIGHT, ZONE_ID);
        
        // Populate data
        for (int h = 0; h < 24; h++) {
            data.add(new TelemetryData(start.plusHours(h), 10.0 + h * 0.5));
        }

        ChartGenerator generator = new ChartGenerator();
        String outputPathStr = OUTPUT_DIR + "/test-area-chart.png";
        
        // Generate Area Chart for water level (metricId 5)
        generator.generateChart(data, "Test Water Level", "Water Level (cm)", "XYAreaChart", 5, outputPathStr);

        File outputFile = new File(outputPathStr);
        assertTrue(outputFile.exists(), "Output area chart image should be generated");
        assertTrue(outputFile.length() > 0, "Output area chart image should not be empty");
    }

    @Test
    public void testEmptyData_ReturnsNull() throws IOException {
        ChartGenerator generator = new ChartGenerator();
        byte[] result = generator.generateChart(new ArrayList<>(), "Empty Chart", "Value", "XYLineChart", 1);
        assertNull(result, "Chart generation with empty dataset should return null");
    }
}
