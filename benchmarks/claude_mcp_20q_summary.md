# Claude MCP 20Q Summary

- MCP URL: `http://127.0.0.1:8003/sse`
- Passed: **18/20**
- Average latency: **428.6 ms**

| ID | OK | Source | Column | Type | Rows | ms | Question |
|---|---|---|---|---|---:|---:|---|
| Q1 | ✅ | Backlog | EXT_PRICE | scalar | 1535 | 3207.3 | What is the total extended price of all orders in the backlog? |
| Q2 | ✅ | Backlog | QUANTITY | scalar | 1535 | 433.8 | How many unique customers are in the backlog? |
| Q3 | ✅ | Backlog | UNIT_PRICE | scalar | 1535 | 345.2 | What is the average unit price across all backlog items? |
| Q4 | ✅ | Backlog | EXT_PRICE | table | 1535 | 235.6 | Which state has the highest total extended price for backlog orders? |
| Q5 | ✅ | Backlog | QUANTITY | table | 1535 | 454.2 | What is the total quantity ordered in the backlog grouped by status? |
| Q6 | ✅ | Backlog | QUANTITY | scalar | 1535 | 238.7 | How many backlog items are projected to ship in each month? |
| Q7 | ✅ | OPO | Ext Open Cost | scalar | 1139 | 323.6 | What is the average extended price per order in the OPO dataset? |
| Q8 | ✅ | OPO | Quantity Ordered | table | 1139 | 197.4 | Which vendor appears most frequently in the OPO records? |
| Q9 | ❌ |  |  | none | 0 | 175.7 | What is the total unit cost across all parts in the recent POS statistics? |
| Q10 | ✅ | Quotes | QUANTITY | scalar | 1676 | 418.5 | How many unique part numbers are tracked in the recent quotes dataset? |
| Q11 | ✅ | Quotes | UNIT_PRICE | table | 1676 | 358.7 | What is the average unit price for quotes grouped by invoice date? |
| Q12 | ✅ | Quotes | OH_COST | scalar | 1676 | 333.3 | What is the total extended cost in the recent quotes dataset? |
| Q13 | ✅ | OPO | Quantity Ordered | scalar | 1139 | 223.2 | Which profit center has the highest order count in the OPO data? |
| Q14 | ✅ | Quotes | QUANTITY | scalar | 1676 | 400.2 | What is the average quantity per order in recent quotes? |
| Q15 | ✅ | Backlog | QUANTITY | scalar | 1535 | 217.7 | How many backlog orders were placed in each month based on ORDERED_ON? |
| Q16 | ✅ | Quotes | EXT_COST | table | 1676 | 320.6 | What is the total extended price for quotes grouped by customer? |
| Q17 | ✅ | OPO | Quantity Ordered | table | 1139 | 208.8 | Which division appears most in the OPO dataset? |
| Q18 | ❌ |  |  |  | 0 | 14.2 | What is the average unit cost for parts in the recent POS statistics? |
| Q19 | ✅ | Backlog | QUANTITY | scalar | 1535 | 239.4 | How many backlog items have a status of 'Open' versus other statuses? |
| Q20 | ✅ | Backlog | EXT_PRICE | table | 1535 | 226.3 | What is the total extended price for backlog orders grouped by project ID? |
