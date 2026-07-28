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

    @Test
    public void testGenerateChartWithMetadata_Success() throws IOException {
        List<TelemetryData> data = new ArrayList<>();
        ZonedDateTime start = ZonedDateTime.of(LocalDate.of(2026, 7, 27), java.time.LocalTime.MIDNIGHT, ZONE_ID);
        for (int h = 0; h < 12; h++) {
            data.add(new TelemetryData(start.plusHours(h), 22.0 + h));
        }

        ChartGenerator generator = new ChartGenerator();
        ChartGenerator.RenderResult result = generator.generateChartWithMetadata(
                data, "Device 1 - Temperature", "Temperature (°C)", "XYLineChart", 1, 1, "Temperature", "°C");

        assertNotNull(result, "RenderResult should not be null");
        assertTrue(result.getImageBytes().length > 0, "PNG image bytes should not be empty");
        assertNotNull(result.getJsonMetadata(), "JSON metadata should not be null");
        assertTrue(result.getJsonMetadata().contains("plotArea"), "Metadata JSON should contain plotArea");
        assertTrue(result.getJsonMetadata().contains("points"), "Metadata JSON should contain points");
    }

    @Test
    public void testGenerateSampleFrontendAssets() throws IOException {
        ChartGenerator generator = new ChartGenerator();
        ZonedDateTime start = ZonedDateTime.of(LocalDate.of(2026, 7, 26), java.time.LocalTime.MIDNIGHT, ZONE_ID);

        int deviceId = 2;
        int[] metricIds = {1, 2, 3, 4};
        String[] names = {"Temperature", "Humidity", "Ambient Light", "Motion Count"};
        String[] units = {"°C", "%", "Lux", "triggers/min"};
        String[] types = {"XYLineChart", "XYLineChart", "XYAreaChart", "XYAreaChart"};

        for (int i = 0; i < metricIds.length; i++) {
            int metId = metricIds[i];
            List<TelemetryData> data = new ArrayList<>();
            for (int h = 0; h < 24; h++) {
                double val = switch (metId) {
                    case 1 -> 20.0 + Math.sin(h * 0.4) * 4.0;
                    case 2 -> 50.0 + Math.cos(h * 0.3) * 10.0;
                    case 3 -> Math.max(0, Math.sin((h - 6) * 0.25) * 400.0);
                    case 4 -> Math.max(0, (h % 3 == 0 ? 5 + (h % 7) : 0));
                    default -> 10.0;
                };
                data.add(new TelemetryData(start.plusHours(h), Math.round(val * 10.0) / 10.0));
            }

            String dirPath = String.format("../../frontend/public/output/%d/%d/2026/07", deviceId, metId);
            Files.createDirectories(Paths.get(dirPath));
            String pngPath = String.format("%s/%d-20260726.png", dirPath, metId);
            String jsonPath = String.format("%s/%d-20260726.json", dirPath, metId);

            String title = String.format("Device %d — %s on 2026/07/26", deviceId, names[i]);
            String yLabel = units[i].isEmpty() ? names[i] : String.format("%s (%s)", names[i], units[i]);

            ChartGenerator.RenderResult res = generator.generateChartWithMetadata(
                    data, title, yLabel, types[i], deviceId, metId, names[i], units[i]);

            if (res != null) {
                Files.write(Paths.get(pngPath), res.getImageBytes());
                Files.writeString(Paths.get(jsonPath), res.getJsonMetadata(), java.nio.charset.StandardCharsets.UTF_8);
            }
        }
    }
}
