#!/usr/bin/env python3
"""All About Circuits textbook scraper.

Covers:
  - Volume I: DC (basic concepts through network analysis)
  - Volume II: AC (AC theory through power systems)
  - Volume III: Semiconductors (diodes through IC technology)
  - Volume IV: Digital (binary through digital communication)
  - Volume V: Reference (tables, equations, pinouts)
  - Volume VI: Experiments (practical labs)
  - Worksheets (practice problems)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class AllAboutCircuitsScraper(BaseScraper):
    """Scrape All About Circuits textbook volumes and worksheets."""

    SOURCES = {
        "dc": {
            "pages": {
                # Volume I - DC: Basic Concepts
                "https://www.allaboutcircuits.com/textbook/direct-current/": "DC - Volume I Index",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/static-electricity/": "Static Electricity",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/atoms-and-their-structure/": "Atoms and Their Structure",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/conductors-insulators-and-electron-flow/": "Conductors, Insulators, and Electron Flow",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/electric-circuits/": "Electric Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/voltage-and-current/": "Voltage and Current",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/resistance/": "Resistance",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/voltage-current-resistance-relate/": "How Voltage, Current, and Resistance Relate",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/polarity-of-voltage-drops/": "Polarity of Voltage Drops",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-1/computer-simulation-of-electric-circuits/": "Computer Simulation of Electric Circuits",
                # Ohm's Law
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-2/how-voltage-current-and-resistance-relate/": "Ohm's Law - How V, I, R Relate",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-2/an-analogy-for-ohms-law/": "An Analogy for Ohm's Law",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-2/power-in-electric-circuits/": "Power in Electric Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-2/calculating-electric-power/": "Calculating Electric Power",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-2/resistors/": "Resistors",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-2/nonlinear-conduction/": "Nonlinear Conduction",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-2/circuit-wiring/": "Circuit Wiring",
                # Electrical Safety
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-3/importance-of-electrical-safety/": "Importance of Electrical Safety",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-3/physiological-effects-of-electricity/": "Physiological Effects of Electricity",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-3/shock-current-path/": "Shock Current Path",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-3/ohms-law-body-resistance/": "Ohm's Law and Body Resistance",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-3/safe-practices/": "Safe Practices",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-3/emergency-response/": "Emergency Response",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-3/common-sources-of-hazard/": "Common Sources of Hazard",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-3/safe-circuit-design/": "Safe Circuit Design",
                # Series Circuits
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/what-are-series-and-parallel-circuits/": "What Are Series and Parallel Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/simple-series-circuits/": "Simple Series Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/resistance-series-circuits/": "Resistance in Series Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/series-circuits-and-power/": "Series Circuits and Power",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/correct-use-of-ohms-law/": "Correct Use of Ohm's Law",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/kirchhoffs-voltage-law-kvl/": "Kirchhoff's Voltage Law (KVL)",
                # Parallel Circuits
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/what-is-a-parallel-circuit/": "What Is a Parallel Circuit",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/simple-parallel-circuits/": "Simple Parallel Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/conductance/": "Conductance",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/parallel-circuits-and-power/": "Parallel Circuits and Power",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/correct-use-of-ohms-law-parallel/": "Correct Use of Ohm's Law (Parallel)",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-5/kirchhoffs-current-law-kcl/": "Kirchhoff's Current Law (KCL)",
                # Series-Parallel Combination Circuits
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-7/what-is-a-series-parallel-circuit/": "What Is a Series-Parallel Circuit",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-7/analysis-technique/": "Series-Parallel Analysis Technique",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-7/re-drawing-complex-schematics/": "Re-Drawing Complex Schematics",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-7/component-failure-analysis/": "Component Failure Analysis",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-7/building-series-parallel-resistor-circuits/": "Building Series-Parallel Resistor Circuits",
                # Divider Circuits and Kirchhoff's Laws
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-6/voltage-divider-circuits/": "Voltage Divider Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-6/kirchhoffs-voltage-law-kvl/": "KVL for Dividers",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-6/current-divider-circuits-and-the-current-divider-formula/": "Current Divider Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-6/kirchhoffs-current-law-kcl/": "KCL for Dividers",
                # DC Metering Circuits
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-8/what-is-a-meter/": "What Is a Meter",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-8/voltmeter-design/": "Voltmeter Design",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-8/ammeter-design/": "Ammeter Design",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-8/ohmmeter-design/": "Ohmmeter Design",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-8/multimeters/": "Multimeters",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-8/kelvin-resistance-measurement/": "Kelvin Resistance Measurement",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-8/bridge-circuits/": "Bridge Circuits",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-8/wattmeter-design/": "Wattmeter Design",
                # Batteries and Power Systems
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-11/electron-activity-in-chemical-reactions/": "Electron Activity in Chemical Reactions",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-11/battery-construction/": "Battery Construction",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-11/battery-ratings/": "Battery Ratings",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-11/special-purpose-batteries/": "Special Purpose Batteries",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-11/practical-considerations/": "Battery Practical Considerations",
                # DC Network Analysis
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/what-is-network-analysis/": "What Is Network Analysis",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/branch-current-method/": "Branch Current Method",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/mesh-current-method/": "Mesh Current Method",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/node-voltage-method/": "Node Voltage Method",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/thevenins-theorem/": "Thevenin's Theorem",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/nortons-theorem/": "Norton's Theorem",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/thevenin-norton-equivalencies/": "Thevenin-Norton Equivalencies",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/millmans-theorem/": "Millman's Theorem",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/superposition-theorem/": "Superposition Theorem",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/maximum-power-transfer-theorem/": "Maximum Power Transfer Theorem",
                "https://www.allaboutcircuits.com/textbook/direct-current/chpt-10/delta-y-and-y-delta-conversions/": "Delta-Y and Y-Delta Conversions",
            },
        },
        "ac": {
            "pages": {
                # Volume II - AC: Basic AC Theory
                "https://www.allaboutcircuits.com/textbook/alternating-current/": "AC - Volume II Index",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-1/what-is-alternating-current-ac/": "What Is Alternating Current (AC)",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-1/ac-waveforms/": "AC Waveforms",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-1/measurements-of-ac-magnitude/": "Measurements of AC Magnitude",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-1/simple-ac-circuit-calculations/": "Simple AC Circuit Calculations",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-1/ac-phase/": "AC Phase",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-1/principles-of-radio/": "Principles of Radio",
                # Complex Numbers
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-2/introduction-to-complex-numbers/": "Introduction to Complex Numbers",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-2/vectors-and-ac-waveforms/": "Vectors and AC Waveforms",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-2/simple-vector-addition/": "Simple Vector Addition",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-2/complex-vector-addition/": "Complex Vector Addition",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-2/polar-and-rectangular-notation/": "Polar and Rectangular Notation",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-2/complex-number-arithmetic/": "Complex Number Arithmetic",
                # Reactance and Impedance
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/ac-resistor-circuits/": "AC Resistor Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/ac-inductor-circuits/": "AC Inductor Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/ac-capacitor-circuits/": "AC Capacitor Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/series-resistor-inductor-circuits/": "Series Resistor-Inductor Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/parallel-resistor-inductor-circuits/": "Parallel Resistor-Inductor Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/series-resistor-capacitor-circuits/": "Series Resistor-Capacitor Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/parallel-resistor-capacitor-circuits/": "Parallel Resistor-Capacitor Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/series-r-l-and-c/": "Series R, L, and C",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/parallel-r-l-and-c/": "Parallel R, L, and C",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-3/susceptance-and-admittance/": "Susceptance and Admittance",
                # Resonance
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-6/an-electric-pendulum/": "An Electric Pendulum",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-6/simple-series-resonance/": "Simple Series Resonance",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-6/simple-parallel-resonance/": "Simple Parallel Resonance",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-6/resonance-in-series-parallel-circuits/": "Resonance in Series-Parallel Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-6/q-and-bandwidth-of-a-resonant-circuit/": "Q and Bandwidth of a Resonant Circuit",
                # AC Metering
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-12/ac-voltmeters-and-ammeters/": "AC Voltmeters and Ammeters",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-12/frequency-and-phase-measurement/": "Frequency and Phase Measurement",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-12/power-measurement/": "AC Power Measurement",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-12/ac-bridge-circuits/": "AC Bridge Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-12/ac-instrumentation-transducers/": "AC Instrumentation Transducers",
                # Power Factor
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-11/what-is-power-factor/": "What Is Power Factor",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-11/calculating-power-factor/": "Calculating Power Factor",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-11/practical-power-factor-correction/": "Practical Power Factor Correction",
                # Transformers
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/mutual-inductance-and-basic-operation/": "Mutual Inductance and Basic Operation",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/step-up-and-step-down-transformers/": "Step-Up and Step-Down Transformers",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/electrical-isolation/": "Electrical Isolation",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/phasing/": "Transformer Phasing",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/winding-configurations/": "Winding Configurations",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/voltage-regulation/": "Transformer Voltage Regulation",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/special-transformers-and-applications/": "Special Transformers and Applications",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-9/practical-considerations-transformers/": "Practical Considerations - Transformers",
                # Polyphase AC
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-10/what-is-polyphase/": "What Is Polyphase",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-10/three-phase-power-systems/": "Three-Phase Power Systems",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-10/phase-rotation/": "Phase Rotation",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-10/polyphase-motor-design/": "Polyphase Motor Design",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-10/three-phase-y-and-delta-configurations/": "Three-Phase Y and Delta Configurations",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-10/three-phase-transformer-circuits/": "Three-Phase Transformer Circuits",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-10/harmonics-in-polyphase-power-systems/": "Harmonics in Polyphase Power Systems",
                # Power Systems
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-13/characteristics-of-power-systems/": "Characteristics of Power Systems",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-13/power-generation/": "Power Generation",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-13/power-transmission/": "Power Transmission",
                "https://www.allaboutcircuits.com/textbook/alternating-current/chpt-13/power-distribution/": "Power Distribution",
            },
        },
        "semiconductors": {
            "pages": {
                # Volume III - Semiconductors
                "https://www.allaboutcircuits.com/textbook/semiconductors/": "Semiconductors - Volume III Index",
                # Diodes and Rectifiers
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/introduction-to-diodes-and-rectifiers/": "Introduction to Diodes and Rectifiers",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/meter-check-of-a-diode/": "Meter Check of a Diode",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/diode-ratings/": "Diode Ratings",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/rectifier-circuits/": "Rectifier Circuits",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/clipper-circuits/": "Clipper Circuits",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/clamper-circuits/": "Clamper Circuits",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/voltage-multipliers/": "Voltage Multipliers",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/zener-diodes/": "Zener Diodes",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-3/special-purpose-diodes/": "Special Purpose Diodes",
                # BJTs
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/introduction-to-bipolar-junction-transistors-bjt/": "Introduction to BJTs",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/the-bipolar-junction-transistor-bjt-as-a-switch/": "BJT as a Switch",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/meter-check-of-a-transistor/": "Meter Check of a Transistor",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/active-mode-operation/": "Active Mode Operation",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/the-common-emitter-amplifier/": "Common Emitter Amplifier",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/the-common-collector-amplifier/": "Common Collector Amplifier",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/the-common-base-amplifier/": "Common Base Amplifier",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/biasing-techniques/": "Biasing Techniques",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/input-and-output-coupling/": "Input and Output Coupling",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/feedback/": "Transistor Feedback",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-4/transistor-ratings-and-packages/": "Transistor Ratings and Packages",
                # JFETs
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-5/introduction-to-junction-field-effect-transistors-jfet/": "Introduction to JFETs",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-5/the-jfet-as-a-switch/": "JFET as a Switch",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-5/meter-check-of-a-jfet/": "Meter Check of a JFET",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-5/jfet-quirks/": "JFET Quirks",
                # MOSFETs
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/introduction-to-insulated-gate-field-effect-transistors-mosfet/": "Introduction to MOSFETs",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/depletion-type-igfets/": "Depletion-Type IGFETs",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/enhancement-type-igfets/": "Enhancement-Type IGFETs",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/active-mode-operation-igfet/": "Active Mode Operation (IGFET)",
                # Thyristors
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/silicon-controlled-rectifier-scr/": "Silicon-Controlled Rectifier (SCR)",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/the-shockley-diode/": "The Shockley Diode",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/the-diac/": "The DIAC",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-7/the-triac/": "The TRIAC",
                # Op-Amps
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/introduction-to-operational-amplifiers/": "Introduction to Operational Amplifiers",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/the-ideal-op-amp/": "The Ideal Op-Amp",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/practical-considerations-op-amps/": "Practical Considerations - Op-Amps",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/op-amp-models/": "Op-Amp Models",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/the-inverting-amplifier/": "The Inverting Amplifier",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/the-noninverting-amplifier/": "The Noninverting Amplifier",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/the-voltage-follower/": "The Voltage Follower",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/the-summing-amplifier/": "The Summing Amplifier",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/the-difference-amplifier/": "The Difference Amplifier",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/the-instrumentation-amplifier/": "The Instrumentation Amplifier",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/the-differentiator-and-integrator/": "The Differentiator and Integrator",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/positive-feedback/": "Positive Feedback",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/voltage-comparator/": "Voltage Comparator",
                # Active Filters
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-8/active-filters/": "Active Filters",
                # Semiconductor Manufacturing
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-2/elementary-semiconductor-physics/": "Elementary Semiconductor Physics",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-2/band-theory-of-solids/": "Band Theory of Solids",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-2/electrons-and-holes/": "Electrons and Holes",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-2/the-p-n-junction/": "The P-N Junction",
                "https://www.allaboutcircuits.com/textbook/semiconductors/chpt-2/junction-diode/": "Junction Diode",
            },
        },
        "digital": {
            "pages": {
                # Volume IV - Digital
                "https://www.allaboutcircuits.com/textbook/digital/": "Digital - Volume IV Index",
                # Binary
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/numbers-and-symbols/": "Numbers and Symbols",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/binary-numeration-system/": "Binary Numeration System",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/octal-and-hexadecimal-numeration-systems/": "Octal and Hexadecimal Systems",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/binary-decimal-conversion/": "Binary-Decimal Conversion",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/octal-and-hexadecimal-to-decimal-conversion/": "Octal/Hex to Decimal Conversion",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/binary-addition/": "Binary Addition",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/negative-binary-numbers/": "Negative Binary Numbers",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/binary-overflow/": "Binary Overflow",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-1/binary-count-sequence/": "Binary Count Sequence",
                # Logic Gates
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/digital-signals-and-gates/": "Digital Signals and Gates",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/the-not-gate/": "The NOT Gate",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/the-and-gate/": "The AND Gate",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/the-nand-gate/": "The NAND Gate",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/the-or-gate/": "The OR Gate",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/the-nor-gate/": "The NOR Gate",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/the-xor-gate/": "The XOR Gate",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/the-xnor-gate/": "The XNOR Gate",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/ttl-nand-and-and-gates/": "TTL NAND and AND Gates",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-3/ttl-nor-and-or-gates/": "TTL NOR and OR Gates",
                # Boolean Algebra
                "https://www.allaboutcircuits.com/textbook/digital/chpt-7/introduction-to-boolean-algebra/": "Introduction to Boolean Algebra",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-7/boolean-arithmetic/": "Boolean Arithmetic",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-7/boolean-algebraic-identities/": "Boolean Algebraic Identities",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-7/boolean-algebraic-properties/": "Boolean Algebraic Properties",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-7/boolean-rules-for-simplification/": "Boolean Rules for Simplification",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-7/circuit-simplification-examples/": "Circuit Simplification Examples",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-8/the-karnaugh-map/": "The Karnaugh Map",
                # Combinational Logic
                "https://www.allaboutcircuits.com/textbook/digital/chpt-9/combinational-logic-functions/": "Combinational Logic Functions",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-9/adder-circuits/": "Adder Circuits",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-9/multiplexers-and-demultiplexers/": "Multiplexers and Demultiplexers",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-9/decoder-circuits/": "Decoder Circuits",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-9/encoder-circuits/": "Encoder Circuits",
                # Sequential Logic
                "https://www.allaboutcircuits.com/textbook/digital/chpt-10/the-s-r-latch/": "The S-R Latch",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-10/the-gated-s-r-latch/": "The Gated S-R Latch",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-10/the-d-latch/": "The D Latch",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-10/edge-triggered-latches-flip-flops/": "Edge-Triggered Latches (Flip-Flops)",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-10/the-j-k-flip-flop/": "The J-K Flip-Flop",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-10/asynchronous-flip-flop-inputs/": "Asynchronous Flip-Flop Inputs",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-10/monostable-multivibrators/": "Monostable Multivibrators",
                # Shift Registers
                "https://www.allaboutcircuits.com/textbook/digital/chpt-12/shift-registers/": "Shift Registers",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-12/parallel-in-serial-out-shift-register/": "Parallel-In Serial-Out Shift Register",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-12/serial-in-parallel-out-shift-register/": "Serial-In Parallel-Out Shift Register",
                # Counters
                "https://www.allaboutcircuits.com/textbook/digital/chpt-11/binary-count-sequence-revisited/": "Binary Count Sequence Revisited",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-11/asynchronous-counters/": "Asynchronous Counters",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-11/synchronous-counters/": "Synchronous Counters",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-11/counter-modulus/": "Counter Modulus",
                # A/D and D/A Conversion
                "https://www.allaboutcircuits.com/textbook/digital/chpt-13/digital-to-analog-conversion/": "Digital-to-Analog Conversion",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-13/analog-to-digital-conversion/": "Analog-to-Digital Conversion",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-13/practical-considerations-adc/": "Practical Considerations - ADC",
                # Digital Communication
                "https://www.allaboutcircuits.com/textbook/digital/chpt-14/networks-and-busses/": "Networks and Busses",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-14/digital-communication/": "Digital Communication",
                "https://www.allaboutcircuits.com/textbook/digital/chpt-14/serial-and-parallel-data-transfer/": "Serial and Parallel Data Transfer",
            },
        },
        "reference": {
            "pages": {
                # Volume V - Reference
                "https://www.allaboutcircuits.com/textbook/reference/": "Reference - Volume V Index",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-1/resistor-color-codes/": "Resistor Color Codes",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-1/capacitor-color-codes/": "Capacitor Color Codes",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-2/algebra-reference/": "Algebra Reference",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-2/trigonometry-reference/": "Trigonometry Reference",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-2/calculus-reference/": "Calculus Reference",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-3/periodic-table-of-the-elements/": "Periodic Table of the Elements",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-4/specific-resistance-of-materials/": "Specific Resistance of Materials",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-4/temperature-coefficient-of-resistance/": "Temperature Coefficient of Resistance",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-4/critical-temperatures-for-superconductors/": "Critical Temperatures for Superconductors",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-5/dielectric-strengths-for-common-materials/": "Dielectric Strengths for Common Materials",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-5/capacitor-equations/": "Capacitor Equations",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-6/inductor-equations/": "Inductor Equations",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-7/conversion-factors/": "Conversion Factors",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-8/555-timer-circuits/": "555 Timer Circuits",
                "https://www.allaboutcircuits.com/textbook/reference/chpt-9/ic-op-amp-pinouts/": "IC Op-Amp Pinouts",
            },
        },
        "experiments": {
            "pages": {
                # Volume VI - Experiments
                "https://www.allaboutcircuits.com/textbook/experiments/": "Experiments - Volume VI Index",
                "https://www.allaboutcircuits.com/textbook/experiments/chpt-1/introduction-dc-experiments/": "Introduction to DC Experiments",
                "https://www.allaboutcircuits.com/textbook/experiments/chpt-1/basic-concepts-and-test-equipment/": "Basic Concepts and Test Equipment",
                "https://www.allaboutcircuits.com/textbook/experiments/chpt-1/series-and-parallel-circuits-experiment/": "Series and Parallel Circuits Experiment",
                "https://www.allaboutcircuits.com/textbook/experiments/chpt-1/voltage-divider/": "Voltage Divider Experiment",
                "https://www.allaboutcircuits.com/textbook/experiments/chpt-2/introduction-ac-experiments/": "Introduction to AC Experiments",
                "https://www.allaboutcircuits.com/textbook/experiments/chpt-3/introduction-semiconductor-experiments/": "Introduction to Semiconductor Experiments",
                "https://www.allaboutcircuits.com/textbook/experiments/chpt-4/introduction-digital-experiments/": "Introduction to Digital Experiments",
                "https://www.allaboutcircuits.com/textbook/experiments/chpt-5/555-timer-experiment/": "555 Timer Experiment",
            },
        },
        "worksheets": {
            "pages": {
                "https://www.allaboutcircuits.com/worksheets/": "Worksheets Index",
                "https://www.allaboutcircuits.com/worksheets/dc-circuits/": "DC Circuits Worksheets",
                "https://www.allaboutcircuits.com/worksheets/ac-circuits/": "AC Circuits Worksheets",
                "https://www.allaboutcircuits.com/worksheets/semiconductors/": "Semiconductors Worksheets",
                "https://www.allaboutcircuits.com/worksheets/digital-circuits/": "Digital Circuits Worksheets",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"allaboutcircuits-{source_key}" if source_key else "allaboutcircuits"
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
            for suffix in [' | All About Circuits', ' - All About Circuits']:
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
                        "category": f"allaboutcircuits-{source_key}",
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
            self.log.info(f"=== Scraping allaboutcircuits/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    AllAboutCircuitsScraper(base, source_key).run()
