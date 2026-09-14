#!/usr/bin/env python3
"""
AI-SRE Engine - Production Grade
Autonomous Incident Response & Root Cause Analysis
Integrates: Prometheus, Alertmanager, Loki, Ollama, Rocket.Chat
"""

from flask import Flask, request, jsonify
import requests
import time
import subprocess
from datetime import datetime
import psutil
import json

app = Flask(__name__)

# ===================================
# CONFIGURATION
# ===================================

LOKI_URL = "http://loki:3100"
OLLAMA_URL = "http://ollama:11434/api/generate"
PROMETHEUS_URL = "http://prometheus:9090"
ROCKET_WEBHOOK = "http://rockerchat:3000/hooks/<WEBHOOK_ID>/<WEBHOOK_TOKEN>"

# ===================================
# LOGGING
# ===================================

def log_msg(msg):
    """Detailed logging"""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{ts}] [AI-SRE] {msg}", flush=True)

# ===================================
# ALERT SERVICE MAPPING
# ===================================

ALERT_SERVICE_MAP = {
    "ApacheDown": "apache2",
    "NginxDown": "nginx",
    "DockerDown": "docker",
    "NodeDown": "node_exporter",
    "PrometheusDown": "prometheus",
    "GrafanaDown": "grafana",
    "LokiDown": "loki",
    "RocketChatDown": "rocketchat",
    "ServiceDown": "unknown",
    "ContainerDown": "unknown",
    "HighCPU": "system",
    "HighMemory": "system",
    "OutOfMemory": "system",
    "DiskFull": "system",
    "DiskCritical": "system",
    "LoadHigh": "system",
    "AlertmanagerDown": "alertmanager"
}

# ===================================
# LOKI QUERIES - UNIVERSAL
# ===================================

def get_loki_query_for_service(service_name):
    """Generate Loki query for any service (universal)"""
    queries = [
        # Try exact service name with unit label
        f'{{unit="{service_name}.service"}}',
        # Try service name variations
        f'{{service="{service_name}"}}',
        f'{{container_name="{service_name}"}}',
        # Try docker logs
        f'{{job="docker"}} |= "{service_name}"',
        # Try host logs
        f'{{job="syslog"}} |= "{service_name}"',
        # Fallback: any logs mentioning service
        f'|= "{service_name}"',
    ]
    return queries

# ===================================
# SYSTEM DIAGNOSTICS
# ===================================

def run_cmd(cmd):
    """Run shell command safely"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout[:1000] if result.stdout else result.stderr[:1000]
    except Exception as e:
        return f"Error: {str(e)[:200]}"

def get_system_metrics():
    """Get current system state"""
    try:
        return {
            'cpu': round(psutil.cpu_percent(interval=1), 1),
            'memory': round(psutil.virtual_memory().percent, 1),
            'disk': round(psutil.disk_usage('/').percent, 1),
            'load': round(psutil.getloadavg()[0], 2),
            'timestamp': datetime.now().isoformat()
        }
    except:
        return {'cpu': 0, 'memory': 0, 'disk': 0, 'load': 0}

def get_service_status(service_name):
    """Get systemd service status"""
    output = run_cmd(f"systemctl status {service_name} --no-pager -l 2>&1")
    return output[:500]

# ===================================
# LOKI LOG FETCHING - UNIVERSAL
# ===================================

def fetch_logs_from_loki(service_name, limit=50):
    """Fetch logs from Loki - tries multiple query patterns"""
    try:
        log_msg(f"Fetching logs for: {service_name}")
        
        queries = get_loki_query_for_service(service_name)
        
        end_ns = int(time.time() * 1_000_000_000)
        start_ns = end_ns - (24 * 60 * 60 * 1_000_000_000)  # 24 hours
        
        for query in queries:
            try:
                log_msg(f"  Trying: {query}")
                
                response = requests.get(
                    f"{LOKI_URL}/loki/api/v1/query_range",
                    params={
                        "query": query,
                        "start": start_ns,
                        "end": end_ns,
                        "limit": limit,
                        "direction": "backward"
                    },
                    timeout=15
                )
                
                if response.status_code != 200:
                    continue
                
                data = response.json()
                results = data.get("data", {}).get("result", [])
                
                if results:
                    logs = []
                    for stream in results:
                        for value in stream.get("values", []):
                            logs.append(value[1])
                    
                    if logs:
                        log_msg(f"  ✓ Found {len(logs)} log lines")
                        # Filter noise
                        filtered = []
                        noise = ['AH00558', 'AH0011', 'deprecated', 'INFO: Config', 'DEBUG']
                        for line in logs:
                            if not any(n in line for n in noise):
                                filtered.append(line)
                        return "\n".join(filtered[:limit]) if filtered else "\n".join(logs[:limit])
            except:
                continue
        
        log_msg(f"  ✗ No logs found")
        return "[No recent logs available]"
        
    except Exception as e:
        log_msg(f"Loki error: {e}")
        return f"[Loki error: {str(e)[:100]}]"

# ===================================
# AI ANALYSIS - PRODUCTION GRADE
# ===================================

def analyze_with_ollama(alert_name, service_name, severity, summary, description, impact, logs, metrics, status_info):
    """Production-grade SRE analysis with Ollama"""
    
    prompt = f"""You are a Senior Site Reliability Engineer. Analyze this production incident.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 ALERT DETAILS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Alert: {alert_name}
Service: {service_name}
Severity: {severity}
Summary: {summary}
Description: {description}
Impact: {impact}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 CURRENT SYSTEM STATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CPU: {metrics.get('cpu', 0)}%
Memory: {metrics.get('memory', 0)}%
Disk: {metrics.get('disk', 0)}%
Load: {metrics.get('load', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔧 SERVICE STATUS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{status_info[:500]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 RECENT LOGS (Last 24 hours)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{logs[:800]}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROVIDE ANALYSIS IN THIS FORMAT:

🔴 ROOT CAUSE:
[What caused this? Only if supported by evidence in logs]

📊 EVIDENCE:
[Quote specific error messages from logs]

💼 BUSINESS IMPACT:
[What services/users affected]

🔍 CONFIDENCE:
[HIGH if clear logs | MEDIUM if partial | LOW if no evidence]

🔧 IMMEDIATE ACTIONS:
1. [Action 1 with command]
2. [Action 2 with command]
3. [Action 3 with command]

🛡️ PREVENTION:
1. [How to prevent]
2. [Monitoring to add]
3. [Documentation needed]

Be CONCISE. Use BULLET POINTS. Quote actual errors from logs.
"""

    try:
        log_msg(f"Sending to Ollama for analysis (timeout: 120s)...")
        
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": "gemma3:4b",
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 1024,
                    "top_p": 0.9
                }
            },
            timeout=120
        )
        
        if response.status_code == 200:
            analysis = response.json().get("response", "")
            log_msg("✓ Ollama analysis completed")
            return analysis
        else:
            log_msg(f"✗ Ollama returned {response.status_code}")
            return f"[Analysis unavailable: HTTP {response.status_code}]"
            
    except requests.exceptions.Timeout:
        log_msg("✗ Ollama timeout (model still loading)")
        return "[⏳ Analysis in progress - model is loading. Usually takes 30-120s on first run.]"
    except Exception as e:
        log_msg(f"✗ Ollama error: {e}")
        return f"[Analysis error: {str(e)[:100]}]"

# ===================================
# ROCKET.CHAT INTEGRATION
# ===================================

def send_rocket_message(message):
    """Send to Rocket.Chat"""
    try:
        log_msg("Sending to Rocket.Chat...")
        response = requests.post(ROCKET_WEBHOOK, json={"text": message}, timeout=10)
        if response.status_code == 200:
            log_msg("✓ Message sent to Rocket.Chat")
            return True
        else:
            log_msg(f"✗ Rocket.Chat: {response.status_code}")
            return False
    except Exception as e:
        log_msg(f"✗ Rocket.Chat error: {e}")
        return False

# ===================================
# WEBHOOK HANDLER - MAIN
# ===================================

@app.route("/webhook", methods=["POST"])
def webhook():
    """Main webhook - receives alerts from Alertmanager"""
    try:
        log_msg("="*70)
        log_msg("🔔 WEBHOOK RECEIVED FROM ALERTMANAGER")
        log_msg("="*70)
        
        data = request.json
        if not data:
            log_msg("❌ No JSON payload")
            return jsonify({"error": "No data"}), 400
        
        alerts = data.get("alerts", [])
        log_msg(f"Total alerts: {len(alerts)}")
        
        processed = 0
        
        for alert in alerts:
            try:
                log_msg("-"*70)
                
                # Extract alert metadata
                labels = alert.get("labels", {})
                annotations = alert.get("annotations", {})
                status = alert.get("status", "firing")
                
                alertname = labels.get("alertname", "Unknown")
                severity = labels.get("severity", "unknown")
                instance = labels.get("instance", "unknown")
                
                summary = annotations.get("summary", "Alert fired")
                description = annotations.get("description", "No description")
                impact = annotations.get("impact", "Service affected")
                runbook = annotations.get("runbook", "")
                
                log_msg(f"Alert: {alertname}")
                log_msg(f"Severity: {severity}")
                log_msg(f"Status: {status}")
                log_msg(f"Instance: {instance}")
                
                # ========== RESOLVED ALERT ==========
                if status == "resolved":
                    log_msg("Status: RESOLVED - sending recovery message")
                    
                    msg = f"""✅ **INCIDENT RESOLVED**

Alert: {alertname}
Status: ✓ RESOLVED
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Service is back to normal operation.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
                    send_rocket_message(msg)
                    processed += 1
                    log_msg("✓ Processed (resolved alert)")
                    continue
                
                # ========== FIRING ALERT ==========
                log_msg("Status: FIRING - analyzing incident...")
                
                # Map alert to service
                service_name = ALERT_SERVICE_MAP.get(alertname, alertname.lower().replace("down", "").strip())
                log_msg(f"Service: {service_name}")
                
                # Step 1: Get metrics
                log_msg("Step 1: Collecting system metrics...")
                metrics = get_system_metrics()
                log_msg(f"  CPU: {metrics['cpu']}% | Memory: {metrics['memory']}% | Disk: {metrics['disk']}%")
                
                # Step 2: Get service status
                log_msg(f"Step 2: Getting service status...")
                status_info = get_service_status(service_name)
                log_msg(f"  Status retrieved ({len(status_info)} chars)")
                
                # Step 3: Fetch logs from Loki
                log_msg(f"Step 3: Fetching logs from Loki...")
                logs = fetch_logs_from_loki(service_name, limit=50)
                log_msg(f"  Logs retrieved ({len(logs)} chars)")
                
                # Step 4: AI Analysis
                log_msg(f"Step 4: Running AI analysis...")
                analysis = analyze_with_ollama(
                    alertname, service_name, severity,
                    summary, description, impact,
                    logs, metrics, status_info
                )
                log_msg(f"  Analysis completed ({len(analysis)} chars)")
                
                # Step 5: Format message
                log_msg(f"Step 5: Formatting Rocket.Chat message...")
                rocket_msg = f"""🚨 **CRITICAL ALERT**: {alertname}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Service: {service_name}
⚠️  Severity: {severity.upper()}
🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📍 Instance: {instance}

Summary: {summary}
Description: {description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 CURRENT SYSTEM STATE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• CPU: {metrics['cpu']}%  |  Memory: {metrics['memory']}%  |  Disk: {metrics['disk']}%
• Load: {metrics['load']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 AI-POWERED RCA ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{analysis}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 DIAGNOSTIC COMMANDS TO RUN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. systemctl status {service_name}
2. journalctl -u {service_name} -n 50 --no-pager
3. docker ps -a | grep {service_name}
4. ps aux | grep {service_name}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📢 NEXT STEPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Acknowledge this alert
✓ Run diagnostic commands above
✓ Follow RCA recommendations
✓ Update incident status
✓ Escalate if not resolved in 15 minutes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
                
                # Step 6: Send message
                log_msg(f"Step 6: Sending to Rocket.Chat...")
                success = send_rocket_message(rocket_msg)
                
                if success:
                    processed += 1
                    log_msg("✓ Alert fully processed")
                else:
                    log_msg("⚠️  Alert analyzed but message send failed")
                
            except Exception as e:
                log_msg(f"❌ Error processing alert: {e}")
                import traceback
                log_msg(traceback.format_exc()[:500])
                continue
        
        log_msg("="*70)
        log_msg(f"✓ WEBHOOK COMPLETE: {processed}/{len(alerts)} alerts processed")
        log_msg("="*70)
        
        return jsonify({"status": "processed", "count": processed}), 200
        
    except Exception as e:
        log_msg(f"❌ WEBHOOK ERROR: {e}")
        import traceback
        log_msg(traceback.format_exc()[:500])
        return jsonify({"error": str(e)}), 500

# ===================================
# HEALTH ENDPOINTS
# ===================================

@app.route("/", methods=["GET"])
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "service": "AI-SRE Engine",
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route("/health/deep", methods=["GET"])
def deep_health():
    """Check all components"""
    log_msg("Deep health check")
    
    health = {
        "timestamp": datetime.now().isoformat(),
        "components": {}
    }
    
    # Check each component
    components = {
        "loki": (f"{LOKI_URL}/ready", 200),
        "ollama": (f"{OLLAMA_URL.replace('/api/generate', '')}/api/tags", 200),
        "prometheus": (f"{PROMETHEUS_URL}/-/healthy", 200),
        "rocketchat": ("http://rocketchat:3000/api/info", 200)
    }
    
    for name, (url, expected_code) in components.items():
        try:
            r = requests.get(url, timeout=5)
            health["components"][name] = "healthy" if r.status_code == expected_code else "unhealthy"
        except:
            health["components"][name] = "unreachable"
    
    overall = "healthy" if all(c == "healthy" for c in health["components"].values()) else "degraded"
    health["overall_status"] = overall
    
    return jsonify(health), 200

# ===================================
# STARTUP
# ===================================

if __name__ == "__main__":
    log_msg("="*70)
    log_msg("🚀 AI-SRE ENGINE v3 - PRODUCTION MODE")
    log_msg("="*70)
    log_msg(f"Loki: {LOKI_URL}")
    log_msg(f"Ollama: {OLLAMA_URL}")
    log_msg(f"Prometheus: {PROMETHEUS_URL}")
    log_msg(f"Rocket.Chat: Configured")
    log_msg("="*70)
    log_msg("Ready to receive alerts from Alertmanager!")
    log_msg("="*70)
    
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
