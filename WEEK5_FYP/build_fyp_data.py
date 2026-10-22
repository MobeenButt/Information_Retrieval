"""Build the FYP browser dataset from both supplied SWE-bench files.

The JSONL and Parquet files contain the same 300 instance IDs. JSONL is used
as the canonical record source and Parquet is read for validation and source
provenance. The output is normalized to the FYP Incident/Evidence/Claim shape.
"""
from __future__ import annotations

import ast
import json
import zipfile
from pathlib import Path

import pandas as pd


HERE = Path(__file__).resolve().parent
JSONL = HERE / "swebench_lite.jsonl"
PARQUET = HERE / "test1.parquet"
OUTPUT = HERE / "fyp_data.json"


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        parsed = ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        return [str(value)] if value and str(value) != "nan" else []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def first_line(text: object, fallback: str) -> str:
    value = str(text or "").strip()
    return next((line.strip("# ").strip() for line in value.splitlines() if line.strip()), fallback)


def evidence(incident_id: str, evidence_id: str, kind: str, source: str,
             locator: str, summary: str, content: str, relevance: float,
             timestamp: str) -> dict:
    return {
        "id": evidence_id,
        "incident_id": incident_id,
        "type": kind,
        "source": source,
        "locator": locator,
        "content_ref": locator,
        "summary": summary[:500],
        "relevance": relevance,
        "timestamp": timestamp,
        "content": content,
    }


def main() -> None:
    records = [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    parquet = pd.read_parquet(PARQUET)
    json_ids = {record["instance_id"] for record in records}
    parquet_ids = set(parquet["instance_id"].astype(str))
    if json_ids != parquet_ids:
        raise ValueError("JSONL and Parquet instance IDs do not match")

    incidents: list[dict] = []
    all_evidence: list[dict] = []
    claims: list[dict] = []
    graph_nodes: list[dict] = []
    graph_edges: list[dict] = []
    category_incidents: dict[str, list[str]] = {}

    def add_record(iid: str, title: str, category: str, repository: str,
                   created: str, items: list[dict], metadata: dict | None = None) -> None:
        incidents.append({
            "id": iid, "title": title[:300], "status": "INVESTIGATING",
            "severity": "medium", "repository": repository, "commit": "",
            "created_at": created, "category": category, **(metadata or {}),
        })
        category_incidents.setdefault(category, []).append(iid)
        all_evidence.extend(items)
        graph_nodes.extend([
            {"id": f"incident:{iid}", "type": "incident", "label": title[:100]},
            {"id": f"repo:{iid}", "type": "repository", "label": repository},
        ])
        for item in items:
            eid = item["id"]
            item["category"] = category
            graph_nodes.append({"id": f"evidence:{eid}", "type": item["type"], "label": item["summary"][:100]})
            graph_edges.append({"from": f"incident:{iid}", "to": f"evidence:{eid}", "type": "contains"})
        for left, right in zip(items, items[1:]):
            graph_edges.append({
                "from": f"evidence:{left['id']}", "to": f"evidence:{right['id']}",
                "type": "related_artifact",
            })
        claims.append({
            "id": f"{iid}:claim", "incident_id": iid,
            "statement": f"Evidence collected for {title[:180]}",
            "evidence_ids": [item["id"] for item in items[:4]],
            "confidence": .75,
        })
        graph_nodes.append({"id": f"claim:{iid}", "type": "claim", "label": "Evidence summary"})
        graph_edges.append({"from": f"incident:{iid}", "to": f"claim:{iid}", "type": "has_claim"})

    for record in records:
        iid = str(record["instance_id"])
        problem = str(record.get("problem_statement") or "")
        repo = str(record.get("repo") or "unknown")
        commit = str(record.get("base_commit") or "")
        created = str(record.get("created_at") or "")
        difficulty = str(record.get("difficulty") or "").lower()
        severity = "critical" if "4 hours" in difficulty else "high" if "1 hour" in difficulty else "medium"
        title = first_line(problem, iid)
        incidents.append({
            "id": iid,
            "title": title,
            "status": "INVESTIGATING",
            "severity": severity,
            "repository": repo,
            "commit": commit,
            "created_at": created,
            "version": record.get("version"),
            "difficulty": record.get("difficulty"),
        })

        failed = as_list(record.get("FAIL_TO_PASS"))
        passing = as_list(record.get("PASS_TO_PASS"))
        code_id = f"{iid}:code"
        test_id = f"{iid}:test"
        incident_evidence = [
            evidence(iid, f"{iid}:jira", "jira", "issue report", f"{repo}/{iid}",
                     "Original issue statement", problem, .95, created),
            evidence(iid, code_id, "code", repo, commit,
                     "Candidate patch supplied for the reported issue", str(record.get("patch") or ""), .92, created),
            evidence(iid, test_id, "test", repo, "FAIL_TO_PASS",
                     f"{len(failed)} regression test(s) expected to change from failing to passing",
                     "\n".join(failed), .94, created),
            evidence(iid, f"{iid}:regression", "test", repo, "PASS_TO_PASS",
                     f"{len(passing)} existing test(s) expected to remain passing",
                     "\n".join(passing), .86, created),
            evidence(iid, f"{iid}:commit", "commit", repo, commit,
                     "Base revision used by the benchmark", commit, .78, created),
            evidence(iid, f"{iid}:log", "log", "evaluation harness", str(record.get("log_parser") or "evaluation"),
                     "Evaluation and test execution metadata", str(record.get("eval_script") or ""), .70, created),
            evidence(iid, f"{iid}:slack", "slack", "investigation notes", "hints_text",
                     "Maintainer hints and investigation context", str(record.get("hints_text") or ""), .62, created),
            evidence(iid, f"{iid}:graph", "graph", "Knowledge Graph", f"incident:{iid}",
                     "Repository, commit, and test relationships for this incident",
                     f"repository={repo}; commit={commit}; version={record.get('version')}", .65, created),
        ]
        all_evidence.extend(incident_evidence)
        evidence_ids = [item["id"] for item in incident_evidence]
        claims.append({
            "id": f"{iid}:claim",
            "incident_id": iid,
            "statement": f"The supplied patch addresses the reported issue in {repo}.",
            "evidence_ids": [f"{iid}:jira", code_id, test_id],
            "confidence": .9 if failed else .78,
        })
        graph_nodes.extend([
            {"id": f"incident:{iid}", "type": "incident", "label": iid},
            {"id": f"repo:{repo}", "type": "repository", "label": repo},
            {"id": f"commit:{iid}", "type": "commit", "label": commit[:12]},
            {"id": f"test:{iid}", "type": "test", "label": f"{len(failed)} failing → passing"},
            {"id": f"claim:{iid}", "type": "claim", "label": "Root-cause claim"},
        ])
        graph_nodes.extend(
            {"id": f"evidence:{item['id']}", "type": item["type"], "label": item["summary"][:80]}
            for item in incident_evidence
        )
        graph_edges.extend([
            {"from": f"incident:{iid}", "to": f"repo:{repo}", "type": "in_repository"},
            {"from": f"incident:{iid}", "to": f"commit:{iid}", "type": "based_on"},
            {"from": f"incident:{iid}", "to": f"test:{iid}", "type": "verified_by"},
            {"from": f"incident:{iid}", "to": f"claim:{iid}", "type": "has_claim"},
            *[
                {"from": f"incident:{iid}", "to": f"evidence:{item_id}", "type": "contains"}
                for item_id in evidence_ids
            ],
            *[
                {"from": f"claim:{iid}", "to": f"evidence:{item_id}", "type": "supported_by"}
                for item_id in [f"{iid}:jira", code_id, test_id]
            ],
            {"from": f"evidence:{iid}:jira", "to": f"evidence:{code_id}", "type": "related_code"},
            {"from": f"evidence:{code_id}", "to": f"evidence:{test_id}", "type": "verified_by"},
            {"from": f"evidence:{code_id}", "to": f"evidence:{iid}:commit", "type": "related_commit"},
            {"from": f"evidence:{iid}:log", "to": f"evidence:{iid}:slack", "type": "related_notes"},
            {"from": f"evidence:{iid}:graph", "to": f"evidence:{code_id}", "type": "same_repository"},
        ])

    for incident in incidents:
        incident["category"] = "SWE Bench"
        category_incidents.setdefault("SWE Bench", []).append(incident["id"])
    for item in all_evidence:
        item.setdefault("category", "SWE Bench")

    # Synthetic cloud incidents: incident/action reports and corrective actions.
    incident_file = HERE / "FYP_Data" / "04_Incident_Action_Dataset" / "PAG-Synthetic-Cloud-Incident-Dataset (2).json"
    for row in json.loads(incident_file.read_text(encoding="utf-8")):
        iid = f"cloud:{row['Incident_ID']}"
        title = str(row.get("Summary") or row["Incident_ID"])
        items = [
            evidence(iid, f"{iid}:report", "jira", "incident action dataset", row["Incident_ID"],
                     "Incident report", f"{row.get('Description', '')}\nSeverity: {row.get('Severity', '')}", .95, row.get("Detected_Time", "")),
            evidence(iid, f"{iid}:root-cause", "code", str(row.get("Root_Cause_Team", "")),
                     str(row.get("Root_Cause_Type", "")), "Root-cause analysis", str(row.get("Root_Cause_Description", "")), .9, row.get("Detected_Time", "")),
            evidence(iid, f"{iid}:action", "test", "incident action dataset", "CAPM",
                     "Corrective actions", str(row.get("CAPM", "")), .82, row.get("Mitigation_Time", "")),
            evidence(iid, f"{iid}:timeline", "log", "incident action dataset", "incident timeline",
                     "Detection and mitigation timeline", f"impact={row.get('Impact_Start_Time')}; detected={row.get('Detected_Time')}; mitigated={row.get('Mitigation_Time')}", .8, row.get("Detected_Time", "")),
        ]
        add_record(iid, title, "Incident Action Reports", str(row.get("Root_Cause_Team", "cloud")), row.get("Detected_Time", ""), items, {"severity": row.get("Severity", ""), "region": row.get("Region", "")})

    # DebugBench: question, buggy implementation, proposed solution, and explanation.
    debug_file = HERE / "FYP_Data" / "06_DebugBench" / "debugbench.jsonl"
    for index, row in enumerate(json.loads(line) for line in debug_file.read_text(encoding="utf-8").splitlines() if line.strip()):
        iid = f"debugbench:{row.get('slug', index)}:{index}"
        title = str(row.get("question") or row.get("slug") or iid)
        items = [
            evidence(iid, f"{iid}:question", "jira", "DebugBench", str(row.get("slug", "")), "Bug report", str(row.get("question", "")), .94, str(row.get("release_time", ""))),
            evidence(iid, f"{iid}:buggy", "code", str(row.get("language", "")), str(row.get("slug", "")), "Buggy code", str(row.get("buggy_code", "")), .93, str(row.get("release_time", ""))),
            evidence(iid, f"{iid}:solution", "commit", str(row.get("language", "")), str(row.get("slug", "")), "Reference solution", str(row.get("solution", "")), .88, str(row.get("release_time", ""))),
            evidence(iid, f"{iid}:explanation", "test", "DebugBench", str(row.get("subtype", "")), "Bug explanation", str(row.get("bug_explanation", "")), .86, str(row.get("release_time", ""))),
        ]
        add_record(iid, title, "DebugBench", str(row.get("language", "")), str(row.get("release_time", "")), items, {"subcategory": row.get("category", ""), "difficulty": row.get("level", "")})

    # BugsInPy is distributed as an archive; index every bug descriptor and patch.
    bugs_zip = HERE / "FYP_Data" / "02_BugsInPy" / "BugsInPy-master.zip"
    with zipfile.ZipFile(bugs_zip) as archive:
        for info_name in [name for name in archive.namelist() if name.endswith("/bug.info")]:
            parts = Path(info_name).parts
            project = parts[-3]
            bug_no = parts[-2]
            values = {}
            for line in archive.read(info_name).decode(errors="replace").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    values[key] = value.strip().strip('"')
            iid = f"bugsinpy:{project}:{bug_no}"
            patch_name = str(Path(info_name).parent / "bug_patch.txt").replace("\\", "/")
            patch = archive.read(patch_name).decode(errors="replace") if patch_name in archive.namelist() else ""
            items = [
                evidence(iid, f"{iid}:bug", "jira", project, bug_no, "Bug metadata", json.dumps(values), .9, ""),
                evidence(iid, f"{iid}:patch", "code", project, values.get("buggy_commit_id", ""), "Bug patch", patch, .94, ""),
                evidence(iid, f"{iid}:test", "test", project, values.get("test_file", ""), "Test target", values.get("test_file", ""), .83, ""),
            ]
            add_record(iid, f"{project} bug {bug_no}", "BugsInPy", project, "", items, values)

    # LogHub: retain every structured log row and link adjacent artifacts.
    for csv_path in sorted((HERE / "FYP_Data" / "05_Loghub").glob("*/*_2k.log_structured.csv")):
        frame = pd.read_csv(csv_path).fillna("")
        service = csv_path.parent.name
        iid = f"loghub:{service.lower()}"
        items = [
            evidence(iid, f"{iid}:summary", "graph", "LogHub", service, "Structured log dataset", f"{len(frame)} rows from {csv_path.name}", .7, ""),
        ]
        for row_number, row in frame.iterrows():
            content = " | ".join(f"{key}={row[key]}" for key in frame.columns)
            items.append(evidence(iid, f"{iid}:line:{row_number + 1}", "log", service, str(row.get("LineId", row_number + 1)),
                                  str(row.get("EventTemplate", "Structured log event")), content[:4000], .8, f"{row.get('Date', '')} {row.get('Time', '')}"))
        add_record(iid, f"{service} operational logs", "LogHub", service, "", items, {"row_count": len(frame)})

    # QuixBugs source files are individual code artifacts with internal links.
    quix_root = HERE / "FYP_Data" / "07_QuixBugs"
    for source_path in sorted(quix_root.rglob("*")):
        if not source_path.is_file() or source_path.suffix.lower() not in {".py", ".java"}:
            continue
        relative = source_path.relative_to(quix_root)
        iid = f"quixbugs:{relative.as_posix()}"
        text = source_path.read_text(encoding="utf-8", errors="replace")
        item = evidence(iid, f"{iid}:source", "code", "QuixBugs", relative.as_posix(), "QuixBugs source artifact", text, .82, "")
        add_record(iid, f"QuixBugs {relative.name}", "QuixBugs", "QuixBugs", "", [item], {"path": relative.as_posix()})

    # Research PDFs are navigable source documents; content extraction is not
    # assumed, so their file identity and topic remain explicit evidence.
    for pdf_path in sorted((HERE / "FYP_Data").glob("*.pdf")):
        iid = f"research:{pdf_path.stem}"
        item = evidence(iid, f"{iid}:document", "graph", "research library", pdf_path.name, "Research document", f"PDF source: {pdf_path.name}", .65, "")
        add_record(iid, pdf_path.stem, "Research Documents", "Research Library", "", [item], {"file": pdf_path.name})

    output = {
        "source_datasets": {
            "jsonl": {"file": JSONL.name, "records": len(records)},
            "parquet": {"file": PARQUET.name, "records": len(parquet), "validated_same_instance_ids": True},
        },
        "incidents": incidents,
        "evidence": all_evidence,
        "claims": claims,
        "graph": {"nodes": graph_nodes, "edges": graph_edges},
        "hierarchy": [
            {"id": category, "label": category, "incident_ids": ids, "count": len(ids)}
            for category, ids in sorted(category_incidents.items())
        ],
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False), encoding="utf-8")
    print(f"Built {len(incidents)} incidents, {len(all_evidence)} evidence records, {len(claims)} claims")


if __name__ == "__main__":
    main()
