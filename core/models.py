from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class CardDetails(BaseModel):
    card_number: str = Field(..., description="13 to 19 digit primary account number")
    expiry_month: str = Field(..., description="2-digit month (01-12)")
    expiry_year: str = Field(..., description="2 or 4-digit year")
    cvv: str = Field(..., description="3 or 4 digit CVV/CVC code")
    cardholder_name: Optional[str] = Field("Authorized Cardholder", description="Name on card")

class TransactionRequest(BaseModel):
    card: CardDetails
    amount: float = Field(..., ge=0.0, description="Transaction amount")
    currency: str = Field("USD", description="ISO currency code")
    merchant_name: str = Field("General Retailer", description="Merchant name")
    merchant_category: str = Field("retail", description="MCC category (retail, electronics, luxury, travel, digital_goods, casino)")
    transaction_hour: Optional[int] = Field(None, ge=0, le=23, description="Hour of transaction (0-23)")
    distance_from_home_km: Optional[float] = Field(5.0, ge=0.0, description="Estimated distance from billing address in km")
    is_foreign_transaction: Optional[bool] = Field(False, description="Flag for international transaction")
    device_trust_score: Optional[float] = Field(0.95, ge=0.0, le=1.0, description="0.0 untrusted to 1.0 trusted")

class ValidationResult(BaseModel):
    card_valid: bool
    luhn_valid: bool
    card_network: str
    expiry_valid: bool
    expiry_message: str
    cvv_valid: bool

class RiskBreakdown(BaseModel):
    ml_fraud_probability: float
    anomaly_score: float
    rules_penalty: float
    velocity_penalty: float
    total_risk_score: float
    risk_tier: str  # LOW, MODERATE, HIGH, CRITICAL
    decision: str   # APPROVE, STEP_UP_2FA, MANUAL_REVIEW, DECLINE

class TransactionResponse(BaseModel):
    transaction_id: str
    timestamp: str
    card_network: str
    masked_card: str
    amount: float
    currency: str
    merchant: str
    validation: ValidationResult
    risk: RiskBreakdown
    risk_factors: List[str]
    recommendations: List[str]
    processing_time_ms: float
