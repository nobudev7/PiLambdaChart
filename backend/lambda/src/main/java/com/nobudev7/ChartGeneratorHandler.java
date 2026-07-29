package com.nobudev7;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.QueryRequest;
import software.amazon.awssdk.services.dynamodb.model.QueryResponse;
import software.amazon.awssdk.services.dynamodb.model.GetItemRequest;
import software.amazon.awssdk.services.dynamodb.model.GetItemResponse;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;

import java.io.InputStreamReader;
import java.lang.reflect.Type;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.stream.Collectors;

public class ChartGeneratorHandler implements RequestHandler<Map<String, Object>, String> {

    static {
        // Fix for "Fontconfig error: No writable cache directories" in AWS Lambda environment
        System.setProperty("user.home", "/tmp");
    }

    private final DynamoDbClient dynamoDbClient;
    private final S3Client s3Client;
    private final ChartGenerator chartGenerator;
    private final Gson gson;

    // Read AWS resource names from environment variables with defaults matching IaC
    private static final String TELEMETRY_TABLE = System.getenv("TELEMETRY_TABLE_NAME") != null 
            ? System.getenv("TELEMETRY_TABLE_NAME") : "IoT_Telemetry";
            
    private static final String METADATA_TABLE = System.getenv("METADATA_TABLE_NAME") != null 
            ? System.getenv("METADATA_TABLE_NAME") : "IoT_Metadata";
            
    private static final String BUCKET_NAME = System.getenv("S3_BUCKET_NAME") != null 
            ? System.getenv("S3_BUCKET_NAME") : "pilambdachart-charts";
            
    private static final String FILE_LIST_JSON_KEY = "output/file-list.json";
    private static final ZoneId DEFAULT_ZONE_ID = ZoneId.of("America/New_York");

    public ChartGeneratorHandler() {
        this.dynamoDbClient = DynamoDbClient.create();
        this.s3Client = S3Client.create();
        this.chartGenerator = new ChartGenerator();
        this.gson = new GsonBuilder().setPrettyPrinting().create();
    }

    // Constructor for testing with mock clients
    public ChartGeneratorHandler(DynamoDbClient dynamoDbClient, S3Client s3Client) {
        this.dynamoDbClient = dynamoDbClient;
        this.s3Client = s3Client;
        this.chartGenerator = new ChartGenerator();
        this.gson = new GsonBuilder().setPrettyPrinting().create();
    }

    @Override
    public String handleRequest(Map<String, Object> input, Context context) {
        int deviceId = 1;
        ZoneId zoneId = DEFAULT_ZONE_ID;
        LocalDate targetDate = null;

        // 1. Parse device_id, timezone, and target date
        if (input != null) {
            if (input.containsKey("device")) {
                deviceId = parseId(input.get("device"));
            } else if (input.containsKey("device_id")) {
                deviceId = parseId(input.get("device_id"));
            }
            
            if (input.containsKey("timezone")) {
                zoneId = ZoneId.of(String.valueOf(input.get("timezone")));
            } else if (input.containsKey("tz")) {
                zoneId = ZoneId.of(String.valueOf(input.get("tz")));
            }

            targetDate = LocalDate.now(zoneId);

            String dateVal = null;
            if (input.containsKey("date")) {
                dateVal = String.valueOf(input.get("date")).trim();
            } else if (input.containsKey("target")) {
                dateVal = String.valueOf(input.get("target")).trim();
            }

            if (dateVal != null && !dateVal.isEmpty()) {
                if ("today".equalsIgnoreCase(dateVal)) {
                    targetDate = LocalDate.now(zoneId);
                } else if ("yesterday".equalsIgnoreCase(dateVal)) {
                    targetDate = LocalDate.now(zoneId).minusDays(1);
                } else {
                    try {
                        targetDate = LocalDate.parse(dateVal);
                    } catch (Exception e) {
                        context.getLogger().log("Invalid date string '" + dateVal + "'. Expected YYYY-MM-DD, 'today', or 'yesterday'. Defaulting to today.");
                        targetDate = LocalDate.now(zoneId);
                    }
                }
            }
        } else {
            targetDate = LocalDate.now(zoneId);
        }

        List<Integer> metricIds = parseMetricIds(input);
        String dateStr = targetDate.format(DateTimeFormatter.ofPattern("yyyyMMdd"));

        context.getLogger().log(String.format("Starting batch chart generation for Device=%d, Metrics=%s, Date=%s, TZ=%s",
                deviceId, metricIds, dateStr, zoneId.getId()));

        try {
            // 2. Look up device metadata once
            Map<String, String> deviceMetadata = fetchMetadata("DEVICE", deviceId);
            String deviceName = deviceMetadata.getOrDefault("Name", "Device " + deviceId);

            // 3. Download existing file-list.json from S3 ONCE before batch processing
            TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> fileTree = loadFileListJson(context);

            int generatedCount = 0;
            int skippedCount = 0;

            // 4. Process each metric ID for this device
            for (int metricId : metricIds) {
                Map<String, String> metricMetadata = fetchMetadata("METRIC", metricId);

                String metricName = getFallbackMetricName(metricId, metricMetadata.getOrDefault("Name", "Metric " + metricId));
                String unit = getFallbackMetricUnit(metricId, metricMetadata.getOrDefault("Unit", ""));
                String chartType = metricMetadata.getOrDefault("ChartType", "XYLineChart");
                String icon = metricMetadata.getOrDefault("Icon", getFallbackMetricIcon(metricId));
                Double minYRange = null;
                if (metricMetadata.containsKey("MinYRange")) {
                    try {
                        minYRange = Double.parseDouble(metricMetadata.get("MinYRange"));
                    } catch (NumberFormatException ignored) {}
                }

                // Query DynamoDB for telemetry data
                List<TelemetryData> data = fetchTelemetryData(deviceId, metricId, targetDate, zoneId, context);
                if (data.isEmpty()) {
                    context.getLogger().log(String.format("No data found for Device=%d, Metric=%d (%s) on %s", deviceId, metricId, metricName, dateStr));
                    skippedCount++;
                    continue;
                }

                // Generate JFreeChart image bytes and JSON metadata sidecar
                String chartTitle = String.format("%s - %s on %s", deviceName, metricName, targetDate.format(DateTimeFormatter.ofPattern("yyyy/MM/dd")));
                String yAxisLabel = unit.isEmpty() ? metricName : String.format("%s (%s)", metricName, unit);

                ChartGenerator.RenderResult result = chartGenerator.generateChartWithMetadata(
                        data, chartTitle, yAxisLabel, chartType, deviceId, metricId, metricName, unit, minYRange, icon);
                if (result != null) {
                    // Upload PNG to S3
                    String s3Key = uploadToS3(result.getImageBytes(), deviceId, metricId, targetDate, dateStr, "image/png", ".png", context);
                    // Upload JSON sidecar to S3
                    uploadToS3(result.getJsonMetadata().getBytes(StandardCharsets.UTF_8),
                            deviceId, metricId, targetDate, dateStr, "application/json", ".json", context);
                    // Update in-memory fileTree
                    updateFileListInMemory(fileTree, deviceId, metricId, s3Key, targetDate);
                    generatedCount++;
                }
            }

            // 5. Upload updated file-list.json and metadata.json back to S3 ONCE after all metric charts are processed
            if (generatedCount > 0) {
                saveFileListJson(fileTree, context);
                exportMetadataJson(context);
            }

            String summary = String.format("Batch complete for Device %d on %s: %d chart(s) generated, %d skipped.",
                    deviceId, dateStr, generatedCount, skippedCount);
            context.getLogger().log(summary);
            return summary;

        } catch (Exception e) {
            context.getLogger().log("Error during batch handler execution: " + e.getMessage());
            e.printStackTrace();
            return "Error: " + e.getMessage();
        }
    }

    private List<Integer> parseMetricIds(Map<String, Object> input) {
        List<Integer> metrics = new ArrayList<>();
        if (input == null) {
            return List.of(1, 2, 3, 4, 5);
        }

        if (input.containsKey("metrics")) {
            Object val = input.get("metrics");
            if (val instanceof List<?>) {
                for (Object item : (List<?>) val) {
                    try { metrics.add(parseId(item)); } catch (Exception ignored) {}
                }
            } else if (val != null) {
                String[] parts = String.valueOf(val).split(",");
                for (String part : parts) {
                    if (!part.trim().isEmpty()) {
                        try { metrics.add(Integer.parseInt(part.trim())); } catch (Exception ignored) {}
                    }
                }
            }
        } else if (input.containsKey("metric")) {
            metrics.add(parseId(input.get("metric")));
        } else if (input.containsKey("metric_id")) {
            metrics.add(parseId(input.get("metric_id")));
        }

        if (metrics.isEmpty()) {
            return List.of(1, 2, 3, 4, 5);
        }
        return metrics;
    }

    private int parseId(Object value) {
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        return Integer.parseInt(String.valueOf(value).trim());
    }

    /**
     * Look up metadata registry configuration for a given EntityType and ID.
     */
    private Map<String, String> fetchMetadata(String entityType, int id) {
        Map<String, String> result = new HashMap<>();
        try {
            GetItemRequest request = GetItemRequest.builder()
                    .tableName(METADATA_TABLE)
                    .key(Map.of(
                            "EntityType", AttributeValue.builder().s(entityType).build(),
                            "ID", AttributeValue.builder().n(String.valueOf(id)).build()
                    ))
                    .build();
            
            GetItemResponse response = dynamoDbClient.getItem(request);
            if (response.hasItem() && response.item() != null) {
                Map<String, AttributeValue> item = response.item();
                if (item.containsKey("Name")) result.put("Name", item.get("Name").s());
                if (item.containsKey("Unit")) result.put("Unit", item.get("Unit").s());
                if (item.containsKey("ChartType")) result.put("ChartType", item.get("ChartType").s());
                if (item.containsKey("Location")) result.put("Location", item.get("Location").s());
                if (item.containsKey("Icon")) result.put("Icon", item.get("Icon").s());
                if (item.containsKey("MinYRange") && item.get("MinYRange").n() != null) {
                    result.put("MinYRange", item.get("MinYRange").n());
                }
            }
        } catch (Exception e) {
            // Logs error but proceeds with clean fallbacks
            System.err.println("Could not read metadata from table " + METADATA_TABLE + " (using code fallback): " + e.getMessage());
        }
        return result;
    }

    // Code fallbacks matching config.yaml.example if metadata table is missing/empty
    private String getFallbackMetricName(int metricId, String defaultVal) {
        if (!defaultVal.startsWith("Metric ")) return defaultVal;
        return switch (metricId) {
            case 1 -> "Temperature";
            case 2 -> "Humidity";
            case 3 -> "Ambient Light";
            case 4 -> "Motion Count";
            case 5 -> "Water Level";
            default -> defaultVal;
        };
    }

    private String getFallbackMetricUnit(int metricId, String defaultVal) {
        if (!defaultVal.isEmpty()) return defaultVal;
        return switch (metricId) {
            case 1 -> "°C";
            case 2 -> "%";
            case 3 -> "Lux";
            case 4 -> "triggers/min";
            case 5 -> "cm";
            default -> "";
        };
    }

    private String getFallbackMetricIcon(int metricId) {
        return switch (metricId) {
            case 1 -> "🌡️";
            case 2 -> "💧";
            case 3 -> "☀️";
            case 4 -> "🔍";
            case 5 -> "📏";
            default -> "📊";
        };
    }

    /**
     * Query data from DynamoDB with UTC time boundary logic.
     */
    private List<TelemetryData> fetchTelemetryData(int deviceId, int metricId, LocalDate targetDate, ZoneId zoneId, Context context) {
        // Calculate timezone bounds relative to targetDate
        ZonedDateTime startLocal = ZonedDateTime.of(targetDate, LocalTime.MIN, zoneId);
        ZonedDateTime endLocal = ZonedDateTime.of(targetDate, LocalTime.MAX, zoneId);
        
        ZonedDateTime startUtc = startLocal.withZoneSameInstant(ZoneId.of("UTC"));
        ZonedDateTime endUtc = endLocal.withZoneSameInstant(ZoneId.of("UTC"));

        List<TelemetryData> allData = new ArrayList<>();
        int startYear = startUtc.getYear();
        int endYear = endUtc.getYear();

        // Query start year partition
        allData.addAll(fetchDataForPartition(deviceId, metricId, startYear, startUtc, endUtc, zoneId, context));
        
        // If query boundary spans a year rollover (e.g. Dec 31st local time), merge second year partition
        if (startYear != endYear) {
            allData.addAll(fetchDataForPartition(deviceId, metricId, endYear, startUtc, endUtc, zoneId, context));
        }

        // Sort telemetry data chronologically
        allData.sort(Comparator.comparing(TelemetryData::getTime));
        return allData;
    }

    private List<TelemetryData> fetchDataForPartition(int deviceId, int metricId, int year, ZonedDateTime startUtc, ZonedDateTime endUtc, ZoneId targetZoneId, Context context) {
        String pk = String.format("%d#%d#%d", deviceId, metricId, year);
        String startUtcStr = startUtc.format(DateTimeFormatter.ISO_INSTANT);
        String endUtcStr = endUtc.format(DateTimeFormatter.ISO_INSTANT);

        context.getLogger().log(String.format("Querying DynamoDB Partition PK='%s' SK BETWEEN '%s' AND '%s'", pk, startUtcStr, endUtcStr));

        QueryRequest queryRequest = QueryRequest.builder()
                .tableName(TELEMETRY_TABLE)
                .keyConditionExpression("Device_Metric_UTCYear = :pkVal AND #ts BETWEEN :startTs AND :endTs")
                .expressionAttributeNames(Map.of("#ts", "Timestamp"))
                .expressionAttributeValues(Map.of(
                        ":pkVal", AttributeValue.builder().s(pk).build(),
                        ":startTs", AttributeValue.builder().s(startUtcStr).build(),
                        ":endTs", AttributeValue.builder().s(endUtcStr).build()
                ))
                .build();

        QueryResponse response = dynamoDbClient.query(queryRequest);

        return response.items().stream()
                .map(item -> {
                    // Convert UTC timestamp back to configured local timezone offset for plotting
                    ZonedDateTime time = Instant.parse(item.get("Timestamp").s()).atZone(targetZoneId);
                    double value = Double.parseDouble(item.get("Value").n());
                    return new TelemetryData(time, value);
                })
                .collect(Collectors.toList());
    }

    /**
     * Upload chart asset bytes to S3 in hierarchical layout.
     */
    private String uploadToS3(byte[] content, int deviceId, int metricId, LocalDate date, String dateStr, String contentType, String ext, Context context) {
        String year = String.valueOf(date.getYear());
        String month = date.format(DateTimeFormatter.ofPattern("MM"));
        
        // Path: output/{deviceID}/{metricID}/{year}/{month}/{metricID}-YYYYMMDD.<ext>
        String s3Key = String.format("output/%d/%d/%s/%s/%d-%s%s", deviceId, metricId, year, month, metricId, dateStr, ext);

        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(BUCKET_NAME)
                .key(s3Key)
                .contentType(contentType)
                .cacheControl("max-age=60")
                .build();

        s3Client.putObject(putObjectRequest, RequestBody.fromBytes(content));
        context.getLogger().log(String.format("Uploaded asset: s3://%s/%s (%s)", BUCKET_NAME, s3Key, contentType));
        return s3Key;
    }

    /**
     * Download existing file-list.json from S3 once before batch processing.
     */
    private TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> loadFileListJson(Context context) {
        try {
            GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                    .bucket(BUCKET_NAME)
                    .key(FILE_LIST_JSON_KEY)
                    .build();
            InputStreamReader reader = new InputStreamReader(s3Client.getObject(getObjectRequest));
            Type type = new TypeToken<TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>>>(){}.getType();
            TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> fileTree = gson.fromJson(reader, type);
            return fileTree != null ? fileTree : new TreeMap<>();
        } catch (Exception e) {
            context.getLogger().log("Could not find or read existing file-list.json, creating a new registry. Msg: " + e.getMessage());
            return new TreeMap<>();
        }
    }

    /**
     * Merge generated key into in-memory fileTree.
     */
    private void updateFileListInMemory(
            TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> fileTree,
            int deviceId, int metricId, String newImageKey, LocalDate date) {
        String devKey = String.valueOf(deviceId);
        String metKey = String.valueOf(metricId);
        String yrKey = String.valueOf(date.getYear());
        String moKey = date.format(DateTimeFormatter.ofPattern("MM"));

        TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>> metricsMap = fileTree.computeIfAbsent(devKey, k -> new TreeMap<>());
        TreeMap<String, TreeMap<String, List<String>>> yearsMap = metricsMap.computeIfAbsent(metKey, k -> new TreeMap<>());
        TreeMap<String, List<String>> monthsMap = yearsMap.computeIfAbsent(yrKey, k -> new TreeMap<>());
        List<String> images = monthsMap.computeIfAbsent(moKey, k -> new ArrayList<>());

        if (!images.contains(newImageKey)) {
            images.add(newImageKey);
            Collections.sort(images);
        }
    }

    /**
     * Upload updated file-list.json back to S3 once after batch processing completes.
     */
    private void saveFileListJson(
            TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> fileTree,
            Context context) {
        try {
            String json = gson.toJson(fileTree);
            PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                    .bucket(BUCKET_NAME)
                    .key(FILE_LIST_JSON_KEY)
                    .contentType("application/json")
                    .cacheControl("public, max-age=60")
                    .build();

            s3Client.putObject(putObjectRequest, RequestBody.fromString(json, StandardCharsets.UTF_8));
            context.getLogger().log("Successfully updated file-list.json on S3");
        } catch (Exception e) {
            context.getLogger().log("Error saving file-list.json to S3: " + e.getMessage());
        }
    }

    /**
     * Export all device and metric metadata from IoT_Metadata table to output/metadata.json on S3.
     */
    private void exportMetadataJson(Context context) {
        try {
            Map<String, Object> root = new HashMap<>();
            Map<String, Map<String, Object>> metricsMap = new HashMap<>();
            Map<String, Map<String, Object>> devicesMap = new HashMap<>();

            software.amazon.awssdk.services.dynamodb.model.ScanRequest scanReq =
                software.amazon.awssdk.services.dynamodb.model.ScanRequest.builder()
                    .tableName(METADATA_TABLE)
                    .build();
            software.amazon.awssdk.services.dynamodb.model.ScanResponse scanResp = dynamoDbClient.scan(scanReq);

            if (scanResp.hasItems()) {
                for (Map<String, AttributeValue> item : scanResp.items()) {
                    if (!item.containsKey("EntityType") || !item.containsKey("ID")) continue;
                    String entityType = item.get("EntityType").s();
                    String id = item.get("ID").n() != null ? item.get("ID").n() : item.get("ID").s();

                    Map<String, Object> m = new HashMap<>();
                    if (item.containsKey("Name")) m.put("name", item.get("Name").s());
                    if (item.containsKey("Unit")) m.put("unit", item.get("Unit").s());
                    if (item.containsKey("ChartType")) m.put("chartType", item.get("ChartType").s());
                    if (item.containsKey("Location")) m.put("location", item.get("Location").s());
                    if (item.containsKey("Icon")) m.put("icon", item.get("Icon").s());
                    if (item.containsKey("MinYRange") && item.get("MinYRange").n() != null) {
                        try { m.put("minYRange", Double.parseDouble(item.get("MinYRange").n())); } catch (Exception ignored) {}
                    }

                    if ("METRIC".equalsIgnoreCase(entityType)) {
                        metricsMap.put(id, m);
                    } else if ("DEVICE".equalsIgnoreCase(entityType)) {
                        devicesMap.put(id, m);
                    }
                }
            }

            root.put("metrics", metricsMap);
            root.put("devices", devicesMap);

            String json = gson.toJson(root);
            PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                    .bucket(BUCKET_NAME)
                    .key("output/metadata.json")
                    .contentType("application/json")
                    .cacheControl("public, max-age=60")
                    .build();

            s3Client.putObject(putObjectRequest, RequestBody.fromString(json, StandardCharsets.UTF_8));
            context.getLogger().log("Successfully updated output/metadata.json on S3");
        } catch (Exception e) {
            context.getLogger().log("Could not export output/metadata.json to S3: " + e.getMessage());
        }
    }
}
