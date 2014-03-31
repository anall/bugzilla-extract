#!/usr/bin/ruby -w

require 'pathname'
require 'rmail'

count = 0

File.open(Pathname.new(ARGV[0]), 'r') do |mbox|
  RMail::Mailbox.parse_mbox(mbox) do |raw|
    count += 1
    print "#{count} mails\n"
    begin
      File.open(RMail::Parser.read(raw).header.date.strftime("split/mail-%y%m"), 'a') do |out|
        out.print(raw)
      end
    rescue NoMethodError
      File.open("split/mail-broken", 'a') do |out|
        out.print(raw)
      end
    end
  end
end
