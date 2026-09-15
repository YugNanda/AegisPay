import time
from collections import defaultdict
from typing import Tuple, List, Dict

class RulesEngine:
    """Heuristic rule-based threat evaluation & velocity scoring."""

    BLOCKED_BINS = {
        '000000', '123456', '999999', '666666', '111111', '888888',
        '411111', '555555', '378282'  # Common test/sandbox BIN prefixes
    }

    HIGH_RISK_MCC = {
        'casino': 35.0,
        'cryptocurrency': 30.0,
        'wire_transfer': 25.0,
        'digital_goods': 15.0,
        'luxury': 10.0,
        'travel': 8.0,
        'retail': 0.0,
        'groceries': 0.0
    }

    SUSPICIOUS_AMOUNTS = {
        0.01: "Micro-authorization card probing ($0.01)",
        1.00: "Common card validation charge ($1.00)",
        999.99: "Structuring near $1,000 threshold ($999.99)",
        1000.00: "Suspicious round amount ($1,000.00)",
        4999.99: "High-value round structuring ($4,999.99)"
    }

    def __init__(self):
        # In-memory sliding window velocity tracker: {card_hash: [(timestamp, amount), ...]}
        self._velocity_store: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

    @staticmethod
    def _has_repeated_digits(pan: str) -> bool:
        """Flag PANs with excessive repeating numbers (e.g. 4111111111111111)."""
        clean = ''.join(filter(str.isdigit, pan))
        if len(clean) >= 12 and len(set(clean)) <= 3:
            return True
        return False

    @staticmethod
    def _has_sequential_patterns(pan: str) -> bool:
        """Detect ascending or descending consecutive 4-digit sequences."""
        clean = ''.join(filter(str.isdigit, pan))
        for i in range(len(clean) - 3):
            sub = [int(d) for d in clean[i:i+4]]
            if (sub[0] + 1 == sub[1] and sub[1] + 1 == sub[2] and sub[2] + 1 == sub[3]) or \
               (sub[0] - 1 == sub[1] and sub[1] - 1 == sub[2] and sub[2] - 1 == sub[3]):
                return True
        return False

    def evaluate_rules(self, card_number: str, amount: float, merchant: str, category: str) -> Tuple[float, List[str]]:
        """
        Evaluate deterministic risk factors.
        Returns: (penalty_score: float [0-100], triggered_rules: List[str])
        """
        penalty = 0.0
        reasons = []

        clean_pan = ''.join(filter(str.isdigit, card_number))
        bin_prefix = clean_pan[:6]

        if bin_prefix in self.BLOCKED_BINS:
            penalty += 50.0
            reasons.append(f"Blocked or sandbox BIN prefix [{bin_prefix}]")

        if self._has_repeated_digits(clean_pan):
            penalty += 30.0
            reasons.append("High degree of repeated digits (synthetic PAN pattern)")

        if self._has_sequential_patterns(clean_pan):
            penalty += 20.0
            reasons.append("Sequential digit run detected (1234/4321 pattern)")

        # Amount heuristics
        for sus_amt, desc in self.SUSPICIOUS_AMOUNTS.items():
            if abs(amount - sus_amt) < 0.001:
                penalty += 15.0
                reasons.append(desc)

        # Merchant Category Risk
        cat_lower = str(category).lower().strip()
        mcc_penalty = self.HIGH_RISK_MCC.get(cat_lower, 5.0)
        if mcc_penalty > 0:
            penalty += mcc_penalty
            if mcc_penalty >= 20.0:
                reasons.append(f"High-risk merchant category: [{cat_lower.upper()}]")

        # Merchant Name inspection
        merchant_lower = str(merchant).lower()
        if any(term in merchant_lower for term in ['darknet', 'fake', 'phish', 'bypass', 'unverified']):
            penalty += 45.0
            reasons.append(f"Flagged merchant name indicator: [{merchant}]")

        return min(penalty, 100.0), reasons

    def record_and_check_velocity(self, card_number: str, amount: float) -> Tuple[float, List[str]]:
        """
        Sliding window velocity monitor:
        - Checks transactions in last 10 minutes, 1 hour, and 24 hours.
        """
        now = time.time()
        clean_pan = ''.join(filter(str.isdigit, card_number))
        card_key = clean_pan[-8:] if len(clean_pan) >= 8 else clean_pan

        # Purge records older than 24h (86400s)
        cutoff_24h = now - 86400
        active_records = [rec for rec in self._velocity_store[card_key] if rec[0] > cutoff_24h]
        active_records.append((now, amount))
        self._velocity_store[card_key] = active_records

        # Calculate counts
        ten_min_count = sum(1 for ts, _ in active_records if ts > (now - 600))
        one_hour_count = sum(1 for ts, _ in active_records if ts > (now - 3600))
        total_24h_amount = sum(amt for _, amt in active_records)

        velocity_penalty = 0.0
        reasons = []

        if ten_min_count > 3:
            velocity_penalty += 35.0
            reasons.append(f"High frequency burst: {ten_min_count} attempts in < 10 mins")
        elif ten_min_count > 1:
            velocity_penalty += 10.0

        if one_hour_count > 6:
            velocity_penalty += 25.0
            reasons.append(f"Hourly threshold exceeded: {one_hour_count} attempts in 1 hr")

        if total_24h_amount > 10000.0:
            velocity_penalty += 20.0
            reasons.append(f"Daily cumulative volume spike (${total_24h_amount:,.2f})")

        return min(velocity_penalty, 100.0), reasons
