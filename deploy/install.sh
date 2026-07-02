#!/usr/bin/env bash
# ============================================================================
# polytrader 只读扫描服务 —— 一键部署脚本(Debian/Ubuntu systemd 服务器)
#
# 部署的是【只读】的篮子套利扫描 + 模拟盘 + 面板:抓真实行情、算错价、跑模拟,
# 从不下单、不需要钱包/私钥。因此没有任何资金合规风险。
#
# 用法(在服务器上,已把整个仓库放到某目录后):
#     sudo bash deploy/install.sh
#
# 幂等:重复运行会更新代码依赖并重启服务。
# ============================================================================
set -euo pipefail

# ---- 可覆盖的参数(通过环境变量)----
APPDIR="${APPDIR:-/opt/polytrader}"     # 安装目录(默认把仓库放这里)
SVC_USER="${SVC_USER:-polytrader}"      # 运行服务的非 root 用户
PORT="${PORT:-8501}"                     # 面板端口

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"  # 仓库根(本脚本上一级)

echo "==> polytrader 部署开始"
echo "    仓库源: $SRC_DIR"
echo "    安装到: $APPDIR   用户: $SVC_USER   端口: $PORT"

if [[ $EUID -ne 0 ]]; then
  echo "请用 root 运行:  sudo bash deploy/install.sh" >&2
  exit 1
fi

# ---- 1. 系统依赖 ----
echo "==> 安装系统依赖 (python3-venv, curl, sqlite3, logrotate)"
apt-get update -qq
apt-get install -y -qq python3-venv python3-pip curl sqlite3 logrotate rsync

# ---- 2. 服务用户 ----
if ! id -u "$SVC_USER" >/dev/null 2>&1; then
  echo "==> 创建服务用户 $SVC_USER"
  useradd --system --create-home --shell /usr/sbin/nologin "$SVC_USER"
fi

# ---- 3. 同步代码到安装目录 ----
echo "==> 同步代码到 $APPDIR"
mkdir -p "$APPDIR"
rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude 'data' \
  --exclude '__pycache__' --exclude '.claude' \
  "$SRC_DIR"/ "$APPDIR"/
mkdir -p "$APPDIR/data"

# ---- 4. Python 虚拟环境 + 安装本项目 ----
echo "==> 创建虚拟环境并安装依赖"
if [[ ! -d "$APPDIR/.venv" ]]; then
  python3 -m venv "$APPDIR/.venv"
fi
"$APPDIR/.venv/bin/pip" install -q --upgrade pip
"$APPDIR/.venv/bin/pip" install -q "$APPDIR"

chown -R "$SVC_USER":"$SVC_USER" "$APPDIR"

# ---- 5. 配置文件 ----
echo "==> 写入配置 /etc/polytrader/polytrader.env"
mkdir -p /etc/polytrader
if [[ ! -f /etc/polytrader/polytrader.env ]]; then
  sed -e "s#/opt/polytrader#$APPDIR#g" \
      -e "s#POLYTRADER_DASHBOARD_PORT=.*#POLYTRADER_DASHBOARD_PORT=$PORT#" \
      "$SRC_DIR/deploy/polytrader.env.example" > /etc/polytrader/polytrader.env
  echo "    已生成(如需改扫描间隔/端口,编辑此文件后 systemctl restart)"
else
  echo "    已存在,保留不覆盖"
fi

# ---- 6. 日志目录 + 轮转 ----
echo "==> 配置日志目录与轮转"
mkdir -p /var/log/polytrader
chown -R "$SVC_USER":"$SVC_USER" /var/log/polytrader
install -m 644 "$SRC_DIR/deploy/polytrader.logrotate" /etc/logrotate.d/polytrader

# ---- 7. 渲染并安装 systemd 单元(替换占位符)----
echo "==> 安装 systemd 服务"
render() {
  sed -e "s#__USER__#$SVC_USER#g" \
      -e "s#__APPDIR__#$APPDIR#g" \
      -e "s#__VENV__#$APPDIR/.venv#g" \
      "$SRC_DIR/deploy/$1" > "/etc/systemd/system/$1"
}
render polytrader-scanner.service
render polytrader-dashboard.service
render polytrader-vacuum.service
install -m 644 "$SRC_DIR/deploy/polytrader-vacuum.timer" /etc/systemd/system/polytrader-vacuum.timer

systemctl daemon-reload
systemctl enable --now polytrader-scanner.service
systemctl enable --now polytrader-dashboard.service
systemctl enable --now polytrader-vacuum.timer

echo ""
echo "==> 部署完成 ✅"
echo "    面板:      http://<服务器IP>:$PORT"
echo "    扫描器状态: systemctl status polytrader-scanner"
echo "    实时日志:   journalctl -u polytrader-scanner -f"
echo "                tail -f /var/log/polytrader/scanner.log"
echo "    改配置:     编辑 /etc/polytrader/polytrader.env 后 systemctl restart polytrader-scanner"
echo ""
echo "    提示:云服务器安全组/防火墙需放行 $PORT 端口才能从外部访问面板。"
echo "    这是只读数据服务,不涉及下单;交易的地区合规限制与本服务无关。"
