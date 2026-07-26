package com.nobudev7;

import org.junit.jupiter.api.Test;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.QueryRequest;
import software.amazon.awssdk.services.dynamodb.model.QueryResponse;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Integration test: fetches real telemetry from DynamoDB and renders chart PNGs
 * saved to the local filesystem (no S3 upload).
 *
 * Combines the AWS connectivity of LocalTest with the local-file output of ChartGeneratorTest.
 *
 * Credentials and region are resolved by the SDK's DefaultCredentialsProvider chain
 * (env vars → ~/.aws/credentials → ~/.aws/config → EC2/ECS metadata).
 * If no credentials are found the test fails with SdkClientException.
 *
 * Run selectively:
 *   mvn test -Dtest=LocalChartRenderTest
 *   AWS_PROFILE=pilambdachart-dev mvn test -Dtest=LocalChartRenderTest
 *
 * Output files are written to: target/test-output/local-render/
 */
public class LocalChartRenderTest {

    private static final String OUTPUT_DIR   = "target/test-output/local-render";
    private static final String TELEMETRY_TABLE = envOrDefault("TELEMETRY_TABLE_NAME", "IoT_Telemetry");
    private static final ZoneId ZONE_ID      = ZoneId.of(envOrDefault("TEST_TIMEZONE", "America/New_York"));

    // ── Test cases ────────────────────────────────────────────────────────────

    @Test
    public void testRenderChart_Device1_Temperature() throws IOException {
        renderAndSave(1, 1, LocalDate.now(ZONE_ID), "XYLineChart",
                "Temperature (°C)", "device1-metric1-temperature.png");
    }

    @Test
    public void testRenderChart_Device1_Humidity() throws IOException {
        renderAndSave(1, 2, LocalDate.now(ZONE_ID), "XYLineChart",
                "Humidity (%)", "device1-metric2-humidity.png");
    }

    @Test
    public void testRenderChart_Device1_AmbientLight() throws IOException {
        renderAndSave(1, 3, LocalDate.now(ZONE_ID), "XYAreaChart",
                "Ambient Light (Lux)", "device1-metric3-light.png");
    }

    // ── Core render logic ─────────────────────────────────────────────────────

    /**
     * Fetches one full day of telemetry from DynamoDB for the given device + metric,
     * renders a chart PNG, and asserts the file was written successfully.
     *
     * @param deviceId   numeric device ID
     * @param metricId   numeric metric ID
     * @param date       local date to query (converted to UTC bounds)
     * @param chartType  "XYLineChart" or "XYAreaChart"
     * @param yAxisLabel Y-axis label shown on the chart
     * @param filename   output filename under target/test-output/local-render/
     */
    private void renderAndSave(int deviceId, int metricId, LocalDate date,
                                String chartType, String yAxisLabel,
                                String filename) throws IOException {

        Files.createDirectories(Paths.get(OUTPUT_DIR));

        // 1. Fetch real telemetry from DynamoDB
        List<TelemetryData> data = fetchTelemetry(deviceId, metricId, date);

        System.out.printf("Fetched %d data point(s) for Device=%d Metric=%d on %s%n",
                data.size(), deviceId, metricId, date);

        if (data.isEmpty()) {
            System.out.printf(
                "[SKIP] No data found for Device=%d Metric=%d on %s — " +
                "run the edge agent first to populate DynamoDB.%n",
                deviceId, metricId, date);
            return;  // Not a failure — the table may simply have no data for today yet
        }

        // 2. Render to a local PNG file (no S3 upload)
        String outputPath = OUTPUT_DIR + "/" + filename;
        String title = String.format("Device %d — %s on %s",
                deviceId, yAxisLabel, date.format(DateTimeFormatter.ofPattern("yyyy/MM/dd")));

        ChartGenerator generator = new ChartGenerator();
        generator.generateChart(data, title, yAxisLabel, chartType, metricId, outputPath);

        // 3. Assert the file was written and is non-empty
        File outputFile = new File(outputPath);
        assertTrue(outputFile.exists(),
                "Chart PNG should have been written to: " + outputPath);
        assertTrue(outputFile.length() > 0,
                "Chart PNG should not be empty");

        System.out.println("Chart saved to: " + outputFile.getAbsolutePath()
                + " (" + outputFile.length() + " bytes)");
    }

    // ── DynamoDB fetch ────────────────────────────────────────────────────────

    /**
     * Queries DynamoDB for one full day of telemetry using the same
     * UTC-bounded partition-key logic as ChartGeneratorHandler.
     * Handles year-rollover queries (e.g. querying Dec 31 in a non-UTC timezone).
     */
    private List<TelemetryData> fetchTelemetry(int deviceId, int metricId, LocalDate date) {
        try (DynamoDbClient db = DynamoDbClient.builder().build()) {

            ZonedDateTime startLocal = ZonedDateTime.of(date, LocalTime.MIN, ZONE_ID);
            ZonedDateTime endLocal   = ZonedDateTime.of(date, LocalTime.MAX, ZONE_ID);
            ZonedDateTime startUtc   = startLocal.withZoneSameInstant(ZoneId.of("UTC"));
            ZonedDateTime endUtc     = endLocal.withZoneSameInstant(ZoneId.of("UTC"));

            List<TelemetryData> all = new ArrayList<>();
            all.addAll(queryPartition(db, deviceId, metricId, startUtc.getYear(), startUtc, endUtc));

            // Merge a second partition if the local day spans a UTC year boundary
            if (startUtc.getYear() != endUtc.getYear()) {
                all.addAll(queryPartition(db, deviceId, metricId, endUtc.getYear(), startUtc, endUtc));
            }

            all.sort(Comparator.comparing(TelemetryData::getTime));
            return all;
        }
    }

    private List<TelemetryData> queryPartition(DynamoDbClient db,
                                                int deviceId, int metricId, int year,
                                                ZonedDateTime startUtc, ZonedDateTime endUtc) {
        String pk       = String.format("%d#%d#%d", deviceId, metricId, year);
        String startStr = startUtc.format(DateTimeFormatter.ISO_INSTANT);
        String endStr   = endUtc.format(DateTimeFormatter.ISO_INSTANT);

        System.out.printf("Querying DynamoDB: table=%s PK='%s' SK BETWEEN '%s' AND '%s'%n",
                TELEMETRY_TABLE, pk, startStr, endStr);

        QueryRequest request = QueryRequest.builder()
                .tableName(TELEMETRY_TABLE)
                .keyConditionExpression("Device_Metric_UTCYear = :pk AND #ts BETWEEN :start AND :end")
                .expressionAttributeNames(Map.of("#ts", "Timestamp"))
                .expressionAttributeValues(Map.of(
                        ":pk",    AttributeValue.builder().s(pk).build(),
                        ":start", AttributeValue.builder().s(startStr).build(),
                        ":end",   AttributeValue.builder().s(endStr).build()
                ))
                .build();

        QueryResponse response = db.query(request);

        return response.items().stream()
                .map(item -> {
                    ZonedDateTime time = Instant.parse(item.get("Timestamp").s()).atZone(ZONE_ID);
                    double value = Double.parseDouble(item.get("Value").n());
                    return new TelemetryData(time, value);
                })
                .collect(Collectors.toList());
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private static String envOrDefault(String key, String defaultValue) {
        String v = System.getenv(key);
        return (v != null && !v.isBlank()) ? v : defaultValue;
    }
}
