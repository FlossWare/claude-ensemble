#!/usr/bin/env python3
"""Electronics Tutorials scraper.

Covers:
  - Basic Electronics (resistors, capacitors, inductors, laws)
  - Semiconductor Devices (diodes, transistors, thyristors)
  - Operational Amplifiers (inverting, non-inverting, filters)
  - Digital Logic (gates, flip-flops, counters, registers)
  - Filters (low-pass, high-pass, band-pass, Butterworth, Chebyshev)
  - Power Electronics (rectifiers, regulators, converters)
  - Oscillators (RC, LC, crystal, 555 timer)
  - Communication (AM, FM, PLL, mixers)
  - Sensors (temperature, light, pressure, Hall effect)
  - Motors (DC, stepper, servo, brushless)
  - Waveforms (sine, square, triangle, sawtooth)
  - Binary Numbers (binary, octal, hex, BCD)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class ElectronicsTutorialsScraper(BaseScraper):
    """Scrape Electronics Tutorials reference pages."""

    SOURCES = {
        "basic-electronics": {
            "pages": {
                # Resistors
                "https://www.electronics-tutorials.ws/resistor/res_1.html": "Resistors - Resistor Types",
                "https://www.electronics-tutorials.ws/resistor/res_2.html": "Resistors in Series",
                "https://www.electronics-tutorials.ws/resistor/res_3.html": "Resistors in Parallel",
                "https://www.electronics-tutorials.ws/resistor/res_4.html": "Resistor Color Code",
                "https://www.electronics-tutorials.ws/resistor/res_5.html": "Potentiometers",
                "https://www.electronics-tutorials.ws/resistor/res_6.html": "Varistors",
                "https://www.electronics-tutorials.ws/resistor/res_7.html": "Thermistors",
                "https://www.electronics-tutorials.ws/resistor/res_8.html": "Light Dependent Resistor (LDR)",
                # Capacitors
                "https://www.electronics-tutorials.ws/capacitor/cap_1.html": "Introduction to Capacitors",
                "https://www.electronics-tutorials.ws/capacitor/cap_2.html": "Capacitance and Charge",
                "https://www.electronics-tutorials.ws/capacitor/cap_3.html": "Capacitor Types",
                "https://www.electronics-tutorials.ws/capacitor/cap_4.html": "Capacitors in Series",
                "https://www.electronics-tutorials.ws/capacitor/cap_5.html": "Capacitors in Parallel",
                "https://www.electronics-tutorials.ws/capacitor/cap_6.html": "Capacitor Color Code",
                "https://www.electronics-tutorials.ws/capacitor/cap_7.html": "Capacitive Reactance",
                "https://www.electronics-tutorials.ws/capacitor/cap_8.html": "Capacitor in AC Circuits",
                "https://www.electronics-tutorials.ws/capacitor/cap_9.html": "Energy Stored in a Capacitor",
                # Inductors
                "https://www.electronics-tutorials.ws/inductor/ind_1.html": "Introduction to Inductors",
                "https://www.electronics-tutorials.ws/inductor/ind_2.html": "Inductance of a Coil",
                "https://www.electronics-tutorials.ws/inductor/ind_3.html": "Inductors in Series",
                "https://www.electronics-tutorials.ws/inductor/ind_4.html": "Inductors in Parallel",
                "https://www.electronics-tutorials.ws/inductor/ind_5.html": "Inductive Reactance",
                "https://www.electronics-tutorials.ws/inductor/ind_6.html": "Inductor in AC Circuits",
                "https://www.electronics-tutorials.ws/inductor/ind_7.html": "LR Series Circuit",
                "https://www.electronics-tutorials.ws/inductor/ind_8.html": "Energy Stored in an Inductor",
                # DC Laws
                "https://www.electronics-tutorials.ws/dccircuits/dcp_1.html": "Ohm's Law and Power",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_2.html": "Kirchhoff's Circuit Laws",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_3.html": "Kirchhoff's Current Law",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_4.html": "Kirchhoff's Voltage Law",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_5.html": "Mesh Current Analysis",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_6.html": "Nodal Voltage Analysis",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_7.html": "Thevenin's Theorem",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_8.html": "Norton's Theorem",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_9.html": "Maximum Power Transfer",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_10.html": "Voltage Sources",
                "https://www.electronics-tutorials.ws/dccircuits/dcp_11.html": "Current Sources",
                # AC Theory
                "https://www.electronics-tutorials.ws/accircuits/ac-waveform.html": "AC Waveform",
                "https://www.electronics-tutorials.ws/accircuits/phase-difference.html": "Phase Difference",
                "https://www.electronics-tutorials.ws/accircuits/phasors.html": "Phasors",
                "https://www.electronics-tutorials.ws/accircuits/complex-numbers.html": "Complex Numbers in AC",
                "https://www.electronics-tutorials.ws/accircuits/series-circuit.html": "AC Series Circuit",
                "https://www.electronics-tutorials.ws/accircuits/parallel-circuit.html": "AC Parallel Circuit",
                "https://www.electronics-tutorials.ws/accircuits/series-resonance.html": "Series Resonance",
                "https://www.electronics-tutorials.ws/accircuits/parallel-resonance.html": "Parallel Resonance",
                "https://www.electronics-tutorials.ws/accircuits/power-in-ac-circuits.html": "Power in AC Circuits",
                "https://www.electronics-tutorials.ws/accircuits/power-triangle.html": "Power Triangle and Power Factor",
            },
        },
        "semiconductor-devices": {
            "pages": {
                # Diodes
                "https://www.electronics-tutorials.ws/diode/diode_1.html": "Introduction to Semiconductor Diodes",
                "https://www.electronics-tutorials.ws/diode/diode_2.html": "PN Junction Diode",
                "https://www.electronics-tutorials.ws/diode/diode_3.html": "Signal Diodes",
                "https://www.electronics-tutorials.ws/diode/diode_4.html": "Zener Diode",
                "https://www.electronics-tutorials.ws/diode/diode_5.html": "LED - Light Emitting Diode",
                "https://www.electronics-tutorials.ws/diode/diode_6.html": "Diode Clipping Circuits",
                "https://www.electronics-tutorials.ws/diode/diode_7.html": "Diode Clamping Circuits",
                "https://www.electronics-tutorials.ws/diode/diode_8.html": "Full Wave Rectifier",
                "https://www.electronics-tutorials.ws/diode/diode_9.html": "Bypass Diodes in Solar Panels",
                # Transistors - BJT
                "https://www.electronics-tutorials.ws/transistor/tran_1.html": "Bipolar Transistor",
                "https://www.electronics-tutorials.ws/transistor/tran_2.html": "NPN Transistor",
                "https://www.electronics-tutorials.ws/transistor/tran_3.html": "PNP Transistor",
                "https://www.electronics-tutorials.ws/transistor/tran_4.html": "Transistor as a Switch",
                "https://www.electronics-tutorials.ws/transistor/tran_5.html": "Darlington Transistor",
                "https://www.electronics-tutorials.ws/transistor/tran_6.html": "Transistor Biasing",
                "https://www.electronics-tutorials.ws/transistor/tran_7.html": "Common Emitter Amplifier",
                "https://www.electronics-tutorials.ws/transistor/tran_8.html": "Transistor Configurations",
                # FET
                "https://www.electronics-tutorials.ws/transistor/tran_9.html": "JFET Transistor",
                "https://www.electronics-tutorials.ws/transistor/tran_10.html": "MOSFET Transistor",
                "https://www.electronics-tutorials.ws/transistor/tran_11.html": "MOSFET as a Switch",
                # Thyristors
                "https://www.electronics-tutorials.ws/power/thyristor.html": "Thyristors",
                "https://www.electronics-tutorials.ws/power/triac.html": "TRIAC",
                "https://www.electronics-tutorials.ws/power/diac.html": "DIAC",
                # Photodiodes
                "https://www.electronics-tutorials.ws/diode/diode_photodiode.html": "Photodiode",
                "https://www.electronics-tutorials.ws/io/io_1.html": "Phototransistor",
            },
        },
        "op-amps": {
            "pages": {
                "https://www.electronics-tutorials.ws/opamp/opamp_1.html": "Operational Amplifier Basics",
                "https://www.electronics-tutorials.ws/opamp/opamp_2.html": "Inverting Operational Amplifier",
                "https://www.electronics-tutorials.ws/opamp/opamp_3.html": "Non-Inverting Operational Amplifier",
                "https://www.electronics-tutorials.ws/opamp/opamp_4.html": "Op-Amp Comparator",
                "https://www.electronics-tutorials.ws/opamp/opamp_5.html": "Differential Amplifier",
                "https://www.electronics-tutorials.ws/opamp/opamp_6.html": "Summing Amplifier",
                "https://www.electronics-tutorials.ws/opamp/opamp_7.html": "Integrator Amplifier",
                "https://www.electronics-tutorials.ws/opamp/opamp_8.html": "Differentiator Amplifier",
                "https://www.electronics-tutorials.ws/opamp/opamp_9.html": "Instrumentation Amplifier",
                "https://www.electronics-tutorials.ws/opamp/opamp_10.html": "Op-Amp Multivibrator",
                "https://www.electronics-tutorials.ws/filter/filter_1.html": "Passive Low Pass Filter",
                "https://www.electronics-tutorials.ws/filter/filter_2.html": "Passive High Pass Filter",
                "https://www.electronics-tutorials.ws/filter/filter_3.html": "Passive Band Pass Filter",
                "https://www.electronics-tutorials.ws/filter/filter_4.html": "Active Low Pass Filter",
                "https://www.electronics-tutorials.ws/filter/filter_5.html": "Active High Pass Filter",
                "https://www.electronics-tutorials.ws/filter/filter_6.html": "Active Band Pass Filter",
                "https://www.electronics-tutorials.ws/filter/filter_7.html": "Band Stop Filter",
                "https://www.electronics-tutorials.ws/filter/filter_8.html": "Butterworth Filter Design",
                "https://www.electronics-tutorials.ws/filter/filter_9.html": "Chebyshev Filter",
                "https://www.electronics-tutorials.ws/filter/filter_bessel.html": "Bessel Filter",
            },
        },
        "digital-logic": {
            "pages": {
                # Logic Gates
                "https://www.electronics-tutorials.ws/logic/logic_1.html": "Digital Logic Gates",
                "https://www.electronics-tutorials.ws/logic/logic_2.html": "AND Gate Tutorial",
                "https://www.electronics-tutorials.ws/logic/logic_3.html": "OR Gate Tutorial",
                "https://www.electronics-tutorials.ws/logic/logic_4.html": "NOT Gate (Inverter)",
                "https://www.electronics-tutorials.ws/logic/logic_5.html": "NAND Gate Tutorial",
                "https://www.electronics-tutorials.ws/logic/logic_6.html": "NOR Gate Tutorial",
                "https://www.electronics-tutorials.ws/logic/logic_7.html": "Exclusive-OR (XOR) Gate",
                "https://www.electronics-tutorials.ws/logic/logic_8.html": "Exclusive-NOR (XNOR) Gate",
                "https://www.electronics-tutorials.ws/logic/logic_9.html": "Universal NAND Gate",
                "https://www.electronics-tutorials.ws/logic/logic_10.html": "Universal NOR Gate",
                # Boolean Algebra
                "https://www.electronics-tutorials.ws/boolean/bool_1.html": "Boolean Algebra Introduction",
                "https://www.electronics-tutorials.ws/boolean/bool_2.html": "Laws of Boolean Algebra",
                "https://www.electronics-tutorials.ws/boolean/bool_3.html": "Boolean Algebra Examples",
                "https://www.electronics-tutorials.ws/boolean/bool_4.html": "De Morgan's Theorem",
                "https://www.electronics-tutorials.ws/boolean/bool_5.html": "Logic Gate Truth Tables",
                "https://www.electronics-tutorials.ws/boolean/bool_6.html": "Karnaugh Map",
                "https://www.electronics-tutorials.ws/boolean/bool_7.html": "Digital Logic Design",
                # Flip-Flops
                "https://www.electronics-tutorials.ws/sequential/seq_1.html": "SR Flip-Flop",
                "https://www.electronics-tutorials.ws/sequential/seq_2.html": "The JK Flip-Flop",
                "https://www.electronics-tutorials.ws/sequential/seq_3.html": "The D Flip-Flop",
                "https://www.electronics-tutorials.ws/sequential/seq_4.html": "The T Flip-Flop",
                "https://www.electronics-tutorials.ws/sequential/seq_5.html": "Sequential Logic Circuits",
                # Counters
                "https://www.electronics-tutorials.ws/counter/count_1.html": "Binary Counter",
                "https://www.electronics-tutorials.ws/counter/count_2.html": "BCD Counter Circuit",
                "https://www.electronics-tutorials.ws/counter/count_3.html": "Synchronous Counter",
                "https://www.electronics-tutorials.ws/counter/count_4.html": "Frequency Division",
                "https://www.electronics-tutorials.ws/counter/count_5.html": "Ripple Counter",
                # Shift Registers
                "https://www.electronics-tutorials.ws/sequential/seq_5.html": "Shift Register",
                "https://www.electronics-tutorials.ws/sequential/seq_6.html": "Shift Register Applications",
                # Combinational Logic
                "https://www.electronics-tutorials.ws/combination/comb_1.html": "Digital Multiplexer",
                "https://www.electronics-tutorials.ws/combination/comb_2.html": "Digital Demultiplexer",
                "https://www.electronics-tutorials.ws/combination/comb_3.html": "Binary Decoder",
                "https://www.electronics-tutorials.ws/combination/comb_4.html": "Binary Encoder",
                "https://www.electronics-tutorials.ws/combination/comb_5.html": "Binary Adder",
                "https://www.electronics-tutorials.ws/combination/comb_6.html": "Binary Subtractor",
                "https://www.electronics-tutorials.ws/combination/comb_7.html": "ALU - Arithmetic Logic Unit",
            },
        },
        "power-electronics": {
            "pages": {
                # Rectifiers
                "https://www.electronics-tutorials.ws/diode/diode_rectifier.html": "Half Wave Rectifier",
                "https://www.electronics-tutorials.ws/diode/diode_6.html": "Full Wave Rectifier",
                "https://www.electronics-tutorials.ws/power/power_1.html": "Unregulated Power Supply",
                "https://www.electronics-tutorials.ws/power/power_2.html": "Linear Voltage Regulator",
                "https://www.electronics-tutorials.ws/power/power_3.html": "Zener Voltage Regulator",
                "https://www.electronics-tutorials.ws/power/power_4.html": "Transistor Voltage Regulator",
                "https://www.electronics-tutorials.ws/power/power_5.html": "Switch Mode Power Supply",
                "https://www.electronics-tutorials.ws/power/power_6.html": "SMPS Topologies",
                "https://www.electronics-tutorials.ws/power/power_7.html": "Power Transistor",
                "https://www.electronics-tutorials.ws/power/power_8.html": "IGBT",
                # Transformers
                "https://www.electronics-tutorials.ws/transformer/transformer-basics.html": "Transformer Basics",
                "https://www.electronics-tutorials.ws/transformer/transformer-construction.html": "Transformer Construction",
                "https://www.electronics-tutorials.ws/transformer/transformer-loading.html": "Transformer Loading",
                "https://www.electronics-tutorials.ws/transformer/transformer-types.html": "Transformer Types",
                "https://www.electronics-tutorials.ws/transformer/current-transformer.html": "Current Transformer",
                "https://www.electronics-tutorials.ws/transformer/multiple-winding-transformers.html": "Multiple Winding Transformers",
                "https://www.electronics-tutorials.ws/transformer/transformer-auto.html": "Auto Transformer",
            },
        },
        "oscillators": {
            "pages": {
                "https://www.electronics-tutorials.ws/oscillator/oscillators.html": "Oscillator Tutorial",
                "https://www.electronics-tutorials.ws/oscillator/rc_oscillator.html": "RC Oscillator Circuit",
                "https://www.electronics-tutorials.ws/oscillator/lc_oscillator.html": "LC Oscillator Tutorial",
                "https://www.electronics-tutorials.ws/oscillator/hartley.html": "Hartley Oscillator",
                "https://www.electronics-tutorials.ws/oscillator/colpitts.html": "Colpitts Oscillator",
                "https://www.electronics-tutorials.ws/oscillator/wien_bridge.html": "Wien Bridge Oscillator",
                "https://www.electronics-tutorials.ws/oscillator/phase_shift.html": "Phase Shift Oscillator",
                "https://www.electronics-tutorials.ws/oscillator/crystal.html": "Crystal Oscillator",
                "https://www.electronics-tutorials.ws/oscillator/relaxation.html": "Relaxation Oscillator",
                "https://www.electronics-tutorials.ws/waveforms/555_timer.html": "555 Timer Tutorial",
                "https://www.electronics-tutorials.ws/waveforms/555_oscillator.html": "555 Oscillator",
                "https://www.electronics-tutorials.ws/waveforms/555_monostable.html": "555 Monostable Multivibrator",
                "https://www.electronics-tutorials.ws/waveforms/astable-multivibrator.html": "Astable Multivibrator",
            },
        },
        "communication": {
            "pages": {
                "https://www.electronics-tutorials.ws/oscillator/am_modulation.html": "Amplitude Modulation (AM)",
                "https://www.electronics-tutorials.ws/oscillator/fm_modulation.html": "Frequency Modulation (FM)",
                "https://www.electronics-tutorials.ws/oscillator/am_demodulation.html": "AM Demodulation",
                "https://www.electronics-tutorials.ws/oscillator/fm_demodulation.html": "FM Demodulation",
                "https://www.electronics-tutorials.ws/oscillator/pll.html": "Phase Locked Loop (PLL)",
                "https://www.electronics-tutorials.ws/oscillator/mixer.html": "Frequency Mixer",
                "https://www.electronics-tutorials.ws/oscillator/vco.html": "Voltage Controlled Oscillator (VCO)",
            },
        },
        "sensors": {
            "pages": {
                "https://www.electronics-tutorials.ws/io/io_1.html": "Phototransistor",
                "https://www.electronics-tutorials.ws/io/io_2.html": "Light Level Detector",
                "https://www.electronics-tutorials.ws/io/io_3.html": "Temperature Sensor",
                "https://www.electronics-tutorials.ws/io/io_4.html": "Thermocouple",
                "https://www.electronics-tutorials.ws/io/io_5.html": "Pressure Sensor",
                "https://www.electronics-tutorials.ws/io/io_6.html": "Position Sensor",
                "https://www.electronics-tutorials.ws/io/io_7.html": "Proximity Sensor",
                "https://www.electronics-tutorials.ws/io/io_8.html": "Hall Effect Sensor",
                "https://www.electronics-tutorials.ws/io/io_9.html": "Strain Gauge",
                "https://www.electronics-tutorials.ws/io/io_10.html": "Ultrasonic Sensor",
                "https://www.electronics-tutorials.ws/io/io_11.html": "Humidity Sensor",
                "https://www.electronics-tutorials.ws/io/io_12.html": "Piezoelectric Sensor",
            },
        },
        "motors": {
            "pages": {
                "https://www.electronics-tutorials.ws/io/io_7.html": "DC Motor",
                "https://www.electronics-tutorials.ws/io/io_stepmotor.html": "Stepper Motor",
                "https://www.electronics-tutorials.ws/io/io_servomotor.html": "Servo Motor",
                "https://www.electronics-tutorials.ws/io/io_brushless.html": "Brushless DC Motor",
                "https://www.electronics-tutorials.ws/electromagnetism/electromagnetic-induction.html": "Electromagnetic Induction",
                "https://www.electronics-tutorials.ws/electromagnetism/electromagnets.html": "Electromagnets",
                "https://www.electronics-tutorials.ws/electromagnetism/electromagnetic-field-theory.html": "Electromagnetic Field Theory",
                "https://www.electronics-tutorials.ws/electromagnetism/magnetic-hysteresis.html": "Magnetic Hysteresis",
            },
        },
        "waveforms": {
            "pages": {
                "https://www.electronics-tutorials.ws/waveforms/waveforms.html": "Waveform Types",
                "https://www.electronics-tutorials.ws/waveforms/waveform-harmonics.html": "Waveform Harmonics",
                "https://www.electronics-tutorials.ws/waveforms/waveform-duty-cycle.html": "Duty Cycle",
                "https://www.electronics-tutorials.ws/waveforms/waveform-generators.html": "Waveform Generators",
                "https://www.electronics-tutorials.ws/waveforms/sine-wave.html": "Sine Wave",
                "https://www.electronics-tutorials.ws/waveforms/square-wave.html": "Square Wave",
                "https://www.electronics-tutorials.ws/waveforms/triangle-wave.html": "Triangle Wave",
                "https://www.electronics-tutorials.ws/waveforms/sawtooth-wave.html": "Sawtooth Wave",
            },
        },
        "binary-numbers": {
            "pages": {
                "https://www.electronics-tutorials.ws/binary/bin_1.html": "Binary Number System",
                "https://www.electronics-tutorials.ws/binary/bin_2.html": "Binary Addition",
                "https://www.electronics-tutorials.ws/binary/bin_3.html": "Binary Subtraction",
                "https://www.electronics-tutorials.ws/binary/bin_4.html": "Binary Multiplication",
                "https://www.electronics-tutorials.ws/binary/bin_5.html": "Binary Division",
                "https://www.electronics-tutorials.ws/binary/bin_oct.html": "Octal Number System",
                "https://www.electronics-tutorials.ws/binary/bin_hex.html": "Hexadecimal Number System",
                "https://www.electronics-tutorials.ws/binary/binary-coded-decimal.html": "Binary Coded Decimal (BCD)",
                "https://www.electronics-tutorials.ws/binary/signed-binary.html": "Signed Binary Numbers",
                "https://www.electronics-tutorials.ws/binary/binary-fractions.html": "Binary Fractions",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"electronics-tutorials-{source_key}" if source_key else "electronics-tutorials"
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
            for suffix in [' - Electronics Tutorials']:
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
                        "category": f"electronics-tutorials-{source_key}",
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
            self.log.info(f"=== Scraping electronics-tutorials/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    ElectronicsTutorialsScraper(base, source_key).run()
