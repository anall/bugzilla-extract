#!/usr/bin/env python
import sys
import mailbox
import os
import sqlite3
import re

url_regex = re.compile(r"http")
whitespace_regex = re.compile(r"^\s*$")
bugzilla_change_table_regex = re.compile(r".* <.*> changed:$")
horizontal_line_regex = re.compile(r"-------------------")
comment_header_regex = re.compile(r"--- Comment #(\d+) from .+? ---$")


def parse_body(body):
    lines = body.split('\n')

    STATE_BEGIN = 1
    STATE_BETWEEN_SECTIONS = 2
    STATE_BUGZILLA_CHANGE_TABLE_HEADER = 3
    STATE_BUGZILLA_CHANGE_TABLE_ROW = 4
    STATE_BUGZILLA_COMMENT = 5

    state = STATE_BEGIN
    output = []
    comment_id = 0
    for line in lines:
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
            else:
                match = comment_header_regex.match(line)
                if match:
                    state = STATE_BUGZILLA_COMMENT
                    comment_id = match.group(1)

        if state == STATE_BUGZILLA_CHANGE_TABLE_HEADER:
            if horizontal_line_regex.match(line):
                state = STATE_BUGZILLA_CHANGE_TABLE_ROW
            continue

        if state == STATE_BUGZILLA_CHANGE_TABLE_ROW:
            if whitespace_regex.match(line):
                state = STATE_BETWEEN_SECTIONS
                continue
            else:
                # if we want to detect anything further about bug state, we can do this here
                # note: it looks like old emails have the changed table
                # emails from 2012 onward have an additional set of information
                pass

        if state == STATE_BUGZILLA_COMMENT:
            pass

    if state == STATE_BUGZILLA_COMMENT:
        return {"body": "\n".join(output), "comment_id": comment_id}
    else:
        return None


def read_file(filename, conn):
    interesting_messages = {
        "newchanged": True,
        "changed": True,
        "new": True,
        "request": True,    # patch/attachment flags

        "admin": False,
        "whine": False,
        None: False      # delivery status failures; not notifications
    }

    cursor = conn.cursor()
    subject_regex = re.compile(r"\[Bug (?P<bug_id>\d+)\] (?:New: )?(?P<subject>.+)$")

    mbox = mailbox.mbox(filename)
    for message in mbox:

        message_type = message["X-Bugzilla-Type"]
        if interesting_messages[message_type]:
            subject_line = message["subject"].replace("\r\n", "").replace("\n", "")
            match = subject_regex.search(subject_line)

            if not match:
                print "Missed a match of the subject regex: %s" % subject_line
                continue

            matched_subject = match.groupdict()
            add_bug_args = [
                matched_subject["bug_id"],
                matched_subject["subject"],
            ]
            add_bug_args.extend([(message["X-Bugzilla-" + x]) for x in "Product Component Severity Priority Status Assigned-To".split()])

            # add the bug headers
            cursor.execute("INSERT OR IGNORE INTO buginfo VALUES (?,?,?,?,?,?,?,?)", add_bug_args)

            for part in message.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    parsed = parse_body(part.get_payload())
                    if parsed is None:
                        print "Not a bugzilla comment; not handling (%s: %s)" \
                            % (filename, subject_line)
                    else:
                        add_comment_args = (matched_subject["bug_id"], parsed["comment_id"], message["X-Bugzilla-Who"], parsed["body"])
                        cursor.execute("INSERT OR IGNORE INTO comments VALUES (?,?,?,?)", add_comment_args)
                else:
                    # multipart/alternative, text/html
                    # but we assume that content is available in text/plain so we ignore these
                    #print "Got a message part of content type %s; not handling (%s: %s)" \
                    #    % (content_type, filename, subject_line)
                    continue

            conn.commit()


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
    except sqlite3.OperationalError:
        print_db_setup()
        sys.exit(1)
