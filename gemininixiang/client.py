"""
Gemini Web Reverse Engineering Client
支持图文请求、上下文对话，OpenAI 格式输入输出
手动配置 token，无需代码登录
"""

import re
import json
import os
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
        proxy: str = None,
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
            proxy: 代理地址 (可选，格式: "http://proxy.example.com:8080" 或 "socks5://proxy.example.com:1080")
            debug: 是否打印调试信息
        """
        self.secure_1psid = secure_1psid
        self.secure_1psidts = secure_1psidts
        self.secure_1psidcc = secure_1psidcc
        self.snlm0e = snlm0e
        self.bl = bl
        self.push_id = push_id
        self.proxy = proxy
        self.debug = debug
        
        # 构建 httpx 客户端参数
        client_kwargs = {
            "timeout": 1220.0,
            "follow_redirects": True,
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": self.BASE_URL,
                "Referer": f"{self.BASE_URL}/",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
        }
        
        # 如果设置了代理，添加到客户端参数
        # httpx 使用 proxy 参数（不是 proxies），可以直接接受字符串
        if proxy:
            # httpx 的 proxy 参数可以直接接受字符串格式的代理地址
            if isinstance(proxy, str):
                # 确保代理地址格式正确
                if not proxy.startswith(("http://", "https://", "socks5://", "socks4://")):
                    # 默认当作 HTTP 代理
                    proxy = f"http://{proxy}"
                client_kwargs["proxy"] = proxy
            elif isinstance(proxy, dict):
                # 如果是字典格式，httpx 也支持，但通常使用字符串更简单
                # 为了兼容，我们可以提取第一个值
                proxy_value = list(proxy.values())[0] if proxy else None
                if proxy_value:
                    client_kwargs["proxy"] = proxy_value
            else:
                # 其他格式，尝试转换为字符串
                client_kwargs["proxy"] = str(proxy)
            
            if self.debug:
                print(f"[DEBUG] 使用代理: {client_kwargs['proxy']}")
        
        self.session = httpx.Client(**client_kwargs)
        
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
        
        # 会话状态文件路径
        self.session_file: str = "conversation_state.json"
        
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
        
        # 尝试加载之前的会话状态
        self._load_session_state()
    
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
            
            init_resp = self.session.post(upload_url, data={"File name": filename}, headers=init_headers, timeout=30.0)
            
            if self.debug:
                print(f"[DEBUG] 初始化上传状态: {init_resp.status_code}")
                print(f"[DEBUG] 初始化响应头: {dict(init_resp.headers)}")
                if init_resp.status_code != 200:
                    print(f"[DEBUG] 初始化响应内容: {init_resp.text[:500]}")
            
            # 检查初始化响应状态
            if init_resp.status_code == 401 or init_resp.status_code == 403:
                raise CookieExpiredError(
                    f"Cookie 已过期或无效 (HTTP {init_resp.status_code})\n"
                    "请重新获取以下信息:\n"
                    "1. __Secure-1PSID\n"
                    "2. __Secure-1PSIDTS\n"
                    "3. SNlM0e\n"
                    "4. push_id\n"
                    f"响应内容: {init_resp.text[:200] if init_resp.text else '(empty)'}"
                )
            
            upload_id = init_resp.headers.get("x-guploader-uploadid")
            if not upload_id:
                error_msg = f"未获取到 upload_id (状态码: {init_resp.status_code})"
                if init_resp.text:
                    error_msg += f"\n响应内容: {init_resp.text[:200]}"
                error_msg += "\n可能原因: Cookie 已过期，请重新获取所有 token"
                raise CookieExpiredError(error_msg)
            
            if self.debug:
                print(f"[DEBUG] Upload ID: {upload_id[:50]}...")
            
            # 第二步：上传图片数据
            final_upload_url = f"{upload_url}?upload_id={upload_id}&upload_protocol=resumable"
            
            upload_headers = {
                **browser_headers,
                "content-type": mime_type,  # 使用图片的 MIME 类型，而不是 form-urlencoded
                "push-id": self.push_id,
                "x-goog-upload-command": "upload, finalize",
                "x-goog-upload-offset": "0",
                "x-tenant-id": "bard-storage",
                "x-client-pctx": "CgcSBWjK7pYx",
            }
            
            upload_resp = self.session.post(
                final_upload_url,
                headers=upload_headers,
                content=image_data,
                timeout=60.0  # 上传可能需要更长时间
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
        except httpx.ConnectTimeout as e:
            # 网络连接超时，提供更友好的错误信息
            error_msg = (
                "图片上传失败: 网络连接超时\n"
                "无法连接到 push.clients6.google.com\n\n"
                "可能的原因:\n"
                "1. 网络无法访问 Google 服务器（可能需要代理/VPN）\n"
                "2. 防火墙阻止了连接\n"
                "3. DNS 解析问题\n\n"
                "解决方法:\n"
                "1. 配置代理: 在 server.py 的 get_client() 函数中添加 proxy 参数\n"
                "2. 检查网络连接和防火墙设置\n"
                "3. 尝试使用 VPN 或代理服务\n"
            )
            if self.proxy:
                error_msg += f"\n当前使用的代理: {self.proxy}\n如果代理无效，请检查代理配置"
            raise ImageUploadError(error_msg)
        except httpx.NetworkError as e:
            # 其他网络错误
            error_msg = (
                f"图片上传失败: 网络错误 ({type(e).__name__})\n"
                f"错误详情: {str(e)}\n\n"
                "可能的原因:\n"
                "1. 网络连接不稳定\n"
                "2. 无法访问 Google 服务器\n"
                "3. 需要配置代理\n"
            )
            raise ImageUploadError(error_msg)
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] 上传失败: {e}")
            raise ImageUploadError(f"图片上传失败: {e}")
    
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
    
    def _build_request_data(self, text: str, images: List[Dict] = None, image_paths: List[str] = None, model: str = None, url_context: bool = False, tools: List[Dict] = None) -> str:
        """构建请求数据 - 基于真实请求格式
        
        Args:
            text: 文本内容
            images: 图片列表
            image_paths: 图片路径列表
            model: 模型名称
            url_context: 是否启用 URL 上下文
            tools: 工具列表（用于 URL 上下文等）
        """
        # 会话上下文 (空字符串表示新对话)
        conv_id = self.conversation_id or ""
        resp_id = self.response_id or ""
        choice_id = self.choice_id or ""
        
        if self.debug:
            print(f"[DEBUG] 构建请求数据 - conversation_id={conv_id[:40] if conv_id else 'None'}..., response_id={resp_id[:40] if resp_id else 'None'}..., choice_id={choice_id[:40] if choice_id else 'None'}...")
        
        # 处理图片数据 - 格式: [[[path, 1, null, mime_type], filename]]
        image_data = None
        if image_paths and len(image_paths) > 0:
            path = image_paths[0]
            mime_type = images[0]["mime_type"] if images else "image/png"
            filename = f"image_{random.randint(100000, 999999)}.png"
            # 构建图片数组结构
            image_data = [[[path, 1, None, mime_type], filename]]
        
        # 处理 URL 上下文和工具
        # 注意：网页版 Gemini 的 URL 上下文可能需要通过特定参数传递
        # 当前实现中，如果 url_context=True 或 tools 中包含 urlContext，会在请求中添加标记
        # 具体实现可能需要根据实际网页版 API 格式调整
        url_context_flag = None
        if url_context or (tools and any("urlContext" in tool for tool in tools)):
            url_context_flag = 1  # 启用 URL 上下文的标记（需要根据实际 API 调整）
            if self.debug:
                print(f"[DEBUG] URL 上下文已启用")
        
        # 生成唯一会话 ID
        session_id = str(uuid.uuid4()).upper()
        timestamp = int(time.time() * 1000)
        
        # 构建内部 JSON 数组 (基于真实请求格式)
        # 第一个元素: [text, 0, null, image_data, null, null, 0]
        # 注意：URL 上下文可能需要添加到特定位置，当前先添加标记
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
            [],  # 工具列表位置（URL 上下文等工具可以添加到这里）
            None,
            None,
            None,
            None,
            [timestamp // 1000, (timestamp % 1000) * 1000000]
        ]
        
        # 如果启用了 URL 上下文，尝试添加到工具列表位置
        # 注意：网页版 API 的工具格式可能需要特殊处理
        if url_context_flag is not None:
            # 在 inner_data[58] 位置（工具列表）添加 URL 上下文标记
            # 具体格式需要根据实际网页版 API 调整
            if self.debug:
                print(f"[DEBUG] URL 上下文标记已设置（位置可能需要根据实际 API 调整）")
        
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
                            # [9] 是引用内容状态标记，可以跳过
                            # [3] 是知识库响应标记，不应该跳过，应该正常处理
                            if len(actual_data) >= 6 and actual_data[5] and isinstance(actual_data[5], list):
                                citation_type = actual_data[5][0] if len(actual_data[5]) > 0 else None
                                # 只有 [9] 是引用内容状态，才跳过
                                if citation_type == 9:
                                    # 这是引用内容状态，跳过
                                    continue
                                # [3] 是知识库响应，不跳过，继续处理
                            
                            if actual_data[2]:
                                inner_json = json.loads(actual_data[2])
                                
                                # 更新会话上下文（即使没有文本内容）
                                if len(inner_json) > 1 and inner_json[1]:
                                    if isinstance(inner_json[1], list):
                                        # 处理 [null, "response_id"] 格式（流式响应初始块）
                                        old_conv_id = self.conversation_id
                                        old_resp_id = self.response_id
                                        
                                        # 更新会话上下文（即使没有文本内容）
                                        if len(inner_json[1]) > 0 and inner_json[1][0]:
                                            self.conversation_id = inner_json[1][0] or self.conversation_id
                                        if len(inner_json[1]) > 1 and inner_json[1][1]:
                                            self.response_id = inner_json[1][1] or self.response_id
                                        # 如果第一个是null，第二个是response_id，尝试从其他地方获取conversation_id
                                        elif len(inner_json[1]) == 2 and inner_json[1][0] is None and inner_json[1][1]:
                                            self.response_id = inner_json[1][1] or self.response_id
                                            # 检查inner_json的其他位置是否有conversation_id
                                            # 有时conversation_id在inner_json[16]位置
                                            if len(inner_json) > 16 and inner_json[16]:
                                                self.conversation_id = inner_json[16] or self.conversation_id
                                        
                                        # 如果会话上下文有更新，保存状态
                                        if self.conversation_id != old_conv_id or self.response_id != old_resp_id:
                                            self._save_session_state()
                                
                                # 提取文本内容
                                if inner_json and len(inner_json) > 4 and inner_json[4]:
                                    candidates = inner_json[4]
                                    if candidates and len(candidates) > 0:
                                        candidate = candidates[0]
                                        if candidate and len(candidate) > 1 and candidate[1]:
                                            # candidate[1] 可能是数组或字符串
                                            content_parts = candidate[1]
                                            
                                            # 处理不同的内容格式
                                            text = ""
                                            if isinstance(content_parts, list):
                                                # 遍历所有内容部分，提取文本和图片
                                                for part in content_parts:
                                                    if isinstance(part, str):
                                                        # 直接添加文本（不再处理图片生成 URL）
                                                        text += part
                                                    elif isinstance(part, dict):
                                                        # 处理带格式的内容（如引用、链接等）
                                                        if "text" in part:
                                                            part_text = part["text"]
                                                            # 直接添加文本（不再处理图片生成 URL）
                                                            text += part_text
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
                                                                        # 跳过图片生成数据（不再处理）
                                                                        if self.debug:
                                                                            print(f"[DEBUG] 检测到 inlineData，已跳过（图片生成功能已移除）")
                                                                        continue
                                                                    elif "functionCall" in subpart:
                                                                        # 跳过函数调用
                                                                        continue
                                                        elif "inlineData" in part:
                                                            # 跳过图片生成数据（不再处理）
                                                            if self.debug:
                                                                print(f"[DEBUG] 检测到 inlineData，已跳过（图片生成功能已移除）")
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
                                                # 直接使用文本内容（不再处理图片生成 URL）
                                                text = content_parts
                                            else:
                                                text = str(content_parts)
                                            
                                            if isinstance(text, str) and len(text.strip()) > 0:
                                                # 如果新文本更长，或者当前文本为空，则更新
                                                if len(text) > len(final_text) or not final_text:
                                                    final_text = text
                                                    if len(candidate) > 0:
                                                        self.choice_id = candidate[0] or self.choice_id
                                                    # 保存会话状态
                                                    self._save_session_state()
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
        model: str = None,
        stream: bool = False,
        url_context: bool = False,
        tools: List[Dict] = None
    ) -> ChatCompletionResponse:
        """
        发送聊天请求 (OpenAI 兼容格式)
        
        Args:
            messages: OpenAI 格式消息列表
            message: 简单文本消息 (与 messages 二选一)
            image: 图片二进制数据
            image_url: 图片 URL
            reset_context: 是否重置上下文
            model: 模型名称
            stream: 是否流式响应
            url_context: 是否启用 URL 上下文
            tools: 工具列表（用于 URL 上下文等）
        
        Returns:
            ChatCompletionResponse: OpenAI 格式响应（流式时返回生成器）
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
        if stream:
            return self._send_stream_request(text, images, model, url_context, tools)
        else:
            return self._send_request(text, images, model, url_context, tools)

    
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

    def _send_stream_request(self, text: str, images: List[Dict] = None, model: str = None, url_context: bool = False, tools: List[Dict] = None, image_paths: List[str] = None):
        """发送流式请求到 Gemini（生成器）
        
        Args:
            text: 文本内容
            images: 图片列表（如果提供了 image_paths，则不需要）
            model: 模型名称
            url_context: 是否启用 URL 上下文
            tools: 工具列表
            image_paths: 已上传的图片路径列表（可选，如果提供则不会重新上传）
        """
        url = f"{self.BASE_URL}/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        params = {
            "bl": self.bl,
            "f.sid": "",
            "hl": "zh-CN",
            "_reqid": str(self.request_count * 100000 + random.randint(10000, 99999)),
            "rt": "c",
        }
        
        # 上传图片获取路径（如果未提供 image_paths）
        if image_paths is None:
            image_paths = []
            if images and len(images) > 0:
                if not self.push_id:
                    raise CookieExpiredError("图片上传需要 push-id")
                try:
                    for img in images:
                        img_data = base64.b64decode(img["data"])
                        path = self._upload_image(img_data, img["mime_type"])
                        image_paths.append(path)
                except Exception as e:
                    raise ImageUploadError(f"图片上传失败: {e}")
        
        req_data = self._build_request_data(text, images, image_paths, model, url_context, tools)
        form_data = {
            "f.req": req_data,
            "at": self.snlm0e,
        }
        
        try:
            # 使用 httpx 的流式请求
            resp = self.session.post(url, params=params, data=form_data, timeout=1220.0)
            resp.raise_for_status()
            self.request_count += 1
            
            # 流式解析响应 - 跟踪已输出的内容，只输出增量
            response_text = resp.text
            lines = response_text.split("\n")
            last_text = ""  # 跟踪上次输出的完整文本
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith(")]}'") or line.isdigit():
                    continue
                
                try:
                    data = json.loads(line)
                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                        actual_data = data[0]
                        if len(actual_data) >= 3 and actual_data[0] == "wrb.fr" and actual_data[2]:
                            inner_json = json.loads(actual_data[2])
                            
                            # 更新会话上下文
                            if len(inner_json) > 1 and inner_json[1]:
                                if isinstance(inner_json[1], list):
                                    if len(inner_json[1]) > 0 and inner_json[1][0]:
                                        self.conversation_id = inner_json[1][0] or self.conversation_id
                                    if len(inner_json[1]) > 1 and inner_json[1][1]:
                                        self.response_id = inner_json[1][1] or self.response_id
                            
                            # 提取文本内容
                            if inner_json and len(inner_json) > 4 and inner_json[4]:
                                candidates = inner_json[4]
                                if candidates and len(candidates) > 0:
                                    candidate = candidates[0]
                                    if candidate and len(candidate) > 1 and candidate[1]:
                                        content_parts = candidate[1]
                                        
                                        # 提取当前完整文本（包括图片）
                                        current_text = ""
                                        if isinstance(content_parts, list):
                                            for part in content_parts:
                                                if isinstance(part, str):
                                                    # 清理换行符和空白字符
                                                    part = part.strip()
                                                    # 检查是否是图片 URL
                                                    # 直接添加文本（不再处理图片生成 URL）
                                                    current_text += part
                                                elif isinstance(part, dict):
                                                    if "text" in part:
                                                        part_text = part["text"]
                                                        # 直接添加文本
                                                        current_text += part_text
                                                    elif "content" in part:
                                                        current_text += str(part["content"])
                                                    elif "inlineData" in part:
                                                        # 跳过 inlineData（图片生成功能已移除）
                                                        if self.debug:
                                                            print(f"[DEBUG] 流式响应中检测到 inlineData，已跳过")
                                                        continue
                                        elif isinstance(content_parts, str):
                                            # 直接使用文本内容
                                            current_text = content_parts
                                        
                                        # 只输出新增的部分（增量）
                                        if current_text and len(current_text) > len(last_text):
                                            new_text = current_text[len(last_text):]
                                            if new_text:
                                                yield new_text
                                                last_text = current_text
                except:
                    continue
        except Exception as e:
            raise Exception(f"流式请求失败: {e}")

    def _send_request(self, text: str, images: List[Dict] = None, model: str = None, url_context: bool = False, tools: List[Dict] = None) -> ChatCompletionResponse:
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
                raise CookieExpiredError(
                    "图片上传需要 push-id\n"
                    "获取方法: 运行 python get_push_id.py 或从浏览器 Network 中获取\n"
                    "或者在后台配置页面重新保存 Cookie，系统会自动获取 push-id"
                )
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
                except CookieExpiredError:
                    # Cookie 过期错误直接抛出
                    raise
                except Exception as e:
                    # 其他错误也抛出，让调用者知道上传失败
                    raise ImageUploadError(f"图片上传失败: {e}")
        
        req_data = self._build_request_data(text, images, image_paths, model, url_context, tools)
        
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
            
            # 如果解析失败，可能是流式响应的初始块或引用内容状态
            if reply_text == "无法解析响应":
                if self.debug:
                    print(f"[DEBUG] 解析失败，检查响应类型")
                    # 检查是否为流式响应的初始块（inner_json[4]为null）
                    is_streaming_initial = False
                    has_citation_marker = False
                    
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
                                        
                                        # 检查是否是流式响应的初始块
                                        if inner_json and len(inner_json) > 4 and inner_json[4] is None:
                                            is_streaming_initial = True
                                            print(f"[DEBUG] 检测到流式响应初始块（inner_json[4]为null）")
                                            # 检查是否有response_id
                                            if len(inner_json) > 1 and inner_json[1] and isinstance(inner_json[1], list):
                                                if len(inner_json[1]) > 1 and inner_json[1][1]:
                                                    print(f"[DEBUG] 响应ID: {inner_json[1][1]}")
                                        
                                        # 检查引用内容标记
                                        if len(actual_data) >= 6 and actual_data[5] and isinstance(actual_data[5], list) and len(actual_data[5]) > 0:
                                            if actual_data[5][0] == 3 or actual_data[5][0] == 9:
                                                has_citation_marker = True
                                                print(f"[DEBUG] 检测到引用内容状态标记: {actual_data[5]}")
                                        
                                        if inner_json:
                                            for idx, item in enumerate(inner_json):
                                                if item:
                                                    print(f"[DEBUG] inner_json[{idx}] = {str(item)[:200]}")
                            except Exception as e:
                                if self.debug:
                                    print(f"[DEBUG] 解析行错误: {e}")
                                continue
                    except Exception as e:
                        print(f"[DEBUG] 分析响应结构时出错: {e}")
                    
                    # 如果是流式响应的初始块，说明图片正在处理中
                    # 对于包含图片的请求，等待足够长时间让 Gemini 处理图片，然后使用流式方式接收响应
                    if is_streaming_initial and self.response_id and image_paths:
                        print(f"[DEBUG] 这是流式响应的初始块，图片正在处理中")
                        print(f"[DEBUG] 当前conversation_id: {self.conversation_id}")
                        print(f"[DEBUG] 当前response_id: {self.response_id}")
                        
                        # 保存原始的 conversation_id 和 response_id
                        original_conv_id = self.conversation_id
                        original_resp_id = self.response_id
                        
                        # 等待足够长时间让 Gemini 处理图片（图片处理通常需要 20-30 秒）
                        wait_time = 25  # 等待25秒
                        print(f"[DEBUG] 等待 {wait_time} 秒让 Gemini 处理图片...")
                        time.sleep(wait_time)
                        
                        # 使用流式请求方式持续接收响应
                        # 注意：使用已经上传的 image_paths，避免重新上传
                        try:
                            # 恢复原始的 conversation_id 和 response_id
                            self.conversation_id = original_conv_id
                            self.response_id = original_resp_id
                            
                            # 收集所有流式响应块
                            full_stream_text = ""
                            stream_gen = self._send_stream_request(text, images=images, model=model, url_context=url_context, tools=tools, image_paths=image_paths)
                            
                            # 等待并收集流式响应，最多等待60秒
                            max_wait_time = 60  # 最多等待60秒
                            start_time = time.time()
                            chunk_count = 0
                            last_chunk_time = time.time()
                            no_content_count = 0  # 连续没有内容的次数
                            
                            print(f"[DEBUG] 开始接收流式响应...")
                            for chunk in stream_gen:
                                chunk_count += 1
                                if chunk:
                                    full_stream_text += chunk
                                    last_chunk_time = time.time()
                                    no_content_count = 0
                                    if self.debug:
                                        print(f"[DEBUG] 收到流式块 #{chunk_count}，当前文本长度: {len(full_stream_text)}")
                                else:
                                    no_content_count += 1
                                
                                # 检查是否超时
                                elapsed = time.time() - start_time
                                if elapsed > max_wait_time:
                                    print(f"[DEBUG] 流式接收超时（{max_wait_time}秒），已接收文本长度: {len(full_stream_text)}")
                                    break
                                
                                # 如果连续5次没有收到内容，可能已经结束
                                if no_content_count >= 5:
                                    print(f"[DEBUG] 连续5次没有收到内容，停止接收")
                                    break
                                
                                # 如果已经收到内容且超过10秒没有新内容，可以退出
                                if len(full_stream_text) > 0:
                                    time_since_last_chunk = time.time() - last_chunk_time
                                    if time_since_last_chunk > 10:
                                        print(f"[DEBUG] 超过10秒没有新内容，停止接收")
                                        break
                            
                            if full_stream_text and len(full_stream_text.strip()) > 0:
                                print(f"[DEBUG] 流式接收成功，总文本长度: {len(full_stream_text)}，块数: {chunk_count}")
                                reply_text = full_stream_text.strip()
                            else:
                                print(f"[DEBUG] 流式接收未获取到内容")
                                reply_text = "图片处理时间较长，请稍后重试或发送新消息继续对话"
                        except Exception as e:
                            error_type = type(e).__name__
                            print(f"[DEBUG] 流式接收出错 ({error_type}): {e}")
                            if self.debug:
                                import traceback
                                traceback.print_exc()
                            # 如果流式接收失败，返回提示
                            reply_text = "图片处理失败，请稍后重试"
                    
                    # 保存失败响应用于分析
                    try:
                        with open("debug_citation_response.txt", "w", encoding="utf-8") as f:
                            f.write(resp.text)
                        print(f"[DEBUG] 响应已保存到 debug_citation_response.txt")
                    except:
                        pass
                    
                    # 如果仍然无法解析，检查是否是知识库响应
                    if reply_text == "无法解析响应":
                        # 检查响应中是否有知识库标记 [3]
                        has_knowledge_base = False
                        try:
                            lines = resp.text.split("\n")
                            for line in lines:
                                line = line.strip()
                                if not line or line.startswith(")]}'") or line.isdigit():
                                    continue
                                try:
                                    data = json.loads(line)
                                    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                                        actual_data = data[0]
                                        if (len(actual_data) >= 6 and actual_data[0] == "wrb.fr" and 
                                            actual_data[5] and isinstance(actual_data[5], list) and 
                                            len(actual_data[5]) > 0 and actual_data[5][0] == 3):
                                            has_knowledge_base = True
                                            if self.debug:
                                                print(f"[DEBUG] 检测到知识库响应标记 [3]")
                                            break
                                except:
                                    continue
                        except:
                            pass
                        
                        if has_knowledge_base:
                            # 知识库响应只有标记，没有内容，这是正常的
                            # 不返回错误，让知识库功能正常工作
                            if self.debug:
                                print(f"[DEBUG] 检测到知识库响应标记 [3]，但 actual_data[2] 为 null，这是正常的")
                            # 不设置 reply_text，让它保持"无法解析响应"
                            # 这样知识库功能可以正常工作，不会返回错误的提示
                        else:
                            print(f"[DEBUG] 最终检查：未检测到知识库响应，返回无法解析响应")
            
            # 保存助手回复
            self.messages.append(Message(role="assistant", content=reply_text))
            
            # 保存会话状态（包括消息历史）
            self._save_session_state()
            
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
    
    def _save_session_state(self):
        """保存会话状态到文件"""
        try:
            state = {
                "conversation_id": self.conversation_id,
                "response_id": self.response_id,
                "choice_id": self.choice_id,
                "messages": [
                    {"role": m.role, "content": m.content}
                    for m in self.messages
                ]
            }
            with open(self.session_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            if self.debug:
                print(f"[DEBUG] 会话状态已保存: conversation_id={self.conversation_id[:20] if self.conversation_id else 'None'}...")
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] 保存会话状态失败: {e}")
    
    def _load_session_state(self):
        """从文件加载会话状态"""
        try:
            if not os.path.exists(self.session_file):
                if self.debug:
                    print(f"[DEBUG] 会话状态文件不存在，使用新会话")
                return
            
            with open(self.session_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            # 恢复会话上下文
            self.conversation_id = state.get("conversation_id", "")
            self.response_id = state.get("response_id", "")
            self.choice_id = state.get("choice_id", "")
            
            # 恢复消息历史
            messages_data = state.get("messages", [])
            self.messages = [
                Message(role=msg["role"], content=msg["content"])
                for msg in messages_data
            ]
            
            # 限制消息历史数量
            if len(self.messages) > self.max_history_messages:
                keep_count = self.max_history_messages
                if keep_count % 2 == 1:
                    keep_count -= 1
                self.messages = self.messages[-keep_count:]
            
            if self.debug:
                print(f"[DEBUG] 会话状态已恢复: conversation_id={self.conversation_id[:20] if self.conversation_id else 'None'}..., messages={len(self.messages)}条")
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] 加载会话状态失败: {e}")
            # 如果加载失败，使用空状态
            self.conversation_id = ""
            self.response_id = ""
            self.choice_id = ""
            self.messages = []
    
    def reset(self):
        """重置会话上下文"""
        self.conversation_id = ""
        self.response_id = ""
        self.choice_id = ""
        self.messages = []
        # 删除会话状态文件
        try:
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
                if self.debug:
                    print(f"[DEBUG] 会话状态文件已删除")
        except Exception as e:
            if self.debug:
                print(f"[DEBUG] 删除会话状态文件失败: {e}")
    
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
