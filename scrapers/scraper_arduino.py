#!/usr/bin/env python3
"""Arduino documentation scraper.

Covers:
  - Language reference (structure, variables, functions)
  - Libraries (Servo, Wire, SPI, Ethernet, WiFi, SD, etc.)
  - Hardware (boards, shields, sensors)
  - Tutorials (built-in examples, project hub)
  - Learn (electronics, programming)

Rate limit: 1.5s between fetches
~300 hardcoded URLs
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ArduinoScraper(BaseScraper):
    """Scrape Arduino documentation and reference pages."""

    SOURCES = {
        "language-reference": {
            "pages": {
                # Structure
                "https://docs.arduino.cc/language-reference/": "Arduino Language Reference",
                "https://www.arduino.cc/reference/en/": "Arduino Reference Home",
                # Control structures
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/if/": "if statement",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/else/": "else statement",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/for/": "for loop",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/while/": "while loop",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/doWhile/": "do-while loop",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/switchCase/": "switch-case",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/break/": "break",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/continue/": "continue",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/return/": "return",
                "https://docs.arduino.cc/language-reference/en/structure/control-structure/goto/": "goto",
                # Sketch structure
                "https://docs.arduino.cc/language-reference/en/structure/sketch/setup/": "setup()",
                "https://docs.arduino.cc/language-reference/en/structure/sketch/loop/": "loop()",
                # Arithmetic operators
                "https://docs.arduino.cc/language-reference/en/structure/arithmetic-operators/addition/": "Addition",
                "https://docs.arduino.cc/language-reference/en/structure/arithmetic-operators/subtraction/": "Subtraction",
                "https://docs.arduino.cc/language-reference/en/structure/arithmetic-operators/multiplication/": "Multiplication",
                "https://docs.arduino.cc/language-reference/en/structure/arithmetic-operators/division/": "Division",
                "https://docs.arduino.cc/language-reference/en/structure/arithmetic-operators/remainder/": "Remainder/Modulo",
                "https://docs.arduino.cc/language-reference/en/structure/arithmetic-operators/assignment/": "Assignment",
                # Comparison operators
                "https://docs.arduino.cc/language-reference/en/structure/comparison-operators/equalto/": "Equal to",
                "https://docs.arduino.cc/language-reference/en/structure/comparison-operators/notequalto/": "Not equal to",
                "https://docs.arduino.cc/language-reference/en/structure/comparison-operators/lessthan/": "Less than",
                "https://docs.arduino.cc/language-reference/en/structure/comparison-operators/greaterthan/": "Greater than",
                # Boolean operators
                "https://docs.arduino.cc/language-reference/en/structure/boolean-operators/logicaland/": "Logical AND",
                "https://docs.arduino.cc/language-reference/en/structure/boolean-operators/logicalor/": "Logical OR",
                "https://docs.arduino.cc/language-reference/en/structure/boolean-operators/logicalnot/": "Logical NOT",
                # Bitwise operators
                "https://docs.arduino.cc/language-reference/en/structure/bitwise-operators/bitwiseand/": "Bitwise AND",
                "https://docs.arduino.cc/language-reference/en/structure/bitwise-operators/bitwiseor/": "Bitwise OR",
                "https://docs.arduino.cc/language-reference/en/structure/bitwise-operators/bitwisexor/": "Bitwise XOR",
                "https://docs.arduino.cc/language-reference/en/structure/bitwise-operators/bitwisenot/": "Bitwise NOT",
                "https://docs.arduino.cc/language-reference/en/structure/bitwise-operators/bitshiftleft/": "Bitshift Left",
                "https://docs.arduino.cc/language-reference/en/structure/bitwise-operators/bitshiftright/": "Bitshift Right",
                # Data types
                "https://docs.arduino.cc/language-reference/en/variables/data-types/void/": "void",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/bool/": "bool",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/char/": "char",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/byte/": "byte",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/int/": "int",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/unsignedint/": "unsigned int",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/long/": "long",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/unsignedlong/": "unsigned long",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/float/": "float",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/double/": "double",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/short/": "short",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/size_t/": "size_t",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/word/": "word",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/array/": "array",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/string/": "String",
                "https://docs.arduino.cc/language-reference/en/variables/data-types/stringObject/": "String Object",
                # Variable scope
                "https://docs.arduino.cc/language-reference/en/variables/variable-scope-qualifiers/const/": "const",
                "https://docs.arduino.cc/language-reference/en/variables/variable-scope-qualifiers/scope/": "scope",
                "https://docs.arduino.cc/language-reference/en/variables/variable-scope-qualifiers/static/": "static",
                "https://docs.arduino.cc/language-reference/en/variables/variable-scope-qualifiers/volatile/": "volatile",
                # Constants
                "https://docs.arduino.cc/language-reference/en/variables/constants/constants/": "Constants",
                "https://docs.arduino.cc/language-reference/en/variables/constants/highlow/": "HIGH/LOW",
                "https://docs.arduino.cc/language-reference/en/variables/constants/inputoutputpullup/": "INPUT/OUTPUT/INPUT_PULLUP",
                "https://docs.arduino.cc/language-reference/en/variables/constants/ledbuiltin/": "LED_BUILTIN",
                "https://docs.arduino.cc/language-reference/en/variables/constants/truefalse/": "true/false",
                # Conversion functions
                "https://docs.arduino.cc/language-reference/en/variables/conversion/bytecast/": "byte()",
                "https://docs.arduino.cc/language-reference/en/variables/conversion/charcast/": "char()",
                "https://docs.arduino.cc/language-reference/en/variables/conversion/floatcast/": "float()",
                "https://docs.arduino.cc/language-reference/en/variables/conversion/intcast/": "int()",
                "https://docs.arduino.cc/language-reference/en/variables/conversion/longcast/": "long()",
                "https://docs.arduino.cc/language-reference/en/variables/conversion/wordcast/": "word()",
                # Digital I/O
                "https://docs.arduino.cc/language-reference/en/functions/digital-io/digitalRead/": "digitalRead()",
                "https://docs.arduino.cc/language-reference/en/functions/digital-io/digitalWrite/": "digitalWrite()",
                "https://docs.arduino.cc/language-reference/en/functions/digital-io/pinMode/": "pinMode()",
                # Analog I/O
                "https://docs.arduino.cc/language-reference/en/functions/analog-io/analogRead/": "analogRead()",
                "https://docs.arduino.cc/language-reference/en/functions/analog-io/analogReference/": "analogReference()",
                "https://docs.arduino.cc/language-reference/en/functions/analog-io/analogWrite/": "analogWrite()",
                # Time
                "https://docs.arduino.cc/language-reference/en/functions/time/delay/": "delay()",
                "https://docs.arduino.cc/language-reference/en/functions/time/delayMicroseconds/": "delayMicroseconds()",
                "https://docs.arduino.cc/language-reference/en/functions/time/micros/": "micros()",
                "https://docs.arduino.cc/language-reference/en/functions/time/millis/": "millis()",
                # Math
                "https://docs.arduino.cc/language-reference/en/functions/math/abs/": "abs()",
                "https://docs.arduino.cc/language-reference/en/functions/math/constrain/": "constrain()",
                "https://docs.arduino.cc/language-reference/en/functions/math/map/": "map()",
                "https://docs.arduino.cc/language-reference/en/functions/math/max/": "max()",
                "https://docs.arduino.cc/language-reference/en/functions/math/min/": "min()",
                "https://docs.arduino.cc/language-reference/en/functions/math/pow/": "pow()",
                "https://docs.arduino.cc/language-reference/en/functions/math/sq/": "sq()",
                "https://docs.arduino.cc/language-reference/en/functions/math/sqrt/": "sqrt()",
                # Trigonometry
                "https://docs.arduino.cc/language-reference/en/functions/trigonometry/cos/": "cos()",
                "https://docs.arduino.cc/language-reference/en/functions/trigonometry/sin/": "sin()",
                "https://docs.arduino.cc/language-reference/en/functions/trigonometry/tan/": "tan()",
                # Random
                "https://docs.arduino.cc/language-reference/en/functions/random-numbers/random/": "random()",
                "https://docs.arduino.cc/language-reference/en/functions/random-numbers/randomSeed/": "randomSeed()",
                # Bits and bytes
                "https://docs.arduino.cc/language-reference/en/functions/bits-and-bytes/bit/": "bit()",
                "https://docs.arduino.cc/language-reference/en/functions/bits-and-bytes/bitClear/": "bitClear()",
                "https://docs.arduino.cc/language-reference/en/functions/bits-and-bytes/bitRead/": "bitRead()",
                "https://docs.arduino.cc/language-reference/en/functions/bits-and-bytes/bitSet/": "bitSet()",
                "https://docs.arduino.cc/language-reference/en/functions/bits-and-bytes/bitWrite/": "bitWrite()",
                "https://docs.arduino.cc/language-reference/en/functions/bits-and-bytes/highByte/": "highByte()",
                "https://docs.arduino.cc/language-reference/en/functions/bits-and-bytes/lowByte/": "lowByte()",
                # Interrupts
                "https://docs.arduino.cc/language-reference/en/functions/external-interrupts/attachInterrupt/": "attachInterrupt()",
                "https://docs.arduino.cc/language-reference/en/functions/external-interrupts/detachInterrupt/": "detachInterrupt()",
                "https://docs.arduino.cc/language-reference/en/functions/interrupts/interrupts/": "interrupts()",
                "https://docs.arduino.cc/language-reference/en/functions/interrupts/noInterrupts/": "noInterrupts()",
                # Serial
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/": "Serial",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/available/": "Serial.available()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/begin/": "Serial.begin()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/end/": "Serial.end()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/print/": "Serial.print()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/println/": "Serial.println()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/read/": "Serial.read()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/write/": "Serial.write()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/parseFloat/": "Serial.parseFloat()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/parseInt/": "Serial.parseInt()",
                "https://docs.arduino.cc/language-reference/en/functions/communication/serial/readString/": "Serial.readString()",
                # Characters
                "https://docs.arduino.cc/language-reference/en/functions/characters/isAlpha/": "isAlpha()",
                "https://docs.arduino.cc/language-reference/en/functions/characters/isAlphaNumeric/": "isAlphaNumeric()",
                "https://docs.arduino.cc/language-reference/en/functions/characters/isDigit/": "isDigit()",
                "https://docs.arduino.cc/language-reference/en/functions/characters/isLowerCase/": "isLowerCase()",
                "https://docs.arduino.cc/language-reference/en/functions/characters/isUpperCase/": "isUpperCase()",
            },
        },
        "libraries": {
            "pages": {
                # Servo
                "https://docs.arduino.cc/libraries/servo/": "Servo Library",
                # Wire (I2C)
                "https://docs.arduino.cc/libraries/wire/": "Wire (I2C) Library",
                # SPI
                "https://docs.arduino.cc/libraries/spi/": "SPI Library",
                # Ethernet
                "https://docs.arduino.cc/libraries/ethernet/": "Ethernet Library",
                # WiFi
                "https://docs.arduino.cc/libraries/wifi/": "WiFi Library",
                "https://docs.arduino.cc/libraries/wifinina/": "WiFiNINA Library",
                "https://docs.arduino.cc/libraries/wifis3/": "WiFiS3 Library",
                # SD
                "https://docs.arduino.cc/libraries/sd/": "SD Library",
                # Stepper
                "https://docs.arduino.cc/libraries/stepper/": "Stepper Library",
                # LiquidCrystal
                "https://docs.arduino.cc/libraries/liquidcrystal/": "LiquidCrystal Library",
                # SoftwareSerial
                "https://docs.arduino.cc/libraries/softwareserial/": "SoftwareSerial Library",
                # EEPROM
                "https://docs.arduino.cc/libraries/eeprom/": "EEPROM Library",
                # Keyboard
                "https://docs.arduino.cc/libraries/keyboard/": "Keyboard Library",
                # Mouse
                "https://docs.arduino.cc/libraries/mouse/": "Mouse Library",
                # ArduinoBLE
                "https://docs.arduino.cc/libraries/arduinoble/": "ArduinoBLE Library",
                # ArduinoHttpClient
                "https://docs.arduino.cc/libraries/arduinohttpclient/": "ArduinoHttpClient Library",
                # ArduinoJson
                "https://docs.arduino.cc/libraries/arduinojson/": "ArduinoJson Library",
                # ArduinoMqttClient
                "https://docs.arduino.cc/libraries/arduinomqttclient/": "ArduinoMqttClient Library",
                # ArduinoOTA
                "https://docs.arduino.cc/libraries/arduinoota/": "ArduinoOTA Library",
                # Audio
                "https://docs.arduino.cc/libraries/audiotoolbox/": "AudioToolbox Library",
                # Firmata
                "https://docs.arduino.cc/libraries/firmata/": "Firmata Library",
                # TFT
                "https://docs.arduino.cc/libraries/tft/": "TFT Library",
            },
        },
        "hardware": {
            "pages": {
                # Boards
                "https://docs.arduino.cc/hardware/uno-rev3/": "Arduino Uno Rev3",
                "https://docs.arduino.cc/hardware/uno-r4-wifi/": "Arduino Uno R4 WiFi",
                "https://docs.arduino.cc/hardware/uno-r4-minima/": "Arduino Uno R4 Minima",
                "https://docs.arduino.cc/hardware/mega-2560/": "Arduino Mega 2560",
                "https://docs.arduino.cc/hardware/nano/": "Arduino Nano",
                "https://docs.arduino.cc/hardware/nano-every/": "Arduino Nano Every",
                "https://docs.arduino.cc/hardware/nano-33-ble/": "Arduino Nano 33 BLE",
                "https://docs.arduino.cc/hardware/nano-33-ble-sense/": "Arduino Nano 33 BLE Sense",
                "https://docs.arduino.cc/hardware/nano-33-ble-sense-rev2/": "Arduino Nano 33 BLE Sense Rev2",
                "https://docs.arduino.cc/hardware/nano-33-iot/": "Arduino Nano 33 IoT",
                "https://docs.arduino.cc/hardware/nano-esp32/": "Arduino Nano ESP32",
                "https://docs.arduino.cc/hardware/nano-rp2040-connect/": "Arduino Nano RP2040 Connect",
                "https://docs.arduino.cc/hardware/leonardo/": "Arduino Leonardo",
                "https://docs.arduino.cc/hardware/due/": "Arduino Due",
                "https://docs.arduino.cc/hardware/micro/": "Arduino Micro",
                "https://docs.arduino.cc/hardware/mkr-wifi-1010/": "Arduino MKR WiFi 1010",
                "https://docs.arduino.cc/hardware/mkr-zero/": "Arduino MKR Zero",
                "https://docs.arduino.cc/hardware/portenta-h7/": "Arduino Portenta H7",
                "https://docs.arduino.cc/hardware/giga-r1-wifi/": "Arduino GIGA R1 WiFi",
                "https://docs.arduino.cc/hardware/nicla-sense-me/": "Arduino Nicla Sense ME",
                "https://docs.arduino.cc/hardware/opta/": "Arduino Opta",
            },
        },
        "tutorials": {
            "pages": {
                # Built-in examples
                "https://docs.arduino.cc/built-in-examples/": "Arduino Built-In Examples",
                # Basics
                "https://docs.arduino.cc/built-in-examples/basics/AnalogReadSerial/": "AnalogReadSerial Example",
                "https://docs.arduino.cc/built-in-examples/basics/BareMinimum/": "BareMinimum Example",
                "https://docs.arduino.cc/built-in-examples/basics/Blink/": "Blink Example",
                "https://docs.arduino.cc/built-in-examples/basics/DigitalReadSerial/": "DigitalReadSerial Example",
                "https://docs.arduino.cc/built-in-examples/basics/Fade/": "Fade Example",
                "https://docs.arduino.cc/built-in-examples/basics/ReadAnalogVoltage/": "ReadAnalogVoltage Example",
                # Digital
                "https://docs.arduino.cc/built-in-examples/digital/BlinkWithoutDelay/": "BlinkWithoutDelay Example",
                "https://docs.arduino.cc/built-in-examples/digital/Button/": "Button Example",
                "https://docs.arduino.cc/built-in-examples/digital/Debounce/": "Debounce Example",
                "https://docs.arduino.cc/built-in-examples/digital/DigitalInputPullup/": "DigitalInputPullup Example",
                "https://docs.arduino.cc/built-in-examples/digital/StateChangeDetection/": "StateChangeDetection Example",
                # Analog
                "https://docs.arduino.cc/built-in-examples/analog/AnalogInOutSerial/": "AnalogInOutSerial Example",
                "https://docs.arduino.cc/built-in-examples/analog/AnalogInput/": "AnalogInput Example",
                "https://docs.arduino.cc/built-in-examples/analog/AnalogWriteMega/": "AnalogWriteMega Example",
                "https://docs.arduino.cc/built-in-examples/analog/Calibration/": "Calibration Example",
                "https://docs.arduino.cc/built-in-examples/analog/Fading/": "Fading Example",
                "https://docs.arduino.cc/built-in-examples/analog/Smoothing/": "Smoothing Example",
                # Communication
                "https://docs.arduino.cc/built-in-examples/communication/ASCIITable/": "ASCIITable Example",
                "https://docs.arduino.cc/built-in-examples/communication/Dimmer/": "Dimmer Example",
                "https://docs.arduino.cc/built-in-examples/communication/Graph/": "Graph Example",
                "https://docs.arduino.cc/built-in-examples/communication/SerialCallResponse/": "SerialCallResponse Example",
                "https://docs.arduino.cc/built-in-examples/communication/SerialEvent/": "SerialEvent Example",
                # Control
                "https://docs.arduino.cc/built-in-examples/control/Arrays/": "Arrays Example",
                "https://docs.arduino.cc/built-in-examples/control/ForLoopIteration/": "ForLoopIteration Example",
                "https://docs.arduino.cc/built-in-examples/control/IfStatementConditional/": "IfStatementConditional Example",
                "https://docs.arduino.cc/built-in-examples/control/WhileStatementConditional/": "WhileStatementConditional Example",
                "https://docs.arduino.cc/built-in-examples/control/switchCase/": "SwitchCase Example",
                # Strings
                "https://docs.arduino.cc/built-in-examples/strings/CharacterAnalysis/": "CharacterAnalysis Example",
                "https://docs.arduino.cc/built-in-examples/strings/StringAdditionOperator/": "StringAdditionOperator Example",
                "https://docs.arduino.cc/built-in-examples/strings/StringComparisonOperators/": "StringComparisonOperators Example",
                "https://docs.arduino.cc/built-in-examples/strings/StringLength/": "StringLength Example",
                "https://docs.arduino.cc/built-in-examples/strings/StringSubstring/": "StringSubstring Example",
            },
        },
        "learn": {
            "pages": {
                # Getting started
                "https://docs.arduino.cc/learn/starting-guide/getting-started-arduino/": "Getting Started with Arduino",
                "https://docs.arduino.cc/learn/starting-guide/cores/": "Arduino Cores",
                # Electronics
                "https://docs.arduino.cc/learn/electronics/lcd-displays/": "LCD Displays",
                "https://docs.arduino.cc/learn/electronics/servo-motors/": "Servo Motors",
                "https://docs.arduino.cc/learn/electronics/stepper-motors/": "Stepper Motors",
                "https://docs.arduino.cc/learn/electronics/dc-motors/": "DC Motors",
                "https://docs.arduino.cc/learn/electronics/potentiometer-basics/": "Potentiometer Basics",
                "https://docs.arduino.cc/learn/electronics/relay-module/": "Relay Module",
                # Communication
                "https://docs.arduino.cc/learn/communication/wire/": "I2C Communication",
                "https://docs.arduino.cc/learn/communication/spi/": "SPI Communication",
                # Programming
                "https://docs.arduino.cc/learn/programming/eeprom-guide/": "EEPROM Guide",
                "https://docs.arduino.cc/learn/programming/memory-guide/": "Memory Guide",
                "https://docs.arduino.cc/learn/programming/bit-math/": "Bit Math Tutorial",
                "https://docs.arduino.cc/learn/programming/ota-programming/": "OTA Programming",
                # Contributions
                "https://docs.arduino.cc/learn/contributions/arduino-creating-library-guide/": "Creating a Library",
                "https://docs.arduino.cc/learn/contributions/arduino-writing-style-guide/": "Writing Style Guide",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"arduino-{source_key}" if source_key else "arduino"
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
            for suffix in [' | Arduino Documentation', ' - Arduino Docs',
                           ' | Arduino', ' - Arduino Reference']:
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
                        "category": f"arduino-{source_key}",
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
            self.log.info(f"=== Scraping arduino/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ArduinoScraper(base, source_key).run()
