import time
import requests
from typing import Any


class WebhookSender:
    def __init__(self, webhook_uri: str):
        self.webhook_uri = webhook_uri

    def send(self, type: str, content: Any | None = None):
        payload = {
            "type": type,
            "timestamp": time.time(),
            "content": content,
        }

        try:
            response = requests.post(
                self.webhook_uri,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if response.status_code >= 200 and response.status_code < 300:
                print(f"Webhook sent successfully: {payload['event']}")
            else:
                print(
                    f"Failed to send webhook: HTTP {response.status_code} - {response.text}"
                )

        except Exception as e:
            print(f"Error sending webhook: {str(e)}")
