import requests
import re
import json
import random
import urllib3
import time

# 禁用代理证书警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class GeminiChatBot:
    def __init__(self, cookie, user_agent, proxy_port):
        self.cookie = cookie.strip()
        self.user_agent = user_agent.strip()
        self.proxy_port = proxy_port
        
        # 核心请求头
        self.headers = {
            "Host": "gemini.google.com",
            "User-Agent": self.user_agent,
            "Cookie": self.cookie,
            "Accept": "*/*",
            "Origin": "https://gemini.google.com",
            "Referer": "https://gemini.google.com/",
            "X-Same-Domain": "1",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
        }
        
        self.proxies = {
            "http": f"http://127.0.0.1:{proxy_port}",
            "https": f"http://127.0.0.1:{proxy_port}",
        }
        
        self.snlm0e = None
        
        # === 记忆模块 ===
        self.cid = ""   # Conversation ID
        self.rid = ""   # Response ID
        self.rcid = ""  # Choice ID

    def step_1_init(self):
        """初始化：获取 SNlM0e 密钥"""
        print("正在连接 Gemini 获取会话密钥...", end="", flush=True)
        url = "https://gemini.google.com/"
        try:
            # 这里的 Header 不需要 Content-Type
            init_headers = self.headers.copy()
            if "Content-Type" in init_headers: del init_headers["Content-Type"]
            
            response = requests.get(url, headers=init_headers, proxies=self.proxies, verify=False)
            
            if response.status_code != 200:
                print(f"\n❌ 连接失败: {response.status_code}")
                return False

            match = re.search(r'"SNlM0e":"(.*?)"', response.text)
            if match:
                self.snlm0e = match.group(1)
                print(f" 成功! (Key: {self.snlm0e[:8]}...)")
                return True
            else:
                print("\n❌ 失败: 未找到密钥 (请检查 Cookie 是否过期)")
                return False
        except Exception as e:
            print(f"\n💥 初始化异常: {e}")
            return False

    def send_message(self, message):
        """发送消息并处理多轮对话逻辑"""
        if not self.snlm0e:
            return "❌ 错误: 未初始化密钥"

        url = "https://gemini.google.com/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"
        
        params = {
            "bl": "boq_assistant-bard-web-server_20240519.16_p0",
            "_reqid": str(random.randint(100000, 999999)),
            "rt": "c",
        }
        
        # 构造请求体 (关键：带入 cid, rid, rcid 实现记忆)
        req_json = [
            None, 
            json.dumps([
                [message, 0, None, [], None, None, 0],
                ["zh-CN"], 
                [self.cid, self.rid, self.rcid],  # <--- 这里就是记忆的关键
                None, None, None, [None], 0, []
            ])
        ]
        
        data = {
            "f.req": json.dumps(req_json),
            "at": self.snlm0e, 
        }

        try:
            resp = requests.post(url, params=params, data=data, headers=self.headers, proxies=self.proxies, verify=False)
            
            if resp.status_code != 200:
                return f"❌服务器拒绝: {resp.status_code}"

            # 解析部分
            raw_text = resp.text
            if raw_text.startswith(")]}'"):
                raw_text = raw_text[4:]

            lines = raw_text.split('\n')
            parsed_text = None
            
            for line in lines:
                if not line.strip(): continue
                try:
                    json_data = json.loads(line)
                    # 寻找包含 wrb.fr 的结构
                    if isinstance(json_data, list) and len(json_data) > 0:
                        if isinstance(json_data[0], list) and len(json_data[0]) > 2:
                            payload_str = json_data[0][2]
                            if not isinstance(payload_str, str): continue
                            
                            inner_data = json.loads(payload_str)
                            
                            # 1. 提取回复文本 (位置: [4][0][1][0])
                            if len(inner_data) > 4 and inner_data[4]:
                                parsed_text = inner_data[4][0][1][0]
                                
                                # 2. 提取上下文 ID (更新记忆)
                                self.cid = inner_data[1][0] # Conversation ID
                                self.rcid = inner_data[4][0][0] # Choice ID
                                # Response ID 有时候在不同位置，尝试获取
                                try:
                                    self.rid = inner_data[4][0][1][1]
                                except:
                                    pass
                                break
                except:
                    continue
            
            if parsed_text:
                return parsed_text
            else:
                return "❌ 未能解析返回内容 (Google 可能返回了空数据)"

        except Exception as e:
            return f"❌ 请求异常: {e}"

def chat_loop(bot):
    print("\n==================================================")
    print("🤖 Gemini 终端聊天室 (输入 'exit' 退出)")
    print("==================================================")
    
    while True:
        try:
            user_input = input("\n👤 你: ").strip()
            if not user_input: continue
            
            if user_input.lower() in ['exit', 'quit', '退出']:
                print("👋 再见！")
                break
            
            print("🤖 Gemini: 正在思考...", end="\r")
            
            # 发送请求
            reply = bot.send_message(user_input)
            
            # 清除 "正在思考..." 并打印回复
            print(" " * 20, end="\r") 
            print(f"🤖 Gemini:\n{reply}")
            
        except KeyboardInterrupt:
            print("\n👋 用户强制停止")
            break

if __name__ == "__main__":
    # ================= 🔧 配置区域 =================
    MY_PORT = 7897
    MY_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    # ⚠️ 请确保这里是你最新的、有效的 Cookie
    MY_COOKIE = """
SID=g.a0005AiszTWiUUjraa1OEw1fXRlqBCfZ8hLhEq-jc0Kx78ecgo3T8eVkBTx2U5DIELlKyHjq0AACgYKAeISARASFQHGX2MiW8PVR0NH9I68gOUCn6KWYxoVAUF8yKrSq45NnAUclLvaikkppZ4J0076; __Secure-1PSID=g.a0005AiszTWiUUjraa1OEw1fXRlqBCfZ8hLhEq-jc0Kx78ecgo3TedXswdAj4Tjacb5LLoNjLQACgYKAagSARASFQHGX2Mi3Tsb3l7mneEW-ragXkn3FxoVAUF8yKoNDdQrA9Db2XLqiCEYDFu40076; __Secure-3PSID=g.a0005AiszTWiUUjraa1OEw1fXRlqBCfZ8hLhEq-jc0Kx78ecgo3TpKJ0E-WFPCRWDMsB2sJ11wACgYKAQoSARASFQHGX2MiBciUBXPV4z0g_jkG2jNCwhoVAUF8yKrNU2lklhbvyoUk5gtLpiZp0076; HSID=AQRaIYBrHRQHVURu4; SSID=AzY5eIzELP-Lah67Z; APISID=cSxL_DlknYB2-qi6/AbupCrYIuiSG4nmyc; SAPISID=SZkCrpm2BSL9HSft/ALPGmPZ73hrivBi4k; __Secure-1PAPISID=SZkCrpm2BSL9HSft/ALPGmPZ73hrivBi4k; __Secure-3PAPISID=SZkCrpm2BSL9HSft/ALPGmPZ73hrivBi4k; _gcl_au=1.1.704562383.1766930840; _ga=GA1.1.1398545504.1766930841; NID=527=d09k5NdsUophJttas_yOejm7q0huzi-f0Ev-U1crqCvAAzBvvfPjS8jV5dlOkhsXV54T_vvAUzrz4RB9bgSJDaeCTx7L7UMuaUfVx9oxGJ4wAsoD3IHwXuvwsqEwEJlWZJoIXHUzb8br2nJrYIUUlcnD5Hzk69mO7a5SU6n55qVOKJFtEWOq6rc8_OtFYDQMyoetoUHveTdZ-egxQHXXLGg-kLE5au4a3VcbAM9HGGtebPsAb19T61oFV2M; COMPASS=gemini-pd=CjwACWuJV93jFYb_b6k1ZbZc5AVi75OXfwVJx6huPFdJgLZgT-iphNSBtyIyTho-2Gurv4U86El7hPmdVFUQmJbKygYaXQAJa4lXTqrPgvgVmcz_loQuw3D0hYlfztA7h2cW-FbGFrut92phKuFWLLrpPMAs33R-KRUWMq5v9YNgUyqCg54PBKsaZXBBqUngBd79re4kbcih-R7UTuiWoYw1qiABMAE:gemini-hl=CkkACWuJV4Jq7gXnYGXm-CCWRGf1MNczIJ0yMsen8R98zb0fdd_v1HDcw_-Y0Gxw7WZu_GGVl89NUAGecp6EG6tM_DjudIlkdiK-EMiZysoGGmoACWuJV17SPBo-ZTQDVyoIi9ZSISeESbolNHpOVVbjuoH0yl7O6LUe5bmAFZjSTu6PocxyUUZLD0Gc-UKDshR17tZ80_MLzkUZuIDOd8fBO88F-ar_cjnNZprKcT0Phdf7TvvPCWDuRRXqIAEwAQ; __Secure-1PSIDTS=sidts-CjIBflaCdVwji5znF4p5OJIMZivMhDX2jo7v71KEGn0J1anyIu041TqZm6WUkz3wehHqpBAA; __Secure-3PSIDTS=sidts-CjIBflaCdVwji5znF4p5OJIMZivMhDX2jo7v71KEGn0J1anyIu041TqZm6WUkz3wehHqpBAA; _ga_BF8Q35BMLM=GS2.1.s1766930841$o1$g1$t1766931935$j60$l0$h0; SIDCC=AKEyXzUgOUqdH90pOvSsAh6KIEnU8NG7T_vdYK3DA7YN6Oq4RyN6T2A27DEwioq6LSHIJ2Urg48; __Secure-1PSIDCC=AKEyXzVcew3wgkiJK8i8cWhD_8QrJkz16LUal-Hr0r7RY15c5cJR2p0Y1hxFICGYil4ZQutRrw; __Secure-3PSIDCC=AKEyXzVhy7jTF5s4bLAyp4z0m-lST3TJ7EgsXFjo__Ip54Ylm6KjFaakH2NRinxkqMADOrPlMQ; _ga_WC57KJ50ZZ=GS2.1.s1766930841$o1$g1$t1766931982$j13$l0$h0
    """
    # ===============================================

    if "此处" in MY_COOKIE:
        print("❌ 请先在代码底部填入 Cookie！")
    else:
        bot = GeminiChatBot(MY_COOKIE, MY_UA, MY_PORT)
        if bot.step_1_init():
            chat_loop(bot)