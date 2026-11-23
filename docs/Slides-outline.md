# DSC5001 Canvas presentation

Use the [Canvas slide PDF](pre/Team-SixSixGoSmooth-PPT.pdf) for submission and the [full presentation script](Full-Presentation-Script.pdf) to rehearse the spoken text. The ten slides take **7 minutes 30 seconds**, including speaker handoffs, leaving 30 seconds before the eight-minute limit. In the [offline HTML deck](pre/deck.html), use the arrow keys to advance and press **N** for the matching speaker notes.

The cover shows **DSC5001 – Statistical Machine Learning I**, the full project title, SixSixGoSmooth, all six names with their eight-digit student numbers and **21 November 2026**, the date the slides were prepared. The numbers follow the Student ID column in the team formation record. The closing slide answers the research question and ends with “Thanks for Listening” alongside the CityUHK crest. [Official course title](https://www.cityu.edu.hk/catalogue/pg/202627/course/DSC5001.htm) · [Team formation record](5001_GroupSixSixGoSmooth.docx)

| Slide and topic | Speaker | Time | Speaking cue | Evidence |
| --- | --- | ---: | --- | --- |
| 1. Beyond the Board | CHEN Siying | 0:20 | Introduce three-minute blitz and ask whether the clocks improve forecasts beyond the position and both players’ ratings. | [Report, abstract](report/Beyond_the_Board_Report.pdf) |
| 2. A queen check and a serious error | CHEN Siying | 0:50 | Before 44…Qd5+, Black had 55.63 seconds and White had 14.27. Black’s engine-derived winning chances fell from 50.00% to 36.45%, crossing the 10-percentage-point threshold for a serious error. | [Game record](https://lichess.org/FFkB7LoP/black#87) · [Outcome definition](../data/README_data.md) |
| 3. Reconstructing the clocks | GUAN Wenxi | 0:55 | The archived opponent clock matched the mover’s post-move clock in all 913,510 labelled rows. Rebuild each player’s starting clock from their last completed turn and compare the readings with the game records. | [Clock audit](../data/processed/clock_audit.json) · [Report, clock reconstruction](report/main.tex) |
| 4. Verified games and three input sets | CHEN Canyang | 0:55 | In 11,253 verified three-minute games, keep the model type and evaluation moves fixed. Start with position and ratings, add both clocks and the mover’s share of the combined time, then add the mover’s recent time use. | [Sample counts](../data/processed/recovery_counts.json) · [Feature definitions](../data/README_data.md) |
| 5. Selecting a model on earlier games | SHI Geyunqing | 1:00 | Use three chronological validation windows to select histogram gradient boosting by average log loss. Refit on days 1–23 and evaluate on days 24–30, which had been examined in the original analysis. | [Model selection](../results/model_comparison/verified_180_0/selection.json) · [Validation design](../experiment/evaluation.md) |
| 6. How much the clocks add | LIU Yibo | 1:00 | On the same 196,508 moves, log loss fell from 0.236168 to 0.235150. The starting clocks accounted for 88% of the reduction in this order of addition. The whole-game bootstrap interval for the combined reduction was above zero. | [Loss by feature set](../results/model_comparison/verified_180_0/published_test_metrics.csv) · [Paired intervals](../results/model_comparison/verified_180_0/paired_log_loss.csv) |
| 7. Clock gains across game phases | LIU Yibo | 0:40 | Compare the gain from adding both clocks within each phase. The endgame estimate was largest. The intervals show uncertainty within each phase, and comparing phases would require a separate test. | [Phase estimates and intervals](../results/model_comparison/clock_subgroups.csv) |
| 8. Calibration of the predicted risks | WU Senyuan | 0:30 | Each point compares mean predicted risk with observed frequency. In the highest-risk tenth, predicted risk was 28.12% and the observed rate was 28.87%, compared with 8.35% overall. | [Calibration by decile](../results/model_comparison/verified_180_0/selected_calibration.csv) · [Overall event rate](../results/model_comparison/clock_subgroups.csv) |
| 9. Performance after removing shared players | WU Senyuan | 0:50 | Keep the evaluation moves fixed. Removing training games with final-week players reduced the training set from 8,621 games to 509 and raised log loss from 0.23515 to 0.24605. Training size and player composition both changed. | [Player-disjoint comparison](../results/model_comparison/robustness.csv) |
| 10. What the clocks added | WU Senyuan | 0:30 | Clocks and recent time use reduced log loss by 0.43% relative to position and ratings. The two starting clocks supplied most of the gain. Thank the audience. | [Paired comparisons](../results/model_comparison/verified_180_0/paired_log_loss.csv) · [Closing slide](pre/deck.html#10) |

Each speaker has one continuous section. The [contribution appendix](Team-SixSixGoSmooth-Appendix.pdf) gives the available evidence for individual project work and marks items awaiting confirmation.

The [23 November evaluation review](Evaluation-Review-Senyuan-WU.md) records the recomputed results and figure checks. The [editable English script](Full-Presentation-Script.md) also lists the speaker schedule and all ten slide scripts.

## Canvas submission

The course asks one representative to submit three files by **28 November 2026 at 11:59 p.m. Hong Kong time**. The slides may have at most ten pages including the cover. All six members must participate in the Zoom recording, which may run up to eight minutes. The contribution appendix lists each member’s actual work and includes the source code or a permanent link to it. [Canvas project instructions, sections 5–6](https://canvas.cityu.edu.hk/courses/72915/files/folder/Project?preview=16044993)

| Canvas assignment | Filename |
| --- | --- |
| PPT | `Team-SixSixGoSmooth-PPT.pdf` |
| Recording | `Team-SixSixGoSmooth-Recording.mp4` |
| Appendix | [Team-SixSixGoSmooth-Appendix.pdf](Team-SixSixGoSmooth-Appendix.pdf) |

## Preview and rendering

The [all-slides preview](pre/预览-全部页面.png) shows the ten pages together. To inspect the text, plots and crest at full size, open the slide PDF or the HTML deck. To regenerate the preview after editing the HTML, run the following from the repository root in PowerShell with Python, Pillow and Chrome installed. The renderer writes one PNG per slide and a contact sheet in the output folder. [Preview renderer](pre/render_preview.py)

```powershell
$env:CHROME = "C:\Program Files\Google\Chrome\Application\chrome.exe"
python docs/pre/render_preview.py docs/pre/deck.html 10 tmp/canvas-preview
```

The [research report](report/Beyond_the_Board_Report.pdf) gives data provenance and reproduction commands in Appendix A and numerical tables in Appendix B.
