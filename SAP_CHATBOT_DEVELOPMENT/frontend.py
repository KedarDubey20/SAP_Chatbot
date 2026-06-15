"""
SAP AI Assistant - Frontend with Persistent Chat History
✅ SQLite-backed sessions (survives server restarts)
✅ Auto title generation from first message
✅ Thinking trace panel
✅ Charts, metrics, follow-ups
✅ Multi-step query results shown per step
✅ Professional dark theme
"""

import streamlit as st
import requests
from datetime import datetime
import pandas as pd
import re

API_BASE = "http://localhost:8000/api/v1"
API_URL  = f"{API_BASE}/ai/query"

CUSTOM_CSS = """
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
        border: 1px solid #2d5a8e;
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        margin: 4px;
    }
    .metric-value { font-size: 26px; font-weight: 700; color: #4fc3f7; margin: 0; }
    .metric-label { font-size: 11px; color: #90a4ae; margin: 4px 0 0 0; text-transform: uppercase; letter-spacing: 1px; }
    .insight-box { background: #0d2137; border-left: 4px solid #4fc3f7; border-radius: 0 8px 8px 0; padding: 12px 16px; margin: 8px 0; font-size: 14px; color: #e0e0e0; }
    .live-badge { display: inline-block; background: #1b5e20; color: #69f0ae; border-radius: 12px; padding: 2px 10px; font-size: 11px; font-weight: 600; letter-spacing: 1px; }
    .think-step { font-size: 12px; padding: 2px 0; font-family: monospace; }
    .step-header { background: #0d2137; border-left: 3px solid #4fc3f7; padding: 6px 12px; margin: 10px 0 4px 0; border-radius: 0 6px 6px 0; font-size: 13px; font-weight: 600; color: #4fc3f7; }
</style>
"""

# ============================================================
# SESSION API CALLS
# ============================================================

def api_create_session(title=None):
    try:
        r = requests.post(f"{API_BASE}/sessions", json={"title": title}, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        st.error(f"Failed to create session: {e}")
    return None

def api_list_sessions():
    try:
        r = requests.get(f"{API_BASE}/sessions?limit=50", timeout=10)
        if r.status_code == 200:
            return r.json().get("sessions", [])
    except:
        pass
    return []

def api_get_messages(session_id):
    try:
        r = requests.get(f"{API_BASE}/sessions/{session_id}/messages", timeout=10)
        if r.status_code == 200:
            return r.json().get("messages", [])
    except:
        pass
    return []

def api_save_message(session_id, role, content, sql_query=None, results=None):
    try:
        r = requests.post(
            f"{API_BASE}/sessions/{session_id}/messages",
            json={"role": role, "content": content, "sql_query": sql_query, "results": results},
            timeout=10
        )
    except Exception as e:
        print(f"SAVE MSG ERROR: {e}")

def api_generate_title(message):
    try:
        r = requests.post(
            f"{API_BASE}/sessions/generate-title",
            json={"message": message},
            timeout=15
        )
        if r.status_code == 200:
            return r.json().get("title", message[:40])
    except:
        pass
    return message[:40]

def api_delete_session(session_id):
    try:
        requests.delete(f"{API_BASE}/sessions/{session_id}", timeout=10)
    except:
        pass

def api_update_title(session_id, title):
    try:
        requests.patch(
            f"{API_BASE}/sessions/{session_id}/title",
            json={"message": title},
            timeout=10
        )
    except:
        pass

# ============================================================
# SESSION STATE INIT
# ============================================================

def init_session_state():
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    if 'current_messages' not in st.session_state:
        st.session_state.current_messages = []
    if 'sessions_list' not in st.session_state:
        st.session_state.sessions_list = api_list_sessions()

def create_new_session():
    session = api_create_session(title="New Chat")
    if session:
        st.session_state.current_session_id = session["session_id"]
        st.session_state.current_messages = []
        st.session_state.sessions_list = api_list_sessions()
    return session

def switch_session(session_id):
    st.session_state.current_session_id = session_id
    raw_messages = api_get_messages(session_id)
    st.session_state.current_messages = [
        {
            "role": m["role"],
            "content": m["content"],
            "timestamp": m["created_at"],
            "metadata": {
                "results": m.get("results") or [],
                "thinking_steps": [],
                "show_chart": False,
                "chart_type": "bar",
                "is_multi_step": False,
                "steps_results": [],
                "follow_ups": []
            }
        }
        for m in raw_messages
    ]

# ============================================================
# AI QUERY
# ============================================================

def query_api(user_query, conversation_history=None, session_id=None):
    try:
        history = []
        if conversation_history:
            for m in conversation_history[-6:]:
                history.append({"role": m["role"], "content": m["content"]})
        r = requests.post(
            API_URL,
            json={
                "query": user_query,
                "session_id": session_id,
                "conversation_history": history
            },
            timeout=90
        )
        if r.status_code == 200:
            return r.json()
        return {"success": False, "response": f"Server error {r.status_code}", "thinking_steps": []}
    except Exception as e:
        return {"success": False, "response": f"Connection error: {str(e)}", "thinking_steps": []}

# ============================================================
# FOLLOW-UPS
# ============================================================

def generate_follow_ups(response, user_query):
    try:
        result_summary = ""
        results = response.get('results', [])
        if results:
            result_summary = f"Query returned {len(results)} rows. First row sample: {results[0]}"

        r = requests.post(
            f"{API_BASE}/ai/follow-ups",
            json={"query": user_query, "result_summary": result_summary},
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get("follow_ups", [])
    except:
        pass
    return [
        "Show top 5 orders by value",
        "Which customer has the most orders?",
        "Give me a summary of all SAP data"
    ]

# ============================================================
# RENDER HELPERS
# ============================================================

def try_render_metrics(response_text):
    metrics = []
    m = re.search(r'(\d[\d,]*)\s+Sales Orders?\s+worth\s+(₹[\d,\.]+)', response_text)
    if m:
        metrics.append(("📦 Sales Orders", m.group(1)))
        metrics.append(("💰 Total Value", m.group(2)))
    m = re.search(r'(\d+)\s+Items?\s+Sold', response_text)
    if m: metrics.append(("🛒 Items Sold", m.group(1)))
    m = re.search(r'(\d+)\s+Customers?', response_text)
    if m: metrics.append(("👥 Customers", m.group(1)))
    m = re.search(r'(\d+)\s+Materials?\s+Available', response_text)
    if m: metrics.append(("🏷️ Materials", m.group(1)))
    m = re.search(r'(\d+)\s+Purchase Orders?', response_text)
    if m: metrics.append(("🧾 Purchase Orders", m.group(1)))
    if len(metrics) >= 3:
        cols = st.columns(len(metrics))
        for i, (label, value) in enumerate(metrics):
            with cols[i]:
                st.markdown(f'<div class="metric-card"><p class="metric-value">{value}</p><p class="metric-label">{label}</p></div>', unsafe_allow_html=True)
        return True
    return False

def render_thinking_panel(thinking_steps, key_suffix=""):
    if not thinking_steps:
        return
    with st.expander(f"🧠 Reasoning trace ({len(thinking_steps)} steps)", expanded=False):
        for step in thinking_steps:
            if step.startswith("```sql"):
                sql_content = step.replace("```sql\n", "").replace("\n```", "")
                st.code(sql_content, language="sql")
            elif step.startswith("✅"):
                st.markdown(f"<div class='think-step' style='color:#69f0ae'>{step}</div>", unsafe_allow_html=True)
            elif step.startswith("❌"):
                st.markdown(f"<div class='think-step' style='color:#ef5350'>{step}</div>", unsafe_allow_html=True)
            elif step.startswith("🔷"):
                st.markdown(f"<div class='think-step' style='color:#4fc3f7'>{step}</div>", unsafe_allow_html=True)
            elif step.startswith("📋") or step.startswith("  Step"):
                st.markdown(f"<div class='think-step' style='color:#ffa726'>{step}</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div class='think-step' style='color:#90a4ae'>{step}</div>", unsafe_allow_html=True)

def render_dataframe(results):
    """Render a list of dicts as a clean dataframe"""
    if not results:
        return
    df = pd.DataFrame(results)
    df = df.dropna(axis=1, how='all')
    if not df.empty:
        st.dataframe(df, use_container_width=True, height=min(350, 38 * (len(df) + 1)))

def render_multi_step_results(steps_results, combined_results):
    """Render each step's results in a separate labeled dataframe"""
    if steps_results:
        for step in steps_results:
            step_num  = step.get('step', '')
            step_desc = step.get('description', f'Step {step_num}')
            step_data = step.get('results', [])
            st.markdown(f"<div class='step-header'>📊 Step {step_num}: {step_desc} ({len(step_data)} rows)</div>", unsafe_allow_html=True)
            render_dataframe(step_data)
    elif combined_results:
        # Fallback if steps_results not available
        render_dataframe(combined_results)

def render_chart(results, chart_type):
    if not results: return
    df = pd.DataFrame(results)
    df = df.dropna(axis=1, how='all')
    if df.empty or len(df.columns) < 2: return
    cols = df.columns.tolist()
    x_col = None
    for col in cols:
        if any(w in col.lower() for w in ['date', 'month', 'year', 'name', 'kunnr', 'matnr', 'vbeln', 'ebeln', 'arktx', 'name1']):
            x_col = col
            break
    if not x_col: x_col = cols[0]
    numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    y_col = None
    if numeric_cols:
        for col in numeric_cols:
            if any(w in col.lower() for w in ['count', 'value', 'amount', 'total', 'sum', 'net', 'netwr']):
                y_col = col
                break
        if not y_col: y_col = numeric_cols[0]
    if not y_col: return
    st.markdown("### 📊 Visualization")
    try:
        chart_df = df[[x_col, y_col]].set_index(x_col)
        if chart_type == 'line':
            st.line_chart(chart_df, use_container_width=True)
        elif chart_type == 'area':
            st.area_chart(chart_df, use_container_width=True)
        else:
            st.bar_chart(chart_df, use_container_width=True)
    except Exception as e:
        st.error(f"Chart error: {e}")
    st.markdown("---")

def render_message(message):
    role    = message['role']
    content = message['content']
    meta    = message.get('metadata', {})

    if role == 'user':
        with st.chat_message("user", avatar="👤"):
            st.write(content)
        return

    with st.chat_message("assistant", avatar="🤖"):
        thinking_steps = meta.get('thinking_steps', [])
        if thinking_steps:
            render_thinking_panel(thinking_steps, key_suffix=message.get('timestamp', ''))

        st.write(content)

        is_multi      = meta.get('is_multi_step', False)
        results       = meta.get('results', [])
        steps_results = meta.get('steps_results', [])

        if is_multi:
            render_multi_step_results(steps_results, results)
        elif results:
            render_dataframe(results)

        if meta.get('show_chart') and results:
            render_chart(results, meta.get('chart_type', 'bar'))

        follow_ups = meta.get('follow_ups', [])
        if follow_ups:
            st.markdown("**💡 Try asking:**")
            fu_cols = st.columns(len(follow_ups))
            for idx, q in enumerate(follow_ups):
                with fu_cols[idx]:
                    if st.button(q, key=f"fup_{message.get('timestamp', idx)}_{idx}", use_container_width=True):
                        st.session_state.pending_query = q
                        st.rerun()


def get_welcome_suggestions():
    if 'welcome_suggestions' in st.session_state:
        return st.session_state.welcome_suggestions
    try:
        r = requests.post(
            f"{API_BASE}/ai/follow-ups",
            json={
                "query": "welcome screen",
                "result_summary": "Tables available: VBAK (sales orders), VBAP (sales items), KNA1 (customers), MARA (materials), EKKO (purchase orders), EKPO (purchase items), VBEP (schedule lines)"
            },
            timeout=10
        )
        if r.status_code == 200:
            suggestions = r.json().get("follow_ups", [])
            st.session_state.welcome_suggestions = suggestions
            return suggestions
    except:
        pass
    return [
        "Which customer has the most orders?",
        "Show top 5 orders by value",
        "Give me a summary of all SAP data"
    ]

# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():
    st.sidebar.title("💬 Conversations")

    if st.sidebar.button("➕ New Chat", use_container_width=True, type="primary"):
        create_new_session()
        st.rerun()

    st.sidebar.divider()

    sessions = st.session_state.sessions_list
    if sessions:
        st.sidebar.subheader("Recent Chats")
        for s in sessions:
            sid     = s["session_id"]
            title   = s["title"]
            is_curr = (sid == st.session_state.current_session_id)
            col1, col2 = st.sidebar.columns([5, 1])
            with col1:
                label = f"{'🟢' if is_curr else '⚪'} {title}"
                if st.button(label, key=f"sess_{sid}", use_container_width=True,
                             type="primary" if is_curr else "secondary"):
                    if not is_curr:
                        switch_session(sid)
                        st.rerun()
            with col2:
                if not is_curr:
                    if st.button("🗑️", key=f"del_{sid}"):
                        api_delete_session(sid)
                        st.session_state.sessions_list = api_list_sessions()
                        st.rerun()

    st.sidebar.divider()
    count = len(sessions)
    st.sidebar.caption(f"💬 {count} conversation{'s' if count != 1 else ''}")
    st.sidebar.markdown('<span class="live-badge">● LIVE</span> SAP HANA Connected', unsafe_allow_html=True)

# ============================================================
# MAIN
# ============================================================

def main():
    st.set_page_config(page_title="SAP AI Assistant", page_icon="🤖", layout="wide", initial_sidebar_state="expanded")
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    init_session_state()
    render_sidebar()

    col_title, col_badge = st.columns([8, 2])
    with col_title:
        st.title("🤖 SAP AI Assistant")
        st.caption("Natural language interface to your live SAP HANA data")
    with col_badge:
        st.markdown('<br><span class="live-badge">● LIVE DATA</span>', unsafe_allow_html=True)

    if not st.session_state.current_session_id:
        session = api_create_session(title="New Chat")
        if session:
            st.session_state.current_session_id = session["session_id"]
            st.session_state.sessions_list = api_list_sessions()

    if st.session_state.current_messages:
        for msg in st.session_state.current_messages:
            render_message(msg)
    else:
        st.markdown('<div class="insight-box">👋 <strong>Welcome!</strong> Ask me anything about your SAP data in plain English. I\'m connected to your live SAP HANA database — no exports, no delays, real-time answers.</div>', unsafe_allow_html=True)
        suggestions = get_welcome_suggestions()
        if suggestions:
            st.markdown("**💡 Try asking:**")
            cols = st.columns(len(suggestions))
            for idx, q in enumerate(suggestions):
                with cols[idx]:
                    if st.button(q, key=f"welcome_{idx}", use_container_width=True):
                        st.session_state.pending_query = q
                        st.rerun()

    if hasattr(st.session_state, 'pending_query'):
        user_input = st.session_state.pending_query
        delattr(st.session_state, 'pending_query')
    else:
        user_input = st.chat_input("Ask anything about your SAP data...")

    if user_input:
        session_id = st.session_state.current_session_id

        api_save_message(session_id, "user", user_input)

        st.session_state.current_messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat(),
            "metadata": {}
        })

        with st.chat_message("user", avatar="👤"):
            st.write(user_input)

        if len(st.session_state.current_messages) == 1:
            title = api_generate_title(user_input)
            api_update_title(session_id, title)
            st.session_state.sessions_list = api_list_sessions()

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🔍 Querying live SAP HANA..."):
                response      = query_api(    user_input,
    st.session_state.current_messages[:-1],
    session_id=st.session_state.current_session_id)
                text          = response.get('response', 'Sorry, I encountered an error.')
                results       = response.get('results', [])
                steps_results = response.get('steps_results', [])
                is_multi      = response.get('is_multi_step', False)
                show_chart    = response.get('show_chart', False)
                chart_type    = response.get('chart_type', 'bar')
                thinking      = response.get('thinking_steps', [])
                sql           = response.get('sql')

            if thinking:
                render_thinking_panel(thinking)

            st.write(text)

            if is_multi:
                render_multi_step_results(steps_results, results)
            elif results:
                render_dataframe(results)

            if show_chart and results:
                render_chart(results, chart_type)

            follow_ups = generate_follow_ups(response, user_input)
            if follow_ups:
                st.markdown("**💡 Try asking:**")
                fu_cols = st.columns(len(follow_ups))
                for idx, q in enumerate(follow_ups):
                    with fu_cols[idx]:
                        if st.button(q, key=f"new_fup_{idx}", use_container_width=True):
                            st.session_state.pending_query = q
                            st.rerun()

        api_save_message(session_id, "assistant", text, sql_query=sql, results=results)

        st.session_state.current_messages.append({
            "role": "assistant",
            "content": text,
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "results": results,
                "steps_results": steps_results,
                "follow_ups": follow_ups,
                "show_chart": show_chart,
                "chart_type": chart_type,
                "is_multi_step": is_multi,
                "thinking_steps": thinking
            }
        })

        st.rerun()

if __name__ == "__main__":
    main()