#!/usr/bin/env python3
"""PHP documentation scraper.

Covers:
  - Language Reference (types, variables, constants, operators, etc.)
  - Function Reference (string, array, math, date, file, json, regex, etc.)
  - Security (best practices, SQL injection, XSS, etc.)
  - Features (HTTP auth, cookies, sessions, file uploads, etc.)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class PHPScraper(BaseScraper):
    """Scrape PHP documentation from php.net."""

    SOURCES = {
        "language-reference": {
            "pages": {
                # Types
                "https://www.php.net/manual/en/language.types.php": "PHP Types Overview",
                "https://www.php.net/manual/en/language.types.intro.php": "PHP Types Introduction",
                "https://www.php.net/manual/en/language.types.type-system.php": "PHP Type System",
                "https://www.php.net/manual/en/language.types.null.php": "PHP Null Type",
                "https://www.php.net/manual/en/language.types.boolean.php": "PHP Booleans",
                "https://www.php.net/manual/en/language.types.integer.php": "PHP Integers",
                "https://www.php.net/manual/en/language.types.float.php": "PHP Floating Point Numbers",
                "https://www.php.net/manual/en/language.types.string.php": "PHP Strings",
                "https://www.php.net/manual/en/language.types.numeric-strings.php": "PHP Numeric Strings",
                "https://www.php.net/manual/en/language.types.array.php": "PHP Arrays",
                "https://www.php.net/manual/en/language.types.object.php": "PHP Objects",
                "https://www.php.net/manual/en/language.types.enumerations.php": "PHP Enumerations",
                "https://www.php.net/manual/en/language.types.resource.php": "PHP Resources",
                "https://www.php.net/manual/en/language.types.callable.php": "PHP Callbacks / Callables",
                "https://www.php.net/manual/en/language.types.mixed.php": "PHP Mixed Type",
                "https://www.php.net/manual/en/language.types.void.php": "PHP Void Type",
                "https://www.php.net/manual/en/language.types.never.php": "PHP Never Type",
                "https://www.php.net/manual/en/language.types.relative-class-types.php": "PHP Relative Class Types",
                "https://www.php.net/manual/en/language.types.value.php": "PHP Value Types",
                "https://www.php.net/manual/en/language.types.iterable.php": "PHP Iterables",
                "https://www.php.net/manual/en/language.types.declarations.php": "PHP Type Declarations",
                "https://www.php.net/manual/en/language.types.type-juggling.php": "PHP Type Juggling",
                # Variables
                "https://www.php.net/manual/en/language.variables.php": "PHP Variables",
                "https://www.php.net/manual/en/language.variables.basics.php": "PHP Variables Basics",
                "https://www.php.net/manual/en/language.variables.predefined.php": "PHP Predefined Variables",
                "https://www.php.net/manual/en/language.variables.scope.php": "PHP Variable Scope",
                "https://www.php.net/manual/en/language.variables.variable.php": "PHP Variable Variables",
                "https://www.php.net/manual/en/language.variables.external.php": "PHP External Variables",
                "https://www.php.net/manual/en/language.variables.superglobals.php": "PHP Superglobals",
                "https://www.php.net/manual/en/reserved.variables.server.php": "PHP $_SERVER",
                "https://www.php.net/manual/en/reserved.variables.get.php": "PHP $_GET",
                "https://www.php.net/manual/en/reserved.variables.post.php": "PHP $_POST",
                "https://www.php.net/manual/en/reserved.variables.files.php": "PHP $_FILES",
                "https://www.php.net/manual/en/reserved.variables.request.php": "PHP $_REQUEST",
                "https://www.php.net/manual/en/reserved.variables.session.php": "PHP $_SESSION",
                "https://www.php.net/manual/en/reserved.variables.environment.php": "PHP $_ENV",
                "https://www.php.net/manual/en/reserved.variables.cookies.php": "PHP $_COOKIE",
                "https://www.php.net/manual/en/reserved.variables.globals.php": "PHP $GLOBALS",
                # Constants
                "https://www.php.net/manual/en/language.constants.php": "PHP Constants",
                "https://www.php.net/manual/en/language.constants.syntax.php": "PHP Constant Syntax",
                "https://www.php.net/manual/en/language.constants.predefined.php": "PHP Magic Constants",
                # Expressions
                "https://www.php.net/manual/en/language.expressions.php": "PHP Expressions",
                # Operators
                "https://www.php.net/manual/en/language.operators.php": "PHP Operators",
                "https://www.php.net/manual/en/language.operators.precedence.php": "PHP Operator Precedence",
                "https://www.php.net/manual/en/language.operators.arithmetic.php": "PHP Arithmetic Operators",
                "https://www.php.net/manual/en/language.operators.assignment.php": "PHP Assignment Operators",
                "https://www.php.net/manual/en/language.operators.bitwise.php": "PHP Bitwise Operators",
                "https://www.php.net/manual/en/language.operators.comparison.php": "PHP Comparison Operators",
                "https://www.php.net/manual/en/language.operators.errorcontrol.php": "PHP Error Control Operators",
                "https://www.php.net/manual/en/language.operators.execution.php": "PHP Execution Operators",
                "https://www.php.net/manual/en/language.operators.increment.php": "PHP Increment/Decrement",
                "https://www.php.net/manual/en/language.operators.logical.php": "PHP Logical Operators",
                "https://www.php.net/manual/en/language.operators.string.php": "PHP String Operators",
                "https://www.php.net/manual/en/language.operators.array.php": "PHP Array Operators",
                "https://www.php.net/manual/en/language.operators.type.php": "PHP Type Operators",
                # Control Structures
                "https://www.php.net/manual/en/language.control-structures.php": "PHP Control Structures",
                "https://www.php.net/manual/en/control-structures.if.php": "PHP if",
                "https://www.php.net/manual/en/control-structures.else.php": "PHP else",
                "https://www.php.net/manual/en/control-structures.elseif.php": "PHP elseif",
                "https://www.php.net/manual/en/control-structures.while.php": "PHP while",
                "https://www.php.net/manual/en/control-structures.do.while.php": "PHP do-while",
                "https://www.php.net/manual/en/control-structures.for.php": "PHP for",
                "https://www.php.net/manual/en/control-structures.foreach.php": "PHP foreach",
                "https://www.php.net/manual/en/control-structures.break.php": "PHP break",
                "https://www.php.net/manual/en/control-structures.continue.php": "PHP continue",
                "https://www.php.net/manual/en/control-structures.switch.php": "PHP switch",
                "https://www.php.net/manual/en/control-structures.match.php": "PHP match",
                "https://www.php.net/manual/en/control-structures.declare.php": "PHP declare",
                "https://www.php.net/manual/en/function.return.php": "PHP return",
                "https://www.php.net/manual/en/function.include.php": "PHP include",
                "https://www.php.net/manual/en/function.include-once.php": "PHP include_once",
                "https://www.php.net/manual/en/function.require.php": "PHP require",
                "https://www.php.net/manual/en/function.require-once.php": "PHP require_once",
                "https://www.php.net/manual/en/control-structures.goto.php": "PHP goto",
                # Functions
                "https://www.php.net/manual/en/language.functions.php": "PHP Functions",
                "https://www.php.net/manual/en/functions.user-defined.php": "PHP User-defined Functions",
                "https://www.php.net/manual/en/functions.arguments.php": "PHP Function Arguments",
                "https://www.php.net/manual/en/functions.returning-values.php": "PHP Returning Values",
                "https://www.php.net/manual/en/functions.variable-functions.php": "PHP Variable Functions",
                "https://www.php.net/manual/en/functions.internal.php": "PHP Internal Functions",
                "https://www.php.net/manual/en/functions.anonymous.php": "PHP Anonymous Functions",
                "https://www.php.net/manual/en/functions.arrow.php": "PHP Arrow Functions",
                "https://www.php.net/manual/en/functions.first_class_callable_syntax.php": "PHP First Class Callable Syntax",
                # Classes and Objects
                "https://www.php.net/manual/en/language.oop5.php": "PHP Classes and Objects",
                "https://www.php.net/manual/en/language.oop5.basic.php": "PHP Classes Basics",
                "https://www.php.net/manual/en/language.oop5.properties.php": "PHP Properties",
                "https://www.php.net/manual/en/language.oop5.constants.php": "PHP Class Constants",
                "https://www.php.net/manual/en/language.oop5.autoload.php": "PHP Autoloading",
                "https://www.php.net/manual/en/language.oop5.decon.php": "PHP Constructors/Destructors",
                "https://www.php.net/manual/en/language.oop5.visibility.php": "PHP Visibility",
                "https://www.php.net/manual/en/language.oop5.inheritance.php": "PHP Inheritance",
                "https://www.php.net/manual/en/language.oop5.paamayim-nekudotayim.php": "PHP Scope Resolution",
                "https://www.php.net/manual/en/language.oop5.static.php": "PHP Static Keyword",
                "https://www.php.net/manual/en/language.oop5.abstract.php": "PHP Abstract Classes",
                "https://www.php.net/manual/en/language.oop5.interfaces.php": "PHP Interfaces",
                "https://www.php.net/manual/en/language.oop5.traits.php": "PHP Traits",
                "https://www.php.net/manual/en/language.oop5.anonymous.php": "PHP Anonymous Classes",
                "https://www.php.net/manual/en/language.oop5.overloading.php": "PHP Overloading",
                "https://www.php.net/manual/en/language.oop5.iterations.php": "PHP Object Iteration",
                "https://www.php.net/manual/en/language.oop5.magic.php": "PHP Magic Methods",
                "https://www.php.net/manual/en/language.oop5.final.php": "PHP Final Keyword",
                "https://www.php.net/manual/en/language.oop5.cloning.php": "PHP Object Cloning",
                "https://www.php.net/manual/en/language.oop5.object-comparison.php": "PHP Object Comparison",
                "https://www.php.net/manual/en/language.oop5.late-static-bindings.php": "PHP Late Static Bindings",
                "https://www.php.net/manual/en/language.oop5.serialization.php": "PHP Serialization",
                "https://www.php.net/manual/en/language.oop5.variance.php": "PHP Covariance and Contravariance",
                "https://www.php.net/manual/en/language.oop5.changelog.php": "PHP OOP Changelog",
                # Enumerations
                "https://www.php.net/manual/en/language.enumerations.php": "PHP Enumerations",
                "https://www.php.net/manual/en/language.enumerations.overview.php": "PHP Enums Overview",
                "https://www.php.net/manual/en/language.enumerations.basics.php": "PHP Enum Basics",
                "https://www.php.net/manual/en/language.enumerations.backed.php": "PHP Backed Enums",
                "https://www.php.net/manual/en/language.enumerations.methods.php": "PHP Enum Methods",
                "https://www.php.net/manual/en/language.enumerations.static-methods.php": "PHP Enum Static Methods",
                "https://www.php.net/manual/en/language.enumerations.constants.php": "PHP Enum Constants",
                "https://www.php.net/manual/en/language.enumerations.interfaces.php": "PHP Enum Interfaces",
                # Namespaces
                "https://www.php.net/manual/en/language.namespaces.php": "PHP Namespaces",
                "https://www.php.net/manual/en/language.namespaces.rationale.php": "PHP Namespaces Rationale",
                "https://www.php.net/manual/en/language.namespaces.definition.php": "PHP Defining Namespaces",
                "https://www.php.net/manual/en/language.namespaces.nested.php": "PHP Declaring Sub-namespaces",
                "https://www.php.net/manual/en/language.namespaces.definitionmultiple.php": "PHP Multiple Namespaces",
                "https://www.php.net/manual/en/language.namespaces.basics.php": "PHP Using Namespaces Basics",
                "https://www.php.net/manual/en/language.namespaces.dynamic.php": "PHP Dynamic Namespaces",
                "https://www.php.net/manual/en/language.namespaces.nsconstants.php": "PHP namespace Keyword",
                "https://www.php.net/manual/en/language.namespaces.importing.php": "PHP Using / Importing",
                "https://www.php.net/manual/en/language.namespaces.global.php": "PHP Global Space",
                "https://www.php.net/manual/en/language.namespaces.rules.php": "PHP Namespace Rules",
                "https://www.php.net/manual/en/language.namespaces.faq.php": "PHP Namespace FAQ",
                # Errors
                "https://www.php.net/manual/en/language.errors.php": "PHP Errors",
                "https://www.php.net/manual/en/language.errors.basics.php": "PHP Error Basics",
                "https://www.php.net/manual/en/language.errors.php7.php": "PHP Errors in PHP 7+",
                # Exceptions
                "https://www.php.net/manual/en/language.exceptions.php": "PHP Exceptions",
                "https://www.php.net/manual/en/language.exceptions.extending.php": "PHP Extending Exceptions",
                # Fibers
                "https://www.php.net/manual/en/language.fibers.php": "PHP Fibers",
                # Generators
                "https://www.php.net/manual/en/language.generators.php": "PHP Generators",
                "https://www.php.net/manual/en/language.generators.overview.php": "PHP Generators Overview",
                "https://www.php.net/manual/en/language.generators.syntax.php": "PHP Generator Syntax",
                "https://www.php.net/manual/en/language.generators.comparison.php": "PHP Generators vs Iterators",
                # Attributes
                "https://www.php.net/manual/en/language.attributes.php": "PHP Attributes",
                "https://www.php.net/manual/en/language.attributes.overview.php": "PHP Attributes Overview",
                "https://www.php.net/manual/en/language.attributes.syntax.php": "PHP Attribute Syntax",
                "https://www.php.net/manual/en/language.attributes.reflection.php": "PHP Reading Attributes with Reflection",
                "https://www.php.net/manual/en/language.attributes.classes.php": "PHP Declaring Attribute Classes",
                # References
                "https://www.php.net/manual/en/language.references.php": "PHP References Explained",
                "https://www.php.net/manual/en/language.references.whatare.php": "PHP What References Are",
                "https://www.php.net/manual/en/language.references.whatdo.php": "PHP What References Do",
                "https://www.php.net/manual/en/language.references.arent.php": "PHP What References Are Not",
                "https://www.php.net/manual/en/language.references.pass.php": "PHP Passing by Reference",
                "https://www.php.net/manual/en/language.references.return.php": "PHP Returning References",
                "https://www.php.net/manual/en/language.references.unset.php": "PHP Unsetting References",
                "https://www.php.net/manual/en/language.references.spot.php": "PHP Spotting References",
            },
        },
        "function-reference": {
            "pages": {
                # String functions
                "https://www.php.net/manual/en/ref.strings.php": "PHP String Functions",
                "https://www.php.net/manual/en/function.strlen.php": "PHP strlen",
                "https://www.php.net/manual/en/function.strpos.php": "PHP strpos",
                "https://www.php.net/manual/en/function.str-replace.php": "PHP str_replace",
                "https://www.php.net/manual/en/function.substr.php": "PHP substr",
                "https://www.php.net/manual/en/function.strtolower.php": "PHP strtolower",
                "https://www.php.net/manual/en/function.strtoupper.php": "PHP strtoupper",
                "https://www.php.net/manual/en/function.trim.php": "PHP trim",
                "https://www.php.net/manual/en/function.explode.php": "PHP explode",
                "https://www.php.net/manual/en/function.implode.php": "PHP implode",
                "https://www.php.net/manual/en/function.sprintf.php": "PHP sprintf",
                "https://www.php.net/manual/en/function.str-contains.php": "PHP str_contains",
                "https://www.php.net/manual/en/function.str-starts-with.php": "PHP str_starts_with",
                "https://www.php.net/manual/en/function.str-ends-with.php": "PHP str_ends_with",
                "https://www.php.net/manual/en/function.str-pad.php": "PHP str_pad",
                "https://www.php.net/manual/en/function.str-repeat.php": "PHP str_repeat",
                "https://www.php.net/manual/en/function.str-split.php": "PHP str_split",
                "https://www.php.net/manual/en/function.str-word-count.php": "PHP str_word_count",
                "https://www.php.net/manual/en/function.strcmp.php": "PHP strcmp",
                "https://www.php.net/manual/en/function.nl2br.php": "PHP nl2br",
                "https://www.php.net/manual/en/function.htmlspecialchars.php": "PHP htmlspecialchars",
                "https://www.php.net/manual/en/function.htmlentities.php": "PHP htmlentities",
                "https://www.php.net/manual/en/function.strip-tags.php": "PHP strip_tags",
                "https://www.php.net/manual/en/function.md5.php": "PHP md5",
                "https://www.php.net/manual/en/function.sha1.php": "PHP sha1",
                "https://www.php.net/manual/en/function.number-format.php": "PHP number_format",
                "https://www.php.net/manual/en/function.ucfirst.php": "PHP ucfirst",
                "https://www.php.net/manual/en/function.ucwords.php": "PHP ucwords",
                "https://www.php.net/manual/en/function.wordwrap.php": "PHP wordwrap",
                "https://www.php.net/manual/en/function.chunk-split.php": "PHP chunk_split",
                "https://www.php.net/manual/en/function.base64-encode.php": "PHP base64_encode",
                "https://www.php.net/manual/en/function.base64-decode.php": "PHP base64_decode",
                "https://www.php.net/manual/en/function.urlencode.php": "PHP urlencode",
                "https://www.php.net/manual/en/function.urldecode.php": "PHP urldecode",
                # Array functions
                "https://www.php.net/manual/en/ref.array.php": "PHP Array Functions",
                "https://www.php.net/manual/en/function.array-push.php": "PHP array_push",
                "https://www.php.net/manual/en/function.array-pop.php": "PHP array_pop",
                "https://www.php.net/manual/en/function.array-shift.php": "PHP array_shift",
                "https://www.php.net/manual/en/function.array-unshift.php": "PHP array_unshift",
                "https://www.php.net/manual/en/function.array-merge.php": "PHP array_merge",
                "https://www.php.net/manual/en/function.array-keys.php": "PHP array_keys",
                "https://www.php.net/manual/en/function.array-values.php": "PHP array_values",
                "https://www.php.net/manual/en/function.array-map.php": "PHP array_map",
                "https://www.php.net/manual/en/function.array-filter.php": "PHP array_filter",
                "https://www.php.net/manual/en/function.array-reduce.php": "PHP array_reduce",
                "https://www.php.net/manual/en/function.array-search.php": "PHP array_search",
                "https://www.php.net/manual/en/function.in-array.php": "PHP in_array",
                "https://www.php.net/manual/en/function.array-key-exists.php": "PHP array_key_exists",
                "https://www.php.net/manual/en/function.array-slice.php": "PHP array_slice",
                "https://www.php.net/manual/en/function.array-splice.php": "PHP array_splice",
                "https://www.php.net/manual/en/function.array-unique.php": "PHP array_unique",
                "https://www.php.net/manual/en/function.array-reverse.php": "PHP array_reverse",
                "https://www.php.net/manual/en/function.array-flip.php": "PHP array_flip",
                "https://www.php.net/manual/en/function.array-combine.php": "PHP array_combine",
                "https://www.php.net/manual/en/function.array-chunk.php": "PHP array_chunk",
                "https://www.php.net/manual/en/function.array-column.php": "PHP array_column",
                "https://www.php.net/manual/en/function.array-diff.php": "PHP array_diff",
                "https://www.php.net/manual/en/function.array-intersect.php": "PHP array_intersect",
                "https://www.php.net/manual/en/function.array-walk.php": "PHP array_walk",
                "https://www.php.net/manual/en/function.sort.php": "PHP sort",
                "https://www.php.net/manual/en/function.rsort.php": "PHP rsort",
                "https://www.php.net/manual/en/function.asort.php": "PHP asort",
                "https://www.php.net/manual/en/function.arsort.php": "PHP arsort",
                "https://www.php.net/manual/en/function.ksort.php": "PHP ksort",
                "https://www.php.net/manual/en/function.usort.php": "PHP usort",
                "https://www.php.net/manual/en/function.count.php": "PHP count",
                "https://www.php.net/manual/en/function.compact.php": "PHP compact",
                "https://www.php.net/manual/en/function.extract.php": "PHP extract",
                "https://www.php.net/manual/en/function.list.php": "PHP list",
                "https://www.php.net/manual/en/function.range.php": "PHP range",
                "https://www.php.net/manual/en/function.array-fill.php": "PHP array_fill",
                # Math functions
                "https://www.php.net/manual/en/ref.math.php": "PHP Math Functions",
                "https://www.php.net/manual/en/function.abs.php": "PHP abs",
                "https://www.php.net/manual/en/function.ceil.php": "PHP ceil",
                "https://www.php.net/manual/en/function.floor.php": "PHP floor",
                "https://www.php.net/manual/en/function.round.php": "PHP round",
                "https://www.php.net/manual/en/function.max.php": "PHP max",
                "https://www.php.net/manual/en/function.min.php": "PHP min",
                "https://www.php.net/manual/en/function.pow.php": "PHP pow",
                "https://www.php.net/manual/en/function.sqrt.php": "PHP sqrt",
                "https://www.php.net/manual/en/function.rand.php": "PHP rand",
                "https://www.php.net/manual/en/function.mt-rand.php": "PHP mt_rand",
                "https://www.php.net/manual/en/function.random-int.php": "PHP random_int",
                "https://www.php.net/manual/en/function.intdiv.php": "PHP intdiv",
                "https://www.php.net/manual/en/function.fmod.php": "PHP fmod",
                "https://www.php.net/manual/en/function.log.php": "PHP log",
                "https://www.php.net/manual/en/function.log10.php": "PHP log10",
                "https://www.php.net/manual/en/function.pi.php": "PHP pi",
                # Date/Time functions
                "https://www.php.net/manual/en/ref.datetime.php": "PHP Date/Time Functions",
                "https://www.php.net/manual/en/function.date.php": "PHP date",
                "https://www.php.net/manual/en/function.time.php": "PHP time",
                "https://www.php.net/manual/en/function.mktime.php": "PHP mktime",
                "https://www.php.net/manual/en/function.strtotime.php": "PHP strtotime",
                "https://www.php.net/manual/en/function.strftime.php": "PHP strftime",
                "https://www.php.net/manual/en/function.getdate.php": "PHP getdate",
                "https://www.php.net/manual/en/function.checkdate.php": "PHP checkdate",
                "https://www.php.net/manual/en/function.microtime.php": "PHP microtime",
                "https://www.php.net/manual/en/class.datetime.php": "PHP DateTime Class",
                "https://www.php.net/manual/en/class.datetimeimmutable.php": "PHP DateTimeImmutable",
                "https://www.php.net/manual/en/class.datetimeinterface.php": "PHP DateTimeInterface",
                "https://www.php.net/manual/en/class.dateinterval.php": "PHP DateInterval",
                "https://www.php.net/manual/en/class.dateperiod.php": "PHP DatePeriod",
                "https://www.php.net/manual/en/class.datetimezone.php": "PHP DateTimeZone",
                # File functions
                "https://www.php.net/manual/en/ref.filesystem.php": "PHP Filesystem Functions",
                "https://www.php.net/manual/en/function.file-get-contents.php": "PHP file_get_contents",
                "https://www.php.net/manual/en/function.file-put-contents.php": "PHP file_put_contents",
                "https://www.php.net/manual/en/function.fopen.php": "PHP fopen",
                "https://www.php.net/manual/en/function.fclose.php": "PHP fclose",
                "https://www.php.net/manual/en/function.fread.php": "PHP fread",
                "https://www.php.net/manual/en/function.fwrite.php": "PHP fwrite",
                "https://www.php.net/manual/en/function.fgets.php": "PHP fgets",
                "https://www.php.net/manual/en/function.file.php": "PHP file",
                "https://www.php.net/manual/en/function.file-exists.php": "PHP file_exists",
                "https://www.php.net/manual/en/function.is-file.php": "PHP is_file",
                "https://www.php.net/manual/en/function.is-dir.php": "PHP is_dir",
                "https://www.php.net/manual/en/function.mkdir.php": "PHP mkdir",
                "https://www.php.net/manual/en/function.rmdir.php": "PHP rmdir",
                "https://www.php.net/manual/en/function.unlink.php": "PHP unlink",
                "https://www.php.net/manual/en/function.copy.php": "PHP copy",
                "https://www.php.net/manual/en/function.rename.php": "PHP rename",
                "https://www.php.net/manual/en/function.glob.php": "PHP glob",
                "https://www.php.net/manual/en/function.scandir.php": "PHP scandir",
                "https://www.php.net/manual/en/function.realpath.php": "PHP realpath",
                "https://www.php.net/manual/en/function.pathinfo.php": "PHP pathinfo",
                "https://www.php.net/manual/en/function.basename.php": "PHP basename",
                "https://www.php.net/manual/en/function.dirname.php": "PHP dirname",
                "https://www.php.net/manual/en/function.tempnam.php": "PHP tempnam",
                "https://www.php.net/manual/en/function.tmpfile.php": "PHP tmpfile",
                "https://www.php.net/manual/en/function.chmod.php": "PHP chmod",
                "https://www.php.net/manual/en/function.filesize.php": "PHP filesize",
                "https://www.php.net/manual/en/function.filetype.php": "PHP filetype",
                "https://www.php.net/manual/en/function.filemtime.php": "PHP filemtime",
                # JSON functions
                "https://www.php.net/manual/en/ref.json.php": "PHP JSON Functions",
                "https://www.php.net/manual/en/function.json-encode.php": "PHP json_encode",
                "https://www.php.net/manual/en/function.json-decode.php": "PHP json_decode",
                "https://www.php.net/manual/en/function.json-last-error.php": "PHP json_last_error",
                "https://www.php.net/manual/en/function.json-last-error-msg.php": "PHP json_last_error_msg",
                "https://www.php.net/manual/en/class.jsonserializable.php": "PHP JsonSerializable",
                # Regex functions
                "https://www.php.net/manual/en/ref.pcre.php": "PHP PCRE Functions",
                "https://www.php.net/manual/en/function.preg-match.php": "PHP preg_match",
                "https://www.php.net/manual/en/function.preg-match-all.php": "PHP preg_match_all",
                "https://www.php.net/manual/en/function.preg-replace.php": "PHP preg_replace",
                "https://www.php.net/manual/en/function.preg-replace-callback.php": "PHP preg_replace_callback",
                "https://www.php.net/manual/en/function.preg-split.php": "PHP preg_split",
                "https://www.php.net/manual/en/function.preg-quote.php": "PHP preg_quote",
                "https://www.php.net/manual/en/reference.pcre.pattern.syntax.php": "PHP PCRE Pattern Syntax",
                "https://www.php.net/manual/en/reference.pcre.pattern.modifiers.php": "PHP PCRE Pattern Modifiers",
                # cURL functions
                "https://www.php.net/manual/en/ref.curl.php": "PHP cURL Functions",
                "https://www.php.net/manual/en/function.curl-init.php": "PHP curl_init",
                "https://www.php.net/manual/en/function.curl-setopt.php": "PHP curl_setopt",
                "https://www.php.net/manual/en/function.curl-exec.php": "PHP curl_exec",
                "https://www.php.net/manual/en/function.curl-close.php": "PHP curl_close",
                "https://www.php.net/manual/en/function.curl-error.php": "PHP curl_error",
                "https://www.php.net/manual/en/function.curl-getinfo.php": "PHP curl_getinfo",
                "https://www.php.net/manual/en/function.curl-setopt-array.php": "PHP curl_setopt_array",
                "https://www.php.net/manual/en/function.curl-multi-init.php": "PHP curl_multi_init",
                "https://www.php.net/manual/en/function.curl-multi-add-handle.php": "PHP curl_multi_add_handle",
                "https://www.php.net/manual/en/function.curl-multi-exec.php": "PHP curl_multi_exec",
                # PDO
                "https://www.php.net/manual/en/book.pdo.php": "PHP PDO",
                "https://www.php.net/manual/en/pdo.connections.php": "PHP PDO Connections",
                "https://www.php.net/manual/en/pdo.prepared-statements.php": "PHP PDO Prepared Statements",
                "https://www.php.net/manual/en/pdo.transactions.php": "PHP PDO Transactions",
                "https://www.php.net/manual/en/pdo.error-handling.php": "PHP PDO Errors",
                "https://www.php.net/manual/en/class.pdo.php": "PHP PDO Class",
                "https://www.php.net/manual/en/class.pdostatement.php": "PHP PDOStatement Class",
                "https://www.php.net/manual/en/class.pdoexception.php": "PHP PDOException Class",
                "https://www.php.net/manual/en/pdo.drivers.php": "PHP PDO Drivers",
                # MySQLi
                "https://www.php.net/manual/en/book.mysqli.php": "PHP MySQLi",
                "https://www.php.net/manual/en/mysqli.quickstart.php": "PHP MySQLi Quick Start",
                "https://www.php.net/manual/en/mysqli.quickstart.connections.php": "PHP MySQLi Connections",
                "https://www.php.net/manual/en/mysqli.quickstart.statements.php": "PHP MySQLi Statements",
                "https://www.php.net/manual/en/mysqli.quickstart.prepared-statements.php": "PHP MySQLi Prepared Statements",
                "https://www.php.net/manual/en/mysqli.quickstart.stored-procedures.php": "PHP MySQLi Stored Procedures",
                "https://www.php.net/manual/en/mysqli.quickstart.multiple-statement.php": "PHP MySQLi Multiple Statements",
                "https://www.php.net/manual/en/mysqli.quickstart.transactions.php": "PHP MySQLi Transactions",
                "https://www.php.net/manual/en/class.mysqli.php": "PHP mysqli Class",
                "https://www.php.net/manual/en/class.mysqli-stmt.php": "PHP mysqli_stmt Class",
                "https://www.php.net/manual/en/class.mysqli-result.php": "PHP mysqli_result Class",
                # Variable handling
                "https://www.php.net/manual/en/ref.var.php": "PHP Variable Handling Functions",
                "https://www.php.net/manual/en/function.isset.php": "PHP isset",
                "https://www.php.net/manual/en/function.empty.php": "PHP empty",
                "https://www.php.net/manual/en/function.unset.php": "PHP unset",
                "https://www.php.net/manual/en/function.var-dump.php": "PHP var_dump",
                "https://www.php.net/manual/en/function.print-r.php": "PHP print_r",
                "https://www.php.net/manual/en/function.var-export.php": "PHP var_export",
                "https://www.php.net/manual/en/function.gettype.php": "PHP gettype",
                "https://www.php.net/manual/en/function.settype.php": "PHP settype",
                "https://www.php.net/manual/en/function.is-array.php": "PHP is_array",
                "https://www.php.net/manual/en/function.is-string.php": "PHP is_string",
                "https://www.php.net/manual/en/function.is-int.php": "PHP is_int",
                "https://www.php.net/manual/en/function.is-float.php": "PHP is_float",
                "https://www.php.net/manual/en/function.is-bool.php": "PHP is_bool",
                "https://www.php.net/manual/en/function.is-null.php": "PHP is_null",
                "https://www.php.net/manual/en/function.is-numeric.php": "PHP is_numeric",
                "https://www.php.net/manual/en/function.is-object.php": "PHP is_object",
                "https://www.php.net/manual/en/function.intval.php": "PHP intval",
                "https://www.php.net/manual/en/function.floatval.php": "PHP floatval",
                "https://www.php.net/manual/en/function.strval.php": "PHP strval",
                "https://www.php.net/manual/en/function.boolval.php": "PHP boolval",
                "https://www.php.net/manual/en/function.serialize.php": "PHP serialize",
                "https://www.php.net/manual/en/function.unserialize.php": "PHP unserialize",
                # Directory functions
                "https://www.php.net/manual/en/ref.dir.php": "PHP Directory Functions",
                "https://www.php.net/manual/en/function.opendir.php": "PHP opendir",
                "https://www.php.net/manual/en/function.readdir.php": "PHP readdir",
                "https://www.php.net/manual/en/function.closedir.php": "PHP closedir",
                "https://www.php.net/manual/en/function.getcwd.php": "PHP getcwd",
                "https://www.php.net/manual/en/function.chdir.php": "PHP chdir",
                # SPL
                "https://www.php.net/manual/en/book.spl.php": "PHP SPL",
                "https://www.php.net/manual/en/class.arrayobject.php": "PHP ArrayObject",
                "https://www.php.net/manual/en/class.arrayiterator.php": "PHP ArrayIterator",
                "https://www.php.net/manual/en/class.splfileinfo.php": "PHP SplFileInfo",
                "https://www.php.net/manual/en/class.splfileobject.php": "PHP SplFileObject",
                "https://www.php.net/manual/en/class.directoryiterator.php": "PHP DirectoryIterator",
                "https://www.php.net/manual/en/class.recursivedirectoryiterator.php": "PHP RecursiveDirectoryIterator",
                "https://www.php.net/manual/en/class.recursiveiteratoriterator.php": "PHP RecursiveIteratorIterator",
                "https://www.php.net/manual/en/class.filteriterator.php": "PHP FilterIterator",
                "https://www.php.net/manual/en/class.regexiterator.php": "PHP RegexIterator",
                "https://www.php.net/manual/en/class.splstack.php": "PHP SplStack",
                "https://www.php.net/manual/en/class.splqueue.php": "PHP SplQueue",
                "https://www.php.net/manual/en/class.splheap.php": "PHP SplHeap",
                "https://www.php.net/manual/en/class.splpriorityqueue.php": "PHP SplPriorityQueue",
                "https://www.php.net/manual/en/class.splfixedarray.php": "PHP SplFixedArray",
                "https://www.php.net/manual/en/class.splobjectstorage.php": "PHP SplObjectStorage",
                "https://www.php.net/manual/en/class.splobserver.php": "PHP SplObserver",
                "https://www.php.net/manual/en/class.splsubject.php": "PHP SplSubject",
                # Multibyte String
                "https://www.php.net/manual/en/ref.mbstring.php": "PHP Multibyte String Functions",
                "https://www.php.net/manual/en/function.mb-strlen.php": "PHP mb_strlen",
                "https://www.php.net/manual/en/function.mb-strpos.php": "PHP mb_strpos",
                "https://www.php.net/manual/en/function.mb-substr.php": "PHP mb_substr",
                "https://www.php.net/manual/en/function.mb-strtolower.php": "PHP mb_strtolower",
                "https://www.php.net/manual/en/function.mb-strtoupper.php": "PHP mb_strtoupper",
                "https://www.php.net/manual/en/function.mb-detect-encoding.php": "PHP mb_detect_encoding",
                "https://www.php.net/manual/en/function.mb-convert-encoding.php": "PHP mb_convert_encoding",
                "https://www.php.net/manual/en/function.mb-internal-encoding.php": "PHP mb_internal_encoding",
                # Filter functions
                "https://www.php.net/manual/en/ref.filter.php": "PHP Filter Functions",
                "https://www.php.net/manual/en/function.filter-var.php": "PHP filter_var",
                "https://www.php.net/manual/en/function.filter-input.php": "PHP filter_input",
                "https://www.php.net/manual/en/function.filter-var-array.php": "PHP filter_var_array",
                "https://www.php.net/manual/en/filter.filters.sanitize.php": "PHP Sanitize Filters",
                "https://www.php.net/manual/en/filter.filters.validate.php": "PHP Validate Filters",
                # Reflection
                "https://www.php.net/manual/en/book.reflection.php": "PHP Reflection",
                "https://www.php.net/manual/en/class.reflectionclass.php": "PHP ReflectionClass",
                "https://www.php.net/manual/en/class.reflectionmethod.php": "PHP ReflectionMethod",
                "https://www.php.net/manual/en/class.reflectionfunction.php": "PHP ReflectionFunction",
                "https://www.php.net/manual/en/class.reflectionproperty.php": "PHP ReflectionProperty",
                "https://www.php.net/manual/en/class.reflectionparameter.php": "PHP ReflectionParameter",
                "https://www.php.net/manual/en/class.reflectiontype.php": "PHP ReflectionType",
                "https://www.php.net/manual/en/class.reflectionattribute.php": "PHP ReflectionAttribute",
                "https://www.php.net/manual/en/class.reflectionenum.php": "PHP ReflectionEnum",
                # XML
                "https://www.php.net/manual/en/book.simplexml.php": "PHP SimpleXML",
                "https://www.php.net/manual/en/function.simplexml-load-string.php": "PHP simplexml_load_string",
                "https://www.php.net/manual/en/function.simplexml-load-file.php": "PHP simplexml_load_file",
                "https://www.php.net/manual/en/book.dom.php": "PHP DOM",
                "https://www.php.net/manual/en/class.domdocument.php": "PHP DOMDocument",
                "https://www.php.net/manual/en/class.domelement.php": "PHP DOMElement",
                "https://www.php.net/manual/en/class.domnode.php": "PHP DOMNode",
                "https://www.php.net/manual/en/class.domxpath.php": "PHP DOMXPath",
                # Streams
                "https://www.php.net/manual/en/book.stream.php": "PHP Streams",
                "https://www.php.net/manual/en/function.stream-context-create.php": "PHP stream_context_create",
                "https://www.php.net/manual/en/function.stream-get-contents.php": "PHP stream_get_contents",
                "https://www.php.net/manual/en/function.stream-socket-client.php": "PHP stream_socket_client",
                "https://www.php.net/manual/en/function.stream-socket-server.php": "PHP stream_socket_server",
                "https://www.php.net/manual/en/wrappers.php.php": "PHP I/O Streams",
                # Misc functions
                "https://www.php.net/manual/en/function.sleep.php": "PHP sleep",
                "https://www.php.net/manual/en/function.usleep.php": "PHP usleep",
                "https://www.php.net/manual/en/function.exit.php": "PHP exit",
                "https://www.php.net/manual/en/function.die.php": "PHP die",
                "https://www.php.net/manual/en/function.eval.php": "PHP eval",
                "https://www.php.net/manual/en/function.define.php": "PHP define",
                "https://www.php.net/manual/en/function.defined.php": "PHP defined",
                "https://www.php.net/manual/en/function.constant.php": "PHP constant",
                "https://www.php.net/manual/en/function.get-class.php": "PHP get_class",
                "https://www.php.net/manual/en/function.get-object-vars.php": "PHP get_object_vars",
                "https://www.php.net/manual/en/function.class-exists.php": "PHP class_exists",
                "https://www.php.net/manual/en/function.method-exists.php": "PHP method_exists",
                "https://www.php.net/manual/en/function.property-exists.php": "PHP property_exists",
                "https://www.php.net/manual/en/function.instanceof.php": "PHP instanceof",
                "https://www.php.net/manual/en/function.call-user-func.php": "PHP call_user_func",
                "https://www.php.net/manual/en/function.call-user-func-array.php": "PHP call_user_func_array",
                "https://www.php.net/manual/en/function.func-get-args.php": "PHP func_get_args",
                "https://www.php.net/manual/en/function.func-num-args.php": "PHP func_num_args",
                "https://www.php.net/manual/en/function.function-exists.php": "PHP function_exists",
            },
        },
        "security": {
            "pages": {
                "https://www.php.net/manual/en/security.php": "PHP Security",
                "https://www.php.net/manual/en/security.intro.php": "PHP Security Introduction",
                "https://www.php.net/manual/en/security.general.php": "PHP General Considerations",
                "https://www.php.net/manual/en/security.cgi-bin.php": "PHP CGI Binary Security",
                "https://www.php.net/manual/en/security.apache.php": "PHP Apache Module Security",
                "https://www.php.net/manual/en/security.sessions.php": "PHP Session Security",
                "https://www.php.net/manual/en/security.filesystem.php": "PHP Filesystem Security",
                "https://www.php.net/manual/en/security.database.php": "PHP Database Security",
                "https://www.php.net/manual/en/security.database.sql-injection.php": "PHP SQL Injection",
                "https://www.php.net/manual/en/security.errors.php": "PHP Error Reporting Security",
                "https://www.php.net/manual/en/security.variables.php": "PHP User Submitted Data",
                "https://www.php.net/manual/en/security.hiding.php": "PHP Hiding PHP",
                "https://www.php.net/manual/en/security.current.php": "PHP Keeping Current",
                # Password hashing
                "https://www.php.net/manual/en/ref.password.php": "PHP Password Hashing Functions",
                "https://www.php.net/manual/en/function.password-hash.php": "PHP password_hash",
                "https://www.php.net/manual/en/function.password-verify.php": "PHP password_verify",
                "https://www.php.net/manual/en/function.password-needs-rehash.php": "PHP password_needs_rehash",
                # OpenSSL
                "https://www.php.net/manual/en/book.openssl.php": "PHP OpenSSL",
                "https://www.php.net/manual/en/function.openssl-encrypt.php": "PHP openssl_encrypt",
                "https://www.php.net/manual/en/function.openssl-decrypt.php": "PHP openssl_decrypt",
                # Hash
                "https://www.php.net/manual/en/function.hash.php": "PHP hash",
                "https://www.php.net/manual/en/function.hash-hmac.php": "PHP hash_hmac",
                "https://www.php.net/manual/en/function.hash-algos.php": "PHP hash_algos",
            },
        },
        "features": {
            "pages": {
                "https://www.php.net/manual/en/features.php": "PHP Features",
                "https://www.php.net/manual/en/features.http-auth.php": "PHP HTTP Authentication",
                "https://www.php.net/manual/en/features.cookies.php": "PHP Cookies",
                "https://www.php.net/manual/en/features.sessions.php": "PHP Sessions",
                "https://www.php.net/manual/en/features.file-upload.php": "PHP File Uploads",
                "https://www.php.net/manual/en/features.file-upload.post-method.php": "PHP POST Method Uploads",
                "https://www.php.net/manual/en/features.file-upload.errors.php": "PHP Upload Error Messages",
                "https://www.php.net/manual/en/features.file-upload.common-pitfalls.php": "PHP Upload Common Pitfalls",
                "https://www.php.net/manual/en/features.file-upload.multiple.php": "PHP Multiple File Uploads",
                "https://www.php.net/manual/en/features.remote-files.php": "PHP Remote Files",
                "https://www.php.net/manual/en/features.connection-handling.php": "PHP Connection Handling",
                "https://www.php.net/manual/en/features.persistent-connections.php": "PHP Persistent Connections",
                "https://www.php.net/manual/en/features.commandline.php": "PHP Command Line",
                "https://www.php.net/manual/en/features.commandline.usage.php": "PHP CLI Usage",
                "https://www.php.net/manual/en/features.commandline.options.php": "PHP CLI Options",
                "https://www.php.net/manual/en/features.commandline.io-streams.php": "PHP CLI I/O Streams",
                "https://www.php.net/manual/en/features.commandline.interactive.php": "PHP CLI Interactive Mode",
                "https://www.php.net/manual/en/features.commandline.webserver.php": "PHP Built-in Web Server",
                "https://www.php.net/manual/en/features.gc.php": "PHP Garbage Collection",
                "https://www.php.net/manual/en/features.gc.refcounting-basics.php": "PHP Reference Counting Basics",
                "https://www.php.net/manual/en/features.gc.collecting-cycles.php": "PHP Collecting Cycles",
                "https://www.php.net/manual/en/features.gc.performance-considerations.php": "PHP GC Performance",
                # Session reference
                "https://www.php.net/manual/en/ref.session.php": "PHP Session Functions",
                "https://www.php.net/manual/en/function.session-start.php": "PHP session_start",
                "https://www.php.net/manual/en/function.session-destroy.php": "PHP session_destroy",
                "https://www.php.net/manual/en/function.session-regenerate-id.php": "PHP session_regenerate_id",
                "https://www.php.net/manual/en/function.session-id.php": "PHP session_id",
                "https://www.php.net/manual/en/function.session-name.php": "PHP session_name",
                # Error handling
                "https://www.php.net/manual/en/ref.errorfunc.php": "PHP Error Functions",
                "https://www.php.net/manual/en/function.error-reporting.php": "PHP error_reporting",
                "https://www.php.net/manual/en/function.set-error-handler.php": "PHP set_error_handler",
                "https://www.php.net/manual/en/function.set-exception-handler.php": "PHP set_exception_handler",
                "https://www.php.net/manual/en/function.trigger-error.php": "PHP trigger_error",
                # Output buffering
                "https://www.php.net/manual/en/ref.outcontrol.php": "PHP Output Control Functions",
                "https://www.php.net/manual/en/function.ob-start.php": "PHP ob_start",
                "https://www.php.net/manual/en/function.ob-get-contents.php": "PHP ob_get_contents",
                "https://www.php.net/manual/en/function.ob-end-clean.php": "PHP ob_end_clean",
                "https://www.php.net/manual/en/function.ob-flush.php": "PHP ob_flush",
                "https://www.php.net/manual/en/function.header.php": "PHP header",
                "https://www.php.net/manual/en/function.headers-sent.php": "PHP headers_sent",
                "https://www.php.net/manual/en/function.setcookie.php": "PHP setcookie",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"php-{source_key}" if source_key else "php"
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
            for suffix in [' - Manual', ' - PHP', ' - Manual - PHP',
                           ' | PHP', ' - PHP Manual']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            # Also strip common prefixes
            for prefix in ['PHP: ']:
                if title.startswith(prefix):
                    title = title[len(prefix):].strip()
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
                        "category": f"php-{source_key}",
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
            self.log.info(f"=== Scraping php/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    PHPScraper(base, source_key).run()
