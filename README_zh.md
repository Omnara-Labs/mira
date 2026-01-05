<div align="center">

# 🌿 Mira Agent

**由 DeepSeek-V3.2 驱动的私人亲密伙伴与智能助理，具备“五觉”感知能力的分布式 Agent。**

[🌐 官方网站](https://www.omnara.top/) | [🐦 X (Twitter)](https://x.com/Omnara_official) | [English](./README.md)

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python-Version](https://img.shields.io/badge/Python-3.10%2B-green)](requirements.txt)
[![Nextcloud-Ready](https://img.shields.io/badge/Platform-Nextcloud%20Talk-informational)](https://nextcloud.com/talk/)
[![Powered-by-DeepSeek](https://img.shields.io/badge/Powered%20by-DeepSeek--V3.2-6112a3)](https://github.com/deepseek-ai/DeepSeek-V3)

</div>

---

## 1. 📖 项目简介

Mira 是一款由 **Omnara Labs** 打造，深度集成 **Nextcloud Talk**、由 **DeepSeek-V3.2** 驱动的私人 Agent。

通过 **MCP (Model Context Protocol)** 协议，Mira 构建了完整的“五觉”感知系统。她运行在你的私有硬件（如树莓派）上，确保你的每一句私语、每一段记忆都只属于你自己。

---

## 2. 🛰️ 五觉感知矩阵 (Sensory Matrix)

| 维度 | 能力描述 | 接入方案 |
| :--- | :--- | :--- |
| **📡 天 (Weather)** | 实时气象监测、灾害预警、空气质量 | 和风天气 |
| **📍 地 (Geo)** | 地理逆编码、POI 搜索、路径规划 | 高德地图 |
| **⏰ 时 (Time)** | 精准授时、天文学历、日出日落 | 国家授时中心 |
| **💾 知过去 (Memory)** | 长短期私人记忆检索，越聊越懂你 | Mem0 |
| **🌐 知现在 (Search)** | 实时全网搜索，获取最新资讯 | Tavily |

---

## 3. 🚀 快速上手

### 3.1 环境准备

```bash
# 克隆项目
git clone [https://github.com/Omnara-Labs/mira.git](https://github.com/Omnara-Labs/mira.git)
cd mira

# 创建并激活虚拟环境
python -m venv mira_env
source mira_env/bin/activate

# 安装依赖项
pip install -r requirements.txt
```

### 3.2 配置
将 .env.example 复制为 .env，并填入你的 API 密钥：
```bash
cp .env.example .env
```


## 4. 🛠️ 生产环境部署
利用 systemd 确保 Mira 7*24 小时在线。将服务文件配置好后执行：

```bash
sudo systemctl enable mira_agent.service
sudo systemctl start mira_agent.service
```
<br />

<div align="center"> <p><b><a href="https://www.omnara.top/">Omnara Labs</a> - 赋予 AI 温度与触觉</b></p> <p>关注我们的 X: <a href="https://x.com/Omnara_official">@Omnara_official</a></p> </div>
