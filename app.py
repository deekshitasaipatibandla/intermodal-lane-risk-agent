import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import math
import anthropic
from datetime import datetime, timedelta

# ── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="Intermodal Lane Risk Agent",
    page_icon="🚛",
    layout="wide"
)

# ── FREIGHT LANES ────────────────────────────────────────────
FREIGHT_LANES = [
    {"lane_id": "LA-CHI",  "name": "Los Angeles → Chicago",       "origin": (34.05, -118.24), "dest": (41.88, -87.63)},
    {"lane_id": "LA-DAL",  "name": "Los Angeles → Dallas",        "origin": (34.05, -118.24), "dest": (32.78, -96.80)},
    {"lane_id": "CHI-NYC", "name": "Chicago → New York",          "origin": (41.88, -87.63),  "dest": (40.71, -74.01)},
    {"lane_id": "DAL-ATL", "name": "Dallas → Atlanta",            "origin": (32.78, -96.80),  "dest": (33.75, -84.39)},
    {"lane_id": "SEA-LA",  "name": "Seattle → Los Angeles",       "origin": (47.61, -122.33), "dest": (34.05, -118.24)},
    {"lane_id": "HOU-CHI", "name": "Houston → Chicago",           "origin": (29.76, -95.37),  "dest": (41.88, -87.63)},
    {"lane_id": "MIA-NYC", "name": "Miami → New York",            "origin": (25.77, -80.19),  "dest": (40.71, -74.01)},
    {"lane_id": "LA-SEA",  "name": "Los Angeles → Seattle",       "origin": (34.05, -118.24), "dest": (47.61, -122.33)},
    {"lane_id": "CHI-DAL", "name": "Chicago → Dallas",            "origin": (41.88, -87.63),  "dest": (32.78, -96.80)},
    {"lane_id": "ATL-NYC", "name": "Atlanta → New York",          "origin": (33.75, -84.39),  "dest": (40.71, -74.01)},
    {"lane_id": "DEN-CHI", "name": "Denver → Chicago",            "origin": (39.74, -104.98), "dest": (41.88, -87.63)},
    {"lane_id": "PHX-LA",  "name": "Phoenix → Los Angeles",       "origin": (33.45, -112.07), "dest": (34.05, -118.24)},
    {"lane_id": "KC-CHI",  "name": "Kansas City → Chicago",       "origin": (39.10, -94.58),  "dest": (41.88, -87.63)},
    {"lane_id": "SAV-CHI", "name": "Savannah Port → Chicago",     "origin": (32.08, -81.10),  "dest": (41.88, -87.63)},
    {"lane_id": "LB-DEN",  "name": "Long Beach Port → Denver",    "origin": (33.77, -118.19), "dest": (39.74, -104.98)},
]

# ── HELPERS ──────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.asin(math.sqrt(a))

def point_to_segment_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2-x1, y2-y1
    if dx == 0 and dy == 0:
        return haversine(px, py, x1, y1)
    t = max(0, min(1, ((px-x1)*dx + (py-y1)*dy) / (dx*dx + dy*dy)))
    return haversine(px, py, x1 + t*dx, y1 + t*dy)

def score_event(event_lat, event_lon, severity, radius=350):
    impacts = []
    for lane in FREIGHT_LANES:
        olat, olon = lane['origin']
        dlat, dlon = lane['dest']
        dist = point_to_segment_dist(event_lat, event_lon, olat, olon, dlat, dlon)
        if dist <= radius:
            pf = max(0, 1 - dist/radius)
            impacts.append({
                "lane_id": lane['lane_id'],
                "lane_name": lane['name'],
                "distance_mi": round(dist, 1),
                "impact": round(severity * pf, 2)
            })
    return sorted(impacts, key=lambda x: -x['impact'])

# ── DATA FETCHERS ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_weather():
    try:
        url = "https://api.weather.gov/alerts/active?area=US"
        r = requests.get(url, headers={"User-Agent": "LaneRiskAgent/1.0"}, timeout=12)
        alerts = []
        for feat in r.json().get('features', [])[:25]:
            props = feat.get('properties', {})
            geo = feat.get('geometry') or {}
            coords = None
            if geo.get('type') == 'Polygon':
                pts = geo['coordinates'][0]
                coords = (sum(p[1] for p in pts)/len(pts), sum(p[0] for p in pts)/len(pts))
            elif geo.get('type') == 'MultiPolygon':
                pts = geo['coordinates'][0][0]
                coords = (sum(p[1] for p in pts)/len(pts), sum(p[0] for p in pts)/len(pts))
            if coords:
                sev_map = {'Extreme': 90, 'Severe': 70, 'Moderate': 45, 'Minor': 20}
                alerts.append({
                    "source": "NOAA", "type": props.get('event', 'Weather Alert'),
                    "headline": props.get('headline', '')[:100],
                    "severity": props.get('severity', 'Minor'),
                    "score": sev_map.get(props.get('severity', 'Minor'), 20),
                    "lat": coords[0], "lon": coords[1]
                })
        return alerts
    except:
        return _sample_weather()

@st.cache_data(ttl=300)
def fetch_earthquakes():
    try:
        end = datetime.utcnow()
        start = end - timedelta(days=3)
        url = (f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
               f"&starttime={start.strftime('%Y-%m-%d')}&endtime={end.strftime('%Y-%m-%d')}"
               f"&minmagnitude=4.0&minlatitude=25&maxlatitude=50&minlongitude=-125&maxlongitude=-65")
        r = requests.get(url, timeout=12)
        events = []
        for feat in r.json().get('features', []):
            props = feat['properties']
            coords = feat['geometry']['coordinates']
            mag = props.get('mag', 0)
            events.append({
                "source": "USGS", "type": f"M{mag:.1f} Earthquake",
                "headline": props.get('place', '')[:100],
                "severity": "Severe" if mag >= 6 else "Moderate",
                "score": min(90, max(20, int((mag-3)*20))),
                "lat": coords[1], "lon": coords[0]
            })
        return events
    except:
        return _sample_quakes()

def _sample_weather():
    return [
        {"source":"NOAA","type":"Winter Storm Warning","headline":"Heavy snow 12-18 inches expected along I-80 corridor","severity":"Severe","score":70,"lat":41.5,"lon":-88.0},
        {"source":"NOAA","type":"Tornado Watch","headline":"Tornado watch in effect across North Texas","severity":"Severe","score":70,"lat":33.5,"lon":-97.0},
        {"source":"NOAA","type":"Blizzard Warning","headline":"Blizzard conditions expected in Rockies overnight","severity":"Extreme","score":90,"lat":39.5,"lon":-105.0},
        {"source":"NOAA","type":"Flood Warning","headline":"Flash flooding possible along Gulf Coast","severity":"Moderate","score":45,"lat":30.0,"lon":-90.0},
        {"source":"NOAA","type":"Ice Storm Warning","headline":"Ice accumulation up to 0.5 inches along I-75","severity":"Severe","score":70,"lat":34.5,"lon":-84.5},
    ]

def _sample_quakes():
    return [
        {"source":"USGS","type":"M5.2 Earthquake","headline":"15km NW of Ridgecrest, CA","severity":"Moderate","score":44,"lat":35.8,"lon":-117.8},
        {"source":"USGS","type":"M4.8 Earthquake","headline":"Southern California","severity":"Moderate","score":36,"lat":34.2,"lon":-116.5},
    ]

def compute_lane_risks(events):
    lane_risk = {
        lane['lane_id']: {"name": lane['name'], "total": 0, "count": 0, "events": []}
        for lane in FREIGHT_LANES
    }
    for ev in events:
        for impact in score_event(ev['lat'], ev['lon'], ev['score']):
            lid = impact['lane_id']
            lane_risk[lid]['total'] += impact['impact']
            lane_risk[lid]['count'] += 1
            lane_risk[lid]['events'].append({**ev, "dist_mi": impact['distance_mi'], "contribution": impact['impact']})

    max_score = max((v['total'] for v in lane_risk.values()), default=1) or 1
    for lid in lane_risk:
        s = round(min(100, (lane_risk[lid]['total'] / max_score) * 100), 1)
        lane_risk[lid]['risk_score'] = s
        lane_risk[lid]['risk_level'] = "HIGH" if s >= 60 else "MEDIUM" if s >= 25 else "LOW"
    return lane_risk

def ai_brief(lane_name, risk_score, events, api_key):
    if not api_key or api_key == "sk-ant-...":
        evts = events[:3]
        return (f"{lane_name} is flagged at risk score {risk_score}/100. "
                f"Active signals include {', '.join(set(e['type'] for e in evts))}. "
                f"Recommend checking carrier availability and monitoring for delays.")
    evts_text = "\n".join([f"- {e['source']} {e['type']}: {e['headline']} ({e['dist_mi']} mi away)" for e in events[:4]])
    prompt = (f"You are a freight ops analyst. Write a 3-sentence briefing for a planner.\n\n"
              f"Lane: {lane_name} (Risk Score: {risk_score}/100)\nSignals:\n{evts_text}\n\n"
              f"Format: 1) What is disrupted. 2) Likely impact. 3) Action. Under 70 words.")
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=180,
                                     messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text
    except:
        return f"{lane_name} risk score {risk_score}/100. Check carrier availability before booking."

# ── UI ────────────────────────────────────────────────────────
st.title("🚛 Intermodal Lane Risk Agent")
st.markdown("**Real-time freight disruption risk scoring across 15 major US corridors**")
st.markdown("*Built by Deekshita Sai Patibandla | Thunderbird School of Global Management*")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    _secret_key = ""
    try:
        _secret_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except:
        pass
    if _secret_key:
        api_key = _secret_key
        st.success("AI briefs active", icon="🤖")
    else:
        api_key = st.text_input("Anthropic API Key (for AI briefs)", type="password", placeholder="sk-ant-...")
    radius = st.slider("Alert Radius (miles)", 100, 500, 350, 50)
    show_low = st.checkbox("Show LOW risk lanes", value=False)
    st.markdown("---")
    st.caption("Data: NOAA Weather API · USGS Earthquake API")
    st.caption("Refreshes every 5 minutes")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# Fetch data
with st.spinner("Fetching live hazard data..."):
    weather = fetch_weather()
    quakes = fetch_earthquakes()
    all_events = weather + quakes

lane_risk = compute_lane_risks(all_events)

# Top metrics
col1, col2, col3, col4 = st.columns(4)
high_lanes = [l for l in lane_risk.values() if l['risk_level'] == "HIGH"]
med_lanes  = [l for l in lane_risk.values() if l['risk_level'] == "MEDIUM"]
col1.metric("🔴 HIGH Risk Lanes",   len(high_lanes))
col2.metric("🟡 MEDIUM Risk Lanes", len(med_lanes))
col3.metric("📡 Active Hazard Events", len(all_events))
col4.metric("🛣️ Corridors Monitored", len(FREIGHT_LANES))

st.markdown("---")

# ── BOOKING RECOMMENDATION PANEL ────────────────────────────
sorted_lanes = sorted(lane_risk.items(), key=lambda x: -x[1]['risk_score'])
top_lid, top_data = sorted_lanes[0]
safe_lanes = [(lid, d) for lid, d in sorted_lanes if d['risk_level'] == "LOW" and d['count'] == 0]
best_alt = safe_lanes[0] if safe_lanes else sorted_lanes[-1]

if top_data['risk_level'] == "HIGH":
    rec_color = "#ff4b4b"
    rec_icon = "🔴"
    rec_action = f"**AVOID {top_lid} today.** Risk score {top_data['risk_score']}/100 — active disruption events within corridor range."
    alt_text = f"**Best alternative:** {best_alt[0]} ({best_alt[1]['name']}) — Risk score {best_alt[1]['risk_score']}/100, {best_alt[1]['count']} active events."
elif top_data['risk_level'] == "MEDIUM":
    rec_color = "#ffa500"
    rec_icon = "🟡"
    rec_action = f"**MONITOR {top_lid} before booking.** Risk score {top_data['risk_score']}/100 — elevated disruption signals present."
    alt_text = f"**Safer option:** {best_alt[0]} ({best_alt[1]['name']}) — Risk score {best_alt[1]['risk_score']}/100."
else:
    rec_color = "#00cc66"
    rec_icon = "🟢"
    rec_action = "**All monitored corridors are LOW risk.** Safe to book on any tracked lane."
    alt_text = "No rerouting required at this time."

st.markdown(f"""
<div style='background:#0e1a2b;border:1px solid {rec_color};border-left:6px solid {rec_color};
padding:16px 20px;border-radius:6px;margin-bottom:16px;'>
<span style='color:{rec_color};font-size:16px;font-weight:bold;'>{rec_icon} Booking Recommendation</span><br><br>
<span style='color:#eee;font-size:14px;'>{rec_action}</span><br>
<span style='color:#aaa;font-size:13px;margin-top:6px;display:block;'>{alt_text}</span>
</div>
""", unsafe_allow_html=True)

# Build risk table
rows = []
for lid, data in lane_risk.items():
    if not show_low and data['risk_level'] == "LOW":
        continue
    emoji = "🔴" if data['risk_level'] == "HIGH" else "🟡" if data['risk_level'] == "MEDIUM" else "🟢"
    rows.append({
        "Lane": lid,
        "Corridor": data['name'],
        "Risk Score": data['risk_score'],
        "Level": f"{emoji} {data['risk_level']}",
        "Events": data['count'],
    })

risk_df = pd.DataFrame(rows, columns=["Lane","Corridor","Risk Score","Level","Events"]).sort_values("Risk Score", ascending=False).reset_index(drop=True) if rows else pd.DataFrame(columns=["Lane","Corridor","Risk Score","Level","Events"])

col_left, col_right = st.columns([1.2, 1])

with col_left:
    st.subheader("🗺️ Lane Risk Ranking")
    st.dataframe(
        risk_df,
        use_container_width=True, height=420
    )

with col_right:
    st.subheader("📋 AI Briefings — Top Risk Lanes")
    top_lanes = risk_df[risk_df['Level'].str.contains("HIGH|MEDIUM")].head(4)['Lane'].tolist()
    if not top_lanes:
        st.info("No HIGH or MEDIUM risk lanes right now. All corridors clear.")
    for lid in top_lanes:
        data = lane_risk[lid]
        if data['count'] > 0:
            brief = ai_brief(data['name'], data['risk_score'], data['events'], api_key)
            color = "#ff4b4b" if data['risk_level'] == "HIGH" else "#ffa500"
            st.markdown(f"""
            <div style='background:#1a1a2e;border-left:4px solid {color};padding:12px;border-radius:4px;margin-bottom:10px;'>
            <b style='color:{color}'>{lid} — {data['name']}</b><br>
            <small style='color:#aaa'>Risk Score: {data['risk_score']}/100 · {data['count']} events</small><br><br>
            <span style='color:#eee;font-size:13px'>{brief}</span>
            </div>
            """, unsafe_allow_html=True)

st.markdown("---")

# Event detail table
st.subheader("📡 Active Hazard Events")
ev_rows = []
for ev in all_events:
    impacts = score_event(ev['lat'], ev['lon'], ev['score'], radius)
    top_lane = impacts[0]['lane_id'] if impacts else "—"
    ev_rows.append({
        "Source": ev['source'],
        "Event Type": ev['type'],
        "Headline": ev['headline'][:80],
        "Severity": ev['severity'],
        "Nearest Lane": top_lane,
        "Impact Score": impacts[0]['impact'] if impacts else 0,
    })
ev_df = pd.DataFrame(ev_rows, columns=["Source","Event Type","Headline","Severity","Nearest Lane","Impact Score"]).sort_values("Impact Score", ascending=False).reset_index(drop=True) if ev_rows else pd.DataFrame(columns=["Source","Event Type","Headline","Severity","Nearest Lane","Impact Score"])
st.dataframe(ev_df, use_container_width=True, height=280)

st.markdown("---")
st.caption("Data: NOAA Weather API · USGS Earthquake API · Built for Supply Chain Analyst portfolio")
st.caption("Deekshita Sai Patibandla | Thunderbird School of Global Management, ASU")
