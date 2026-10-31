# 2026 年 10 月 TAS1 与 VIC1 分析

本报告只分析用户上传的两份 AEMO CSV，不代表实时数据，也未与最新在线文件复核。网页 prototype/index.html 仍为模拟数据。

## 数据与口径

实际列为 REGION、SETTLEMENTDATE、TOTALDEMAND、RRP、PERIODTYPE；两州各 8,928 行，全部为 TRADE。原始记录覆盖 2026-10-01 00:05 至 2026-11-01 00:00，5 分钟频率完整，两个区域逐时间对齐。验证未发现重复键、空值、缺失区间或月外记录。

RRP 为批发区域参考价格（AUD/MWh），TOTALDEMAND 为区域需求（MW）。平均电价为各 5 分钟 RRP 等权平均；标准差使用样本标准差。月均不按需求加权。日汇总采用区间结束时间减 5 分钟后的日期。保留负电价，没有平滑或剔除极端值。图片展示日均，不能用它判断区间峰值。

## 统计结果

| 指标 | TAS1 | VIC1 |
|---|---:|---:|
| 平均批发价 AUD/MWh | 61.59 | 52.94 |
| 价格中位数 AUD/MWh | 88.14 | 55.52 |
| 最低区间价 AUD/MWh | -157.83 | -365.23 |
| 最高区间价 AUD/MWh | 359.12 | 406.11 |
| 价格标准差 AUD/MWh | 55.54 | 64.04 |
| 95% 分位价格 AUD/MWh | 122.77 | 144.46 |
| 负电价区间占比 | 18.66% | 26.97% |
| 平均需求 MW | 978.07 | 4,885.05 |
| 最大区间需求 MW | 1,281.83 | 7,367.24 |
| 需求加权价格 AUD/MWh | 64.15 | 60.28 |

需求加权价格 = Σ(RRP × TOTALDEMAND) / Σ(TOTALDEMAND)，只作为补充描述，不是零售电费或真实购电合同成本。需求的平均值和最大值都是功率；本报告没有把 MW 相加后称为电量。

## 价差如何解释

价差定义为同一时间 TAS1 RRP − VIC1 RRP。8,928 对区间的平均价差为 **+8.65 AUD/MWh**，价差中位数为 **+0.59 AUD/MWh**。最小为 -239.31，最大为 +350.05。塔州更贵的区间占 57.35%，相同占 1.84%，其余约 40.82% 为维州更贵。

因此可写：“在这两份 2026 年 10 月文件中，塔州的区间等权平均批发价高于维州，但逐区间的价格高低会变化。”维州负电价更频繁、最低价格更低，价格标准差也更大；这些是观察到的分布差异，不能据此确定发电结构或网络约束造成了价差。

维州平均需求约为塔州的 5 倍，这描述区域规模差异。两州平均需求与平均价格的排序不足以证明需求导致价格上升或下降，也不能据此判断人均用电或能源效率。

## 结论边界与后续研究

仅靠价格和需求两列，不能确定价差由水电、风光、Basslink 输电约束、机组故障、天气或市场报价造成。要研究原因，需要加入同期发电结构、跨区潮流及约束、机组可用性、天气和报价等数据，并建立明确的比较方法。相关性与同日出现都不是因果证据。

本月均价差也不代表全年、未来或两州居民电费差。批发价与家庭账单属于不同口径。

## 来源与复现

- 输入：用户上传的 PRICE_AND_DEMAND_202610_TAS1.csv 和 PRICE_AND_DEMAND_202610_VIC1.csv，原样保存在 data/raw；文件摘要见 quality_report.json。
- [AEMO 官方聚合价格和需求数据入口](https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/aggregated-data)。
- [AEMO NEM 数据仪表板及字段说明](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/data-dashboard-nem)：RRP 为现货价字段；不要把网页其他需求定义直接等同于本 CSV 的 TOTALDEMAND。
- [AEMO 报告的 NEM 时间说明](https://www.aemo.com.au/Electricity/National-Electricity-Market-NEM/~/-/media/F1314EB879E544708E29A5C04CF0111E.ashx)：AEST，不随夏令时变化。

运行 scripts/process_data.py 会重新生成所有派生 CSV、质量报告与图片；不会更新本手写分析文字。换输入后请重核报告数值。本次输入完整，若将来存在缺失，脚本会报告数量，月均仅代表可用区间，不能再声称完整月。

实际验证环境：Python 3.12.14，pandas 2.2.3，matplotlib 3.11.2。
