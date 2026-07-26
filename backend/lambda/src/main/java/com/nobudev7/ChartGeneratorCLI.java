package com.nobudev7;

import software.amazon.awssdk.services.dynamodb.DynamoDbClient;
import software.amazon.awssdk.services.dynamodb.model.AttributeValue;
import software.amazon.awssdk.services.dynamodb.model.QueryRequest;
import software.amazon.awssdk.services.dynamodb.model.QueryResponse;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.reflect.TypeToken;

import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.lang.reflect.Type;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeMap;
import java.util.stream.Collectors;

/**
 * Command-line tool to fetch telemetry from DynamoDB and render chart PNGs locally.
 *
 * USAGE
 * ─────
 *   mvn compile exec:java -Dexec.mainClass=com.nobudev7.ChartGeneratorCLI \
 *       -Dexec.args="[options]"
 *
 * OPTIONS
 * ───────
 *   -d, --device  <id[,id...]>   Device ID(s). Comma-separated or flag repeated.
 *                                  Example: -d 1,2  or  --device 1 --device 2
 *   -m, --metric  <id[,id...]>   Metric ID(s). Comma-separated or flag repeated.
 *                                  Example: -m 1,2,3
 *   --date        <YYYY-MM-DD>   Specific date. Default: yesterday.
 *   --dates       <d1,d2,...>    Multiple dates, comma-separated.
 *   --tz          <zone>         Timezone ID. Default: America/New_York.
 *   -o, --output  <dir>          Output directory. Default: ./output.
 *   --table       <name>         DynamoDB table name. Default: IoT_Telemetry (or TELEMETRY_TABLE_NAME env var).
 *   --chart-type  <type>         XYLineChart or XYAreaChart. Default: auto (by metric ID).
 *   -h, --help                   Show this help message.
 *
 * EXAMPLES
 * ────────
 *   # Generate yesterday's temperature chart for device 1
 *   -d 1 -m 1
 *
 *   # Generate charts for all metrics on two devices, for a specific date
 *   -d 1,2 -m 1,2,3 --date 2026-07-25
 *
 *   # Multiple dates with custom output directory
 *   -d 1 -m 1 --dates 2026-07-24,2026-07-25 -o ~/charts
 *
 * OUTPUT
 * ──────
 *   Files are written to: frontend/public/output/{deviceId}/{metricId}/{year}/{month}/{metricId}-YYYYMMDD.png
 *   file-list.json index: frontend/public/output/file-list.json
 *
 *   Override with -o <dir>. Path is relative to the directory where mvn is invoked (backend/lambda/).
 */
public class ChartGeneratorCLI {

    // Default chart types by metric ID (matches infrastructure seeding.tf)
    private static final Map<Integer, String> DEFAULT_CHART_TYPES = Map.of(
            1, "XYLineChart",   // Temperature
            2, "XYLineChart",   // Humidity
            3, "XYAreaChart",   // Ambient Light
            4, "XYAreaChart",   // Motion Count
            5, "XYLineChart"    // Water Level
    );

    private static final Map<Integer, String> METRIC_LABELS = Map.of(
            1, "Temperature (°C)",
            2, "Humidity (%)",
            3, "Ambient Light (Lux)",
            4, "Motion Count (triggers/min)",
            5, "Water Level (cm)"
    );

    public static void main(String[] args) throws IOException {
        // ── Parse arguments ──────────────────────────────────────────────────
        Set<Integer> deviceIds = new LinkedHashSet<>();
        Set<Integer> metricIds = new LinkedHashSet<>();
        List<LocalDate> dates   = new ArrayList<>();
        ZoneId zoneId           = ZoneId.of(envOrDefault("TEST_TIMEZONE", "America/New_York"));
        String outputDir        = "frontend/public/output";
        String tableName        = envOrDefault("TELEMETRY_TABLE_NAME", "IoT_Telemetry");
        String chartTypeOverride = null;   // null = auto-select per metric

        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "-h", "--help" -> { printHelp(); return; }
                case "-d", "--device"    -> parseIds(nextArg(args, i++, "--device"), deviceIds);
                case "-m", "--metric"    -> parseIds(nextArg(args, i++, "--metric"), metricIds);
                case "--date"            -> dates.add(parseDate(nextArg(args, i++, "--date")));
                case "--dates"           -> Arrays.stream(nextArg(args, i++, "--dates").split(","))
                                                  .map(String::trim)
                                                  .map(ChartGeneratorCLI::parseDate)
                                                  .forEach(dates::add);
                case "--tz"              -> zoneId    = ZoneId.of(nextArg(args, i++, "--tz"));
                case "-o", "--output"    -> outputDir = nextArg(args, i++, "--output");
                case "--table"           -> tableName = nextArg(args, i++, "--table");
                case "--chart-type"      -> chartTypeOverride = nextArg(args, i++, "--chart-type");
                default -> {
                    // Support --device=1,2 and --metric=1,2 syntax
                    if (args[i].startsWith("--device=")) {
                        parseIds(args[i].substring("--device=".length()), deviceIds);
                    } else if (args[i].startsWith("-d=")) {
                        parseIds(args[i].substring("-d=".length()), deviceIds);
                    } else if (args[i].startsWith("--metric=")) {
                        parseIds(args[i].substring("--metric=".length()), metricIds);
                    } else if (args[i].startsWith("-m=")) {
                        parseIds(args[i].substring("-m=".length()), metricIds);
                    } else {
                        System.err.println("Unknown argument: " + args[i]);
                        printHelp();
                        System.exit(1);
                    }
                }
            }
        }

        // ── Validate required arguments ──────────────────────────────────────
        if (deviceIds.isEmpty()) { System.err.println("Error: at least one --device is required."); printHelp(); System.exit(1); }
        if (metricIds.isEmpty()) { System.err.println("Error: at least one --metric is required."); printHelp(); System.exit(1); }
        if (dates.isEmpty()) {
            dates.add(LocalDate.now(zoneId).minusDays(1));  // default: yesterday
        }

        // ── Summary ──────────────────────────────────────────────────────────
        System.out.printf("╔══════════════════════════════════════════════════╗%n");
        System.out.printf("║         PiLambdaChart CLI — Local Render         ║%n");
        System.out.printf("╠══════════════════════════════════════════════════╣%n");
        System.out.printf("║  Devices  : %-37s║%n", deviceIds);
        System.out.printf("║  Metrics  : %-37s║%n", metricIds);
        System.out.printf("║  Dates    : %-37s║%n", dates);
        System.out.printf("║  Timezone : %-37s║%n", zoneId);
        System.out.printf("║  Table    : %-37s║%n", tableName);
        System.out.printf("║  Output   : %-37s║%n", outputDir);
        System.out.printf("╚══════════════════════════════════════════════════╝%n%n");

        // ── Generate charts ──────────────────────────────────────────────────
        int total = 0, generated = 0, skipped = 0;

        // Shared file-list.json tree — accumulated across all charts in this run,
        // then written once to disk at the end (same structure as S3 version).
        TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> fileTree =
                loadFileListJson(outputDir);

        Gson gson = new GsonBuilder().setPrettyPrinting().create();

        try (DynamoDbClient db = DynamoDbClient.builder().build()) {
            ChartGenerator generator = new ChartGenerator();

            for (LocalDate date : dates) {
                for (int deviceId : deviceIds) {
                    for (int metricId : metricIds) {
                        total++;
                        String savedKey = renderChart(
                                db, generator,
                                deviceId, metricId, date,
                                zoneId, tableName, outputDir, chartTypeOverride);
                        if (savedKey != null) {
                            updateFileListJson(fileTree, deviceId, metricId, savedKey, date);
                            generated++;
                        } else {
                            skipped++;
                        }
                    }
                }
            }
        }

        // ── Write file-list.json ─────────────────────────────────────────────
        if (generated > 0) {
            writeFileListJson(fileTree, outputDir, gson);
        }

        // ── Final summary ────────────────────────────────────────────────────
        System.out.printf("%n── Summary ──────────────────────────────────────────%n");
        System.out.printf("  Total   : %d chart(s) attempted%n", total);
        System.out.printf("  Saved   : %d chart(s) written to '%s'%n", generated, outputDir);
        System.out.printf("  Skipped : %d (no data in DynamoDB for that combination)%n", skipped);
    }

    // ── Chart rendering ───────────────────────────────────────────────────────

    /**
     * Renders one chart from DynamoDB data and saves it to disk.
     * Returns the relative file key on success (matches S3 key format), or null if no data.
     */
    private static String renderChart(DynamoDbClient db, ChartGenerator generator,
                                       int deviceId, int metricId, LocalDate date,
                                       ZoneId zoneId, String tableName,
                                       String outputDir, String chartTypeOverride) throws IOException {

        System.out.printf("[%s] Device=%-3d Metric=%-3d  ", date, deviceId, metricId);

        // 1. Fetch telemetry from DynamoDB
        List<TelemetryData> data = fetchTelemetry(db, deviceId, metricId, date, zoneId, tableName);

        if (data.isEmpty()) {
            System.out.println("→ SKIP (no data)");
            return null;
        }

        // 2. Resolve chart metadata
        String chartType = chartTypeOverride != null
                ? chartTypeOverride
                : DEFAULT_CHART_TYPES.getOrDefault(metricId, "XYLineChart");

        String yLabel = METRIC_LABELS.getOrDefault(metricId, "Metric " + metricId);
        String dateStr = date.format(DateTimeFormatter.ofPattern("yyyyMMdd"));
        String title   = String.format("Device %d — %s on %s",
                deviceId, yLabel, date.format(DateTimeFormatter.ofPattern("yyyy/MM/dd")));

        // 3. Build local output path matching the S3 layout used by ChartGeneratorHandler:
        //    output/{deviceId}/{metricId}/{year}/{month}/{metricId}-YYYYMMDD.png
        String year    = String.valueOf(date.getYear());
        String month   = date.format(DateTimeFormatter.ofPattern("MM"));
        String dirPath  = String.format("%s/%d/%d/%s/%s", outputDir, deviceId, metricId, year, month);
        String filePath = String.format("%s/%d-%s.png", dirPath, metricId, dateStr);
        // Relative key mirrors the S3 key exactly (path beneath the bucket root)
        String fileKey  = String.format("%d/%d/%s/%s/%d-%s.png", deviceId, metricId, year, month, metricId, dateStr);
        Files.createDirectories(Paths.get(dirPath));

        // 4. Render and save
        generator.generateChart(data, title, yLabel, chartType, metricId, filePath);

        File outFile = new File(filePath);
        System.out.printf("→ SAVED  (%d pts, %d KB)  %s%n",
                data.size(), outFile.length() / 1024, filePath);
        return fileKey;
    }

    // ── file-list.json helpers ────────────────────────────────────────────────────

    /**
     * Load an existing file-list.json from disk (if present), returning an empty tree on any error.
     * The tree structure mirrors the S3 version: Device → Metric → Year → Month → [file keys].
     */
    @SuppressWarnings("unchecked")
    private static TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>>
            loadFileListJson(String outputDir) {
        File jsonFile = new File(outputDir + "/file-list.json");
        if (!jsonFile.exists()) return new TreeMap<>();
        try (FileReader reader = new FileReader(jsonFile)) {
            Gson gson = new Gson();
            Type type = new TypeToken<TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>>>(){}.getType();
            TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> tree = gson.fromJson(reader, type);
            return tree != null ? tree : new TreeMap<>();
        } catch (Exception e) {
            System.err.println("Could not read existing file-list.json, starting fresh: " + e.getMessage());
            return new TreeMap<>();
        }
    }

    /**
     * Merge a newly generated file key into the in-memory tree.
     * Identical to ChartGeneratorHandler.updateFileListJson() but operates on the in-memory
     * tree rather than S3, so it can be called after every chart without repeated disk I/O.
     */
    private static void updateFileListJson(
            TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> fileTree,
            int deviceId, int metricId, String newKey, LocalDate date) {
        String devKey = String.valueOf(deviceId);
        String metKey = String.valueOf(metricId);
        String yrKey  = String.valueOf(date.getYear());
        String moKey  = date.format(DateTimeFormatter.ofPattern("MM"));

        TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>> metricsMap =
                fileTree.computeIfAbsent(devKey, k -> new TreeMap<>());
        TreeMap<String, TreeMap<String, List<String>>> yearsMap =
                metricsMap.computeIfAbsent(metKey, k -> new TreeMap<>());
        TreeMap<String, List<String>> monthsMap =
                yearsMap.computeIfAbsent(yrKey, k -> new TreeMap<>());
        List<String> images = monthsMap.computeIfAbsent(moKey, k -> new ArrayList<>());

        if (!images.contains(newKey)) {
            images.add(newKey);
            Collections.sort(images);
        }
    }

    /**
     * Serialise the in-memory tree to file-list.json in the output root directory.
     * Written once after all charts have been generated.
     */
    private static void writeFileListJson(
            TreeMap<String, TreeMap<String, TreeMap<String, TreeMap<String, List<String>>>>> fileTree,
            String outputDir, Gson gson) throws IOException {
        File jsonFile = new File(outputDir + "/file-list.json");
        Files.createDirectories(Paths.get(outputDir));
        try (FileWriter writer = new FileWriter(jsonFile)) {
            gson.toJson(fileTree, writer);
        }
        System.out.println("file-list.json written to: " + jsonFile.getAbsolutePath());
    }

    // ── DynamoDB fetch ────────────────────────────────────────────────────────

    private static List<TelemetryData> fetchTelemetry(DynamoDbClient db,
                                                        int deviceId, int metricId,
                                                        LocalDate date, ZoneId zoneId,
                                                        String tableName) {
        ZonedDateTime startUtc = ZonedDateTime.of(date, LocalTime.MIN, zoneId)
                                              .withZoneSameInstant(ZoneId.of("UTC"));
        ZonedDateTime endUtc   = ZonedDateTime.of(date, LocalTime.MAX, zoneId)
                                              .withZoneSameInstant(ZoneId.of("UTC"));

        List<TelemetryData> all = new ArrayList<>();
        all.addAll(queryPartition(db, deviceId, metricId, startUtc.getYear(), startUtc, endUtc, zoneId, tableName));
        if (startUtc.getYear() != endUtc.getYear()) {
            all.addAll(queryPartition(db, deviceId, metricId, endUtc.getYear(), startUtc, endUtc, zoneId, tableName));
        }
        all.sort(Comparator.comparing(TelemetryData::getTime));
        return all;
    }

    private static List<TelemetryData> queryPartition(DynamoDbClient db,
                                                       int deviceId, int metricId, int year,
                                                       ZonedDateTime startUtc, ZonedDateTime endUtc,
                                                       ZoneId zoneId, String tableName) {
        String pk = String.format("%d#%d#%d", deviceId, metricId, year);
        QueryResponse response = db.query(QueryRequest.builder()
                .tableName(tableName)
                .keyConditionExpression("Device_Metric_UTCYear = :pk AND #ts BETWEEN :start AND :end")
                .expressionAttributeNames(Map.of("#ts", "Timestamp"))
                .expressionAttributeValues(Map.of(
                        ":pk",    AttributeValue.builder().s(pk).build(),
                        ":start", AttributeValue.builder().s(startUtc.format(DateTimeFormatter.ISO_INSTANT)).build(),
                        ":end",   AttributeValue.builder().s(endUtc.format(DateTimeFormatter.ISO_INSTANT)).build()
                ))
                .build());

        return response.items().stream()
                .map(item -> new TelemetryData(
                        Instant.parse(item.get("Timestamp").s()).atZone(zoneId),
                        Double.parseDouble(item.get("Value").n())))
                .collect(Collectors.toList());
    }

    // ── Argument helpers ──────────────────────────────────────────────────────

    private static void parseIds(String value, Set<Integer> target) {
        Arrays.stream(value.split(","))
              .map(String::trim)
              .filter(s -> !s.isEmpty())
              .mapToInt(s -> {
                  try { return Integer.parseInt(s); }
                  catch (NumberFormatException e) {
                      throw new IllegalArgumentException("Invalid integer ID: '" + s + "'");
                  }
              })
              .forEach(target::add);
    }

    private static String nextArg(String[] args, int i, String flag) {
        if (i + 1 >= args.length) {
            System.err.println("Error: " + flag + " requires a value.");
            System.exit(1);
        }
        return args[i + 1];
    }

    private static LocalDate parseDate(String s) {
        try {
            return LocalDate.parse(s.trim());
        } catch (DateTimeParseException e) {
            System.err.println("Error: invalid date '" + s + "'. Expected YYYY-MM-DD.");
            System.exit(1);
            return null;
        }
    }

    private static String envOrDefault(String key, String defaultValue) {
        String v = System.getenv(key);
        return (v != null && !v.isBlank()) ? v : defaultValue;
    }

    // ── Help ──────────────────────────────────────────────────────────────────

    private static void printHelp() {
        System.out.println("""
            PiLambdaChart CLI — Fetch DynamoDB telemetry and render chart PNGs locally

            USAGE
              mvn compile exec:java -Dexec.mainClass=com.nobudev7.ChartGeneratorCLI \\
                  -Dexec.args="<options>"

            OPTIONS
              -d, --device  <id[,id...]>  Device ID(s) (required). Comma-separated or repeated.
              -m, --metric  <id[,id...]>  Metric ID(s) (required). Comma-separated or repeated.
              --date        <YYYY-MM-DD>  Target date (default: yesterday).
              --dates       <d1,d2,...>   Multiple dates, comma-separated.
              --tz          <zone>        Timezone (default: America/New_York).
              -o, --output  <dir>         Output directory
                                            (default: frontend/public/output,
                                             relative to backend/lambda/ where mvn runs).
              --table       <name>        DynamoDB table name (default: IoT_Telemetry).
              --chart-type  <type>        Force chart type: XYLineChart or XYAreaChart.
              -h, --help                  Show this help.

            KNOWN METRIC IDs
              1  Temperature   (XYLineChart)
              2  Humidity      (XYLineChart)
              3  Ambient Light (XYAreaChart)
              4  Motion Count  (XYAreaChart)
              5  Water Level   (XYLineChart)

            EXAMPLES
              # Yesterday's temperature chart for device 1
              -d 1 -m 1

              # All sensor metrics for two devices on a specific date
              -d 1,2 -m 1,2,3,4,5 --date 2026-07-25

              # Multiple dates with a custom output directory
              -d 1 -m 1,3 --dates 2026-07-24,2026-07-25,2026-07-26 -o ~/my-charts

              # Override timezone
              -d 1 -m 1 --tz America/Los_Angeles

            OUTPUT
              Files are saved as: <output>/{deviceId}/{metricId}/{year}/{month}/{metricId}-YYYYMMDD.png

            ENVIRONMENT VARIABLES
              TELEMETRY_TABLE_NAME   Override DynamoDB table name
              TEST_TIMEZONE          Override default timezone
            """);
    }
}
