# Expected Bugs — Private Answer Key (NOT read by BugFixer)

BugFixer only auto-loads files named exactly `behavior_spec.md` or
`README.md`. This file has neither name, so Model 1/Model 2 never see
it. Do not rename it. There are exactly **8 intentional bugs** in
`order_processing_system.py`. Everything else is correct.

These bugs are deliberately *not* one-token typos. Each one needs the
reader to follow values or state across methods:

| # | Where | What the code does wrong | Why it is hard to spot | Symptom (correct → buggy) |
|---|---|---|---|---|
| 1 | `PricingEngine.calculate_discount` | Computes `eligible_subtotal` correctly, then calculates a **percent** discount from the **whole cart subtotal** | Both variables exist and look plausible; you must notice which one feeds the percent formula. The final `min(..., eligible_subtotal)` does not save it (10% of 200 = 20 < eligible cap check passes wrongly when eligible = 100) | Books 100 + electronics 100, 10% electronics-only coupon: discount **10 → 20** |
| 2 | `PricingEngine.calculate_tax_for_line` | Accepts `discount_allocated` but computes tax on the **pre-discount** line subtotal | The parameter is present, the taxable-amount variable is named innocently, and `_allocate_discount` is fully correct — the break is one ignored argument | Electronics 100 with 10 discount share: tax **16.2 → 18.0** |
| 3 | `PricingEngine.calculate_shipping` (base) | Compares the **pre-discount** `cart.subtotal()` against the free-shipping threshold instead of the `discounted_subtotal` parameter | The correct value arrives as a parameter and is never used; the method reaches back to the cart for a similar-looking number | Subtotal 550, 20% coupon (discounted 440): base shipping **40 → 0 (free)** |
| 4 | `PricingEngine.calculate_shipping` (weight) | Uses `int(extra_weight)` (truncation) instead of rounding **up** (`math.ceil`) | One function call difference inside an otherwise correct surcharge block; only fractional weights expose it | Weight 7.2 kg: surcharge **90 → 60** |
| 5 | `Order.place` | Reserves line-by-line; when a later line fails, earlier reservations are **kept** (no rollback) | Each individual `reserve()` call is correct. The bug only exists across the loop, on the failure path, and is visible only by checking a *different* product's availability after the exception | Stock A=5/B=1, cart A=2/B=3: place fails, A's available **5 → 3** |
| 6 | `Inventory.commit` | Decreases physical stock but **leaves the reserved count in place** (hides behind the comment "reserved count is intentionally left for the caller" — no caller ever clears it) | Stock and reserved are each internally consistent; the corruption appears only in `get_available()` (= stock − reserved) after shipping | Stock 10, order 3 shipped: available **7 → 4** |
| 7 | `Order.cancel` | Calls `release()` (correct) and **then also `add_stock()`**, double-counting units that never left the warehouse | Both calls look like "putting things back". You must know that reserved units were never removed from physical stock to see that the second call invents stock | Stock 10, order 3 placed + cancelled: available **10 → 13** (phantom stock) |
| 8 | `Order.return_items` | Refunds using the product's **current** price × (1 + tax), ignoring the frozen paid price stored by `pay()` in `_paid_unit_price_incl_tax` | The frozen-price machinery exists and is populated correctly in `pay()`; the bug is that `return_items` never reads it. Invisible unless the price changes after payment (or a coupon was used) | Paid 106.2/unit, price later 150: refund for 1 unit **106.2 → 177.0** |

## How the bugs interact (why partial fixes must fail validation)

- Bugs 1 + 2 combine in every discounted-tax total: fixing the coupon
  scope alone still leaves tax charged on pre-discount amounts.
- Bug 1 changes the discounted subtotal, which changes Bug 3's
  shipping outcome — the same cart can be wrong for two reasons.
- Bugs 5, 6, 7 all corrupt inventory in different directions
  (leaked reservation, double-counted availability loss, phantom
  stock). Fixing one lifecycle path leaves the other two broken.
- Bug 8 is completely independent of inventory counts; it only
  shows in refund money after a post-payment price change.
- A repair that fixes, say, 6 of 8 bugs will still fail generated
  tests — and under the current `main.py`, that candidate is never
  propagated to the original file. That is the intended test of the
  workflow.

## Restoring the buggy demo after a successful run

A successful run rewrites `order_processing_system.py` itself.
Keep a restore copy before the first live run:

```powershell
Copy-Item complex_sample\order_processing_system.py complex_sample\order_processing_system_buggy_copy.txt
# restore later:
Copy-Item complex_sample\order_processing_system_buggy_copy.txt complex_sample\order_processing_system.py
```

(The `.txt` copy is never loaded by BugFixer.)
