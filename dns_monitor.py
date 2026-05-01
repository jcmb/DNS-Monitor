import time
import threading
import argparse
import sqlite3
import dns.resolver
from flask import Flask, jsonify, render_template_string
from datetime import datetime
from waitress import serve

# --- Configuration Defaults ---
TARGET_DOMAIN = "id.trimble.com"
POLL_INTERVAL = 5
DB_FILE = "dns_monitor.db"
VERBOSE = False

app = Flask(__name__)

# Track when the current session started
app_start_time = datetime.now()

# --- Database Setup ---
def init_db():
    """Initializes the SQLite database and creates the table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ip_stats (
            domain TEXT,
            ip_address TEXT,
            primary_count INTEGER DEFAULT 0,
            last_seen DATETIME,
            PRIMARY KEY (domain, ip_address)
        )
    ''')
    conn.commit()
    conn.close()

# --- Background Worker ---
def poll_dns():
    """Continuously queries DNS and updates the SQLite database."""
    while True:
        try:
            answers = dns.resolver.resolve(TARGET_DOMAIN, 'A')
            ips = [rdata.address for rdata in answers]
            
            if ips:
                primary_ip = ips[0]
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Open DB connection for this thread's operation
                conn = sqlite3.connect(DB_FILE, timeout=10)
                cursor = conn.cursor()
                
                for ip in ips:
                    is_primary = 1 if ip == primary_ip else 0
                    
                    # Upsert (Insert or Update) the IP record
                    cursor.execute('''
                        INSERT INTO ip_stats (domain, ip_address, primary_count, last_seen)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(domain, ip_address) DO UPDATE SET
                            primary_count = primary_count + ?,
                            last_seen = excluded.last_seen
                    ''', (TARGET_DOMAIN, ip, is_primary, now_str, is_primary))
                
                conn.commit()
                conn.close()
                
                # Only print to console if the verbose flag was passed
                if VERBOSE:
                    print(f"[{now_str}] Checked {TARGET_DOMAIN}. Primary: {primary_ip} (Total IPs: {len(ips)})")
                
        except Exception as e:
            if VERBOSE:
                print(f"DNS query failed for {TARGET_DOMAIN}: {e}")
        
        time.sleep(POLL_INTERVAL)

# --- Web UI / API ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>DNS Monitor: {{ domain }}</title>
    <style>
        body { font-family: sans-serif; margin: 40px; background-color: #f4f4f9; color: #333;}
        .container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 700px; margin: auto;}
        h1 { font-size: 1.5em; border-bottom: 2px solid #ddd; padding-bottom: 10px;}
        .stat { margin-bottom: 20px; font-size: 1.1em;}
        table { width: 100%; border-collapse: collapse; margin-top: 20px;}
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd;}
        th { background-color: #0056b3; color: white;}
        tr:hover { background-color: #f1f1f1;}
    </style>
</head>
<body>
    <div class="container">
        <h1>DNS Monitor: {{ domain }}</h1>
        <div class="stat"><strong>Current Session Uptime:</strong> <span id="uptime">Loading...</span></div>
        
        <table>
            <thead>
                <tr>
                    <th>IP Address</th>
                    <th>Times Primary</th>
                    <th>Last Seen</th>
                </tr>
            </thead>
            <tbody id="ip-table-body">
                <tr><td colspan="3">Waiting for data...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        function updateUI() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('uptime').innerText = data.uptime;
                    
                    const tbody = document.getElementById('ip-table-body');
                    tbody.innerHTML = '';
                    
                    if (data.ips.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="3">No IPs discovered yet.</td></tr>';
                        return;
                    }

                    data.ips.forEach(row => {
                        tbody.innerHTML += `<tr>
                            <td><strong>${row.ip}</strong></td>
                            <td>${row.primary_count}</td>
                            <td>${row.last_seen}</td>
                        </tr>`;
                    });
                });
        }

        updateUI();
        setInterval(updateUI, 2000);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Serves the main UI page."""
    return render_template_string(HTML_TEMPLATE, domain=TARGET_DOMAIN)

@app.route('/api/stats')
def stats():
    """API endpoint to fetch data from the SQLite database."""
    uptime_td = datetime.now() - app_start_time
    uptime_str = str(uptime_td).split('.')[0] 
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ip_address, primary_count, last_seen 
        FROM ip_stats 
        WHERE domain = ? 
        ORDER BY ip_address ASC
    ''', (TARGET_DOMAIN,))
    
    rows = cursor.fetchall()
    conn.close()
    
    ip_data = [
        {"ip": row["ip_address"], "primary_count": row["primary_count"], "last_seen": row["last_seen"]}
        for row in rows
    ]
    
    return jsonify({
        "uptime": uptime_str,
        "ips": ip_data
    })

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Monitor DNS Round Robin changes.")
    parser.add_argument("-d", "--domain", type=str, default="id.trimble.com", help="The target domain to monitor")
    parser.add_argument("-p", "--port", type=int, default=7001, help="The port to run the web UI on (default: 7001)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="The interface to bind to (default: 127.0.0.1)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable detailed logging in the console")
    args = parser.parse_args()

    # Apply arguments to global configuration
    TARGET_DOMAIN = args.domain
    WEB_PORT = args.port
    BIND_HOST = args.host
    VERBOSE = args.verbose

    init_db()

    poller_thread = threading.Thread(target=poll_dns, daemon=True)
    poller_thread.start()
    
    print(f"Data is being saved to local database: {DB_FILE}")
    print(f"Starting web UI for {TARGET_DOMAIN} on http://{BIND_HOST}:{WEB_PORT}")
    if not VERBOSE:
        print("Running in quiet mode. Use -v or --verbose to see DNS query logs.")
        
    # Using Waitress to serve the app eliminates the development server warning
    # and automatically suppresses the spammy HTTP access logs.
    serve(app, host=BIND_HOST, port=WEB_PORT)