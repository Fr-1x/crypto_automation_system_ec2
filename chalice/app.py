import os
import logging
import boto3
import time
import json
from chalice import Chalice, Cron
from chalicelib import utils, trade_processing, trade_execution

app = Chalice(app_name="crypto_bot_ec2")
app.log.setLevel(logging.DEBUG)

# REST API Endpoint
@app.route("/receive_trade_signals_ec2", methods=["POST"])
def receive_trade_signals_ec2():
    """Receives trade signal via post request and executes stop loss or writes it to database."""
    trade_in = app.current_request.json_body
    app.log.debug("Trade Signal Received: %s", trade_in)

    trade_out = trade_processing.preprocess_trade_signal(trade_in)
    app.log.debug("Trade Signal Processed: %s", trade_out)

    if "stop" in trade_out.get("order_comment").lower():
        try:
            order_json_str = app.current_request.raw_body.decode()
            queue_url = os.environ.get("QUEUE_URL")
            sqs = boto3.client('sqs')
            command = 'execute-order'
            msg_dedup_id = str(time.time_ns()) + command
            response = sqs.send_message(QueueUrl=queue_url, MessageGroupId=command, MessageBody=command, MessageDeduplicationId=msg_dedup_id, MessageAttributes={
                'Order': {
                    'StringValue': order_json_str,
                    'DataType': 'String'
                }
            })
            app.log.info(f"Message execute-order sent:", order_json_str)

        except Exception as e:
            app.log.error("Error queuing stop order message:", e)
            time.sleep(30)

    else:
        table_name = os.environ.get("TABLE_NAME")
        dynamodb_manager = utils.DynamoDBManager()
        table = dynamodb_manager.get_table(table_name)
        app.log.debug("Established connection to %s database", table_name)

        table.put_item(Item=trade_out)
        app.log.info("Trade on %s at %s saved to database.", trade_out['ticker'], trade_out['create_ts'])

# Scheduled Lambda Function 
@app.schedule(Cron("1", "0,8,16", "*", "*", "?", "*"))
def execute_trade_signals(event):

    try:
        queue_url = os.environ.get("QUEUE_URL")
        sqs = boto3.client('sqs')
        command = 'execute-recent-orders'
        msg_dedup_id = str(time.time_ns()) + command
        response = sqs.send_message(QueueUrl=queue_url, MessageGroupId=command, MessageBody=command, MessageDeduplicationId=msg_dedup_id, MessageAttributes={})
        app.log.info(f"Message execute-recent-orders sent")

    except Exception as e:
        app.log.error("Error queuing stop order message:", e)
        time.sleep(30)

