# starter_v0/ui.py
import json
import streamlit as st
from pathlib import Path
from datetime import datetime

from env_loader import load_lab_env
from providers import make_provider
from tools import TOOL_FUNCTIONS, load_tool_declarations, to_openai_tools
from versioning import build_artifact_version, artifact_version_dict
from chat import run_model_tool_loop, trim_history, write_transcript, safe_slug, now_iso

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
load_lab_env(ROOT)

# ── Sidebar config ──────────────────────────────────
st.sidebar.title("⚙️ Cấu hình Agent")
provider_name = st.sidebar.selectbox("Provider", ["gemini", "openai", "openrouter", "anthropic"])
version_label = st.sidebar.text_input("Version label", value="v0")
max_rounds = st.sidebar.slider("Max tool rounds", 1, 8, 4)

# ── Load artifacts ──────────────────────────────────
system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
tool_declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
openai_tools = to_openai_tools(tool_declarations)
provider = make_provider(provider_name)
artifact_version = build_artifact_version(version_label, ARTIFACTS_DIR / "system_prompt.md", ARTIFACTS_DIR / "tools.yaml")

# ── Hiển thị version/hash ───────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown(f"**artifact_version:** `{artifact_version.artifact_version}`")
st.sidebar.markdown(f"**prompt_hash:** `{artifact_version.prompt_hash[:12]}`")
st.sidebar.markdown(f"**tools_hash:** `{artifact_version.tools_hash[:12]}`")

# ── Session state ───────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []
if "turns" not in st.session_state:
    st.session_state.turns = []

st.title("🛟 IT Helpdesk Agent")

# ── Input ───────────────────────────────────────────
user_input = st.chat_input("Nhập yêu cầu của bạn...")

# Hiển thị lịch sử
for turn in st.session_state.turns:
    with st.chat_message("user"):
        st.write(turn["user"])

    # Hiển thị từng round + tool calls
    for r in turn.get("rounds", []):
        if r["tool_calls"]:
            with st.expander(f"🔧 Round {r['round']} — {len(r['tool_calls'])} tool call(s)"):
                for tc, tr in zip(r["tool_calls"], r["tool_results"]):
                    st.markdown(f"**Tool:** `{tc['name']}`")
                    st.json(tc["args"])                          # ← args
                    result = tr["result"]
                    if isinstance(result, dict) and "error" in result:
                        st.error(f"❌ Error: {result}")          # ← error
                    else:
                        st.success("✅ Result:")
                        st.json(result)                          # ← result

    # Status badge
    status = turn.get("status", "?")
    badge = {"answered": "🟢", "waiting_for_user": "🟡", "max_tool_rounds": "🔴"}.get(status, "⚪")
    st.caption(f"{badge} Status: `{status}` | Round: {len(turn.get('rounds', []))}")

    with st.chat_message("assistant"):
        st.write(turn.get("assistant_text", ""))

# ── Xử lý input mới ─────────────────────────────────
if user_input:
    messages = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.history, 5),
        {"role": "user", "content": user_input},
    ]

    with st.spinner("Agent đang xử lý..."):
        result = run_model_tool_loop(
            provider=provider,
            messages=messages,
            tools=openai_tools,
            model=None,
            max_tool_rounds=max_rounds,
        )

    turn_record = {
        "turn_index": len(st.session_state.turns) + 1,
        "started_at": now_iso(),
        "user": user_input,
        **result,
        "ended_at": now_iso(),
    }
    st.session_state.turns.append(turn_record)
    st.session_state.history.append({"role": "user", "content": user_input})
    st.session_state.history.append({"role": "assistant", "content": result["assistant_text"]})

    # Lưu transcript
    transcript_path = ROOT / "transcripts" / f"{safe_slug(version_label)}_{provider_name}_{datetime.now().strftime('%Y%m%dT%H%M%S')}.transcript.json"
    write_transcript(transcript_path, {
        "transcript_id": transcript_path.stem,
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "turns": st.session_state.turns,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    st.caption(f"📄 Transcript: `{transcript_path}`")
    st.rerun()
