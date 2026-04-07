import streamlit as st
import requests
import json

st.title("RealityOps Interactive Demo")
st.markdown("Explore the SRE incident response environment interactively!")

# Sidebar for configuration
st.sidebar.header("Configuration")
base_url = st.sidebar.text_input("Server URL", "http://localhost:7860")
task = st.sidebar.selectbox("Task", ["false_alarm", "ambiguous_root", "revenue_tradeoff", "cascading_failure", "multi_incident"])

# Main interface
col1, col2 = st.columns(2)

with col1:
    st.header("Environment Control")
    if st.button("Reset Episode"):
        try:
            resp = requests.post(f"{base_url}/reset", json={"task": task}, timeout=5)
            if resp.status_code == 200:
                st.success("Episode reset!")
                st.session_state.observation = resp.json()["observation"]
                st.session_state.done = False
                st.session_state.step = 0
            else:
                st.error(f"Reset failed: {resp.status_code}")
        except Exception as e:
            st.error(f"Connection error: {e}")

    action_type = st.selectbox("Action Type", ["probe", "check_logs", "check_metrics", "update_belief", "commit_fix", "safe_mitigation", "risky_hotfix", "ask_team", "wait"])
    payload_input = st.text_area("Payload (JSON)", "{}")
    
    if st.button("Take Step"):
        try:
            payload = json.loads(payload_input) if payload_input.strip() else {}
            action = {"type": action_type, **payload}
            resp = requests.post(f"{base_url}/step", json=action, timeout=5)
            if resp.status_code == 200:
                result = resp.json()
                st.session_state.observation = result["observation"]
                st.session_state.done = result["done"]
                st.session_state.step += 1
                st.success(f"Step taken! Reward: {result['reward']:.2f}, Done: {result['done']}")
            else:
                st.error(f"Step failed: {resp.status_code}")
        except json.JSONDecodeError:
            st.error("Invalid JSON payload")
        except Exception as e:
            st.error(f"Connection error: {e}")

with col2:
    st.header("Current State")
    if "observation" in st.session_state:
        obs = st.session_state.observation
        st.subheader("Alerts")
        for alert in obs.get("alerts", []):
            st.write(f"• {alert}")
        
        st.subheader("Metrics")
        metrics = obs.get("metrics", {})
        st.json(metrics)
        
        st.subheader("Slack")
        for msg in obs.get("slack", []):
            st.write(f"💬 {msg}")
        
        st.subheader("Confidence Levels")
        conf = obs.get("confidence_levels", {})
        st.bar_chart(conf)
        
        st.subheader("Hints")
        for hint in obs.get("hints", []):
            st.info(hint)
        
        st.write(f"Revenue Loss: ${obs.get('revenue_loss', 0):,.0f}")
        st.write(f"Step: {obs.get('step', 0)}")
    else:
        st.info("Reset the episode to start.")

# Visualization
st.header("Episode Visualization")
if st.button("Get Visualization"):
    try:
        resp = requests.get(f"{base_url}/visualize", timeout=5)
        if resp.status_code == 200:
            viz = resp.json()
            st.subheader("Trajectory")
            st.json(viz["trajectory"])
            st.subheader("Belief History")
            st.line_chart(viz["beliefs_over_time"])
        else:
            st.error(f"Visualization failed: {resp.status_code}")
    except Exception as e:
        st.error(f"Connection error: {e}")

st.markdown("---")
st.markdown("**Note**: Ensure the server is running at the specified URL.")