import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from core.validator import CardValidator
from core.rules_engine import RulesEngine
from core.ml_engine import MLEngine
from core.models import CardDetails, TransactionRequest
from main import AegisPayEngine

class TestAegisPay(unittest.TestCase):
    def setUp(self):
        self.engine = AegisPayEngine()

    def test_luhn_algorithm(self):
        # Valid Visa test number
        valid, _ = CardValidator.validate_luhn("4532015698741250")
        self.assertTrue(valid)
        
        # Corrupted checksum
        invalid, _ = CardValidator.validate_luhn("4532015698741259")
        self.assertFalse(invalid)

    def test_network_detection(self):
        self.assertEqual(CardValidator.detect_network("4532015698741250"), "Visa")
        self.assertEqual(CardValidator.detect_network("5425233430109903"), "MasterCard")
        self.assertEqual(CardValidator.detect_network("378282246310005"), "American Express")

    def test_expiry_validation(self):
        valid, _ = CardValidator.validate_expiry("12", "2030")
        self.assertTrue(valid)
        
        expired, msg = CardValidator.validate_expiry("01", "2020")
        self.assertFalse(expired)

    def test_ml_prediction(self):
        prob, anom, exp = self.engine.ml_engine.predict(
            amount=25.0, hour=14, distance_km=2.0, is_foreign=False,
            category="groceries", device_trust=0.98
        )
        self.assertLess(prob, 0.40)
        self.assertIsInstance(anom, float)

    def test_end_to_end_analysis(self):
        req = TransactionRequest(
            card=CardDetails(
                card_number="4532015698741250",
                expiry_month="12",
                expiry_year="2029",
                cvv="123"
            ),
            amount=15.00,
            merchant_name="Local Supermarket",
            merchant_category="groceries"
        )
        res = self.engine.analyze(req)
        self.assertEqual(res.risk.decision, "APPROVE")
        self.assertEqual(res.risk.risk_tier, "LOW")

if __name__ == "__main__":
    unittest.main()
