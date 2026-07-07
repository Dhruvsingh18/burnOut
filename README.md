
# Burnout Tracker

A full-stack screen time tracker that monitors which apps you use, analyzes your Chrome browsing productivity, and helps you avoid developer burnout — all in real time.

## What it does

Burnout Tracker runs a silent background agent on your laptop that tracks which applications you use and for how long. Every 60 seconds, it records your active window and sends it to a cloud backend. A live dashboard shows your screen time broken down by app, category, and hour — with Chrome-specific analysis that classifies your browsing as productive, unproductive, or neutral based on the sites you visit.

## Features

- **Real-time screen time tracking** — knows exactly which apps you used and for how long each day
- **Chrome tab analysis** — classifies browsing as productive (GitHub, Stack Overflow, Coursera) vs unproductive (YouTube, Instagram, Reddit) vs neutral
- **Live dashboard** — today's total, hourly breakdown, weekly trends, 30-day history
- **App time limits** — set daily limits per app, get alerts when exceeded
- **Compare view** — today vs yesterday side by side
- **Automation panel** — focus modes, alert rules, break reminders
- **Session persistence** — data is stored in the cloud, no data lost between sessions
- **Chrome Extension** — optional install for full tab tracking across all open windows
- **Windows Tray App** — runs silently in the background with a system tray icon, auto-starts on login

## Tech stack

- **Backend** — Python, FastAPI, SQLAlchemy, PostgreSQL (deployed on Render)
- **Frontend** — Vanilla JavaScript, Chart.js (deployed on Vercel)
- **Agent** — Python, Win32 API, psutil (runs locally on Windows)
- **Chrome Extension** — Manifest V3, background service worker
- **Tray App** — Python, pystray, PyInstaller (packaged as a standalone Windows EXE)

## How it works

A lightweight Python agent runs on your laptop and polls your active window every 60 seconds using the Windows API. Each sample is sent immediately to a FastAPI backend deployed on Render, which normalises app names, classifies productivity categories, and stores everything in a PostgreSQL database. The dashboard — deployed on Vercel — fetches live data from the backend and renders it with Chart.js. An optional Chrome extension sends all open tab URLs every minute for more accurate browsing analysis.

## Live demo

Dashboard: [burn-out-nu.vercel.app](https://burn-out-nu.vercel.app)
Backend API: [burnout-n9p9.onrender.com](https://burnout-n9p9.onrender.com/docs)

## Getting started

See the full documentation for setup instructions, API reference, deployment guide, and troubleshooting.
