import os
import requests
import json
from datetime import datetime

# 从 GitHub Secrets 获取环境变量
TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DB_ID")

headers = {
    "Authorization": "Bearer " + TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def get_property_value(prop):
    """
    辅助函数：解析 Notion 复杂的属性格式，转为简单的字符串
    """
    try:
        p_type = prop['type']
        if p_type == 'title':
            return prop['title'][0]['plain_text'] if prop['title'] else "无标题"
        elif p_type == 'rich_text':
            return "".join([t['plain_text'] for t in prop['rich_text']])
        elif p_type == 'select':
            return prop['select']['name'] if prop['select'] else ""
        elif p_type == 'multi_select':
            return ", ".join([t['name'] for t in prop['multi_select']])
        elif p_type == 'date':
            return prop['date']['start'] if prop['date'] else ""
        elif p_type == 'url':
            return prop['url'] if prop['url'] else ""
        elif p_type == 'checkbox':
            return "是" if prop['checkbox'] else "否"
        else:
            return "[其它类型数据]"
    except:
        return ""

def fetch_data():
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    results = []
    has_more = True
    next_cursor = None

    # 分页抓取（如果数据超过100条）
    while has_more:
        payload = {"page_size": 100}
        if next_cursor:
            payload["start_cursor"] = next_cursor
        
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()
        
        if "results" not in data:
            print("Error:", data)
            break
            
        results.extend(data["results"])
        has_more = data.get("has_more")
        next_cursor = data.get("next_cursor")
    
    return results

def generate_markdown(pages):
    md_content = f"# Notion 数据库导出\n更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    for page in pages:
        props = page['properties']
        
        # 尝试找到标题列（Notion API中标题列的 Key 也是动态的，但类型一定是 title）
        title = "未命名条目"
        other_props = {}
        
        for name, prop_data in props.items():
            val = get_property_value(prop_data)
            if prop_data['type'] == 'title':
                title = val
            else:
                other_props[name] = val
        
        # 拼接 Markdown
        md_content += f"## {title}\n"
        for key, val in other_props.items():
            if val: # 只有当值不为空时才写入
                md_content += f"- **{key}**: {val}\n"
        md_content += "\n---\n\n"
        
    return md_content

if __name__ == "__main__":
    print("开始获取 Notion 数据...")
    pages = fetch_data()
    print(f"获取到 {len(pages)} 条数据，开始生成 Markdown...")
    content = generate_markdown(pages)
    
    with open("notion_data.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("完成！文件已保存为 notion_data.md")
