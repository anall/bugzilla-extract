There are a couple scripts here. They should be run in this order:

* create.sql
    setup the database. Run this first

* find-types.py
    on a new set of mboxes, to find out if there's a message type not covered in extract.interesting_types. Not required, but advisable

* extract.py
    to extract the data from an mbox and put it into sql
