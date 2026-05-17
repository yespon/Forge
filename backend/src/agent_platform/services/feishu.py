"""Feishu (Lark) SDK wrapper for sending notifications.

This module provides a client for interacting with Feishu APIs,
sending messages, and handling OAuth authentication.
"""

import base64
import hashlib
import hmac
import json
import time as time_module
from typing import Any, Optional

import httpx

from agent_platform.config import get_settings


class FeishuError(Exception):
    """Feishu API error."""

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        response: Optional[dict] = None,
    ):
        super().__init__(message)
        self.code = code
        self.response = response

    def __str__(self) -> str:
        if self.code:
            return f"[FeishuError {self.code}] {super().__str__()}"
        return super().__str__()


class FeishuClient:
    """Feishu API client.

    Provides methods for sending messages, managing users, and
    handling webhook events.
    """

    BASE_URL = "https://open.feishu.cn/open-apis"
    TOKEN_URL = f"{BASE_URL}/auth/v3/tenant_access_token/internal"
    USER_BATCH_GET_URL = f"{BASE_URL}/contact/v3/users/batch_get_id"
    USER_GET_URL = f"{BASE_URL}/contact/v3/users"

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        bot_webhook: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """Initialize Feishu client.

        Args:
            app_id: Feishu app ID (defaults to settings)
            app_secret: Feishu app secret (defaults to settings)
            bot_webhook: Bot webhook URL for sending messages
            timeout: HTTP request timeout in seconds
        """
        settings = get_settings()

        self.app_id = app_id or getattr(settings, "FEISHU_APP_ID", None)
        self.app_secret = app_secret or getattr(settings, "FEISHU_APP_SECRET", None)
        self.bot_webhook = bot_webhook or getattr(settings, "FEISHU_BOT_WEBHOOK", None)
        self.timeout = timeout

        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def _ensure_token(self) -> str:
        """Ensure access token is valid, refresh if needed.

        Returns:
            Valid access token

        Raises:
            FeishuError: If token refresh fails
        """
        # Check if token is still valid (with 60s buffer)
        if self._access_token and time_module.time() < (self._token_expires_at - 60):
            return self._access_token

        # Refresh token
        await self._refresh_token()
        return self._access_token

    async def _refresh_token(self) -> None:
        """Refresh tenant access token.

        Raises:
            FeishuError: If token refresh fails
        """
        if not self.app_id or not self.app_secret:
            raise FeishuError(
                "Feishu app_id and app_secret are required for token refresh"
            )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.TOKEN_URL,
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret,
                },
            )

            result = response.json()

            if result.get("code") != 0:
                raise FeishuError(
                    f"Failed to get access token: {result.get('msg')}",
                    code=result.get("code"),
                    response=result,
                )

            self._access_token = result["tenant_access_token"]
            # Token typically expires in 7200 seconds (2 hours)
            expires_in = result.get("expire", 7200)
            self._token_expires_at = time_module.time() + expires_in

    async def _make_api_request(
        self,
        method: str,
        url: str,
        json_data: Optional[dict] = None,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        use_auth: bool = True,
    ) -> dict:
        """Make authenticated API request.

        Args:
            method: HTTP method
            url: Request URL
            json_data: JSON request body
            params: Query parameters
            headers: Additional headers
            use_auth: Whether to use authentication

        Returns:
            Response JSON as dictionary

        Raises:
            FeishuError: If request fails
        """
        request_headers = headers or {}

        if use_auth:
            token = await self._ensure_token()
            request_headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                json=json_data,
                params=params,
                headers=request_headers,
            )

            try:
                result = response.json()
            except json.JSONDecodeError:
                raise FeishuError(
                    f"Invalid JSON response: {response.text}",
                    response={"status_code": response.status_code, "text": response.text},
                )

            # Check for API errors
            if result.get("code") != 0:
                raise FeishuError(
                    result.get("msg", "Unknown error"),
                    code=result.get("code"),
                    response=result,
                )

            return result

    async def send_text(
        self,
        content: str,
        open_id: Optional[str] = None,
        email: Optional[str] = None,
        user_id: Optional[str] = None,
        webhook: Optional[str] = None,
    ) -> bool:
        """Send text message.

        Args:
            content: Message content
            open_id: Recipient's open_id
            email: Recipient's email (will lookup open_id)
            user_id: Recipient's user_id
            webhook: Custom webhook URL (uses default if not provided)

        Returns:
            True if message was sent successfully

        Raises:
            FeishuError: If send fails
        """
        # Determine recipient
        recipient_id = open_id
        if not recipient_id and email:
            recipient_id = await self.get_user_id_by_email(email)
            if not recipient_id:
                raise FeishuError(f"User not found for email: {email}")

        if not recipient_id and not webhook:
            raise FeishuError("No recipient specified (open_id, email, or webhook required)")

        # Build message payload
        if recipient_id:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": content,
                },
                "open_id": recipient_id,
            }
        else:
            # Group chat via webhook
            payload = {
                "msg_type": "text",
                "content": {
                    "text": content,
                },
            }

        # Send via webhook or API
        target_webhook = webhook or self.bot_webhook
        if target_webhook:
            return await self._send_via_webhook(target_webhook, payload)

        # TODO: Implement send via direct message API
        raise FeishuError("Direct message API not yet implemented")

    async def send_card(
        self,
        card: dict[str, Any],
        open_id: Optional[str] = None,
        email: Optional[str] = None,
        webhook: Optional[str] = None,
    ) -> bool:
        """Send interactive card message.

        Args:
            card: Card JSON data
            open_id: Recipient's open_id
            email: Recipient's email
            webhook: Custom webhook URL

        Returns:
            True if message was sent successfully

        Raises:
            FeishuError: If send fails
        """
        # Determine recipient
        recipient_id = open_id
        if not recipient_id and email:
            recipient_id = await self.get_user_id_by_email(email)
            if not recipient_id:
                raise FeishuError(f"User not found for email: {email}")

        # Build message payload
        payload = {
            "msg_type": "interactive",
            "card": card,
        }

        if recipient_id:
            payload["open_id"] = recipient_id

        # Send via webhook or API
        target_webhook = webhook or self.bot_webhook
        if target_webhook:
            return await self._send_via_webhook(target_webhook, payload)

        raise FeishuError("Webhook required for card messages")

    async def _send_via_webhook(
        self,
        webhook: str,
        payload: dict[str, Any],
    ) -> bool:
        """Send message via webhook.

        Args:
            webhook: Webhook URL
            payload: Message payload

        Returns:
            True if sent successfully

        Raises:
            FeishuError: If send fails
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                webhook,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            result = response.json()

            if result.get("code") != 0:
                raise FeishuError(
                    result.get("msg", "Unknown error"),
                    code=result.get("code"),
                    response=result,
                )

            return True

    async def get_user_id_by_email(self, email: str) -> Optional[str]:
        """Get Feishu user ID by email.

        Args:
            email: User's email address

        Returns:
            Feishu open_id or None if not found
        """
        try:
            result = await self._make_api_request(
                method="POST",
                url=self.USER_BATCH_GET_URL,
                json_data={
                    "emails": [email],
                },
            )

            user_list = result.get("data", {}).get("user_list", [])
            for user in user_list:
                if user.get("email") == email:
                    return user.get("user_id")

            return None
        except FeishuError:
            return None

    async def get_user_info(self, user_id: str) -> Optional[dict]:
        """Get user information by user ID.

        Args:
            user_id: Feishu user ID

        Returns:
            User info dictionary or None if not found
        """
        try:
            result = await self._make_api_request(
                method="GET",
                url=f"{self.USER_GET_URL}/{user_id}",
                params={"user_id_type": "open_id"},
            )
            return result.get("data", {}).get("user")
        except FeishuError:
            return None

    def verify_webhook_signature(
        self,
        signature: str,
        timestamp: str,
        body: str,
        secret: Optional[str] = None,
        nonce: Optional[str] = None,
    ) -> bool:
        """Verify webhook signature from Feishu.

        Feishu uses HMAC-SHA256 signature verification.

        Args:
            signature: Signature from X-Lark-Signature header
            timestamp: Timestamp from X-Lark-Request-Timestamp header
            body: Request body
            secret: Webhook secret (uses app_secret if not provided)
            nonce: Nonce from X-Lark-Request-Nonce header (optional)

        Returns:
            True if signature is valid
        """
        secret_key = secret or self.app_secret
        if not secret_key:
            return False

        try:
            # Build string to sign
            # Format: timestamp\nsecret or timestamp\nsecret\nbody
            if nonce:
                # Newer format with nonce
                string_to_sign = f"{timestamp}\n{nonce}\n{secret_key}\n{body}"
            else:
                # Legacy format
                string_to_sign = f"{timestamp}\n{secret_key}"

            # Calculate HMAC-SHA256
            hmac_code = hmac.new(
                string_to_sign.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()

            expected_signature = base64.b64encode(hmac_code).decode("utf-8")

            return hmac.compare_digest(expected_signature, signature)
        except Exception:
            return False

    def parse_event(self, body: str) -> dict[str, Any]:
        """Parse webhook event from Feishu.

        Args:
            body: Request body as string

        Returns:
            Parsed event dictionary

        Raises:
            FeishuError: If parsing fails
        """
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise FeishuError(f"Invalid JSON in webhook body: {e}")

    def decrypt_encrypt_field(
        self,
        encrypt: str,
        encrypt_key: str,
    ) -> dict[str, Any]:
        """Decrypt encrypted field from Feishu.

        Feishu may encrypt webhook payloads for security.

        Args:
            encrypt: Encrypted string
            encrypt_key: Encryption key

        Returns:
            Decrypted data as dictionary

        Raises:
            FeishuError: If decryption fails
        """
        try:
            # Decode base64
            cipher_text = base64.b64decode(encrypt)

            # Derive key using SHA256
            key = hashlib.sha256(encrypt_key.encode()).digest()

            # AES-256-CBC decryption
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend

            # IV is first 16 bytes
            iv = cipher_text[:16]
            ciphertext = cipher_text[16:]

            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()
            padded_data = decryptor.update(ciphertext) + decryptor.finalize()

            # Remove PKCS7 padding
            padding_length = padded_data[-1]
            data = padded_data[:-padding_length]

            return json.loads(data.decode("utf-8"))
        except Exception as e:
            raise FeishuError(f"Failed to decrypt: {e}")


# Singleton instance
_feishu_client: Optional[FeishuClient] = None


def get_feishu_client() -> FeishuClient:
    """Get or create Feishu client singleton.

    Returns:
        FeishuClient instance
    """
    global _feishu_client
    if _feishu_client is None:
        _feishu_client = FeishuClient()
    return _feishu_client


def set_feishu_client(client: FeishuClient) -> None:
    """Set Feishu client singleton (for testing).

    Args:
        client: FeishuClient instance
    """
    global _feishu_client
    _feishu_client = client
