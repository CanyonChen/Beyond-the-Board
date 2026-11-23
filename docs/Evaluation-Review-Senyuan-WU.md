# Senyuan WU 的模型评估与实验结论复核

Senyuan WU（60231487），2026 年 11 月 23 日。本次复核使用下文 SHA-256 所标识的正式校正数据及配套模型和指标核验已有实验、图表和结论，并准备了校准与棋手互斥检查的英文讲稿。

复核支持原有核心发现。在相同的末周走法上，时钟与近期用时合计带来约 **0.43% 的相对 log loss 降幅**，其中约 **87.70%** 来自先加入双方走前时钟。校准点与实际比例接近。棋手互斥检查同时改变训练量和棋手构成，其成绩变化需要连同这两项变化解释。

## 复核范围和方法

正式数据为 [moves_verified.csv.gz](../data/processed/moves_verified.csv.gz)，SHA-256 为 `9faf8fd13a2196d4daad9491baa4c1fb735e0cc46a0de7793c206a87a41a554b`。共 11,253 局、839,176 条可标注走法、69,799 次严重失误。训练期为 2026 年 9 月 1–23 日，末周评估期为 9 月 24–30 日（UTC）。

1. 复算全部主标签，确认 45,606 条低于十点下降理论界限的走法均无阳性标签。检查各时间窗口的训练集与评估集没有共享棋局。
2. 从逐窗表重新计算三个验证窗口的等权平均值，确认所选模型仍是 HGB 加零风险规则。此项复核使用已提交的逐窗结果。
3. 载入已保存模型，对全部 196,508 条末周走法重新推理。重新拟合仅含局面与评级、以及加入双方时钟的两个模型，计算相同走法上的指标和配对差值。
4. 重新形成十个校准组，复算 1,000 次按整局配对重抽样的置信区间及阶段、评级分组。重跑七项敏感性拟合，包括棋手互斥、5/15 个百分点、150 厘兵及纳入将杀的标签检查。
5. 核验四幅正式统计图所列的五份源文件哈希，逐项核对图中数字与置信区间方向。渲染并检查报告的结果图、展示稿第 8–9 页及其支持表。运行仓库原有 6 项数据测试和 4 项模型测试。

所有上述数值比较与已提交结果一致，最大绝对差为 **0.0**。三个开发窗口的模型本次采用记录核验，末周的两个输入对照和七项敏感性拟合本次重新执行。完整机器记录见 [review_summary.json](../results/model_comparison/review_2026_11_23/review_summary.json)。

## 同一批走法上的指标

以下三行均使用相同 HGB 设置和零风险规则，在 642,668 条开发期走法上拟合，在 2,632 局的 196,508 条末周走法上评估。末周共 16,401 次事件，发生率为 8.35%。

| 输入 | Log loss | Brier | ROC AUC | Average precision |
| --- | ---: | ---: | ---: | ---: |
| 局面与评级 | 0.236168 | 0.068344 | 0.809827 | 0.255285 |
| 再加入双方走前时钟 | 0.235275 | 0.068179 | 0.811971 | 0.259375 |
| 再加入本人近期用时 | 0.235150 | 0.068152 | 0.812272 | 0.260142 |

| 比较 | Log loss 绝对降幅 | 按整局配对的 95% 区间 |
| --- | ---: | --- |
| 加入双方走前时钟 | 0.000893 | 0.000510–0.001284 |
| 进一步加入本人近期用时 | 0.000125 | 0.000006–0.000246 |
| 两次加入合计 | 0.001018 | 0.000658–0.001429 |

这些区间来自 1,000 次按整局配对的百分位 bootstrap。上表将改善写成正值，源 CSV 的“增强模型减参考模型”差值为负。近期用时的额外改善较小，其区间下限接近零。88% 的占比取决于当前的输入加入顺序。

来源为 [复算指标](../results/model_comparison/review_2026_11_23/recomputed_metrics.csv)及[复算配对区间](../results/model_comparison/review_2026_11_23/recomputed_paired_intervals.csv)。

## 第 8 页的校准解释

最高风险十分组有 19,651 条走法，平均预测概率 28.12%，实际事件比例 28.87%，相差约 0.75 个百分点。十组的最大绝对差为 **0.9115 个百分点**，按组内走法数加权的绝对差为 **0.3528 个百分点**。这一加权差取决于十组的划分，仅用于描述本次样本的分组校准。

校准图的横轴是平均预测概率，纵轴是实际事件比例，均使用百分数。对角线表示两者相等，线上方的点表示模型低估该组风险。这里的组均值接近支持本样本中的分组校准解释。评估期曾被早期分析使用，未来独立月份的表现仍需另行测量。

来源为 [复算校准表](../results/model_comparison/review_2026_11_23/recomputed_calibration.csv)。

## 第 9 页的棋手互斥解释

| 训练方案 | 训练棋局 | 训练走法 | 与末周共享棋手 | 末周走法 | Log loss | AP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 全部开发期数据 | 8,621 | 642,668 | 639 | 196,508 | 0.235150 | 0.260142 |
| 排除所有涉及末周棋手的训练局 | 509 | 33,737 | 0 | 196,508 | 0.246045 | 0.225954 |

互斥筛选保留 5.25% 的训练走法或 5.90% 的训练棋局。评估走法和标签相同。log loss 上升意味着该设置的概率预测变差。训练量减少和棋手构成改变同时发生，现有比较无法分别估计两者的贡献。

来源为 [复算敏感性结果](../results/model_comparison/review_2026_11_23/recomputed_robustness.csv)。

## 完善后的英文实验结论

On the same 196,508 moves from the previously examined final week, adding pre-move clocks and the mover’s recent time use reduced HGB log loss from 0.236168 to 0.235150. The absolute reduction was 0.001018, with a 95% paired whole-game bootstrap interval of 0.000658 to 0.001429, equivalent to a 0.43% relative reduction. With inputs added in this order, the starting clocks accounted for 87.70% of the gain. Recent time use supplied a smaller additional improvement. The finding supports modest incremental predictive value for time information in these annotated three-minute games.

The full model’s predicted and observed event rates differed by less than one percentage point in every risk decile. This describes group-level calibration in the evaluated sample. Excluding training games involving evaluation-period players increased log loss to 0.246045 while retaining only 5.25% of the training moves. Training size and player composition changed together, so the comparison combines their effects. The reused final week, sampling of active players with engine-annotated games, and repeated players across games limit generalisation. The whole-game bootstrap accounts for moves within a game, while dependence between games involving the same player remains. A new month would provide an independent evaluation. The observed predictive gain alone cannot establish how allocating more time would change a player’s error risk.

## 复现和交付

从仓库根目录、在与已保存模型匹配的环境中运行。

```text
python scripts/review_evaluation.py
python -m unittest discover -s data -p "test_*.py"
python -m unittest discover -s scripts -p "test_*.py"
```

本次使用 Python 3.13.12、NumPy 2.5.4、pandas 3.1.1、SciPy 1.18.1、scikit-learn 1.9.1、joblib 1.6.0、XGBoost CPU 3.4.1，线程数为 4。机器环境与评估摘要另存于复核目录。

报告已补充复核后的实验结论，贡献附录记录了复核和讲稿工作。文稿整理使用了生成式 AI 工具，实验结果来自上述复核程序。当前英文讲稿与 HTML 讲者备注同步，Senyuan WU 按计划讲第 8–10 页。[英文讲稿](Full-Presentation-Script.md) · [录制分工](Slides-outline.md)

## 成品核验

已重新生成并逐页检查 8 页英文报告，以及登记本次贡献的单页附录。报告使用 Tectonic 编译，附录以同一 TeX 正文排版后通过 pypdf 嵌入原源码 ZIP。附件字节与仓库源码包完全一致，13 个不同链接已核验。正式展示 PDF 的校准和棋手互斥图表已核验。

| 11 月 23 日复核版本 | SHA-256 |
| --- | --- |
| 英文报告 | `d48b0e5e908d117c0c3f33276f955a853ddb1bc30af642d097264c4d74329745` |
| 贡献附录 | `4236f3a55736d681aae7136c7533bb36fdf1fa5fe8418371ffc0b16d6747b22b` |
| 展示 HTML | `ab8e6211620fd29e6d37ced1df246932e4faff845d7a324f4a7de72fc75bc741` |

贡献附录的内嵌源码包已更新，含 19 个 Python 源文件、当前报告、完整英文演讲稿及复核结果。归档共 53 个文件，内部 SHA256SUMS.txt 校验各文件。新包解压后的 6 项数据测试和 4 项模型测试通过。
