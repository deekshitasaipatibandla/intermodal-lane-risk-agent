# 🚛 Intermodal Lane Risk Agent

**Real-time freight disruption risk scoring across 15 major US freight corridors**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)

Built by **Deekshita Sai Patibandla** | Thunderbird School of Global Management, ASU

---

## The Problem

Freight planners at logistics companies manually check weather sites, USGS alerts, and news feeds separately to spot disruptions on their lanes. There is no unified risk score per corridor. A severe weather event combined with seismic activity on the same freight corridor creates compounding risk that planners often miss until shipments are already delayed.

## The Solution

An automated pipeline that:
1. Pulls live hazard data from NOAA and USGS (free, no API key needed)
2. Scores each event by proximity to 15 major US intermodal corridors
3. Aggregates risk into a 0–100 composite score per lane
4. Generates plain-English AI briefings via Claude (Anthropic API)
5. Delivers a ranked alert queue so planners see the top risk corridors in one view

## Results

| Metric | Value |
|--------|-------|
| Corridors monitored | 15 major US freight lanes |
| Data sources fused | NOAA Weather API + USGS Earthquake API |
| Alert processing time | < 30 seconds |
| Risk score | 0–100 composite per lane |
| AI briefing | Auto-generated per high-risk corridor |

## Corridors Covered

LA→CHI · LA→DAL · CHI→NYC · DAL→ATL · SEA→LA · HOU→CHI · MIA→NYC ·
LA→SEA · CHI→DAL · ATL→NYC · DEN→CHI · PHX→LA · KC→CHI · SAV→CHI · LB→DEN

## Stack

- **Python** — core pipeline
- **NOAA Weather API** — live severe weather alerts (free)
- **USGS Earthquake API** — real-time seismic events (free)
- **Anthropic API** — AI-generated ops briefings (Claude Haiku)
- **Streamlit** — interactive dashboard
- **Pandas / Shapely** — data processing and proximity scoring

## How to Run

```bash
git clone https://github.com/deekshitasaipatibandla/intermodal-lane-risk-agent
cd intermodal-lane-risk-agent
pip install -r requirements.txt
streamlit run app.py
```

Add your Anthropic API key in the sidebar to enable AI briefings.
Free API key: [console.anthropic.com](https://console.anthropic.com)

## Project Context

This is **Project 2 of 3** in my AI Supply Chain Analytics portfolio.

- ✅ Project 1: [Rural Demand Proxy Engine](https://github.com/deekshitasaipatibandla/rural-demand-proxy)
- ✅ Project 2: Intermodal Lane Risk Agent ← this repo
- 🔜 Project 3: De Minimis Compliance Defender

---

*Data: NOAA Weather API · USGS Earthquake API | Built for Supply Chain Analyst portfolio*
