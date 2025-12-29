"""
测试新整合的功能
1. 流式响应（真流式/假流式）
2. Gemini 原生 API
3. 模型列表
"""

import requests
import json
import os
import time
import sys

# 配置
BASE_URL = "http://localhost:8000"
API_KEY = "sk-gemini"

def test_list_models():
    """测试模型列表 API"""
    print("\n" + "="*60)
    print("测试 1: 列出模型 (OpenAI 格式)")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/v1/models",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"模型数量: {len(data.get('data', []))}")
        for model in data.get('data', [])[:5]:  # 只显示前5个
            print(f"  - {model.get('id')}")
    else:
        print(f"错误: {response.text}")
    
    print("\n" + "="*60)
    print("测试 2: 列出模型 (Gemini 原生格式)")
    print("="*60)
    
    response = requests.get(
        f"{BASE_URL}/v1beta/models",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"模型数量: {len(data.get('models', []))}")
        for model in data.get('models', [])[:5]:  # 只显示前5个
            print(f"  - {model.get('name')} ({model.get('displayName')})")
    else:
        print(f"错误: {response.text}")


def test_openai_chat_streaming(stream_mode="real"):
    """测试 OpenAI 格式的流式响应"""
    print("\n" + "="*60)
    print(f"测试 3: OpenAI 格式流式响应 (模式: {stream_mode})")
    print("="*60)
    print(f"注意: 流式模式需要在服务器启动时设置环境变量 STREAMING_MODE={stream_mode}")
    print("当前测试将使用服务器默认配置")
    
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gemini-3.0-flash",
            "messages": [
                {"role": "user", "content": "用一句话介绍 Python 编程语言"}
            ],
            "stream": True
        },
        stream=True
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print("流式响应内容:")
        full_content = ""
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        print("\n[流式响应结束]")
                        break
                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                content = delta["content"]
                                print(content, end="", flush=True)
                                full_content += content
                    except:
                        pass
        print(f"\n\n完整内容长度: {len(full_content)} 字符")
    else:
        print(f"错误: {response.text}")


def test_gemini_native_api():
    """测试 Gemini 原生 API"""
    print("\n" + "="*60)
    print("测试 4: Gemini 原生 API - generateContent")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/v1beta/models/gemini-3.0-flash:generateContent",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "什么是人工智能？用一句话回答"}
                    ]
                }
            ]
        }
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        print(f"响应: {part['text']}")
        if "usageMetadata" in data:
            usage = data["usageMetadata"]
            print(f"Token 使用: {usage.get('totalTokenCount', 0)}")
    else:
        print(f"错误: {response.text}")


def test_gemini_streaming():
    """测试 Gemini 原生 API 流式响应"""
    print("\n" + "="*60)
    print("测试 5: Gemini 原生 API - streamGenerateContent")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/v1beta/models/gemini-3.0-flash:streamGenerateContent?alt=sse",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "数数从1到10，每个数字一行"}
                    ]
                }
            ]
        },
        stream=True
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print("流式响应内容:")
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        print("\n[流式响应结束]")
                        break
                    try:
                        data = json.loads(data_str)
                        if "candidates" in data and len(data["candidates"]) > 0:
                            candidate = data["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                for part in candidate["content"]["parts"]:
                                    if "text" in part:
                                        print(part["text"], end="", flush=True)
                    except:
                        pass
        print()
    else:
        print(f"错误: {response.text}")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始测试新整合的功能")
    print("="*60)
    print(f"API 地址: {BASE_URL}")
    print(f"API Key: {API_KEY}")
    
    try:
        # 测试模型列表
        test_list_models()
        
        # 测试 OpenAI 格式流式响应（真流式）
        test_openai_chat_streaming("real")
        time.sleep(2)
        
        # 测试 OpenAI 格式流式响应（假流式）
        test_openai_chat_streaming("fake")
        time.sleep(2)
        
        # 测试 Gemini 原生 API
        test_gemini_native_api()
        time.sleep(2)
        
        # 测试 Gemini 原生 API 流式
        test_gemini_streaming()
        
        print("\n" + "="*60)
        print("所有测试完成！")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n错误: 无法连接到服务器")
        print("请确保服务器正在运行: python server.py")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

