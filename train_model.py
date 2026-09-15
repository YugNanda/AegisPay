#!/usr/bin/env python3
"""Standalone script to re-train and evaluate AegisPay machine learning pipeline."""
import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.ml_engine import MLEngine

def main():
    print("[INIT] Initializing AegisPay Model Training Pipeline...")
    model_path = os.path.join(os.path.dirname(__file__), "models", "aegis_fraud_pipeline.joblib")
    if os.path.exists(model_path):
        os.remove(model_path)
        print(f"Removed stale model bundle: {model_path}")
    
    engine = MLEngine(model_path=model_path)
    print(f"[OK] Training completed successfully! Model bundle saved to: {model_path}")
    print("Features trained:", engine.FEATURE_NAMES)
    
    # Test evaluation sample
    prob, anom, exp = engine.predict(
        amount=1450.0, hour=3, distance_km=850.0,
        is_foreign=True, category="electronics", device_trust=0.20
    )
    print(f"[TEST] Test Sample Prediction -> Fraud Prob: {prob*100:.1f}%, Anomaly: {anom*100:.1f}%, Explanations: {exp}")

if __name__ == "__main__":
    main()
