const sheetData = `ID,Name,Parent,URL,Summary
LEAREV-1,HubSpot reporting dashboards for executives,Executive Strategy,https://knowledge.hubspot.com/reports/create-dashboards,See the big picture and monitor your revenue targets with high-level reporting dashboards for executives and C-suite.
REVREV-1,Forecasting tool overview,Revenue Insights,https://knowledge.hubspot.com/forecast/use-the-forecast-tool,Visualize your weighted forecast, update deal stages, and analyze revenue projections using the forecasting tool.
MARMAR-1,Marketing analytics dashboards,Marketing Leadership,https://knowledge.hubspot.com/reports/create-marketing-dashboards,Review ROI and track lead sources effectively.
SALSAL-1,Advanced sales forecasting,Sales Leadership,https://knowledge.hubspot.com/forecast/advanced-sales-forecasting,Set revenue goals and track total quota attainment.
SALFRO-1,Coaching tools,Frontline Managers,https://knowledge.hubspot.com/playbooks/use-playbooks,Review rep scorecards, call tracking, and utilize conversation intelligence for coaching.
SALSAL-2,Deal pipelines,Sales Ops,https://knowledge.hubspot.com/deals/create-and-manage-deal-pipelines,Create and manage deal pipelines to track active deals and predict your forecast.
SALFIE-1,HubSpot mobile app features,Field Sales (Outside),https://knowledge.hubspot.com/mobile/hubspot-mobile-app-features,Use the mobile app on the go to update your deal pipelines, scan business cards, and stay aligned with the forecast.
CUSRET-1,Customer health scoring,Retention Strategy,https://knowledge.hubspot.com/health/customer-health-score,Track customer health scoring and identify churn risks before they happen.`;

const lastSynced = 'April 17, 2026 (Manual Bypass)';

const semanticDictionary = {
    "forecast": [
        "mobile app", 
        "deal pipelines", 
        "sales forecasting", 
        "dashboards",
        "roi"
    ],
    "coaching": [
        "scorecards", 
        "playbooks", 
        "leaderboards",
        "reporting"
    ],
    "churn": [
        "health scoring", 
        "ticket SLA", 
        "retention reporting"
    ]
};
