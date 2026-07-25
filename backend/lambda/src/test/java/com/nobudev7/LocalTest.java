package com.nobudev7;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;

/**
 * Local integration test that invokes the Lambda handler directly against real AWS resources.
 *
 * Credentials and region are resolved automatically by the AWS SDK's default provider chain:
 *   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars
 *   → ~/.aws/credentials / ~/.aws/config (named or default profile)
 *   → EC2 / ECS instance metadata
 *
 * If no credentials are available the SDK throws SdkClientException and the test fails
 * with a clear message — no silent skipping.
 *
 * Run selectively (not part of the standard unit-test suite):
 *   mvn test -Dtest=LocalTest
 *   AWS_PROFILE=pilambdachart-dev mvn test -Dtest=LocalTest
 */
public class LocalTest {

    @Test
    public void testLambdaHandler_Device1_Temperature() {
        System.out.println("Starting local Lambda integration test (Device 2 - Metric 1 - Temperature)...");
        Map<String, Object> input = new HashMap<>();
        input.put("device_id", 1);
        input.put("metric_id", 1);
        input.put("date", "2026-07-25");
        runHandler(input);
    }

    @Test
    public void testLambdaHandler_Device1_Humidity() {
        System.out.println("Starting local Lambda integration test (Device 1 - Metric 5 - Water Level)...");
        Map<String, Object> input = new HashMap<>();
        input.put("device_id", 1);
        input.put("metric_id", 2);
        input.put("target", "yesterday");
        runHandler(input);
    }


    private void runHandler(Map<String, Object> input) {
        ChartGeneratorHandler handler = new ChartGeneratorHandler();
        String result = handler.handleRequest(input, new TestContext());
        System.out.println("Result: " + result);
    }

    private static class TestContext implements com.amazonaws.services.lambda.runtime.Context {
        public String getAwsRequestId() { return "local-test-id"; }
        public String getLogGroupName() { return "local-log-group"; }
        public String getLogStreamName() { return "local-log-stream"; }
        public String getFunctionName() { return "ChartGeneratorFunction"; }
        public String getFunctionVersion() { return "1"; }
        public String getInvokedFunctionArn() { return "arn:aws:lambda:local:123:function:ChartGeneratorFunction"; }
        public com.amazonaws.services.lambda.runtime.CognitoIdentity getIdentity() { return null; }
        public com.amazonaws.services.lambda.runtime.ClientContext getClientContext() { return null; }
        public int getRemainingTimeInMillis() { return 30000; }
        public int getMemoryLimitInMB() { return 512; }
        public com.amazonaws.services.lambda.runtime.LambdaLogger getLogger() {
            return new com.amazonaws.services.lambda.runtime.LambdaLogger() {
                public void log(String message) { System.out.println("[LAMBDA] " + message); }
                public void log(byte[] message) { System.out.println("[LAMBDA] " + new String(message)); }
            };
        }
    }
}
