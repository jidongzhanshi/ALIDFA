#!/bin/bash
echo "=== DFA交易机器人监控 ==="
echo "时间: $(date)"
echo "服务器: $(hostname)"

# 检查Docker服务
if ! systemctl is-active --quiet docker; then
    echo "❌ Docker服务未运行"
    sudo systemctl start docker
fi

# 检查容器状态
cd /home/trader/dfa_live_trader
if docker-compose ps | grep -q "Up"; then
    echo "✅ 交易容器运行中"
else
    echo "❌ 交易容器未运行，尝试重启..."
    docker-compose down
    docker-compose up -d
fi

# 检查系统资源
echo "💾 系统资源:"
echo "内存: $(free -h | awk 'NR==2{print $3"/"$2}')"
echo "磁盘: $(df -h / | awk 'NR==2{print $3"/"$2}')"

# 检查网络连接
echo "🌐 网络测试:"
curl -s --connect-timeout 10 https://api.binance.com/api/v3/time > /dev/null && echo "✅ 币安API连接正常" || echo "❌ 币安API连接失败"