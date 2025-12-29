"""
验证模型列表脚本

用于验证 API 返回的模型列表是否与 configs/models.json 中的模型一致
"""

import requests
import json
import os
from pathlib import Path

# 配置
API_BASE_URL = "http://localhost:8000"
API_KEY = "sk-gemini"
MODELS_FILE = os.path.join(os.path.dirname(__file__), "configs", "models.json")

def load_models_from_file():
    """从 models.json 文件加载模型列表"""
    models_from_file = []
    if os.path.exists(MODELS_FILE):
        try:
            with open(MODELS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for model in data.get("models", []):
                    model_name = model.get("name", "")
                    # 去掉 "models/" 前缀
                    if model_name.startswith("models/"):
                        model_name = model_name[7:]
                    models_from_file.append({
                        "id": model_name,
                        "displayName": model.get("displayName", ""),
                        "version": model.get("version", ""),
                        "thinking": model.get("thinking", False)
                    })
        except Exception as e:
            print(f"❌ 读取 models.json 失败: {e}")
            return []
    return models_from_file

def get_models_from_api(format_type="openai"):
    """从 API 获取模型列表"""
    try:
        if format_type == "openai":
            url = f"{API_BASE_URL}/v1/models"
        else:
            url = f"{API_BASE_URL}/v1beta/models"
        
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if format_type == "openai":
                return [{"id": m.get("id", ""), "displayName": "", "version": "", "thinking": False} 
                       for m in data.get("data", [])]
            else:
                return [{"id": m.get("name", "").replace("models/", ""), 
                        "displayName": m.get("displayName", ""),
                        "version": m.get("version", ""),
                        "thinking": m.get("thinking", False)} 
                       for m in data.get("models", [])]
        else:
            print(f"❌ API 请求失败: HTTP {response.status_code}")
            print(f"响应: {response.text}")
            return []
    except Exception as e:
        print(f"❌ 获取 API 模型列表失败: {e}")
        return []

def compare_models(file_models, api_models, format_name, check_thinking=True):
    """对比模型列表
    
    Args:
        file_models: 文件中的模型列表
        api_models: API 返回的模型列表
        format_name: 格式名称（用于显示）
        check_thinking: 是否检查思考模式（OpenAI 格式不包含此字段）
    """
    file_model_ids = {m["id"] for m in file_models}
    api_model_ids = {m["id"] for m in api_models}
    
    # 只在文件中存在的模型
    only_in_file = file_model_ids - api_model_ids
    # 只在 API 中存在的模型
    only_in_api = api_model_ids - file_model_ids
    # 两者都存在的模型
    in_both = file_model_ids & api_model_ids
    
    print(f"\n{'='*60}")
    print(f"📋 {format_name} 格式模型对比")
    print(f"{'='*60}")
    
    if not check_thinking:
        print(f"\n💡 注意: {format_name} 格式不包含思考模式字段，将跳过该字段的对比")
    
    print(f"\n✅ 两者都存在的模型 ({len(in_both)} 个):")
    if in_both:
        for model_id in sorted(in_both):
            file_model = next((m for m in file_models if m["id"] == model_id), None)
            api_model = next((m for m in api_models if m["id"] == model_id), None)
            if file_model and api_model:
                # 检查详细信息是否一致
                details_match = []
                if file_model.get("displayName") and api_model.get("displayName"):
                    if file_model["displayName"] != api_model["displayName"]:
                        details_match.append(f"显示名称不一致: 文件={file_model['displayName']}, API={api_model['displayName']}")
                if file_model.get("version") and api_model.get("version"):
                    if file_model["version"] != api_model["version"]:
                        details_match.append(f"版本不一致: 文件={file_model['version']}, API={api_model['version']}")
                # 只有 Gemini 原生格式才检查思考模式
                if check_thinking and file_model.get("thinking") != api_model.get("thinking"):
                    details_match.append(f"思考模式不一致: 文件={file_model['thinking']}, API={api_model['thinking']}")
                
                if details_match:
                    print(f"  ⚠️  {model_id}")
                    for detail in details_match:
                        print(f"     - {detail}")
                else:
                    print(f"  ✅ {model_id}")
    else:
        print("  (无)")
    
    if only_in_file:
        print(f"\n⚠️  只在文件中存在的模型 ({len(only_in_file)} 个):")
        for model_id in sorted(only_in_file):
            file_model = next((m for m in file_models if m["id"] == model_id), None)
            display_name = file_model.get("displayName", "") if file_model else ""
            print(f"  - {model_id}" + (f" ({display_name})" if display_name else ""))
    
    if only_in_api:
        print(f"\n⚠️  只在 API 中存在的模型 ({len(only_in_api)} 个):")
        for model_id in sorted(only_in_api):
            api_model = next((m for m in api_models if m["id"] == model_id), None)
            display_name = api_model.get("displayName", "") if api_model else ""
            print(f"  - {model_id}" + (f" ({display_name})" if display_name else ""))
    
    # 总结
    print(f"\n📊 对比结果:")
    print(f"  - 文件中的模型数: {len(file_models)}")
    print(f"  - API 中的模型数: {len(api_models)}")
    print(f"  - 两者都存在的: {len(in_both)}")
    print(f"  - 只在文件中的: {len(only_in_file)}")
    print(f"  - 只在 API 中的: {len(only_in_api)}")
    
    if not only_in_file and not only_in_api:
        print(f"\n✅ 模型列表完全一致！")
        return True
    else:
        print(f"\n⚠️  模型列表存在差异，请检查上述信息")
        return False

def main():
    """主函数"""
    print("="*60)
    print("模型列表验证工具")
    print("="*60)
    print(f"\nAPI 地址: {API_BASE_URL}")
    print(f"模型文件: {MODELS_FILE}")
    
    # 检查文件是否存在
    if not os.path.exists(MODELS_FILE):
        print(f"\n❌ 模型文件不存在: {MODELS_FILE}")
        return
    
    # 从文件加载模型
    print(f"\n📖 从文件加载模型列表...")
    file_models = load_models_from_file()
    if not file_models:
        print("❌ 无法从文件加载模型列表")
        return
    
    print(f"✅ 从文件加载了 {len(file_models)} 个模型")
    
    # 从 API 获取模型（OpenAI 格式）
    print(f"\n🌐 从 API 获取模型列表 (OpenAI 格式)...")
    openai_models = get_models_from_api("openai")
    if not openai_models:
        print("❌ 无法从 API 获取模型列表")
        return
    
    print(f"✅ 从 API 获取了 {len(openai_models)} 个模型")
    
    # 从 API 获取模型（Gemini 原生格式）
    print(f"\n🌐 从 API 获取模型列表 (Gemini 原生格式)...")
    gemini_models = get_models_from_api("gemini")
    if not gemini_models:
        print("⚠️  无法从 API 获取 Gemini 格式模型列表（可能不支持）")
    else:
        print(f"✅ 从 API 获取了 {len(gemini_models)} 个模型")
    
    # 对比模型
    print(f"\n{'='*60}")
    print("开始对比模型列表...")
    print(f"{'='*60}")
    
    # 对比 OpenAI 格式（不检查思考模式，因为 OpenAI 格式不包含此字段）
    openai_match = compare_models(file_models, openai_models, "OpenAI", check_thinking=False)
    
    # 对比 Gemini 原生格式（如果有，检查思考模式）
    if gemini_models:
        print()
        gemini_match = compare_models(file_models, gemini_models, "Gemini 原生", check_thinking=True)
    
    # 显示文件中的模型详情
    print(f"\n{'='*60}")
    print("📋 文件中的模型详情")
    print(f"{'='*60}")
    for model in sorted(file_models, key=lambda x: x["id"]):
        thinking_str = "✅" if model.get("thinking") else "❌"
        print(f"  - {model['id']}")
        if model.get("displayName"):
            print(f"    显示名称: {model['displayName']}")
        if model.get("version"):
            print(f"    版本: {model['version']}")
        print(f"    思考模式: {thinking_str}")
    
    print(f"\n{'='*60}")
    print("验证完成！")
    print(f"{'='*60}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

