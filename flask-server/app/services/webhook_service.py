# flask-server/app/services/webhook_service.py
import requests
import json
import hmac
import hashlib
from typing import Dict, List, Optional, Any, Callable
from flask import current_app, request
from datetime import datetime, timezone
from dataclasses import dataclass
import asyncio
import threading
from enum import Enum
import time
from concurrent.futures import ThreadPoolExecutor

class WebhookEventType(Enum):
    """Webhook event types"""

    SNIPPET_CREATED = "snippet.created"
    SNIPPET_UPDATED = "snippet.updated"
    SNIPPET_DELETED = "snippet.deleted"
    COLLECTION_CREATED = "collection.created"
    COLLECTION_UPDATED = "collection.updated"
    COLLECTION_DELETED = "collection.deleted"
    USER_REGISTERED = "user.registered"
    TEAM_CREATED = "team.created"
    TEAM_MEMBER_ADDED = "team.member_added"
    TEAM_MEMBER_REMOVED = "team.member_removed"


@dataclass
class WebhookEndpoint:
    """Webhook endpoint configuration"""

    id: str
    url: str
    secret: str
    events: List[str]
    active: bool
    user_id: int
    team_id: Optional[int] = None
    created_at: datetime = None
    updated_at: datetime = None


@dataclass
class WebhookPayload:
    """Webhook payload structure"""

    event: str
    timestamp: str
    data: Dict[str, Any]
    user_id: int
    team_id: Optional[int] = None


class WebhookService:
    """Webhook service for external integrations and automation"""

    def __init__(self):
        self.endpoints: Dict[str, WebhookEndpoint] = {}
        self.retry_attempts = 3
        self.retry_delay = 1  # seconds
        self.timeout = 30  # seconds
        self._executor = ThreadPoolExecutor(max_workers=10)

    def register_webhook(
        self,
        user_id: int,
        url: str,
        events: List[str],
        secret: str = None,
        team_id: int = None,
    ) -> str:
        """Register a new webhook endpoint"""
        import uuid

        webhook_id = str(uuid.uuid4())

        # Generate secret if not provided
        if not secret:
            secret = self._generate_secret()

        endpoint = WebhookEndpoint(
            id=webhook_id,
            url=url,
            secret=secret,
            events=events,
            active=True,
            user_id=user_id,
            team_id=team_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        self.endpoints[webhook_id] = endpoint

        # Log webhook registration
        current_app.logger.info(f"Webhook registered: {webhook_id} for user {user_id}")

        return webhook_id

    def update_webhook(
        self,
        webhook_id: str,
        url: str = None,
        events: List[str] = None,
        active: bool = None,
    ) -> bool:
        """Update existing webhook endpoint"""
        if webhook_id not in self.endpoints:
            return False

        endpoint = self.endpoints[webhook_id]

        if url:
            endpoint.url = url
        if events is not None:
            endpoint.events = events
        if active is not None:
            endpoint.active = active

        endpoint.updated_at = datetime.now(timezone.utc)

        return True

    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete webhook endpoint"""
        if webhook_id in self.endpoints:
            del self.endpoints[webhook_id]
            current_app.logger.info(f"Webhook deleted: {webhook_id}")
            return True
        return False

    def get_user_webhooks(self, user_id: int) -> List[WebhookEndpoint]:
        """Get all webhooks for a user"""
        return [
            endpoint
            for endpoint in self.endpoints.values()
            if endpoint.user_id == user_id
        ]

    def get_team_webhooks(self, team_id: int) -> List[WebhookEndpoint]:
        """Get all webhooks for a team"""
        return [
            endpoint
            for endpoint in self.endpoints.values()
            if endpoint.team_id == team_id
        ]

    def trigger_webhook(
        self,
        event_type: WebhookEventType,
        data: Dict[str, Any],
        user_id: int,
        team_id: int = None,
    ) -> None:
        """Trigger webhook for specific event"""
        event_name = event_type.value

        # Find matching webhooks
        matching_webhooks = []
        for endpoint in self.endpoints.values():
            if not endpoint.active:
                continue

            # Check if event matches
            if event_name not in endpoint.events and "*" not in endpoint.events:
                continue

            # Check user/team scope
            if team_id and endpoint.team_id == team_id:
                matching_webhooks.append(endpoint)
            elif endpoint.user_id == user_id and not endpoint.team_id:
                matching_webhooks.append(endpoint)

        # Send webhooks asynchronously
        if matching_webhooks:
            payload = WebhookPayload(
                event=event_name,
                timestamp=datetime.now(timezone.utc).isoformat(),
                data=data,
                user_id=user_id,
                team_id=team_id,
            )

            for endpoint in matching_webhooks:
                self._executor.submit(self._send_webhook, endpoint, payload)

    def _send_webhook(self, endpoint: WebhookEndpoint, payload: WebhookPayload) -> None:
        """Send webhook with retry logic"""
        payload_dict = {
            "event": payload.event,
            "timestamp": payload.timestamp,
            "data": payload.data,
            "user_id": payload.user_id,
            "team_id": payload.team_id,
        }

        payload_json = json.dumps(payload_dict, default=str)
        signature = self._generate_signature(payload_json, endpoint.secret)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": payload.event,
            "X-Webhook-Timestamp": payload.timestamp,
            "User-Agent": "SnippetManager-Webhooks/1.0",
        }

        for attempt in range(self.retry_attempts):
            try:
                response = requests.post(
                    endpoint.url,
                    data=payload_json,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code in [200, 201, 202, 204]:
                    current_app.logger.info(
                        f"Webhook sent successfully: {endpoint.id} "
                        f"(attempt {attempt + 1})"
                    )
                    self._log_webhook_delivery(
                        endpoint.id, payload.event, True, response.status_code
                    )
                    return
                else:
                    current_app.logger.warning(
                        f"Webhook failed with status {response.status_code}: "
                        f"{endpoint.id} (attempt {attempt + 1})"
                    )

            except requests.exceptions.RequestException as e:
                current_app.logger.error(
                    f"Webhook request failed: {endpoint.id} "
                    f"(attempt {attempt + 1}) - {str(e)}"
                )

            # Wait before retry (exponential backoff)
            if attempt < self.retry_attempts - 1:
                time.sleep(self.retry_delay * (2**attempt))

        # All attempts failed
        current_app.logger.error(
            f"Webhook delivery failed after {self.retry_attempts} attempts: "
            f"{endpoint.id}"
        )
        self._log_webhook_delivery(endpoint.id, payload.event, False, 0)

    def verify_webhook_signature(
        self, payload: str, signature: str, secret: str
    ) -> bool:
        """Verify incoming webhook signature"""
        expected_signature = self._generate_signature(payload, secret)
        return hmac.compare_digest(signature, expected_signature)

    def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Test webhook endpoint with a ping event"""
        if webhook_id not in self.endpoints:
            return {"success": False, "error": "Webhook not found"}

        endpoint = self.endpoints[webhook_id]

        test_payload = WebhookPayload(
            event="ping",
            timestamp=datetime.now(timezone.utc).isoformat(),
            data={"message": "This is a test webhook from Snippet Manager"},
            user_id=endpoint.user_id,
            team_id=endpoint.team_id,
        )

        try:
            payload_dict = {
                "event": test_payload.event,
                "timestamp": test_payload.timestamp,
                "data": test_payload.data,
                "user_id": test_payload.user_id,
                "team_id": test_payload.team_id,
            }

            payload_json = json.dumps(payload_dict, default=str)
            signature = self._generate_signature(payload_json, endpoint.secret)

            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Event": "ping",
                "X-Webhook-Timestamp": test_payload.timestamp,
                "User-Agent": "SnippetManager-Webhooks/1.0",
            }

            response = requests.post(
                endpoint.url, data=payload_json, headers=headers, timeout=self.timeout
            )

            return {
                "success": response.status_code in [200, 201, 202, 204],
                "status_code": response.status_code,
                "response_time": response.elapsed.total_seconds(),
                "response_headers": dict(response.headers),
                "response_body": response.text[:1000],  # Limit response body
            }

        except requests.exceptions.RequestException as e:
            return {"success": False, "error": str(e)}

    def get_webhook_logs(self, webhook_id: str, limit: int = 50) -> List[Dict]:
        """Get webhook delivery logs"""
        # In a real implementation, this would query a database
        # For now, return mock data structure
        return []

    def create_webhook_url(
        self, endpoint_type: str, user_id: int, params: Dict[str, str] = None
    ) -> str:
        """Create webhook URL for specific integrations"""
        base_url = current_app.config.get("BASE_URL", "http://localhost:5000")
        webhook_url = f"{base_url}/api/webhooks/{endpoint_type}"

        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            webhook_url += f"?{query_string}"

        return webhook_url

    # Integration-specific webhook handlers

    def handle_github_webhook(
        self, payload: Dict[str, Any], signature: str
    ) -> Dict[str, Any]:
        """Handle incoming GitHub webhook"""
        # Verify GitHub signature
        secret = current_app.config.get("GITHUB_WEBHOOK_SECRET", "")
        if not self.verify_github_signature(json.dumps(payload), signature, secret):
            return {"error": "Invalid signature"}

        event_type = payload.get("action")
        repository = payload.get("repository", {})

        # Process different GitHub events
        if event_type == "created" and "gist" in payload:
            return self._handle_gist_created(payload)
        elif event_type == "push":
            return self._handle_repo_push(payload)

        return {"message": "Event processed"}

    def handle_slack_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming Slack webhook/slash command"""
        command = payload.get("command")
        text = payload.get("text", "")
        user_id = payload.get("user_id")

        if command == "/snippets":
            return self._handle_slack_snippets_command(text, user_id)
        elif command == "/save-snippet":
            return self._handle_slack_save_command(text, user_id)

        return {"text": "Unknown command"}

    def _generate_secret(self) -> str:
        """Generate webhook secret"""
        import secrets

        return secrets.token_urlsafe(32)

    def _generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook payload"""
        signature = hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"

    def verify_github_signature(
        self, payload: str, signature: str, secret: str
    ) -> bool:
        """Verify GitHub webhook signature"""
        expected_signature = hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha1
        ).hexdigest()
        expected_signature = f"sha1={expected_signature}"
        return hmac.compare_digest(signature, expected_signature)

    def _log_webhook_delivery(
        self, webhook_id: str, event: str, success: bool, status_code: int
    ) -> None:
        """Log webhook delivery attempt"""
        # In a real implementation, this would save to database
        log_entry = {
            "webhook_id": webhook_id,
            "event": event,
            "success": success,
            "status_code": status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        current_app.logger.info(f"Webhook delivery log: {json.dumps(log_entry)}")

    def _handle_gist_created(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GitHub gist created event"""
        # Extract gist information and potentially auto-import
        gist = payload.get("gist", {})
        return {
            "message": f"Gist created: {gist.get('id')}",
            "auto_import_available": True,
        }

    def _handle_repo_push(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GitHub repository push event"""
        commits = payload.get("commits", [])
        return {
            "message": f"Repository updated with {len(commits)} commits",
            "sync_available": True,
        }

    def _handle_slack_snippets_command(self, text: str, user_id: str) -> Dict[str, Any]:
        """Handle Slack /snippets command"""
        # In a real implementation, this would query user's snippets
        return {
            "response_type": "ephemeral",
            "text": f"Here are your recent snippets...\n(Implementation needed for user: {user_id})",
        }

    def _handle_slack_save_command(self, text: str, user_id: str) -> Dict[str, Any]:
        """Handle Slack /save-snippet command"""
        # Parse text to extract snippet information
        return {
            "response_type": "ephemeral",
            "text": f"Snippet saved: {text[:50]}...\n(Implementation needed for user: {user_id})",
        }


# Global webhook service instance
webhook_service = WebhookService()


# Convenience functions for triggering webhooks
def trigger_snippet_created(snippet_data: Dict, user_id: int, team_id: int = None):
    """Trigger webhook for snippet creation"""
    webhook_service.trigger_webhook(
        WebhookEventType.SNIPPET_CREATED, snippet_data, user_id, team_id
    )


def trigger_snippet_updated(snippet_data: Dict, user_id: int, team_id: int = None):
    """Trigger webhook for snippet update"""
    webhook_service.trigger_webhook(
        WebhookEventType.SNIPPET_UPDATED, snippet_data, user_id, team_id
    )


def trigger_snippet_deleted(snippet_id: str, user_id: int, team_id: int = None):
    """Trigger webhook for snippet deletion"""
    webhook_service.trigger_webhook(
        WebhookEventType.SNIPPET_DELETED, {"snippet_id": snippet_id}, user_id, team_id
    )


def trigger_collection_created(
    collection_data: Dict, user_id: int, team_id: int = None
):
    """Trigger webhook for collection creation"""
    webhook_service.trigger_webhook(
        WebhookEventType.COLLECTION_CREATED, collection_data, user_id, team_id
    )


def trigger_collection_updated(
    collection_data: Dict, user_id: int, team_id: int = None
):
    """Trigger webhook for collection update"""
    webhook_service.trigger_webhook(
        WebhookEventType.COLLECTION_UPDATED, collection_data, user_id, team_id
    )


def trigger_collection_deleted(collection_id: str, user_id: int, team_id: int = None):
    """Trigger webhook for collection deletion"""
    webhook_service.trigger_webhook(
        WebhookEventType.COLLECTION_DELETED,
        {"collection_id": collection_id},
        user_id,
        team_id,
    )


def trigger_user_registered(user_data: Dict, user_id: int):
    """Trigger webhook for user registration"""
    webhook_service.trigger_webhook(
        WebhookEventType.USER_REGISTERED, user_data, user_id
    )


def trigger_team_created(team_data: Dict, user_id: int, team_id: int):
    """Trigger webhook for team creation"""
    webhook_service.trigger_webhook(
        WebhookEventType.TEAM_CREATED, team_data, user_id, team_id
    )


def trigger_team_member_added(member_data: Dict, user_id: int, team_id: int):
    """Trigger webhook for team member addition"""
    webhook_service.trigger_webhook(
        WebhookEventType.TEAM_MEMBER_ADDED, member_data, user_id, team_id
    )


def trigger_team_member_removed(member_data: Dict, user_id: int, team_id: int):
    """Trigger webhook for team member removal"""
    webhook_service.trigger_webhook(
        WebhookEventType.TEAM_MEMBER_REMOVED, member_data, user_id, team_id
    )
