# -*- coding: utf-8 -*-
"""
统一AI路由 - 多provider自动切换，免费优先，零豆包token
支持: Gemini(需代理) / 硅基流动 / 智谱 / 通义 / DeepSeek / Moonshot / Pollinations(免费无key)
用法:
  from ai_router import chat, summarize, classify, extract, translate
  result = chat("你好")  # 自动选最优provider
  result = chat("你好", provider="gemini")  # 指定provider
"""
import requests, json, sys, time, os
from config import PROXIES

# ============ Provider配置 ============
# key为空则跳过该provider；去对应平台注册免费key填入config.py即可
PROVIDERS = {
    # 硅基流动 - 免费模型多(Qwen/GLM/DeepSeek)，国内直连，OpenAI兼容
    "siliconflow": {
        "url": "https://api.siliconflow.cn/v1/chat/completions",
        "key": "",  # 去 siliconflow.cn 注册，免费额度
        "model": "Qwen/Qwen2.5-7B-Instruct",  # 免费
        "proxy": None,
    },
    # 智谱 - GLM-4-Flash永久免费，国内直连
    "zhipu": {
        "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "key": "",  # 去 bigmodel.cn 注册
        "model": "glm-4-flash",  # 免费
        "proxy": None,
    },
    # 通义千问 - qwen-turbo有免费额度，国内直连
    "dashscope": {
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        "key": "",  # 去 dashscope.aliyun.com 注册
        "model": "qwen-turbo",
        "proxy": None,
    },
    # DeepSeek - 极便宜(¥1/百万token)，国内直连，质量高
    "deepseek": {
        "url": "https://api.deepseek.com/chat/completions",
        "key": "",  # 去 platform.deepseek.com 充值
        "model": "deepseek-chat",
        "proxy": None,
    },
    # 火山引擎豆包 - doubao-seed-2-0-lite每日200万token免费，国内直连
    "ark": {
        "url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        "key": "",
        "model": "doubao-seed-2-0-lite-260428",
        "proxy": None,
    },
    # Moonshot Kimi - 长文本强，国内直连
    "moonshot": {
        "url": "https://api.moonshot.cn/v1/chat/completions",
        "key": "",  # 去 platform.moonshot.cn 注册
        "model": "moonshot-v1-8k",
        "proxy": None,
    },
    # Gemini - 免费1500次/天，需FlClash代理
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
        "key": "",  # 已在config.py
        "model": "gemini-flash-latest",
        "proxy": PROXIES,
    },
    # Pollinations - 完全免费无key，有限流，作为最后兜底
    "pollinations": {
        "url": "https://text.pollinations.ai/",
        "key": "FREE",
        "model": "openai",
        "proxy": None,
    },
}

# 从config.py覆盖key
import config as _cfg
for _pname, _kname in [("gemini","GEMINI_KEY"),("siliconflow","SF_KEY"),
    ("zhipu","ZHIPU_KEY"),("dashscope","DASHSCOPE_KEY"),
    ("deepseek","DEEPSEEK_KEY"),("moonshot","MOONSHOT_KEY"),
    ("ark","ARK_KEY")]:
    _k = getattr(_cfg, _kname, "")
    if _k:
        PROVIDERS[_pname]["key"] = _k

# ============ 任务路由策略 ============
# 中文简单任务 → 国内免费优先；英文/复杂任务 → Gemini/DeepSeek
# 2026-08-29实测延迟重排：智谱0.4s/通义0.3s/火山2.1s/DeepSeek0.9s/Gemini55s(代理慢,垫底)
# 已摘除：siliconflow/moonshot(未配key)、pollinations(402失效)
ROUTE = {
    "zh": ["zhipu", "dashscope", "ark", "siliconflow", "deepseek", "gemini"],
    "en": ["deepseek", "ark", "siliconflow", "zhipu", "dashscope", "gemini"],
    "code": ["deepseek", "ark", "siliconflow", "zhipu", "dashscope", "gemini"],
    "long": ["deepseek", "ark", "siliconflow", "gemini"],
}

_stats = {"calls": 0, "errors": 0, "cache_hit": 0, "by_provider": {}}
_cooldown = {}  # provider -> timestamp until which it's skipped
_cache = {}     # md5(prompt+task) -> (response, timestamp)
CACHE_TTL = 3600  # 缓存1小时
# 磁盘持久化语义缓存：本项目多为一次性脚本进程，内存缓存退出即失，落盘后跨会话命中(重复问题0花费)
_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ai_cache.json")
_cache_dirty = 0
def _cache_load():
    global _cache
    try:
        if os.path.exists(_CACHE_FILE):
            _d = json.load(open(_CACHE_FILE, encoding="utf-8"))
            _cache = {k: (v["r"], v["t"]) for k, v in _d.items()}
    except Exception:
        _cache = {}
def _cache_save():
    try:
        _d = {k: {"r": v[0], "t": v[1]} for k, v in _cache.items()}
        _tmp = _CACHE_FILE + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as f:
            json.dump(_d, f, ensure_ascii=False)
        os.replace(_tmp, _CACHE_FILE)
    except Exception:
        pass
def _cache_put(ck, result):
    global _cache_dirty
    _cache[ck] = (result, time.time())
    _cache_dirty += 1
    if _cache_dirty >= 15:
        _cache_dirty = 0; _cache_save()
_cache_load()
import atexit as _atexit
_atexit.register(_cache_save)

import hashlib

_TOKEN_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_token_usage.jsonl")

def _log_token(provider, model, prompt_tokens, completion_tokens, task=""):
    try:
        import datetime
        entry = {"time": datetime.datetime.now().isoformat(), "provider": provider, "model": model,
                 "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                 "total_tokens": prompt_tokens + completion_tokens, "task": task}
        with open(_TOKEN_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except:
        pass

def token_stats(days=7):
    try:
        import datetime
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).isoformat()
        total = calls = 0
        by_provider = {}
        by_task = {}
        if os.path.exists(_TOKEN_LOG):
            with open(_TOKEN_LOG, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        e = json.loads(line.strip())
                        if e["time"] < cutoff: continue
                        calls += 1
                        total += e["total_tokens"]
                        by_provider[e["provider"]] = by_provider.get(e["provider"], 0) + e["total_tokens"]
                        t = e.get("task", "")
                        by_task[t] = by_task.get(t, 0) + e["total_tokens"]
                    except: continue
        return {"calls": calls, "total_tokens": total, "by_provider": by_provider, "by_task": by_task}
    except Exception as ex:
        return {"error": str(ex)}

def _cache_key(prompt, task, model):
    return hashlib.md5(f"{task}:{model}:{prompt[:500]}".encode()).hexdigest()


def _call_openai(pname, messages, max_tokens=2048, temperature=0.3, timeout=60):
    """调用OpenAI兼容接口"""
    p = PROVIDERS[pname]
    if not p["key"]:
        return None
    data = {
        "model": p["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {p['key']}", "Content-Type": "application/json"}
    for attempt in range(2):
        r = requests.post(p["url"], json=data, headers=headers,
                          proxies=p["proxy"], timeout=timeout)
        if r.status_code == 429 or r.status_code >= 500:
            if attempt == 0:
                time.sleep(2)
                continue
        if r.status_code != 200:
            print(f"[AI:{pname}] {r.status_code}: {r.text[:150]}", file=sys.stderr)
            return None
        resp = r.json()
        usage = resp.get("usage", {})
        if usage:
            _log_token(pname, p["model"], usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        return resp["choices"][0]["message"]["content"].strip()
    return None


def _call_gemini(messages, max_tokens=2048, temperature=0.3, timeout=60):
    """调用Gemini（非OpenAI格式）"""
    p = PROVIDERS["gemini"]
    if not p["key"]:
        return None
    url = p["url"].format(model=p["model"], key=p["key"])
    parts = [{"text": m["content"]} for m in messages]
    data = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    for attempt in range(2):
        r = requests.post(url, json=data, proxies=p["proxy"], timeout=timeout)
        if (r.status_code == 429 or r.status_code >= 500) and attempt == 0:
            time.sleep(2)
            continue
        if r.status_code != 200:
            print(f"[AI:gemini] {r.status_code}: {r.text[:150]}", file=sys.stderr)
            return None
        resp = r.json()
        candidates = resp.get("candidates", [])
        if not candidates:
            return None
        parts_out = candidates[0].get("content", {}).get("parts", [])
        return "".join(x.get("text", "") for x in parts_out if x.get("text")).strip()


def _call_pollinations(messages, max_tokens=2048, temperature=0.3, timeout=30):
    """调用Pollinations免费API（无key，有限流，作为兜底）"""
    p = PROVIDERS["pollinations"]
    data = {
        "messages": messages,
        "model": p["model"],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    r = requests.post(p["url"], json=data,
                      headers={"Content-Type": "application/json"},
                      proxies=p["proxy"], timeout=timeout)
    if r.status_code != 200:
        print(f"[AI:pollinations] {r.status_code}: {r.text[:100]}", file=sys.stderr)
        return None
    return r.text.strip()


def translate(text, source="auto", target="zh-CN"):
    """免费翻译（MyMemory API，无需key）"""
    try:
        r = requests.get("https://api.mymemory.translated.net/get",
                         params={"q": text[:500], "langpair": f"{source}|{target}"},
                         timeout=10)
        if r.status_code == 200:
            return r.json()["responseData"]["translatedText"]
    except Exception:
        pass
    # fallback到AI
    return chat(f"将以下文本翻译成{target}，只返回译文：\n{text[:2000]}", max_tokens=2048)


def _detect_lang(text):
    """简单语言检测"""
    zh = sum(1 for c in text[:200] if '\u4e00' <= c <= '\u9fff')
    return "zh" if zh > 10 else "en"


def chat(prompt, context="", provider=None, task="zh", model=None,
         max_tokens=None, temperature=0.3):
    """
    统一对话接口。
    provider: 指定provider名，None=自动路由
    task: zh/en/code/long
    返回文本或None
    """
    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": prompt})

    if max_tokens is None:  # 任务分级输出上限，简单任务不浪费
        max_tokens = {"zh": 512, "en": 700, "code": 4096, "long": 4096}.get(task, 512)

    if provider:
        chain = [provider]
    else:
        lang = _detect_lang(prompt + context)
        route_key = task if task in ROUTE else lang
        chain = ROUTE.get(route_key, ROUTE["zh"])

    # 缓存检查
    ck = _cache_key(prompt, route_key if not provider else provider, model or "")
    if ck in _cache:
        cached_resp, cached_time = _cache[ck]
        if time.time() - cached_time < CACHE_TTL:
            _stats["cache_hit"] += 1
            return cached_resp

    for pname in chain:
        # 冷却期跳过
        if pname in _cooldown and time.time() < _cooldown[pname]:
            continue
        p = PROVIDERS.get(pname)
        if not p or not p["key"]:
            continue
        try:
            t0 = time.time()
            if pname == "gemini":
                result = _call_gemini(messages, max_tokens, temperature)
            elif pname == "pollinations":
                result = _call_pollinations(messages, max_tokens, temperature)
            else:
                result = _call_openai(pname, messages, max_tokens, temperature)
            dt = time.time() - t0
            if result:
                _stats["calls"] += 1
                _stats["by_provider"][pname] = _stats["by_provider"].get(pname, 0) + 1
                _cache_put(ck, result)
                if os.environ.get("AI_DEBUG"):
                    print(f"[AI] {pname} 响应 {dt:.1f}s", file=sys.stderr)
                return result
            else:
                # 无结果，短冷却60秒
                _cooldown[pname] = time.time() + 60
        except Exception as e:
            _stats["errors"] += 1
            err = str(e)[:80]
            print(f"[AI:{pname}] 异常: {type(e).__name__}: {err}", file=sys.stderr)
            # 503/429冷却10分钟，其他60秒
            if "503" in err or "429" in err or "overloaded" in err.lower():
                _cooldown[pname] = time.time() + 600
            else:
                _cooldown[pname] = time.time() + 60
            continue
    return None


def summarize(text, instruction="总结要点", provider=None):
    """总结文本"""
    prompt = f"{instruction}，用中文，简洁要点式：\n\n{text}"
    _long = len(text) > 6000
    task = "long" if _long else "zh"
    return chat(prompt, provider=provider, task=task, max_tokens=2500 if _long else 1200, temperature=0.2)


def classify(text, categories, provider=None):
    """文本分类"""
    cats = "、".join(categories)
    prompt = f"将以下文本分类为[{cats}]中的一个，只返回类别名：\n\n{text[:2000]}"
    result = chat(prompt, provider=provider, max_tokens=20, temperature=0.0)
    if result:
        for c in categories:
            if c in result:
                return c
    return None


def extract(text, fields, provider=None):
    """提取字段返回JSON"""
    field_str = "、".join(fields)
    prompt = (f"从以下文本中提取{field_str}，以JSON格式返回，字段名用英文，"
              f"值用中文。找不到填null。只返回JSON：\n\n{text[:4000]}")
    result = chat(prompt, provider=provider, max_tokens=1024, temperature=0.0)
    if result:
        try:
            s = result.index("{")
            e = result.rindex("}") + 1
            return json.loads(result[s:e])
        except (ValueError, json.JSONDecodeError):
            return None
    return None


def stats():
    """返回使用统计"""
    return dict(_stats)


def code_helper(question, context="", max_tokens=4096):
    """代码问题求助其他AI（DeepSeek/Gemini），不占豆包token"""
    prompt = f"你是编程专家。{question}"
    if context:
        prompt += f"\n\n相关代码/错误信息:\n{context}"
    return chat(prompt, task="code", max_tokens=max_tokens, temperature=0.1)


def available_providers():
    """返回当前可用的provider列表"""
    return [name for name, p in PROVIDERS.items() if p["key"]]


if __name__ == "__main__":
    print("可用provider:", available_providers())
    print("测试...")
    r = chat("说OK", max_tokens=10)
    print(f"回复: {r}")
    print("统计:", stats())
