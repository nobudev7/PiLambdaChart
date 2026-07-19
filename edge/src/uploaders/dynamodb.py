import asyncio
import logging
from decimal import Decimal
import boto3
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

class DynamoDbUploader:
    def __init__(self, region: str, table_name: str, enabled: bool = True):
        """
        DynamoDB Uploader for IoT Telemetry.
        :param region: AWS region.
        :param table_name: DynamoDB table name.
        :param enabled: If False, runs in dry-run/mock mode and logs data without uploading.
        """
        self.region = region
        self.table_name = table_name
        self.enabled = enabled
        self.db = None
        self.table = None

    def setup(self):
        if not self.enabled:
            logger.info("DynamoDB Uploader initialized in DRY-RUN mode.")
            return

        try:
            self.db = boto3.resource("dynamodb", region_name=self.region)
            self.table = self.db.Table(self.table_name)
            logger.info(f"DynamoDB Uploader connected to table: '{self.table_name}' in region: '{self.region}'")
        except Exception as e:
            logger.error(f"Failed to initialize boto3 DynamoDB connection: {e}")
            raise e

    def _put_item_sync(self, item: dict):
        if not self.enabled:
            logger.info(f"[DRY-RUN] Would upload data point: {item}")
            return True
        
        try:
            # Construct DynamoDB record matching schema
            # PK: Device_Metric_UTCYear (e.g. "1#1#2026")
            # SK: Timestamp (UTC ISO-8601, e.g. "2026-07-12T14:30:00Z")
            timestamp_utc = item["timestamp"] # datetime object
            utc_year = timestamp_utc.strftime("%Y")
            iso_timestamp = timestamp_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            pk = f"{item['device_id']}#{item['metric_id']}#{utc_year}"
            
            db_item = {
                "Device_Metric_UTCYear": pk,
                "Timestamp": iso_timestamp,
                "Value": Decimal(str(item["value"])),
                "DeviceID": Decimal(str(item["device_id"])),
                "MetricID": Decimal(str(item["metric_id"]))
            }
            
            self.table.put_item(Item=db_item)
            logger.debug(f"Successfully uploaded data point to DynamoDB: {db_item}")
            return True
        except (BotoCoreError, ClientError) as e:
            logger.error(f"AWS DynamoDB client/core error uploading point: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error formatting or uploading point: {e}")
            return False

    async def upload(self, data_point: dict) -> bool:
        """
        Uploads a single data point asynchronously.
        :param data_point: Dict containing keys: device_id, metric_id, value, timestamp (datetime)
        :returns: True if upload succeeded, False otherwise
        """
        return await asyncio.to_thread(self._put_item_sync, data_point)
