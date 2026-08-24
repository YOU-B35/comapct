#!/bin/bash
# CrossHub Sync Helper - 测试运行脚本
# 运行所有测试并生成报告

set -e

echo "=========================================="
echo " CrossHub Sync Helper - 测试套件运行"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Node.js
echo -e "\n${YELLOW}检查依赖...${NC}"
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js: $(node --version)${NC}"

# 检查 npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}✗ npm 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ npm: $(npm --version)${NC}"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python: $(python3 --version)${NC}"

# 进入面板目录
cd "$(dirname "$0")"
PANEL_DIR=$(pwd)
echo -e "\n${YELLOW}工作目录: $PANEL_DIR${NC}"

# ========== 前端测试 ==========
echo -e "\n${YELLOW}========== 前端单元测试 ==========${NC}"

if [ ! -d "node_modules" ]; then
    echo "安装前端依赖..."
    npm install
fi

echo "运行 Vitest..."
npm run test 2>&1 | tee test-results.log || true

echo "生成覆盖率报告..."
npm run test:coverage 2>&1 || true

if [ -d "coverage" ]; then
    echo -e "${GREEN}✓ 覆盖率报告已生成: coverage/index.html${NC}"
fi

# ========== 后端测试 ==========
echo -e "\n${YELLOW}========== 后端集成测试 ==========${NC}"

if ! command -v pytest &> /dev/null; then
    echo "安装 pytest..."
    python3 -m pip install pytest pytest-cov -q
fi

echo "运行 pytest..."
python3 -m pytest tests/test_integration.py -v --tb=short 2>&1 | tee backend-test-results.log || true

# ========== 代码质量检查 ==========
echo -e "\n${YELLOW}========== 代码质量检查 ==========${NC}"

if [ -f ".eslintrc.json" ] || [ -f ".eslintrc.js" ]; then
    if ! command -v eslint &> /dev/null; then
        npm install --save-dev eslint
    fi
    echo "运行 ESLint..."
    npx eslint lib tests --max-warnings 0 || echo "ESLint 检查完成（可能有警告）"
fi

# ========== 输出总结 ==========
echo -e "\n${YELLOW}========== 测试总结 ==========${NC}"

# 统计测试结果
if [ -f "test-results.log" ]; then
    passed=$(grep -o "✓" test-results.log | wc -l || echo "0")
    failed=$(grep -o "✗" test-results.log | wc -l || echo "0")
    echo -e "前端测试: ${GREEN}✓ $passed 通过${NC}, ${RED}✗ $failed 失败${NC}"
fi

if [ -f "backend-test-results.log" ]; then
    passed=$(grep -o "PASSED" backend-test-results.log | wc -l || echo "0")
    failed=$(grep -o "FAILED" backend-test-results.log | wc -l || echo "0")
    echo -e "后端测试: ${GREEN}✓ $passed 通过${NC}, ${RED}✗ $failed 失败${NC}"
fi

echo -e "\n${GREEN}========== 测试运行完成 ==========${NC}"
echo ""
echo "报告文件:"
echo "  - 前端测试: test-results.log"
echo "  - 后端测试: backend-test-results.log"
echo "  - 覆盖率报告: coverage/index.html (如果生成)"
echo ""
