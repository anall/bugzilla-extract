#!/usr/bin/env python
import sys
import os
import mailbox


def find_message_types(dir_or_file):
    """Look at all messages in an mbox to figure out what X-Bugzilla-Types exist
    (so we can decide which ones we want to handle in extraction)"""
    message_types = set()

    if os.path.isdir(dir_or_file):
        for filename in os.listdir(dir_or_file):
            message_types = message_types.union(find_message_types_in_file(dir_or_file + "/" + filename))
    elif os.path.isfile(dir_or_file):
        message_types = find_message_types_in_file(dir_or_file)
    return message_types


def find_message_types_in_file(filename):
    message_types = set()

    mbox = mailbox.mbox(filename)
    for message in mbox:
        message_types.add(message["X-Bugzilla-Type"])
    return message_types

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print "Usage: python find-types.py mbox|directory"

    message_types = find_message_types(sys.argv[1])
    print("%r" % message_types)
