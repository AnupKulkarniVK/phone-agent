"""
SMS Service - Send confirmation messages via Twilio (trial-safe)
"""
import os
import certifi
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.http.http_client import TwilioHttpClient
from datetime import datetime

load_dotenv()


class SMSService:
    """Service for sending SMS messages via Twilio"""

    # Leave buffer because Twilio trial may prepend a disclaimer
    TRIAL_SAFE_LEN = 145

    def __init__(self):
        """Initialize Twilio SMS client with proper SSL configuration"""
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.from_phone = os.getenv("TWILIO_PHONE_NUMBER")

        # Optional: set this in .env for clarity (true/false)
        self.is_trial = os.getenv("TWILIO_IS_TRIAL", "true").strip().lower() == "true"

        if not all([account_sid, auth_token, self.from_phone]):
            print("⚠️  Twilio credentials not fully configured - SMS disabled")
            self.client = None
        else:
            # Create custom HTTP client with proper SSL verification
            # This fixes SSL certificate errors on macOS
            http_client = TwilioHttpClient()
            http_client.session.verify = certifi.where()

            self.client = Client(account_sid, auth_token, http_client=http_client)

    # ---------- formatting helpers ----------
    @staticmethod
    def _format_date(date_str: str) -> str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.strftime("%b %d, %Y")  # short: "Jan 02, 2026"
        except Exception:
            return date_str

    @staticmethod
    def _format_time(time_str: str) -> str:
        try:
            t = datetime.strptime(time_str, "%H:%M")
            return t.strftime("%I:%M%p").lstrip("0").lower()  # "6:30pm"
        except Exception:
            return time_str

    @staticmethod
    def _strip_non_gsm(s: str) -> str:
        """
        Conservative approach: remove emojis / non-basic chars that may push into Unicode.
        Keeps typical punctuation and ASCII.
        """
        return "".join(ch for ch in s if ord(ch) < 128)

    def _enforce_trial_limit(self, message: str) -> str:
        """
        Make message safe for trial by:
        1) If too long, remove non-ascii (emoji/unicode)
        2) If still too long, truncate
        """
        if not self.is_trial:
            return message

        if len(message) > self.TRIAL_SAFE_LEN:
            message = self._strip_non_gsm(message)

        if len(message) > self.TRIAL_SAFE_LEN:
            message = message[: self.TRIAL_SAFE_LEN - 3] + "..."

        return message

    # ---------- message builders ----------
    def _build_confirmation_message(
            self, name: str, party_size: int, date: str, time: str, table_number: int = None
    ) -> str:
        d = self._format_date(date)
        t = self._format_time(time)
        table_info = f" Table {table_number}" if table_number else ""

        # Trial-safe short template
        msg = (
            f"Luigi's Italian\n"
            f"Confirmed: {name}\n"
            f"{d} {t}{table_info}\n"
            f"Party {party_size}. 123 Main St SJ."
        )

        # If for some reason still long, fallback even shorter
        msg = self._enforce_trial_limit(msg)
        if self.is_trial and len(msg) > self.TRIAL_SAFE_LEN:
            msg = f"Luigi's: Confirmed for {name}, {d} {t}. Party {party_size}."
            msg = self._enforce_trial_limit(msg)

        return msg

    def _build_cancellation_message(self, name: str, date: str, time: str) -> str:
        d = self._format_date(date)
        t = self._format_time(time)

        msg = (
            f"Luigi's Italian\n"
            f"Cancelled: {name}\n"
            f"{d} {t}\n"
            f"Call 408-555-LUIGI to rebook."
        )

        msg = self._enforce_trial_limit(msg)
        if self.is_trial and len(msg) > self.TRIAL_SAFE_LEN:
            msg = f"Luigi's: Cancelled for {name}, {d} {t}. Call 408-555-LUIGI."
            msg = self._enforce_trial_limit(msg)

        return msg

    # ---------- public APIs ----------
    def send_confirmation_sms(
            self,
            to_phone: str,
            name: str,
            party_size: int,
            date: str,
            time: str,
            table_number: int = None
    ) -> bool:
        if not self.client:
            print("⚠️  SMS not configured - skipping")
            return False

        message = self._build_confirmation_message(name, party_size, date, time, table_number)

        try:
            msg = self.client.messages.create(body=message, from_=self.from_phone, to=to_phone)
            print(f"✅ SMS sent to {to_phone}: {msg.sid}")
            return True

        except Exception as e:
            print(f"❌ Failed to send SMS: {e}")
            return False

    def send_cancellation_sms(self, to_phone: str, name: str, date: str, time: str) -> bool:
        if not self.client:
            print("⚠️  SMS not configured - skipping")
            return False

        message = self._build_cancellation_message(name, date, time)

        try:
            msg = self.client.messages.create(body=message, from_=self.from_phone, to=to_phone)
            print(f"✅ Cancellation SMS sent to {to_phone}: {msg.sid}")
            return True

        except Exception as e:
            print(f"❌ Failed to send cancellation SMS: {e}")
            return False


# Create singleton instance
sms_service = SMSService()