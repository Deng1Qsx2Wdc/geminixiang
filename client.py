"""
Gemini Web Reverse Engineering Client
支持图文请求、上下文对话，OpenAI 格式输入输出
手动配置 token，无需代码登录
"""

import re
import json
import random
import string
import base64
import uuid
import httpx
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import time


class CookieExpiredError(Exception):
    """Cookie 过期或无效异常"""
    pass


class ImageUploadError(Exception):
    """图片上传失败异常"""
    pass


@dataclass
class Message:
    """OpenAI 格式消息"""
    role: str
    content: Union[str, List[Dict[str, Any]]]


@dataclass
class ChatCompletionChoice:
    index: int
    message: Message
    finish_reason: str = "stop"


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class ChatCompletionResponse:
    """OpenAI 格式响应"""
    id: str
    object: str = "chat.completion"
    created: int = 0
    model: str = "gemini-web"
    choices: List[ChatCompletionChoice] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [
                {
                    "index": c.index,
                    "message": {"role": c.message.role, "content": c.message.content},
                    "finish_reason": c.finish_reason
                }
                for c in self.choices
            ],
            "usage": {
                "prompt_tokens": self.usage.prompt_tokens,
                "completion_tokens": self.usage.completion_tokens,
                "total_tokens": self.usage.total_tokens
            }
        }


class GeminiClient:
    """
    Gemini 网页版逆向客户端
    
    使用方法:
    1. 打开 https://gemini.google.com 并登录
    2. F12 打开开发者工具 -> Application -> Cookies
    3. 复制以下 cookie 值:
       - __Secure-1PSID
       - __Secure-1PSIDTS (可选)
    4. Network 标签 -> 找任意请求 -> 复制 SNlM0e 值 (在页面源码中搜索)
    """
    
    BASE_URL = "https://gemini.google.com"
    
    def __init__(
        self,
        secure_1psid: str,
        secure_1psidts: str = None,
        secure_1psidcc: str = None,
        snlm0e: str = None,
        bl: str = None,
        cookies_str: str = None,
        push_id: str = None,
        debug: bool = False,
    ):
        """
        初始化客户端 - 手动填写 token
        
        Args:
            secure_1psid: __Secure-1PSID cookie (必填)
            secure_1psidts: __Secure-1PSIDTS cookie (推荐)
            secure_1psidcc: __Secure-1PSIDCC cookie (推荐)
            snlm0e: SNlM0e token (必填，从页面源码获取)
            bl: BL 版本号 (可选，自动获取)
            cookies_str: 完整 cookie 字符串 (可选，替代单独设置)
            push_id: Push ID for image upload (必填用于图片上传)
            debug: 是否打印调试信息
        """
        self.secure_1psid = secure_1psid
        self.secure_1psidts = secure_1psidts
        self.secure_1psidcc = secure_1psidcc
        self.snlm0e = snlm0e
        self.bl = bl
        self.push_id = push_id
        self.debug = debug
        
        self.session = httpx.Client(
            timeout=1220.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        )
        
        # 设置 cookies
        if cookies_str:
            self._set_cookies_from_string(cookies_str)
        else:
            self.session.cookies.set("__Secure-1PSID", secure_1psid, domain=".google.com")
            if secure_1psidts:
                self.session.cookies.set("__Secure-1PSIDTS", secure_1psidts, domain=".google.com")
            if secure_1psidcc:
                self.session.cookies.set("__Secure-1PSIDCC", secure_1psidcc, domain=".google.com")
        
        # 会话上下文
        self.conversation_id: str = ""
        self.response_id: str = ""
        self.choice_id: str = ""
        self.request_count: int = 0
        
        # 消息历史
        self.messages: List[Message] = []
        
        # 消息历史限制（默认保留最近 50 轮对话，即 100 条消息）
        self.max_history_messages: int = 100
        
        # 验证必填参数
        if not self.snlm0e:
            raise ValueError(
                "SNlM0e 是必填参数！\n"
                "获取方法:\n"
                "1. 打开 https://gemini.google.com 并登录\n"
                "2. F12 -> 查看页面源代码 (Ctrl+U)\n"
                "3. 搜索 'SNlM0e' 找到类似: \"SNlM0e\":\"xxxxxx\"\n"
                "4. 复制引号内的值"
            )
        
        # 自动获取 bl
        if not self.bl:
            self._fetch_bl()
    
    def _set_cookies_from_string(self, cookies_str: str):
        """从完整 cookie 字符串解析"""
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                self.session.cookies.set(key.strip(), value.strip(), domain=".google.com")
    
    def _fetch_bl(self):
        """获取 BL 版本号"""
        try:
            resp = self.session.get(self.BASE_URL)
            match = re.search(r'"cfb2h":"([^"]+)"', resp.text)
            if match:
                self.bl = match.group(1)
            else:
                # 使用默认值
                self.bl = "boq_assistant-bard-web-server_20241209.00_p0"
            if self.debug:
                print(f"[DEBUG] BL: {self.bl}")
        except Exception as e:
            self.bl = "boq_assistant-bard-web-server_20241209.00_p0"
            if self.debug:
                print(f"[DEBUG] 获取 BL 失败，使用默认值: {e}")


    
    def _parse_content(self, content: Union[str, List[Dict]]) -> tuple:
        """解析 OpenAI 格式 content，返回 (text, images)"""
        if isinstance(content, str):
            return content, []
        
        text_parts = []
        images = []
        
        for item in content:
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
            elif item.get("type") == "image_url":
                # 支持两种格式: {"url": "..."} 或直接字符串
                image_url_data = item.get("image_url", {})
                if isinstance(image_url_data, str):
                    url = image_url_data
                else:
                    url = image_url_data.get("url", "")
                
                if not url:
                    continue
                    
                if url.startswith("data:"):
                    # base64 格式: data:image/png;base64,xxxxx
                    match = re.match(r'data:([^;]+);base64,(.+)', url)
                    if match:
                        images.append({"mime_type": match.group(1), "data": match.group(2)})
                elif url.startswith("http://") or url.startswith("https://"):
                    # URL 格式，下载图片
                    try:
                        resp = httpx.get(url, timeout=30)
                        if resp.status_code == 200:
                            mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                            images.append({"mime_type": mime, "data": base64.b64encode(resp.content).decode()})
                    except Exception as e:
                        if self.debug:
                            print(f"[DEBUG] 下载图片失败: {e}")
                else:
                    # 可能是纯 base64 字符串 (没有 data: 前缀)
                    try:
                        # 尝试解码验证是否是有效 base64
                        base64.b64decode(url[:100])  # 只验证前100字符
                        images.append({"mime_type": "image/png", "data": url})
                    except:
                        pass
        
        return " ".join(text_parts) if text_parts else "", images
    
    def _upload_image(self, image_data: bytes, mime_type: str = "image/jpeg") -> str:
        """
        上传图片到 Gemini 服务器
        
        Args:
            image_data: 图片二进制数据
            mime_type: 图片 MIME 类型
            
        Returns:
            str: 上传后的图片路径（带 token）
        """
        if not self.push_id:
            raise CookieExpiredError(
                "图片上传需要 push_id\n"
                "获取方法: 运行 python get_push_id.py 或从浏览器 Network 中获取"
            )
        
        try:
            upload_url = "https://push.clients6.google.com/upload/"
            filename = f"image_{random.randint(100000, 999999)}.png"
            
            # 浏览器必需的头
            browser_headers = {
                "accept": "*/*",
                "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
                "origin": "https://gemini.google.com",
                "referer": "https://gemini.google.com/",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "x-browser-channel": "stable",
                "x-browser-copyright": "Copyright 2025 Google LLC. All Rights reserved.",
                "x-browser-validation": "Aj9fzfu+SaGLBY9Oqr3S7RokOtM=",
                "x-browser-year": "2025",
                "x-client-data": "CIa2yQEIpbbJAQipncoBCNvaygEIk6HLAQiFoM0BCJaMzwEIkZHPAQiSpM8BGOyFzwEYsobPAQ==",
            }
            
            # 第一步：获取 upload_id
            init_headers = {
                **browser_headers,
                "content-type": "application/x-www-form-urlencoded;charset=utf-8",
                "push-id": self.push_id,
                "x-goog-upload-command": "start",
                "x-goog-upload-header-content-length": str(len(image_data)),
                "x-goog-upload-protocol": "resumable",
                "x-tenant-id": "bard-storage",
            }
            
            init_resp = self.session.post(upload_url, data={"File name": filename}, headers=init_headers)
            
            if self.debug:
                print(f"[DEBUG] 初始化上传状态: {init_resp.status_code}")
            
            # 检查初始化响应状态
            if init_resp.status_code == 401 or init_resp.status_code == 403:
                raise CookieExpiredError(
                    f"Cookie 已过期或无效 (HTTP {init_resp.status_code})\n"
                    "请重新获取以下信息:\n"
                    "1. __Secure-1PSID\n"
                    "2. __Secure-1PSIDTS\n"
                    "3. SNlM0e\n"
                    "4. push_id"
                )
            
            upload_id = init_resp.headers.get("x-guploader-uploadid")
            if not upload_id:
                raise CookieExpiredError(
                    f"未获取到 upload_id (状态码: {init_resp.status_code})\n"
                    "可能原因: Cookie 已过期，请重新获取所有 token"
                )
            
            if self.debug:
                print(f"[DEBUG] Upload ID: {upload_id[:50]}...")
            
            # 第二步：上传图片数据
            final_upload_url = f"{upload_url}?upload_id={upload_id}&upload_protocol=resumable"
            
            upload_headers = {
                **browser_headers,
                "content-type": "application/x-www-form-urlencoded;charset=utf-8",
                "push-id": self.push_id,
                "x-goog-upload-command": "upload, finalize",
                "x-goog-upload-offset": "0",
                "x-tenant-id": "bard-storage",
                "x-client-pctx": "CgcSBWjK7pYx",
            }
            
            upload_resp = self.session.post(
                final_upload_url,
                headers=upload_headers,
                content=image_data
            )
            
            if self.debug:
                print(f"[DEBUG] 上传数据状态: {upload_resp.status_code}")
                print(f"[DEBUG] 响应头: {dict(upload_resp.headers)}")
                print(f"[DEBUG] 响应内容完整: {upload_resp.text}")
            
            # 检查上传响应状态
            if upload_resp.status_code == 401 or upload_resp.status_code == 403:
                raise CookieExpiredError(
                    f"上传图片认证失败 (HTTP {upload_resp.status_code})\n"
                    "Cookie 已过期，请重新获取"
                )
            
            if upload_resp.status_code != 200:
                raise Exception(f"上传图片数据失败: {upload_resp.status_code}, 响应: {upload_resp.text[:200] if upload_resp.text else '(empty)'}")
            
            # 从响应中提取图片路径
            response_text = upload_resp.text
            image_path = None
            
            # 尝试解析 JSON
            try:
                response_json = json.loads(response_text)
                image_path = self._extract_image_path(response_json)
            except json.JSONDecodeError:
                # 如果不是 JSON，尝试从文本中提取路径
                match = re.search(r'/contrib_service/[^\s"\']+', response_text)
                if match:
                    image_path = match.group(0)
            
            # 验证图片路径完整性
            if not image_path:
                raise CookieExpiredError(
                    f"无法从响应中提取图片路径\n"
                    f"响应内容: {response_text[:300]}\n"
                    "可能原因: Cookie 已过期，请重新获取所有 token"
                )
            
            # 检查路径是否有效（长度足够即可，新版可能不带查询参数）
            if "/contrib_service/" in image_path:
                # 路径长度至少要有一定长度才是有效的
                if len(image_path) < 40:
                    raise CookieExpiredError(
                        f"图片路径不完整\n"
                        f"返回路径: {image_path}\n"
                        "原因: Cookie 已过期或权限不足\n"
                        "解决方法:\n"
                        "1. 重新登录 https://gemini.google.com\n"
                        "2. 更新 config.py 中的所有 token:\n"
                        "   - SECURE_1PSID\n"
                        "   - SECURE_1PSIDTS\n"
                        "   - SNLM0E\n"
                        "   - PUSH_ID"
                    )
            
            if self.debug:
                print(f"[DEBUG] 图片路径: {image_path}")
            
            return image_path
            
        except CookieExpiredError:
            raise
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] 上传失败: {e}")
            raise Exception(f"图片上传失败: {e}")
    
    def _extract_image_path(self, data: Any) -> str:
        """从响应数据中递归提取图片路径"""
        if isinstance(data, str):
            if data.startswith("/contrib_service/"):
                return data
        elif isinstance(data, dict):
            for value in data.values():
                result = self._extract_image_path(value)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._extract_image_path(item)
                if result:
                    return result
        return None
    
    def _build_request_data(self, text: str, images: List[Dict] = None, image_paths: List[str] = None, model: str = None) -> str:
        """构建请求数据 - 基于真实请求格式"""
        # 会话上下文 (空字符串表示新对话)
        conv_id = self.conversation_id or ""
        resp_id = self.response_id or ""
        choice_id = self.choice_id or ""
        
        # 处理图片数据 - 格式: [[[path, 1, null, mime_type], filename]]
        image_data = None
        if image_paths and len(image_paths) > 0:
            path = image_paths[0]
            mime_type = images[0]["mime_type"] if images else "image/png"
            filename = f"image_{random.randint(100000, 999999)}.png"
            # 构建图片数组结构
            image_data = [[[path, 1, None, mime_type], filename]]
        
        # 生成唯一会话 ID
        session_id = str(uuid.uuid4()).upper()
        timestamp = int(time.time() * 1000)
        
        # 构建内部 JSON 数组 (基于真实请求格式)
        # 第一个元素: [text, 0, null, image_data, null, null, 0]
        inner_data = [
            [text, 0, None, image_data, None, None, 0],
            ["zh-CN"],
            [conv_id, resp_id, choice_id, None, None, None, None, None, None, ""],
            self.snlm0e,
            None,  # 之前是 "test123"，改为 null
            None,
            [1],
            1,
            None,
            None,
            1,
            0,
            None,
            None,
            None,
            None,
            None,
            [[0]],  # 模型相关字段，暂时使用 0
            0,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            1,
            None,
            None,
            [4],
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            [1],
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            0,
            None,
            None,
            None,
            None,
            None,
            session_id,
            None,
            [],
            None,
            None,
            None,
            None,
            [timestamp // 1000, (timestamp % 1000) * 1000000]
        ]
        
        # 序列化为 JSON 字符串
        inner_json = json.dumps(inner_data, ensure_ascii=False, separators=(',', ':'))
        
        # 外层包装
        outer_data = [None, inner_json]
        f_req_value = json.dumps(outer_data, ensure_ascii=False, separators=(',', ':'))
        
        return f_req_value

    
    def _parse_response(self, response_text: str) -> str:
        """解析响应文本 - 支持引用内容版本"""
        try:
            # 跳过前缀并按行解析
            lines = response_text.split("\n")
            final_text = ""
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith(")]}'"):
                    continue
                
                # 跳过数字行（长度标记）
                if line.isdigit():
                    continue
                
                try:
                    data = json.loads(line)
                    # data 是一个嵌套数组，data[0] 才是真正的数据
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                        actual_data = data[0]
                        # 检查是否是 wrb.fr 响应
                        if len(actual_data) >= 3 and actual_data[0] == "wrb.fr":
                            # 处理引用内容状态：[[\"wrb.fr\",null,null,null,null,[9]]]
                            if len(actual_data) >= 6 and actual_data[5] and isinstance(actual_data[5], list):
                                # 这是引用内容状态，跳过
                                continue
                            
                            if actual_data[2]:
                                inner_json = json.loads(actual_data[2])
                                
                                # 更新会话上下文（即使没有文本内容）
                                if len(inner_json) > 1 and inner_json[1]:
                                    if isinstance(inner_json[1], list):
                                        if len(inner_json[1]) > 0:
                                            self.conversation_id = inner_json[1][0] or self.conversation_id
                                        if len(inner_json[1]) > 1:
                                            self.response_id = inner_json[1][1] or self.response_id
                                
                                # 提取文本内容
                                if inner_json and len(inner_json) > 4 and inner_json[4]:
                                    candidates = inner_json[4]
                                    if candidates and len(candidates) > 0:
                                        candidate = candidates[0]
                                        if candidate and len(candidate) > 1 and candidate[1]:
                                            # candidate[1] 可能是数组或字符串
                                            content_parts = candidate[1]
                                            
                                            # 处理不同的内容格式（支持引用内容）
                                            text = ""
                                            if isinstance(content_parts, list):
                                                # 遍历所有内容部分，提取文本
                                                for part in content_parts:
                                                    if isinstance(part, str):
                                                        text += part
                                                    elif isinstance(part, dict):
                                                        # 处理带格式的内容（如引用、链接等）
                                                        if "text" in part:
                                                            text += part["text"]
                                                        elif "content" in part:
                                                            text += str(part["content"])
                                                        elif "parts" in part:
                                                            # 处理 parts 数组（可能包含引用内容）
                                                            for subpart in part.get("parts", []):
                                                                if isinstance(subpart, str):
                                                                    text += subpart
                                                                elif isinstance(subpart, dict):
                                                                    if "text" in subpart:
                                                                        text += subpart["text"]
                                                                    elif "inlineData" in subpart:
                                                                        # 跳过图片数据
                                                                        continue
                                                                    elif "functionCall" in subpart:
                                                                        # 跳过函数调用
                                                                        continue
                                                        elif "inlineData" in part:
                                                            # 跳过图片数据
                                                            continue
                                                        elif "functionCall" in part:
                                                            # 跳过函数调用
                                                            continue
                                                        else:
                                                            # 尝试提取所有可能的文本字段
                                                            for key in ["text", "content", "value"]:
                                                                if key in part:
                                                                    text += str(part[key])
                                                                    break
                                                    else:
                                                        text += str(part)
                                            elif isinstance(content_parts, str):
                                                text = content_parts
                                            else:
                                                text = str(content_parts)
                                            
                                            if isinstance(text, str) and len(text.strip()) > 0:
                                                # 如果新文本更长，或者当前文本为空，则更新
                                                if len(text) > len(final_text) or not final_text:
                                                    final_text = text
                                                    if len(candidate) > 0:
                                                        self.choice_id = candidate[0] or self.choice_id
                except Exception as e:
                    if self.debug:
                        import traceback
                        print(f"[DEBUG] 解析行错误: {e}")
                        print(f"[DEBUG] 行内容: {line[:200]}")
                        print(f"[DEBUG] 错误详情: {traceback.format_exc()}")
                    continue
            
            if final_text and final_text.strip():
                return final_text.strip()
                
        except Exception as e:
            if self.debug:
                import traceback
                print(f"[DEBUG] 解析错误: {e}")
                print(f"[DEBUG] 响应内容前1000字符: {response_text[:1000]}")
                print(f"[DEBUG] 错误详情: {traceback.format_exc()}")
                # 保存完整响应用于调试
                try:
                    with open("debug_response_failed.txt", "w", encoding="utf-8") as f:
                        f.write(response_text)
                    print(f"[DEBUG] 完整响应已保存到 debug_response_failed.txt")
                except:
                    pass
        
        return "无法解析响应"

    
    def _extract_text(self, parsed_data: list) -> str:
        """从解析后的数据中提取文本"""
        try:
            # 更新会话上下文
            if parsed_data and len(parsed_data) > 1:
                if parsed_data[1] and len(parsed_data[1]) > 0:
                    self.conversation_id = parsed_data[1][0] or self.conversation_id
                if parsed_data[1] and len(parsed_data[1]) > 1:
                    self.response_id = parsed_data[1][1] or self.response_id
            
            # 提取候选回复
            if parsed_data and len(parsed_data) > 4 and parsed_data[4]:
                candidates = parsed_data[4]
                if candidates and len(candidates) > 0:
                    first_candidate = candidates[0]
                    if first_candidate and len(first_candidate) > 1:
                        self.choice_id = first_candidate[0] or self.choice_id
                        content_parts = first_candidate[1]
                        if content_parts and len(content_parts) > 0:
                            return content_parts[0] if isinstance(content_parts[0], str) else str(content_parts[0])
            
            # 备用提取
            if parsed_data and len(parsed_data) > 0:
                def find_text(obj, depth=0):
                    if depth > 10:
                        return None
                    if isinstance(obj, str) and len(obj) > 50:
                        return obj
                    if isinstance(obj, list):
                        for item in obj:
                            result = find_text(item, depth + 1)
                            if result:
                                return result
                    return None
                
                text = find_text(parsed_data)
                if text:
                    return text
                    
        except Exception as e:
            pass
        
        return "无法提取回复内容"
    
    def chat(
        self,
        messages: List[Dict[str, Any]] = None,
        message: str = None,
        image: bytes = None,
        image_url: str = None,
        reset_context: bool = False,
        model: str = None
    ) -> ChatCompletionResponse:
        """
        发送聊天请求 (OpenAI 兼容格式)
        
        Args:
            messages: OpenAI 格式消息列表
            message: 简单文本消息 (与 messages 二选一)
            image: 图片二进制数据
            image_url: 图片 URL
            reset_context: 是否重置上下文
            model: 模型名称 (gemini-3.0-flash/gemini-3.0-flash-thinking/gemini-3.0-pro)
        
        Returns:
            ChatCompletionResponse: OpenAI 格式响应
        """
        if reset_context:
            self.reset()
        
        # 处理输入
        text = ""
        images = []
        
        if messages:
            # OpenAI 格式 - 处理所有消息（保留历史上下文）
            # 只提取最后一条用户消息的内容用于发送
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                
                # 保存所有消息到历史（用于上下文）
                if role == "user":
                    self.messages.append(Message(role="user", content=content))
                    # 只提取最后一条用户消息的内容
                    t, imgs = self._parse_content(content)
                    text = t
                    images = imgs
                elif role == "assistant":
                    # 保存 assistant 的回复到历史
                    self.messages.append(Message(role="assistant", content=content))
                # 忽略 system 等其他角色的消息
            
            # 限制消息历史数量（保留最近的对话）
            if len(self.messages) > self.max_history_messages:
                # 保留最近的消息，删除最旧的消息
                # 但要确保保留完整的对话对（user + assistant）
                keep_count = self.max_history_messages
                if keep_count % 2 == 1:  # 如果是奇数，减1确保是偶数（成对保留）
                    keep_count -= 1
                self.messages = self.messages[-keep_count:]
        elif message:
            text = message
            self.messages.append(Message(role="user", content=message))
            
            if image:
                images = [{"mime_type": "image/jpeg", "data": base64.b64encode(image).decode()}]
            elif image_url:
                if image_url.startswith("data:"):
                    match = re.match(r'data:([^;]+);base64,(.+)', image_url)
                    if match:
                        images = [{"mime_type": match.group(1), "data": match.group(2)}]
                else:
                    try:
                        resp = httpx.get(image_url, timeout=30)
                        mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
                        images = [{"mime_type": mime, "data": base64.b64encode(resp.content).decode()}]
                    except:
                        pass
        
        if not text:
            raise ValueError("消息内容不能为空")
        
        # 发送请求
        return self._send_request(text, images, model)

    
    def _log_gemini_call(self, request_data: dict, response_text: str, error: str = None):
        """记录 Gemini 内部调用日志"""
        import datetime
        log_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "type": "gemini_internal",
            "request": request_data,
            "response_raw": response_text,
            "error": error
        }
        try:
            with open("api_logs.json", "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False, indent=2) + "\n---\n")
        except Exception as e:
            print(f"[LOG ERROR] 写入 Gemini 日志失败: {e}")

    def _send_request(self, text: str, images: List[Dict] = None, model: str = None) -> ChatCompletionResponse:
        """发送请求到 Gemini"""
        url = f"{self.BASE_URL}/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        params = {
            "bl": self.bl,
            "f.sid": "",
            "hl": "zh-CN",
            "_reqid": str(self.request_count * 100000 + random.randint(10000, 99999)),
            "rt": "c",
        }
        
        # 上传图片获取路径
        image_paths = []
        if images and len(images) > 0:
            if not self.push_id:
                print("⚠️  图片上传需要 push-id，请运行: python get_push_id.py")
                print("   然后将获取的 push-id 添加到 config.py")
            else:
                try:
                    for img in images:
                        # 解码 base64 数据
                        img_data = base64.b64decode(img["data"])
                        # 上传并获取路径
                        path = self._upload_image(img_data, img["mime_type"])
                        image_paths.append(path)
                        if self.debug:
                            print(f"[DEBUG] 图片上传成功: {path[:50]}...")
                except Exception as e:
                    print(f"⚠️  图片上传失败: {e}")
                    image_paths = []
        
        req_data = self._build_request_data(text, images, image_paths, model)
        
        form_data = {
            "f.req": req_data,
            "at": self.snlm0e,
        }
        
        # 构建日志记录
        gemini_request_log = {
            "url": url,
            "params": params,
            "text": text,
            "model": model,
            "has_images": len(images) > 0 if images else False,
            "image_paths": image_paths,
            "f_req_preview": req_data[:500] + "..." if len(req_data) > 500 else req_data,
        }
        
        if self.debug:
            print(f"[DEBUG] 请求 URL: {url}")
            print(f"[DEBUG] AT Token: {self.snlm0e[:30]}...")
            print(f"[DEBUG] 模型: {model or '默认'}")
            if image_paths:
                print(f"[DEBUG] 请求数据前300字符: {req_data[:300]}")
        
        try:
            resp = self.session.post(url, params=params, data=form_data)
            
            if self.debug:
                print(f"[DEBUG] 响应状态: {resp.status_code}")
                print(f"[DEBUG] 响应内容前1000字符: {resp.text[:1000]}")
                if image_paths:
                    # 保存完整响应用于调试
                    with open("debug_image_response.txt", "w", encoding="utf-8") as f:
                        f.write(resp.text)
                    print(f"[DEBUG] 完整响应已保存到 debug_image_response.txt")
            
            # 记录 Gemini 完整响应
            self._log_gemini_call(gemini_request_log, resp.text)
            
            resp.raise_for_status()
            self.request_count += 1
            
            reply_text = self._parse_response(resp.text)
            
            # 如果解析失败，可能是引用内容状态，尝试等待或重试
            if reply_text == "无法解析响应":
                if self.debug:
                    print(f"[DEBUG] 解析失败，检查是否为引用内容状态")
                    # 检查是否包含引用内容标记
                    if '[9]' in resp.text or 'null,null,null,null,[9]' in resp.text:
                        print(f"[DEBUG] 检测到引用内容状态标记")
                        # 尝试从响应中提取更多信息
                        try:
                            lines = resp.text.split("\n")
                            for i, line in enumerate(lines):
                                line = line.strip()
                                if not line or line.startswith(")]}'") or line.isdigit():
                                    continue
                                try:
                                    data = json.loads(line)
                                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                                        actual_data = data[0]
                                        if len(actual_data) >= 3 and actual_data[0] == "wrb.fr" and actual_data[2]:
                                            inner_json = json.loads(actual_data[2])
                                            print(f"[DEBUG] 响应结构: inner_json长度={len(inner_json) if inner_json else 0}")
                                            if inner_json:
                                                for idx, item in enumerate(inner_json):
                                                    if item:
                                                        print(f"[DEBUG] inner_json[{idx}] = {str(item)[:200]}")
                        except Exception as e:
                            print(f"[DEBUG] 分析响应结构时出错: {e}")
                        # 保存失败响应用于分析
                        try:
                            with open("debug_citation_response.txt", "w", encoding="utf-8") as f:
                                f.write(resp.text)
                            print(f"[DEBUG] 引用内容响应已保存到 debug_citation_response.txt")
                        except:
                            pass
            
            # 保存助手回复
            self.messages.append(Message(role="assistant", content=reply_text))
            
            # 构建 OpenAI 格式响应
            return ChatCompletionResponse(
                id=f"chatcmpl-{self.conversation_id or 'gemini'}-{int(time.time())}",
                created=int(time.time()),
                model="gemini-web",
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=Message(role="assistant", content=reply_text),
                        finish_reason="stop"
                    )
                ],
                usage=Usage(
                    prompt_tokens=len(text),
                    completion_tokens=len(reply_text),
                    total_tokens=len(text) + len(reply_text)
                )
            )
            
        except httpx.HTTPStatusError as e:
            self._log_gemini_call(gemini_request_log, e.response.text if hasattr(e, 'response') else "", error=f"HTTP {e.response.status_code}")
            raise Exception(f"HTTP 错误: {e.response.status_code}")
        except Exception as e:
            self._log_gemini_call(gemini_request_log, "", error=str(e))
            raise Exception(f"请求失败: {e}")
    
    def reset(self):
        """重置会话上下文"""
        self.conversation_id = ""
        self.response_id = ""
        self.choice_id = ""
        self.messages = []
    
    def get_history(self) -> List[Dict]:
        """获取消息历史 (OpenAI 格式)"""
        return [{"role": m.role, "content": m.content} for m in self.messages]


# OpenAI 兼容接口
class OpenAICompatible:
    """OpenAI SDK 兼容封装"""
    
    def __init__(self, client: GeminiClient):
        self.client = client
        self.chat = self.Chat(client)
    
    class Chat:
        def __init__(self, client: GeminiClient):
            self.client = client
            self.completions = self.Completions(client)
        
        class Completions:
            def __init__(self, client: GeminiClient):
                self.client = client
            
            def create(
                self,
                model: str = "gemini-web",
                messages: List[Dict] = None,
                **kwargs
            ) -> ChatCompletionResponse:
                return self.client.chat(messages=messages)
