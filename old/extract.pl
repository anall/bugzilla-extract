#!/usr/bin/env perl
use strict;
use Mail::MboxParser;
use DBI;
use Term::ProgressBar;

my $dbh = DBI->connect("dbi:SQLite:dbname=data.db","","");

my $add_bug = $dbh->prepare("INSERT OR IGNORE INTO buginfo VALUES (?,?,?,?,?,?,?,?)");
my $add_comment = $dbh->prepare("INSERT OR IGNORE INTO comments VALUES (?,?,?,?)");

my $parseropts = {
    enable_grep     => 1,
    enable_cache    => 0,
};
my $mb = Mail::MboxParser->new('bugs.mbox', 
    decode     => 'ALL',
    newline    => 'UNIX',
    parseropts => $parseropts);

# -----------

$dbh->{AutoCommit} = 0;

my $progress = Term::ProgressBar->new ({count => 46008,ETA   => 'linear'});
my $mark = 256-1;
my $ct = 0;
while (my $msg = $mb->next_message) {
    ++$ct;

    my $headers = $msg->header;

    my $orig_subject = unarray( $headers->{'subject'} );

    my ($bugid,$subject) = $orig_subject =~ m/^\[Bug (\d+)\] (?:New: )?(.+)$/;
    next unless $bugid;
    $subject = $orig_subject unless $subject;

    $add_bug->execute(
        $bugid,
        $subject,
        map{ unarray( $headers->{'x-bugzilla-'.$_} ) } qw( product component severity priority status assigned-to )
    ) if $subject;

    my $body = $msg->body( $msg->find_body );

    my ($in_bug,$commentid, $new_body) = parse_it( $body );
    my $from = unarray( $headers->{'x-bugzilla-who'} );

    $add_comment->execute( $bugid, $commentid, $from, $new_body ) if $in_bug;

    if ( ($ct & $mark) == 0 ) {
        $dbh->commit;
        $progress->update($ct);
    }
}

$dbh->commit;

sub unarray {
    my ($orig) = @_;

    return $orig->[0] if ( ref $orig eq 'ARRAY' );
    return $orig;
}

sub parse_it {
    my @lines = split(/\n/,$_[0]);
    my @ws;
    my @out;
    my $eat_ws = 0;
    my $begin = 1;

    my $cmtid = -1;
    my $in_bug = 0;

    foreach my $line ( @lines ) {
        if ( $begin && $line =~ m/^http/ ) {
            $begin = 0;
            $eat_ws = 1;
            next;
        }
        if ( $line =~ m/^\s*$/ ) {
            push @ws, $line unless $eat_ws;
        } elsif ( $line =~ m/^--\s*$/ ) {
            last;
        } elsif ( ! $in_bug && $line =~ m/^--- Comment #(\d+) from .+? ---$/ ) {
            $cmtid = $1;
            $in_bug = 1;
            
            if ( $cmtid == 0 ) {
                push @out, @ws, $line;
            } else {
                @out = ( $line );
            }
            $eat_ws = 0;
            @ws = (); 
        } else {
            $in_bug = 1 if ( $line =~ m/Bug ID:/ );

            $eat_ws = 0;
            push @out, @ws, $line;
            @ws = ();
        }
        $begin = 0;
    }

    return ( $in_bug, $cmtid, join("\n",@out) );
}
