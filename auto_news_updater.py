#!/usr/bin/env python3
"""
AI News 日报自动更新脚本
每天自动抓取内网文档内容，更新 ai-news.html 的"近期精彩内容"区块并推送到 GitHub
需在公司内网或 VPN 环境下运行
"""

import urllib.request
import urllib.error
import json
import base64
import os
import re
from datetime import datetime

# ============================================================
# 配置（按需修改）
# ============================================================
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOS = ["peixunde/ai-learning-hub", "peixunde/chengdu-wuqiao"]
NEWS_FILE    = "news/ai-news.html"
DOC_URL      = "https://docs.corp.kuaishou.com/d/home/fcABJ9T4vXww_pr7taLhSY6V8"
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "User-Agent":    "ai-news-updater",
    "Accept":        "application/vnd.github.v3+json",
    "Content-Type":  "application/json",
}

# ============================================================
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ============================================================
def fetch_doc():
    """抓取内网文档 HTML"""
    log(f"抓取文档: {DOC_URL}")
    try:
        req = urllib.request.Request(DOC_URL, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="ignore")
        log(f"文档抓取成功，大小: {len(html)} 字节")
        return html
    except Exception as e:
        log(f"❌ 文档抓取失败: {e}")
        return None

# ============================================================
def parse_news_items(html):
    """
    从文档 HTML 中解析新闻条目
    尝试提取标题、日期、摘要信息
    """
    # 去除 script/style
    clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    clean = re.sub(r'<style[^>]*>.*?</style>',  '', clean, flags=re.DOTALL)

    # 提取所有文本段落（去除 HTML 标签）
    text = re.sub(r'<[^>]+>', '\n', clean)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    # 按行分割，过滤有效内容
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 5]

    # 尝试提取日期行和内容行
    date_pattern = re.compile(r'(20\d{2}[年/-]\d{1,2}[月/-]\d{1,2}|第\d+期|\d{1,2}月\d{1,2}日)')
    news_items = []
    current_item = None

    for line in lines[:80]:  # 只取前80行
        if date_pattern.search(line):
            if current_item:
                news_items.append(current_item)
            current_item = {"date": line, "title": "", "desc": ""}
        elif current_item:
            if not current_item["title"] and len(line) > 3:
                current_item["title"] = line[:60]
            elif not current_item["desc"] and len(line) > 5:
                current_item["desc"] = line[:80]

    if current_item:
        news_items.append(current_item)

    # 如果没解析到结构化内容，返回原始文本摘要
    if not news_items:
        snippets = [l for l in lines if len(l) > 10][:6]
        news_items = [{"date": "", "title": s[:50], "desc": ""} for s in snippets]

    return news_items[:5]  # 最多5条

# ============================================================
def build_news_html(items, doc_url):
    """构建新闻卡片 HTML"""
    today = datetime.now().strftime("%Y年%m月%d日")

    cards = ""
    for item in items:
        date_html = f'<span class="news-date"><i class="fas fa-calendar-alt"></i> {item["date"]}</span>' if item["date"] else ""
        desc_html = f'<p class="news-desc">{item["desc"]}</p>' if item["desc"] else ""
        cards += f"""
                    <div class="news-item">
                        {date_html}
                        <h4>{item["title"]}</h4>
                        {desc_html}
                    </div>"""

    return f"""                <!-- 自动更新区块 START - 最后更新: {today} -->
                <div class="auto-news-block">
                    <div class="auto-news-header">
                        <span><i class="fas fa-sync-alt"></i> 自动更新 · {today}</span>
                        <a href="{doc_url}" target="_blank" style="font-size:0.82rem;color:#6B7280;">查看完整版 →</a>
                    </div>
                    <style>
                        .auto-news-block {{border:1px solid #E5E7EB;border-radius:12px;overflow:hidden;margin-bottom:1.5rem;}}
                        .auto-news-header {{background:#F9FAFB;padding:0.75rem 1.25rem;font-size:0.85rem;color:#374151;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #E5E7EB;}}
                        .news-item {{padding:1rem 1.25rem;border-bottom:1px solid #F3F4F6;}}
                        .news-item:last-child {{border-bottom:none;}}
                        .news-item h4 {{font-size:0.95rem;color:#1F2937;margin:0.25rem 0;}}
                        .news-date {{font-size:0.78rem;color:#6B7280;}}
                        .news-desc {{font-size:0.85rem;color:#6B7280;margin-top:0.3rem;}}
                    </style>
                    {cards}
                </div>
                <!-- 自动更新区块 END -->"""

# ============================================================
def update_html_file(news_html):
    """更新本地 ai-news.html 文件"""
    fpath = os.path.join(BASE_DIR, NEWS_FILE)
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # 先尝试替换已有的自动更新区块
    pattern = r'<!-- 自动更新区块 START.*?<!-- 自动更新区块 END -->'
    if re.search(pattern, content, re.DOTALL):
        new_content = re.sub(pattern, news_html.strip(), content, flags=re.DOTALL)
        log("替换已有的自动更新区块")
    else:
        # 插入到"近期精彩内容"标题后面
        target = '近期精彩内容'
        if target in content:
            # 找到标题所在的标签结束位置后插入
            insert_after = re.search(r'近期精彩内容.*?</h\d>', content, re.DOTALL)
            if insert_after:
                pos = insert_after.end()
                new_content = content[:pos] + '\n' + news_html + '\n' + content[pos:]
                log("插入到近期精彩内容标题后")
            else:
                new_content = content.replace(target, target + '\n' + news_html)
        else:
            log("⚠️ 未找到插入位置，跳过更新")
            return False

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(new_content)
    log(f"✅ 本地文件已更新: {NEWS_FILE}")
    return True

# ============================================================
def push_to_github():
    """推送到所有 GitHub 仓库"""
    fpath = os.path.join(BASE_DIR, NEWS_FILE)
    with open(fpath, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    today = datetime.now().strftime("%Y-%m-%d")
    success = False
    for repo in GITHUB_REPOS:
        log(f"推送到 GitHub: {repo}/{NEWS_FILE}")
        api_url = f"https://api.github.com/repos/{repo}/contents/{NEWS_FILE}"
        try:
            with urllib.request.urlopen(urllib.request.Request(api_url, headers=HEADERS), timeout=30) as r:
                sha = json.load(r).get("sha")
        except:
            sha = None
        body = {"message": f"AI News 日报自动更新 {today}", "content": content, "branch": "main"}
        if sha:
            body["sha"] = sha
        req = urllib.request.Request(api_url, data=json.dumps(body).encode(), method="PUT", headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                json.load(r)
                log(f"✅ {repo} 推送成功")
                success = True
        except urllib.error.HTTPError as e:
            log(f"❌ {repo} 推送失败: {e.read().decode()[:100]}")
    if success:
        log(f"🔗 https://peixunde.github.io/ai-learning-hub/news/ai-news.html")
    return success

# ============================================================
def main():
    log("=" * 50)
    log("AI News 日报自动更新脚本")
    log("=" * 50)

    # Step 1: 抓取文档
    html = fetch_doc()
    if not html:
        log("❌ 无法访问内网文档，请确认网络环境")
        log("💡 提示：需要在公司内网或 VPN 环境下运行")
        return

    # Step 2: 解析新闻
    items = parse_news_items(html)
    log(f"解析到 {len(items)} 条内容")
    for i, item in enumerate(items, 1):
        log(f"  {i}. {item.get('title', '')[:40]}")

    # Step 3: 构建 HTML
    news_html = build_news_html(items, DOC_URL)

    # Step 4: 更新本地文件
    if not update_html_file(news_html):
        return

    # Step 5: 推送到 GitHub
    push_to_github()

    log("=" * 50)
    log("完成！")

if __name__ == "__main__":
    main()
