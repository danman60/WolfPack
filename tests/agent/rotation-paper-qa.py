#!/usr/bin/env python3
"""Real local-browser acceptance through QA Agent's existing WebExecutor.

No model calls, mocked prices, stable production endpoints, or injected portfolio state.
The explicit URL must be localhost or an authorized immutable workshop preview.
"""
import argparse
import json
import re
import sys
import time
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path.home() / "projects/qa-agent"))
from executors.web import WebExecutor


def target_origin(url, workshop_preview=False):
    parsed = urlparse(url)
    local = (parsed.scheme, parsed.hostname, parsed.port) == ("http", "127.0.0.1", 3218)
    preview = workshop_preview and parsed.scheme == "https" and parsed.port is None and bool(
        re.fullmatch(r"wolf-pack-[a-z0-9]{9}-danman60s-projects\.vercel\.app", parsed.hostname or "")
    )
    if not (local or preview) or parsed.path != "/rotation" or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("An explicit isolated localhost URL or immutable workshop preview URL is required; stable production aliases are refused.")
    return f"{parsed.scheme}://{parsed.netloc}"


def run(url, report_dir, account_file=None, resume_opening=False, workshop_preview=False, protection_file=None):
    origin = target_origin(url, workshop_preview)
    print(f"QA target: {url}", flush=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    browser = WebExecutor()
    results = []
    requests = []
    markets = []
    previews = []

    def record(name, detail=None):
        results.append({"check": name, "status": "PASS", "detail": detail})
        print(f"PASS {name}", flush=True)

    def until(probe, message, seconds=35):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = probe()
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(message)

    def portfolio():
        response = browser.context.request.get(origin + "/api/rotation/portfolio")
        assert response.ok, f"Authenticated portfolio read returned {response.status}"
        return response.json()["portfolio"]

    def save_state(name):
        value = portfolio()
        (report_dir / f"{name}.json").write_text(json.dumps(value, indent=2))
        (report_dir / f"{name}.aria.txt").write_text(browser.snapshot())
        return value

    def field(names, value, select=False):
        snapshot = browser.snapshot()
        options = re.findall(r'(textbox|spinbutton|combobox) "([^"\n]+)"', snapshot)
        chosen = next(((role, label) for expected in names for role, label in options
                       if label.casefold() == expected.casefold()), None)
        if chosen is None:
            chosen = next(((role, label) for expected in names for role, label in options
                           if label.casefold().startswith(expected.casefold() + " ")), None)
        if chosen is None:
            raise AssertionError(f"Field {names} not found. Available: {options}")
        result = (browser.select_option if select else browser.fill)(*chosen, str(value))
        assert result[0], result[1]

    def click(names):
        snapshot = browser.snapshot()
        labels = re.findall(r'button "([^"\n]+)"', snapshot)
        name = next((label for expected in names for label in labels
                     if label.casefold() == expected.casefold()), None)
        if name is None:
            raise AssertionError(f"Button {names} not found. Available: {labels}")
        result = browser.click("button", name)
        assert result[0], result[1]
        return name

    def capture_market(response):
        if response.url.startswith(origin + "/api/rotation/") and response.ok:
            try:
                value = response.json()
                if "books" in value:
                    markets.append(value)
                elif "market" in value:
                    markets.append(value["market"])
                if "preview" in value:
                    previews.append(value["preview"])
            except Exception:
                pass

    def profit_at(p, market):
        value = Decimal(p["balances"]["CAD"])
        for asset in ("BTC", "ETH", "LINK"):
            book = market["books"][asset]
            midpoint = (Decimal(book["bid"]) + Decimal(book["ask"])) / 2
            value += Decimal(p["balances"][asset]) * midpoint
        return value - Decimal(p["initialValueCad"]) - Decimal(p["netFlowsCad"])

    try:
        assert browser.setup(), "Browser setup failed"
        if protection_file:
            assert workshop_preview, "Vercel automation access is only permitted for explicit preview QA"
            protected = browser.context.request.get(url, headers={
                "x-vercel-protection-bypass": protection_file.read_text().strip(),
                "x-vercel-set-bypass-cookie": "true",
            })
            assert protected.ok, f"Authorized preview access failed: {protected.status}"
        browser.set_viewport(1440, 1000)
        browser.page.on("request", lambda request: requests.append(request.url))
        browser.page.on("response", capture_market)
        assert browser.navigate(url), "Local workspace navigation failed"
        until(lambda: "Enter paper demo" in browser.snapshot(), "Demo access did not render")
        anonymous = browser.context.request.get(origin + "/api/rotation/portfolio")
        assert anonymous.status == 401, f"Anonymous portfolio request returned {anonymous.status}"
        if account_file:
            account = json.loads(account_file.read_text())["isolation"]
            field(["Email"], account["email"])
            field(["Password"], account["password"])
            click(["Sign in"])
        else:
            click(["Enter paper demo"])
        until(lambda: "Sign out" in browser.snapshot(), "Authenticated workspace did not render")
        readiness = browser.context.request.get(origin + "/api/rotation/readiness")
        assert readiness.ok and readiness.json()["mode"] == "paper-workshop" and readiness.json()["liveTrading"] == "disabled", "Target must attest paper-only mode before any QA writes"
        opening = portfolio()
        if opening is not None:
            assert resume_opening and opening["revision"] == 0 and len(opening["events"]) == 1, "Existing paper state cannot be overwritten; only explicit opening-only resume is allowed"
        browser.context.storage_state(path=str(report_dir / "browser-session.json"))
        (report_dir / "browser-session.json").chmod(0o600)
        record("anonymous access refused and real workshop session established")

        if opening is None:
            until(lambda: "Create paper portfolio" in browser.snapshot(), "Opening form did not render")
            field(["Portfolio name", "Paper portfolio name"], "Rotation browser QA")
            for asset, value in (("CAD", "10000"), ("BTC", "0"), ("ETH", "0"), ("LINK", "0")):
                field([f"Opening {asset}", f"Opening {asset} amount", f"{asset} opening balance"], value)
            field(["Fee (bps)", "Trading fee (bps)", "Fee basis points"], "20")
            field(["Review cadence", "Cadence"], "weekly", select=True)
        until(lambda: markets, "Public market quote did not load")
        if opening is None:
            click(["Create paper portfolio"])
            opening = until(portfolio, "Portfolio was not persisted")
        assert opening["balances"] == opening["baseline"] == opening["opening"]
        assert Decimal(opening["initialValueCad"]) == 10000
        assert Decimal(opening["netFlowsCad"]) == Decimal(opening["feesCad"]) == 0
        assert opening["feeBps"] == 20 and opening["cadence"] == "weekly"
        assert profit_at(opening, markets[-1]) == 0
        save_state("01-opening")
        record("opening balances and untouched HOLD")

        field(["From", "Sell asset"], "CAD", select=True)
        field(["To", "Buy asset"], "BTC", select=True)
        field(["Amount", "Shift amount", "Amount to move"], "1000")
        click(["Preview shift", "Review shift"])
        until(lambda: "Approve paper shift" in browser.snapshot(), "Cost preview did not render")
        assert portfolio() == opening, "Preview changed holdings before approval"
        assert previews, "No actual quote response captured"
        expected_quote = previews[-1]
        (report_dir / "02-preview.aria.txt").write_text(browser.snapshot())
        approved_button = click(["Approve paper shift"])
        shifted = until(lambda: (p if (p := portfolio())["revision"] > opening["revision"] else None),
                        "Approval was not persisted")
        assert shifted["baseline"] == opening["baseline"]
        assert shifted["opening"] == opening["opening"]
        assert shifted["balances"] == expected_quote["after"]
        assert Decimal(shifted["feesCad"]) == Decimal(expected_quote["feeCad"])
        assert Decimal(shifted["balances"]["BTC"]) > 0
        spent = Decimal(opening["balances"]["CAD"]) - Decimal(shifted["balances"]["CAD"])
        assert 0 < spent <= 1000
        assert Decimal(shifted["feesCad"]) > 0
        assert len([e for e in shifted["events"] if e["kind"] == "shift"]) == 1
        # A settled UI must remove/disable the exact approved action. Replaying any
        # still-exposed action may reject; it must never append a second shift.
        approval_line = next((line for line in browser.snapshot().splitlines()
                              if f'button "{approved_button}"' in line), "")
        if approval_line and "disabled" not in approval_line:
            browser.click("button", approved_button)
        assert portfolio() == shifted, "Repeated approval changed paper ledger"
        save_state("03-shift")
        record("single approved paper fill and duplicate-action protection", {"spentCad": str(spent)})

        click(["Record HOLD", "Hold this review", "Keep holding"])
        held = until(lambda: (p if (p := portfolio())["revision"] > shifted["revision"] else None),
                     "HOLD decision was not persisted")
        assert held["balances"] == shifted["balances"] and held["feesCad"] == shifted["feesCad"]
        assert held["events"][-1]["kind"] == "hold"
        assert browser.navigate(url), "Reload failed"
        until(lambda: "Create paper portfolio" not in browser.snapshot(), "Reload did not restore portfolio")
        assert portfolio() == held
        save_state("04-reloaded")
        record("HOLD preserves units and reload preserves ledger")

        field(["Cash flow type", "Cash movement", "Flow type"], "deposit", select=True)
        field(["Cash flow amount", "CAD amount", "Cash amount"], "100")
        click(["Record cash flow", "Record cash movement", "Add deposit"])
        deposited = until(lambda: (p if (p := portfolio())["revision"] > held["revision"] else None),
                          "Deposit did not persist")
        assert Decimal(deposited["balances"]["CAD"]) - Decimal(held["balances"]["CAD"]) == 100
        assert Decimal(deposited["baseline"]["CAD"]) - Decimal(held["baseline"]["CAD"]) == 100
        assert Decimal(deposited["netFlowsCad"]) - Decimal(held["netFlowsCad"]) == 100
        assert profit_at(deposited, markets[-1]) == profit_at(held, markets[-1])
        assert deposited["opening"] == opening["opening"]
        save_state("05-deposited")
        record("matched CAD deposit has zero profit effect under identical marks")

        field(["Cash flow type", "Cash movement", "Flow type"], "withdrawal", select=True)
        field(["Cash flow amount", "CAD amount", "Cash amount"], "999999")
        click(["Record cash flow", "Record cash movement", "Record withdrawal"])
        assert portfolio() == deposited, "Rejected withdrawal modified ledger"
        until(lambda: any("withdrawal requires enough cad" in text.lower()
                          for text in browser.page.get_by_role("alert").all_text_contents()), "Withdrawal error not visible")
        record("insufficient withdrawal rejected without state changes")

        with browser.page.expect_download() as download_event:
            click(["Export ledger", "Export JSON", "Export paper ledger"])
        exported = report_dir / "exported-ledger.json"
        download_event.value.save_as(str(exported))
        export_data = json.loads(exported.read_text())
        assert export_data["portfolio"] == deposited
        assert isinstance(export_data["trials"], list) and isinstance(export_data["audit"], list)
        approved = [event for event in deposited["events"] if event["kind"] == "shift"][0]
        filled = [preview for preview in export_data["previews"] if preview["id"] == approved["id"]]
        assert len(filled) == 1 and filled[0]["data"]["preview"]["after"] == shifted["balances"], "Export must reconcile approved event to its exact stored quote"
        record("exported artifact matches actual persisted ledger")

        click(["Advanced research"])
        (report_dir / "before-research.aria.txt").write_text(browser.snapshot())
        # Exact research field labels are intentionally explicit and checked against
        # the composed page, rather than inferred from an internal implementation.
        field(["Historical scenario capital (CAD)", "Research capital (CAD)", "Research capital", "Starting CAD"], "10000")
        field(["Research cadence", "Review cadence"], "weekly", select=True)
        field(["Lookback (14–180 calendar days)", "Lookback days", "Lookback (days)"], "30")
        field(["Crypto allocation (0–100%)", "Allocation (%)", "Risk allocation (%)", "Crypto allocation (%)"], "50")
        field(["Fee per leg (basis points)", "Research fee (bps)", "Research fees (bps)"], "20")
        field(["Adverse slippage (basis points)", "Slippage (bps)", "Research slippage (bps)"], "10")
        click(["Register scenario & run research", "Run research", "Run historical comparison"])
        snapshot = until(lambda: (s if any(x in (s := browser.snapshot()).lower() for x in
                         ("worst daily drawdown", "data unavailable", "history unavailable", "historical request failed")) else None),
                         "Research produced neither results nor a clear source failure", seconds=90)
        (report_dir / "06-research.aria.txt").write_text(snapshot)
        assert "worst daily drawdown" in snapshot.lower(), "Source failure is reported honestly but does not satisfy research acceptance"
        record("genuine-data research result rendered and persisted")

        for width, height in ((1440, 1000), (390, 844)):
            browser.set_viewport(width, height)
            browser.screenshot(str(report_dir / f"workspace-{width}.png"))
        browser.context.storage_state(path=str(report_dir / "browser-session.json"))
        (report_dir / "browser-session.json").chmod(0o600)
        assert not any("/intel/" in request for request in requests), "Rotation contacted legacy intelligence"
        application_errors = browser.get_console_errors(False)
        (report_dir / "console.json").write_text(json.dumps(application_errors, indent=2))
        record("rotation did not contact legacy /intel endpoints")
    except Exception as error:
        results.append({"check": "run", "status": "FAIL", "detail": str(error)})
        print(f"FAIL {error}", flush=True)
        if browser.page:
            (report_dir / "failure.aria.txt").write_text(browser.snapshot())
            browser.screenshot(str(report_dir / "failure.png"))
        return 1
    finally:
        (report_dir / "requests.json").write_text(json.dumps(requests, indent=2))
        (report_dir / "checks.json").write_text(json.dumps(results, indent=2))
        browser.teardown()
    return 0


def inspect_saved(url, report_dir, state_file, workshop_preview=False):
    """Read-only follow-up plus the intentionally refused future-holdout action."""
    origin = target_origin(url, workshop_preview)
    print(f"QA target: {url}", flush=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    browser = WebExecutor()
    findings = {}
    try:
        browser.setup()
        browser.context.add_cookies(json.loads(state_file.read_text())["cookies"])
        assert browser.navigate(url)
        deadline = time.monotonic() + 30
        while "Advanced research" not in browser.snapshot() and time.monotonic() < deadline:
            time.sleep(0.2)
        read = lambda path: browser.context.request.get(origin + "/api/rotation/" + path)
        portfolio_response = read("portfolio")
        assert portfolio_response.ok
        saved = portfolio_response.json()["portfolio"]
        assert saved and saved["revision"] == 3
        findings["serverPortfolioReload"] = {"id": saved["id"], "revision": saved["revision"]}
        readiness = read("readiness")
        assert readiness.ok
        status = readiness.json()
        assert status["database"] == status["auth"] == "operational"
        assert status["liveTrading"] == "disabled"
        findings["readiness"] = status
        trials_response = read("trials")
        assert trials_response.ok
        trials = trials_response.json()["trials"]
        assert {"protocol", "development"}.issubset({trial["kind"] for trial in trials})
        findings["retainedTrials"] = len(trials)
        assert browser.click("button", "Advanced research")[0]
        deadline = time.monotonic() + 30
        while "Chronological evaluation" not in browser.snapshot() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert "Chronological evaluation" in browser.snapshot(), "Saved result was not restored"
        before = read("trials").json()["trials"]
        assert browser.click("button", "Check holdout eligibility")[0]
        deadline = time.monotonic() + 20
        alerts = []
        while not alerts and time.monotonic() < deadline:
            alerts = [text for text in browser.page.get_by_role("alert").all_text_contents() if text.strip()]
            time.sleep(0.2)
        assert alerts and any("holdout" in text.lower() for text in alerts), "Future holdout refusal was not visible"
        assert read("trials").json()["trials"] == before, "Refused future holdout appended a trial"
        findings["futureHoldoutRefused"] = alerts
        exported_response = read("portfolio?export=1")
        assert exported_response.ok
        exported = exported_response.json()
        assert exported["portfolio"] == saved
        assert {"protocol", "development"}.issubset({trial["kind"] for trial in exported["trials"]})
        assert exported["audit"], "Full export omitted audit history"
        (report_dir / "complete-export.json").write_text(json.dumps(exported, indent=2))
        findings["fullExport"] = {"trials": len(exported["trials"]), "audit": len(exported["audit"])}
        # Capture the ordinary saved-result screen after the intentional refusal check.
        assert browser.navigate(url)
        deadline = time.monotonic() + 30
        while "Advanced research" not in browser.snapshot() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert browser.click("button", "Advanced research")[0]
        deadline = time.monotonic() + 30
        while "Chronological evaluation" not in browser.snapshot() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert "Chronological evaluation" in browser.snapshot()
        findings["viewports"] = []
        for width in (1440, 390, 360, 320):
            browser.set_viewport(width, 1000 if width == 1440 else 844)
            time.sleep(1)  # Allow ResponsiveContainer's ResizeObserver to settle.
            sizes = browser.page.evaluate("({client:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth})")
            if sizes["scroll"] != sizes["client"]:
                browser.screenshot(str(report_dir / f"overflow-{width}.png"))
                findings["overflowElements"] = browser.page.evaluate("Array.from(document.querySelectorAll('body *')).map(e=>({tag:e.tagName,cls:e.className,w:e.getBoundingClientRect().width,right:e.getBoundingClientRect().right})).filter(e=>e.right>window.innerWidth+1).slice(0,30)")
            assert sizes["scroll"] == sizes["client"], f"Page overflow at {width}: {sizes}"
            findings["viewports"].append({"width": width, **sizes})
            if width in (1440, 390):
                full_height = browser.page.evaluate("document.documentElement.scrollHeight")
                browser.set_viewport(width, full_height)
                browser.page.evaluate("window.scrollTo(0,0)")
                time.sleep(0.3)
                screenshot = report_dir / f"research-{width}.png"
                browser.screenshot(str(screenshot))
                shot_source = (Path.home() / ".local/bin/shot").read_text()
                dom_function = shot_source.split("const domChecks = ", 1)[1].split(";\n\nconst browser", 1)[0]
                measured = browser.page.evaluate(dom_function)
                browser.page.add_script_tag(content=(Path.home() / ".claude/tools/shot/node_modules/axe-core/axe.min.js").read_text())
                contrast = browser.page.evaluate("async () => (await window.axe.run(document,{runOnly:['color-contrast']})).violations")
                for violation in contrast:
                    for node in violation["nodes"]:
                        measured["fail"].append({"check": "contrast", "el": " ".join(node["target"]), "detail": violation["help"]})
                stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%dT%H%M%S")
                held = Path.home() / f".claude/shots/pending/wolfpack-rotation-research-{'preview' if workshop_preview else 'local'}-{width}-{stamp}.png"
                shutil.copyfile(screenshot, held)
                review = {"url": url, "width": width, "png": str(held), "captured": datetime.now(ZoneInfo("America/New_York")).isoformat(), "pass": not measured["fail"], **measured}
                Path(str(held) + ".review.json").write_text(json.dumps(review, indent=2))
                findings.setdefault("measuredScreenshots", []).append(review)
                assert review["pass"], f"Research mechanical screenshot check failed: {measured['fail']}"

        (report_dir / "research.aria.txt").write_text(browser.snapshot())
        findings["console"] = browser.get_console_errors(False)
        findings["status"] = "PASS"
        print(json.dumps({k: v for k, v in findings.items() if k != "console"}, indent=2), flush=True)
        return 0
    except Exception as error:
        findings["status"] = "FAIL"
        findings["error"] = str(error)
        print(f"FAIL {error}", flush=True)
        if browser.page:
            (report_dir / "failure.aria.txt").write_text(browser.snapshot())
        return 1
    finally:
        (report_dir / "inspection.json").write_text(json.dumps(findings, indent=2))
        browser.teardown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--account-file", type=Path, help="Private seeded isolation login JSON; omitted tests one-click demo.")
    parser.add_argument("--resume-opening", action="store_true", help="Continue an existing revision-zero QA opening without resetting server data.")
    parser.add_argument("--inspect-state", type=Path, help="Read saved results and readiness using an existing private browser cookie artifact.")
    parser.add_argument("--workshop-preview", action="store_true", help="Permit an explicit immutable Vercel workshop preview; stable production aliases remain forbidden.")
    parser.add_argument("--protection-file", type=Path, help="Private Vercel automation secret; sets only deployment protection cookie, never app auth.")
    args = parser.parse_args()
    raise SystemExit(inspect_saved(args.url, args.report_dir, args.inspect_state, args.workshop_preview) if args.inspect_state else
                     run(args.url, args.report_dir, args.account_file, args.resume_opening, args.workshop_preview, args.protection_file))
