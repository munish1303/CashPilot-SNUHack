export const mockState = {
  vitals: {
    totalBank: 12450,
    phantomUsable: 4100,
    daysToZero: 8,
  },

  // 30-day cash projection
  cashFlow: Array.from({ length: 30 }, (_, i) => {
    const day = i + 1;
    const standard = Math.max(0, 12450 - day * 380 + (day % 5 === 0 ? 1200 : 0));
    const phantom = Math.max(-2000, 4100 - day * 520 + (day % 7 === 0 ? 600 : 0));
    return { day: `D+${day}`, standard: Math.round(standard), phantom: Math.round(phantom) };
  }),

  // 14-day sparkline for dashboard
  sparkline: Array.from({ length: 14 }, (_, i) => {
    const day = i + 1;
    const phantom = Math.max(-1500, 4100 - day * 520 + (day % 7 === 0 ? 600 : 0));
    return { day: `D+${day}`, phantom: Math.round(phantom) };
  }),

  survivalProbability: 82,

  monteCarlo: {
    probability: 82,
    simulations: 10000,
    median: 3200,
    p10: 800,
    p90: 7400,
  },

  vendors: [
    { name: "Acme Corp", tier: "Tier 1", goodwill: 95, outstanding: 3200 },
    { name: "AWS", tier: "Tier 2", goodwill: 78, outstanding: 640 },
    { name: "Shopify", tier: "Tier 2", goodwill: 88, outstanding: 1100 },
    { name: "Home Depot", tier: "Tier 3", goodwill: 62, outstanding: 420 },
    { name: "FedEx", tier: "Tier 3", goodwill: 55, outstanding: 280 },
  ],

  ingestion: {
    recentItems: [
      {
        id: "r1",
        source: "Plaid",
        description: "Home Depot — Purchase",
        amount: -418.32,
        date: "Jun 12",
        matched: true,
        confidence: 98,
        matchedWith: "Scanned Receipt #HD-2024-0612",
      },
      {
        id: "r2",
        source: "Stripe",
        description: "Acme Corp — Invoice #1042",
        amount: 3200.0,
        date: "Jun 11",
        matched: true,
        confidence: 100,
        matchedWith: "Stripe Webhook INV-1042",
      },
      {
        id: "r3",
        source: "PDF Upload",
        description: "AWS Invoice — June",
        amount: -640.0,
        date: "Jun 10",
        matched: false,
        confidence: 0,
        matchedWith: null,
      },
      {
        id: "r4",
        source: "Plaid",
        description: "FedEx Shipping — Batch",
        amount: -278.5,
        date: "Jun 9",
        matched: true,
        confidence: 91,
        matchedWith: "Scanned Receipt #FX-0609",
      },
    ],
  },

  actions: [
    {
      id: "a1",
      title: "Fractionalize Acme Corp Payment",
      subtitle: "$3,200 receivable · Due Thursday",
      priority: "critical",
      emailDraft: `Subject: Early Payment Request — Invoice #1042

Hi Sarah,

I hope this finds you well. We're reaching out regarding Invoice #1042 ($3,200) due this Thursday.

Given our current cash flow cycle, we'd greatly appreciate an early partial release of 30% ($960) today, with the remainder on the original due date.

Acme Corp's payment history with us is exceptional, and we're confident this is a smooth process.

Best regards,
CashPilot Autopilot`,
      steps: [
        { label: "Shortfall Detected", detail: "Phantom balance drops to -$1,800 on Thursday (D+3)." },
        { label: "Tier 0 Lock Confirmed", detail: "Rent ($2,400) is Tier 0 — cannot be deferred or fractioned." },
        { label: "Goodwill Analysis", detail: "Acme Corp Goodwill score: 95/100. Low dispute risk, high flexibility." },
        { label: "LP Solver Output", detail: "Optimal: Request 30% advance ($960) today. Bridges gap with zero penalty." },
      ],
    },
    {
      id: "a2",
      title: "Launch Shopify Flash Sale",
      subtitle: "Projected +$2,100 revenue · 48 hrs",
      priority: "high",
      emailDraft: `Subject: 48-Hour Flash Sale — Activate Campaign

Hi Marketing Team,

CashPilot's Monte Carlo engine has flagged a liquidity window requiring action.

Recommended action: Activate the pre-built "Summer Flash" Shopify campaign immediately.

Projected revenue: $2,100 within 48 hours (73% confidence interval).
Subscriber list: 8,400 active emails.
Discount: 15% storewide.

Please confirm activation or provide override reason.

CashPilot Autopilot`,
      steps: [
        { label: "Runway Alert", detail: "Phantom balance falls below $1,000 by D+6 without intervention." },
        { label: "Revenue Modeling", detail: "Historical flash-sale CVR: 4.2% on 8,400 subscribers = ~353 orders." },
        { label: "Monte Carlo Validation", detail: "73% probability of raising $2,100+ within 48 hours across 10k simulations." },
        { label: "LP Solver Output", detail: "Flash sale is highest-ROI lever. No vendor relationships at risk." },
      ],
    },
    {
      id: "a3",
      title: "Defer AWS Invoice $640",
      subtitle: "Net-15 extension · Zero penalty",
      priority: "medium",
      emailDraft: `Subject: Net-15 Payment Extension Request

Hi AWS Billing,

We'd like to request a Net-15 payment extension on our June invoice ($640.00), Invoice ID: AWS-2024-06.

Our account is in good standing with no prior late payments. This extension would be applied under the standard Net-15 policy.

Please confirm the extension at your earliest convenience.

CashPilot Autopilot`,
      steps: [
        { label: "Conflict Detected", detail: "AWS invoice ($640) due D+2 conflicts with payroll obligation on D+4." },
        { label: "Tier Classification", detail: "AWS is Tier 2 — deferrable. Payroll is Tier 0 — locked." },
        { label: "Policy Check", detail: "AWS Net-15 extension available with 0% penalty for accounts in good standing." },
        { label: "LP Solver Output", detail: "Deferring frees $640 phantom cash, extending runway by ~1.5 days." },
      ],
    },
    {
      id: "a4",
      title: "Offer Client X Early Pay Discount",
      subtitle: "3% discount · Unlock $4,800 today",
      priority: "high",
      emailDraft: `Subject: Exclusive Early Payment Offer — 3% Discount

Hi James,

As a valued client, we're offering you an exclusive 3% early payment discount on your outstanding balance of $4,950.

Pay today and save $148.50 — net payment of $4,801.50.

This offer expires in 24 hours.

Best regards,
CashPilot Autopilot`,
      steps: [
        { label: "Receivables Scan", detail: "Client X has $4,950 outstanding, originally due D+12." },
        { label: "Goodwill Score", detail: "Client X Goodwill: 88/100. High likelihood of accepting discount offer." },
        { label: "Cost-Benefit Analysis", detail: "3% discount costs $148.50 but unlocks $4,801.50 cash 10 days early." },
        { label: "LP Solver Output", detail: "Net benefit: +9.2 days runway. Recommended action: send offer immediately." },
      ],
    },
  ],
};

export type Action = (typeof mockState.actions)[0];
