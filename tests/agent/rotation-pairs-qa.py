#!/usr/bin/env python3
"""Bounded real-browser BTC -> ETH -> LINK -> CAD paper acceptance.

Uses QA Agent WebExecutor and the existing immutable-preview target gate. The
separate seeded synthetic account must already own BTC; no state is overwritten.
"""
import argparse
import importlib.util
import json
import re
import time
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from zoneinfo import ZoneInfo

spec = importlib.util.spec_from_file_location("rotation_existing_qa", Path(__file__).with_name("rotation-paper-qa.py"))
existing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(existing)
WebExecutor = existing.WebExecutor
UNIT = Decimal("0.00000001")


def run(args):
    origin = existing.target_origin(args.url, args.workshop_preview)
    requested_btc = Decimal(args.btc_amount)
    assert Decimal("0") < requested_btc <= Decimal("0.001"), "QA first leg is explicitly bounded to at most 0.001 BTC"
    print(f"QA target: {args.url}", flush=True)
    output = args.report_dir
    output.mkdir(parents=True, exist_ok=True)
    browser = WebExecutor()
    captured = []
    response_diagnostics = []
    report = {"target": args.url, "mode": "paper-only", "startedEastern": datetime.now(ZoneInfo("America/Toronto")).isoformat(), "checks": []}

    def record(name, detail=None):
        report["checks"].append({"check": name, "status": "PASS", "detail": detail})
        print(f"PASS {name}", flush=True)

    def until(probe, message, seconds=40):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = probe()
            if result:
                return result
            time.sleep(0.2)
        raise AssertionError(message)

    def read(path):
        response = browser.context.request.get(origin + "/api/rotation/" + path)
        assert response.ok, f"Authoritative {path} read returned {response.status}"
        return response.json()

    def portfolio():
        return read("portfolio")["portfolio"]

    def field(label, text, select=False):
        options = re.findall(r'(textbox|spinbutton|combobox) "([^"\n]+)"', browser.snapshot())
        choice = next(((role, name) for role, name in options if name.casefold() == label.casefold()), None)
        if choice is None:
            choice = next(((role, name) for role, name in options if name.casefold().startswith(label.casefold() + " ")), None)
        assert choice, f"Visible field {label} was not found"
        ok, detail = (browser.select_option if select else browser.fill)(*choice, str(text))
        assert ok, detail

    def click(label):
        ok, detail = browser.click("button", label)
        assert ok, detail

    def capture(response):
        if response.url == origin + "/api/rotation/preview" and response.ok:
            response_diagnostics.append({"event": "preview-response", "status": response.status})
            captured.append(response.json())

    def screenshot(name, full=False):
        if full:
            height = browser.page.evaluate("document.documentElement.scrollHeight")
            browser.set_viewport(1440, height)
            browser.page.evaluate("window.scrollTo(0,0)")
        browser.screenshot(str(output / f"{name}.png"))
        (output / f"{name}.aria.txt").write_text(browser.snapshot())
        if full:
            browser.set_viewport(1440, 1100)

    try:
        assert browser.setup(), "QA Agent browser setup failed"
        browser.set_viewport(1440, 1100)
        if args.protection_file:
            assert args.workshop_preview, "Protection access requires explicit workshop preview mode"
            access = browser.context.request.get(args.url, headers={
                "x-vercel-protection-bypass": args.protection_file.read_text().strip(),
                "x-vercel-set-bypass-cookie": "true",
            })
            assert access.ok, f"Preview protection access returned {access.status}"
        browser.page.on("response", capture)
        assert browser.navigate(args.url), "Workspace navigation failed"
        until(lambda: "Enter paper demo" in browser.snapshot(), "Sign-in screen did not render")
        account = json.loads(args.account_file.read_text())[args.account_key]
        field("Email", account["email"])
        field("Password", account["password"])
        click("Sign in")
        until(lambda: "Sign out" in browser.snapshot(), "Separate synthetic account did not authenticate")
        session = read("session")
        # The explicitly authorized seeded isolation fixture is synthetic even
        # when its membership tests the ordinary (is_demo=false) login path.
        assert session["authenticated"] and session["user"]["email"] == account["email"], "Authenticated identity must exactly match the separate authorized QA fixture"
        readiness = read("readiness")
        assert readiness["mode"] == "paper-workshop" and readiness["liveTrading"] == "disabled", "Writes require authoritative paper-only readiness"
        initial = portfolio()
        assert initial and Decimal(initial["balances"]["BTC"]) >= requested_btc, "Separate synthetic portfolio must already own the bounded BTC amount"
        assert initial["feeBps"] > 0, "This acceptance case requires a positive configured fee"
        report["portfolioId"] = initial["id"]
        report["startingRevision"] = initial["revision"]
        report["opening"] = initial["opening"]
        report["holdBaseline"] = initial["baseline"]
        (output / "initial-portfolio.json").write_text(json.dumps(initial, indent=2))
        browser.context.storage_state(path=str(output / "browser-session.json"))
        (output / "browser-session.json").chmod(0o600)
        record("separate authenticated synthetic account; existing ledger preserved", {"revision": initial["revision"], "btcAmount": str(requested_btc)})

        current = initial
        amount = str(requested_btc)
        for number, (source, destination) in enumerate((("BTC", "ETH"), ("ETH", "LINK"), ("LINK", "CAD")), 1):
            field("From", source, select=True)
            field("To", destination, select=True)
            field("Amount", amount)
            prior_quotes = len(captured)
            click("Preview shift")
            before_snapshot = len(captured)
            visible_preview = "Approve paper shift" in browser.snapshot()
            response_diagnostics.append({"event": "preview-dispatch-probe", "beforeBrowserRead": before_snapshot, "afterBrowserRead": len(captured), "visiblePreview": visible_preview})
            # A browser RPC must occur first: otherwise the pure Python length
            # check short-circuits and starves Playwright's event dispatch while
            # the quote is visibly rendered in Chromium.
            until(lambda: "Approve paper shift" in browser.snapshot() and len(captured) > prior_quotes, f"{source}->{destination} preview did not render")
            payload = captured[-1]
            quote, market = payload["preview"], payload["market"]
            assert portfolio() == current, "A preview changed authoritative balances"
            assert quote["from"] == source and quote["to"] == destination and Decimal(quote["amount"]) == Decimal(amount)
            expected_sides = [("sell", source)] + ([("buy", destination)] if destination != "CAD" else [])
            assert [(leg["side"], leg["asset"]) for leg in quote["legs"]] == expected_sides
            expected = {asset: Decimal(units) for asset, units in current["balances"].items()}
            total_fee = Decimal(0)
            for leg in quote["legs"]:
                quantity = Decimal(leg["quantity"])
                remaining, raw_gross = quantity, Decimal(0)
                book = market["books"][leg["asset"]]
                for level in book["asks" if leg["side"] == "buy" else "bids"]:
                    taken = min(remaining, Decimal(level["quantity"]))
                    raw_gross += taken * Decimal(level["price"])
                    remaining -= taken
                    if remaining == 0:
                        break
                assert remaining == 0, "Captured depth cannot independently fill the quoted amount"
                rounding = ROUND_CEILING if leg["side"] == "buy" else ROUND_FLOOR
                gross = raw_gross.quantize(UNIT, rounding=rounding)
                fee = (gross * Decimal(current["feeBps"]) / Decimal(10000)).quantize(UNIT, rounding=ROUND_CEILING)
                assert gross == Decimal(leg["grossCad"]), "Independent order-book gross does not reconcile"
                assert fee == Decimal(leg["feeCad"]) and fee > 0, "Independent per-leg fee does not reconcile"
                if leg["side"] == "sell":
                    expected[leg["asset"]] -= quantity
                    expected["CAD"] += gross - fee
                else:
                    expected[leg["asset"]] += quantity
                    expected["CAD"] -= gross + fee
                total_fee += fee
            assert total_fee == Decimal(quote["feeCad"])
            assert all(units >= 0 for units in expected.values())
            if destination != "CAD":
                assert expected["CAD"] >= Decimal(current["balances"]["CAD"]), "Cross conversion spent unrelated CAD"
            (output / f"{number:02}-{source}-{destination}-quote.json").write_text(json.dumps(payload, indent=2))
            screenshot(f"{number:02}-{source}-{destination}-preview")
            click("Approve paper shift")
            updated = until(lambda: (p if (p := portfolio())["revision"] > current["revision"] else None), f"{source}->{destination} approval did not persist")
            assert updated["revision"] == current["revision"] + 1
            assert updated["opening"] == initial["opening"] and updated["baseline"] == initial["baseline"], "Original HOLD units changed"
            assert updated["netFlowsCad"] == initial["netFlowsCad"]
            assert updated["events"][:-1] == current["events"], "Existing ledger history was modified"
            assert updated["events"][-1]["id"] == quote["id"] and updated["events"][-1]["kind"] == "shift"
            assert updated["balances"] == quote["after"]
            assert all(Decimal(updated["balances"][asset]) == units for asset, units in expected.items())
            assert Decimal(updated["feesCad"]) - Decimal(current["feesCad"]) == total_fee
            (output / f"{number:02}-{source}-{destination}-portfolio.json").write_text(json.dumps(updated, indent=2))
            record(f"{source} to {destination}: approved real-book paper fill, independent fees, immutable HOLD", {
                "previewId": quote["id"], "fromAmount": amount, "received": quote["received"], "feesCad": str(total_fee), "legs": quote["legs"], "revision": updated["revision"],
            })
            amount = quote["received"]
            current = updated

        assert browser.navigate(args.url), "Final reload failed"
        until(lambda: "Refresh ledger" in browser.snapshot(), "Final ledger did not reload")
        assert portfolio() == current, "Reload altered the server ledger"
        screenshot("04-final-ledger", full=True)
        record("three approved shifts survive reload; original HOLD unchanged", {"endingRevision": current["revision"], "totalNewFeesCad": str(Decimal(current["feesCad"]) - Decimal(initial["feesCad"]))})
        report["console"] = browser.get_console_errors(False)
        assert not report["console"], "Unexpected browser console errors"
        report["status"] = "PASS"
        return 0
    except Exception as error:
        report["status"] = "FAIL"
        report["error"] = str(error)
        print(f"FAIL {error}", flush=True)
        if browser.page:
            screenshot("failure")
        return 1
    finally:
        report["responseDiagnostics"] = response_diagnostics
        (output / "checks.json").write_text(json.dumps(report, indent=2))
        browser.teardown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--account-file", type=Path, required=True)
    parser.add_argument("--account-key", required=True)
    parser.add_argument("--btc-amount", required=True)
    parser.add_argument("--workshop-preview", action="store_true")
    parser.add_argument("--protection-file", type=Path)
    raise SystemExit(run(parser.parse_args()))
