CREATE TABLE comments (bug_id INTEGER, comment_id INTEGER, who TEXT, content TEXT, PRIMARY KEY(bug_id,comment_id) );
CREATE TABLE buginfo (bug_id INTEGER PRIMARY KEY, subject TEXT, product TEXT, component TEXT, severity TEXT, priority TEXT, status TEXT, assigned TEXT);
CREATE TABLE commitinfo (bug_id INTEGER, sha TEXT, PRIMARY KEY(bug_id, sha) );
