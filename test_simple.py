"""
简单的功能测试脚本
用于快速验证基本功能是否正常
"""

import requests
import json

BASE_URL = "http://localhost:8000"
API_KEY = "sk-gemini"

def test_basic():
    """基本功能测试"""
    print("="*60)
    print("简单功能测试")
    print("="*60)
    
    # 测试 1: 模型列表
    print("\n[测试 1] 获取模型列表...")
    try:
        resp = requests.get(
            f"{BASE_URL}/v1/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ 成功！找到 {len(data.get('data', []))} 个模型")
        else:
            print(f"❌ 失败！状态码: {resp.status_code}")
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试 2: 简单对话
    print("\n[测试 2] 简单对话...")
    try:
        resp = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "gemini-3.0-flash",
                "messages": [{"role": "user", "content": "说'你好'"}],
                "stream": False
            },
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                print(f"✅ 成功！响应: {content[:50]}...")
            else:
                print(f"❌ 响应格式异常: {data}")
        else:
            print(f"❌ 失败！状态码: {resp.status_code}, 响应: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    # 测试 3: Gemini 原生 API
    print("\n[测试 3] Gemini 原生 API...")
    try:
        resp = requests.post(
            f"{BASE_URL}/v1beta/models/gemini-3.0-flash:generateContent",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "contents": [{
                    "role": "user",
                    "parts": [{"text": "说'测试成功'"}]
                }]
            },
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    text = candidate["content"]["parts"][0].get("text", "")
                    print(f"✅ 成功！响应: {text[:50]}...")
            else:
                print(f"❌ 响应格式异常: {data}")
        else:
            print(f"❌ 失败！状态码: {resp.status_code}, 响应: {resp.text[:200]}")
    except Exception as e:
        print(f"❌ 错误: {e}")
    
    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)

if __name__ == "__main__":
    test_basic()



