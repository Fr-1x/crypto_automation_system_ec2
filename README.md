# Crypto Automation System for EC2

A Variant of the [Crypto Automation System by lukenew2](https://github.com/lukenew2/crypto_automation_system) for deployment on EC2. From the lambda function receiving trades, message passing through a queue notifies the server-side app.


### Queue setup

In the AWS management console or with the aws command, create a FIFO queue with the parameters below. Messages that cannot be delivered should be deleted after the MessageRetentionPeriod timeout, e.g., 3540 seconds.

```aws sqs create-queue --queue-name 'crypto_automation_system_queue.fifo' --attributes FifoQueue=true,MessageRetentionPeriod=3540```

Note URL of the queue such as: https://sqs.REGION.amazonaws.com/ID/crypto_automation_system_queue.fifo

### Server setup

- Clone the Crypto Automation System to the server.
- Create a virtual environment and activate it (see documentation).
- Install the requirements and configure the strategy according to the documentation.
- Create database tables and secrets according to the documentation.
- Replace app.py by ec2/app.py from this repository.
- In app.py, set the variables in the beginng of the script, including the queue URL.
- Run the script manually or automated, e.g., with cron or systemd.

#### Manual start

Activate virtual environment, e.g., source venv/bin/activate, and test trade execution:

```
python3 app.py --execute-order '{"time": "2024-12-07T16:00:10Z", "ticker": "BTCUSD", "order_action": "buy", "order_price": "99217.77", "order_comment": "long" }'
```

Start the app in daemon mode:

```
python3 app.py --daemon
```

#### Sysetemd

Setup a script that starts the app with logging. E.g., create run-daemon.sh, execute ```chmod +x run-daemon.sh``` to make it executable and set the following content with path adjustments as needed.

```
#!/bin/bash
cd /opt/crypto-automation
source /opt/crypto-automation/venv/bin/activate
date >> /opt/crypto-automation/crypto-automation.log
python3 -u app.py --daemon >> /opt/crypto-automation/crypto-automation.log 2>&1
```

Create a systemd service that starts the run script. Create the file /etc/systemd/system/crypto-automation.service as follows and adjust the path to run-daemon.sh, the working directory, user name and group name as needed.

```
[Unit]
Description=Trading
Wants=network-online.target
After=network-online.target

[Service]
User=ubuntu
Group=ubuntu
Type=simple
Restart=always
RestartSec=30
StandardOutput=null
WorkingDirectory=/opt/crypto-automation
ExecStart=/usr/bin/bash -c '/opt/crypto-automation/run-daemon.sh'

[Install]
WantedBy=multi-user.target
```

Reload systemd and enable the service:
```
sudo systemctl daemon-reload
sudo systemctl enable crypto-automation
```

Display the status with ```sudo systemctl status cc-automation```. Start or stop the service using ```sudo systemctl start crypto-automation``` or ```sudo systemctl stop crypto-automation```. Systemd will auto start the service after reboots.


### Chalice app

- Clone the Crypto Automation System to the server.
- Create a virtual environment and activate it (see documentation).
- Install the requirements.
- Replace app.py by chalice/app.py from this repository.
- Replace .chalice/config.json by chalice/.chalice/config.json.
- Replace .chalice/policy-prod.json by chalice/.chalice/policy-prod.json.
- Setup the variables in .chalice/config.json.
- Deploy the app using ```chalice --stage prod deploy```.

