import json
import logging
from typing import Optional

import requests
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 配置常量
API_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = "sk-7d28545b94fc41b6909e367357ad79a7"

# 配置常量
MAX_HISTORY_LENGTH = 10  # 限制历史消息数量
SYSTEM_MESSAGE = {
    "role": "system",
    "content": "You are a helpful assistant. Please communicate in Chinese and provide clear and concise responses.",
}

app = FastAPI(title="Chat API", description="AI聊天服务API", version="1.0.0")

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储用户会话历史
chat_histories = {}


class Message(BaseModel):
    content: str
    user_id: Optional[str] = "default_user"


class ChatResponse(BaseModel):
    response: str
    status: str = "success"


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.post("/chat", response_model=ChatResponse)
async def chat(message: Message):
    try:
        logger.info(f"收到请求: {message.content}")

        # 获取或初始化用户的聊天历史
        if message.user_id not in chat_histories:
            chat_histories[message.user_id] = [SYSTEM_MESSAGE]

        # 添加用户消息到历史记录
        chat_histories[message.user_id].append(
            {"role": "user", "content": message.content}
        )

        # 保持历史记录在限制范围内
        if (
            len(chat_histories[message.user_id]) > MAX_HISTORY_LENGTH * 2 + 1
        ):  # +1 是因为系统消息
            chat_histories[message.user_id] = (
                [chat_histories[message.user_id][0]]  # 保留系统消息
                + chat_histories[message.user_id][
                    -MAX_HISTORY_LENGTH * 2 :
                ]  # 保留最近的对话
            )

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            }

            payload = {
                "model": "deepseek-chat",
                "messages": chat_histories[message.user_id],
                "stream": True,
                "response_format": {"type": "text"},
            }

            # 使用流式响应处理
            response = requests.post(
                API_URL, headers=headers, json=payload, timeout=30, stream=True
            )

            if response.status_code == 200:
                # 初始化完整响应内容
                full_content = ""

                # 逐行处理流式响应
                for line in response.iter_lines():
                    if line:
                        # 去除 "data: " 前缀并解析 JSON
                        line_text = line.decode("utf-8")
                        if line_text.startswith("data: "):
                            json_str = line_text[6:]  # 跳过 "data: " 前缀

                            # 处理结束标记
                            if json_str == "[DONE]":
                                break

                            try:
                                chunk = json.loads(json_str)
                                if "choices" in chunk and len(chunk["choices"]) > 0:
                                    delta = chunk["choices"][0].get("delta", {})
                                    if "content" in delta:
                                        content_chunk = delta["content"]
                                        full_content += content_chunk
                                        logger.info(f"收到回复: {content_chunk}")
                                        # 这里可以添加实时发送内容到客户端的代码
                            except json.JSONDecodeError:
                                logger.error(f"无法解析JSON: {json_str}")

                # 将完整响应添加到历史记录
                ai_message = {
                    "role": "assistant",
                    "content": full_content,
                }
                chat_histories[message.user_id].append(ai_message)

                return ChatResponse(response=full_content)
            else:
                logger.error(f"API请求失败: {response.status_code} - {response.text}")
                return ChatResponse(
                    response=f"API请求失败: {response.status_code}", status="error"
                )

        except requests.exceptions.RequestException as e:
            logger.error(f"请求异常: {str(e)}", exc_info=True)
            return ChatResponse(
                response="API服务连接失败，请稍后重试。", status="error"
            )
        except Exception as e:
            logger.error(f"API调用错误: {str(e)}", exc_info=True)
            return ChatResponse(
                response="抱歉，服务暂时不可用，请稍后重试。", status="error"
            )

    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}", exc_info=True)
        return ChatResponse(response="系统内部错误，请稍后重试。", status="error")


@app.post("/clear_history")
async def clear_history(user_id: str = "default_user"):
    if user_id in chat_histories:
        chat_histories[user_id] = [SYSTEM_MESSAGE]  # 清除历史时保留系统消息
    return {"status": "success", "message": "聊天历史已清除"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="localhost",
        port=8000,
        reload=True,
    )
