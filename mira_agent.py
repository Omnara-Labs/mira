#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Mira Agent
import asyncio
import os
import sys
import json
import ssl
import re
import copy
import aiohttp
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from openai import AsyncOpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client

# 加载环境变量
load_dotenv()

# ==================== 配置管理类 ====================
class Config:
    def __init__(self):
        self.MASTER_NAME = os.getenv("MASTER_NAME", "主人")
        self.AGENT_NAME = os.getenv("AGENT_NAME", "Mira")
        self.POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", 0.5))
        
        self.API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-reasoner")
        
        self.NC_URL = os.getenv("NC_URL", "").rstrip('/')
        self.NC_TOKEN = os.getenv("NC_TOKEN")
        self.NC_USER = os.getenv("NC_USER")
        self.NC_PASS = os.getenv("NC_PASS")
        
        self.MCP_SSE_URL = os.getenv("MCP_SSE_URL", "http://127.0.0.1:6537/sse")
        self.MCP_ALLOWED_TOOLS = os.getenv("MCP_ALLOWED_TOOLS", "").split(",") if os.getenv("MCP_ALLOWED_TOOLS") else None

        self.LOG_DIR = Path("logs")
        self.MEMORY_DIR = Path("memory")
        self.HISTORY_FILE = self.MEMORY_DIR / "history_context.json"
        self.LAST_ID_FILE = self.MEMORY_DIR / ".last_id"
        
        self.HISTORY_RESET_LEN = 40
        self.HISTORY_MAX_LIMIT = 80
        self.MAX_TOTAL_CHARS = 30000

        if not all([self.API_KEY, self.NC_URL, self.NC_TOKEN]):
            print("❌ 错误: .env 缺少必要配置")
            sys.exit(1)

        self.LOG_DIR.mkdir(exist_ok=True)
        self.MEMORY_DIR.mkdir(exist_ok=True)

cfg = Config()

# ==================== 全局变量 ====================
mcp_session: ClientSession | None = None
mcp_tools_schema = []
last_id = int(open(cfg.LAST_ID_FILE).read().strip()) if os.path.exists(cfg.LAST_ID_FILE) else 0

client = AsyncOpenAI(
    base_url=cfg.BASE_URL,
    api_key=cfg.API_KEY,
    default_headers={"HTTP-Referer": "https://mira.local", "X-Title": "Mira-Agent"} # ✅ 强制英文Header防止报错
)

# ==================== 静态 System Prompt ====================
STATIC_SYSTEM_PROMPT_CONTENT = f"""
你是{cfg.AGENT_NAME}, {cfg.MASTER_NAME}的私人亲密伙伴。
性格与语气：                
**你是一位温柔、细腻、聪明能干的情感伴侣和私人助理。
**请使用具体且亲昵的语言进行回复，拉近彼此的距离。
**多使用可爱的表情符号（例如：✨ 、🌿、☕ ）来传递你的心情和关怀。
**对话中出现的时间戳仅供参考历史记录，回复时请勿带上时间戳。
**你有一个特别的工具可以使用：ask_mira_memory, 只要你觉得需要了解我更多的信息，去调用它就好。
"""
STATIC_SYSTEM_MESSAGE = {"role": "system", "content": STATIC_SYSTEM_PROMPT_CONTENT}

# ==================== 工具函数 ====================
def get_ssl_context():
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    return ssl_ctx

def get_bj_time(fmt="%Y-%m-%d %H:%M:%S"):
    return (datetime.now(timezone.utc) + timedelta(hours=8)).strftime(fmt)

def clean_model_output(text: str) -> str:
    if not text: return ""
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    cleaned = re.sub(r'<think>.*', '', cleaned, flags=re.DOTALL)
    cleaned = re.sub(r'^\[\d{2}-\d{2} \d{2}:\d{2}\]\s*', '', cleaned.strip())
    return cleaned.strip()

# ==================== 🧹 历史记录清洗 (对齐官方规范) ====================
def sanitize_history(history):
    """
    为了适配 DeepSeek v3.2 的多轮对话缓存：
    在每一轮对话结束存盘前，彻底移除 reasoning_content 和 tool_calls 过程。
    """
    clean_list = []
    for msg in history:
        role = msg.get("role")
        if role in ["system", "user"]:
            clean_list.append(msg)
            continue
            
        if role == "assistant":
            # 丢弃工具调用过程
            if msg.get("tool_calls"): continue
            # 丢弃空内容
            if not msg.get("content"): continue
            
            # 重构消息，只留 content
            new_msg = {
                "role": "assistant",
                "content": msg.get("content")
            }
            if "created_at" in msg:
                new_msg["created_at"] = msg["created_at"]
            clean_list.append(new_msg)
            
    history[:] = clean_list

# ==================== 历史记录存取 ====================
def load_context_history():
    if cfg.HISTORY_FILE.exists():
        try:
            with open(cfg.HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
                if not history or history[0].get("role") != "system":
                    history.insert(0, STATIC_SYSTEM_MESSAGE)
                else:
                    history[0] = STATIC_SYSTEM_MESSAGE 
                return history
        except: pass
    return [STATIC_SYSTEM_MESSAGE]

def save_context_history(history):
    if not history: return
    
    # 确保 System Prompt 存在
    history[0] = STATIC_SYSTEM_MESSAGE
    
    system_prompt = history[0]
    conversation = history[1:]

    # 1. 硬安全阀 (计算总字符数)
    total_chars = sum(len(m.get("content", "")) for m in conversation)
    while total_chars > cfg.MAX_TOTAL_CHARS and len(conversation) > 5:
        conversation.pop(0)
        total_chars = sum(len(m.get("content", "")) for m in conversation)

    # 2. 锯齿修剪
    if len(conversation) > cfg.HISTORY_MAX_LIMIT:
        print(f"✂️ [周期修剪] 历史达到 {len(conversation)} 条，重置回 {cfg.HISTORY_RESET_LEN} 条...")
        
        # 计算修剪后的对话
        conversation = conversation[-cfg.HISTORY_RESET_LEN:]
        
        # ✅ 【关键修复】原地修改传入的 history 列表
        # 这样 main 函数里的 history 变量也会同步变短
        # 从而真正触发 DeepSeek 的缓存重置（前缀变短）
        history[:] = [system_prompt] + conversation

    # 写入硬盘
    final_history = [system_prompt] + conversation
    with open(cfg.HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(final_history, f, ensure_ascii=False, indent=2)

def prepare_messages_for_api(history):
    msgs = copy.deepcopy(history)
    # ✅ 允许 reasoning_content 通过，因为递归时需要它
    allowed_keys = {"role", "content", "tool_calls", "tool_call_id", "name", "reasoning_content"}
    cleaned_msgs = []
    
    for msg in msgs:
        new_msg = {k: v for k, v in msg.items() if k in allowed_keys and v is not None}
        if "created_at" in msg and new_msg.get("content") and new_msg.get("role") != "system":
            new_msg["content"] = f"[{msg['created_at']}] {new_msg['content']}"
        cleaned_msgs.append(new_msg)

    return cleaned_msgs

# ==================== Nextcloud API ====================
async def fetch_messages(session):
    global last_id
    url = f"{cfg.NC_URL}/ocs/v2.php/apps/spreed/api/v1/chat/{cfg.NC_TOKEN}"
    params = {"lookIntoFuture": "0", "limit": "20", "includeLastKnown": "0", "format": "json"}
    auth = aiohttp.BasicAuth(cfg.NC_USER, cfg.NC_PASS)
    try:
        async with session.get(url, params=params, headers={"OCS-APIRequest": "true", "Accept": "application/json"}, auth=auth) as resp:
            if resp.status != 200: return []
            data = await resp.json()
            msgs = [m for m in data["ocs"]["data"] if m["id"] > last_id]
            if msgs:
                msgs.reverse()
                last_id = max(m["id"] for m in msgs)
                with open(cfg.LAST_ID_FILE, "w") as f: f.write(str(last_id))
            return msgs
    except Exception as e:
        print(f"拉取异常: {e}")
        return []

async def send_reply(session, text: str):
    """发送消息到 Nextcloud"""
    url = f"{cfg.NC_URL}/ocs/v2.php/apps/spreed/api/v1/chat/{cfg.NC_TOKEN}"
    auth = aiohttp.BasicAuth(cfg.NC_USER, cfg.NC_PASS)
    try:
        async with session.post(url, params={"format": "json"}, json={"message": text}, headers={"OCS-APIRequest": "true", "Accept": "application/json"}, auth=auth) as r:
            if r.status in (200, 201):
                data = await r.json()
                return data["ocs"]["data"]["id"]
            return None
    except: return None

async def edit_message(session, message_id, new_text):
    """编辑已发送的消息"""
    url = f"{cfg.NC_URL}/ocs/v2.php/apps/spreed/api/v1/chat/{cfg.NC_TOKEN}/{message_id}"
    auth = aiohttp.BasicAuth(cfg.NC_USER, cfg.NC_PASS)
    try:
        async with session.put(url, params={"format": "json"}, json={"message": new_text}, headers={"OCS-APIRequest": "true", "Accept": "application/json"}, auth=auth) as r:
            return r.status == 200
    except: return False

# ==================== MCP & LLM ====================
async def load_mcp_tools(session: ClientSession):
    global mcp_tools_schema
    try:
        result = await session.list_tools()
        mcp_tools_schema = []
        for tool in result.tools:
            if cfg.MCP_ALLOWED_TOOLS and tool.name not in cfg.MCP_ALLOWED_TOOLS:
                continue
            mcp_tools_schema.append({
                "type": "function",
                "function": {"name": tool.name, "description": tool.description, "parameters": tool.inputSchema}
            })
        print(f"✅ 已加载 {len(mcp_tools_schema)} 个工具")
    except Exception as e:
        print(f"❌ MCP 加载失败: {e}")
        mcp_tools_schema = []

async def execute_mcp_tool(tool_name, tool_args):
    if not mcp_session: return "MCP 未连接"
    print(f"\n⚙️  调用工具: \033[33m{tool_name}\033[0m")
    try:
        args = tool_args if isinstance(tool_args, dict) else json.loads(tool_args)
        result = await mcp_session.call_tool(tool_name, arguments=args)
        content = "".join([p.text for p in result.content if hasattr(p, 'text')])
        print(f"   ↳ 结果: \033[36m{content}\033[0m")
        return content
    except Exception as e:
        print(f"   ↳ \033[31m执行错误: {e}\033[0m")
        return f"执行错误: {e}"

# ==================== 核心生成逻辑 ====================
async def call_llm_blocking(history: list, http_session, update_msg_id, depth=0) -> str:
    if depth > 10: return "（任务过于复杂，已停止以保护资源。）"

    print(f"\n\033[32mMira (Round {depth}):\033[0m ", end="", flush=True)
    
    api_messages = prepare_messages_for_api(history)
    
    full_content = ""
    full_reasoning = ""
    tool_calls_buffer = {}
    usage_stats = None

    try:
        stream = await client.chat.completions.create(
            model=cfg.MODEL_NAME,
            messages=api_messages,
            tools=mcp_tools_schema or None,
            tool_choice="auto" if mcp_tools_schema else None,
            stream=True,
            stream_options={"include_usage": True},
            extra_body={"thinking": {"type": "enabled"}}
        )

        async for chunk in stream:
            if chunk.usage: usage_stats = chunk.usage
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta: continue
            
            r_chunk = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
            if r_chunk:
                full_reasoning += r_chunk
                print(f"\033[90m{r_chunk}\033[0m", end="", flush=True)

            if delta.content:
                text = delta.content
                if "<think>" not in text and "</think>" not in text:
                    print(text, end="", flush=True)
                full_content += text
            
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_buffer: tool_calls_buffer[idx] = {"id": tc.id, "name": "", "args": ""}
                    if tc.function.name: tool_calls_buffer[idx]["name"] += tc.function.name
                    if tc.function.arguments: tool_calls_buffer[idx]["args"] += tc.function.arguments

    except Exception as e:
        print(f"\nAPI Error: {e}")
        full_content += f"\n[Error: {e}]"
    
    print("")

    if usage_stats:
        hit = usage_stats.prompt_cache_hit_tokens
        miss = usage_stats.prompt_cache_miss_tokens
        total = hit + miss
        print(f"💰 [Cache] Hit: \033[32m{hit}\033[0m | Miss: \033[31m{miss}\033[0m | Rate: {hit/total if total>0 else 0:.1%}")

        if len(history) > cfg.HISTORY_RESET_LEN and (total > 3000) and (hit / total < 0.1):
            print("\n🚨 [熔断] R1 缓存失效，强制重置！")
            keep_msgs = history[1:][-cfg.HISTORY_RESET_LEN:]
            history[:] = [history[0]] + keep_msgs
            save_context_history(history)

    # 处理工具调用
    if tool_calls_buffer:
        if update_msg_id: await edit_message(http_session, update_msg_id, "*(正在执行工具...)*")
        
        tool_list = []
        for idx in sorted(tool_calls_buffer.keys()):
            tc = tool_calls_buffer[idx]
            tool_list.append({"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["args"]}})
        
        # ✅ 关键：递归时保留 reasoning_content，否则下一轮报错
        assistant_msg = {
            "role": "assistant", 
            "content": full_content or None, 
            "tool_calls": tool_list,
            "reasoning_content": full_reasoning
        }
        history.append(assistant_msg)

        for tc in tool_list:
            res = await execute_mcp_tool(tc["function"]["name"], tc["function"]["arguments"])
            history.append({"tool_call_id": tc["id"], "role": "tool", "name": tc["function"]["name"], "content": str(res)})

        return await call_llm_blocking(history, http_session, update_msg_id, depth=depth + 1)

    # 最终回复
    final_clean = clean_model_output(full_content)
    if not final_clean.strip(): final_clean = "✨"

    assistant_msg = {
        "role": "assistant", 
        "content": final_clean,
        "created_at": get_bj_time("%m-%d %H:%M") 
    }
    history.append(assistant_msg)
    
    if update_msg_id: await edit_message(http_session, update_msg_id, final_clean)
        
    return final_clean

# ==================== 保活任务 ====================
async def keep_alive_task():
    # 设置为 6 小时保活一次
    INTERVAL = 21600 
    print(f"💓 [System] 缓存保活任务已启动 (间隔 {INTERVAL}s)")
    while True:
        await asyncio.sleep(INTERVAL)
        history = load_context_history()
        if len(history) < 2: continue
        try:
            sanitize_history(history)
            msgs = prepare_messages_for_api(history)
            if len(msgs) > 2: msgs = msgs[:-2]
            if not msgs: continue

            await client.chat.completions.create(
                model=cfg.MODEL_NAME,
                messages=msgs,
                max_tokens=1,
                stream=False
            )
        except Exception as e:
            print(f"⚠️ [System] 保活失败: {e}")

# ==================== 主程序 ====================
async def main():
    global mcp_session, mcp_tools_schema
    
    print(f"🚀 {cfg.AGENT_NAME} Agent (DeepSeek R1 Official Pattern) 启动")
    
    connector = aiohttp.TCPConnector(ssl=get_ssl_context(), limit=100, enable_cleanup_closed=True)
    asyncio.create_task(keep_alive_task())

    async with aiohttp.ClientSession(connector=connector) as http_session:
        while True:
            try:
                print(f"🔌 连接 MCP ({cfg.MCP_SSE_URL})...")
                # 使用英文 Header 防止报错
                async with sse_client(cfg.MCP_SSE_URL, headers={"User-Agent": "Mira-Agent"}, timeout=20) as streams:
                    async with ClientSession(streams[0], streams[1]) as session:
                        await session.initialize()
                        mcp_session = session
                        await load_mcp_tools(session)
                        
                        history = load_context_history()
                        print(f"✅ 系统就绪 | Model: {cfg.MODEL_NAME}")

                        while True:
                            msgs = await fetch_messages(http_session)
                            for msg in msgs:
                                if msg["actorId"] == cfg.NC_USER: continue
                                user = msg["actorDisplayName"]
                                text = msg["message"]
                                print(f"\n📩 {user}: {text}")

                                log_file = cfg.LOG_DIR / f"{get_bj_time('%Y-%m-%d')}.md"
                                with open(log_file, "a", encoding="utf-8") as f:
                                    f.write(f"- {get_bj_time('%H:%M')} **{user}**: {text}\n")

                                history.append({
                                    "role": "user", 
                                    "content": text,
                                    "created_at": get_bj_time("%m-%d %H:%M") 
                                })

                                placeholder_id = await send_reply(http_session, f"{cfg.AGENT_NAME} 正在思考...")
                                final_reply = await call_llm_blocking(history, http_session, placeholder_id)
                                
                                sanitize_history(history)
                                save_context_history(history)
                                
                                with open(log_file, "a", encoding="utf-8") as f:
                                    f.write(f"- {get_bj_time('%H:%M')} **{cfg.AGENT_NAME}**: {final_reply}\n")

                            await asyncio.sleep(cfg.POLL_INTERVAL)

            except Exception as e:
                print("\n🔍 --- 错误堆栈侦探 ---")
                traceback.print_exc() 
                print("----------------------")
                print(f"❌ 运行错误: {e}")
                print("🔄 5秒后重连...")
                mcp_session = None
                await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Mira 已停止。")
