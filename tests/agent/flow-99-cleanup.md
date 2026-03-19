# Flow 99: Cleanup

## Purpose
Delete ONLY the rows created during this test run.
Reads the test ledger at tests/agent/tmp/test-ledger.json.
This flow runs ALWAYS — even if previous flows failed.

## Step 1: Check Test Ledger

Read `tests/agent/tmp/test-ledger.json`. If it doesn't exist or is empty (`[]`), report "No test data to clean up" and STOP.

## Step 2: Display Cleanup Preview

For each row in the ledger, query the DB to verify it exists:

```sql
SELECT id, symbol, exchange_id, added_at FROM wp_watchlist WHERE id = '<uuid>';
```

Display a table:
| Table | ID | Identifier | Created At | Oracle Tag |
|-------|----|-----------|------------|------------|

## Step 3: Ask for Confirmation

**ASK THE USER: "About to delete N rows created during this test run. See table above. Proceed? (y/n)"**

If user says no: skip cleanup, leave data for manual review.

## Step 4: Delete by Specific ID

```sql
-- Watchlist items (if any were added and not removed during testing)
DELETE FROM wp_watchlist WHERE id = '<specific-uuid>';
```

## Step 5: Verify Deletion

For each deleted row, confirm it's gone:
```sql
SELECT id FROM wp_watchlist WHERE id = '<specific-uuid>';
-- Should return 0 rows
```

## SAFETY RULES
- NEVER use DELETE WHERE symbol LIKE 'Test%' or any pattern match
- NEVER delete without reading the ledger first
- NEVER delete rows not in the ledger
- ALWAYS show the preview table and get user confirmation
- ALWAYS verify created_at is from this test run

## Note
WolfPack tests are mostly read-only (navigation, UI verification). The only potential writes are:
- Watchlist add/remove (flow-02, steps 9-10 — but step 10 removes what step 9 added)
- No other test flows create persistent data

If the watchlist add/remove cycle completed successfully, there should be nothing to clean up.
