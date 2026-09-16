// AegisPay Real-Time Frontend Controller

const scenarios = {
  legit: {
    card: "4532015698741250",
    month: "12",
    year: "2028",
    cvv: "345",
    amount: "18.50",
    merchant: "Whole Foods Market",
    mcc: "groceries",
    dist: 3,
    foreign: false,
    night: false
  },
  crypto: {
    card: "4532015698741250",
    month: "12",
    year: "2028",
    cvv: "345",
    amount: "2400.00",
    merchant: "Panama Crypto Exchange Ltd",
    mcc: "cryptocurrency",
    dist: 1250,
    foreign: true,
    night: true
  },
  probing: {
    card: "4532015698741250",
    month: "12",
    year: "2028",
    cvv: "345",
    amount: "0.01",
    merchant: "Online Digital Store",
    mcc: "digital_goods",
    dist: 15,
    foreign: false,
    night: false
  },
  invalid: {
    card: "4532015698741259", // Invalid Luhn
    month: "02",
    year: "2022", // Expired
    cvv: "99",
    amount: "150.00",
    merchant: "ElectroHub Retail",
    mcc: "electronics",
    dist: 45,
    foreign: false,
    night: false
  }
};

function loadScenario(type) {
  const sc = scenarios[type];
  if (!sc) return;

  document.getElementById('card_number').value = sc.card;
  document.getElementById('exp_month').value = sc.month;
  document.getElementById('exp_year').value = sc.year;
  document.getElementById('cvv').value = sc.cvv;
  document.getElementById('amount').value = sc.amount;
  document.getElementById('merchant_name').value = sc.merchant;
  document.getElementById('mcc_category').value = sc.mcc;
  document.getElementById('distance').value = sc.dist;
  document.getElementById('dist-val').innerText = sc.dist + " km";
  document.getElementById('is_foreign').checked = sc.foreign;
  document.getElementById('night_tx').checked = sc.night;

  handleCardInput(document.getElementById('card_number'));
  submitAnalysis();
}

function handleCardInput(el) {
  const pan = el.value.replace(/\D/g, '');
  let network = "Unknown";
  
  if (/^4/.test(pan)) network = "Visa";
  else if (/^(5[1-5]|2[2-7])/.test(pan)) network = "MasterCard";
  else if (/^3[47]/.test(pan)) network = "Amex";
  else if (/^6(?:011|5)/.test(pan)) network = "Discover";
  else if (/^(508|60|6521)/.test(pan)) network = "RuPay";
  
  document.getElementById('network-badge').innerText = network;
}

async function submitAnalysis() {
  const submitBtn = document.getElementById('submit-btn');
  submitBtn.disabled = true;
  submitBtn.innerHTML = "<span>⚙️ Running ML Inference & Rules...</span>";

  const payload = {
    card: {
      card_number: document.getElementById('card_number').value.trim(),
      expiry_month: document.getElementById('exp_month').value.trim(),
      expiry_year: document.getElementById('exp_year').value.trim(),
      cvv: document.getElementById('cvv').value.trim(),
      cardholder_name: "Demo Cardholder"
    },
    amount: parseFloat(document.getElementById('amount').value) || 0,
    currency: "USD",
    merchant_name: document.getElementById('merchant_name').value.trim(),
    merchant_category: document.getElementById('mcc_category').value,
    distance_from_home_km: parseFloat(document.getElementById('distance').value) || 5.0,
    is_foreign_transaction: document.getElementById('is_foreign').checked,
    transaction_hour: document.getElementById('night_tx').checked ? 3 : null,
    device_trust_score: document.getElementById('is_foreign').checked ? 0.35 : 0.95
  };

  try {
    const res = await fetch('/api/v1/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      throw new Error(`Server returned ${res.status}`);
    }

    const data = await res.json();
    renderVerdict(data);
    addLedgerRow(data);
  } catch (err) {
    alert("Analysis failed: " + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = "<span>🛡️ Analyze & Score Transaction</span>";
  }
}

function renderVerdict(data) {
  document.getElementById('tx-id-tag').innerText = data.transaction_id;
  document.getElementById('latency-tag').innerText = data.processing_time_ms + "ms";

  const risk = data.risk;
  const score = risk.total_risk_score;
  const decision = risk.decision;
  const tier = risk.risk_tier;

  const banner = document.getElementById('verdict-banner');
  const icon = document.getElementById('verdict-icon');
  const title = document.getElementById('decision-text');
  const desc = document.getElementById('tier-text');
  const scoreEl = document.getElementById('total-score');
  const bar = document.getElementById('gauge-bar-fill');

  scoreEl.innerText = score;
  bar.style.width = score + "%";

  banner.className = "verdict-banner";
  if (decision === "APPROVE") {
    banner.classList.add("verdict-approve");
    icon.innerText = "✅";
    title.innerText = "TRANSACTION APPROVED";
    desc.innerText = `Risk Tier: ${tier} (Clean Behavioral Profile)`;
    scoreEl.style.color = "var(--color-success)";
    bar.style.backgroundColor = "var(--color-success)";
  } else if (decision === "STEP_UP_2FA") {
    banner.classList.add("verdict-warn");
    icon.innerText = "🔐";
    title.innerText = "STEP-UP 2FA CHALLENGE";
    desc.innerText = `Risk Tier: ${tier} (Secondary Verification Required)`;
    scoreEl.style.color = "var(--color-primary)";
    bar.style.backgroundColor = "var(--color-primary)";
  } else if (decision === "MANUAL_REVIEW") {
    banner.classList.add("verdict-warn");
    icon.innerText = "⚠️";
    title.innerText = "MANUAL FRAUD REVIEW";
    desc.innerText = `Risk Tier: ${tier} (High-Risk Threshold Detected)`;
    scoreEl.style.color = "var(--color-warning)";
    bar.style.backgroundColor = "var(--color-warning)";
  } else {
    banner.classList.add("verdict-decline");
    icon.innerText = "🚫";
    title.innerText = "TRANSACTION DECLINED";
    desc.innerText = `Risk Tier: ${tier} (Critical Threat Flagged)`;
    scoreEl.style.color = "var(--color-danger)";
    bar.style.backgroundColor = "var(--color-danger)";
  }

  document.getElementById('ml-prob').innerText = risk.ml_fraud_probability + "%";
  document.getElementById('anom-score').innerText = risk.anomaly_score + "%";

  // Factors
  const factorsList = document.getElementById('risk-factors-list');
  factorsList.innerHTML = "";
  data.risk_factors.forEach(f => {
    const li = document.createElement('li');
    li.className = "signal-item " + (decision === "APPROVE" ? "ok-item" : "danger-item");
    li.innerText = (decision === "APPROVE" ? "✓ " : "⚠️ ") + f;
    factorsList.appendChild(li);
  });

  // Recommendations
  const recsList = document.getElementById('recs-list');
  recsList.innerHTML = "";
  data.recommendations.forEach(r => {
    const li = document.createElement('li');
    li.innerText = "• " + r;
    recsList.appendChild(li);
  });
}

function addLedgerRow(data) {
  const tbody = document.getElementById('ledger-body');
  if (tbody.querySelector('.empty-cell')) {
    tbody.innerHTML = "";
  }

  const tr = document.createElement('tr');
  const d = new Date(data.timestamp);
  const timeStr = d.toLocaleTimeString();

  tr.innerHTML = `
    <td>${timeStr}</td>
    <td><code>${data.transaction_id}</code></td>
    <td>${data.masked_card}</td>
    <td><span class="network-tag">${data.card_network}</span></td>
    <td>$${data.amount.toFixed(2)}</td>
    <td>${data.merchant}</td>
    <td><strong>${data.risk.total_risk_score}</strong>/100</td>
    <td><span class="status-badge badge-${data.risk.decision}">${data.risk.decision}</span></td>
  `;

  tbody.insertBefore(tr, tbody.firstChild);
}
