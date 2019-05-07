CREATE TABLE score(
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    submission_id INTEGER,
    title TEXT,
    RMSLE FLOAT
); 

CREATE TABLE submit(
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    title TEXT,
    raw_text TEXT,
    upload_date TIMESTAMP DEFAULT (datetime(CURRENT_TIMESTAMP, 'localtime'))
);
