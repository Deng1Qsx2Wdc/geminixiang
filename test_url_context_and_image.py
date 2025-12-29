"""
测试 URL 上下文和图片生成功能
1. URL 上下文支持
2. 图片生成支持
"""

import requests
import json
import time
import sys

# 配置
BASE_URL = "http://localhost:8000"
API_KEY = "sk-gemini"

def test_url_context_openai():
    """测试 OpenAI 格式的 URL 上下文"""
    print("\n" + "="*60)
    print("测试 1: OpenAI 格式 - URL 上下文")
    print("="*60)
    
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gemini-3.0-flash",
            "messages": [
                {"role": "user", "content": "总结这个网页的内容: https://www.python.org"}
            ],
            "tools": [
                {"urlContext": {}}
            ],
            "stream": False
        },
        timeout=60
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            print(f"✅ 成功！响应长度: {len(content)} 字符")
            print(f"响应预览: {content[:200]}...")
        else:
            print(f"❌ 响应格式异常: {data}")
    else:
        print(f"❌ 失败！状态码: {response.status_code}")
        print(f"响应: {response.text[:500]}")


def test_url_context_gemini_native():
    """测试 Gemini 原生格式的 URL 上下文"""
    print("\n" + "="*60)
    print("测试 2: Gemini 原生格式 - URL 上下文")
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
                        {"text": "总结这个网页的内容: https://www.python.org"}
                    ]
                }
            ],
            "tools": [
                {"urlContext": {}}
            ]
        },
        timeout=60
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                for part in candidate["content"]["parts"]:
                    if "text" in part:
                        text = part["text"]
                        print(f"✅ 成功！响应长度: {len(text)} 字符")
                        print(f"响应预览: {text[:200]}...")
        else:
            print(f"❌ 响应格式异常: {data}")
    else:
        print(f"❌ 失败！状态码: {response.status_code}")
        print(f"响应: {response.text[:500]}")


def test_image_generation_openai():
    """测试 OpenAI 格式的图片生成"""
    print("\n" + "="*60)
    print("测试 3: OpenAI 格式 - 图片生成")
    print("="*60)
    print("注意: 图片生成可能需要较长时间（20-30秒）")
    
    # 检查是否有图片生成模型
    models_resp = requests.get(
        f"{BASE_URL}/v1/models",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    
    if models_resp.status_code == 200:
        models_data = models_resp.json()
        image_models = [m for m in models_data.get("data", []) if "-image" in m.get("id", "").lower()]
        if not image_models:
            print("⚠️  未找到图片生成模型，跳过测试")
            return
        
        model_id = image_models[0].get("id")
        print(f"使用模型: {model_id}")
    else:
        print("⚠️  无法获取模型列表，使用默认模型")
        model_id = "gemini-2.5-flash-image"
    
    print("发送图片生成请求...")
    response = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": model_id,
            "messages": [
                {"role": "user", "content": "生成一只可爱的小猫"}
            ],
            "stream": False
        },
        timeout=120  # 图片生成需要更长时间
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"]["content"]
            print(f"✅ 成功！响应长度: {len(content)} 字符")
            
            # 检查是否包含图片 Markdown
            if "![Generated Image]" in content:
                print("✅ 检测到图片 Markdown 格式")
                # 提取图片信息
                import re
                image_pattern = r'!\[Generated Image\]\(data:([^;]+);base64,([^\)]+)\)'
                matches = re.findall(image_pattern, content)
                if matches:
                    print(f"✅ 找到 {len(matches)} 张图片")
                    for i, (mime_type, base64_data) in enumerate(matches):
                        print(f"  图片 {i+1}: MIME类型={mime_type}, Base64长度={len(base64_data)}")
            else:
                print("⚠️  响应中未检测到图片格式")
                print(f"响应预览: {content[:300]}...")
        else:
            print(f"❌ 响应格式异常: {data}")
    else:
        print(f"❌ 失败！状态码: {response.status_code}")
        print(f"响应: {response.text[:500]}")


def test_image_generation_gemini_native():
    """测试 Gemini 原生格式的图片生成"""
    print("\n" + "="*60)
    print("测试 4: Gemini 原生格式 - 图片生成")
    print("="*60)
    print("注意: 图片生成可能需要较长时间（20-30秒）")
    
    # 检查是否有图片生成模型
    models_resp = requests.get(
        f"{BASE_URL}/v1beta/models",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    
    if models_resp.status_code == 200:
        models_data = models_resp.json()
        image_models = [m for m in models_data.get("models", []) if "-image" in m.get("name", "").lower()]
        if not image_models:
            print("⚠️  未找到图片生成模型，跳过测试")
            return
        
        model_name = image_models[0].get("name", "").replace("models/", "")
        print(f"使用模型: {model_name}")
    else:
        print("⚠️  无法获取模型列表，使用默认模型")
        model_name = "gemini-2.5-flash-image"
    
    print("发送图片生成请求...")
    response = requests.post(
        f"{BASE_URL}/v1beta/models/{model_name}:generateContent",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "生成一只可爱的小猫"}
                    ]
                }
            ]
        },
        timeout=120  # 图片生成需要更长时间
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            candidate = data["candidates"][0]
            if "content" in candidate and "parts" in candidate["content"]:
                parts = candidate["content"]["parts"]
                print(f"✅ 成功！找到 {len(parts)} 个部分")
                
                has_image = False
                for i, part in enumerate(parts):
                    if "text" in part:
                        text_content = part["text"]
                        # 检查文本中是否包含图片 URL
                        if "googleusercontent.com" in text_content or "image_generation" in text_content:
                            has_image = True
                            print(f"  部分 {i+1}: 图片 URL")
                            print(f"    URL: {text_content[:100]}...")
                            print(f"    ✅ 检测到图片 URL（服务器会尝试下载并转换为 base64）")
                        else:
                            print(f"  部分 {i+1}: 文本 (长度: {len(text_content)} 字符)")
                            if text_content[:100]:
                                print(f"    预览: {text_content[:100]}...")
                    elif "inlineData" in part:
                        has_image = True
                        inline_data = part["inlineData"]
                        mime_type = inline_data.get("mimeType", "unknown")
                        data_length = len(inline_data.get("data", ""))
                        print(f"  部分 {i+1}: 图片 (Base64)")
                        print(f"    MIME类型: {mime_type}")
                        print(f"    Base64数据长度: {data_length} 字符")
                        print(f"    ✅ 图片数据格式正确")
                
                if not has_image:
                    print("⚠️  响应中未检测到图片数据")
        else:
            print(f"❌ 响应格式异常: {data}")
    else:
        print(f"❌ 失败！状态码: {response.status_code}")
        print(f"响应: {response.text[:500]}")


def test_image_generation_streaming():
    """测试图片生成的流式响应"""
    print("\n" + "="*60)
    print("测试 5: 图片生成 - 流式响应")
    print("="*60)
    print("注意: 图片生成可能需要较长时间（20-30秒）")
    
    # 检查是否有图片生成模型
    models_resp = requests.get(
        f"{BASE_URL}/v1beta/models",
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    
    if models_resp.status_code == 200:
        models_data = models_resp.json()
        image_models = [m for m in models_data.get("models", []) if "-image" in m.get("name", "").lower()]
        if not image_models:
            print("⚠️  未找到图片生成模型，跳过测试")
            return
        
        model_name = image_models[0].get("name", "").replace("models/", "")
        print(f"使用模型: {model_name}")
    else:
        print("⚠️  无法获取模型列表，使用默认模型")
        model_name = "gemini-2.5-flash-image"
    
    print("发送流式图片生成请求...")
    response = requests.post(
        f"{BASE_URL}/v1beta/models/{model_name}:streamGenerateContent?alt=sse",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "生成一只可爱的小猫"}
                    ]
                }
            ]
        },
        stream=True,
        timeout=120
    )
    
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print("流式响应内容:")
        has_image = False
        text_parts = []
        
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
                                        text = part["text"]
                                        # 检查文本中是否包含图片 URL
                                        if "googleusercontent.com" in text or "image_generation" in text:
                                            has_image = True
                                            print(f"\n✅ 检测到图片 URL: {text[:80]}...")
                                        else:
                                            print(text, end="", flush=True)
                                            text_parts.append(text)
                                    elif "inlineData" in part:
                                        has_image = True
                                        inline_data = part["inlineData"]
                                        print(f"\n✅ 检测到图片数据 (Base64): MIME类型={inline_data.get('mimeType')}, 数据长度={len(inline_data.get('data', ''))}")
                    except:
                        pass
        
        print()
        if has_image:
            print("✅ 流式响应中成功检测到图片")
        else:
            print("⚠️  流式响应中未检测到图片数据")
    else:
        print(f"❌ 失败！状态码: {response.status_code}")
        print(f"响应: {response.text[:500]}")


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始测试 URL 上下文和图片生成功能")
    print("="*60)
    print(f"API 地址: {BASE_URL}")
    print(f"API Key: {API_KEY}")
    print("\n提示:")
    print("1. 确保服务器正在运行: python server.py")
    print("2. 确保已配置 Token 和 Cookie")
    print("3. URL 上下文测试需要网络连接")
    print("4. 图片生成测试可能需要较长时间")
    
    try:
        # 测试 URL 上下文
        test_url_context_openai()
        time.sleep(2)
        
        test_url_context_gemini_native()
        time.sleep(2)
        
        # 测试图片生成
        test_image_generation_openai()
        time.sleep(2)
        
        test_image_generation_gemini_native()
        time.sleep(2)
        
        test_image_generation_streaming()
        
        print("\n" + "="*60)
        print("所有测试完成！")
        print("="*60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ 错误: 无法连接到服务器")
        print("请确保服务器正在运行: python server.py")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

