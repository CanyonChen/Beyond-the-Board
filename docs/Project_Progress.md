# SixSixGoSmooth 项目进度

更新至 2026 年 11 月 27 日。DSC5001 小组项目研究三分钟快棋中，在已知局面与双方等级分的情况下，回合开始时的棋钟读数能为下一步严重失误的预测增加多少信息。项目范围和原定排期见[项目提案](Team-Proposal-SixSixGoSmooth.pdf)。

## 六位组员的进度

| 组员 | 提案分工 | 已完成的交付与依据 | 当前汇报分工 |
| --- | --- | --- | --- |
| CHEN Canyang | 设计研究方法和建模流程，负责报告的相应部分 | 建立项目仓库，归档提案和组队表，建立项目进度文档。研究设计和最终方法章节的具体个人贡献待组内确认。[项目初始化](https://github.com/CanyonChen/Beyond-the-Board/commit/b4448e68f8426f5328feb3310f4bba4d840ef17c) · [进度记录](https://github.com/CanyonChen/Beyond-the-Board/commit/8b9397dfcb8ecd91bf672f0a81331c76927a7766) | 第 4 页，研究设计与三套输入，0:55 |
| CHEN Siying | 完善建模方案，整合项目工作，协调报告和幻灯片 | 完成建模方案完善、项目材料整合及报告与幻灯片协调，11 月 23 日经组内确认。[研究报告](report/Beyond_the_Board_Report.pdf) · [贡献附录](Team-SixSixGoSmooth-Appendix.pdf) | 第 1–2 页，研究问题与棋局示例，1:10 |
| GUAN Wenxi | 采集、整理和预处理数据，准备数据说明 | 通过 Lichess API 采集棋局，预处理原始走法数据，交付采集与转换脚本、走法表及数据说明。[数据交付](https://github.com/CanyonChen/Beyond-the-Board/commit/f2c681e0be8c2489ec55fbb363ac6953f71e8f86) · [采集记录](https://github.com/CanyonChen/Beyond-the-Board/commit/87aa01f8eacefd3a4e21599ab0fe9219db3b72ba) | 第 3 页，时钟错位与重建，0:55 |
| LIU Yibo | 执行实验方案，搭建实验流程，训练和测试模型 | 完成实验流程搭建及模型训练和测试，11 月 23 日经组内确认。[评估方案](../experiment/evaluation.md) · [实验记录](../experiment/results.md) · [贡献附录](Team-SixSixGoSmooth-Appendix.pdf) | 第 6–7 页，用时特征的总体增益与阶段结果，1:40 |
| SHI Geyunqing | 构建和实现模型，撰写方法说明并准备展示材料 | 实现原始失误率基线、L2 正则逻辑回归和直方图梯度提升，提交原方法说明、早期汇报提纲及基准评估表和图。[建模与方法](https://github.com/CanyonChen/Beyond-the-Board/commit/f430a045a849deae184541d6762851490f2a511e) · [原评估结果](https://github.com/CanyonChen/Beyond-the-Board/commit/eede3daec7dd6b3fc659e7c7e7e3de32b95748a9) · [固定配置复跑](https://github.com/CanyonChen/Beyond-the-Board/commit/92dd2e7c60d5f3efc5950686f538bdd42e310a98) | 第 5 页，按时间窗口验证与模型选择，1:00 |
| WU Senyuan | 评估模型，分析、可视化和总结实验结果，准备实验汇报 | 复算末周指标、用时特征对照、风险校准、配对区间及敏感性实验，核对图表并修订实验结论。准备全组英文讲稿及实验展示内容。[评估复核](Evaluation-Review-Senyuan-WU.md) · [完整英文讲稿](Full-Presentation-Script.pdf) | 第 8–10 页，校准、棋手互斥检验与结论，1:50 |

时钟修复、校正样本重建、完整新版实验及最终报告和幻灯片的具体个人分工，待小组核对实际承担的部分。上表的汇报页码用于排练。已确认的个人交付见[贡献与源码附录](Team-SixSixGoSmooth-Appendix.pdf)。

## 项目阶段与小组成果

| 日期 | 进度 |
| --- | --- |
| 10 月 28 日至 11 月 16 日 | 归档提案与组队资料，完成小样本验证并开展正式采集。数据采集采用 Lichess API，从快棋排行榜种子棋手扩展到其对手并优先填补评级段，向 150 位棋手查询后共取得 12,131 条棋局记录。 |
| 11 月 19–20 日 | 完成原始基线和模型评估。原始表的 913,510 条有标签走法和对应指标保留供复现。发现旧表的棋钟索引问题和混合时限后，重新核对官方原谱，重建走前时钟与同一棋手的近期用时，再完成校正样本的模型比较与敏感性分析。 |
| 11 月 21–23 日 | 完成英文研究报告、10 页课程展示、团队贡献与源码附录。11 月 23 日复核末周评估和图表，整理六人英文讲稿与展示备注。 |

### 数据与评估核验

- 找回全部 11,833 个不同原始棋局 ID。先排除 37 局自定义开局，再排除 520 局时限不符和 23 局棋钟异常增加的对局。最终保留 11,253 局三分钟无加秒棋局，重建 888,993 步。主分析的 839,176 条有标签走法包括 69,799 次严重失误。[数据说明](../data/README_data.md) · [样本筛选统计](../data/processed/recovery_counts.json)
- 原表 913,510 条有标签走法的“对手钟”字段全部等于行棋方的走后读数。校正后的索引在 926,332 条可比读数中均与棋谱记录相差至多 0.5 秒。原表指标保留作历史复现，走前棋钟的增益以校正数据上的比较为依据。[全量时钟审计](../data/processed/clock_audit.json) · [原始基准复现](../results/model_comparison/baseline_reproduction.json)
- [校正后的数据表](../data/processed/moves_verified.csv.gz)的 SHA-256 为 `9faf8fd13a2196d4daad9491baa4c1fb735e0cc46a0de7793c206a87a41a554b`。开发期为 9 月 1–23 日，含 8,621 局、642,668 条有标签走法。末周为 9 月 24–30 日，含 2,632 局、196,508 条有标签走法。两期按整局拆分，末周已用于早期分析。[评估方案](../experiment/evaluation.md)
- 11 月 23 日复核了三个开发窗口的既有结果，重新评分全部末周走法，并重拟合两组输入对照及七项敏感性设置。主指标、分组校准、配对区间和敏感性结果均与已发布结果一致，最大绝对差为 0.0。6 项数据测试和 4 项模型测试通过。[复核报告](Evaluation-Review-Senyuan-WU.md) · [复核汇总](../results/model_comparison/review_2026_11_23/review_summary.json)

### 主要研究结果

| 比较 | 结果与解释 |
| --- | --- |
| 模型选择 | 加零风险规则的直方图梯度提升模型在三个开发窗口的平均 log loss 最低，为 0.239866。该模型的末周 log loss 为 0.235150，ROC AUC 为 0.81227，平均精确率为 0.26014。[模型选择结果](../results/model_comparison/verified_180_0/selection.json) · [末周指标](../results/model_comparison/verified_180_0/published_test_metrics.csv) |
| 用时信息的增益 | 同一批末周走法上，log loss 从仅用局面和等级分的 0.236168，降至加入双方走前时钟后的 0.235275，再降至加入本人近期用时后的 0.235150。相对降幅为 0.43%，绝对降幅为 0.001018，按整局配对的 95% 区间为 0.000658–0.001429。在这一加入顺序下，双方走前时钟贡献约 88% 的增益。[配对区间](../results/model_comparison/verified_180_0/paired_log_loss.csv) |
| 阶段与校准 | 仅新增双方走前时钟时，开局、中局、残局的 log loss 降幅点估计分别为 0.000585、0.000733、0.002147。各区间描述阶段内的不确定性。完整模型的最高风险十分位平均预测 28.12%，实测 28.87%，全末周实测 8.35%。[阶段比较](../results/model_comparison/clock_subgroups.csv) · [分组校准](../results/model_comparison/verified_180_0/selected_calibration.csv) |
| 棋手互斥检验 | 排除涉及末周棋手的训练对局后，训练从 8,621 局缩至 509 局，同一批末周走法的 log loss 从 0.235150 升至 0.246045。训练量和棋手构成同时改变，这一差值反映两者共同变化下的表现。[敏感性结果](../results/model_comparison/robustness.csv) |

以上结果描述这批有引擎注释的三分钟快棋中的预测表现。新月份的表现有待独立评估，改变可用时长对失误风险的因果影响需要另外的研究设计。完整解释、附录及复现入口见[研究报告](report/Beyond_the_Board_Report.pdf)、[实验记录](../experiment/results.md)与[运行说明](../README.md#run-locally)。

## 课程交付与剩余事项

组队资料与提案已按项目记录提交。最终三项由一位代表分别提交，截止时间为 **2026 年 11 月 28 日 23:59（香港时间）**。[项目说明](https://canvas.cityu.edu.hk/courses/72915/files/folder/Project?preview=16044993) · [提交对照](Slides-outline.md#canvas-submission)

| 交付物 | 当前状态 |
| --- | --- |
| [Team-SixSixGoSmooth-PPT.pdf](pre/Team-SixSixGoSmooth-PPT.pdf) | 10 页，含封面。封面包含课程名、项目题目、队名、六位成员姓名与学号以及制作日期。文件已备，Canvas 上传状态待核实。 |
| Team-SixSixGoSmooth-Recording.mp4 | 六人均需参加 Zoom 录制，全片最多 8 分钟。讲稿目标 **7:30，已含交接**，录制成片及实际时长待核实。[完整英文讲稿](Full-Presentation-Script.pdf) · [逐页分工与时间](Slides-outline.md) · [HTML 展示稿，按 N 看讲者备注](pre/deck.html) |
| [Team-SixSixGoSmooth-Appendix.pdf](Team-SixSixGoSmooth-Appendix.pdf) | 单页，列出六人的已确认贡献及来源，附[源码 ZIP](appendix-assets/Beyond-the-Board-source.zip)和[项目仓库](https://github.com/CanyonChen/Beyond-the-Board)。待小组核对尚未确认的个人分工，Canvas 上传状态待核实。 |

组内排练时，按 CHEN Siying、GUAN Wenxi、CHEN Canyang、SHI Geyunqing、LIU Yibo、WU Senyuan 的顺序讲解。录制后核对实际时长，由小组代表完成并核验三项提交。

## 2026-11-27 仓库同步与贡献附录更新

从远程 `main` 快进同步至 `9ff3cae`，取得更新后的 10 页 PPT 和新增的 15 页 [APA 格式报告](report/Beyond-the-Board-APA-report.pdf)。本轮仅同步附录材料，没有重跑实验或更改个人贡献归属。

- [贡献附录](Team-SixSixGoSmooth-Appendix.pdf)中的报告链接改为 APA 版，另补完整英文讲稿链接，保留六人学号、已核实工作及原始交付依据，不写具体演讲页码。
- [源码与材料 ZIP](appendix-assets/Beyond-the-Board-source.zip)同步当前讲稿文本，加入最新 PPT、HTML 备注和 APA 报告，保留原八页报告及分析源码。共 56 个文件，其中 19 个 Python 源文件。
- 已逐页检查单页附录排版，核验 15 个不同链接的仓库目标、全部归档文件哈希、与本地材料的逐字节一致性及 PDF 内嵌附件。录制安排仍按当前全组讲稿执行，成片与课程平台提交状态待小组确认。

| 11 月 27 日附录版本 | SHA-256 |
| --- | --- |
| 贡献附录 PDF | `0677f674ac75a53a485e73aff7e1f34f0f6b62fd61b3b7cc3b1c2131cebc8f2c` |
| 内嵌源码与材料 ZIP | `3f9429e428460c3eabc2ae61e088b8696d85d2c56ec7926a91f0e601910fcfe3` |

本次附录更新以 Senyuan WU 的署名提交并同步到仓库 `main`。课程平台上传状态由小组另行核实。
