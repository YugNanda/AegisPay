import os
import joblib
import numpy as np
from typing import Dict, Any, Tuple, List
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler

class MLEngine:
    """Production ML Inference & Anomaly Detection Pipeline."""

    FEATURE_NAMES = [
        'amount', 'log_amount', 'transaction_hour', 'is_night',
        'distance_km', 'is_foreign', 'mcc_risk_score', 'device_trust'
    ]

    MCC_RISK_MAP = {
        'groceries': 0.05,
        'retail': 0.10,
        'travel': 0.35,
        'electronics': 0.45,
        'digital_goods': 0.60,
        'luxury': 0.70,
        'wire_transfer': 0.85,
        'cryptocurrency': 0.90,
        'casino': 0.95
    }

    def __init__(self, model_path: str = None):
        if model_path is None:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(base, "models", "aegis_fraud_pipeline.joblib")
        self.model_path = model_path
        self.classifier = None
        self.anomaly_detector = None
        self.scaler = None
        self._load_or_train()

    def _extract_features(self, amount: float, hour: int, distance_km: float,
                          is_foreign: bool, category: str, device_trust: float) -> np.ndarray:
        """Transform raw transaction attributes into normalized model feature vector."""
        log_amt = float(np.log1p(max(0.0, amount)))
        is_night = 1.0 if hour in [0, 1, 2, 3, 4, 5] else 0.0
        mcc_risk = self.MCC_RISK_MAP.get(str(category).lower().strip(), 0.25)
        foreign = 1.0 if is_foreign else 0.0

        vec = np.array([[
            float(amount),
            float(log_amt),
            float(hour),
            is_night,
            float(distance_km),
            foreign,
            mcc_risk,
            float(device_trust)
        ]])
        return vec

    def _train_default_models(self):
        """Train standard Random Forest and Isolation Forest models on simulated transaction distributions."""
        np.random.seed(42)
        n_samples = 4000

        # Normal transactions (~94%)
        n_legit = int(n_samples * 0.94)
        legit_amount = np.random.exponential(scale=45.0, size=n_legit) + 2.0
        legit_hour = np.random.choice(range(6, 24), size=n_legit)
        legit_dist = np.random.exponential(scale=6.0, size=n_legit)
        legit_foreign = np.random.binomial(1, 0.03, size=n_legit)
        legit_mcc = np.random.choice([0.05, 0.10, 0.20, 0.35], size=n_legit)
        legit_device = np.random.beta(a=8, b=1, size=n_legit)

        # Fraud transactions (~6%)
        n_fraud = n_samples - n_legit
        part1 = n_fraud // 3
        part2 = n_fraud // 3
        part3 = n_fraud - part1 - part2

        fraud_amount = np.concatenate([
            np.random.uniform(0.01, 1.5, size=part1),
            np.random.exponential(scale=850.0, size=part2) + 250.0,
            np.random.uniform(900.0, 4500.0, size=part3)
        ])
        fraud_hour = np.random.choice(range(0, 24), size=n_fraud)
        fraud_dist = np.random.exponential(scale=250.0, size=n_fraud) + 20.0
        fraud_foreign = np.random.binomial(1, 0.55, size=n_fraud)
        fraud_mcc = np.random.choice([0.60, 0.70, 0.85, 0.90, 0.95], size=n_fraud)
        fraud_device = np.random.beta(a=2, b=6, size=n_fraud)

        # Combine
        amounts = np.concatenate([legit_amount, fraud_amount])
        hours = np.concatenate([legit_hour, fraud_hour])
        distances = np.concatenate([legit_dist, fraud_dist])
        foreigns = np.concatenate([legit_foreign, fraud_foreign])
        mccs = np.concatenate([legit_mcc, fraud_mcc])
        devices = np.concatenate([legit_device, fraud_device])
        labels = np.concatenate([np.zeros(n_legit), np.ones(n_fraud)])

        log_amounts = np.log1p(amounts)
        is_nights = np.array([1.0 if h in [0, 1, 2, 3, 4, 5] else 0.0 for h in hours])

        X = np.column_stack([
            amounts, log_amounts, hours, is_nights, distances, foreigns, mccs, devices
        ])
        y = labels

        # Scaler
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        # Random Forest Classifier
        self.classifier = RandomForestClassifier(
            n_estimators=80,
            max_depth=8,
            class_weight='balanced',
            random_state=42
        )
        self.classifier.fit(X_scaled, y)

        # Isolation Forest for Anomaly Detection
        self.anomaly_detector = IsolationForest(
            n_estimators=80,
            contamination=0.06,
            random_state=42
        )
        self.anomaly_detector.fit(X_scaled)

        # Save bundle
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        bundle = {
            'classifier': self.classifier,
            'anomaly_detector': self.anomaly_detector,
            'scaler': self.scaler,
            'feature_names': self.FEATURE_NAMES
        }
        joblib.dump(bundle, self.model_path)

    def _load_or_train(self):
        """Load pre-trained pipeline or initiate reproducible training."""
        if os.path.exists(self.model_path):
            try:
                bundle = joblib.load(self.model_path)
                self.classifier = bundle['classifier']
                self.anomaly_detector = bundle['anomaly_detector']
                self.scaler = bundle['scaler']
                return
            except Exception:
                pass
        self._train_default_models()

    def predict(self, amount: float, hour: int, distance_km: float,
                is_foreign: bool, category: str, device_trust: float) -> Tuple[float, float, List[str]]:
        """
        Execute ML fraud classification & anomaly detection.
        Returns:
            - fraud_probability (0.0 - 1.0)
            - anomaly_score (0.0 - 1.0)
            - risk_explanations (List of human-readable feature flags)
        """
        raw_vec = self._extract_features(amount, hour, distance_km, is_foreign, category, device_trust)
        scaled_vec = self.scaler.transform(raw_vec)

        # Supervised probability
        prob = float(self.classifier.predict_proba(scaled_vec)[0][1])

        # Anomaly decision score (lower is more anomalous)
        raw_anomaly = float(self.anomaly_detector.decision_function(scaled_vec)[0])
        # Normalize into a 0.0 - 1.0 anomaly risk index
        anomaly_risk = float(np.clip(1.0 - (raw_anomaly + 0.25) / 0.5, 0.0, 1.0))

        explanations = []
        if prob > 0.40 or anomaly_risk > 0.60:
            if amount > 500.0:
                explanations.append(f"Elevated transaction volume (${amount:,.2f}) deviates from profile")
            elif amount < 2.0:
                explanations.append("Micro-amount pattern consistent with automated card testing")
            if distance_km > 100.0:
                explanations.append(f"Geospatial anomaly: {distance_km:.1f} km from primary billing location")
            if is_foreign:
                explanations.append("Cross-border payment channel activated")
            if hour in [0, 1, 2, 3, 4, 5]:
                explanations.append(f"High-risk temporal window ({hour:02d}:00 UTC)")
            if device_trust < 0.50:
                explanations.append(f"Untrusted device profile (Trust score: {device_trust:.2f})")

        return prob, anomaly_risk, explanations
