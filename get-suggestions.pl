#!/usr/bin/env perl
use strict;
use DBI;
use Data::Dumper;

my $dbh = DBI->connect("dbi:SQLite:dbname=data.db","","");

my $info_sth = $dbh->prepare('select b.*,count(c.sha) as ct_commits from buginfo as b left join commitinfo as c on b.bug_id = c.bug_id where b.bug_id = ? group by b.bug_id');

my $sth = $dbh->prepare('select bug_id,content from comments where comment_id = 0 and content like "%dw_suggestions%" order by bug_id');
$sth->execute;

while ( my $row = $sth->fetchrow_hashref ) {
    my ($url) = $row->{content} =~ m!(http://dw-suggestions\.dreamwidth\.org/\d+\.html)!;
    ($url) = $row->{content} =~ m!^\s+URL: (.+)$!m unless $url;
    next unless $url;

    $info_sth->execute( $row->{bug_id} );
    if ( my $info_row = $info_sth->fetchrow_hashref ) {
        next if $info_row->{status} eq 'RESOLVED';
        printf "%4i %9s %2i %s %s\n", $row->{bug_id}, $info_row->{status}, $info_row->{ct_commits}, $url, $info_row->{subject};
    }
}
