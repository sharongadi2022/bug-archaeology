Run `python eval/run_eval.py` and compare the result to the most recent scorecard in
eval/scorecards/.

Report: per-question pass/fail, aggregate retrieval recall, citation-verification pass rate,
and abstention accuracy on the questions whose expected answer is "insufficient information".

Then diff against the previous scorecard and list every question that changed state. Call out
regressions first and loudly. Write the new scorecard to eval/scorecards/ with today's date.
