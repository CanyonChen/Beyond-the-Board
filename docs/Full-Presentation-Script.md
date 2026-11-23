# Beyond the Board English presentation script

SixSixGoSmooth · DSC5001. Allow **7 minutes 30 seconds**, including handoffs. Read the paragraphs aloud and use the timings to rehearse. Bold lines mark handoffs or the closing line.

## Speaker schedule

| Speaker | Slides | Duration | Run time |
| --- | --- | ---: | ---: |
| CHEN Siying | 1-2 | 1:10 | 0:00-1:10 |
| GUAN Wenxi | 3 | 0:55 | 1:10-2:05 |
| CHEN Canyang | 4 | 0:55 | 2:05-3:00 |
| SHI Geyunqing | 5 | 1:00 | 3:00-4:00 |
| LIU Yibo | 6-7 | 1:40 | 4:00-5:40 |
| WU Senyuan | 8-10 | 1:50 | 5:40-7:30 |

## Slide 1 · Beyond the Board

**CHEN Siying · 0:20**

Hello, everyone. We're SixSixGoSmooth. In three-minute chess, even a strong player can make a serious mistake with seconds left. Our question is whether knowing how much time both players have helps us predict that mistake, once we already know the position and their ratings.

## Slide 2 · A queen check and a serious error

**CHEN Siying · 0:50**

Here's an example. Black is about to play queen to d-five with check. At the start of the turn, Black has about fifty-six seconds left and White has about fourteen. After the queen check, the engine's estimate of Black's winning chances falls from fifty percent to about thirty-six percent.

We call a move a serious error when that estimate drops by at least ten percentage points. The engine scores before and after the move tell us whether an error happened. The forecast itself uses only what was available before Black played.

**Wenxi will show us how we recovered the clock readings that the model could actually use.**

## Slide 3 · Reconstructing the clocks

**GUAN Wenxi · 0:55**

Let's stay with the same position. The original table gave about fifty-five seconds as the opponent's time. That was Black's clock after the queen check. For our forecast, the reading we needed was White's clock before Black moved, which was about fourteen seconds. We found this mismatch in every labelled move in the original table.

We went back to the Lichess game records to rebuild the clocks. Each player starts with one hundred and eighty seconds. After that, we take the clock from that player's last completed turn. All comparable readings matched the game records within half a second.

**With the clocks reconstructed, Canyang will explain how we measured what they added to the prediction.**

## Slide 4 · Verified games and three input sets

**CHEN Canyang · 0:55**

Our verified sample has just over eleven thousand games and about eight hundred and thirty-nine thousand labelled moves. Each player had three minutes for the whole game, with no extra time added after a move.

We built three sets of inputs. The first uses the position and both players' ratings. The second adds both starting clocks and the share of their combined time held by the player about to move. The third adds how long that same player spent on recent turns. We keep the model type and evaluation moves fixed. Adding the inputs in steps lets us measure what each group contributed.

**Geyunqing will walk us through how we chose the model.**

## Slide 5 · Selecting a model on earlier games

**SHI Geyunqing · 1:00**

This timeline shows how we chose a model using earlier games. In each of the three windows, we trained on the earlier dates and validated on the next block of dates. We kept all moves from a game together and fitted any preprocessing using the training games in that window.

We ranked the models by average validation log loss. Log loss penalises a model when it assigns a high probability to an outcome that doesn't happen. Histogram gradient boosting had the lowest average score. For the final comparison, we refitted it on days one through twenty-three and scored the last week of the month. That week had already been examined in the original analysis.

**Yibo will show what happened when we added the clocks and recent thinking times.**

## Slide 6 · How much the clocks add

**LIU Yibo · 1:00**

We trained the same model separately for each input set and scored it on the same roughly one hundred and ninety-seven thousand moves. With position and ratings alone, log loss was about zero point two three six. With all the inputs, it was about zero point two three five.

The bar breaks down that small gain. Adding both starting clocks first accounted for about eighty-eight percent of the improvement. Adding the player's recent thinking times then supplied the remaining twelve percent. Those shares describe that order of addition. To estimate uncertainty, we resampled whole games. The interval for the combined improvement stayed above zero in this comparison.

## Slide 7 · Clock gains across game phases

**LIU Yibo · 0:40**

Does that gain vary by game phase? Each row shows how much adding the two clocks improved log loss within that phase. Farther to the right means a larger improvement. The largest estimate was in endgames. The lines show uncertainty within each phase. We'd need a separate test to tell whether the gains really differ between phases.

**Senyuan will now show how closely the model's predicted risks matched what actually happened.**

## Slide 8 · Calibration of the predicted risks

**WU Senyuan · 0:30**

To check those probabilities, we ranked the final-week moves by predicted risk and split them into ten groups. In the highest-risk group, the model predicted serious errors in about twenty-eight out of every hundred moves. We observed about twenty-nine. Across all final-week moves, the rate was about eight per hundred. Each point compares one group's average prediction with what actually happened.

## Slide 9 · Performance after removing shared players

**WU Senyuan · 0:50**

We also asked how sensitive our result was to having the same players in training and evaluation. We removed every training game that involved a player from the final week, refitted the model, and scored the same final-week moves. The training set fell from about eighty-six hundred games to just over five hundred. Log loss rose from about zero point two three five to zero point two four six.

The model had fewer games to learn from, and the mix of players changed at the same time. This check cannot tell us how much of the difference came from each change.

## Slide 10 · What the clocks added

**WU Senyuan · 0:30**

So what did the clocks add? In these three-minute games, using both starting clocks and recent thinking times reduced log loss by about four-tenths of one percent relative to the model using position and ratings alone. Most of that small gain came from the two clock readings at the start of the turn.

**Thank you for listening.**

## Presentation files

Rehearse from the [six-page script PDF](Full-Presentation-Script.pdf) or press **N** in the [offline HTML presentation](pre/deck.html) for the same spoken text and handoffs. Use the [ten-slide PDF](pre/Team-SixSixGoSmooth-PPT.pdf) for the Canvas presentation upload. The [research report](report/Beyond_the_Board_Report.pdf) contains the methods, results and limitations.
