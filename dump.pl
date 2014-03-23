#!/usr/bin/env perl
use strict;
use DBI;

my $dbh = DBI->connect("dbi:SQLite:dbname=data.db","","");

my $get_bugs =
    $dbh->prepare("SELECT * FROM buginfo ORDER BY bug_id");
my $get_comments =
    $dbh->prepare("SELECT * FROM comments WHERE bug_id = ? ORDER BY comment_id");

mkdir("out");
$get_bugs->execute;
while ( my $bug = $get_bugs->fetchrow_hashref ) {
    my $bugid = $bug->{bug_id};
    print "$bugid\n";
    open(my $fh,">:encoding(UTF-8)","out/$bugid.txt");
    foreach my $what ( qw(bug_id subject product component severity priority status assigned) ) {
        printf $fh "%15s: %s\n", $what, $bug->{$what};
    }

    print $fh "\n\n";
    $get_comments->execute( $bugid );
    while ( my $cmt = $get_comments->fetchrow_hashref ) {
        print $fh $cmt->{who} . "\n" . $cmt->{content} . "\n\n";
    }
    close $fh;
}
