"""
The AI Missed-Call Booker — FastAPI webhook for Twilio SMS + OpenAI replies.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request, Response, status
from openai import OpenAI
from twilio.rest import Client as TwilioRestClient

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the friendly dispatch assistant for Mike's HVAC. A customer just called "
    "and we missed it. Your goal is to text them back, ask what HVAC issue they are "
    "facing, and ask for their address and preferred time for a visit tomorrow. "
    "Be concise and blue-collar friendly."
)

app = FastAPI(title="AI Missed-Call Booker", version="1.0.0")


def _openai_client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=key)


def _twilio_client() -> TwilioRestClient:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise RuntimeError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set")
    return TwilioRestClient(sid, token)


def parse_ai_reply(raw: str) -> str:
    """
    Normalize model output for SMS: trim, strip stray markdown fences, collapse whitespace.
    """
    if not raw:
        return ""
    text = raw.strip()
    fence = re.match(r"^```(?:\w*)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def generate_reply(customer_message: str) -> str:
    client = _openai_client()
    user_content = customer_message.strip() if customer_message else "(No message text.)"
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.7,
        max_tokens=500,
    )
    raw = completion.choices[0].message.content or ""
    return parse_ai_reply(raw)


def send_sms_to_customer(to_number: str, body: str) -> str:
    """
    Send SMS via Twilio REST API. Returns the Twilio Message SID.
    """
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")
    if not from_number:
        raise RuntimeError("TWILIO_PHONE_NUMBER is not set (your Twilio SMS-capable number)")
    twilio = _twilio_client()
    msg = twilio.messages.create(to=to_number, from_=from_number, body=body)
    return msg.sid


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook/twilio")
async def twilio_sms_webhook(
    request: Request,
    Body: str = Form(default=""),
    From: str = Form(default=""),
    To: str = Form(default=""),
    MessageSid: str = Form(default=""),
):
    """
    Twilio posts application/x-www-form-urlencoded fields including Body, From, To.
    We generate an AI reply and send it with the Messages API; webhook returns empty TwiML.
    """
    logger.info(
        "Inbound SMS MessageSid=%s From=%s To=%s preview=%r",
        MessageSid,
        From,
        To,
        Body[:80] + ("…" if len(Body) > 80 else ""),
    )

    empty_twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'

    if not From:
        logger.warning("Missing From; skipping outbound reply")
        return Response(content=empty_twiml, media_type="application/xml")

    try:
        reply_text = await asyncio.to_thread(generate_reply, Body)
        if not reply_text:
            logger.warning("OpenAI returned empty reply; not sending SMS")
            return Response(content=empty_twiml, media_type="application/xml")

        sid = await asyncio.to_thread(send_sms_to_customer, From, reply_text)
        logger.info("Outbound SMS queued sid=%s to=%s", sid, From)
    except Exception:
        logger.exception("Failed to process webhook")
        # Return 200 + empty TwiML so Twilio does not endlessly retry for app logic errors.
        return Response(
            content=empty_twiml,
            media_type="application/xml",
            status_code=status.HTTP_200_OK,
        )

    return Response(content=empty_twiml, media_type="application/xml")
