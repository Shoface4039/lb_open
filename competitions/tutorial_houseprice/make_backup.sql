.headers on
.mode csv
.output backup/score.csv
SELECT * FROM score;
.output backup/submit.csv
SELECT * FROM submit;
.quit
