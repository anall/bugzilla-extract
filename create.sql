CREATE TABLE comments (bug_id INTEGER, comment_id INTEGER, who TEXT, content TEXT, log_date DATE, hash TEXT, PRIMARY KEY(bug_id,hash));
CREATE TABLE buginfo (bug_id INTEGER PRIMARY KEY, subject TEXT, product TEXT, component TEXT, severity TEXT, priority TEXT, status TEXT, assigned TEXT, last_update DATE);
CREATE TABLE commitinfo (bug_id INTEGER, sha TEXT, PRIMARY KEY(bug_id, sha) );

CREATE INDEX comment_date ON comments(log_date);
