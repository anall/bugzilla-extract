#!/usr/bin/env perl
use strict;
use DBI;
use Term::ProgressBar;

my $dbh = DBI->connect("dbi:SQLite:dbname=data.db","","");

my $add_commit = $dbh->prepare("INSERT OR IGNORE INTO commitinfo VALUES (?,?)");

$dbh->{AutoCommit} = 0;
my $mark = 256-1;
my $ct = 0;

foreach my $line (<STDIN>) {
    ++$ct;

    chomp $line; chomp $line;
    my ($sha,$rest) = $line =~ m/^([a-z0-9]{7}) (.+)$/;
    my ( $bugid ) = $rest =~ m/^\(bug (\d+)\)/i;
    ( $bugid ) = $rest =~ m/^\[bug (\d+)\]/i unless $bugid;
    ( $bugid ) = $rest =~ m/show_bug\.cgi\?id=(\d+)/i unless $bugid;
    
    $add_commit->execute($bugid,$sha) if $bugid;

    if ( ($ct & $mark) == 0 ) {
        $dbh->commit;
        printf "%5i\n",$ct;
    }
}
      
$dbh->commit;
