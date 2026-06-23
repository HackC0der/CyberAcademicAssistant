#!/bin/bash
# 四大顶会论文一键爬取脚本
# 用法: bash crawl_all.sh [会议名称...]
# 示例: bash crawl_all.sh          # 爬取所有会议
#       bash crawl_all.sh ndss ccs # 仅爬取NDSS和CCS

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_err()   { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查Python依赖
check_deps() {
    log_info "检查Python依赖..."
    python3 -c "import requests, bs4" 2>/dev/null || {
        log_warn "缺少依赖，正在安装..."
        pip3 install requests beautifulsoup4 lxml
    }
    log_ok "依赖检查通过"
}

# 爬取单个会议
crawl_conference() {
    local name=$1
    local script=$2
    local start_time

    echo ""
    echo -e "${BLUE}============================================================${NC}"
    log_info "开始爬取 $name 论文"
    echo -e "${BLUE}============================================================${NC}"

    start_time=$(date +%s)

    if python3 "$script"; then
        local elapsed=$(( $(date +%s) - start_time ))
        log_ok "$name 爬取完成 (耗时 ${elapsed}s)"
    else
        log_err "$name 爬取失败"
        return 1
    fi
}

main() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}       四大顶会论文爬虫 - 一键爬取${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo ""

    check_deps

    local total_start
    total_start=$(date +%s)

    # 定义会议列表: 名称|脚本文件
    CRAWLER_DIR="$SCRIPT_DIR/crawlers"
    declare -A CONFERENCES
    CONFERENCES=(
        [ndss]="$CRAWLER_DIR/ndss_crawler.py"
        [usenix]="$CRAWLER_DIR/usenix_crawler.py"
        [sp]="$CRAWLER_DIR/sp_crawler.py"
        [ccs]="$CRAWLER_DIR/ccs_crawler.py"
    )

    # 确定要爬取的会议
    local targets=("$@")
    if [ ${#targets[@]} -eq 0 ]; then
        targets=(ndss usenix sp ccs)
    fi

    local success=0
    local failed=0

    for conf in "${targets[@]}"; do
        conf=$(echo "$conf" | tr '[:upper:]' '[:lower:]')
        if [ -z "${CONFERENCES[$conf]}" ]; then
            log_err "未知会议: $conf (可选: ndss, usenix, sp, ccs)"
            ((failed++))
            continue
        fi

        if crawl_conference "$conf" "${CONFERENCES[$conf]}"; then
            ((success++))
        else
            ((failed++))
        fi

        # 会议间延迟
        if [ "$conf" != "${targets[-1]}" ]; then
            log_info "等待5秒后继续下一个会议..."
            sleep 5
        fi
    done

    local total_elapsed=$(( $(date +%s) - total_start ))

    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}       爬取完成${NC}"
    echo -e "${BLUE}============================================================${NC}"
    echo -e "  成功: ${GREEN}${success}${NC} 个会议"
    [ $failed -gt 0 ] && echo -e "  失败: ${RED}${failed}${NC} 个会议"
    echo -e "  总耗时: ${total_elapsed}s"
    echo ""

    # 统计数据量
    log_info "数据统计:"
    for dir in NDSS USENIX CCS; do
        if [ -d "$dir" ]; then
            local count
            count=$(find "$dir" -name "*.md" | wc -l)
            echo "  $dir: ${count} 个文件"
        fi
    done
    if [ -d "S&P" ]; then
        local count
        count=$(find "S&P" -name "*.md" | wc -l)
        echo "  S&P: ${count} 个文件"
    fi
}

main "$@"
