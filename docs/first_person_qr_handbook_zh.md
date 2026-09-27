# A股电池产业链 Systematic Equity QR：第一人称从零到完成全流程手册

## 开场：我先决定自己到底在做什么岗位的工作

我不能因为用了 Python、回归和蒙特卡洛，就说自己在做 Quant。岗位性质取决于我服务的决策、使用的数据频率和最后交付的东西。

旧项目围绕宁德时代一家公司展开：我解释收入、股价共同因子、同业经营位置和材料成本风险。那是量化工具辅助的 Equity Research。它有价值，但不是系统化选股。

如果我要把后续项目做成真实的 Quant Research，我必须改变的不是措辞，而是研究对象：

> 我每个月面对一个当时可投资的股票横截面，用执行前可得的信息形成信号，预测下一期相对收益，再把信号转成带风险、换手、容量和成本约束的组合，最后让未参与开发的数据决定模型能不能继续。

这就是我选择的岗位方向：

> **Systematic Equity Quantitative Research，月频、中频、A股电池产业链横截面选股与基准增强。**

我不把它叫 Quant Trader。因为我没有逐笔成交、盘口、订单状态、排队位置、成交概率、做市库存、实盘订单或真实 P&L。月度交易成本建模是严谨 QR 的一部分，但不能把我变成 QT。

我还要先把时间线说清楚：当前公开仓库和系统化结果是在 2026 年独立重建的，研究信息截止到 2025 年 8 月 29 日。截止日表示模型不许看后面的数据，不表示代码在 2025 年已经存在。公开项目不是 UBS 交付物，不能倒写进 2025 年实习。

---

# 第一章：我先把模糊任务变成可以证伪的研究问题

## 1.1 我不是先打开 Python

如果我一上来就下载数据，我会立即遇到这些问题：

- 我要预测 CATL，还是预测一组股票？
- 预测绝对收益还是相对收益？
- 持有一天、一周还是一个月？
- 信号什么时候计算，什么时候交易？
- 用今天的成分股回看过去，还是重建历史股票池？
- 一个因子 Rank IC 为正，是否就可以交易？
- 长短组合在 A 股真的能借到券吗？

所以我先写研究任务书：

> 在电池主题的历史股票池中，每个月用执行日前可得的价格和财务信息，对下一月相对收益进行横截面排序；先检验信号，再检验加入风险、换手、容量和交易成本后的纯多头基准增强组合。

我的目标变量是：

\[
y_{i,t+1}=R_{i,t\rightarrow t+1}-R_{b,t\rightarrow t+1}.
\]

这里：

- \(i\) 是股票；
- \(t\) 是本月月末执行日；
- \(R_i\) 是股票从本月执行收盘到下月执行收盘的收益；
- \(R_b\) 是同一时期电池主题基准组合收益。

这一行公式改变了整个项目。CATL 不再是唯一研究对象，只是历史股票池中的一个公司。我的任务也不再是“解释 CATL”，而是“形成可重复的股票排序和主动权重”。

## 1.2 我先写经济假设，不先看回测答案

我注册四类简单、可解释的假设：

1. 价格动量：中期信息扩散可能使强者继续相对走强；
2. 经营质量：盈利能力强、杠杆低的企业可能更有韧性；
3. 基本面动量：经营改善可能比静态高质量更有信息；
4. 低风险：高波动主题中，低总波动和低特质波动可能有更好的风险调整表现。

我故意不用复杂机器学习作为第一版。样本只有几十个月，股票池每月约 50 只。随机森林、XGBoost 或神经网络可以拟合出更漂亮的样本内结果，却很难区分真实结构和噪声。我先要求线性、透明、可诊断的基线通过，再谈复杂模型。

## 1.3 我预先定义什么叫失败

我在 `docs/signal_registry.md` 里写下：如果最终留出期出现以下任何核心问题，综合信号就不能叫 validated alpha：

- 平均 Rank IC 非正；
- top-minus-bottom 收益非正；
- 纯多头组合净主动收益或信息比率非正；
- 双倍成本后结果非正；
- 多滞后一个交易日后结果失败；
- 结果由单一公司或行业组支配；
- 使用了公告前或成分可得日前的数据。

这样做的目的，是防止我看完结果后把“成功”重新定义成模型刚好做到的事情。

---

# 第二章：我设计仓库，而不是把所有代码塞进一个 notebook

## 2.1 我为什么分文件

我把“数据、特征、统计、组合、报告”分开，因为它们有不同责任：

```text
config/systematic.yaml
        ↓
systematic_data.py
        ↓
systematic_features.py
        ↓
systematic_evaluation.py
        ↓
systematic_portfolio.py
        ↓
systematic_pipeline.py
        ↓
reports / figures / summary
```

如果所有东西写在 notebook 里，我很容易不小心让后面单元格修改前面对象，或者只运行部分单元格得到不可复现结果。模块化以后：

- 数据下载函数不知道信号结果；
- 特征函数不知道未来收益好不好；
- 评估函数只接受面板和列名；
- 组合函数只接受冻结的分数、风险和成本参数；
- 流水线负责调用顺序和输出文件。

## 2.2 正确的文件创建顺序

Git 只能证明提交历史，不能证明我脑中每一步的先后。下面是按依赖关系重建的正确施工顺序：

1. `config/systematic.yaml`：冻结时钟、样本切分、参数和成本；
2. `docs/signal_registry.md`：在第一次端到端回测前登记假设和失败条件；
3. `data/manual/systematic_industry_groups.csv`：记录分组、排除项和理由；
4. `systematic_data.py`：下载历史成分、行情和财务数据；
5. `data/source_manifest.json`：记录来源、参数、抓取时间和哈希；
6. `systematic_features.py`：建立 point-in-time 特征和未来标签；
7. `systematic_evaluation.py`：IC、HAC、FDR 和分组收益；
8. `systematic_portfolio.py`：权重、风险、换手、容量和成本；
9. `systematic_pipeline.py`：端到端生成面板、表格、图片和总结；
10. `tests/test_systematic_*.py`：验证时间、公式、成分切换和 NAV；
11. `README.md`、方法文档和面试手册：只能在结果真实生成后写数字。

第 11 步放最后很重要。如果我先写简历数字，再去改代码配合它，就是先画靶后射箭。

---

# 第三章：我先挖数据资产，不先挖因子

## 3.1 第一个数据问题是历史股票池

真实研究不能拿今天的股票名单回看过去。这样会漏掉后来退市、被剔除或经营失败的公司，形成幸存者偏差。

我想要的是 CSI 新能源动力电池主题的历史成分，但公开接口没有稳定的不可变历史成分数据库。我因此寻找可以审计的代理，选择跟踪该指数的 ETF 561910 历史持仓披露。

我每年抓取 Q2 和 Q4，按披露权重保留前 50 名。但报告期末不是投资者知道名单的时间，所以我设置：

- Q2 6 月 30 日快照，60 个自然日后才能用；
- Q4 12 月 31 日快照，90 个自然日后才能用。

在任何信号日 \(s\)，我只选择同时满足

\[
snapshot\_date\le s,
\]

\[
available\_date\le s
\]

的最新快照。

这不是官方历史成分，可能存在 ETF 跟踪差异，但它比“用今天的 50 只股票回看三年”更诚实。

## 3.2 我为什么保留退市公司

300116 后来退市，Yahoo 没有返回可用历史。如果我因为下载麻烦而删除它，模型就会事后知道这是一家失败公司。

我加了腾讯/AkShare 备用行情：

- 不复权价格用于原始价格和成交额；
- 后复权价格用于收益；
- 它在历史成分期间继续参加信号和组合；
- 退出股票池时，旧持仓必须卖出并计入成本。

这一步比“多一个股票样本”更重要，因为它证明我理解幸存者偏差如何进入代码。

## 3.3 我为什么排除北交所股票

920185 在持仓历史里，但北交所交易制度、流动性和公共行情覆盖与沪深基线不同。我在看因子结果前按数据可比性排除它，同时在手工映射和原始持仓中保留记录。

我不能说自己完全没有选择偏差；我能做的是让排除规则可见、事前、可复核。

## 3.4 行情数据为什么要同时保留 raw 和 adjusted

如果股票分红或拆股，原始收盘价会跳变。收益必须使用复权收盘价：

\[
r_{i,d}=\frac{P^{adj}_{i,d}}{P^{adj}_{i,d-1}}-1.
\]

但成交额应该使用原始价格和原始成交量：

\[
Amount_{i,d}=P^{raw}_{i,d}\times Volume^{raw}_{i,d}.
\]

我不能拿后复权价格乘当前成交量估计真实成交额。于是市场表同时保留 raw OHLCV、adjusted OHLCV 和 adjustment factor。

## 3.5 财务数据的核心不是 report date，而是 notice date

一份 2024 年年报的 `report_date` 是 2024-12-31，但市场可能到 2025 年 3 月才看到。如果我按会计期合并，模型会提前几个月知道答案。

所以每条记录至少保留：

- `report_date`：描述哪个会计期间；
- `notice_date`：哪天公告；
- `available_date`：我保守允许使用的日期。

有效日期是 notice 和 available 中更晚的一个。信号日只能选择有效日期已经到达的最新版本。

我要诚实承认：公共供应商可能后来重述历史数据，而不提供完整版本历史。公告日过滤能阻止明显前视，不能替代 Wind/Bloomberg 真正的 point-in-time snapshot。

## 3.6 我怎样留下数据血缘

`data/source_manifest.json` 记录：

- provider 和 URL；
- 请求的时间区间、股票列表和参数；
- 抓取时间；
- 行数；
- dataframe SHA-256；
- 主源和备用源；
- 排除项。

原始 parquet 太大，不提交 GitHub，但哈希让我能判断两次下载是否完全一致。公开 API 将来可能变化，所以“代码可重跑”和“未来一定得到相同原始数据”不是一回事。

---

# 第四章：我把日频数据变成严格的月频研究时钟

## 4.1 三个日期不能混

每个月我定义：

- `execution_date`：本月最后一个交易日；
- `signal_date`：执行日前一个交易日；
- `next_execution_date`：下月最后一个交易日。

特征只看到 `signal_date`。标签使用 execution close 到 next execution close。

例如 2024-01-31 是执行日，2024-01-30 是基线信号日，2024-02-29 是下一个执行日。1 月 31 日收盘价可以进入标签起点，但绝不能进入 1 月 30 日计算的动量和波动率。

我专门写测试：如果只修改执行日收盘价，信号特征必须不变，未来收益标签必须变化。这比在文档里写“无前视”更可信。

## 4.2 为什么最后一个月没有标签

研究截止日是 2025-08-29。8 月可以形成信号横截面，但截止日前没有 9 月月末价格，所以它没有下一月标签。

我保留这行面板以证明时钟完整，但评估和回测自动删除没有 forward return 的月份。不能把它补成 0，也不能偷偷下载 9 月数据。

---

# 第五章：我开始因子研究，但每个因子先有经济理由

## 5.1 价格动量

12–1 动量：

\[
MOM^{12-1}_{i,t}=\log\left(\frac{P_{i,t-21}}{P_{i,t-252}}\right).
\]

6–1 动量：

\[
MOM^{6-1}_{i,t}=\log\left(\frac{P_{i,t-21}}{P_{i,t-126}}\right).
\]

我跳过最近约 21 个交易日，是为了减少短期反转和微观结构噪声。两个窗口等权平均，避免只依赖一个任意期限。

替代方案包括 12 个月不跳过、1 个月反转、指数加权趋势或残差动量。我没有在 final holdout 里轮流尝试它们，因为那会把留出集变成调参集。

## 5.2 总波动率

最近 63 日：

\[
\sigma^{63}_{i,t}=sd(r_{i,d})\sqrt{252}.
\]

至少需要 50 个有效日。年化只改变单位，不创造预测能力。

## 5.3 市场 beta 和特质波动率

最近 126 个对齐交易日：

\[
r_{i,d}=\alpha_i+\beta_i r^{510300}_d+\epsilon_{i,d}.
\]

斜率是 beta：

\[
\hat\beta_i=\frac{Cov(r_i,r_m)}{Var(r_m)}.
\]

残差年化波动率是：

\[
\sigma^{idio}_{i,t}=sd(\epsilon_{i,d})\sqrt{252}.
\]

beta 用于风险控制，不进入 alpha。低风险家族使用总波动率和特质波动率的负值。

## 5.4 流动性和 Amihud

20 日平均成交额：

\[
ADV20=mean(P^{raw}\times Volume^{raw}).
\]

Amihud：

\[
ILLIQ=mean\left(\frac{|r|}{P^{raw}V}\right).
\]

ADV 负责：

- 过滤日均成交额低于 5000 万元的股票；
- 作为中性化控制；
- 计算 1 亿元 AUM 下的参与率。

Amihud 在当前基线是诊断变量，不进入综合 alpha。

## 5.5 经营质量

如果有完整资产负债表和现金流，我更愿意用 gross profitability、accrual quality 和 leverage-to-assets。公共冻结数据没有完整字段，所以使用明确的 fallback：

\[
Q=\frac{ROE+GrossMargin+NetMargin-DebtRatio}{4}.
\]

百分数先除以 100。这个 raw quality 不是“公司得分 80 分”，只是横截面描述符，后面还要稳健标准化。

这个定义的弱点是四个百分比的经济尺度不同，而且供应商定义可能变化。它后来在最终留出期没有验证成功，这个结果必须保留。

## 5.6 基本面动量

我先计算最新可得报告相对上年同期的收入和利润增长：

\[
Growth=\frac{RevenueYoY+ProfitYoY}{2}.
\]

再计算质量变化：

\[
\Delta Q=Q_t-Q_{t-1y}.
\]

基本面动量家族是二者的横截面标准化分数平均。

为什么不直接用 CATL 的 2025H1 增速？因为真正系统化因子要求每家公司、每个月遵守同一公告日规则。

---

# 第六章：我必须把不同量纲变成可比较的横截面分数

## 6.1 为什么普通 z-score 不够

电池产业链存在亏损、重组和退市公司。利润增长可能从负数变正数，产生极端百分比。直接均值和标准差容易被一家公司拖走。

我先用中位数和 MAD：

\[
m=median(x),
\]

\[
MAD=median(|x-m|),
\]

\[
s_{robust}=1.4826\times MAD.
\]

把数据裁剪在 \(m\pm5s_{robust}\)，再用裁剪后的均值和总体标准差做 z-score。

1.4826 使正态分布下 MAD 与标准差大致同尺度。MAD 为 0 时回退普通标准差；整个横截面常数时给 0，而不是除以 0。

## 6.2 为什么要控制 ADV 和产业组

假设高动量股票刚好全是高流动性设备股。回测成功时，我无法区分动量和流动性/行业暴露。

每个月，我做横截面回归：

\[
z(x_i)=a+b\bigl(\log ADV_i-mean(\log ADV)\bigr)+\sum_g\gamma_gD_{i,g}+u_i.
\]

我取残差 \(u_i\)，再标准化成均值 0、标准差 1。

我同时放入 ADV 和 group dummies，而不是先行业去均值再回归 ADV，因为顺序处理可能重新引入已经去掉的暴露。

中性化只说明线性暴露接近 0，不说明因子变成了 alpha。

## 6.3 四个家族怎样组合

\[
S^{mom}=mean(z(MOM^{12-1}),z(MOM^{6-1})),
\]

\[
S^{quality}=z(Q),
\]

\[
S^{fundmom}=mean(z(Growth),z(\Delta Q)),
\]

\[
S^{lowrisk}=-mean(z(\sigma^{63}),z(\sigma^{idio})).
\]

综合分数：

\[
S^{comp}=0.25S^{mom}+0.25S^{quality}+0.25S^{fundmom}+0.25S^{lowrisk}.
\]

为什么等权？因为用短样本估计 IC 最优权重会严重过拟合。我宁可让基线简单、可解释、可能失败，也不要让权重记住历史噪声。

---

# 第七章：我用时间顺序切分，而不是随机 train/test split

## 7.1 三段时间

- design：截至 2023-06-30，共 15 个有标签月份；
- validation：2023-07 到 2024-06，共 12 个月；
- final holdout：2024-07 到 2025-08 截止，共 13 个有标签月份。

随机打乱会让未来市场状态进入训练，也无法检验 regime change。时间切分更接近真实流程：我先在过去设计，再向未来走。

## 7.2 final holdout 看过以后就不再 untouched

我现在已经知道 final holdout 的结果。以后如果我改成只做 low risk，或者把 momentum 权重降为 0，我不能继续把 2024-07 到 2025-08 称作未见数据。新模型必须登记新实验，并等待新的未来区间。

这是研究诚信中非常容易被忽略的一点。

---

# 第八章：我先检查信号，再检查组合

## 8.1 每月 Rank IC

每个月，我计算信号和下一月超额收益的 Spearman 秩相关：

\[
IC_t=Corr(rank(S_{i,t}),rank(y_{i,t+1})).
\]

如果 IC 为 0.1，意思不是收益提高 10%，而是高分与高收益的排序存在弱正相关。

我同时保留 Pearson IC，看线性关系是否完全不同，但 Rank IC 是主要诊断。

## 8.2 ICIR

\[
ICIR=\frac{mean(IC_t)}{sd(IC_t)}.
\]

它衡量平均排序能力相对月度不稳定程度。这里没有乘 \(\sqrt{12}\)，所以要按代码定义解释，不能随意称为年化 ICIR。

## 8.3 HAC 均值检验

月度 IC 可能有自相关和异方差。我用只有常数项的 OLS：

\[
IC_t=\mu+e_t
\]

对 \(\hat\mu\) 使用 3 lag Newey–West/HAC 标准误。HAC 只修正推断，不会修复错误因子或小样本。

## 8.4 FDR

我同时检验 5 个分数：4 个家族加综合。多个 p-value 会增加偶然显著。我在每个时间段内使用 Benjamini–Hochberg 调整。

它只能控制我登记的 5 个测试。如果我私下试过 100 个版本只报告最好一个，FDR 也救不了。

## 8.5 分组收益

每个月按分数排序，样本足够时分五组，不足时分三组。诊断价差是：

\[
Spread_t=mean(R_{top,t})-mean(R_{bottom,t}).
\]

这是研究诊断，不是可执行 A 股多空策略，因为我没有历史融券可得性、借券费和召回数据。

## 8.6 真实结果怎样读

最终留出期综合分数：

- 平均 Rank IC：0.0467；
- HAC p-value：0.1665；
- FDR p-value：0.2081；
- 正 IC 月份比例：53.8%；
- top-minus-bottom：每月 -0.8728%。

为什么 Rank IC 为正，价差却为负？

Rank IC 只看顺序，不看收益大小。多数股票可能略微排序正确，但 top 组中少数大幅下跌可以把经济价差拉成负数。

所以我不能只挑 0.047 说“因子有效”。真正关系到资金的是收益幅度和组合。

## 8.7 validation 为什么看起来很漂亮

validation 期间综合 Rank IC 约 0.172，价差约每月 +2.77%；价格动量 Rank IC 约 0.163。

final holdout 中价格动量 Rank IC 变成 -0.060，价差约 -2.35%。这说明 validation 的结构没有延续，可能是市场 regime 改变，也可能是短样本噪声。

如果我只报告 validation，就是典型的选择性报告。

---

# 第九章：我把分数转成一个真正可以审计的纯多头组合

## 9.1 为什么不用诊断多空组合做简历 P&L

A 股历史融券供应不稳定。没有借券数据时，我只能把 long-short 当信号形状诊断。

可执行层采用 long-only benchmark enhancement：从电池主题基准权重出发，做小幅主动偏离。

## 9.2 指数型分数倾斜

设基准权重为 \(b_i\)，综合分数为 \(s_i\)：

\[
\tilde w_i=b_i\exp(0.35s_i).
\]

指数函数有两个优点：

- 单调：高分得到更高权重；
- 正值：不会直接产生负权重。

0.35 是固定 tilt intensity，不是看到回测后优化出的参数。

## 9.3 我先保留产业组权重

每个宽泛产业组，我把 raw weights 重新缩放到该组基准权重。然后求解：

\[
\min_w\sum_i(w_i-\tilde w_i)^2
\]

约束：

\[
\sum_iw_i=1,
\]

\[
w_i\ge0,
\]

\[
w_i\le12\%,
\]

\[
|w_i-b_i|\le3\%,
\]

以及每个产业组权重等于基准组权重。

SciPy SLSQP 求解。如果求解失败，我退回基准，不使用不可行结果。

这不是完整 mean-variance optimizer，因为我没有可靠的预期收益率单位。它是透明的分数倾斜加约束投影。

## 9.4 协方差收缩

我用最近 126 日收益估计样本协方差，再向对角线收缩 35%：

\[
\Sigma^{shrunk}=0.65\Sigma^{sample}+0.35diag(\Sigma^{sample}).
\]

为什么？50 只股票、126 天，非对角协方差噪声很大。收缩牺牲一些精细结构，换取稳定性。

主动跟踪误差：

\[
TE=\sqrt{(w-b)^\top\Sigma(w-b)}.
\]

如果超过 10%，我把主动权重整体缩回基准。主动 beta：

\[
\beta^{active}=(w-b)^\top\beta.
\]

绝对值不能超过 0.10。

## 9.5 换手和容量

漂移后旧权重是 \(w^{old}\)，新目标是 \(w^{target}\)：

\[
Turnover=\frac12\sum_i|w_i^{target}-w_i^{old}|.
\]

上限为每月 25%。假设 AUM 为 1 亿元，每只股票单次交易不得超过 ADV20 的 5%。如果最紧的股票只能完成目标交易的 40%，整个可选交易向量都缩到 40%，避免挑着成交后改变组合意图。

## 9.6 成分股退出不能凭空消失

一个重要代码风险是：新月份先把旧持仓 reindex 到新股票池，退出股票会直接丢失，资产、换手和卖出成本都消失。

正确做法：

1. 旧持仓和新股票池取 union；
2. 退出股票目标权重明确设为 0；
3. 卖出计入 trade ledger；
4. 收取佣金、价差、印花税和冲击；
5. 卖出所得先进入现金，再为新买入提供资金；
6. 月末 NAV 必须和净收益精确对账。

仓库有专门单元测试验证这一点。

---

# 第十章：我把交易成本写成公式，而不是随手减 20 bps

## 10.1 线性成本

对股票权重变化 \(\Delta w_i\)：

\[
C_{commission}=\sum_i|\Delta w_i|\frac{3}{10000},
\]

\[
C_{spread}=\sum_i|\Delta w_i|\frac{5}{10000}.
\]

卖出印花税：

\[
C_{stamp}=\sum_i\max(-\Delta w_i,0)\frac{d_t}{10000}.
\]

2023-08-28 前 \(d_t=10\) bps，之后为 5 bps。

## 10.2 非线性冲击

参与率：

\[
p_i=\frac{|\Delta w_i|\times AUM}{ADV20_i}.
\]

冲击率：

\[
c_i^{impact}=0.25\sigma_i^{daily}\sqrt{p_i}.
\]

冲击成本：

\[
C_{impact}=\sum_i|\Delta w_i|c_i^{impact}.
\]

平方根结构表达：交易越大，边际冲击上升，但不是简单线性。0.25 是假设参数，不是用真实成交校准的，因此必须做 0.5 倍和 2 倍成本敏感性。

## 10.3 成本怎样付

如果组合目标权重加成本超过 100%，我不能默许负现金借款。算法按比例缩小风险资产，重新计算交易和成本，直到：

\[
\sum_iw_i+Cash+Cost=1.
\]

下一期持仓再按股票收益漂移。每个月都检查：

\[
EndingNAV=1+NetReturn.
\]

不对账就报错。

---

# 第十一章：我怎样逐月跑回测

对每个 execution month，我按以下顺序执行：

1. 取得当时可用股票池；
2. 删除没有 forward return 或 composite score 的股票；
3. 读取并归一化 benchmark weights；
4. 将上月持仓按已实现收益漂移；
5. 找出本月退出股票并强制卖出；
6. 用综合分数生成 raw tilt；
7. 做产业组、个股和主动权重约束投影；
8. 估计当时可得的 126 日收缩协方差；
9. 按 TE 和 active beta 缩放主动权重；
10. 按 turnover 和 ADV 容量缩放交易；
11. 计算佣金、价差、印花税和冲击；
12. 用现金支付成本，必要时缩小风险资产；
13. 计算股票组合 gross return；
14. 减成本得到 net return；
15. 计算 benchmark return 和 active return；
16. 保存 weights、trades、cost components 和风险指标；
17. 更新月末漂移权重，进入下个月。

这个顺序说明为什么 `systematic_portfolio.py` 不能只写一行 `score.rank()`。真实 QR 结果必须穿过资金约束和状态转移。

---

# 第十二章：我如何判断回测，而不是只看累计净值

## 12.1 绝对收益和主动收益

最终留出期，策略年化净收益约 47.74%，电池主题基准约 48.14%。如果我只写 47.7%，会显得非常好，但真实主动收益是：

\[
47.74\%-48.14\%=-0.41\%.
\]

高绝对收益来自主题行情，不是 alpha。

## 12.2 信息比率

月度主动收益：

\[
a_t=R^{net}_{strategy,t}-R_{benchmark,t}.
\]

\[
IR=\frac{mean(a_t)}{sd(a_t)}\sqrt{12}.
\]

最终留出期 IR 约 -0.43。负数说明承担主动波动没有得到正主动回报。

## 12.3 回撤

净值 \(V_t\) 的回撤：

\[
DD_t=\frac{V_t}{\max_{s\le t}V_s}-1.
\]

最大回撤是最小的 \(DD_t\)。它衡量从历史峰值跌了多少，但不能单独证明 alpha。

## 12.4 成本和换手

最终留出期：

- 平均单边换手约 5.37% 每月；
- 年化算术成本拖累约 0.17%；
- 有 6 个月发生强制成分退出；
- 双倍成本时年化主动收益约 -0.66%。

成本不是失败的唯一原因；gross active 也没有足够优势。

---

# 第十三章：我做稳健性检查，并接受同一个负结论

## 13.1 额外一个交易日滞后

基线在执行前 1 个交易日截断信息。稳健性版本在前 2 个交易日截断，但仍在相同月末执行，收益窗口不变。

结果：

- 综合 Rank IC 约 0.042；
- top-minus-bottom 每月约 -1.15%；
- 年化主动收益约 -0.45%；
- IR 约 -0.44。

说明结果不是靠最后一个信号日变正，但经济表现仍然失败。

## 13.2 个股贡献集中度

我将每只股票每月的 gross active contribution 写成：

\[
Contribution_{i,t}=(w_{i,t}-b_{i,t})R_{i,t+1}.
\]

在最终留出期，CATL 是绝对贡献最大的单一股票，但占全部绝对个股贡献约 7.1%。最大单票主动权重约 1.52%，最大产业组主动权重约 0.015%。

所以失败不是“被 CATL 一只股票拖累”这么简单。这个贡献审计不是完整的 leave-one-out 重新优化，我不能把它说成精确反事实。

## 13.3 为什么我不继续调到成功

我已经打开 final holdout。如果我现在：

- 删除 momentum；
- 只保留 low risk；
- 改权重；
- 调 score tilt；
- 换切分点；
- 删除表现差的公司；

然后继续在同一留出期报告结果，我就是在训练留出集。

正确做法是把当前实验标记失败。新的 low-risk-only 或 valuation-enhanced 模型必须登记新 ID，并等待新数据。

---

# 第十四章：最终结论是什么

我得到的不是“电池行业没有 alpha”，也不是“所有这些因子永久无效”。我的结论只针对当前定义、数据和样本：

> 等权组合的价格动量、经营质量、基本面动量和低风险信号，在 validation 中表现较强，但没有在 13 个月 final holdout 中转化为正的极端组收益和正的成本后主动收益，因此不能作为持续 alpha 或生产候选。

单因子里 low risk 的留出表现相对最好，但这是看完 holdout 后发现的研究线索，不是已经验证的新策略。

这个结果对 QR 面试有价值，因为我能说明：

- 为什么定义 target；
- 为什么重建历史 universe；
- 如何处理公告时间和退市；
- 因子怎样形成；
- IC 为什么不等于 P&L；
- 组合怎样受风险和成本约束；
- 为什么 validation 成功不够；
- 什么情况下我必须拒绝模型。

---

# 第十五章：旧 CATL 项目现在放在哪里

旧模块保留为 economic context：

- 量价桥解释 2024 收入由销量还是 ASP 驱动；
- 市场/同业/锂价回归解释同期共同波动；
- 六家公司评分描述经营相对位置；
- 材料成本和传导率网格提供条件情景。

它们不能改名为 alpha：

- 78 周 held-out attribution 的系数只用过去估计，但评价周输入的是评价周已经实现的市场、同业和锂价收益，所以是条件归因稳定性，不是事前预测；
- 经营评分只有很小的公司横截面和三个前向观察；
- 锂价 AR(1) 相对随机游走改进很小；
- 材料 beta 和客户传导率是情景假设。

新系统化项目把“经营好不等于股票未来收益高”扩展到更宽股票池，并得到一个不支持综合 alpha 的结果。

---

# 第十六章：我怎样实际运行项目

## 16.1 环境

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

`pyproject.toml` 固定 pandas、NumPy、SciPy、statsmodels、matplotlib、AkShare、yfinance 和 PyArrow 等版本，减少环境漂移。

## 16.2 下载

```bash
make systematic-download
```

这会：

1. 下载 ETF 历史持仓；
2. 根据 include map 得到需下载证券；
3. 用 Yahoo 下载 raw/adjusted OHLCV；
4. 对缺失沪深股票使用腾讯 fallback；
5. 下载公告日财务数据；
6. 写入三个 raw parquet；
7. 更新 source manifest 和 hashes。

如果缺少必需股票，程序报错，不静默继续。

## 16.3 研究流水线

```bash
make systematic-run
```

它会生成：

- baseline 月度面板；
- lag2 稳健性面板；
- monthly IC；
- signal summary；
- quantile returns；
- 0.5×/1×/2× cost portfolio；
- weights 和 trades；
- active contribution；
- figures；
- `reports/systematic_summary.json`；
- systematic research report。

## 16.4 测试

```bash
make test
```

当前 26 个测试覆盖：

- 成分公布延迟；
- Yahoo raw/adjusted 对齐；
- 腾讯退市 fallback；
- 财报 cutoff；
- 哈希顺序独立；
- 动量、波动、beta、流动性公式；
- 执行日不进入特征；
- 财报版本和成分 point-in-time；
- MAD 和中性化；
- 时间切分；
- IC、FDR 和分组收益；
- 权重约束、风险缩放和成本；
- 成分退出卖出及 NAV 对账；
- 端到端输出可重复。

测试通过不等于生产验证完成，但测试失败时我没有资格相信回测。

---

# 第十七章：每个输出文件告诉我什么

| 文件 | 我用它回答的问题 |
|---|---|
| `systematic_monthly_ic.csv` | 每个月每个因子的横截面排序表现 |
| `systematic_signal_summary.csv` | 各时间段平均 IC、ICIR、HAC 和 FDR |
| `systematic_quantile_returns.csv` | 每个月各分组和 top-bottom 收益 |
| `systematic_quantile_summary.csv` | 分组收益的长期汇总 |
| `systematic_portfolio_monthly.csv` | 每月 gross/net/benchmark、换手、风险和成本 |
| `systematic_portfolio_weights.csv` | 每只股票目标、实际和主动权重 |
| `systematic_portfolio_trades.csv` | 每月交易、金额、ADV 和强制退出 |
| `systematic_portfolio_summary.csv` | 不同成本倍数和时间段的绩效 |
| `systematic_lag2_*.csv` | 额外信号滞后的稳健性 |
| `systematic_active_contribution_by_name.csv` | 最终留出期个股贡献集中度 |
| `systematic_summary.json` | 机器可读的唯一数字口径和失败结论 |
| `systematic_research_report.md` | 人类可读报告 |

如果 README、简历和 summary 数字不一致，我以重新生成的 summary 和 CSV 为准，并修改陈旧文案。

---

# 第十八章：如果 mentor 让我白板推导，我怎样讲

我按下面的顺序画：

```text
历史可投资股票池 U_t
        ↓
执行前信息集 I_t
        ↓
raw descriptors
        ↓
MAD clipping + z-score
        ↓
ADV / group neutralization
        ↓
4 family scores + equal-weight composite
        ↓
next-month excess-return label
        ↓
design → validation → final holdout
        ↓
IC / HAC / FDR / quantile spread
        ↓
benchmark-relative long-only weights
        ↓
TE / beta / turnover / ADV constraints
        ↓
commission / spread / stamp / impact
        ↓
net active return / IR / failure gate
```

然后我主动指出两个最容易被追问的地方：

1. Universe 是延迟 ETF 持仓代理，不是官方历史指数；
2. final holdout 只有 13 个月，所以任何正结果也只能叫 preliminary。

最后我说结果失败，而不是等面试官发现：

> Composite Rank IC was mildly positive, but the holdout spread and cost-aware active return were negative, so I rejected the signal.

---

# 第十九章：简历应该怎样放

我不能把 2026 年仓库放在 UBS 2025 经历下面，让读者以为当时交付了这些模型。

推荐放在 `Selected Projects`：

> **A-Share Battery-Value-Chain Systematic Equity Research — Independent Public-Data Reconstruction**  
> Python, pandas, statsmodels, SciPy | 2026 | GitHub

项目 bullet 可以写：

- Reconstructed a point-in-time monthly panel from delayed ETF holdings, 148K public daily observations and notice-dated fundamentals, retaining a delisted constituent and documenting provider fallbacks.
- Evaluated four pre-registered cross-sectional signal families with chronological Rank IC, HAC/FDR and quantile tests; rejected the composite after its final-holdout spread turned negative.
- Built a benchmark-relative long-only simulation with group, weight, beta, tracking-error, turnover and ADV constraints plus explicit commission, spread, stamp-duty and impact costs; final-holdout net active return was approximately -0.4% annualized.

UBS Work Experience 只写有 2025 同期证据的任务。仓库不能证明当时完成了什么。

如果被问代码作者，我必须按事实说清 AI 和工具协助。我不能声称逐行独立编写，除非真的如此。我可以通过理解、复核、修改、测试和现场解释来建立可信度，但不能用 GitHub 所有权替代真实作者边界。

---

# 第二十章：下一版我会怎么做

我不会在同一 final holdout 上继续调参。我会先设计新实验：

1. 获得官方历史指数成分和公司行动 master；
2. 获得真正 point-in-time 的估值、盈利预测和分析师修正；
3. 加入可交易性：停牌、涨跌停队列、历史价差；
4. 延长到更多市场周期；
5. 使用 joint alpha-risk-cost optimizer；
6. 做 provider reconciliation 和数据漂移监控；
7. 将 low-risk-only 作为新假设，而不是复用旧 holdout；
8. 纸面交易，再讨论 production。

我现在真正学会的不是四个因子公式，而是这条思考链：

> 岗位决定研究对象；研究对象决定 target；target 决定信息时钟；信息时钟决定数据结构；数据结构决定特征；特征必须经过未见数据和组合实现；组合必须支付成本；结果失败时，QR 的工作是停止和解释，而不是改名字。
