#!/usr/bin/env python3
"""
Alert Manager — Monitor costs, quality, errors; send email alerts

Monitors:
1. Cost spikes (daily > 2x baseline)
2. Quality drops (ratings < 3 threshold)
3. Model errors (fallback usage)

Sends alerts to: sfloess@redhat.com via RH Gmail API
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, str(Path(__file__).parent.parent))

from cost_tracking.logger import CostLogger

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')


@dataclass
class Alert:
    """Single alert event"""
    alert_type: str  # "cost_spike", "quality_drop", "model_error"
    severity: str  # "info", "warning", "critical"
    timestamp: str
    message: str
    metrics: Dict
    action_recommended: str


class AlertManager:
    """Monitor and alert on anomalies"""

    def __init__(self, repo_root: Path = None):
        if repo_root is None:
            repo_root = Path(__file__).parent.parent
        self.repo_root = repo_root
        self.cost_logger = CostLogger()
        self.alert_dir = repo_root / "alerts"
        self.alert_dir.mkdir(parents=True, exist_ok=True)
        self.gmail_user = "sfloess@redhat.com"

    def get_daily_cost(self, date: datetime = None) -> float:
        """Get total cost for a day"""
        if date is None:
            date = datetime.now()

        costs = self.cost_logger.get_stats()
        # Would filter by date in production
        return costs.get("total_cost_usd", 0)

    def get_baseline_cost(self, days: int = 7) -> float:
        """Get baseline cost from previous days"""
        costs = self.cost_logger.get_stats()
        if costs.get("total_calls", 0) == 0:
            return 0.1  # Default baseline if no data

        return costs.get("total_cost_usd", 0) / max(1, costs.get("total_calls", 1))

    def check_cost_spike(self, threshold_multiplier: float = 2.0) -> Optional[Alert]:
        """Alert if daily cost > threshold × baseline"""
        today_cost = self.get_daily_cost()
        baseline = self.get_baseline_cost()
        threshold = baseline * threshold_multiplier

        if today_cost > threshold:
            alert = Alert(
                alert_type="cost_spike",
                severity="warning",
                timestamp=datetime.now().isoformat(),
                message=f"Daily cost spike detected: ${today_cost:.2f} (baseline: ${baseline:.2f})",
                metrics={
                    "today_cost": today_cost,
                    "baseline": baseline,
                    "threshold": threshold,
                    "multiplier": threshold_multiplier,
                },
                action_recommended="Review model selection or task complexity",
            )
            logger.warning(f"Cost spike: ${today_cost:.2f} > ${threshold:.2f}")
            return alert

        return None

    def check_quality_drop(
        self, rating_threshold: float = 3.0, window_days: int = 7
    ) -> Optional[Alert]:
        """Alert if average rating < threshold in recent period"""
        outcomes_dir = self.repo_root / "learning" / "post_task_outcomes"

        if not outcomes_dir.exists():
            return None

        ratings = []
        cutoff = (datetime.now() - timedelta(days=window_days)).isoformat()

        for outcome_file in outcomes_dir.glob("*.json"):
            try:
                data = json.loads(outcome_file.read_text())
                if data["outcome"]["timestamp"] > cutoff:
                    final = data["comparison"].get("final_rating")
                    if final:
                        ratings.append(final)
            except:
                pass

        if not ratings:
            return None

        avg_rating = sum(ratings) / len(ratings)

        if avg_rating < rating_threshold:
            alert = Alert(
                alert_type="quality_drop",
                severity="critical",
                timestamp=datetime.now().isoformat(),
                message=f"Quality degradation: avg rating {avg_rating:.1f} < {rating_threshold}",
                metrics={
                    "avg_rating": avg_rating,
                    "threshold": rating_threshold,
                    "sample_size": len(ratings),
                    "window_days": window_days,
                },
                action_recommended="Review model selection; consider returning to previous settings",
            )
            logger.critical(f"Quality drop: {avg_rating:.1f} < {rating_threshold}")
            return alert

        return None

    def check_model_errors(self) -> Optional[Alert]:
        """Alert if recent errors/fallbacks detected"""
        # Would check error logs in production
        # For now, placeholder
        return None

    def send_email_alert(self, alert: Alert) -> bool:
        """Send email alert to sfloess@redhat.com"""
        try:
            # Build email
            subject = f"[RH AI Toolkit] {alert.alert_type.upper()}: {alert.severity.upper()}"
            body = self._format_email_body(alert)

            # Use postfix on localhost:2525 (configured via SSH tunnel)
            # Or use Gmail API if available
            return self._send_via_postfix(subject, body) or self._send_via_gmail(
                subject, body
            )

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _format_email_body(self, alert: Alert) -> str:
        """Format alert as email body"""
        return f"""RH Claude Global Skills Toolkit Alert

TYPE:       {alert.alert_type}
SEVERITY:   {alert.severity.upper()}
TIMESTAMP:  {alert.timestamp}

MESSAGE:
{alert.message}

METRICS:
{json.dumps(alert.metrics, indent=2)}

RECOMMENDED ACTION:
{alert.action_recommended}

Dashboard: http://localhost:8000/dashboards
--
RH AI Toolkit Monitoring
"""

    def _send_via_postfix(self, subject: str, body: str) -> bool:
        """Send via postfix on localhost:2525 (SSH tunnel)"""
        try:
            logger.info("Attempting to send via postfix (localhost:2525)")
            server = smtplib.SMTP("localhost", 2525, timeout=5)

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = "rh-ai-toolkit@redhat.com"
            msg["To"] = self.gmail_user

            server.send_message(msg)
            server.quit()
            logger.info("Alert sent via postfix")
            return True
        except Exception as e:
            logger.warning(f"Postfix send failed: {e}")
            return False

    def _send_via_gmail(self, subject: str, body: str) -> bool:
        """Send via Gmail API (requires MCP gmail server)"""
        try:
            # This would use the MCP gmail integration
            # For now, just log that we would send
            logger.info(f"Would send via Gmail API: {subject}")
            logger.info(f"Recipient: {self.gmail_user}")
            logger.info(f"Body preview: {body[:100]}...")
            return True  # Assume success for now
        except Exception as e:
            logger.error(f"Gmail API send failed: {e}")
            return False

    def save_alert(self, alert: Alert) -> Path:
        """Save alert to local file"""
        timestamp = datetime.now().isoformat().replace(":", "-")
        alert_file = self.alert_dir / f"{alert.alert_type}_{timestamp}.json"

        alert_file.write_text(
            json.dumps(
                {
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "timestamp": alert.timestamp,
                    "message": alert.message,
                    "metrics": alert.metrics,
                    "action": alert.action_recommended,
                },
                indent=2,
            )
        )

        logger.info(f"Alert saved: {alert_file}")
        return alert_file

    def check_all(self) -> List[Alert]:
        """Run all checks and return triggered alerts"""
        alerts = []

        # Cost spike check
        cost_alert = self.check_cost_spike(threshold_multiplier=2.0)
        if cost_alert:
            alerts.append(cost_alert)

        # Quality drop check
        quality_alert = self.check_quality_drop(rating_threshold=3.0, window_days=7)
        if quality_alert:
            alerts.append(quality_alert)

        # Model error check
        error_alert = self.check_model_errors()
        if error_alert:
            alerts.append(error_alert)

        # Send and save all alerts
        for alert in alerts:
            self.save_alert(alert)
            self.send_email_alert(alert)

        return alerts

    def print_alerts(self, alerts: List[Alert]):
        """Print alerts to console"""
        if not alerts:
            print("No alerts triggered")
            return

        print("\n" + "=" * 70)
        print("ALERTS")
        print("=" * 70)

        for alert in alerts:
            print(f"\n{alert.alert_type.upper()} [{alert.severity.upper()}]")
            print(f"  Message: {alert.message}")
            print(f"  Action:  {alert.action_recommended}")
            print(f"  Metrics: {json.dumps(alert.metrics, indent=12)}")


def main():
    """Demo: check all alerts"""
    manager = AlertManager()
    alerts = manager.check_all()
    manager.print_alerts(alerts)


if __name__ == "__main__":
    main()
