#!/usr/bin/env python3
"""Swift documentation scraper.

Covers:
  - The Swift Programming Language book (basics, strings, collections,
    control flow, functions, closures, enumerations, classes, structs,
    properties, methods, subscripts, inheritance, initialization,
    deinitialization, optional chaining, error handling, concurrency,
    macros, type casting, nested types, extensions, protocols, generics,
    opaque types, ARC, memory safety, access control, advanced operators)
  - Standard Library
  - Package Manager
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class SwiftScraper(BaseScraper):
    """Scrape Swift documentation from docs.swift.org and swift.org."""

    SOURCES = {
        "swift-book": {
            "pages": {
                # Welcome
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/": "The Swift Programming Language",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutswift": "About Swift",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/compatibility": "Version Compatibility",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/guidedtour": "A Swift Tour",
                # Language Guide
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/thebasics": "Swift The Basics",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/basicoperators": "Swift Basic Operators",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/stringsandcharacters": "Swift Strings and Characters",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/collectiontypes": "Swift Collection Types",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/controlflow": "Swift Control Flow",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/functions": "Swift Functions",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/closures": "Swift Closures",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/enumerations": "Swift Enumerations",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/classesandstructures": "Swift Structures and Classes",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/properties": "Swift Properties",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/methods": "Swift Methods",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/subscripts": "Swift Subscripts",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/inheritance": "Swift Inheritance",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/initialization": "Swift Initialization",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/deinitialization": "Swift Deinitialization",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/optionalchaining": "Swift Optional Chaining",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/errorhandling": "Swift Error Handling",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/concurrency": "Swift Concurrency",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/macros": "Swift Macros",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/typecasting": "Swift Type Casting",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/nestedtypes": "Swift Nested Types",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/extensions": "Swift Extensions",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/protocols": "Swift Protocols",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/generics": "Swift Generics",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/opaquetypes": "Swift Opaque and Boxed Types",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/automaticreferencecounting": "Swift Automatic Reference Counting",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/memorysafety": "Swift Memory Safety",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/accesscontrol": "Swift Access Control",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/advancedoperators": "Swift Advanced Operators",
                # Language Reference
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/aboutthelanguagereference": "Swift Language Reference About",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/lexicalstructure": "Swift Lexical Structure",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/types": "Swift Types",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/expressions": "Swift Expressions",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/statements": "Swift Statements",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/declarations": "Swift Declarations",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/attributes": "Swift Attributes",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/patterns": "Swift Patterns",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/genericparametersandarguments": "Swift Generic Parameters and Arguments",
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/summaryofthegrammar": "Swift Summary of the Grammar",
                # Revision History
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/revisionhistory": "Swift Book Revision History",
            },
        },
        "standard-library": {
            "pages": {
                # Swift Standard Library
                "https://developer.apple.com/documentation/swift": "Swift Documentation",
                "https://developer.apple.com/documentation/swift/string": "Swift String",
                "https://developer.apple.com/documentation/swift/int": "Swift Int",
                "https://developer.apple.com/documentation/swift/double": "Swift Double",
                "https://developer.apple.com/documentation/swift/float": "Swift Float",
                "https://developer.apple.com/documentation/swift/bool": "Swift Bool",
                "https://developer.apple.com/documentation/swift/array": "Swift Array",
                "https://developer.apple.com/documentation/swift/dictionary": "Swift Dictionary",
                "https://developer.apple.com/documentation/swift/set": "Swift Set",
                "https://developer.apple.com/documentation/swift/optional": "Swift Optional",
                "https://developer.apple.com/documentation/swift/result": "Swift Result",
                "https://developer.apple.com/documentation/swift/character": "Swift Character",
                "https://developer.apple.com/documentation/swift/substring": "Swift Substring",
                "https://developer.apple.com/documentation/swift/range": "Swift Range",
                "https://developer.apple.com/documentation/swift/closedrange": "Swift ClosedRange",
                "https://developer.apple.com/documentation/swift/sequence": "Swift Sequence",
                "https://developer.apple.com/documentation/swift/collection": "Swift Collection",
                "https://developer.apple.com/documentation/swift/iteratorprotocol": "Swift IteratorProtocol",
                "https://developer.apple.com/documentation/swift/comparable": "Swift Comparable",
                "https://developer.apple.com/documentation/swift/equatable": "Swift Equatable",
                "https://developer.apple.com/documentation/swift/hashable": "Swift Hashable",
                "https://developer.apple.com/documentation/swift/codable": "Swift Codable",
                "https://developer.apple.com/documentation/swift/encodable": "Swift Encodable",
                "https://developer.apple.com/documentation/swift/decodable": "Swift Decodable",
                "https://developer.apple.com/documentation/swift/customstringconvertible": "Swift CustomStringConvertible",
                "https://developer.apple.com/documentation/swift/error": "Swift Error Protocol",
                "https://developer.apple.com/documentation/swift/identifiable": "Swift Identifiable",
                "https://developer.apple.com/documentation/swift/sendable": "Swift Sendable",
                "https://developer.apple.com/documentation/swift/actor": "Swift Actor",
                "https://developer.apple.com/documentation/swift/globalactor": "Swift GlobalActor",
                "https://developer.apple.com/documentation/swift/mainactor": "Swift MainActor",
                "https://developer.apple.com/documentation/swift/task": "Swift Task",
                "https://developer.apple.com/documentation/swift/taskgroup": "Swift TaskGroup",
                "https://developer.apple.com/documentation/swift/asyncsequence": "Swift AsyncSequence",
                "https://developer.apple.com/documentation/swift/asyncstream": "Swift AsyncStream",
                "https://developer.apple.com/documentation/swift/checkedcontinuation": "Swift CheckedContinuation",
                "https://developer.apple.com/documentation/swift/unsafecontinuation": "Swift UnsafeContinuation",
                "https://developer.apple.com/documentation/swift/slice": "Swift Slice",
                "https://developer.apple.com/documentation/swift/lazycollectionprotocol": "Swift LazyCollectionProtocol",
                "https://developer.apple.com/documentation/swift/lazysequenceprotocol": "Swift LazySequenceProtocol",
                "https://developer.apple.com/documentation/swift/keyvaluepairs": "Swift KeyValuePairs",
                "https://developer.apple.com/documentation/swift/mirror": "Swift Mirror",
                "https://developer.apple.com/documentation/swift/commandline": "Swift CommandLine",
                "https://developer.apple.com/documentation/swift/print(_:separator:terminator:)": "Swift print",
                "https://developer.apple.com/documentation/swift/assert(_:_:file:line:)": "Swift assert",
                "https://developer.apple.com/documentation/swift/precondition(_:_:file:line:)": "Swift precondition",
                "https://developer.apple.com/documentation/swift/fatalerror(_:file:line:)": "Swift fatalError",
                "https://developer.apple.com/documentation/swift/unsafepointer": "Swift UnsafePointer",
                "https://developer.apple.com/documentation/swift/unsafemutablepointer": "Swift UnsafeMutablePointer",
                "https://developer.apple.com/documentation/swift/unsafebufferpointer": "Swift UnsafeBufferPointer",
                "https://developer.apple.com/documentation/swift/unsaferawpointer": "Swift UnsafeRawPointer",
                "https://developer.apple.com/documentation/swift/managedbyteorder": "Swift ManagedByteOrder",
                # Foundation
                "https://developer.apple.com/documentation/foundation": "Swift Foundation",
                "https://developer.apple.com/documentation/foundation/url": "Swift Foundation URL",
                "https://developer.apple.com/documentation/foundation/urlsession": "Swift Foundation URLSession",
                "https://developer.apple.com/documentation/foundation/urlrequest": "Swift Foundation URLRequest",
                "https://developer.apple.com/documentation/foundation/jsonencoder": "Swift Foundation JSONEncoder",
                "https://developer.apple.com/documentation/foundation/jsondecoder": "Swift Foundation JSONDecoder",
                "https://developer.apple.com/documentation/foundation/data": "Swift Foundation Data",
                "https://developer.apple.com/documentation/foundation/date": "Swift Foundation Date",
                "https://developer.apple.com/documentation/foundation/dateformatter": "Swift Foundation DateFormatter",
                "https://developer.apple.com/documentation/foundation/calendar": "Swift Foundation Calendar",
                "https://developer.apple.com/documentation/foundation/uuid": "Swift Foundation UUID",
                "https://developer.apple.com/documentation/foundation/filemanager": "Swift Foundation FileManager",
                "https://developer.apple.com/documentation/foundation/userdefaults": "Swift Foundation UserDefaults",
                "https://developer.apple.com/documentation/foundation/notificationcenter": "Swift Foundation NotificationCenter",
                "https://developer.apple.com/documentation/foundation/timer": "Swift Foundation Timer",
                "https://developer.apple.com/documentation/foundation/processinfo": "Swift Foundation ProcessInfo",
                "https://developer.apple.com/documentation/foundation/nserror": "Swift Foundation NSError",
                "https://developer.apple.com/documentation/foundation/nsregularexpression": "Swift Foundation NSRegularExpression",
                "https://developer.apple.com/documentation/foundation/attributedstring": "Swift Foundation AttributedString",
                "https://developer.apple.com/documentation/foundation/propertylistencoder": "Swift Foundation PropertyListEncoder",
                "https://developer.apple.com/documentation/foundation/propertylistdecoder": "Swift Foundation PropertyListDecoder",
                # More Foundation
                "https://developer.apple.com/documentation/foundation/bundle": "Swift Foundation Bundle",
                "https://developer.apple.com/documentation/foundation/locale": "Swift Foundation Locale",
                "https://developer.apple.com/documentation/foundation/timezone": "Swift Foundation TimeZone",
                "https://developer.apple.com/documentation/foundation/measurement": "Swift Foundation Measurement",
                "https://developer.apple.com/documentation/foundation/numberformatter": "Swift Foundation NumberFormatter",
                "https://developer.apple.com/documentation/foundation/iso8601dateformatter": "Swift Foundation ISO8601DateFormatter",
                "https://developer.apple.com/documentation/foundation/operationqueue": "Swift Foundation OperationQueue",
                "https://developer.apple.com/documentation/foundation/operation": "Swift Foundation Operation",
                "https://developer.apple.com/documentation/foundation/dispatchqueue": "Swift Foundation DispatchQueue",
                "https://developer.apple.com/documentation/foundation/runloop": "Swift Foundation RunLoop",
                "https://developer.apple.com/documentation/foundation/urlsessiontask": "Swift Foundation URLSessionTask",
                "https://developer.apple.com/documentation/foundation/urlsessiondatatask": "Swift Foundation URLSessionDataTask",
                "https://developer.apple.com/documentation/foundation/urlsessiondownloadtask": "Swift Foundation URLSessionDownloadTask",
                "https://developer.apple.com/documentation/foundation/urlsessionuploadtask": "Swift Foundation URLSessionUploadTask",
                "https://developer.apple.com/documentation/foundation/urlsessionconfiguration": "Swift Foundation URLSessionConfiguration",
                "https://developer.apple.com/documentation/foundation/httpurlresponse": "Swift Foundation HTTPURLResponse",
                "https://developer.apple.com/documentation/foundation/urlcomponents": "Swift Foundation URLComponents",
                "https://developer.apple.com/documentation/foundation/urlqueryitem": "Swift Foundation URLQueryItem",
                "https://developer.apple.com/documentation/foundation/notification": "Swift Foundation Notification",
                "https://developer.apple.com/documentation/foundation/notification/name": "Swift Foundation Notification.Name",
                "https://developer.apple.com/documentation/foundation/nsstring": "Swift Foundation NSString",
                "https://developer.apple.com/documentation/foundation/nsmutablestring": "Swift Foundation NSMutableString",
                "https://developer.apple.com/documentation/foundation/nsarray": "Swift Foundation NSArray",
                "https://developer.apple.com/documentation/foundation/nsmutablearray": "Swift Foundation NSMutableArray",
                "https://developer.apple.com/documentation/foundation/nsdictionary": "Swift Foundation NSDictionary",
                "https://developer.apple.com/documentation/foundation/nsmutabledictionary": "Swift Foundation NSMutableDictionary",
                "https://developer.apple.com/documentation/foundation/nsset": "Swift Foundation NSSet",
                "https://developer.apple.com/documentation/foundation/nscache": "Swift Foundation NSCache",
                "https://developer.apple.com/documentation/foundation/nscoding": "Swift Foundation NSCoding",
                "https://developer.apple.com/documentation/foundation/nssecurecoding": "Swift Foundation NSSecureCoding",
                "https://developer.apple.com/documentation/foundation/nscopying": "Swift Foundation NSCopying",
                "https://developer.apple.com/documentation/foundation/nsobject": "Swift Foundation NSObject",
                "https://developer.apple.com/documentation/foundation/nsvalue": "Swift Foundation NSValue",
                "https://developer.apple.com/documentation/foundation/nsnumber": "Swift Foundation NSNumber",
                "https://developer.apple.com/documentation/foundation/nsdecimalnumber": "Swift Foundation NSDecimalNumber",
                "https://developer.apple.com/documentation/foundation/decimal": "Swift Foundation Decimal",
                "https://developer.apple.com/documentation/foundation/characterset": "Swift Foundation CharacterSet",
                "https://developer.apple.com/documentation/foundation/indexpath": "Swift Foundation IndexPath",
                "https://developer.apple.com/documentation/foundation/indexset": "Swift Foundation IndexSet",
                "https://developer.apple.com/documentation/foundation/nspredicate": "Swift Foundation NSPredicate",
                "https://developer.apple.com/documentation/foundation/nssortdescriptor": "Swift Foundation NSSortDescriptor",
                "https://developer.apple.com/documentation/foundation/nserror": "Swift Foundation NSError (detailed)",
                "https://developer.apple.com/documentation/foundation/nsexception": "Swift Foundation NSException",
                "https://developer.apple.com/documentation/foundation/nsthread": "Swift Foundation NSThread",
                "https://developer.apple.com/documentation/foundation/nslock": "Swift Foundation NSLock",
                "https://developer.apple.com/documentation/foundation/nscondition": "Swift Foundation NSCondition",
                # Combine
                "https://developer.apple.com/documentation/combine": "Swift Combine",
                "https://developer.apple.com/documentation/combine/publisher": "Swift Combine Publisher",
                "https://developer.apple.com/documentation/combine/subscriber": "Swift Combine Subscriber",
                "https://developer.apple.com/documentation/combine/subject": "Swift Combine Subject",
                "https://developer.apple.com/documentation/combine/passthroughsubject": "Swift Combine PassthroughSubject",
                "https://developer.apple.com/documentation/combine/currentvaluesubject": "Swift Combine CurrentValueSubject",
                "https://developer.apple.com/documentation/combine/anypublisher": "Swift Combine AnyPublisher",
                "https://developer.apple.com/documentation/combine/anycancellable": "Swift Combine AnyCancellable",
                "https://developer.apple.com/documentation/combine/just": "Swift Combine Just",
                "https://developer.apple.com/documentation/combine/future": "Swift Combine Future",
                # Observation
                "https://developer.apple.com/documentation/observation": "Swift Observation",
                # Concurrency
                "https://developer.apple.com/documentation/swift/withtaskgroup(of:returning:body:)": "Swift withTaskGroup",
                "https://developer.apple.com/documentation/swift/withcheckedcontinuation(function:_:)": "Swift withCheckedContinuation",
                "https://developer.apple.com/documentation/swift/withunsafecontinuation(_:)": "Swift withUnsafeContinuation",
                "https://developer.apple.com/documentation/swift/withcheckedthrowingcontinuation(function:_:)": "Swift withCheckedThrowingContinuation",
                # Swift Testing
                "https://developer.apple.com/documentation/testing": "Swift Testing Framework",
                # Dispatch
                "https://developer.apple.com/documentation/dispatch": "Swift Dispatch",
                "https://developer.apple.com/documentation/dispatch/dispatchqueue": "Swift Dispatch DispatchQueue",
                "https://developer.apple.com/documentation/dispatch/dispatchgroup": "Swift Dispatch DispatchGroup",
                "https://developer.apple.com/documentation/dispatch/dispatchsemaphore": "Swift Dispatch DispatchSemaphore",
                "https://developer.apple.com/documentation/dispatch/dispatchworkitem": "Swift Dispatch DispatchWorkItem",
                "https://developer.apple.com/documentation/dispatch/dispatchsource": "Swift Dispatch DispatchSource",
                # XCTest
                "https://developer.apple.com/documentation/xctest": "Swift XCTest",
                "https://developer.apple.com/documentation/xctest/xctestcase": "Swift XCTestCase",
                "https://developer.apple.com/documentation/xctest/xctestexpectation": "Swift XCTestExpectation",
                # Swift Standard Library additional
                "https://developer.apple.com/documentation/swift/regexcomponent": "Swift RegexComponent",
                "https://developer.apple.com/documentation/swift/regex": "Swift Regex",
                "https://developer.apple.com/documentation/swift/duration": "Swift Duration",
                "https://developer.apple.com/documentation/swift/clock": "Swift Clock",
                "https://developer.apple.com/documentation/swift/continuousclock": "Swift ContinuousClock",
                "https://developer.apple.com/documentation/swift/suspendingclock": "Swift SuspendingClock",
                "https://developer.apple.com/documentation/swift/discardingresults": "Swift DiscardingResults",
                "https://developer.apple.com/documentation/swift/withobservationtracking(_:onchange:)": "Swift withObservationTracking",
            },
        },
        "package-manager": {
            "pages": {
                # Swift Package Manager
                "https://www.swift.org/documentation/package-manager/": "Swift Package Manager",
                "https://www.swift.org/getting-started/swiftpm-library/": "Swift Package Manager Library",
                "https://www.swift.org/getting-started/cli-swiftpm/": "Swift CLI with SwiftPM",
                # swift.org pages
                "https://www.swift.org/about/": "About Swift",
                "https://www.swift.org/blog/": "Swift Blog",
                "https://www.swift.org/getting-started/": "Swift Getting Started",
                "https://www.swift.org/install/": "Swift Installation",
                "https://www.swift.org/install/linux/": "Swift Install on Linux",
                "https://www.swift.org/install/macos/": "Swift Install on macOS",
                "https://www.swift.org/install/windows/": "Swift Install on Windows",
                "https://www.swift.org/documentation/": "Swift Documentation",
                "https://www.swift.org/documentation/api-design-guidelines/": "Swift API Design Guidelines",
                "https://www.swift.org/documentation/server/": "Swift on Server",
                "https://www.swift.org/documentation/cxx-interop/": "Swift C++ Interop",
                "https://www.swift.org/documentation/articles/zero-to-swift-nvim.html": "Zero to Swift NVim",
                "https://www.swift.org/migration-guide/": "Swift Migration Guide",
                "https://www.swift.org/contributing/": "Swift Contributing",
                "https://www.swift.org/community/": "Swift Community",
                "https://www.swift.org/diversity/": "Swift Diversity",
                "https://www.swift.org/platform-support/": "Swift Platform Support",
                # Swift evolution
                "https://www.swift.org/swift-evolution/": "Swift Evolution",
                # Server-side Swift
                "https://www.swift.org/documentation/server/guides/deploying/aws-copilot.html": "Swift Server Deploy to AWS",
                "https://www.swift.org/documentation/server/guides/deploying/digital-ocean.html": "Swift Server Deploy to DigitalOcean",
                "https://www.swift.org/documentation/server/guides/libraries/log-levels.html": "Swift Server Logging",
                "https://www.swift.org/documentation/server/guides/packaging.html": "Swift Server Packaging",
                # Concurrency
                "https://www.swift.org/documentation/concurrency/": "Swift Concurrency Overview",
                # Testing
                "https://www.swift.org/documentation/testing/": "Swift Testing",
                # Blog posts (technical depth)
                "https://www.swift.org/blog/announcing-swift-6/": "Swift 6 Announcement",
                "https://www.swift.org/blog/swift-5.10-released/": "Swift 5.10 Released",
                "https://www.swift.org/blog/swift-5.9-released/": "Swift 5.9 Released",
                "https://www.swift.org/blog/swift-5.8-released/": "Swift 5.8 Released",
                "https://www.swift.org/blog/swift-5.7-released/": "Swift 5.7 Released",
                "https://www.swift.org/blog/swift-regex/": "Swift Regex Blog",
                "https://www.swift.org/blog/swift-async-algorithms/": "Swift Async Algorithms",
                "https://www.swift.org/blog/distributed-actors/": "Swift Distributed Actors",
                "https://www.swift.org/blog/swift-certificates-and-asn1/": "Swift Certificates and ASN.1",
                "https://www.swift.org/blog/swift-openapi-generator-1.0/": "Swift OpenAPI Generator 1.0",
                "https://www.swift.org/blog/byte-sized-swift/": "Byte-Sized Swift",
                "https://www.swift.org/blog/swift-testing-vision/": "Swift Testing Vision",
                "https://www.swift.org/blog/package-registry/": "Swift Package Registry",
                # Swift TSPL additional chapters
                "https://docs.swift.org/swift-book/documentation/the-swift-programming-language/opaqueandboxedtypes": "Swift Opaque and Boxed Types (alt)",
                # Developer documentation additional
                "https://developer.apple.com/documentation/swift/adopting-strict-concurrency-checking": "Swift Strict Concurrency Checking",
                "https://developer.apple.com/documentation/swift/updating-an-app-to-use-strict-concurrency": "Swift Updating for Strict Concurrency",
                "https://developer.apple.com/documentation/swift/calling-objective-c-apis-in-swift": "Calling Objective-C APIs in Swift",
                "https://developer.apple.com/documentation/swift/imported-c-and-objective-c-apis": "Swift Imported C and ObjC APIs",
                "https://developer.apple.com/documentation/swift/using-imported-c-structs-and-unions-in-swift": "Swift Using C Structs",
                "https://developer.apple.com/documentation/swift/using-imported-c-macros-in-swift": "Swift Using C Macros",
                "https://developer.apple.com/documentation/swift/maintaining-state-in-your-apps": "Swift Maintaining State",
                "https://developer.apple.com/documentation/swift/preventing-timing-problems-when-using-closures": "Swift Closure Timing",
                "https://developer.apple.com/documentation/swift/choosing-between-structures-and-classes": "Swift Structs vs Classes",
                "https://developer.apple.com/documentation/swift/handling-dynamically-typed-methods-and-objects-in-swift": "Swift Dynamic Typing",
                # More Swift types
                "https://developer.apple.com/documentation/swift/uint": "Swift UInt",
                "https://developer.apple.com/documentation/swift/int8": "Swift Int8",
                "https://developer.apple.com/documentation/swift/int16": "Swift Int16",
                "https://developer.apple.com/documentation/swift/int32": "Swift Int32",
                "https://developer.apple.com/documentation/swift/int64": "Swift Int64",
                "https://developer.apple.com/documentation/swift/uint8": "Swift UInt8",
                "https://developer.apple.com/documentation/swift/uint16": "Swift UInt16",
                "https://developer.apple.com/documentation/swift/uint32": "Swift UInt32",
                "https://developer.apple.com/documentation/swift/uint64": "Swift UInt64",
                "https://developer.apple.com/documentation/swift/simd2": "Swift SIMD2",
                "https://developer.apple.com/documentation/swift/simd3": "Swift SIMD3",
                "https://developer.apple.com/documentation/swift/simd4": "Swift SIMD4",
                "https://developer.apple.com/documentation/swift/managedbuffer": "Swift ManagedBuffer",
                "https://developer.apple.com/documentation/swift/unmanaged": "Swift Unmanaged",
                "https://developer.apple.com/documentation/swift/strideable": "Swift Strideable",
                "https://developer.apple.com/documentation/swift/bidirectionalcollection": "Swift BidirectionalCollection",
                "https://developer.apple.com/documentation/swift/randomaccesscollection": "Swift RandomAccessCollection",
                "https://developer.apple.com/documentation/swift/mutablecollection": "Swift MutableCollection",
                "https://developer.apple.com/documentation/swift/rangereplaceable-collection": "Swift RangeReplaceableCollection",
                "https://developer.apple.com/documentation/swift/stringprotocol": "Swift StringProtocol",
                "https://developer.apple.com/documentation/swift/numericprotocol": "Swift Numeric",
                "https://developer.apple.com/documentation/swift/signedintnumeric": "Swift SignedNumeric",
                "https://developer.apple.com/documentation/swift/fixedwidthinteger": "Swift FixedWidthInteger",
                "https://developer.apple.com/documentation/swift/binaryinteger": "Swift BinaryInteger",
                "https://developer.apple.com/documentation/swift/floatingpoint": "Swift FloatingPoint",
                "https://developer.apple.com/documentation/swift/binaryfloatingpoint": "Swift BinaryFloatingPoint",
                "https://developer.apple.com/documentation/swift/rawrepresentable": "Swift RawRepresentable",
                "https://developer.apple.com/documentation/swift/caseiterable": "Swift CaseIterable",
                "https://developer.apple.com/documentation/swift/expressiblebystringliteral": "Swift ExpressibleByStringLiteral",
                "https://developer.apple.com/documentation/swift/expressiblebyintegerliteral": "Swift ExpressibleByIntegerLiteral",
                "https://developer.apple.com/documentation/swift/expressiblebyfloatliteral": "Swift ExpressibleByFloatLiteral",
                "https://developer.apple.com/documentation/swift/expressiblebybooleanliteral": "Swift ExpressibleByBooleanLiteral",
                "https://developer.apple.com/documentation/swift/expressiblebynilliteral": "Swift ExpressibleByNilLiteral",
                "https://developer.apple.com/documentation/swift/expressiblebyarrayliteral": "Swift ExpressibleByArrayLiteral",
                "https://developer.apple.com/documentation/swift/expressiblebydictionaryliteral": "Swift ExpressibleByDictionaryLiteral",
                "https://developer.apple.com/documentation/swift/textoutputstream": "Swift TextOutputStreamable",
                "https://developer.apple.com/documentation/swift/customdebugstringconvertible": "Swift CustomDebugStringConvertible",
                "https://developer.apple.com/documentation/swift/customreflectable": "Swift CustomReflectable",
                "https://developer.apple.com/documentation/swift/losslessstringconvertible": "Swift LosslessStringConvertible",
                "https://developer.apple.com/documentation/swift/neverconvertible": "Swift Never",
                # Swift Argument Parser
                "https://www.swift.org/blog/argument-parser/": "Swift Argument Parser",
                # Server-side Swift libraries
                "https://www.swift.org/documentation/server/guides/libraries/": "Swift Server Libraries",
                "https://www.swift.org/documentation/server/guides/setup.html": "Swift Server Setup",
                "https://www.swift.org/documentation/server/guides/linux.html": "Swift Server Linux",
                "https://www.swift.org/documentation/server/guides/performance.html": "Swift Server Performance",
                # More Swift blog
                "https://www.swift.org/blog/swift-embedded-examples/": "Swift Embedded Examples",
                "https://www.swift.org/blog/swift-foundation/": "Swift Foundation Blog",
                "https://www.swift.org/blog/noncopyable-switch-and-borrow/": "Swift Noncopyable Switch and Borrow",
                "https://www.swift.org/blog/swift-syntax/": "Swift Syntax",
                "https://www.swift.org/blog/swift-format/": "Swift Format",
                "https://www.swift.org/blog/swift-evolution-status-page/": "Swift Evolution Status Page",
                "https://www.swift.org/blog/swift-on-server-linux-performance/": "Swift Server Linux Performance",
                "https://www.swift.org/blog/value-and-reference-types/": "Swift Value and Reference Types",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"swift-{source_key}" if source_key else "swift"
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
            for suffix in [' | Documentation', ' - Swift.org',
                           ' | Apple Developer Documentation',
                           ' - The Swift Programming Language',
                           ' | Swift.org', ' - Swift',
                           ' | The Swift Programming Language']:
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
                        "category": f"swift-{source_key}",
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
            self.log.info(f"=== Scraping swift/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    SwiftScraper(base, source_key).run()
