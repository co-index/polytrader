# 部署:polytrader 只读扫描服务

把**篮子套利扫描 + 模拟盘 + 面板**部署到一台常开服务器,7×24 采集真实市场的套利机会数据。

> ⚠️ 这套服务是**只读**的:抓取 Polymarket 行情、计算错价、跑模拟盘,**从不下单、不需要钱包或私钥**。因此不涉及资金合规风险。真实交易(下单)是另一回事,受地区限制,与本服务无关。

## 组成

| 组件 | 作用 | 常驻方式 |
|---|---|---|
| `polytrader-scanner` | 每 5 分钟扫一遍 negRisk 多结果事件,写 `basket.db`,并跑模拟盘写 `paper.db` | systemd 服务 |
| `polytrader-dashboard` | Streamlit 面板,读库展示(端口 8501) | systemd 服务 |
| `polytrader-vacuum` | 每周 VACUUM 压缩数据库 | systemd timer |

## 资源需求(实测轻量)

- 内存:扫描器 ~140 MB + 面板 ~130 MB ≈ **270 MB**
- CPU:~1%(I/O 密集,大部分时间在 sleep)
- 磁盘:数据库每年增长几 MB;10 GB 足够
- 带宽:约 **1 GB/天**(~30 GB/月)

**推荐规格**:1 vCPU / 1 GB 内存 / 10–25 GB SSD。最便宜的 VPS 档即可;Oracle Cloud 永久免费层(4核 ARM/24GB)零成本绰绰有余。只跑扫描器不跑面板的话,512 MB 也够。

## 一键部署

在服务器上(Debian/Ubuntu),把整个仓库放上去后:

```bash
sudo bash deploy/install.sh
```

脚本会:装系统依赖 → 建服务用户 → 同步代码到 `/opt/polytrader` → 建 venv 并 `pip install` → 写配置 `/etc/polytrader/polytrader.env` → 装并启动三个 systemd 单元。幂等,可重复运行以更新。

可用环境变量覆盖默认值:

```bash
sudo APPDIR=/opt/polytrader SVC_USER=polytrader PORT=8501 bash deploy/install.sh
```

## 常用运维

```bash
systemctl status polytrader-scanner          # 看运行状态
journalctl -u polytrader-scanner -f          # 跟随日志
tail -f /var/log/polytrader/scanner.log      # 或直接看日志文件
systemctl restart polytrader-scanner         # 改完配置后重启
```

改扫描间隔、边际阈值、端口:编辑 `/etc/polytrader/polytrader.env`,然后 `systemctl restart polytrader-scanner`(改端口需重启 dashboard)。

## 访问面板

浏览器打开 `http://<服务器IP>:8501`。**云服务器需在安全组/防火墙放行该端口。** 若不想公网暴露,建议只绑内网 + 用 SSH 隧道:

```bash
ssh -L 8501:localhost:8501 user@服务器   # 然后本地开 http://localhost:8501
```

## 手动运行(不装 systemd,快速试跑)

```bash
python -m venv .venv && ./.venv/bin/pip install -e .
POLYTRADER_BASKET_DB=data/basket.db POLYTRADER_PAPER_DB=data/paper.db \
  ./.venv/bin/polytrader-scanner
```
