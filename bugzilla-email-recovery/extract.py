#!/usr/bin/env python
import sys
import mailbox
import os
import sqlite3
import re
import datetime
import hashlib

url_regex = re.compile(r"http")
whitespace_regex = re.compile(r"^\s*$")
bugzilla_change_table_regex = re.compile(r".* <.*> changed:$")
bugzilla_summary_header_regex = re.compile("\s+Summary:")
horizontal_line_regex = re.compile(r"-------------------")
comment_header_regex = re.compile(r"--- Comment #(\d+) from .+? ---$")
footer_regex = re.compile(r"^--\s*$")
split_regex = re.compile(r"\r?\n")


def parse_body(body):
    lines = split_regex.split(body)

    STATE_BEGIN = 1
    STATE_BETWEEN_SECTIONS = 2
    STATE_BUGZILLA_CHANGE_TABLE_HEADER = 3
    STATE_BUGZILLA_CHANGE_TABLE_ROW = 4
    STATE_BUGZILLA_COMMENT = 5
    STATE_BUGZILLA_SUMMARY_HEADER = 6

    state = STATE_BEGIN
    output = []
    comment_id = -1
    is_security = False
    for line in lines:
        if footer_regex.match(line):
            break

        output.append(line)

        # we ignore everything before a line that starts with the bugzilla bug URL
        if state == STATE_BEGIN:
            if url_regex.match(line):
                state = STATE_BETWEEN_SECTIONS
                continue

        if state == STATE_BETWEEN_SECTIONS:
            if whitespace_regex.match(line):
                # ignore
                continue
            elif bugzilla_change_table_regex.match(line):
                state = STATE_BUGZILLA_CHANGE_TABLE_HEADER
                continue
            elif bugzilla_summary_header_regex.match(line):
                state = STATE_BUGZILLA_SUMMARY_HEADER
            else:
                match = comment_header_regex.match(line)
                if match:
                    state = STATE_BUGZILLA_COMMENT
                    comment_id = match.group(1)

        if state == STATE_BUGZILLA_CHANGE_TABLE_HEADER:
            if horizontal_line_regex.match(line):
                state = STATE_BUGZILLA_CHANGE_TABLE_ROW
            continue

        if state == STATE_BUGZILLA_SUMMARY_HEADER:
            if whitespace_regex.match(line):
                state = STATE_BETWEEN_SECTIONS

            # some values can be split across multiple lines. We ignore that for now
            if ":" in line:
                (key, value) = [x.strip() for x in line.split(":", 1)]

                if key == "Group" and value == "Security Issue":
                    is_security = True
                if key == "Summary":
                    comment_id = 0
            continue

        if state == STATE_BUGZILLA_CHANGE_TABLE_ROW:
            if whitespace_regex.match(line):
                state = STATE_BETWEEN_SECTIONS
                continue
            else:
                # if we want to detect anything further about bug state, we can do this here
                # note: it looks like old emails have the changed table
                # emails from 2012 onward have an additional set of information
                (key, removed, added) = [x.strip() for x in line.split("|", 2)]
                if key == "Group" and added == "Security Issue":
                    is_security = True

                continue
                pass

        if state == STATE_BUGZILLA_COMMENT:
            pass

    return {"body": "\n".join(output), "comment_id": comment_id, "is_security": is_security}

def read_file(filename, conn):
    interesting_messages = {
        "newchanged": True,
        "changed": True,
        "new": True,
        "request": False,    # patch/attachment flags

        "admin": False,
        "whine": False,
        None: False      # delivery status failures; not notifications
    }

    cursor = conn.cursor()
    subject_regex = re.compile(r"\[Bug (?P<bug_id>\d+)\] (?:New: )?(?P<subject>.+?)(?: : \[Attachment (?P<attach_id>\d+)\] .+)?$")
    # strip off the timezone, because python datetime doesn't support tz
    date_regex = re.compile(r" [+-]\d{4}$")

    mbox = mailbox.mbox(filename)
    sys.stderr.write("Processing %s\n" % filename)
    for (counter, message) in enumerate(mbox):

        message_type = message["X-Bugzilla-Type"]
        if interesting_messages[message_type]:
            subject_line = message["subject"].replace("\r\n", "").replace("\n", "")
            match = subject_regex.search(subject_line)

            if not match:
                print "Missed a match of the subject regex: %s" % subject_line
                continue
            matched_subject = match.groupdict()
            interesting_attributes = "Product Component Severity Priority Status Assigned-To".split()

            date_cleaned_text = date_regex.sub("", message["Date"])
            date_received = datetime.datetime.strptime(date_cleaned_text, "%a, %d %b %Y %H:%M:%S")

            for part in message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True)
                        charset = part.get_charset()
                        #if charset:
                        body = body.decode("utf-8")
                    except UnicodeDecodeError as e:
                        print "Got bad encoded content, treating as text (%s: %s)" \
                            % (filename, subject_line)
                        body = part.get_payload()

                    parsed = parse_body(body)

                    if parsed is None:
                        # print "Not a bugzilla comment; not handling (%s: %s)" \
                        #    % (filename, subject_line)
                        pass
                    else:
                        digest_source = parsed["body"]
                        # Do not use actual comment body if we've got a comment id
                        if parsed["comment_id"] >= 0:
                            digest_source = "___special_bug_%s_comment_%s" % (matched_subject["bug_id"], parsed["comment_id"])
                        add_comment_args = (matched_subject["bug_id"], parsed["comment_id"],
                                            message["X-Bugzilla-Who"], parsed["body"],
                                            date_received, hashlib.md5(digest_source.encode('utf-8')).hexdigest())
                        cursor.execute("INSERT OR IGNORE INTO comments VALUES (?,?,?,?,?,?)", add_comment_args)
                        is_security = parsed["is_security"]
                else:
                    # multipart/alternative, text/html
                    # but we assume that content is available in text/plain so we ignore these
                    #print "Got a message part of content type %s; not handling (%s: %s)" \
                    #    % (content_type, filename, subject_line)
                    continue

            cursor.execute("SELECT last_update,status from buginfo where bug_id = ?", (matched_subject["bug_id"], ))
            (last_updated,status) = cursor.fetchone() or (None,None)

            # we have an existing bug
            if last_updated:
                # bug that needs updating, and we have the data ( not 'request' type )
                if last_updated < date_received.isoformat(" ") and message_type != "request":
                    update_bug_args = [matched_subject["subject"]]
                    update_bug_args.extend([(message["X-Bugzilla-" + x]) for x in interesting_attributes])
                    update_bug_args.append(date_received)
                    update_bug_args.append(matched_subject["bug_id"])

                    sql = ["UPDATE buginfo SET subject=?, product=?, component=?, severity=?,",
                           "priority=?, status=?, assigned=?, last_update=?"]
                    if is_security:
                        sql.append(", is_security='Y'")
                    sql.append("WHERE bug_id = ?")

                    cursor.execute(" ".join(sql), update_bug_args)
                # bug that exists, but we have newer information (possibly merged from two data sources): ignore
                else:
                    pass
            else:
                add_bug_args = [
                    matched_subject["bug_id"],
                    matched_subject["subject"],
                ]
                add_bug_args.extend([(message["X-Bugzilla-" + x]) for x in interesting_attributes])
                if is_security:
                    add_bug_args.append("Y")
                else:
                    add_bug_args.append("N")
                add_bug_args.append(date_received)

                cursor.execute("INSERT INTO buginfo VALUES (?,?,?,?,?,?,?,?,?,?)", add_bug_args)

        if counter % 100 == 0:
            conn.commit()
            sys.stderr.write(" ...%d\r" % counter)

    conn.commit()
    sys.stderr.write(" ...%d\n" % counter)


def get_connection():
    return sqlite3.connect("data.db")

if __name__ == "__main__":
    def print_usage():
        print "Usage: python extract.py mbox|directory"

    def print_db_setup():
        print "Create an sqlite database first:"
        print "sqlite3 data.db < ../create.sql"

    if len(sys.argv) != 2:
        print_usage()
        sys.exit(1)

    user_input = sys.argv[1]

    try:
        if os.path.isdir(user_input):
            connection = get_connection()
            for filename in os.listdir(user_input):
                read_file(user_input + "/" + filename, connection)
        elif os.path.isfile(user_input):
            read_file(user_input, get_connection())
    except sqlite3.OperationalError, e:
        print e
        print_db_setup()
        sys.exit(1)
