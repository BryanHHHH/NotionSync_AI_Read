import os
import sys
import requests
import json
from datetime import datetime

# ================= 配置区域 =================
# 在这里填入你不想导出的属性名称（区分大小写）
# 例如：SKIP_PROPERTIES = ["创建时间", "状态", "Files & media"]
SKIP_PROPERTIES = ["Created time", "Created by"] 

# 是否抓取页面正文？(True=抓取, False=只抓属性)
# 注意：开启抓取正文会变慢，因为要逐页请求
FETCH_PAGE_CONTENT = True 
# ===========================================

# --- 自检环节 ---
print("🚀 脚本开始运行...")
TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("NOTION_DB_ID")

if not TOKEN or not DATABASE_ID:
    print("❌ 错误: 环境变量未设置。")
    sys.exit(1)

headers = {
    "Authorization": "Bearer " + TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- 核心功能函数 ---

def get_property_value(prop):
    """解析数据库属性"""
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
            return "✅" if prop['checkbox'] else "⬜"
        elif p_type == 'number':
            return str(prop['number'])
        else:
            return "" # 其他复杂类型暂时忽略，保持整洁
    except:
        return ""

def fetch_block_children(block_id):
    """抓取页面内部的 Blocks（正文）"""
    children = []
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    has_more = True
    next_cursor = None
    
    while has_more:
        try:
            params = {"page_size": 100}
            if next_cursor:
                params["start_cursor"] = next_cursor
            
            response = requests.get(url, headers=headers, params=params)
            data = response.json()
            children.extend(data.get("results", []))
            has_more = data.get("has_more")
            next_cursor = data.get("next_cursor")
        except Exception as e:
            print(f"   ⚠️ 读取正文出错: {e}")
            break
    return children

def parse_blocks_to_markdown(blocks):
    """将 Notion Blocks 转换为 Markdown"""
    md_text = ""
    for block in blocks:
        b_type = block['type']
        content = ""
        
        # 提取文本内容的通用方法
        if b_type in block and 'rich_text' in block[b_type]:
            texts = block[b_type]['rich_text']
            content = "".join([t['plain_text'] for t in texts])
        
        # 根据类型格式化
        if b_type == 'paragraph':
            md_text += f"{content}\n\n"
        elif b_type.startswith('heading_1'):
            md_text += f"# {content}\n\n"
        elif b_type.startswith('heading_2'):
            md_text += f"## {content}\n\n"
        elif b_type.startswith('heading_3'):
            md_text += f"### {content}\n\n"
        elif b_type == 'bulleted_list_item':
            md_text += f"- {content}\n"
        elif b_type == 'numbered_list_item':
            md_text += f"1. {content}\n"
        elif b_type == 'to_do':
            checked = "x" if block['to_do']['checked'] else " "
            md_text += f"- [{checked}] {content}\n"
        elif b_type == 'code':
            lang = block['code']['language']
            md_text += f"```{lang}\n{content}\n```\n\n"
        elif b_type == 'quote':
            md_text += f"> {content}\n\n"
        
        # 处理嵌套（简单的缩进处理）
        if block.get('has_children'):
             # 递归获取子块稍微复杂，这里为了脚本稳定性暂不深度递归，
             # 只有Toggle或列表可能有子项。
             pass 
             
    return md_text

def fetch_database_pages():
    print(f"📡 正在连接数据库...")
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    results = []
    has_more = True
    next_cursor = None

    while has_more:
        payload = {"page_size": 50} # 稍微调小一点，防止超时
        if next_cursor:
            payload["start_cursor"] = next_cursor
        
        resp = requests.post(url, json=payload, headers=headers)
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more")
        next_cursor = data.get("next_cursor")
        print(f"   - 已加载 {len(results)} 个页面元数据...")
    
    return results

def generate_markdown(pages):
    print("📝 开始处理数据并生成 Markdown...")
    md_content = f"# Notion 数据库导出\n更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    total = len(pages)
    for index, page in enumerate(pages):
        # 1. 处理属性
        props = page['properties']
        title = "无标题"
        other_props = {}
        
        for name, prop_data in props.items():
            if name in SKIP_PROPERTIES: # ---> 过滤逻辑在这里
                continue
                
            val = get_property_value(prop_data)
            if prop_data['type'] == 'title':
                title = val
            else:
                other_props[name] = val
        
        # 2. 写入标题和属性
        print(f"   [{index+1}/{total}] 处理页面: {title}")
        md_content += f"## {title}\n"
        for key, val in other_props.items():
            if val:
                md_content += f"- **{key}**: {val}\n"
        
        # 3. 处理正文 (如果开启)
        if FETCH_PAGE_CONTENT:
            md_content += "\n**--- 正文内容 ---**\n\n"
            blocks = fetch_block_children(page['id'])
            page_body = parse_blocks_to_markdown(blocks)
            if not page_body.strip():
                page_body = "(无正文内容)\n"
            md_content += page_body
            
        md_content += "\n---\n\n"
        
    return md_content

if __name__ == "__main__":
    pages = fetch_database_pages()
    content = generate_markdown(pages)
    
    with open("notion_data.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ 完成！")
