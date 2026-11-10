"""Embed archived specifications and reconciled findings in the running document.

The prose above the marker is maintained by hand. Appended sections are rebuilt
from saved evidence without changing historical experiment outputs.
"""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
MARKER = "<!-- BEGIN GENERATED CONSOLIDATED APPENDICES -->"


def rebase(text, parent):
    """Move a Markdown excerpt to equity/ while preserving relative links."""
    def replace(match):
        target = match.group(2)
        if re.match(r"(?:https?://|#|/)", target):
            return match.group(0)
        import os
        target = os.path.relpath(parent / target, ROOT)
        return match.group(1) + target + match.group(3)
    return re.sub(r"(!?\[[^\]]*\]\()([^\s)]+)(\))", replace, text)


def demote(text):
    return re.sub(r"(?m)^(#{1,5}) ", r"#\1 ", text)


def main():
    path = ROOT / "EQUITY_RESEARCH_LOG.md"
    prose = path.read_text().split(MARKER)[0].rstrip()
    validation = ROOT / "EQUITY_VALIDATION.md"
    recent = ROOT / "experiments/equity_recent_refresh_2026_11_10/README.md"
    pieces = [prose, MARKER,
        "## Appendix A — Reconciled performance and risk findings\n\n"
        "The complete validated comparison is reproduced here for one-document reading. "
        "These metrics use the October 27 data vintage and original experiment periods; "
        "they are not updated strategy results through November 9.\n\n" + demote(validation.read_text()),
        "## Appendix B — Complete executed method specifications\n\n"
        "These are the complete saved specifications, embedded verbatim as JSON so exact "
        "windows, features, fitting, thresholds, target timing, missingness, comparison "
        "families and random seeds can be read in this document. Expand an experiment "
        "for its technical detail. Findings and interpretations are in entries 01–23 "
        "and Appendix A/C. Archived instructions describe their own experiment only. "
        "Historical cost scenarios in the original frozen backtest specification are "
        "superseded by the October 28 gross/pre-fee reporting instruction; they are "
        "retained as provenance, not current assumptions."]
    specs = sorted(p for p in (ROOT / "experiments").glob("*/specification.json"))
    specs += [ROOT / "experiments/equity_residual_backtest/frozen_specification.json",
              ROOT / "experiments/equity_residual_diagnostics/diagnostic_specification.json"]
    records = []
    for source in sorted(specs):
        relative = source.relative_to(ROOT)
        title = source.parent.name.replace("_", " ")
        value = json.loads(source.read_text())
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        records.append({"source": str(relative), "sha256": digest})
        pieces.append(f"### {title}\n\n"
            f"Original: [{relative}]({relative}). SHA256 `{digest}`.\n\n"
            f"<details>\n<summary>Complete saved method specification</summary>\n\n"
            f"```json\n{json.dumps(value, indent=2)}\n```\n\n</details>")
    initial = ROOT / "experiments/equity_correlation_pca/summary.json"
    pieces.append("### Initial correlation/PCA descriptive analysis\n\n"
        "The initial study stores its settings and exact descriptive results together "
        "rather than in a separate specification. Its complete summary follows.\n\n"
        "<details>\n<summary>Initial descriptive settings and findings</summary>\n\n"
        "```json\n" + json.dumps(json.loads(initial.read_text()), indent=2) + "\n```\n\n</details>")
    for data_name in ["equity_daily_expanded_2016_2026-10-27", "equity_daily_expanded_2016_2026-11-09"]:
        source = ROOT.parent / "market_data/datasets" / data_name / "collection_plan.json"
        pieces.append(f"### Data collection: {data_name}\n\n"
            "<details>\n<summary>Complete collection design</summary>\n\n```json\n" +
            json.dumps(json.loads(source.read_text()), indent=2) + "\n```\n\n</details>")
        records.append({"source": str(source.relative_to(ROOT.parent)), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    pieces.append("## Appendix C — Complete recent-data and unwind assessment\n\n" +
                  demote(rebase(recent.read_text(), recent.parent)))
    pieces.append("## Consolidation provenance\n\n"
        f"Generated with [build_equity_compendium.py](experiments/build_equity_compendium.py). "
        f"Contains {len(specs)} full experiment specifications, the original descriptive "
        "summary, both expanded data-collection designs, the full validated comparison "
        "ledger and the complete recent-update assessment. This is documentation "
        "consolidation; it does not rerun archived models. Rebuild after updating the "
        "source documents; maintain new numbered entries above the generated marker.")
    path.write_text("\n\n".join(pieces).rstrip()+"\n")
    provenance = ROOT / "experiments/equity_recent_refresh_2026_11_10/consolidation_sources.json"
    provenance.write_text(json.dumps({"embedded_specifications": len(specs), "sources": records,
        "validation_sha256": hashlib.sha256(validation.read_bytes()).hexdigest(),
        "recent_report_sha256": hashlib.sha256(recent.read_bytes()).hexdigest()}, indent=2)+"\n")
    print(f"Consolidated {len(specs)} method specifications into {path.name}")


if __name__ == "__main__":
    main()
