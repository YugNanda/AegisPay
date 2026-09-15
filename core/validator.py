import re
from datetime import datetime, timedelta
from typing import Tuple

class CardValidator:
    """Cryptographic & format validation for payment cards."""

    NETWORK_PATTERNS = {
        'Visa': r'^4[0-9]{12}(?:[0-9]{3})?$',
        'MasterCard': r'^(?:5[1-5][0-9]{14}|2(?:2[2-9][0-9]{12}|[3-6][0-9]{13}|7[0-1][0-9]{12}|720[0-9]{12}))$',
        'American Express': r'^3[47][0-9]{13}$',
        'Discover': r'^6(?:011|5[0-9]{2}|4[4-9][0-9]|22(?:1(?:2[6-9]|[3-9][0-9])|[2-8][0-9]{2}|9(?:[01][0-9]|2[0-5])))[0-9]{12}$',
        'RuPay': r'^(?:508[5-9]|6069|607[0-9]|608[0-4]|6521|6522|6530|6531)[0-9]{12}$',
        'JCB': r'^(?:2131|1800|35\d{3})\d{11}$',
        'Diners Club': r'^3(?:0[0-5]|[68][0-9])[0-9]{11}$',
        'UnionPay': r'^(62[0-9]{14,17})$',
        'Maestro': r'^(?:50|5[6-9]|6[0-9])\d{10,17}$'
    }

    @staticmethod
    def clean_card_number(card_number: str) -> str:
        """Remove whitespace, hyphens, and non-digit characters."""
        return re.sub(r'\D', '', str(card_number))

    @classmethod
    def validate_luhn(cls, card_number: str) -> Tuple[bool, int]:
        """
        Validate primary account number using the standard ISO/IEC 7812 Luhn formula.
        Returns: (is_valid, check_digit)
        """
        clean_num = cls.clean_card_number(card_number)
        if len(clean_num) < 12 or len(clean_num) > 19:
            return False, -1

        digits = [int(d) for d in clean_num]
        check_digit = digits[-1]
        payload = digits[:-1]

        # Double every second digit from right to left
        payload.reverse()
        total = 0
        for i, digit in enumerate(payload):
            if i % 2 == 0:
                doubled = digit * 2
                total += (doubled - 9) if doubled > 9 else doubled
            else:
                total += digit

        calculated_check = (10 - (total % 10)) % 10
        is_valid = (total + check_digit) % 10 == 0
        return is_valid, calculated_check

    @classmethod
    def detect_network(cls, card_number: str) -> str:
        """Identify card issuing scheme/network from primary account number."""
        clean_num = cls.clean_card_number(card_number)
        for network, pattern in cls.NETWORK_PATTERNS.items():
            if re.match(pattern, clean_num):
                return network
        return "Unknown Network"

    @staticmethod
    def validate_expiry(month_str: str, year_str: str) -> Tuple[bool, str]:
        """Verify card expiration against current calendar date."""
        try:
            m = int(str(month_str).strip())
            y = int(str(year_str).strip())
            if m < 1 or m > 12:
                return False, "Invalid month: must be between 01 and 12"

            if y < 100:
                y += 2000

            now = datetime.now()
            # Card is valid until the last second of the expiration month
            if m == 12:
                expiry_dt = datetime(y + 1, 1, 1) - timedelta(seconds=1)
            else:
                expiry_dt = datetime(y, m + 1, 1) - timedelta(seconds=1)

            if expiry_dt < now:
                return False, f"Card expired on {m:02d}/{y}"
            if expiry_dt > now + timedelta(days=365 * 10):
                return False, "Expiry date unreasonably far in the future (>10 years)"

            return True, "Valid"
        except Exception as e:
            return False, f"Malformed expiration date: {str(e)}"

    @staticmethod
    def validate_cvv(cvv: str, network: str) -> bool:
        """Validate security code against card scheme standards."""
        clean_cvv = re.sub(r'\D', '', str(cvv))
        if network == 'American Express':
            return len(clean_cvv) == 4
        return len(clean_cvv) == 3

    @classmethod
    def mask_card(cls, card_number: str) -> str:
        """Return PCI-DSS compliant masked PAN (first 6 and last 4)."""
        clean = cls.clean_card_number(card_number)
        if len(clean) < 10:
            return "•••• " * 3 + clean[-4:] if len(clean) >= 4 else "••••"
        first6 = clean[:6]
        last4 = clean[-4:]
        stars = "•" * (len(clean) - 10)
        return f"{first6[:4]} {first6[4:6]}{stars[:2]} •••• {last4}"
