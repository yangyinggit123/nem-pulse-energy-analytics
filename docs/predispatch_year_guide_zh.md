# 全年 AEMO 预调度数据

已对齐 2025-11-01 至 2026-10-31，共 365 天，TAS1、VIC1 各 8,760 小时。

## 本地成果

- 数据库：`data/nem_pulse.db`
- 完整小时特征表：`predispatch_hourly_features`，17,520 行。
- 默认模型输入视图：`predispatch_hourly_model_input`，17,514 行。
- 全年导出：`data/processed/predispatch_year_features.csv`。
- 下载清单与 SHA-256：`data/predispatch_year_download_manifest.json`。
- 年度质量检查：`reports/predispatch_year_quality.json`，每月检查与数据另行保存。
- 原始实际价格与需求保持 210,240 行。

## 边界情况

第一小时之前没有观测数据，两州首行的上一小时价格、需求为空，未填补。
2026-03-10 19:00 和 20:00 两个预测时点的最新可选报告分别已生成约 117、177 分钟，涉及两州共四行。保留完整表，但默认模型输入视图排除报告年龄超过 60 分钟的记录。这个阈值是项目约定，不是官方标准。排除记录后，不可简单按行 shift 构造滞后特征；应在连续历史小时数据上先构造滞后项，再按时间连接。

所有报告生成时间均不晚于预测时点，但生成时间仍只是实际发布时间的代理，尚未核实送达延迟。`actual_hour_mean_label` 是预测目标，禁止作为输入。

## 复现

在项目根目录执行：

```bash
python3 scripts/download_predispatch_year.py
python3 scripts/build_predispatch_year.py
```

前提是已有全年 `price_demand` 表及 `data/predispatch_year_download_plan.json`。下载器复用已验证文件，构建器按月保存检查点。原始 ZIP 与数据库留在本地。

## 下一阶段

本轮扩充数据，没有重新训练或更新线上误差指标。后续按时间训练与回测，比较相同时间段的基准、AEMO 参考和新模型。九月、十月已用于此前实验，不再宣称为未见独立测试；全年仍只有一个季节周期。
V0.5 将结合模拟零售商客户负荷与对冲假设估算成本风险；V1.0 自动化下载、检查及报告。
