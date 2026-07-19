#!/usr/bin/env python3
"""Ruby and Rails documentation scraper.

Covers:
  - Ruby core (classes, modules, exceptions, IO, Enumerable, Comparable)
  - Ruby standard library
  - Rails Getting Started
  - Rails Models (Active Record, migrations, validations, associations, queries)
  - Rails Controllers (routing, Action Controller)
  - Rails Views (layouts, helpers, form helpers)
  - Rails Advanced (Active Job, Action Mailer, Action Cable, asset pipeline,
    caching, security, testing)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class RubyScraper(BaseScraper):
    """Scrape Ruby and Rails documentation."""

    SOURCES = {
        "ruby-core": {
            "pages": {
                # Core classes
                "https://ruby-doc.org/3.3.0/Object.html": "Ruby Object",
                "https://ruby-doc.org/3.3.0/BasicObject.html": "Ruby BasicObject",
                "https://ruby-doc.org/3.3.0/Kernel.html": "Ruby Kernel",
                "https://ruby-doc.org/3.3.0/String.html": "Ruby String",
                "https://ruby-doc.org/3.3.0/Integer.html": "Ruby Integer",
                "https://ruby-doc.org/3.3.0/Float.html": "Ruby Float",
                "https://ruby-doc.org/3.3.0/Numeric.html": "Ruby Numeric",
                "https://ruby-doc.org/3.3.0/Array.html": "Ruby Array",
                "https://ruby-doc.org/3.3.0/Hash.html": "Ruby Hash",
                "https://ruby-doc.org/3.3.0/Symbol.html": "Ruby Symbol",
                "https://ruby-doc.org/3.3.0/Regexp.html": "Ruby Regexp",
                "https://ruby-doc.org/3.3.0/Range.html": "Ruby Range",
                "https://ruby-doc.org/3.3.0/NilClass.html": "Ruby NilClass",
                "https://ruby-doc.org/3.3.0/TrueClass.html": "Ruby TrueClass",
                "https://ruby-doc.org/3.3.0/FalseClass.html": "Ruby FalseClass",
                "https://ruby-doc.org/3.3.0/Proc.html": "Ruby Proc",
                "https://ruby-doc.org/3.3.0/Method.html": "Ruby Method",
                "https://ruby-doc.org/3.3.0/UnboundMethod.html": "Ruby UnboundMethod",
                "https://ruby-doc.org/3.3.0/Binding.html": "Ruby Binding",
                "https://ruby-doc.org/3.3.0/Struct.html": "Ruby Struct",
                "https://ruby-doc.org/3.3.0/Data.html": "Ruby Data",
                "https://ruby-doc.org/3.3.0/Complex.html": "Ruby Complex",
                "https://ruby-doc.org/3.3.0/Rational.html": "Ruby Rational",
                "https://ruby-doc.org/3.3.0/Time.html": "Ruby Time",
                "https://ruby-doc.org/3.3.0/Dir.html": "Ruby Dir",
                "https://ruby-doc.org/3.3.0/File.html": "Ruby File",
                "https://ruby-doc.org/3.3.0/Fiber.html": "Ruby Fiber",
                "https://ruby-doc.org/3.3.0/Thread.html": "Ruby Thread",
                "https://ruby-doc.org/3.3.0/Mutex.html": "Ruby Mutex",
                "https://ruby-doc.org/3.3.0/Process.html": "Ruby Process",
                "https://ruby-doc.org/3.3.0/Signal.html": "Ruby Signal",
                "https://ruby-doc.org/3.3.0/ObjectSpace.html": "Ruby ObjectSpace",
                "https://ruby-doc.org/3.3.0/GC.html": "Ruby GC",
                "https://ruby-doc.org/3.3.0/ENV.html": "Ruby ENV",
                "https://ruby-doc.org/3.3.0/Encoding.html": "Ruby Encoding",
                "https://ruby-doc.org/3.3.0/Marshal.html": "Ruby Marshal",
                "https://ruby-doc.org/3.3.0/Random.html": "Ruby Random",
                "https://ruby-doc.org/3.3.0/MatchData.html": "Ruby MatchData",
                "https://ruby-doc.org/3.3.0/Enumerator.html": "Ruby Enumerator",
                "https://ruby-doc.org/3.3.0/Set.html": "Ruby Set",
                # Modules
                "https://ruby-doc.org/3.3.0/Module.html": "Ruby Module",
                "https://ruby-doc.org/3.3.0/Class.html": "Ruby Class",
                "https://ruby-doc.org/3.3.0/Enumerable.html": "Ruby Enumerable",
                "https://ruby-doc.org/3.3.0/Comparable.html": "Ruby Comparable",
                "https://ruby-doc.org/3.3.0/Enumerator/Lazy.html": "Ruby Enumerator::Lazy",
                "https://ruby-doc.org/3.3.0/Math.html": "Ruby Math",
                "https://ruby-doc.org/3.3.0/FileUtils.html": "Ruby FileUtils",
                # Exceptions
                "https://ruby-doc.org/3.3.0/Exception.html": "Ruby Exception",
                "https://ruby-doc.org/3.3.0/StandardError.html": "Ruby StandardError",
                "https://ruby-doc.org/3.3.0/RuntimeError.html": "Ruby RuntimeError",
                "https://ruby-doc.org/3.3.0/TypeError.html": "Ruby TypeError",
                "https://ruby-doc.org/3.3.0/ArgumentError.html": "Ruby ArgumentError",
                "https://ruby-doc.org/3.3.0/NameError.html": "Ruby NameError",
                "https://ruby-doc.org/3.3.0/NoMethodError.html": "Ruby NoMethodError",
                "https://ruby-doc.org/3.3.0/IndexError.html": "Ruby IndexError",
                "https://ruby-doc.org/3.3.0/KeyError.html": "Ruby KeyError",
                "https://ruby-doc.org/3.3.0/RangeError.html": "Ruby RangeError",
                "https://ruby-doc.org/3.3.0/IOError.html": "Ruby IOError",
                "https://ruby-doc.org/3.3.0/Errno.html": "Ruby Errno",
                "https://ruby-doc.org/3.3.0/SystemCallError.html": "Ruby SystemCallError",
                "https://ruby-doc.org/3.3.0/RegexpError.html": "Ruby RegexpError",
                "https://ruby-doc.org/3.3.0/ZeroDivisionError.html": "Ruby ZeroDivisionError",
                "https://ruby-doc.org/3.3.0/StopIteration.html": "Ruby StopIteration",
                "https://ruby-doc.org/3.3.0/ScriptError.html": "Ruby ScriptError",
                "https://ruby-doc.org/3.3.0/LoadError.html": "Ruby LoadError",
                "https://ruby-doc.org/3.3.0/SyntaxError.html": "Ruby SyntaxError",
                "https://ruby-doc.org/3.3.0/NotImplementedError.html": "Ruby NotImplementedError",
                # IO
                "https://ruby-doc.org/3.3.0/IO.html": "Ruby IO",
                "https://ruby-doc.org/3.3.0/ARGF.html": "Ruby ARGF",
                "https://ruby-doc.org/3.3.0/StringIO.html": "Ruby StringIO",
                # More core classes
                "https://ruby-doc.org/3.3.0/Comparable.html": "Ruby Comparable Module",
                "https://ruby-doc.org/3.3.0/Errno.html": "Ruby Errno Module",
                "https://ruby-doc.org/3.3.0/Ractor.html": "Ruby Ractor",
                "https://ruby-doc.org/3.3.0/TracePoint.html": "Ruby TracePoint",
                "https://ruby-doc.org/3.3.0/RubyVM.html": "Ruby RubyVM",
                "https://ruby-doc.org/3.3.0/RubyVM/AbstractSyntaxTree.html": "Ruby AST",
                "https://ruby-doc.org/3.3.0/RubyVM/InstructionSequence.html": "Ruby InstructionSequence",
                "https://ruby-doc.org/3.3.0/Enumerator/Chain.html": "Ruby Enumerator::Chain",
                "https://ruby-doc.org/3.3.0/Enumerator/ArithmeticSequence.html": "Ruby Enumerator::ArithmeticSequence",
                "https://ruby-doc.org/3.3.0/Enumerator/Product.html": "Ruby Enumerator::Product",
                "https://ruby-doc.org/3.3.0/Fiber/Scheduler.html": "Ruby Fiber::Scheduler",
                "https://ruby-doc.org/3.3.0/Thread/Mutex.html": "Ruby Thread::Mutex",
                "https://ruby-doc.org/3.3.0/Thread/Queue.html": "Ruby Thread::Queue",
                "https://ruby-doc.org/3.3.0/Thread/SizedQueue.html": "Ruby Thread::SizedQueue",
                "https://ruby-doc.org/3.3.0/Thread/ConditionVariable.html": "Ruby Thread::ConditionVariable",
                "https://ruby-doc.org/3.3.0/Thread/Backtrace/Location.html": "Ruby Thread::Backtrace::Location",
                "https://ruby-doc.org/3.3.0/IO/Buffer.html": "Ruby IO::Buffer",
                "https://ruby-doc.org/3.3.0/File/Stat.html": "Ruby File::Stat",
                "https://ruby-doc.org/3.3.0/Dir.html": "Ruby Dir Class",
                "https://ruby-doc.org/3.3.0/ObjectSpace/WeakMap.html": "Ruby ObjectSpace::WeakMap",
                "https://ruby-doc.org/3.3.0/ObjectSpace/WeakKeyMap.html": "Ruby ObjectSpace::WeakKeyMap",
                "https://ruby-doc.org/3.3.0/Comparable.html": "Ruby Comparable (core)",
                "https://ruby-doc.org/3.3.0/Warning.html": "Ruby Warning",
                "https://ruby-doc.org/3.3.0/FrozenError.html": "Ruby FrozenError",
                "https://ruby-doc.org/3.3.0/FloatDomainError.html": "Ruby FloatDomainError",
                "https://ruby-doc.org/3.3.0/Encoding/CompatibilityError.html": "Ruby Encoding::CompatibilityError",
                "https://ruby-doc.org/3.3.0/Encoding/UndefinedConversionError.html": "Ruby Encoding::UndefinedConversionError",
                "https://ruby-doc.org/3.3.0/Encoding/InvalidByteSequenceError.html": "Ruby Encoding::InvalidByteSequenceError",
                "https://ruby-doc.org/3.3.0/Encoding/Converter.html": "Ruby Encoding::Converter",
                # Earlier Ruby versions reference
                "https://ruby-doc.org/3.2.0/Object.html": "Ruby 3.2 Object",
                "https://ruby-doc.org/3.2.0/String.html": "Ruby 3.2 String",
                "https://ruby-doc.org/3.2.0/Array.html": "Ruby 3.2 Array",
                "https://ruby-doc.org/3.2.0/Hash.html": "Ruby 3.2 Hash",
                "https://ruby-doc.org/3.2.0/Integer.html": "Ruby 3.2 Integer",
                "https://ruby-doc.org/3.2.0/Enumerable.html": "Ruby 3.2 Enumerable",
                "https://ruby-doc.org/3.2.0/IO.html": "Ruby 3.2 IO",
                "https://ruby-doc.org/3.2.0/Regexp.html": "Ruby 3.2 Regexp",
                "https://ruby-doc.org/3.2.0/Proc.html": "Ruby 3.2 Proc",
                "https://ruby-doc.org/3.2.0/Time.html": "Ruby 3.2 Time",
                "https://ruby-doc.org/3.2.0/File.html": "Ruby 3.2 File",
                "https://ruby-doc.org/3.2.0/Fiber.html": "Ruby 3.2 Fiber",
                "https://ruby-doc.org/3.2.0/Thread.html": "Ruby 3.2 Thread",
                "https://ruby-doc.org/3.2.0/Range.html": "Ruby 3.2 Range",
                "https://ruby-doc.org/3.2.0/Struct.html": "Ruby 3.2 Struct",
                "https://ruby-doc.org/3.2.0/Data.html": "Ruby 3.2 Data",
                "https://ruby-doc.org/3.2.0/Module.html": "Ruby 3.2 Module",
                "https://ruby-doc.org/3.2.0/Class.html": "Ruby 3.2 Class",
                "https://ruby-doc.org/3.2.0/Exception.html": "Ruby 3.2 Exception",
                "https://ruby-doc.org/3.2.0/Encoding.html": "Ruby 3.2 Encoding",
                "https://ruby-doc.org/3.2.0/Random.html": "Ruby 3.2 Random",
                "https://ruby-doc.org/3.2.0/Set.html": "Ruby 3.2 Set",
                "https://ruby-doc.org/3.2.0/Complex.html": "Ruby 3.2 Complex",
                "https://ruby-doc.org/3.2.0/Rational.html": "Ruby 3.2 Rational",
                "https://ruby-doc.org/3.2.0/Numeric.html": "Ruby 3.2 Numeric",
                "https://ruby-doc.org/3.2.0/Float.html": "Ruby 3.2 Float",
                "https://ruby-doc.org/3.2.0/Comparable.html": "Ruby 3.2 Comparable",
                "https://ruby-doc.org/3.2.0/Symbol.html": "Ruby 3.2 Symbol",
                "https://ruby-doc.org/3.2.0/NilClass.html": "Ruby 3.2 NilClass",
                "https://ruby-doc.org/3.2.0/TrueClass.html": "Ruby 3.2 TrueClass",
                "https://ruby-doc.org/3.2.0/FalseClass.html": "Ruby 3.2 FalseClass",
                "https://ruby-doc.org/3.2.0/Kernel.html": "Ruby 3.2 Kernel",
                "https://ruby-doc.org/3.2.0/GC.html": "Ruby 3.2 GC",
                "https://ruby-doc.org/3.2.0/Marshal.html": "Ruby 3.2 Marshal",
                "https://ruby-doc.org/3.2.0/MatchData.html": "Ruby 3.2 MatchData",
                "https://ruby-doc.org/3.2.0/Enumerator.html": "Ruby 3.2 Enumerator",
                "https://ruby-doc.org/3.2.0/Math.html": "Ruby 3.2 Math",
                "https://ruby-doc.org/3.2.0/Process.html": "Ruby 3.2 Process",
                "https://ruby-doc.org/3.2.0/Signal.html": "Ruby 3.2 Signal",
                "https://ruby-doc.org/3.2.0/ObjectSpace.html": "Ruby 3.2 ObjectSpace",
                "https://ruby-doc.org/3.2.0/ENV.html": "Ruby 3.2 ENV",
                "https://ruby-doc.org/3.2.0/ARGF.html": "Ruby 3.2 ARGF",
                "https://ruby-doc.org/3.2.0/BasicObject.html": "Ruby 3.2 BasicObject",
                "https://ruby-doc.org/3.2.0/Method.html": "Ruby 3.2 Method",
                "https://ruby-doc.org/3.2.0/UnboundMethod.html": "Ruby 3.2 UnboundMethod",
                "https://ruby-doc.org/3.2.0/Binding.html": "Ruby 3.2 Binding",
            },
        },
        "ruby-stdlib": {
            "pages": {
                # Standard library
                "https://ruby-doc.org/3.3.0/stdlibs/json/JSON.html": "Ruby JSON",
                "https://ruby-doc.org/3.3.0/stdlibs/yaml/YAML.html": "Ruby YAML",
                "https://ruby-doc.org/3.3.0/stdlibs/csv/CSV.html": "Ruby CSV",
                "https://ruby-doc.org/3.3.0/stdlibs/net-http/Net/HTTP.html": "Ruby Net::HTTP",
                "https://ruby-doc.org/3.3.0/stdlibs/uri/URI.html": "Ruby URI",
                "https://ruby-doc.org/3.3.0/stdlibs/open-uri/OpenURI.html": "Ruby OpenURI",
                "https://ruby-doc.org/3.3.0/stdlibs/fileutils/FileUtils.html": "Ruby FileUtils (stdlib)",
                "https://ruby-doc.org/3.3.0/stdlibs/pathname/Pathname.html": "Ruby Pathname",
                "https://ruby-doc.org/3.3.0/stdlibs/tempfile/Tempfile.html": "Ruby Tempfile",
                "https://ruby-doc.org/3.3.0/stdlibs/tmpdir/Dir.html": "Ruby Tmpdir",
                "https://ruby-doc.org/3.3.0/stdlibs/optparse/OptionParser.html": "Ruby OptionParser",
                "https://ruby-doc.org/3.3.0/stdlibs/logger/Logger.html": "Ruby Logger",
                "https://ruby-doc.org/3.3.0/stdlibs/erb/ERB.html": "Ruby ERB",
                "https://ruby-doc.org/3.3.0/stdlibs/date/Date.html": "Ruby Date",
                "https://ruby-doc.org/3.3.0/stdlibs/date/DateTime.html": "Ruby DateTime",
                "https://ruby-doc.org/3.3.0/stdlibs/digest/Digest.html": "Ruby Digest",
                "https://ruby-doc.org/3.3.0/stdlibs/openssl/OpenSSL.html": "Ruby OpenSSL",
                "https://ruby-doc.org/3.3.0/stdlibs/socket/Socket.html": "Ruby Socket",
                "https://ruby-doc.org/3.3.0/stdlibs/socket/TCPServer.html": "Ruby TCPServer",
                "https://ruby-doc.org/3.3.0/stdlibs/socket/TCPSocket.html": "Ruby TCPSocket",
                "https://ruby-doc.org/3.3.0/stdlibs/socket/UDPSocket.html": "Ruby UDPSocket",
                "https://ruby-doc.org/3.3.0/stdlibs/benchmark/Benchmark.html": "Ruby Benchmark",
                "https://ruby-doc.org/3.3.0/stdlibs/minitest/Minitest.html": "Ruby Minitest",
                "https://ruby-doc.org/3.3.0/stdlibs/test-unit/Test/Unit.html": "Ruby Test::Unit",
                "https://ruby-doc.org/3.3.0/stdlibs/set/Set.html": "Ruby Set (stdlib)",
                "https://ruby-doc.org/3.3.0/stdlibs/ostruct/OpenStruct.html": "Ruby OpenStruct",
                "https://ruby-doc.org/3.3.0/stdlibs/singleton/Singleton.html": "Ruby Singleton",
                "https://ruby-doc.org/3.3.0/stdlibs/observer/Observable.html": "Ruby Observable",
                "https://ruby-doc.org/3.3.0/stdlibs/delegate/Delegator.html": "Ruby Delegator",
                "https://ruby-doc.org/3.3.0/stdlibs/forwardable/Forwardable.html": "Ruby Forwardable",
                "https://ruby-doc.org/3.3.0/stdlibs/abbrev/Abbrev.html": "Ruby Abbrev",
                "https://ruby-doc.org/3.3.0/stdlibs/shellwords/Shellwords.html": "Ruby Shellwords",
                "https://ruby-doc.org/3.3.0/stdlibs/securerandom/SecureRandom.html": "Ruby SecureRandom",
                "https://ruby-doc.org/3.3.0/stdlibs/cgi/CGI.html": "Ruby CGI",
                "https://ruby-doc.org/3.3.0/stdlibs/drb/DRb.html": "Ruby DRb",
                "https://ruby-doc.org/3.3.0/stdlibs/strscan/StringScanner.html": "Ruby StringScanner",
                "https://ruby-doc.org/3.3.0/stdlibs/base64/Base64.html": "Ruby Base64",
                "https://ruby-doc.org/3.3.0/stdlibs/zlib/Zlib.html": "Ruby Zlib",
                # More stdlib
                "https://ruby-doc.org/3.3.0/stdlibs/etc/Etc.html": "Ruby Etc",
                "https://ruby-doc.org/3.3.0/stdlibs/fiddle/Fiddle.html": "Ruby Fiddle",
                "https://ruby-doc.org/3.3.0/stdlibs/io-console/IO.html": "Ruby IO Console",
                "https://ruby-doc.org/3.3.0/stdlibs/ipaddr/IPAddr.html": "Ruby IPAddr",
                "https://ruby-doc.org/3.3.0/stdlibs/monitor/Monitor.html": "Ruby Monitor",
                "https://ruby-doc.org/3.3.0/stdlibs/open3/Open3.html": "Ruby Open3",
                "https://ruby-doc.org/3.3.0/stdlibs/pp/PP.html": "Ruby PP",
                "https://ruby-doc.org/3.3.0/stdlibs/prettyprint/PrettyPrint.html": "Ruby PrettyPrint",
                "https://ruby-doc.org/3.3.0/stdlibs/pstore/PStore.html": "Ruby PStore",
                "https://ruby-doc.org/3.3.0/stdlibs/resolv/Resolv.html": "Ruby Resolv",
                "https://ruby-doc.org/3.3.0/stdlibs/timeout/Timeout.html": "Ruby Timeout",
                "https://ruby-doc.org/3.3.0/stdlibs/tsort/TSort.html": "Ruby TSort",
                "https://ruby-doc.org/3.3.0/stdlibs/weakref/WeakRef.html": "Ruby WeakRef",
                "https://ruby-doc.org/3.3.0/stdlibs/webrick/WEBrick.html": "Ruby WEBrick",
                "https://ruby-doc.org/3.3.0/stdlibs/net-ftp/Net/FTP.html": "Ruby Net::FTP",
                "https://ruby-doc.org/3.3.0/stdlibs/net-imap/Net/IMAP.html": "Ruby Net::IMAP",
                "https://ruby-doc.org/3.3.0/stdlibs/net-pop/Net/POP3.html": "Ruby Net::POP3",
                "https://ruby-doc.org/3.3.0/stdlibs/net-smtp/Net/SMTP.html": "Ruby Net::SMTP",
                "https://ruby-doc.org/3.3.0/stdlibs/rexml/REXML.html": "Ruby REXML",
                "https://ruby-doc.org/3.3.0/stdlibs/rss/RSS.html": "Ruby RSS",
                "https://ruby-doc.org/3.3.0/stdlibs/rdoc/RDoc.html": "Ruby RDoc",
                "https://ruby-doc.org/3.3.0/stdlibs/irb/IRB.html": "Ruby IRB",
                "https://ruby-doc.org/3.3.0/stdlibs/mutex_m/Mutex_m.html": "Ruby Mutex_m",
                "https://ruby-doc.org/3.3.0/stdlibs/English/English.html": "Ruby English",
                # Ruby 3.2 stdlib
                "https://ruby-doc.org/3.2.0/stdlibs/json/JSON.html": "Ruby 3.2 JSON",
                "https://ruby-doc.org/3.2.0/stdlibs/yaml/YAML.html": "Ruby 3.2 YAML",
                "https://ruby-doc.org/3.2.0/stdlibs/csv/CSV.html": "Ruby 3.2 CSV",
                "https://ruby-doc.org/3.2.0/stdlibs/net-http/Net/HTTP.html": "Ruby 3.2 Net::HTTP",
                "https://ruby-doc.org/3.2.0/stdlibs/uri/URI.html": "Ruby 3.2 URI",
                "https://ruby-doc.org/3.2.0/stdlibs/pathname/Pathname.html": "Ruby 3.2 Pathname",
                "https://ruby-doc.org/3.2.0/stdlibs/fileutils/FileUtils.html": "Ruby 3.2 FileUtils",
                "https://ruby-doc.org/3.2.0/stdlibs/optparse/OptionParser.html": "Ruby 3.2 OptionParser",
                "https://ruby-doc.org/3.2.0/stdlibs/logger/Logger.html": "Ruby 3.2 Logger",
                "https://ruby-doc.org/3.2.0/stdlibs/erb/ERB.html": "Ruby 3.2 ERB",
                "https://ruby-doc.org/3.2.0/stdlibs/date/Date.html": "Ruby 3.2 Date",
                "https://ruby-doc.org/3.2.0/stdlibs/date/DateTime.html": "Ruby 3.2 DateTime",
                "https://ruby-doc.org/3.2.0/stdlibs/digest/Digest.html": "Ruby 3.2 Digest",
                "https://ruby-doc.org/3.2.0/stdlibs/openssl/OpenSSL.html": "Ruby 3.2 OpenSSL",
                "https://ruby-doc.org/3.2.0/stdlibs/benchmark/Benchmark.html": "Ruby 3.2 Benchmark",
                "https://ruby-doc.org/3.2.0/stdlibs/securerandom/SecureRandom.html": "Ruby 3.2 SecureRandom",
                "https://ruby-doc.org/3.2.0/stdlibs/base64/Base64.html": "Ruby 3.2 Base64",
                "https://ruby-doc.org/3.2.0/stdlibs/set/Set.html": "Ruby 3.2 Set (stdlib)",
                "https://ruby-doc.org/3.2.0/stdlibs/open3/Open3.html": "Ruby 3.2 Open3",
                "https://ruby-doc.org/3.2.0/stdlibs/tempfile/Tempfile.html": "Ruby 3.2 Tempfile",
                "https://ruby-doc.org/3.2.0/stdlibs/strscan/StringScanner.html": "Ruby 3.2 StringScanner",
                "https://ruby-doc.org/3.2.0/stdlibs/zlib/Zlib.html": "Ruby 3.2 Zlib",
                "https://ruby-doc.org/3.2.0/stdlibs/socket/Socket.html": "Ruby 3.2 Socket",
                "https://ruby-doc.org/3.2.0/stdlibs/socket/TCPServer.html": "Ruby 3.2 TCPServer",
                "https://ruby-doc.org/3.2.0/stdlibs/socket/TCPSocket.html": "Ruby 3.2 TCPSocket",
            },
        },
        "rails-getting-started": {
            "pages": {
                "https://guides.rubyonrails.org/": "Rails Guides Home",
                "https://guides.rubyonrails.org/getting_started.html": "Rails Getting Started",
                "https://guides.rubyonrails.org/install.html": "Rails Installation",
                "https://guides.rubyonrails.org/command_line.html": "Rails Command Line",
                "https://guides.rubyonrails.org/configuring.html": "Rails Configuring",
                "https://guides.rubyonrails.org/initialization.html": "Rails Initialization",
                "https://guides.rubyonrails.org/autoloading_and_reloading_constants.html": "Rails Autoloading and Reloading",
                "https://guides.rubyonrails.org/engines.html": "Rails Engines",
                "https://guides.rubyonrails.org/threading_and_code_execution.html": "Rails Threading",
                "https://guides.rubyonrails.org/error_reporting.html": "Rails Error Reporting",
                "https://guides.rubyonrails.org/debugging_rails_applications.html": "Rails Debugging",
                "https://guides.rubyonrails.org/plugins.html": "Rails Plugins",
                "https://guides.rubyonrails.org/api_app.html": "Rails API App",
                "https://guides.rubyonrails.org/working_with_javascript_in_rails.html": "Rails Working with JavaScript",
                # Ruby language reference from ruby-lang.org
                "https://www.ruby-lang.org/en/": "Ruby Language Home",
                "https://www.ruby-lang.org/en/about/": "About Ruby",
                "https://www.ruby-lang.org/en/documentation/": "Ruby Documentation",
                "https://www.ruby-lang.org/en/documentation/quickstart/": "Ruby in Twenty Minutes",
                "https://www.ruby-lang.org/en/documentation/quickstart/2/": "Ruby in Twenty Minutes (2)",
                "https://www.ruby-lang.org/en/documentation/quickstart/3/": "Ruby in Twenty Minutes (3)",
                "https://www.ruby-lang.org/en/documentation/quickstart/4/": "Ruby in Twenty Minutes (4)",
                "https://www.ruby-lang.org/en/documentation/ruby-from-other-languages/": "Ruby From Other Languages",
                "https://www.ruby-lang.org/en/documentation/ruby-from-other-languages/to-ruby-from-c-and-cpp/": "Ruby From C/C++",
                "https://www.ruby-lang.org/en/documentation/ruby-from-other-languages/to-ruby-from-java/": "Ruby From Java",
                "https://www.ruby-lang.org/en/documentation/ruby-from-other-languages/to-ruby-from-perl/": "Ruby From Perl",
                "https://www.ruby-lang.org/en/documentation/ruby-from-other-languages/to-ruby-from-php/": "Ruby From PHP",
                "https://www.ruby-lang.org/en/documentation/ruby-from-other-languages/to-ruby-from-python/": "Ruby From Python",
                "https://www.ruby-lang.org/en/documentation/installation/": "Ruby Installation",
                "https://www.ruby-lang.org/en/documentation/success-stories/": "Ruby Success Stories",
                "https://www.ruby-lang.org/en/documentation/faq/": "Ruby FAQ",
                "https://www.ruby-lang.org/en/libraries/": "Ruby Libraries",
                "https://www.ruby-lang.org/en/community/": "Ruby Community",
                "https://www.ruby-lang.org/en/news/": "Ruby News",
                "https://www.ruby-lang.org/en/security/": "Ruby Security",
                "https://www.ruby-lang.org/en/downloads/": "Ruby Downloads",
                "https://www.ruby-lang.org/en/downloads/releases/": "Ruby Releases",
                # Bundler
                "https://bundler.io/": "Bundler Home",
                "https://bundler.io/guides/getting_started.html": "Bundler Getting Started",
                "https://bundler.io/guides/gemfile.html": "Bundler Gemfile",
                "https://bundler.io/guides/groups.html": "Bundler Groups",
                "https://bundler.io/guides/git.html": "Bundler Git",
                "https://bundler.io/guides/deploying.html": "Bundler Deploying",
                "https://bundler.io/guides/using_bundler_in_applications.html": "Bundler In Applications",
                "https://bundler.io/guides/creating_gem.html": "Bundler Creating a Gem",
                # RubyGems
                "https://rubygems.org/": "RubyGems Home",
                "https://guides.rubygems.org/": "RubyGems Guides",
                "https://guides.rubygems.org/rubygems-basics/": "RubyGems Basics",
                "https://guides.rubygems.org/what-is-a-gem/": "What is a Gem",
                "https://guides.rubygems.org/make-your-own-gem/": "Make Your Own Gem",
                "https://guides.rubygems.org/gems-with-extensions/": "Gems with Extensions",
                "https://guides.rubygems.org/name-your-gem/": "Name Your Gem",
                "https://guides.rubygems.org/publishing/": "Publishing Gems",
                "https://guides.rubygems.org/security/": "RubyGems Security",
                "https://guides.rubygems.org/patterns/": "RubyGems Patterns",
                "https://guides.rubygems.org/specification-reference/": "Gem Specification Reference",
                "https://guides.rubygems.org/command-reference/": "RubyGems Command Reference",
                # RSpec reference
                "https://rspec.info/": "RSpec Home",
                "https://rspec.info/documentation/": "RSpec Documentation",
                "https://rspec.info/features/3-13/rspec-core/": "RSpec Core",
                "https://rspec.info/features/3-13/rspec-expectations/": "RSpec Expectations",
                "https://rspec.info/features/3-13/rspec-mocks/": "RSpec Mocks",
                "https://rspec.info/features/3-13/rspec-rails/": "RSpec Rails",
                # Rake
                "https://ruby.github.io/rake/": "Rake Documentation",
                "https://ruby.github.io/rake/Rake/Task.html": "Rake Task",
                "https://ruby.github.io/rake/Rake/FileTask.html": "Rake FileTask",
                "https://ruby.github.io/rake/Rake/Application.html": "Rake Application",
                # Minitest
                "https://docs.seattlerb.org/minitest/": "Minitest Documentation",
                "https://docs.seattlerb.org/minitest/Minitest/Test.html": "Minitest Test",
                "https://docs.seattlerb.org/minitest/Minitest/Spec.html": "Minitest Spec",
                "https://docs.seattlerb.org/minitest/Minitest/Mock.html": "Minitest Mock",
                "https://docs.seattlerb.org/minitest/Minitest/Assertions.html": "Minitest Assertions",
                "https://docs.seattlerb.org/minitest/Minitest/Expectations.html": "Minitest Expectations",
                # Capybara
                "https://rubydoc.info/github/teamcapybara/capybara/master": "Capybara Documentation",
                # Devise
                "https://rubydoc.info/github/heartcombo/devise/master": "Devise Documentation",
                # Sidekiq
                "https://github.com/sidekiq/sidekiq/wiki/Getting-Started": "Sidekiq Getting Started",
                "https://github.com/sidekiq/sidekiq/wiki/Active-Job": "Sidekiq Active Job",
                "https://github.com/sidekiq/sidekiq/wiki/Best-Practices": "Sidekiq Best Practices",
                "https://github.com/sidekiq/sidekiq/wiki/FAQ": "Sidekiq FAQ",
                # Puma
                "https://puma.io/": "Puma Web Server",
                # Ruby reference docs
                "https://ruby-doc.org/": "Ruby Doc Home",
                "https://ruby-doc.org/3.3.0/": "Ruby 3.3.0 Documentation",
                "https://ruby-doc.org/3.2.0/": "Ruby 3.2.0 Documentation",
                # Sorbet type checker
                "https://sorbet.org/docs/overview": "Sorbet Overview",
                "https://sorbet.org/docs/adopting": "Sorbet Adopting",
                "https://sorbet.org/docs/sigs": "Sorbet Signatures",
                "https://sorbet.org/docs/class-types": "Sorbet Class Types",
                "https://sorbet.org/docs/union-types": "Sorbet Union Types",
                "https://sorbet.org/docs/nilable-types": "Sorbet Nilable Types",
                "https://sorbet.org/docs/generics": "Sorbet Generics",
                "https://sorbet.org/docs/abstract": "Sorbet Abstract Classes",
                "https://sorbet.org/docs/sealed": "Sorbet Sealed Classes",
                "https://sorbet.org/docs/tenum": "Sorbet T::Enum",
                "https://sorbet.org/docs/tstruct": "Sorbet T::Struct",
                # Ruby on Rails blog / news
                "https://rubyonrails.org/": "Ruby on Rails Home",
                "https://rubyonrails.org/doctrine": "Rails Doctrine",
                "https://rubyonrails.org/community": "Rails Community",
                # Rails guides additional
                "https://guides.rubyonrails.org/active_support_core_extensions.html": "Rails Active Support Core Extensions",
                "https://guides.rubyonrails.org/generators.html": "Rails Generators",
                "https://guides.rubyonrails.org/active_record_postgresql.html": "Rails Active Record PostgreSQL Guide",
                "https://guides.rubyonrails.org/documents.html": "Rails Documentation Index",
                "https://guides.rubyonrails.org/association_basics.html": "Rails Association Basics (extra)",
                "https://guides.rubyonrails.org/classic_to_zeitwerk_howto.html": "Rails Classic to Zeitwerk (extra)",
                # Haml / Slim templating
                "https://haml.info/docs.html": "Haml Documentation",
                "https://haml.info/docs/yardoc/Haml/Engine.html": "Haml Engine",
            },
        },
        "rails-models": {
            "pages": {
                # Active Record
                "https://guides.rubyonrails.org/active_record_basics.html": "Rails Active Record Basics",
                "https://guides.rubyonrails.org/active_record_migrations.html": "Rails Active Record Migrations",
                "https://guides.rubyonrails.org/active_record_validations.html": "Rails Active Record Validations",
                "https://guides.rubyonrails.org/active_record_callbacks.html": "Rails Active Record Callbacks",
                "https://guides.rubyonrails.org/association_basics.html": "Rails Active Record Associations",
                "https://guides.rubyonrails.org/active_record_querying.html": "Rails Active Record Query Interface",
                "https://guides.rubyonrails.org/active_model_basics.html": "Rails Active Model Basics",
                "https://guides.rubyonrails.org/active_record_postgresql.html": "Rails Active Record PostgreSQL",
                "https://guides.rubyonrails.org/active_record_multiple_databases.html": "Rails Multiple Databases",
                "https://guides.rubyonrails.org/active_record_encryption.html": "Rails Active Record Encryption",
                "https://guides.rubyonrails.org/active_record_composite_primary_keys.html": "Rails Composite Primary Keys",
            },
        },
        "rails-controllers": {
            "pages": {
                # Routing
                "https://guides.rubyonrails.org/routing.html": "Rails Routing",
                # Action Controller
                "https://guides.rubyonrails.org/action_controller_overview.html": "Rails Action Controller Overview",
                "https://guides.rubyonrails.org/api_documentation_guidelines.html": "Rails API Documentation Guidelines",
                "https://guides.rubyonrails.org/ruby_on_rails_guides_guidelines.html": "Rails Guides Guidelines",
                # Rack
                "https://guides.rubyonrails.org/rails_on_rack.html": "Rails on Rack",
            },
        },
        "rails-views": {
            "pages": {
                # Layouts and Rendering
                "https://guides.rubyonrails.org/layouts_and_rendering.html": "Rails Layouts and Rendering",
                # Form Helpers
                "https://guides.rubyonrails.org/form_helpers.html": "Rails Form Helpers",
                # Action View
                "https://guides.rubyonrails.org/action_view_overview.html": "Rails Action View Overview",
                "https://guides.rubyonrails.org/action_view_helpers.html": "Rails Action View Helpers",
            },
        },
        "rails-advanced": {
            "pages": {
                # Active Job
                "https://guides.rubyonrails.org/active_job_basics.html": "Rails Active Job Basics",
                # Action Mailer
                "https://guides.rubyonrails.org/action_mailer_basics.html": "Rails Action Mailer Basics",
                # Action Mailbox
                "https://guides.rubyonrails.org/action_mailbox_basics.html": "Rails Action Mailbox Basics",
                # Action Text
                "https://guides.rubyonrails.org/action_text_overview.html": "Rails Action Text Overview",
                # Active Storage
                "https://guides.rubyonrails.org/active_storage_overview.html": "Rails Active Storage Overview",
                # Action Cable
                "https://guides.rubyonrails.org/action_cable_overview.html": "Rails Action Cable Overview",
                # Asset Pipeline
                "https://guides.rubyonrails.org/asset_pipeline.html": "Rails Asset Pipeline",
                # Caching
                "https://guides.rubyonrails.org/caching_with_rails.html": "Rails Caching",
                # Security
                "https://guides.rubyonrails.org/security.html": "Rails Security Guide",
                # Testing
                "https://guides.rubyonrails.org/testing.html": "Rails Testing Guide",
                # Internationalization
                "https://guides.rubyonrails.org/i18n.html": "Rails Internationalization (I18n)",
                # Webpacker
                "https://guides.rubyonrails.org/webpacker.html": "Rails Webpacker",
                # Classic to Zeitwerk
                "https://guides.rubyonrails.org/classic_to_zeitwerk_howto.html": "Rails Classic to Zeitwerk",
                # Upgrading
                "https://guides.rubyonrails.org/upgrading_ruby_on_rails.html": "Rails Upgrading Guide",
                # Maintenance Policy
                "https://guides.rubyonrails.org/maintenance_policy.html": "Rails Maintenance Policy",
                # Contributing
                "https://guides.rubyonrails.org/contributing_to_ruby_on_rails.html": "Rails Contributing Guide",
                # Release Notes
                "https://guides.rubyonrails.org/7_2_release_notes.html": "Rails 7.2 Release Notes",
                "https://guides.rubyonrails.org/7_1_release_notes.html": "Rails 7.1 Release Notes",
                "https://guides.rubyonrails.org/7_0_release_notes.html": "Rails 7.0 Release Notes",
                "https://guides.rubyonrails.org/6_1_release_notes.html": "Rails 6.1 Release Notes",
                "https://guides.rubyonrails.org/6_0_release_notes.html": "Rails 6.0 Release Notes",
                "https://guides.rubyonrails.org/5_2_release_notes.html": "Rails 5.2 Release Notes",
                # API
                "https://api.rubyonrails.org/": "Rails API Documentation",
                "https://api.rubyonrails.org/classes/ActiveRecord/Base.html": "Rails ActiveRecord::Base",
                "https://api.rubyonrails.org/classes/ActiveRecord/Relation.html": "Rails ActiveRecord::Relation",
                "https://api.rubyonrails.org/classes/ActiveRecord/QueryMethods.html": "Rails ActiveRecord::QueryMethods",
                "https://api.rubyonrails.org/classes/ActiveRecord/FinderMethods.html": "Rails ActiveRecord::FinderMethods",
                "https://api.rubyonrails.org/classes/ActiveRecord/Calculations.html": "Rails ActiveRecord::Calculations",
                "https://api.rubyonrails.org/classes/ActiveRecord/Associations/ClassMethods.html": "Rails ActiveRecord Associations",
                "https://api.rubyonrails.org/classes/ActiveRecord/Validations.html": "Rails ActiveRecord::Validations",
                "https://api.rubyonrails.org/classes/ActiveRecord/Callbacks.html": "Rails ActiveRecord::Callbacks",
                "https://api.rubyonrails.org/classes/ActiveRecord/Migration.html": "Rails ActiveRecord::Migration",
                "https://api.rubyonrails.org/classes/ActiveRecord/Schema.html": "Rails ActiveRecord::Schema",
                "https://api.rubyonrails.org/classes/ActiveRecord/ConnectionAdapters/SchemaStatements.html": "Rails Schema Statements",
                "https://api.rubyonrails.org/classes/ActionController/Base.html": "Rails ActionController::Base",
                "https://api.rubyonrails.org/classes/ActionController/API.html": "Rails ActionController::API",
                "https://api.rubyonrails.org/classes/ActionController/Parameters.html": "Rails ActionController::Parameters",
                "https://api.rubyonrails.org/classes/ActionView/Base.html": "Rails ActionView::Base",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/FormHelper.html": "Rails FormHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/UrlHelper.html": "Rails UrlHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/TagHelper.html": "Rails TagHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/AssetTagHelper.html": "Rails AssetTagHelper",
                "https://api.rubyonrails.org/classes/ActiveJob/Base.html": "Rails ActiveJob::Base",
                "https://api.rubyonrails.org/classes/ActionMailer/Base.html": "Rails ActionMailer::Base",
                "https://api.rubyonrails.org/classes/ActionCable/Channel/Base.html": "Rails ActionCable::Channel::Base",
                "https://api.rubyonrails.org/classes/ActiveStorage/Blob.html": "Rails ActiveStorage::Blob",
                "https://api.rubyonrails.org/classes/ActiveStorage/Attachment.html": "Rails ActiveStorage::Attachment",
                "https://api.rubyonrails.org/classes/ActiveSupport/Concern.html": "Rails ActiveSupport::Concern",
                "https://api.rubyonrails.org/classes/ActiveSupport/Callbacks.html": "Rails ActiveSupport::Callbacks",
                "https://api.rubyonrails.org/classes/ActiveSupport/TimeWithZone.html": "Rails ActiveSupport::TimeWithZone",
                "https://api.rubyonrails.org/classes/ActiveSupport/Duration.html": "Rails ActiveSupport::Duration",
                "https://api.rubyonrails.org/classes/ActiveSupport/Cache.html": "Rails ActiveSupport::Cache",
                "https://api.rubyonrails.org/classes/ActiveSupport/Notifications.html": "Rails ActiveSupport::Notifications",
                "https://api.rubyonrails.org/classes/ActiveSupport/HashWithIndifferentAccess.html": "Rails HashWithIndifferentAccess",
                # More Rails API classes
                "https://api.rubyonrails.org/classes/ActiveSupport/Inflector.html": "Rails ActiveSupport::Inflector",
                "https://api.rubyonrails.org/classes/ActiveSupport/StringInquirer.html": "Rails ActiveSupport::StringInquirer",
                "https://api.rubyonrails.org/classes/ActiveSupport/OrderedOptions.html": "Rails ActiveSupport::OrderedOptions",
                "https://api.rubyonrails.org/classes/ActiveSupport/Deprecation.html": "Rails ActiveSupport::Deprecation",
                "https://api.rubyonrails.org/classes/ActiveSupport/Logger.html": "Rails ActiveSupport::Logger",
                "https://api.rubyonrails.org/classes/ActiveSupport/MessageEncryptor.html": "Rails ActiveSupport::MessageEncryptor",
                "https://api.rubyonrails.org/classes/ActiveSupport/MessageVerifier.html": "Rails ActiveSupport::MessageVerifier",
                "https://api.rubyonrails.org/classes/ActiveSupport/TaggedLogging.html": "Rails ActiveSupport::TaggedLogging",
                "https://api.rubyonrails.org/classes/ActiveSupport/CurrentAttributes.html": "Rails ActiveSupport::CurrentAttributes",
                "https://api.rubyonrails.org/classes/ActiveSupport/Configurable.html": "Rails ActiveSupport::Configurable",
                "https://api.rubyonrails.org/classes/ActiveSupport/Testing/TimeHelpers.html": "Rails ActiveSupport::Testing::TimeHelpers",
                "https://api.rubyonrails.org/classes/ActiveRecord/Enum.html": "Rails ActiveRecord::Enum",
                "https://api.rubyonrails.org/classes/ActiveRecord/Scoping/Named/ClassMethods.html": "Rails ActiveRecord Scoping",
                "https://api.rubyonrails.org/classes/ActiveRecord/Store.html": "Rails ActiveRecord::Store",
                "https://api.rubyonrails.org/classes/ActiveRecord/Locking/Optimistic.html": "Rails ActiveRecord Optimistic Locking",
                "https://api.rubyonrails.org/classes/ActiveRecord/Locking/Pessimistic.html": "Rails ActiveRecord Pessimistic Locking",
                "https://api.rubyonrails.org/classes/ActiveRecord/Transactions/ClassMethods.html": "Rails ActiveRecord Transactions",
                "https://api.rubyonrails.org/classes/ActiveRecord/NestedAttributes/ClassMethods.html": "Rails Nested Attributes",
                "https://api.rubyonrails.org/classes/ActiveRecord/CounterCache/ClassMethods.html": "Rails Counter Cache",
                "https://api.rubyonrails.org/classes/ActiveRecord/Batches.html": "Rails ActiveRecord::Batches",
                "https://api.rubyonrails.org/classes/ActiveRecord/Sanitization/ClassMethods.html": "Rails ActiveRecord Sanitization",
                "https://api.rubyonrails.org/classes/ActiveRecord/Aggregations/ClassMethods.html": "Rails ActiveRecord Aggregations",
                "https://api.rubyonrails.org/classes/ActiveRecord/Serialization.html": "Rails ActiveRecord::Serialization",
                "https://api.rubyonrails.org/classes/ActiveRecord/AttributeMethods.html": "Rails ActiveRecord::AttributeMethods",
                "https://api.rubyonrails.org/classes/ActiveRecord/Integration.html": "Rails ActiveRecord::Integration",
                "https://api.rubyonrails.org/classes/ActiveRecord/SecureToken/ClassMethods.html": "Rails Secure Token",
                "https://api.rubyonrails.org/classes/ActiveRecord/SignedId.html": "Rails ActiveRecord::SignedId",
                "https://api.rubyonrails.org/classes/ActiveModel/Serialization.html": "Rails ActiveModel::Serialization",
                "https://api.rubyonrails.org/classes/ActiveModel/Serializers/JSON.html": "Rails ActiveModel JSON Serializers",
                "https://api.rubyonrails.org/classes/ActiveModel/Validations.html": "Rails ActiveModel::Validations",
                "https://api.rubyonrails.org/classes/ActiveModel/Dirty.html": "Rails ActiveModel::Dirty",
                "https://api.rubyonrails.org/classes/ActiveModel/Naming.html": "Rails ActiveModel::Naming",
                "https://api.rubyonrails.org/classes/ActiveModel/Conversion.html": "Rails ActiveModel::Conversion",
                "https://api.rubyonrails.org/classes/ActiveModel/Model.html": "Rails ActiveModel::Model",
                "https://api.rubyonrails.org/classes/ActionController/Rendering.html": "Rails ActionController::Rendering",
                "https://api.rubyonrails.org/classes/ActionController/Redirecting.html": "Rails ActionController::Redirecting",
                "https://api.rubyonrails.org/classes/ActionController/Cookies.html": "Rails ActionController::Cookies",
                "https://api.rubyonrails.org/classes/ActionController/Flash.html": "Rails ActionController::Flash",
                "https://api.rubyonrails.org/classes/ActionController/RequestForgeryProtection.html": "Rails CSRF Protection",
                "https://api.rubyonrails.org/classes/ActionController/HttpAuthentication/Basic.html": "Rails HTTP Basic Auth",
                "https://api.rubyonrails.org/classes/ActionController/HttpAuthentication/Token.html": "Rails HTTP Token Auth",
                "https://api.rubyonrails.org/classes/ActionController/Streaming.html": "Rails ActionController::Streaming",
                "https://api.rubyonrails.org/classes/ActionController/Live.html": "Rails ActionController::Live",
                "https://api.rubyonrails.org/classes/ActionController/StrongParameters.html": "Rails Strong Parameters",
                "https://api.rubyonrails.org/classes/ActionController/Caching.html": "Rails ActionController::Caching",
                "https://api.rubyonrails.org/classes/ActionDispatch/Routing.html": "Rails ActionDispatch::Routing",
                "https://api.rubyonrails.org/classes/ActionDispatch/Routing/Mapper.html": "Rails Routing Mapper",
                "https://api.rubyonrails.org/classes/ActionDispatch/Session.html": "Rails ActionDispatch::Session",
                "https://api.rubyonrails.org/classes/ActionDispatch/Request.html": "Rails ActionDispatch::Request",
                "https://api.rubyonrails.org/classes/ActionDispatch/Response.html": "Rails ActionDispatch::Response",
                "https://api.rubyonrails.org/classes/ActionDispatch/IntegrationTest.html": "Rails Integration Testing",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/FormBuilder.html": "Rails FormBuilder",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/DateHelper.html": "Rails DateHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/NumberHelper.html": "Rails NumberHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/TextHelper.html": "Rails TextHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/SanitizeHelper.html": "Rails SanitizeHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/CaptureHelper.html": "Rails CaptureHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/CacheHelper.html": "Rails CacheHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/TranslationHelper.html": "Rails TranslationHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/DebugHelper.html": "Rails DebugHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/JavaScriptHelper.html": "Rails JavaScriptHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/CspHelper.html": "Rails CspHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/OutputSafetyHelper.html": "Rails OutputSafetyHelper",
                "https://api.rubyonrails.org/classes/ActionView/Helpers/RenderingHelper.html": "Rails RenderingHelper",
                "https://api.rubyonrails.org/classes/ActiveJob/QueueAdapters.html": "Rails ActiveJob QueueAdapters",
                "https://api.rubyonrails.org/classes/ActiveJob/Callbacks.html": "Rails ActiveJob::Callbacks",
                "https://api.rubyonrails.org/classes/ActiveJob/Exceptions.html": "Rails ActiveJob::Exceptions",
                "https://api.rubyonrails.org/classes/ActionMailer/MessageDelivery.html": "Rails ActionMailer::MessageDelivery",
                "https://api.rubyonrails.org/classes/ActionMailer/Parameterized.html": "Rails ActionMailer::Parameterized",
                "https://api.rubyonrails.org/classes/ActionCable/Connection/Base.html": "Rails ActionCable Connection",
                "https://api.rubyonrails.org/classes/ActionCable/Channel/Streams.html": "Rails ActionCable Streams",
                "https://api.rubyonrails.org/classes/ActiveStorage/Variant.html": "Rails ActiveStorage::Variant",
                "https://api.rubyonrails.org/classes/ActiveStorage/Service.html": "Rails ActiveStorage::Service",
                "https://api.rubyonrails.org/classes/ActionText/RichText.html": "Rails ActionText::RichText",
                "https://api.rubyonrails.org/classes/ActionText/Content.html": "Rails ActionText::Content",
                "https://api.rubyonrails.org/classes/Rails/Application.html": "Rails::Application",
                "https://api.rubyonrails.org/classes/Rails/Engine.html": "Rails::Engine",
                "https://api.rubyonrails.org/classes/Rails/Railtie.html": "Rails::Railtie",
                "https://api.rubyonrails.org/classes/Rails/Generators/Base.html": "Rails Generators",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"ruby-{source_key}" if source_key else "ruby"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - Ruby Documentation', ' | Ruby Documentation',
                           ' - Ruby-Doc.org', ' | Ruby-Doc.org',
                           ' - Ruby on Rails Guides', ' | Ruby on Rails Guides',
                           ' - Ruby on Rails API', ' | Ruby on Rails API',
                           ' (Ruby 3.3)', ' (Ruby 3.3.0)',
                           ' - Rails API', ' | Rails API']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
        """Scrape all pages for a given source section."""
        count = 0
        pages = config.get("pages", {})

        for url, title in pages.items():
            if not self.running:
                break

            item_id = self.make_id(url)
            content = self.fetch_url(url)

            if content and len(content) > 500:
                text = self._strip_html(content)
                if len(text) > 100:
                    page_title = self._extract_title(content, title)

                    if self.save_item(item_id, {
                        "title": page_title,
                        "content": text[:50000],
                        "url": url,
                        "category": f"ruby-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)

        return count

    def scrape(self):
        """Run scrape across all or a specific source."""
        total = 0

        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(
                    f"Unknown source key: {self.source_key}. "
                    f"Available: {list(self.SOURCES.keys())}"
                )
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES

        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping ruby/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    RubyScraper(base, source_key).run()
