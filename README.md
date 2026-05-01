# DNS Round Robin Monitor

A lightweight Python application that continuously monitors a target DNS name, tracks the returned IP addresses, and provides a live-updating web interface to view the results.

This tool is particularly useful for tracking DNS Load Balancing (Round Robin) behavior, CDNs, or dynamic DNS changes. It records how many times each IP was returned as the "primary" (first) IP in the list and logs the last time each IP was seen.

## Features

* **Continuous Polling:** Runs a background thread to query DNS records at a fixed interval (default 5 seconds).
* **Live Web Dashboard:** A Flask-based UI that auto-refreshes every 2 seconds without reloading the page.
* **Persistent Storage:** Uses a local SQLite database (`dns_monitor.db`) so your data survives application restarts.
* **Production-Ready Server:** Uses `waitress` to serve the web interface securely and quietly.
* **Highly Configurable:** Control the target domain, listening port, host binding, and log verbosity via command-line arguments.

## Prerequisites

* Python 3.7 or higher
* `pip` (Python package installer)

## Installation

1. **Clone or download the repository** (or just save the `dns_monitor.py` file to a directory).
2. **Create a `requirements.txt` file** in the same directory with the following contents:

        Flask
        dnspython
        waitress

3. **Install the dependencies:**
   It is recommended to use a virtual environment, but you can install globally or locally:

        pip install -r requirements.txt

## Usage

Run the application from your terminal. By default, it monitors `id.trimble.com` and opens the web interface on localhost (`127.0.0.1`) port `7001`.

        python dns_monitor.py

### Command-Line Arguments

You can customize the application's behavior using the following flags:

| Argument | Short | Default | Description |
| :--- | :--- | :--- | :--- |
| `--domain` | `-d` | `id.trimble.com` | The target DNS name to monitor. |
| `--port` | `-p` | `7001` | The port for the web dashboard. |
| `--host` | | `127.0.0.1` | The interface to bind to (`0.0.0.0` for all network interfaces). |
| `--verbose` | `-v` | `False` | Enables detailed DNS query logs in the console. |

### Examples

**Monitor a different domain:**

        python dns_monitor.py -d example.com

**Allow other computers on your network to view the dashboard on port 8080:**

        python dns_monitor.py --host 0.0.0.0 -p 8080

**Run with detailed console logging:**

        python dns_monitor.py -v

## Viewing the Dashboard

Once the application is running, open your web browser and navigate to:
[http://127.0.0.1:7001](http://127.0.0.1:7001) *(or your custom host/port).*

The dashboard displays:
* **Current Session Uptime:** How long the script has been running.
* **IP Address:** All unique IPv4 addresses discovered for the domain.
* **Times Primary:** The number of times that specific IP was the *first* IP returned in the DNS response.
* **Last Seen:** The exact date and time the IP was most recently returned in any position by the DNS server.

## Database

Data is automatically saved to a local SQLite database file named `dns_monitor.db` in the same directory as the script. You can safely stop and start the application; your historical IP counts and "last seen" timestamps will be preserved.

To reset your data, simply delete or rename the `dns_monitor.db` file while the application is stopped.

## Running as a Linux Systemd Service

If you want the monitor to run continuously in the background and start automatically when your server boots, configure it as a `systemd` service.

1. Create a service file:

        sudo nano /etc/systemd/system/dns-monitor.service

2. Add the following configuration (update `User`, `WorkingDirectory`, and `ExecStart` to match your environment):

        [Unit]
        Description=DNS Round Robin Monitor Service
        After=network.target

        [Service]
        User=YOUR_USERNAME
        Group=YOUR_USERNAME
        WorkingDirectory=/path/to/your/app_directory
        ExecStart=/usr/bin/python3 /path/to/your/app_directory/dns_monitor.py --host 0.0.0.0 --port 7001
        Restart=always
        RestartSec=5
        Environment=PYTHONUNBUFFERED=1

        [Install]
        WantedBy=multi-user.target

3. Enable and start the service:

        sudo systemctl daemon-reload
        sudo systemctl enable dns-monitor
        sudo systemctl start dns-monitor

4. View the logs:

        sudo journalctl -u dns-monitor -f
