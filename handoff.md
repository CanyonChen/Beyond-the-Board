# 项目交接

1. 先读[项目进度](docs/Project_Progress.md)的组员分工与交付状态。评估和复现细节见[实验账本](experiment/results.md)。
2. 历史样本保存在 `data/moves.csv.gz`。它含多种时限，旧表 913,510 条有标签走法的“对手钟”全部等于当前棋手的走后钟；相应结果只用于复现。主分析使用 `data/processed/moves_verified.csv.gz`，由原有棋局 ID 和 Lichess 官方逐步棋钟重建。数据定义、原谱下载断点续传和重建命令见[数据说明](data/README_data.md)。
3. 新模型在 9 月 1–23 日的三个滚动窗口比较。9 月 24–30 日的标签在本轮工作前已经用于项目报告，因此末周是重复评估。不同数据版本间的分数变化不能直接归因于某个模型。
4. [项目首页](README.md)列出复现、建模、分组、风险曲线和敏感性分析的命令。对照表中负的 log loss 差值表示前者预测更好。评估定义和区间单位见[测评方案](experiment/evaluation.md)。
5. [研究报告](docs/report/Beyond_the_Board_Report.pdf)第 7–8 页含复现附录与精确数据表。当前版本按 [Canvas 项目原文](https://canvas.cityu.edu.hk/courses/72915/files/folder/Project?preview=16044993)制作，请用 [Team-SixSixGoSmooth-PPT.pdf](docs/pre/Team-SixSixGoSmooth-PPT.pdf) 作为 PPT 作业的文件。共 10 页，封面含正式课名、题目、队名、六名组员及组队表 Student ID 栏所列的八位学号、制作日期。按 [六人试讲安排](docs/Slides-outline.md)演练，目标时长 7 分 30 秒，包含交接。[离线展示稿](docs/pre/deck.html)按 N 查看英文讲稿及数据。
6. [独立贡献及源码附录](docs/Team-SixSixGoSmooth-Appendix.pdf)已整理六人条目，标示有记录的交付和需要本人确认的事项，附原始仓库固定版本及当前分析的[源码快照](docs/appendix-assets/Beyond-the-Board-source.zip)。11 月 23 日已确认 CHEN Siying、LIU Yibo 完成分工，附录已登记。CHEN Canyang 的方法章节归属仍待核对。团队还需录制全员出席且不超过 8 分钟的 `Team-SixSixGoSmooth-Recording.mp4`，由代表将三份成品分别上传。Canvas 原说明列出的截止时间为 2026 年 11 月 28 日 23:59（香港时间）。

7. Senyuan WU 于 11 月 23 日提交[评估与图表复核](docs/Evaluation-Review-Senyuan-WU.md)，并参与修订实验结论和准备英文讲稿。贡献附录已登记相关工作。按当前安排，Senyuan 讲第 8–10 页，逐页预算为 30 秒、50 秒、30 秒。[录制分工](docs/Slides-outline.md)

8. 11 月 23 日的复阅补充了报告的预处理和风险曲线解释，以及展示稿的模型比较及评估指标。提交材料的格式、内容和期限以课程项目说明为准。[Canvas 项目说明](https://canvas.cityu.edu.hk/courses/72915/files/folder/Project?preview=16044993)

9. 全组英文演讲稿共有 [PDF 版](docs/Full-Presentation-Script.pdf)和[可编辑文本](docs/Full-Presentation-Script.md)，标出逐页讲者、目标时间和交接句。HTML 按 N 可读相同正文。录制安排以本版讲稿为准，实际时长待排练确认。

10. 11 月 27 日已同步远程 `9ff3cae` 并更新贡献附录。六人学号和已核实贡献保留，个人描述不指定演讲页码；报告链接改为新增的 [APA 格式报告](docs/report/Beyond-the-Board-APA-report.pdf)，另补全组英文讲稿链接。内嵌源码 ZIP 同步当前讲稿文本，加入最新 PPT、HTML 备注及 APA 报告，保留原八页报告，共 19 个 Python 源文件和 56 个文件，带完整哈希清单。单页排版、15 个不同链接的仓库目标及附件字节一致性已核验。本次更新以 Senyuan WU 的署名纳入仓库；课程平台上传状态另行确认。
