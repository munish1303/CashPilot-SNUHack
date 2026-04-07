CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    plaid_current_balance DECIMAL(12,2) NOT NULL DEFAULT 0.00,
    current_simulated_date DATE DEFAULT CURRENT_DATE,
    last_synced_at TIMESTAMP DEFAULT now()
);
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(10) NOT NULL, -- 'VENDOR' or 'CLIENT'
    ontology_tier INT NOT NULL, -- 0 (Locked), 1 (Penalty), 2 (Relational), 3 (Flexible)
    goodwill_score INT DEFAULT 100, -- 0 to 100 scale
    late_fee_rate DECIMAL(5,4) DEFAULT 0.0000, -- e.g., 0.015 for 1.5%
    avg_latency_days INT DEFAULT 0 -- Used by Monte Carlo
);
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES entities(id),
    amount DECIMAL(12,2) NOT NULL,
    cleared_date DATE NOT NULL,
    source VARCHAR(50) DEFAULT 'PLAID_API'
);
CREATE TABLE obligations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES entities(id),
    amount DECIMAL(12,2) NOT NULL, -- Negative = Payable, Positive = Receivable
    due_date DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING', -- 'PENDING', 'SHUFFLED', 'PAID'
    is_locked BOOLEAN DEFAULT FALSE -- True if Tier 0 (Taxes/Payroll)
);

CREATE TABLE action_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    is_resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT now(),
    status VARCHAR(50) DEFAULT 'PENDING_USER', -- 'PENDING_USER', 'NEGOTIATING', 'RESOLVED'
    chain_of_thought JSONB,
    execution_type VARCHAR(50), -- 'GMAIL', 'SHOPIFY', 'STRIPE', 'SYSTEM_ALERT'
    execution_payload JSONB,
    agent_thread_id VARCHAR(255) -- For tracking vendor email replies
);