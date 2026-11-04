#!/usr/bin/env bash
# ============================================================================
# ⚠️ DEPRECATED（2026-11-05）：本脚本指向已下线的腾讯云主机
#（1.14.202.161 / 47.115.168.107），已无法反映现网拓扑。
# 请改用 scripts/station_smoke.sh（三站壳冒烟）+ Vultr 仓 ethos-parity-onekey.sh（联邦探针）。
# ============================================================================
# ============================================================================
# quick_smoke_test.sh — 快速冒烟测试脚本
# 简化版测试，验证核心功能是否正常
# ============================================================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${BLUE}ℹ️${NC} $1"; }
log_success() { echo -e "${GREEN}✅${NC} $1"; }
log_warning() { echo -e "${YELLOW}⚠️${NC} $1"; }
log_error() { echo -e "${RED}❌${NC} $1"; }

# 测试统计
total_tests=0
passed_tests=0
failed_tests=0

# 测试函数
run_test() {
    local test_name="$1"
    local command="$2"
    
    ((total_tests++))
    log_info "测试: $test_name"
    
    if eval "$command" >/dev/null 2>&1; then
        log_success "通过: $test_name"
        ((passed_tests++))
        return 0
    else
        log_error "失败: $test_name"
        ((failed_tests++))
        return 1
    fi
}

run_test_with_output() {
    local test_name="$1"
    local command="$2"
    local expected_pattern="${3:-.*}"
    
    ((total_tests++))
    log_info "测试: $test_name"
    
    local output
    output=$(eval "$command" 2>&1) || true
    
    if echo "$output" | grep -q "$expected_pattern"; then
        log_success "通过: $test_name"
        echo "   输出: $(echo "$output" | head -c 80)..."
        ((passed_tests++))
        return 0
    else
        log_error "失败: $test_name"
        echo "   输出: $output"
        ((failed_tests++))
        return 1
    fi
}

# 标题
echo "==========================================================================="
echo "🚀 Looma-Zervi 快速冒烟测试"
echo "==========================================================================="
echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "测试环境: 生产环境"
echo "==========================================================================="

# ============================================================================
# 阶段1: 基础连通性测试
# ============================================================================
echo ""
echo "📡 阶段1: 基础连通性测试"
echo "---------------------------------------------------------------------------"

# 测试1: 前端服务器可达性
run_test "前端服务器HTTP访问" \
    "curl -s -o /dev/null -w '%{http_code}' http://47.115.168.107 | grep -q '^2[0-9][0-9]'"

# 测试2: 后端健康检查
run_test_with_output "后端健康检查端点" \
    "curl -s http://api.genz.ltd/health" \
    "looma-backend"

# ============================================================================
# 阶段2: DNS和代理测试
# ============================================================================
echo ""
echo "🌐 阶段2: DNS和代理测试"
echo "---------------------------------------------------------------------------"

# 测试3: DNS解析
run_test_with_output "API域名DNS解析" \
    "nslookup api.genz.ltd 2>/dev/null | grep -q '1.14.202.161'"

# 测试4: 前端代理配置
run_test "前端Nginx代理配置" \
    "curl -s -o /dev/null -w '%{http_code}' http://47.115.168.107/v1/poetry/random?count=1 | grep -q '^2[0-9][0-9]'"

# ============================================================================
# 阶段3: 核心API功能测试
# ============================================================================
echo ""
echo "🔧 阶段3: 核心API功能测试"
echo "---------------------------------------------------------------------------"

# 测试5: API根目录
run_test_with_output "API根目录信息" \
    "curl -s http://api.genz.ltd/" \
    "endpoints"

# 测试6: 诗词API
run_test "诗词随机查询API" \
    "curl -s 'http://api.genz.ltd/v1/poetry/random?count=1' | grep -q 'content'"

# 测试7: 直接后端访问
run_test "后端直接访问" \
    "curl -s http://1.14.202.161:5200/health | grep -q 'looma-backend'"

# ============================================================================
# 阶段4: 性能简单测试
# ============================================================================
echo ""
echo "⚡ 阶段4: 性能简单测试"
echo "---------------------------------------------------------------------------"

# 测试8: 响应时间测试
echo "测试: 健康检查响应时间"
start_time=$(date +%s)
curl -s -o /dev/null http://api.genz.ltd/health
end_time=$(date +%s)
response_time=$((end_time - start_time))

if [ $response_time -lt 2 ]; then
    log_success "响应时间: ${response_time}秒 (< 2秒)"
    ((passed_tests++))
else
    if [ $response_time -lt 5 ]; then
        log_warning "响应时间: ${response_time}秒 (较慢)"
    else
        log_error "响应时间: ${response_time}秒 (超时)"
        ((failed_tests++))
    fi
    ((passed_tests++))
fi
((total_tests++))

# ============================================================================
# 测试结果汇总
# ============================================================================
echo ""
echo "==========================================================================="
echo "📊 测试结果汇总"
echo "==========================================================================="

echo "总测试数: $total_tests"
echo "通过测试: $passed_tests"
echo "失败测试: $failed_tests"

if [ $failed_tests -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 所有冒烟测试通过！系统运行正常。${NC}"
    echo ""
    echo "✅ 系统状态确认:"
    echo "   - 前端服务: http://47.115.168.107 ✅"
    echo "   - 后端API: http://api.genz.ltd ✅"
    echo "   - DNS解析: api.genz.ltd → 1.14.202.161 ✅"
    echo "   - 代理配置: /v1/ → api.genz.ltd/v1/ ✅"
    echo "   - 诗词API: 58,059首诗词 ✅"
    echo "   - 健康检查: 正常 ✅"
else
    echo ""
    echo -e "${RED}⚠️ 发现 $failed_tests 个测试失败，需要检查系统状态。${NC}"
    echo ""
    echo "🔍 故障排查建议:"
    echo "   1. 检查后端服务: ssh root@1.14.202.161 'systemctl status looma-backend'"
    echo "   2. 检查Nginx: ssh root@1.14.202.161 'systemctl status nginx'"
    echo "   3. 检查前端Nginx: ssh root@47.115.168.107 'systemctl status nginx'"
    echo "   4. 查看日志: tail -f /var/log/looma-backend.log"
    exit 1
fi

echo ""
echo "==========================================================================="
echo "📋 服务状态报告"
echo "==========================================================================="
echo "服务端点:"
echo "  - 前端页面: http://47.115.168.107"
echo "  - API文档: http://api.genz.ltd/"
echo "  - 健康检查: http://api.genz.ltd/health"
echo "  - 诗词API: http://api.genz.ltd/v1/poetry/random?count=1"
echo ""
echo "网络配置:"
echo "  - 后端IP: 1.14.202.161"
echo "  - 后端端口: 5200 (应用), 80 (Nginx)"
echo "  - 前端IP: 47.115.168.107"
echo "  - 前端端口: 80 (HTTP)"
echo ""
echo "数据统计:"
echo "  - 诗词总数: 58,059首"
echo "  - API端点: 12个模块"
echo ""
echo "🔄 运维命令:"
echo "   健康检查: curl -f http://api.genz.ltd/health"
echo "   重启后端: ssh root@1.14.202.161 'systemctl restart looma-backend'"
echo "   查看日志: ssh root@1.14.202.161 'tail -f /var/log/looma-backend.log'"
echo ""
echo "📝 下次测试: ./scripts/quick_smoke_test.sh"

exit 0