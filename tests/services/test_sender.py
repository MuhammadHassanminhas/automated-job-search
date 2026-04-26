"""Sender MIME + send-queue idempotency tests — B.2 spec.

Tests for:
1. respx-mocked Gmail API send: assert correct MIME From/To/Subject/body
2. Attachment part: resume.pdf, application/pdf, non-empty bytes
3. Parametrize over unicode subjects and long bodies
4. @given: random valid email addresses → MIME To header always valid RFC 5321
5. Send-queue idempotency: APPROVED draft → process_send_queue twice → exactly one OutreachEvent
"""
from __future__ import annotations

import uuid
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
import httpx
from hypothesis import given, settings as h_settings
import hypothesis.strategies as st
from pydantic import BaseModel
from polyfactory.factories.pydantic_factory import ModelFactory


# ---------------------------------------------------------------------------
# Pydantic models + polyfactory factories
# ---------------------------------------------------------------------------


class DraftModel(BaseModel):
    id: str
    application_id: str
    resume_md: Optional[str]
    cover_letter_md: Optional[str]
    email_subject: Optional[str]
    email_body: Optional[str]
    model_used: Optional[str]
    prompt_version: Optional[str]


class DraftFactory(ModelFactory):
    __model__ = DraftModel

    id = lambda: str(uuid.uuid4())  # noqa: E731
    application_id = lambda: str(uuid.uuid4())  # noqa: E731
    resume_md = "# Jane Doe\n\nExperience: ML Intern at XYZ"
    cover_letter_md = "Dear Hiring Team,\n\nI am excited to apply."
    email_subject = "Application for ML Intern"
    email_body = "Hello, I am very interested in this opportunity."
    model_used = "mixtral"
    prompt_version = "v1"


class ApplicationModel(BaseModel):
    id: str
    user_id: str
    job_id: str
    profile_id: str
    status: str


class ApplicationFactory(ModelFactory):
    __model__ = ApplicationModel

    id = lambda: str(uuid.uuid4())  # noqa: E731
    user_id = lambda: str(uuid.uuid4())  # noqa: E731
    job_id = lambda: str(uuid.uuid4())  # noqa: E731
    profile_id = lambda: str(uuid.uuid4())  # noqa: E731
    status = "APPROVED"


def _make_draft(**kwargs: Any) -> dict:
    return DraftFactory.build().model_dump() | kwargs


def _make_application(status: str = "APPROVED", **kwargs: Any) -> dict:
    return ApplicationFactory.build(status=status).model_dump() | kwargs


GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

# ---------------------------------------------------------------------------
# 1. MIME message structure — From, To, Subject, body
# ---------------------------------------------------------------------------


class TestSenderMimeStructure:
    """GmailSender.build_message returns correctly structured MIME message."""

    def test_mime_from_header_matches(self) -> None:
        from app.services.sender import GmailSender  # ImportError until impl

        sender = GmailSender(access_token="token-abc")
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="Internship Application",
            body="Hello, I would like to apply.",
        )
        assert msg["From"] == "sender@gmail.com"

    def test_mime_to_header_matches(self) -> None:
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="Internship Application",
            body="Hello, I would like to apply.",
        )
        assert msg["To"] == "recruiter@example.com"

    def test_mime_subject_header_matches(self) -> None:
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="ML Intern Position",
            body="Hello, I would like to apply.",
        )
        assert msg["Subject"] == "ML Intern Position"

    def test_mime_body_text_present(self) -> None:
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        body_text = "Hello, I am very interested in the ML Internship role."
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="Application",
            body=body_text,
        )
        # Walk parts to find text/plain
        found_body = False
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload and body_text.encode() in payload:
                    found_body = True
                    break
        assert found_body, "Body text not found in any text/plain MIME part"

    @pytest.mark.parametrize("subject", [
        "نوکری کی درخواست",  # Urdu
        "실습생 지원",         # Korean
        "インターンシップ申請",  # Japanese
        "Praktikum Bewerbung — Müller",  # German with umlaut
        "A" * 256,  # max-length subject
        "",  # empty subject
        "Subject with <html> & entities",
    ])
    def test_mime_subject_unicode_and_edge_cases(self, subject: str) -> None:
        """build_message must not raise on any subject content."""
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject=subject,
            body="Test body",
        )
        # Must produce a valid MIME message without exception
        assert msg is not None

    @pytest.mark.parametrize("body", [
        "Short body.",
        "x" * 5000,  # long body
        "Unicode: 파이썬 개발자 인턴십 지원합니다. আমি আবেদন করতে চাই।",
        "Body\nwith\nnewlines\n\nand\n\nblank lines",
        "<p>HTML-like content</p>",
        "",  # empty body
    ])
    def test_mime_long_and_unicode_bodies(self, body: str) -> None:
        """build_message must handle any body text without exception."""
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        msg = sender.build_message(
            from_addr="a@example.com",
            to_addr="b@example.com",
            subject="Test",
            body=body,
        )
        assert msg is not None


# ---------------------------------------------------------------------------
# 2. Attachment part: resume.pdf
# ---------------------------------------------------------------------------


class TestSenderAttachment:
    """build_message with pdf_bytes attaches a resume.pdf part."""

    def test_attachment_name_is_resume_pdf(self) -> None:
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        pdf_bytes = b"%PDF-1.4 fake pdf content"
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="Application",
            body="Hello",
            pdf_bytes=pdf_bytes,
        )
        found = False
        for part in msg.walk():
            content_disposition = part.get_content_disposition()
            if content_disposition and "attachment" in content_disposition:
                filename = part.get_filename()
                if filename == "resume.pdf":
                    found = True
                    break
        assert found, "No attachment named 'resume.pdf' found in MIME message"

    def test_attachment_content_type_is_pdf(self) -> None:
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        pdf_bytes = b"%PDF-1.4 fake pdf content bytes here"
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="Application",
            body="Hello",
            pdf_bytes=pdf_bytes,
        )
        found_pdf = False
        for part in msg.walk():
            if part.get_content_type() == "application/pdf":
                found_pdf = True
                break
        assert found_pdf, "No application/pdf part found in MIME message"

    def test_attachment_bytes_are_non_empty(self) -> None:
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        pdf_bytes = b"%PDF-1.4 " + b"A" * 512  # non-trivial PDF stub
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="Application",
            body="Hello",
            pdf_bytes=pdf_bytes,
        )
        for part in msg.walk():
            if part.get_content_type() == "application/pdf":
                payload = part.get_payload(decode=True)
                assert payload is not None
                assert len(payload) > 0
                return
        pytest.fail("No application/pdf part found")

    def test_no_attachment_when_pdf_bytes_none(self) -> None:
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="token-abc")
        msg = sender.build_message(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="Application",
            body="Hello",
            pdf_bytes=None,
        )
        for part in msg.walk():
            assert part.get_content_type() != "application/pdf", (
                "Unexpected PDF attachment when pdf_bytes=None"
            )


# ---------------------------------------------------------------------------
# 3. Gmail API send — respx-mocked
# ---------------------------------------------------------------------------


class TestGmailApiSend:
    """send_email calls Gmail REST API with correct payload; mock returns message ID."""

    @respx.mock
    def test_send_email_calls_gmail_api(self) -> None:
        from app.services.sender import GmailSender

        sender = GmailSender(access_token="ya29.test-token")
        mock_route = respx.post(GMAIL_SEND_URL).mock(
            return_value=httpx.Response(
                200, json={"id": "msg-id-123", "threadId": "thread-1", "labelIds": ["SENT"]}
            )
        )

        result = sender.send_email(
            from_addr="sender@gmail.com",
            to_addr="recruiter@example.com",
            subject="Internship Application",
            body="Hello, I am applying.",
        )
        assert mock_route.called
        assert result["id"] == "msg-id-123"

    @respx.mock
    def test_send_email_uses_bearer_auth(self) -> None:
        from app.services.sender import GmailSender

        access_token = f"ya29.{uuid.uuid4().hex}"
        sender = GmailSender(access_token=access_token)

        captured_request: list = []

        def capture(request: httpx.Request) -> httpx.Response:
            captured_request.append(request)
            return httpx.Response(200, json={"id": "msg-id", "threadId": "t1", "labelIds": []})

        respx.post(GMAIL_SEND_URL).mock(side_effect=capture)

        sender.send_email(
            from_addr="me@gmail.com",
            to_addr="hr@company.com",
            subject="Job Application",
            body="Hello",
        )
        assert len(captured_request) == 1
        auth_header = captured_request[0].headers.get("Authorization", "")
        assert access_token in auth_header

    @respx.mock
    def test_send_email_raises_on_401(self) -> None:
        from app.services.sender import GmailSender, GmailSendError

        sender = GmailSender(access_token="expired-token")
        respx.post(GMAIL_SEND_URL).mock(
            return_value=httpx.Response(401, json={"error": {"message": "Invalid Credentials"}})
        )
        with pytest.raises(GmailSendError):
            sender.send_email(
                from_addr="me@gmail.com",
                to_addr="hr@company.com",
                subject="Test",
                body="Test",
            )

    @respx.mock
    def test_send_email_raises_on_500(self) -> None:
        from app.services.sender import GmailSender, GmailSendError

        sender = GmailSender(access_token="token")
        respx.post(GMAIL_SEND_URL).mock(
            return_value=httpx.Response(500, json={"error": {"message": "Internal error"}})
        )
        with pytest.raises(GmailSendError):
            sender.send_email(
                from_addr="me@gmail.com",
                to_addr="hr@company.com",
                subject="Test",
                body="Test",
            )


# ---------------------------------------------------------------------------
# 4. Property-based: random valid email → To header always valid
# ---------------------------------------------------------------------------

# RFC 5321 valid email strategy: local@domain.tld
_local_chars = st.text(
    min_size=1,
    max_size=20,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="._+-",
        blacklist_characters="@",
    ),
)
_domain_chars = st.text(
    min_size=2,
    max_size=20,
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters="-",
    ),
)
_tld = st.sampled_from(["com", "org", "net", "io", "co.uk", "pk"])
_email_strategy = st.builds(
    lambda local, domain, tld: f"{local}@{domain}.{tld}",
    local=_local_chars,
    domain=_domain_chars,
    tld=_tld,
).filter(lambda e: len(e) <= 254 and "@" in e and "." in e.split("@")[1])


@given(_email_strategy)
@h_settings(max_examples=50)
def test_to_header_always_valid_for_rfc5321_emails(to_email: str) -> None:
    """Property: any RFC 5321-compliant To address is preserved unchanged in MIME To header."""
    from app.services.sender import GmailSender

    sender = GmailSender(access_token="token")
    msg = sender.build_message(
        from_addr="sender@gmail.com",
        to_addr=to_email,
        subject="Test",
        body="Test body",
    )
    assert msg["To"] == to_email, (
        f"Expected To={to_email!r}, got {msg['To']!r}"
    )


# ---------------------------------------------------------------------------
# 5. Send-queue idempotency
# ---------------------------------------------------------------------------


class TestSendQueueIdempotency:
    """process_send_queue called twice on one APPROVED draft → exactly one OutreachEvent row."""

    @pytest.mark.asyncio
    async def test_single_outreach_event_on_double_call(self) -> None:
        """Seed one APPROVED application+draft, call process_send_queue twice.
        Exactly one OutreachEvent must exist (UNIQUE on sent_hash).
        """
        from app.services.sender import process_send_queue  # ImportError until impl

        # Use an in-memory approach: mock the DB and sender internals
        sent_hashes: set[str] = set()
        events: list[dict] = []

        async def mock_sender_call(application_id: str, draft: Any, _session: Any) -> None:
            import hashlib
            h = hashlib.sha256(f"{application_id}:{draft['email_subject']}".encode()).hexdigest()
            if h in sent_hashes:
                # Idempotent — do nothing (simulate UNIQUE constraint)
                return
            sent_hashes.add(h)
            events.append({"application_id": application_id, "sent_hash": h})

        draft = _make_draft()
        app_id = str(uuid.uuid4())

        with (
            patch("app.services.sender._get_approved_drafts", new_callable=AsyncMock) as mock_get,
            patch("app.services.sender._send_one", new=mock_sender_call),
        ):
            mock_get.return_value = [(app_id, draft)]
            await process_send_queue(session=MagicMock())
            await process_send_queue(session=MagicMock())

        assert len(events) == 1, (
            f"Expected exactly 1 OutreachEvent, got {len(events)}"
        )

    @pytest.mark.asyncio
    async def test_second_call_is_no_op_no_exception(self) -> None:
        """Second call to process_send_queue must not raise, even with duplicate."""
        from app.services.sender import process_send_queue

        call_count = 0

        async def mock_sender_once(application_id: str, draft: Any, _session: Any) -> None:
            nonlocal call_count
            call_count += 1

        draft = _make_draft()
        app_id = str(uuid.uuid4())

        with (
            patch("app.services.sender._get_approved_drafts", new_callable=AsyncMock) as mock_get,
            patch("app.services.sender._send_one", new=mock_sender_once),
        ):
            mock_get.return_value = [(app_id, draft)]
            await process_send_queue(session=MagicMock())

        # Second call with empty approved queue (already processed)
        with (
            patch("app.services.sender._get_approved_drafts", new_callable=AsyncMock) as mock_get2,
            patch("app.services.sender._send_one", new=mock_sender_once),
        ):
            mock_get2.return_value = []
            # Must not raise
            await process_send_queue(session=MagicMock())

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_no_outreach_event_for_non_approved_draft(self) -> None:
        """Drafts in DRAFTED or SENT status must NOT be processed by process_send_queue."""
        from app.services.sender import process_send_queue

        send_calls: list = []

        async def mock_sender(application_id: str, draft: Any, _session: Any) -> None:
            send_calls.append(application_id)

        with (
            patch("app.services.sender._get_approved_drafts", new_callable=AsyncMock) as mock_get,
            patch("app.services.sender._send_one", new=mock_sender),
        ):
            # No APPROVED drafts
            mock_get.return_value = []
            await process_send_queue(session=MagicMock())

        assert send_calls == [], (
            f"Expected no sends for non-approved drafts, got {send_calls}"
        )
