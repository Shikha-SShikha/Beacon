"""
review_app.py — Beacon Enrichment Review

Shows draft entities extracted from the copyedit XML by NER Stage 1.
No ontology IDs yet — those are resolved at the mastercopy stage.

Scan the chips grouped by type. Click any entity to reject it.
Optionally correct its type using the dropdown in the Rejected panel.
Hit Approve to write decisions back to the manifest and kick off
the full mastercopy enrichment pass.

Usage:
    streamlit run review_app.py
"""

import json
import subprocess
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ─── Config ───────────────────────────────────────────────────────────────────

MANIFEST_PATH = Path(__file__).parent / ".tmp" / "enrichment_copyedit.json"
PROOF_XML     = Path(__file__).parent / "Proof .xml"
COPYEDIT_XML  = Path(__file__).parent / "Copyedit.xml"

ENTITY_TYPES = [
    "DISEASE", "DRUG", "CHEMICAL", "GENE", "PROTEIN",
    "ORGANISM", "CELL_LINE", "METHOD", "TECHNOLOGY",
    "METRIC", "ANATOMY", "DEVICE", "CONCEPT",
]

TYPE_COLOR = {
    "DISEASE":  "#c0392b", "DRUG":     "#8e44ad",
    "CHEMICAL": "#1a5276", "GENE":     "#1e8449",
    "PROTEIN":  "#196f3d", "METHOD":   "#117a65",
    "METRIC":   "#7d6608", "ANATOMY":  "#6e2f1a",
    "DEVICE":   "#154360", "CONCEPT":  "#4a235a",
}


# ─── Data helpers ─────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        st.error(
            f"Run `python stage_copyedit.py Copyedit.xml` first — manifest not found at:\n{MANIFEST_PATH}"
        )
        st.stop()
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def save_manifest(m: dict) -> None:
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(m, f, indent=2, ensure_ascii=False)


def iter_entities(manifest: dict):
    """Yield (key, entity_dict) for every entity across all sections/paragraphs."""
    for i, sec in enumerate(manifest.get("sections", [])):
        for j, para in enumerate(sec.get("paragraphs", [])):
            for k, e in enumerate(para.get("entities", [])):
                yield f"sec:{i}:para:{j}:entity:{k}", e


def collect_unique_entities(manifest: dict) -> list[tuple[str, dict]]:
    """
    Deduplicate by (text.lower(), type) — same entity across paragraphs counts once.
    Returns first-occurrence (key, entity) for each unique (text, type) pair.
    """
    seen: set = set()
    result: list = []
    for key, e in iter_entities(manifest):
        dedup_key = (e["text"].lower(), e["type"])
        if dedup_key not in seen:
            seen.add(dedup_key)
            result.append((key, e))
    return result


def apply_decisions(manifest: dict, rejected_keys: set, type_corrections: dict) -> dict:
    """Write status/verified_by/verified_at + type corrections back into manifest."""
    ts = datetime.now(timezone.utc).isoformat()
    updated = deepcopy(manifest)
    for i, sec in enumerate(updated.get("sections", [])):
        for j, para in enumerate(sec.get("paragraphs", [])):
            for k, e in enumerate(para.get("entities", [])):
                key = f"sec:{i}:para:{j}:entity:{k}"
                if key in rejected_keys:
                    e["status"]      = "rejected"
                    e["verified_by"] = "human"
                    e["verified_at"] = ts
                else:
                    e["status"]      = "draft"
                    e["verified_by"] = None
                    e["verified_at"] = None
                    if key in type_corrections:
                        e["type"] = type_corrections[key]
    updated["manifest_status"] = "reviewed"
    updated["reviewed_at"]     = ts
    return updated


# ─── Rendering ────────────────────────────────────────────────────────────────

def type_badge_html(etype: str, size: str = "0.75em") -> str:
    color = TYPE_COLOR.get(etype, "#555")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:{size};font-weight:700;">{etype}</span>'
    )


# ─── App ──────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Beacon — Review", layout="wide", page_icon="🔬")

st.markdown("""
<style>
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
.beacon-rejected { opacity: 0.45; text-decoration: line-through; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

if "manifest" not in st.session_state:
    st.session_state.manifest = load_manifest()
if "rejected" not in st.session_state:
    st.session_state.rejected: set = set()
if "type_corrections" not in st.session_state:
    st.session_state.type_corrections: dict = {}
if "pipeline_output" not in st.session_state:
    st.session_state.pipeline_output = None

manifest         = st.session_state.manifest
rejected         = st.session_state.rejected
type_corrections = st.session_state.type_corrections
meta             = manifest.get("metadata", {})

entities = collect_unique_entities(manifest)
n_rejected = len(rejected)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("Enrichment Review")
st.markdown(meta.get("title", ""))
st.caption(
    f"DOI: {meta.get('doi','—')} · "
    f"Journal: {meta.get('journal_id','—')} · "
    f"Authors: {', '.join(meta.get('authors',[]))}"
)

st.divider()

c1, c2 = st.columns(2)
c1.metric("Entities to review", len(entities), help="Unique entities extracted from copyedit XML — no IDs yet")
c2.metric("Rejected", n_rejected)

st.caption("These are draft entities — type and name only. Ontology IDs are resolved after approval at the mastercopy stage.")

# ── Entity chips ──────────────────────────────────────────────────────────────

st.divider()
st.subheader("Quick review")
st.caption("Click any entity to reject it. Everything else is approved when you hit the button below.")

if not entities:
    st.info("No entities found in this manifest.")
else:
    by_type: dict = defaultdict(list)
    for key, e in entities:
        by_type[e["type"]].append((key, e))

    for etype, items in sorted(by_type.items()):
        st.markdown(
            type_badge_html(etype, "0.8em") +
            f'<span style="opacity:0.6;font-size:0.8em;margin-left:6px;">{len(items)}</span>',
            unsafe_allow_html=True,
        )

        COLS = 6
        rows = [items[i:i+COLS] for i in range(0, len(items), COLS)]
        for row in rows:
            cols = st.columns(COLS)
            for col, (key, entity) in zip(cols, row):
                is_rejected = key in rejected
                with col:
                    btn_style = "🚫 " if is_rejected else ""
                    if st.button(
                        f"{btn_style}{entity['text']}",
                        key=f"chip_{key}",
                        use_container_width=True,
                        type="secondary",
                        help="Click to reject / click again to un-reject",
                    ):
                        if is_rejected:
                            rejected.discard(key)
                        else:
                            rejected.add(key)
                        st.rerun()

        st.markdown("")

# ── Rejected panel ────────────────────────────────────────────────────────────

if rejected:
    st.divider()
    st.subheader(f"Rejected ({len(rejected)})")
    st.caption("Optionally correct the type — it will be re-approved with the new type.")

    entity_map = {key: e for key, e in entities}
    for key in sorted(rejected):
        entity = entity_map.get(key)
        if not entity:
            continue
        ca, cb, cc = st.columns([3, 2, 1])
        with ca:
            st.markdown(
                f'{type_badge_html(entity["type"])} '
                f'<span class="beacon-rejected">{entity["text"]}</span>',
                unsafe_allow_html=True,
            )
        with cb:
            new_type = st.selectbox(
                "Change type",
                options=["— keep rejected —"] + ENTITY_TYPES,
                index=0,
                key=f"typecorr_{key}",
                label_visibility="collapsed",
            )
            if new_type != "— keep rejected —":
                type_corrections[key] = new_type
                rejected.discard(key)
                st.rerun()
        with cc:
            if st.button("Undo", key=f"undo_{key}", use_container_width=True):
                rejected.discard(key)
                type_corrections.pop(key, None)
                st.rerun()

# ── Approve & Run ─────────────────────────────────────────────────────────────

st.divider()

already_reviewed = manifest.get("manifest_status") == "reviewed"

if st.button(
    "✅  Approve & run mastercopy enrichment",
    type="primary",
    use_container_width=True,
    disabled=already_reviewed and st.session_state.pipeline_output is not None,
):
    updated = apply_decisions(manifest, rejected, type_corrections)
    save_manifest(updated)
    st.session_state.manifest  = updated
    st.session_state.pipeline_output = None
    st.rerun()

# ── Auto-run mastercopy ────────────────────────────────────────────────────────

if manifest.get("manifest_status") == "reviewed" and st.session_state.pipeline_output is None:
    st.info("Running mastercopy enrichment pass…")
    lines: list[str] = []
    log_box = st.empty()

    proc = subprocess.Popen(
        [sys.executable, "stage_mastercopy.py", str(PROOF_XML), "--copyedit", str(COPYEDIT_XML)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, cwd=str(Path(__file__).parent),
    )
    for line in proc.stdout:
        lines.append(line.rstrip())
        log_box.code("\n".join(lines[-35:]), language="")
    proc.wait()

    st.session_state.pipeline_output = "\n".join(lines)
    icon = "🎉" if proc.returncode == 0 else "⚠️"
    st.toast("Mastercopy pass complete!" if proc.returncode == 0 else "Check log.", icon=icon)
    st.rerun()

if st.session_state.pipeline_output:
    with st.expander("Pipeline log", expanded=False):
        st.code(st.session_state.pipeline_output, language="")
    chunks_path = Path(__file__).parent / "chunks" / "Proof__chunks.json"
    if chunks_path.exists():
        st.success("✅ Verified chunks ready — open `chat_app.py` to query.")
