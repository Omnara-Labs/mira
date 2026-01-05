# mira
A private, Nextcloud Talk-integrated AI assistant powered by DeepSeek V3.2, featuring "Five Senses" MCP tools for real-time weather, geo-location, time sync, personal memory retrieval, and live web search.


<div align="center">

# 🌿 Mira Agent

**A DeepSeek-R1 powered personal secretary & intimate companion with "Five Senses" sensory matrix.**

[🌐 Website](https://www.omnara.top/) | [🐦 X (Twitter)](https://x.com/Omnara_official) | [简体中文](./README_zh.md)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python-Version](https://img.shields.io/badge/Python-3.10%2B-green)](requirements.txt)
[![Nextcloud-Ready](https://img.shields.io/badge/Platform-Nextcloud%20Talk-informational)](https://nextcloud.com/talk/)
[![Powered-by-DeepSeek](https://img.shields.io/badge/Powered%20by-DeepSeek--V3.2-6112a3)](https://github.com/deepseek-ai/DeepSeek-V3)

</div>

---

## 1. 📖 Introduction

Mira is a next-generation AI agent developed by **Omnara Labs**. Deeply integrated with **Nextcloud Talk** and powered by **DeepSeek-Reasoner (R1)**, Mira is designed to be more than just a chatbot.

Through the **MCP (Model Context Protocol)**, Mira possesses a complete "Five Senses" sensory matrix, allowing her to perceive the real world while ensuring 100% data sovereignty by running on your private hardware (e.g., Raspberry Pi).

### Core Values
* **🧠 Reasoning-First**: Native support for DeepSeek-R1 with Chain of Thought (CoT).
* **🔒 Privacy Sovereign**: End-to-end communication via Nextcloud; logs and memories stay on your hardware.
* **🛰️ Real-time Perception**: Breaks the knowledge cutoff with real-time tools for weather, geo, and news.
* **🚀 Production Ready**: Native `systemd` support for 24/7 stable operation.

---

## 2. 🛰️ Sensory Matrix

| Dimension | Description | Integration |
| :--- | :--- | :--- |
| **Sky (Weather)** | Real-time weather, warnings, and air quality | QWeather API |
| **Earth (Geo)** | Geocoding, POI search, and route planning | Amap API |
| **Time (Clock)** | Precise timing, astronomy, and holidays | NTSC |
| **Past (Memory)** | Long-term personal memory retrieval | Mem0 |
| **Present (Search)** | Real-time global web search | Tavily |

---

## 3. 🚀 Quick Start

### 3.1 Prerequisites
```bash
git clone [https://github.com/Omnara-Labs/mira.git](https://github.com/Omnara-Labs/mira.git)
cd mira
python -m venv mira_env
source mira_env/bin/activate
pip install -r requirements.txt
```

### 3.2 Configuration
Copy `.env.example` to `.env` and fill in your API keys:
```bash
cp .env.example .env
```
## 4. 🛠️ Production Deployment

Use `systemd` to ensure Mira stays online 24/7. After configuring the service file, run the following commands:
```bash
sudo systemctl enable mira_agent.service
sudo systemctl start mira_agent.service
```

<div align="center"> <br /> <p><b><a href="https://www.omnara.top/">Omnara Labs</a> - Giving AI Temperature and Touch</b></p> </div>
