#!/usr/bin/env bash
# 梗百科一键启动脚本
set -e

echo "🔍 梗百科 — 网络梗智能检索与分析系统"
echo "========================================"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
python3 -c "import fastapi, langgraph, openai" 2>/dev/null || {
    echo "📥 安装依赖..."
    pip install -r memeclaw/requirements.txt
}

# 加载 .env
if [ -f .env ]; then
    echo "📄 加载 .env 配置..."
    set -a
    source .env
    set +a
fi

# 显示提供商状态
echo ""
echo "📊 提供商状态："
python3 -m memeclaw.main info

echo ""
echo "🚀 启动 API 服务 (http://localhost:8000)..."
echo "   交互式文档: http://localhost:8000/docs"
echo "   按 Ctrl+C 停止"
echo ""

python3 -m memeclaw.main serve
