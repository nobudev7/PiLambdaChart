package com.nobudev7;

import org.jfree.chart.ChartFactory;
import org.jfree.chart.JFreeChart;
import org.jfree.chart.axis.AxisState;
import org.jfree.chart.axis.NumberAxis;
import org.jfree.chart.axis.NumberTick;
import org.jfree.chart.axis.NumberTickUnit;
import org.jfree.chart.axis.Tick;
import org.jfree.chart.plot.PlotOrientation;
import org.jfree.chart.plot.XYPlot;
import org.jfree.chart.renderer.xy.XYAreaRenderer;
import org.jfree.chart.renderer.xy.XYLineAndShapeRenderer;
import org.jfree.chart.ui.RectangleEdge;
import org.jfree.chart.ui.RectangleInsets;
import org.jfree.chart.ui.TextAnchor;
import org.jfree.data.xy.XYSeries;
import org.jfree.data.xy.XYSeriesCollection;

import org.jfree.chart.ChartRenderingInfo;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import javax.imageio.ImageIO;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.geom.Rectangle2D;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.time.ZonedDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Modern JFreeChart generator for PiLambdaChart metrics.
 * Uses a premium dark-slate design system matching high-end dashboards.
 */
public class ChartGenerator {

    public static class RenderResult {
        private final byte[] imageBytes;
        private final String jsonMetadata;

        public RenderResult(byte[] imageBytes, String jsonMetadata) {
            this.imageBytes = imageBytes;
            this.jsonMetadata = jsonMetadata;
        }

        public byte[] getImageBytes() {
            return imageBytes;
        }

        public String getJsonMetadata() {
            return jsonMetadata;
        }
    }

    // Tailored color palette
    private static final Color BG_OUTER = new Color(15, 23, 42);      // Slate 900
    private static final Color BG_PLOT = new Color(30, 41, 59);       // Slate 800
    private static final Color GRID_LINE = new Color(71, 85, 105);    // Slate 600
    private static final Color TEXT_TITLE = new Color(248, 250, 252);  // Slate 50
    private static final Color TEXT_LABEL = new Color(203, 213, 225);  // Slate 300
    private static final Color TEXT_TICK = new Color(148, 163, 184);   // Slate 400
    
    // Bright neon accent colors based on metric type
    private static final Color ACCENT_BLUE = new Color(56, 189, 248);  // Sky 400 (e.g. Temperature, Light)
    private static final Color ACCENT_GREEN = new Color(52, 211, 153); // Emerald 400 (e.g. Water Level)
    private static final Color ACCENT_PURPLE = new Color(192, 132, 252); // Purple 400 (e.g. Humidity)
    private static final Color ACCENT_ORANGE = new Color(251, 146, 60); // Orange 400 (e.g. Motion Count)

    public RenderResult generateChartWithMetadata(List<TelemetryData> data, String title, String yAxisLabel, String chartType, int deviceId, int metricId, String metricName, String unit) throws IOException {
        if (data == null || data.isEmpty()) {
            return null;
        }

        XYSeries series = new XYSeries("Data");
        double maxValue = Double.MIN_VALUE;
        double minValue = Double.MAX_VALUE;

        for (int i = 0; i < data.size(); i++) {
            TelemetryData d = data.get(i);
            series.add(i, d.getValue());
            if (d.getValue() > maxValue) {
                maxValue = d.getValue();
            }
            if (d.getValue() < minValue) {
                minValue = d.getValue();
            }
        }

        XYSeriesCollection dataset = new XYSeriesCollection(series);
        
        boolean isArea = "XYAreaChart".equalsIgnoreCase(chartType) || "AreaChart".equalsIgnoreCase(chartType);
        
        JFreeChart chart = ChartFactory.createXYLineChart(
                title,
                "Time",
                yAxisLabel,
                dataset,
                PlotOrientation.VERTICAL,
                false,
                false,
                false
        );

        // Styling the outer frame
        chart.setBackgroundPaint(BG_OUTER);
        chart.getTitle().setPaint(TEXT_TITLE);
        chart.getTitle().setFont(new Font("SansSerif", Font.BOLD, 48));
        chart.getTitle().setPadding(new RectangleInsets(15, 10, 25, 10));

        // Styling the plot area
        XYPlot plot = (XYPlot) chart.getPlot();
        plot.setBackgroundPaint(BG_PLOT);
        plot.setDomainGridlinesVisible(false);
        plot.setRangeGridlinePaint(GRID_LINE);
        plot.setRangeGridlineStroke(new BasicStroke(1.0f));
        plot.setOutlineVisible(false);
        plot.setInsets(new RectangleInsets(10, 15, 10, 35));

        // Determine dynamic accent color depending on Metric ID
        Color accentColor;
        switch (metricId) {
            case 1: // Temperature
                accentColor = ACCENT_BLUE;
                break;
            case 2: // Humidity
                accentColor = ACCENT_PURPLE;
                break;
            case 3: // Lux/Light
                accentColor = ACCENT_ORANGE;
                break;
            case 4: // Motion
                accentColor = ACCENT_ORANGE;
                break;
            case 5: // Water Level
                accentColor = ACCENT_GREEN;
                break;
            default:
                accentColor = ACCENT_BLUE;
        }

        // Configure renderer
        if (isArea) {
            XYAreaRenderer areaRenderer = new XYAreaRenderer();
            areaRenderer.setSeriesPaint(0, new Color(accentColor.getRed(), accentColor.getGreen(), accentColor.getBlue(), 80)); // translucent fill
            areaRenderer.setOutline(true);
            areaRenderer.setSeriesOutlinePaint(0, accentColor);
            areaRenderer.setSeriesOutlineStroke(0, new BasicStroke(3.0f));
            plot.setRenderer(areaRenderer);
        } else {
            XYLineAndShapeRenderer lineRenderer = new XYLineAndShapeRenderer(true, false);
            lineRenderer.setSeriesPaint(0, accentColor);
            lineRenderer.setSeriesStroke(0, new BasicStroke(3.5f));
            plot.setRenderer(lineRenderer);
        }

        // Configure Y axis
        NumberAxis rangeAxis = (NumberAxis) plot.getRangeAxis();
        rangeAxis.setLabelFont(new Font("SansSerif", Font.BOLD, 30));
        rangeAxis.setLabelPaint(TEXT_LABEL);
        rangeAxis.setTickLabelFont(new Font("SansSerif", Font.PLAIN, 22));
        rangeAxis.setTickLabelPaint(TEXT_TICK);
        rangeAxis.setAxisLineVisible(false);

        // Adjust bounds with dynamic spacing
        double span = maxValue - minValue;
        double margin = span * 0.15;
        if (margin == 0) {
            margin = maxValue != 0 ? Math.abs(maxValue) * 0.15 : 1.0;
        }

        double lowerBound = minValue - margin;
        // Don't go below zero for strictly positive metrics
        if (minValue >= 0.0 && lowerBound < 0.0) {
            lowerBound = 0.0;
        }
        double upperBound = maxValue + margin;

        rangeAxis.setLowerBound(lowerBound);
        rangeAxis.setUpperBound(upperBound);

        // Pick reasonable tick spacing based on total range span
        double totalSpan = upperBound - lowerBound;
        if (totalSpan <= 1.0) {
            rangeAxis.setTickUnit(new NumberTickUnit(0.1));
        } else if (totalSpan <= 5.0) {
            rangeAxis.setTickUnit(new NumberTickUnit(0.5));
        } else if (totalSpan <= 20.0) {
            rangeAxis.setTickUnit(new NumberTickUnit(2.0));
        } else if (totalSpan <= 50.0) {
            rangeAxis.setTickUnit(new NumberTickUnit(5.0));
        } else if (totalSpan <= 200.0) {
            rangeAxis.setTickUnit(new NumberTickUnit(20.0));
        } else {
            rangeAxis.setTickUnit(new NumberTickUnit(50.0));
        }

        // Configure X axis
        plot.setDomainAxis(new HourlyNumberAxis(data));
        NumberAxis domainAxis = (NumberAxis) plot.getDomainAxis();
        domainAxis.setLabel("Time");
        domainAxis.setLabelFont(new Font("SansSerif", Font.BOLD, 30));
        domainAxis.setLabelPaint(TEXT_LABEL);
        domainAxis.setTickLabelFont(new Font("SansSerif", Font.PLAIN, 22));
        domainAxis.setTickLabelPaint(TEXT_TICK);
        domainAxis.setAxisLineVisible(false);
        domainAxis.setLowerMargin(0.0);
        domainAxis.setUpperMargin(0.0);

        int width = 1600;
        int height = 900;
        int borderPadding = 20;

        BufferedImage image = new BufferedImage(width + borderPadding, height + borderPadding, BufferedImage.TYPE_INT_ARGB);
        Graphics2D g2 = image.createGraphics();
        
        // Turn on high-quality rendering hints for anti-aliasing
        g2.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g2.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
        g2.setRenderingHint(RenderingHints.KEY_RENDERING, RenderingHints.VALUE_RENDER_QUALITY);
        
        g2.setColor(BG_OUTER);
        g2.fillRect(0, 0, width + borderPadding, height + borderPadding);

        ChartRenderingInfo info = new ChartRenderingInfo();
        chart.draw(g2, new Rectangle2D.Double(0, borderPadding, width, height), info);
        g2.dispose();

        ByteArrayOutputStream chartByteStream = new ByteArrayOutputStream();
        ImageIO.write(image, "png", chartByteStream);
        byte[] imageBytes = chartByteStream.toByteArray();

        Rectangle2D dataArea = info.getPlotInfo().getDataArea();

        Map<String, Object> metaMap = new HashMap<>();
        metaMap.put("deviceId", deviceId);
        metaMap.put("metricId", metricId);
        metaMap.put("metricName", metricName != null ? metricName : "Metric " + metricId);
        metaMap.put("unit", unit != null ? unit : "");

        Map<String, Object> plotArea = new HashMap<>();
        plotArea.put("x", dataArea.getX());
        plotArea.put("y", dataArea.getY());
        plotArea.put("width", dataArea.getWidth());
        plotArea.put("height", dataArea.getHeight());
        plotArea.put("imageWidth", width + borderPadding);
        plotArea.put("imageHeight", height + borderPadding);
        plotArea.put("yLowerBound", lowerBound);
        plotArea.put("yUpperBound", upperBound);
        metaMap.put("plotArea", plotArea);

        List<Map<String, Object>> points = new ArrayList<>();
        DateTimeFormatter fmt = DateTimeFormatter.ofPattern("HH:mm:ss");
        for (int i = 0; i < data.size(); i++) {
            TelemetryData d = data.get(i);
            Map<String, Object> p = new HashMap<>();
            p.put("index", i);
            p.put("iso", d.getTime().toString());
            p.put("epochMs", d.getTime().toInstant().toEpochMilli());
            p.put("time", d.getTime().format(fmt));
            p.put("value", d.getValue());
            points.add(p);
        }
        metaMap.put("points", points);

        Gson gson = new GsonBuilder().setPrettyPrinting().create();
        String jsonMetadata = gson.toJson(metaMap);

        return new RenderResult(imageBytes, jsonMetadata);
    }

    public byte[] generateChart(List<TelemetryData> data, String title, String yAxisLabel, String chartType, int metricId) throws IOException {
        RenderResult result = generateChartWithMetadata(data, title, yAxisLabel, chartType, 0, metricId, null, null);
        return result != null ? result.getImageBytes() : null;
    }

    public void generateChart(List<TelemetryData> data, String title, String yAxisLabel, String chartType, int metricId, String filePath) throws IOException {
        byte[] chartBytes = generateChart(data, title, yAxisLabel, chartType, metricId);
        if (chartBytes != null) {
            java.nio.file.Files.write(new File(filePath).toPath(), chartBytes);
        }
    }

    /**
     * Custom hourly tick axis for rendering times.
     */
    private static class HourlyNumberAxis extends NumberAxis {
        private final List<TelemetryData> data;

        public HourlyNumberAxis(List<TelemetryData> data) {
            super();
            this.data = data;
        }

        @Override
        public List<Tick> refreshTicks(Graphics2D g2, AxisState state, Rectangle2D dataArea, RectangleEdge edge) {
            List<Tick> ticks = new ArrayList<>();
            if (data == null || data.isEmpty()) {
                return ticks;
            }

            DateTimeFormatter timeFormatter = DateTimeFormatter.ofPattern("H:mm");

            int lastHour = -1;
            ZonedDateTime lastTime = null;

            for (int i = 0; i < data.size(); i++) {
                ZonedDateTime time = data.get(i).getTime();
                int currentHour = time.getHour();
                
                // Show tick every 2 hours, or if there's a timezone transition (offset change) at that hour
                if (currentHour % 2 == 0 && (currentHour != lastHour || (lastTime != null && !time.getOffset().equals(lastTime.getOffset())))) {
                    ticks.add(new NumberTick(i, time.format(timeFormatter),
                            TextAnchor.TOP_CENTER, TextAnchor.CENTER, 0.0));
                    lastHour = currentHour;
                    lastTime = time;
                }
            }
            return ticks;
        }
    }
}
