#!/usr/bin/env python3
"""
AegisPay — Production Machine Learning Financial Fraud Detection & Risk Scoring System.
Unified Server: REST API, Real-Time Web Dashboard, CLI & Desktop GUI.
"""

import sys
import os
import time
import uuid
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from core.models import TransactionRequest, TransactionResponse, ValidationResult, RiskBreakdown
from core.validator import CardValidator
from core.rules_engine import RulesEngine
from core.ml_engine import MLEngine

class AegisPayEngine:
    """Enterprise risk decisioning engine combining cryptographic checks, heuristics, and ML."""

    def __init__(self):
        self.validator = CardValidator()
        self.rules_engine = RulesEngine()
        self.ml_engine = MLEngine()
        self.transaction_ledger: List[Dict[str, Any]] = []

    def analyze(self, req: TransactionRequest) -> TransactionResponse:
        start_time = time.time()
        tx_id = f"tx_{uuid.uuid4().hex[:12]}"
        now_dt = datetime.now(timezone.utc)
        hour = req.transaction_hour if req.transaction_hour is not None else now_dt.hour

        # 1. Cryptographic & Card Format Validation
        clean_pan = self.validator.clean_card_number(req.card.card_number)
        luhn_ok, _ = self.validator.validate_luhn(clean_pan)
        network = self.validator.detect_network(clean_pan)
        expiry_ok, expiry_msg = self.validator.validate_expiry(req.card.expiry_month, req.card.expiry_year)
        cvv_ok = self.validator.validate_cvv(req.card.cvv, network)
        card_valid = luhn_ok and expiry_ok and cvv_ok

        validation_res = ValidationResult(
            card_valid=card_valid,
            luhn_valid=luhn_ok,
            card_network=network,
            expiry_valid=expiry_ok,
            expiry_message=expiry_msg,
            cvv_valid=cvv_ok
        )

        # 2. Rule & Heuristics Check
        rules_penalty, rules_reasons = self.rules_engine.evaluate_rules(
            clean_pan, req.amount, req.merchant_name, req.merchant_category
        )

        # 3. Velocity Checks
        velocity_penalty, velocity_reasons = self.rules_engine.record_and_check_velocity(
            clean_pan, req.amount
        )

        # 4. Machine Learning & Anomaly Detection
        ml_prob, anomaly_score, ml_reasons = self.ml_engine.predict(
            amount=req.amount,
            hour=hour,
            distance_km=req.distance_from_home_km or 5.0,
            is_foreign=bool(req.is_foreign_transaction),
            category=req.merchant_category,
            device_trust=req.device_trust_score or 0.95
        )

        # 5. Composite Risk Scoring Synthesis
        # Weighting: ML probability (45%), Anomaly score (20%), Rules penalty (20%), Velocity penalty (15%)
        composite_score = (
            (ml_prob * 100.0 * 0.45) +
            (anomaly_score * 100.0 * 0.20) +
            (rules_penalty * 0.20) +
            (velocity_penalty * 0.15)
        )

        # Fatal validation failures push to maximum risk
        if not luhn_ok or not expiry_ok or not cvv_ok:
            composite_score = max(composite_score, 88.0)

        total_risk = round(min(max(composite_score, 0.0), 100.0), 1)

        # Decision Matrix & Risk Tiering
        if not card_valid or total_risk >= 80.0:
            risk_tier = "CRITICAL"
            decision = "DECLINE"
        elif total_risk >= 60.0:
            risk_tier = "HIGH"
            decision = "MANUAL_REVIEW"
        elif total_risk >= 35.0:
            risk_tier = "MODERATE"
            decision = "STEP_UP_2FA"
        else:
            risk_tier = "LOW"
            decision = "APPROVE"

        # Aggregate Risk Factors
        all_factors = []
        if not luhn_ok:
            all_factors.append("Failed Luhn checksum validation (invalid card number)")
        if not expiry_ok:
            all_factors.append(f"Expiration check failed: {expiry_msg}")
        if not cvv_ok:
            all_factors.append(f"CVV security format invalid for {network}")

        all_factors.extend(rules_reasons)
        all_factors.extend(velocity_reasons)
        all_factors.extend(ml_reasons)

        if not all_factors:
            all_factors.append("Transaction behavioral pattern aligns with normal consumer baseline")

        # Actionable Recommendations
        recs = []
        if decision == "DECLINE":
            recs.append("Reject transaction immediately and notify issuing bank risk desk.")
            if not card_valid:
                recs.append("Prompt consumer to verify physical card credentials.")
        elif decision == "MANUAL_REVIEW":
            recs.append("Route transaction to Tier-2 Fraud Analysts for manual authorization.")
            recs.append("Request secondary proof of billing address or device token.")
        elif decision == "STEP_UP_2FA":
            recs.append("Trigger 3D-Secure 2.0 biometric or SMS OTP challenge.")
        else:
            recs.append("Transaction is low risk. Clear for immediate zero-friction settlement.")

        elapsed_ms = round((time.time() - start_time) * 1000, 2)

        resp = TransactionResponse(
            transaction_id=tx_id,
            timestamp=now_dt.isoformat() + "Z",
            card_network=network,
            masked_card=self.validator.mask_card(clean_pan),
            amount=req.amount,
            currency=req.currency,
            merchant=req.merchant_name,
            validation=validation_res,
            risk=RiskBreakdown(
                ml_fraud_probability=round(ml_prob * 100, 1),
                anomaly_score=round(anomaly_score * 100, 1),
                rules_penalty=round(rules_penalty, 1),
                velocity_penalty=round(velocity_penalty, 1),
                total_risk_score=total_risk,
                risk_tier=risk_tier,
                decision=decision
            ),
            risk_factors=all_factors,
            recommendations=recs,
            processing_time_ms=elapsed_ms
        )

        # Store in audit ledger (keep last 100)
        self.transaction_ledger.insert(0, resp.model_dump())
        if len(self.transaction_ledger) > 100:
            self.transaction_ledger.pop()

        return resp

# Instantiate global engine
engine = AegisPayEngine()

# FastAPI Application
app = FastAPI(
    title="AegisPay — Payment Fraud Detection Engine",
    description="Production-ready REST API & telemetry for ML-based credit card fraud classification.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "web", "static")
if not os.path.exists(static_dir):
    static_dir = BASE_DIR

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_dashboard():
    for candidate in [
        os.path.join(BASE_DIR, "web", "static", "index.html"),
        os.path.join(BASE_DIR, "index.html"),
        os.path.join(static_dir, "index.html"),
    ]:
        if os.path.exists(candidate):
            return FileResponse(candidate, media_type="text/html")
    return {"message": "AegisPay Engine Active. Static UI directory not found."}

@app.post("/api/v1/analyze", response_model=TransactionResponse)
def analyze_transaction(req: TransactionRequest):
    try:
        return engine.analyze(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/ledger")
def get_ledger():
    return {"count": len(engine.transaction_ledger), "transactions": engine.transaction_ledger}

@app.get("/api/v1/health")
def health():
    return {
        "status": "HEALTHY",
        "service": "AegisPay Engine",
        "version": "2.0.0",
        "ml_pipeline_loaded": engine.ml_engine.classifier is not None,
        "features": engine.ml_engine.FEATURE_NAMES,
        "timestamp": datetime.now(timezone.utc).isoformat() + "Z"
    }

def run_cli_demo():
    print("=" * 65)
    print("  AegisPay — ML Credit Card Fraud Detection Terminal Demo")
    print("=" * 65)
    from core.models import CardDetails
    
    sample_tx = TransactionRequest(
        card=CardDetails(
            card_number="4532015698741250",
            expiry_month="12",
            expiry_year="2028",
            cvv="345",
            cardholder_name="Jane Doe"
        ),
        amount=1850.00,
        currency="USD",
        merchant_name="Offshore Crypto Broker",
        merchant_category="cryptocurrency",
        transaction_hour=3,
        distance_from_home_km=620.0,
        is_foreign_transaction=True,
        device_trust_score=0.25
    )

    print(f"\nAnalyzing Sample Transaction: ${sample_tx.amount} at {sample_tx.merchant_name}...")
    res = engine.analyze(sample_tx)
    print(f"\n[DECISION]: {res.risk.decision} (Risk Score: {res.risk.total_risk_score}/100 - {res.risk.risk_tier})")
    print(f"ML Fraud Probability: {res.risk.ml_fraud_probability}% | Anomaly Index: {res.risk.anomaly_score}%")
    print(f"Card Scheme: {res.card_network} (Masked: {res.masked_card})")
    print("\nTriggered Risk Factors:")
    for f in res.risk_factors:
        print(f"  - {f}")
    print("\nRecommendations:")
    for r in res.recommendations:
        print(f"  * {r}")
    print(f"\nLatency: {res.processing_time_ms} ms")
    print("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="AegisPay Fraud Detection System")
    parser.add_argument("--cli", action="store_true", help="Run interactive terminal demo")
    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Web server host (default: 127.0.0.1)")
    args = parser.parse_args()

    if args.cli:
        run_cli_demo()
    else:
        import uvicorn
        print(f"[START] Starting AegisPay Production Server at http://{args.host}:{args.port} ...")
        uvicorn.run("main:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
