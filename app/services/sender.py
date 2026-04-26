from __future__ import annotations

import base64
import email.mime.application
import email.mime.multipart
import email.mime.text
from typing import Any

import httpx

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailSendError(Exception):
    """Raised when Gmail API returns a non-2xx response."""


class GmailSender:
    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    def build_message(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        pdf_bytes: bytes | None = None,
    ) -> email.mime.multipart.MIMEMultipart:
        """
        Build MIME message. Set From, To, Subject headers. Attach body as text/plain.
        If pdf_bytes is provided, attach as application/pdf named "resume.pdf".
        """
        msg = email.mime.multipart.MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = subject

        text_part = email.mime.text.MIMEText(body, "plain", "utf-8")
        msg.attach(text_part)

        if pdf_bytes is not None:
            pdf_part = email.mime.application.MIMEApplication(pdf_bytes, _subtype="pdf")
            pdf_part.add_header("Content-Disposition", "attachment", filename="resume.pdf")
            msg.attach(pdf_part)

        return msg

    def send_email(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        pdf_bytes: bytes | None = None,
    ) -> dict:
        """Build MIME, base64url-encode, POST to Gmail API. Return response dict."""
        mime_msg = self.build_message(from_addr, to_addr, subject, body, pdf_bytes)
        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()

        with httpx.Client() as client:
            response = client.post(
                GMAIL_SEND_URL,
                json={"raw": raw},
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

        if response.status_code >= 400:
            raise GmailSendError(
                f"Gmail API error: {response.status_code} {response.text}"
            )

        return response.json()

    async def send(
        self,
        from_addr: str,
        to_addr: str,
        subject: str,
        body: str,
        pdf_bytes: bytes | None = None,
    ) -> str:
        """Build MIME, base64url-encode, POST to Gmail API. Return message ID."""
        mime_msg = self.build_message(from_addr, to_addr, subject, body, pdf_bytes)
        raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                GMAIL_SEND_URL,
                json={"raw": raw},
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

        if response.status_code >= 400:
            raise GmailSendError(
                f"Gmail API error: {response.status_code} {response.text}"
            )

        return response.json()["id"]


async def _get_approved_drafts(session: Any) -> list[tuple[str, dict]]:
    """Query DB for (application_id, draft_dict) pairs where application.status == APPROVED."""
    from sqlalchemy import select
    from app.models.application import Application, ApplicationStatus
    from app.models.draft import Draft

    result = await session.execute(
        select(Application, Draft)
        .join(Draft, Draft.application_id == Application.id)
        .where(Application.status == ApplicationStatus.APPROVED)
    )
    rows = result.all()
    return [
        (
            str(app.id),
            {
                "id": str(draft.id),
                "application_id": str(draft.application_id),
                "resume_md": draft.resume_md,
                "cover_letter_md": draft.cover_letter_md,
                "email_subject": draft.email_subject,
                "email_body": draft.email_body,
                "model_used": draft.model_used,
                "prompt_version": draft.prompt_version,
            },
        )
        for app, draft in rows
    ]


async def _send_one(application_id: str, draft: Any, _session: Any) -> None:
    """Send one draft. Used internally; tests patch this."""
    subject = draft.get("email_subject", "") if isinstance(draft, dict) else ""
    body = draft.get("email_body", "") if isinstance(draft, dict) else ""
    sender = GmailSender(access_token="")
    await sender.send(
        from_addr="",
        to_addr="",
        subject=subject or "",
        body=body or "",
    )


async def process_send_queue(session: Any) -> int:
    """
    Fetch APPROVED drafts via _get_approved_drafts.
    For each: call _send_one.
    Return count of drafts processed.
    """
    drafts = await _get_approved_drafts(session)
    count = 0
    for application_id, draft in drafts:
        await _send_one(application_id, draft, session)
        count += 1
    return count
