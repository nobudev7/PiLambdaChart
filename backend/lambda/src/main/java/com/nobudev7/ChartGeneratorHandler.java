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
        int metricId = 1;
        ZoneId zoneId = DEFAULT_ZONE_ID;
        LocalDate targetDate = null;

        // 1. Parse incoming payload parameters
        if (input != null) {
            if (input.containsKey("device")) {
                deviceId = parseId(input.get("device"));
            } else if (input.containsKey("device_id")) {
                deviceId = parseId(input.get("device_id"));
            }
            
            if (input.containsKey("metric")) {
                metricId = parseId(input.get("metric"));
            } else if (input.containsKey("metric_id")) {
                metricId = parseId(input.get("metric_id"));
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

        String dateStr = targetDate.format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        context.getLogger().log(String.format("Generating chart for Device=%d, Metric=%d, Date=%s, TZ=%s", 
                deviceId, metricId, dateStr, zoneId.getId()));

        try {
            // 2. Look up metadata for the device and metric to get labels and chart types
            Map<String, String> deviceMetadata = fetchMetadata("DEVICE", deviceId);
            Map<String, String> metricMetadata = fetchMetadata("METRIC", metricId);

            String deviceName = deviceMetadata.getOrDefault("Name", "Device " + deviceId);
            String metricName = getFallbackMetricName(metricId, metricMetadata.getOrDefault("Name", "Metric " + metricId));
            String unit = getFallbackMetricUnit(metricId, metricMetadata.getOrDefault("Unit", ""));
            String chartType = metricMetadata.getOrDefault("ChartType", "XYLineChart");

            context.getLogger().log(String.format("Metadata resolved: DeviceName='%s', MetricName='%s', Unit='%s', ChartType='%s'", 
                    deviceName, metricName, unit, chartType));

            // 3. Query DynamoDB using Year-Bounded Timezone Bounds
            List<TelemetryData> data = fetchTelemetryData(deviceId, metricId, targetDate, zoneId, context);
            if (data.isEmpty()) {
                context.getLogger().log(String.format("No data found for Device=%d, Metric=%d on %s", deviceId, metricId, dateStr));
                return "No data found for date " + dateStr;
            }

            // 4. Generate the styled chart JFreeChart image
            String chartTitle = String.format("%s - %s on %s", deviceName, metricName, targetDate.format(DateTimeFormatter.ofPattern("yyyy/MM/dd")));
            String yAxisLabel = unit.isEmpty() ? metricName : String.format("%s (%s)", metricName, unit);
            
            byte[] chartImage = chartGenerator.generateChart(data, chartTitle, yAxisLabel, chartType, metricId);

            if (chartImage != null) {
                // 5. Upload image to S3 in the hierarchical output path
                // output/{deviceID}/{metricID}/{year}/{month}/{metricID}-YYYYMMDD.png
                String s3Key = uploadToS3(chartImage, deviceId, metricId, targetDate, dateStr, context);
                
                // 6. Update file-list.json S3 registry tree
                updateFileListJson(deviceId, metricId, s3Key, targetDate, context);
                
                return String.format("Successfully generated chart: s3://%s/%s", BUCKET_NAME, s3Key);
            } else {
                return "Error: Failed to generate chart bytes.";
            }

        } catch (Exception e) {
            context.getLogger().log("Error during handler execution: " + e.getMessage());
            e.printStackTrace();
            return "Error: " + e.getMessage();
        }
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
            default -> defaultVal;
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
     * Upload JFreeChart image bytes to S3 in hierarchical layout.
     */
    private String uploadToS3(byte[] content, int deviceId, int metricId, LocalDate date, String dateStr, Context context) {
        String year = String.valueOf(date.getYear());
        String month = date.format(DateTimeFormatter.ofPattern("MM"));
        
        // Path: output/{deviceID}/{metricID}/{year}/{month}/{metricID}-YYYYMMDD.png
        String s3Key = String.format("output/%d/%d/%s/%s/%d-%s.png", deviceId, metricId, year, month, metricId, dateStr);

        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(BUCKET_NAME)
                .key(s3Key)
                .contentType("image/png")
                .cacheControl("max-age=60")
                .build();

        s3Client.putObject(putObjectRequest, RequestBody.fromBytes(content));
        context.getLogger().log(String.format("Uploaded chart image: s3://%s/%s", BUCKET_NAME, s3Key));
        return s3Key;
    }

    /**
     * Update index file-list.json matching multi-level hierarchy: Device -> Metric -> Year -> Month -> Files
     */
    private void updateFileListJson(int deviceId, int metricId, String newImageKey, LocalDate date, Context context) {
        TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> fileTree;

        // 1. Download existing file-list.json from S3
        try {
            GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                    .bucket(BUCKET_NAME)
                    .key(FILE_LIST_JSON_KEY)
                    .build();
            
            InputStreamReader reader = new InputStreamReader(s3Client.getObject(getObjectRequest));
            Type type = new TypeToken<TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>>>(){}.getType();
            fileTree = gson.fromJson(reader, type);
            if (fileTree == null) fileTree = new TreeMap<>();
            
        } catch (Exception e) {
            context.getLogger().log("Could not find or read existing file-list.json, creating a new registry. Msg: " + e.getMessage());
            fileTree = new TreeMap<>();
        }

        // 2. Traverse and update the tree structures
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

        // 3. Upload updated tree back to S3
        String json = gson.toJson(fileTree);
        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(BUCKET_NAME)
                .key(FILE_LIST_JSON_KEY)
                .contentType("application/json")
                .cacheControl("max-age=60")
                .build();

        s3Client.putObject(putObjectRequest, RequestBody.fromString(json));
        context.getLogger().log("Successfully updated S3 file-list.json");
    }
}
