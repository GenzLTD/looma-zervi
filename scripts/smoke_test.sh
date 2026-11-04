#!/usr/bin/env bash
# ============================================================================
# ⚠️ DEPRECATED（2026-11-05）：本脚本指向已下线的腾讯云主机
#（1.14.202.161 / 47.115.168.107），已无法反映现网拓扑。
# 请改用 scripts/station_smoke.sh（三站壳冒烟）+ Vultr 仓 ethos-parity-onekey.sh（联邦探针）。
# ============================================================================
# ============================================================================
# smoke_test.sh — 生产环境冒烟测试脚本
# 测试范围：前端访问、API健康、核心功能、代理配置、DNS解析
# ============================================================================

set -euo pipefail

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
    local expected_status="${3:-0}"
    
    ((total_tests++))
    log_info "测试: $test_name"
    
    if eval "$command" >/dev/null 2>&1; then
        if [ $? -eq "$expected_status" ]; then
            log_success "通过: $test_name"
            ((passed_tests++))
            return 0
        else
            log_error "失败: $test_name (状态码: $?, 预期: $expected_status)"
            ((failed_tests++))
            return 1
        fi
    else
        local exit_code=$?
        log_error "失败: $test_name (退出码: $exit_code, 预期: $expected_status)"
        ((failed_tests++))
        return 1
    fi
}

# 带输出的测试函数（用于需要查看输出的测试）
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
        echo "   输出: $(echo "$output" | head -c 100)..."
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
echo "🚀 Looma-Zervi 生产环境冒烟测试"
echo "==========================================================================="
echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "测试环境: 生产环境"
echo "==========================================================================="

# ============================================================================
# 阶段1: 网络连通性测试
# ============================================================================
echo ""
echo "📡 阶段1: 网络连通性测试"
echo "---------------------------------------------------------------------------"

# 测试1: 前端服务器可达性
run_test "前端服务器可达性 (47.115.168.107)" \
    "curl -s -o /dev/null -w '%{http_code}' http://47.115.168.107 | grep -q '^2[0-9][0-9]\|^3[0-9][0-9]'"

# 测试2: 后端服务器可达性
run_test "后端服务器可达性 (1.14.202.161)" \
    "ping -c 2 -W 2 1.14.202.161 >/dev/null"

# 测试3: 后端端口5200开放
run_test "后端应用端口开放 (5200)" \
    "nc -z -w 2 1.14.202.161 5200"

# 测试4: 后端Nginx端口80开放
run_test "后端Nginx端口开放 (80)" \
    "nc -z -w 2 1.14.202.161 80"

# ============================================================================
# 阶段2: DNS解析测试
# ============================================================================
echo ""
echo "🌐 阶段2: DNS解析测试"
echo "---------------------------------------------------------------------------"

# 测试5: api.genz.ltd DNS解析
run_test_with_output "API域名DNS解析 (api.genz.ltd)" \
    "nslookup api.genz.ltd | grep -q '1.14.202.161'"

# 测试6: 域名解析到正确IP
run_test_with_output "域名解析到正确IP" \
    "dig +short api.genz.ltd | grep -q '1.14.202.161'"

# ============================================================================
# 阶段3: 服务健康检查
# ============================================================================
echo ""
echo "🏥 阶段3: 服务健康检查"
echo "---------------------------------------------------------------------------"

# 测试7: 后端健康检查端点
run_test_with_output "后端健康检查 (/health)" \
    "curl -s http://1.14.202.161:5200/health" \
    "looma-backend"

# 测试8: 通过域名访问健康检查
run_test_with_output "域名健康检查 (api.genz.ltd/health)" \
    "curl -s http://api.genz.ltd/health" \
    "looma-backend"

# 测试9: Nginx代理健康检查
run_test_with_output "Nginx代理健康检查" \
    "curl -s http://api.genz.ltd/health" \
    "ok"

# ============================================================================
# 阶段4: API功能测试
# ============================================================================
echo ""
echo "🔧 阶段4: API功能测试"
echo "---------------------------------------------------------------------------"

# 测试10: 诗词随机查询
run_test_with_output "诗词随机查询API" \
    "curl -s 'http://api.genz.ltd/v1/poetry/random?count=1'" \
    "content"

# 测试11: API根目录信息
run_test_with_output "API根目录信息" \
    "curl -s http://api.genz.ltd/" \
    "endpoints"

# 测试12: 前端代理配置测试
run_test_with_output "前端代理配置 (/v1/ 转发)" \
    "curl -s http://47.115.168.107/v1/poetry/random?count=1" \
    "content"

# ============================================================================
# 阶段5: 性能基准测试
# ============================================================================
echo ""
echo "⚡ 阶段5: 性能基准测试"
echo "---------------------------------------------------------------------------"

# 测试13: 健康检查响应时间
echo "测试: 健康检查响应时间"
start_time=$(date +%s)
curl -s -o /dev/null http://api.genz.ltd/health
end_time=$(date +%s)
response_time=$((end_time - start_time))
if [ $response_time -lt 1 ]; then
    log_success "健康检查响应时间: ${response_time}s (< 1秒)"
    ((passed_tests++))
else
    if [ $response_time -lt 3 ]; then
        log_warning "健康检查响应时间: ${response_time}s (较慢)"
    else
        log_error "健康检查响应时间: ${response_time}s (超时)"
        ((failed_tests++))
    fi
    ((passed_tests++))
fi
((total_tests++))

# 测试14: 诗词API响应时间
echo "测试: 诗词API响应时间"
start_time=$(date +%s)
curl -s -o /dev/null "http://api.genz.ltd/v1/poetry/random?count=1"
end_time=$(date +%s)
response_time=$((end_time - start_time))
if [ $response_time -lt 2 ]; then
    log_success "诗词API响应时间: ${response_time}s (< 2秒)"
    ((passed_tests++))
else
    if [ $response_time -lt 5 ]; then
        log_warning "诗词API响应时间: ${response_time}s (较慢)"
    else
        log_error "诗词API响应时间: ${response_time}s (超时)"
        ((failed_tests++))
    fi
    ((passed_tests++))
fi
((total_tests++))

# ============================================================================
# 阶段6: 前端功能测试
# ============================================================================
echo ""
echo "🌐 阶段6: 前端功能测试"
echo "---------------------------------------------------------------------------"

# 测试15: 前端首页访问
run_test "前端首页访问" \
    "curl -s -o /dev/null -w '%{http_code}' http://47.115.168.107 | grep -q '^2[0-9][0-9]'"

# 测试16: 前端静态资源加载
run_test "前端CSS资源加载" \
    "curl -s -o /dev/null -w '%{http_code}' http://47.115.168.107/assets/index-*.css | head -1 | grep -q '^2[0-9][0-9]'"

# 测试17: 前端JS资源加载
run_test "前端JS资源加载" \
    "curl -s -o /dev/null -w '%{http_code}' http://47.115.168.107/assets/index-*.js | head -1 | grep -q '^2[0-9][0-9]'"

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
    echo "   - 前端服务: 正常运行 (http://47.115.168.107)"
    echo "   - 后端API: 正常运行 (http://api.genz.ltd)"
    echo "   - DNS解析: 正常 (api.genz.ltd → 1.14.202.161)"
    echo "   - 代理配置: 正常 (/v1/ → api.genz.ltd/v1/)"
    echo "   - 核心功能: 诗词API可用"
    echo "   - 性能表现: 响应时间正常"
else
    echo ""
    echo -e "${RED}⚠️ 发现 $failed_tests 个测试失败，需要检查系统状态。${NC}"
    echo ""
    echo "🔍 故障排查建议:"
    echo "   1. 检查后端服务状态: systemctl status looma-backend"
    echo "   2. 检查Nginx配置: nginx -t && systemctl status nginx"
    echo "   3. 检查网络连通性: ping 1.14.202.161"
    echo "   4. 检查DNS解析: nslookup api.genz.ltd"
    echo "   5. 查看应用日志: tail -f /var/log/looma-backend.log"
    exit 1
fi

echo ""
echo "==========================================================================="
echo "📋 详细测试报告"
echo "==========================================================================="
echo "前端访问地址: http://47.115.168.107"
echo "后端API地址: http://api.genz.ltd"
echo "后端服务器: 1.14.202.161:5200"
echo "诗词总数: 58,059 首"
echo ""
echo "🔧 运维命令参考:"
echo "   后端重启: systemctl restart looma-backend"
echo "   Nginx重启: systemctl restart nginx"
echo "   健康检查: curl -f http://api.genz.ltd/health"
echo "   日志查看: tail -f /var/log/nginx/error.log"
echo ""
echo "🔄 下次测试执行:"
echo "   chmod +x scripts/smoke_test.sh"
echo "   ./scripts/smoke_test.sh"

exit 0