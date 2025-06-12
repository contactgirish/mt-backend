from fastapi import APIRouter, Request, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from utils.datetime_utils import utc_now
from utils.auth import authorize_user
from utils.telegram_notifier import _send_to_telegram, TELEGRAM_CHANNELS, notify_internal
import aiohttp
import os
import re

router = APIRouter()
SPARKPOST_API_KEY = os.getenv("SPARKPOST_API_KEY")

class SupportTicketRequest(BaseModel):
    name: str
    email: EmailStr
    phone: str
    subject: str
    feedback: str

# Custom Telegram-safe Markdown escape that preserves ., @, -, :
def escape_markdown_lite(text: str) -> str:
    return re.sub(r'([*_`\[\]])', r'\\\1', text)

@router.post("/raise_support_ticket")
async def raise_support_ticket(
    payload: SupportTicketRequest,
    request: Request,
    user=Depends(authorize_user)
):
    try:
        now = utc_now().astimezone()
        formatted_datetime = now.strftime("%d-%b-%Y %I:%M %p").replace(" 0", " ").lstrip("0")
        subject_line = f"Support ticket raised - {formatted_datetime}"

        # Email HTML body
        html_body = f"""
        <div style='font-family: Arial, sans-serif; font-size: 16px;'>
            <p><strong>Name:</strong> {payload.name}</p>
            <p><strong>Email:</strong> {payload.email}</p>
            <p><strong>Phone:</strong> {payload.phone}</p>
            <p><strong>Subject:</strong> {payload.subject}</p>
            <p><strong>Feedback:</strong><br>{payload.feedback}</p>
        </div>
        """

        email_payload = {
            "content": {
                "from": {
                    "email": "txn@notifications.monktrader.in",
                    "name": "MonkTrader Support"
                },
                "subject": subject_line,
                "html": html_body,
            },
            "recipients": [{"address": "support@monktrader.ai"}]
        }

        headers = {
            "Authorization": SPARKPOST_API_KEY,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.sparkpost.com/api/v1/transmissions",
                json=email_payload,
                headers=headers,
                timeout=10
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    await notify_internal(f"[Support Ticket Email Error] {resp.status}: {error_text}")
                    raise HTTPException(status_code=500, detail="Failed to send support ticket")

        # Properly escaped Telegram message
        telegram_msg = f"""
📩 *New Support Ticket Raised*

🧑 *Name:* {escape_markdown_lite(payload.name)}
📧 *Email:* {escape_markdown_lite(payload.email)}
📱 *Phone:* {escape_markdown_lite(payload.phone)}
📝 *Subject:* {escape_markdown_lite(payload.subject)}
💬 *Feedback:* {escape_markdown_lite(payload.feedback)}
🕒 *Time:* {formatted_datetime}
        """.strip()

        await _send_to_telegram(
            chat_id=TELEGRAM_CHANNELS["customer_queries"],
            message=telegram_msg,
            parse_mode="Markdown"
        )

        return {"message": "Support ticket submitted successfully"}

    except Exception as e:
        await notify_internal(f"[Support Ticket Error] {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
