# PiLambdaChart Presentation Layer (Web Dashboard)

This folder contains the static website files served to dashboard users.

## Folder Structure
*   `public/index.html`: Main HTML entrypoint for the dashboard.
*   `public/style.css`: Clean, dark-mode default glassmorphic styles.
*   `public/app.js`: Script to parse S3 file trees and populate the dashboard views.
*   `public/output/`: Chart PNG images and `file-list.json` index.
    *   Populated locally by running the **Chart Generator CLI** (`backend/lambda/ChartGeneratorCLI.java`).
    *   In production, this content is served from the S3 bucket written by the Lambda function.
    *   Structure: `output/{deviceId}/{metricId}/{year}/{month}/{metricId}-YYYYMMDD.png`
    *   Index: `output/file-list.json` — hierarchical tree of all available chart keys.
