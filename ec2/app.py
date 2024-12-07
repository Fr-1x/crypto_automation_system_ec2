import os
import logging
import json
import argparse
import boto3
import json
import time
from chalicelib import utils, trade_processing, trade_execution

# Exchange, set to gemini, binance, binance_usdm
exchange_name = "binance"

# Base currency such as USD or USDT
base_currency = "USDT"

# AWS secret name
secret_name = "SECRET_NAME"

# AWS dynamo db table name for trades
table_name = "TABLE_NAME"

# Queue URL
queue_url = "https://sqs..."

def execute_order(order_json_str):
    """Receives trade signal and executes it."""

    try:
        trade_in = json.loads(order_json_str)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON string for execute_order. Error: {e}")
        raise e

    print("Trade Signal Received: ", trade_in)

    trade_out = trade_processing.preprocess_trade_signal(trade_in)
    print("Trade Signal Processed: ", trade_out)

    exchange = trade_execution.Exchange(exchange_name, base_currency)
    exchange.connect(secret_name, sandbox=False)
    print(f"Succesfully connected to exchange: {exchange_name}")

    if "stop" in trade_out.get("order_comment").lower():
        order = trade_execution.execute_long_stop(exchange, trade_out, increment_pct=0.001)
        print(f"Successfully executed order: {order}")
    else:
        trades = [ trade_out ]
        orders = trade_execution.buy_side_boost(exchange, trades, increment_pct=0.001)
        if orders:
            print(f"Successfully placed order(s): {orders}")


def execute_recent_orders():
    """Executes recent orders read from the database."""

    utcnow = utils.get_utc_now_rounded()
    trades = trade_processing.get_all_recent_signals(utcnow, table_name)
    if trades:
        print(f"Succesfully retrieved trade signals from database: {trades}")

        exchange = trade_execution.Exchange(exchange_name, base_currency)
        exchange.connect(secret_name, sandbox=False)
        print(f"Succesfully connected to exchange: {exchange_name}")

        orders = trade_execution.buy_side_boost(exchange, trades, increment_pct=0.001)
        if orders:
            print(f"Successfully placed order(s): {orders}")
    else:
        print(f"No trade signals at {utcnow}")


def daemon_sqs(wait_time=20, max_messages=1):
    """
    Listen to an AWS SQS queue and process messages.

    :param queue_url: The URL of the SQS queue to listen to.
    :param wait_time: The maximum number of seconds to wait for a message (long polling).
    :param max_messages: The maximum number of messages to retrieve at once.
    """
    # Create an SQS client
    sqs = boto3.client('sqs')

    print(f"Listening to SQS queue: {queue_url}")

    while True:
        try:
            # Receive messages
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sqs/client/receive_message.html#
            response = sqs.receive_message(
                QueueUrl=queue_url,
                AttributeNames=['All'],  # Retrieve all message attributes
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time,  # Parameter enables long polling, duration max. 20 s
                MessageAttributeNames=['All']
            )

            # Check if messages were received
            messages = response.get('Messages', [])
            if not messages:
                print("No messages received. Waiting...")
                continue

            for message in messages:
                # Process the message
                print("Received message:")
                print(json.dumps(message, indent=4))

                # Delete the message from the queue
                receipt_handle = message['ReceiptHandle']
                sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
                print("Message deleted.")

                # Execute
                # Note: code assumes MessageRetentionPeriod is set for messages to expire, e.g., after 3540 seconds
                body = message.get('Body', '')
                if body == "execute-recent-orders":
                    print('Received execute-recent-orders message')
                    execute_recent_orders()
                elif body == "execute-order":
                    message_attributes = message.get('MessageAttributes', '{}')
                    order_msg_json_str = message_attributes.get('Order', '{}').get('StringValue', '')
                    print('Received execute-order message:', order_msg_json_str)
                    execute_order(order_msg_json_str)

        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(30)  # Pause before retrying in case of an error

def main():
    parser = argparse.ArgumentParser(description="Order execution script.")

    # Add mutually exclusive group for options
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--execute-order", type=str, help="Execute a specific order provided as JSON string.")
    group.add_argument("--execute-recent-orders", action="store_true", help="Load recent orders (default: from the start of the hour) from DynamoDB and execute.")
    group.add_argument("--daemon", action="store_true", help="Listen to order messages continuously using SQS.")

    # Parse the command-line arguments
    args = parser.parse_args()

    # Determine which option was provided and call the appropriate function
    if args.execute_order:
        execute_order(args.execute_order)
    elif args.execute_recent_orders:
        execute_recent_orders()
    elif args.daemon:
        daemon_sqs()
    else:
        print(parser.print_help())

main()
