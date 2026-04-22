import os
import random
from notion_client import Client
import requests
import json

# 从环境变量读取
notion_token = os.getenv("NOTION_TOKEN")
database_id = os.getenv("NOTION_DATABASE_ID")
feishu_webhook = os.getenv("FEISHU_WEBHOOK")

# 初始化 Notion 客户端
client = Client(auth=notion_token)

def get_all_notes():
    """从 Notion Database 获取所有笔记"""
    results = []
    cursor = None

    while True:
        if cursor:
            response = client.databases.query(
                database_id=database_id,
                start_cursor=cursor
            )
        else:
            response = client.databases.query(database_id=database_id)

        results.extend(response.get("results", []))

        cursor = response.get("next_cursor")
        if not cursor:
            break

    return results

def extract_note_content(page):
    """从 Notion Page 提取笔记内容"""
    props = page.get("properties", {})

    book_name = ""
    if "BookName" in props:
        title = props["BookName"].get("title", [])
        book_name = "".join([t.get("plain_text", "") for t in title])

    author = ""
    if "Author" in props:
        author = "".join([t.get("plain_text", "") for t in props["Author"].get("rich_text", [])])

    url = ""
    if "URL" in props:
        url = props["URL"].get("url", "") or ""

    # 提取笔记内容（blocks）
    blocks = []
    block_id = page.get("id")
    try:
        children = client.blocks.children.list(block_id=block_id)
        for block in children.get("results", []):
            block_type = block.get("type")
            if block_type in ["callout", "paragraph"]:
                text_content = block.get(block_type, {}).get("rich_text", [])
                text = "".join([t.get("plain_text", "") for t in text_content])
                if text.strip():
                    blocks.append(text)
            elif block_type == "heading":
                level = block.get("heading", {}).get("level", 1)
                text_content = block.get("heading", {}).get("rich_text", [])
                text = "".join([t.get("plain_text", "") for t in text_content])
                if text.strip():
                    prefix = "#" * level
                    blocks.append(f"{prefix} {text}")
    except Exception as e:
        print(f"获取笔记内容失败: {e}")

    return {
        "book_name": book_name,
        "author": author,
        "url": url,
        "blocks": blocks
    }

def format_message(note):
    """格式化推送到飞书的消息"""
    book_name = note.get("book_name", "未知书名")
    author = note.get("author", "")
    url = note.get("url", "")
    blocks = note.get("blocks", [])

    content = ""
    for block in blocks:
        if not block.startswith("#"):
            content = block
            break

    if not content and blocks:
        content = blocks[0]

    header = f"📖 **{book_name}**"
    if author:
        header += f"\n👤 {author}"

    message = f"{header}\n\n💬 {content}"

    if url:
        message += f"\n\n🔗 [微信读书阅读]({url})"

    return message

def send_to_feishu(message):
    """发送到飞书机器人"""
    payload = {
        "msg_type": "text",
        "content": {
            "text": f"📚 每日读书回顾\n\n{message}\n\n---\n每天进步一点点 🚀"
        }
    }

    response = requests.post(
        feishu_webhook,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload)
    )
    return response.json()

def main():
    print("📚 开始获取笔记...")

    pages = get_all_notes()
    print(f"共找到 {len(pages)} 条笔记")

    if not pages:
        print("没有找到笔记，退出")
        return

    selected = random.choice(pages)
    note = extract_note_content(selected)

    print(f"选中: {note['book_name']}")

    message = format_message(note)
    print(f"消息内容:\n{message}")

    result = send_to_feishu(message)
    print(f"发送结果: {result}")

if __name__ == "__main__":
    main()
