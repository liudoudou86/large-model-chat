import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

# 配置常量
API_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = "sk-7d28545b94fc41b6909e367357ad79a7"

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key="sk-7d28545b94fc41b6909e367357ad79a7", base_url="https://api.deepseek.com"
)

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
            chat_histories[message.user_id] = []

        # 添加用户消息到历史记录
        chat_histories[message.user_id].append(
            {"role": "user", "content": message.content}
        )

        try:
            response = client.chat.completions.create(
                model="deepseek-chat", messages=chat_histories[message.user_id]
            )
            # 打印API响应内容
            logger.info(f"API响应内容: {response}")

            # 修改消息处理方式
            ai_message = {
                "role": "assistant",
                "content": response.choices[0].message.content,
            }
            chat_histories[message.user_id].append(ai_message)

            return ChatResponse(response=ai_message["content"])
        except Exception as e:
            logger.error(f"API调用错误: {str(e)}")
            return ChatResponse(
                response="抱歉，服务暂时不可用，请稍后重试。", status="error"
            )
            return ChatResponse(response.choices[0].message.content)

    except Exception as e:
        logger.error(f"处理请求时发生错误: {str(e)}")
        return ChatResponse(response="系统内部错误，请稍后重试。", status="error")


@app.post("/clear_history")
async def clear_history(user_id: str = "default_user"):
    if user_id in chat_histories:
        chat_histories[user_id] = []
    return {"status": "success", "message": "聊天历史已清除"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server:app",
        host="localhost",
        port=8000,
        reload=True,
    )
