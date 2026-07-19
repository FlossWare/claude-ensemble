#!/usr/bin/env python3
"""The Engineering ToolBox scraper.

Covers:
  - Fluid Mechanics (pipe flow, Bernoulli, Reynolds, pumps, valves)
  - Thermodynamics (heat transfer, steam tables, air/water properties)
  - Electrical (wire gauges, voltage drop, motors, transformers)
  - HVAC (air conditioning, ductwork, psychrometrics, ventilation)
  - Materials (steel, aluminum, copper, concrete, wood)
  - Piping (dimensions, fittings, flanges, insulation)
  - Structural (beams, loads, stress/strain, moment of inertia)
  - Hydraulics (systems, cylinders, pumps, fluids)
  - Unit Conversion (length, area, volume, mass, pressure, energy)
  - Water Systems (supply, sewage, treatment, fire protection)
  - Acoustics (sound levels, noise control, insulation)
  - Gases (ideal gas law, compressed air, natural gas)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class EngineeringToolboxScraper(BaseScraper):
    """Scrape The Engineering ToolBox reference pages."""

    SOURCES = {
        "fluid-mechanics": {
            "pages": {
                "https://www.engineeringtoolbox.com/bernoulli-equation-d_183.html": "Bernoulli Equation",
                "https://www.engineeringtoolbox.com/reynolds-number-d_237.html": "Reynolds Number",
                "https://www.engineeringtoolbox.com/darcy-weisbach-equation-d_646.html": "Darcy-Weisbach Equation",
                "https://www.engineeringtoolbox.com/moody-diagram-d_618.html": "Moody Diagram",
                "https://www.engineeringtoolbox.com/hazen-williams-coefficients-d_798.html": "Hazen-Williams Coefficients",
                "https://www.engineeringtoolbox.com/colebrook-equation-d_1031.html": "Colebrook Equation",
                "https://www.engineeringtoolbox.com/fluid-flow-velocity-pipe-d_726.html": "Fluid Flow Velocity in Pipes",
                "https://www.engineeringtoolbox.com/hydraulic-diameter-d_110.html": "Hydraulic Diameter",
                "https://www.engineeringtoolbox.com/minor-loss-coefficients-pipes-d_626.html": "Minor Loss Coefficients in Pipes",
                "https://www.engineeringtoolbox.com/pipe-equivalent-length-d_2004.html": "Pipe Equivalent Length",
                "https://www.engineeringtoolbox.com/flow-coefficients-d_277.html": "Flow Coefficients - Cv and Kv",
                "https://www.engineeringtoolbox.com/pumps-t_34.html": "Pumps Overview",
                "https://www.engineeringtoolbox.com/centrifugal-pumps-d_54.html": "Centrifugal Pumps",
                "https://www.engineeringtoolbox.com/pump-affinity-laws-d_408.html": "Pump Affinity Laws",
                "https://www.engineeringtoolbox.com/npsh-net-positive-suction-head-d_634.html": "NPSH - Net Positive Suction Head",
                "https://www.engineeringtoolbox.com/cavitation-d_407.html": "Cavitation",
                "https://www.engineeringtoolbox.com/dynamic-absolute-kinematic-viscosity-d_412.html": "Dynamic and Kinematic Viscosity",
                "https://www.engineeringtoolbox.com/water-dynamic-kinematic-viscosity-d_596.html": "Water - Dynamic and Kinematic Viscosity",
                "https://www.engineeringtoolbox.com/specific-gravity-liquids-d_336.html": "Specific Gravity of Liquids",
                "https://www.engineeringtoolbox.com/absolute-dynamic-viscosity-liquids-d_1187.html": "Absolute Viscosity of Liquids",
                "https://www.engineeringtoolbox.com/orifice-nozzle-venturi-d_590.html": "Orifice, Nozzle, Venturi Flow",
                "https://www.engineeringtoolbox.com/valve-types-d_1073.html": "Valve Types",
                "https://www.engineeringtoolbox.com/check-valve-d_938.html": "Check Valves",
            },
        },
        "thermodynamics": {
            "pages": {
                "https://www.engineeringtoolbox.com/conductive-heat-transfer-d_428.html": "Conductive Heat Transfer",
                "https://www.engineeringtoolbox.com/convective-heat-transfer-d_430.html": "Convective Heat Transfer",
                "https://www.engineeringtoolbox.com/radiation-heat-transfer-d_431.html": "Radiation Heat Transfer",
                "https://www.engineeringtoolbox.com/overall-heat-transfer-coefficient-d_434.html": "Overall Heat Transfer Coefficient",
                "https://www.engineeringtoolbox.com/thermal-conductivity-d_429.html": "Thermal Conductivity",
                "https://www.engineeringtoolbox.com/thermal-conductivity-metals-d_858.html": "Thermal Conductivity of Metals",
                "https://www.engineeringtoolbox.com/heat-exchanger-effectiveness-d_615.html": "Heat Exchanger Effectiveness",
                "https://www.engineeringtoolbox.com/lmtd-d_1171.html": "LMTD - Log Mean Temperature Difference",
                "https://www.engineeringtoolbox.com/fouling-heat-transfer-d_1661.html": "Fouling and Heat Transfer",
                "https://www.engineeringtoolbox.com/saturated-steam-properties-d_101.html": "Saturated Steam Properties",
                "https://www.engineeringtoolbox.com/superheated-steam-properties-d_103.html": "Superheated Steam Properties",
                "https://www.engineeringtoolbox.com/boiling-point-water-d_926.html": "Boiling Point of Water",
                "https://www.engineeringtoolbox.com/specific-heat-capacity-water-d_660.html": "Specific Heat Capacity of Water",
                "https://www.engineeringtoolbox.com/air-properties-d_156.html": "Air Properties",
                "https://www.engineeringtoolbox.com/dry-air-properties-d_973.html": "Dry Air Properties",
                "https://www.engineeringtoolbox.com/air-density-specific-weight-d_600.html": "Air Density and Specific Weight",
                "https://www.engineeringtoolbox.com/water-properties-d_1508.html": "Water Properties",
                "https://www.engineeringtoolbox.com/water-thermal-properties-d_162.html": "Water Thermal Properties",
                "https://www.engineeringtoolbox.com/specific-heat-gases-d_159.html": "Specific Heat of Gases",
                "https://www.engineeringtoolbox.com/enthalpy-moist-air-d_683.html": "Enthalpy of Moist Air",
                "https://www.engineeringtoolbox.com/carnot-efficiency-d_1199.html": "Carnot Efficiency",
                "https://www.engineeringtoolbox.com/heat-transfer-coefficients-d_1529.html": "Heat Transfer Coefficients",
            },
        },
        "electrical": {
            "pages": {
                "https://www.engineeringtoolbox.com/awg-wire-gauge-d_731.html": "AWG - American Wire Gauge",
                "https://www.engineeringtoolbox.com/wire-gauges-d_419.html": "Wire Gauges",
                "https://www.engineeringtoolbox.com/voltage-drop-conductor-d_734.html": "Voltage Drop in Conductors",
                "https://www.engineeringtoolbox.com/electrical-motor-data-d_291.html": "Electrical Motor Data",
                "https://www.engineeringtoolbox.com/electrical-motor-efficiency-d_655.html": "Electrical Motor Efficiency",
                "https://www.engineeringtoolbox.com/electrical-motor-full-load-current-d_1218.html": "Motor Full-Load Current",
                "https://www.engineeringtoolbox.com/power-factor-electrical-motor-d_654.html": "Power Factor - Electrical Motors",
                "https://www.engineeringtoolbox.com/transformer-sizing-d_1122.html": "Transformer Sizing",
                "https://www.engineeringtoolbox.com/electrical-resistivity-conductivity-d_418.html": "Electrical Resistivity and Conductivity",
                "https://www.engineeringtoolbox.com/ohms-law-d_379.html": "Ohm's Law",
                "https://www.engineeringtoolbox.com/kva-kw-d_888.html": "kVA and kW",
                "https://www.engineeringtoolbox.com/three-phase-electrical-d_1455.html": "Three Phase Electrical Power",
                "https://www.engineeringtoolbox.com/nema-enclosure-types-d_935.html": "NEMA Enclosure Types",
                "https://www.engineeringtoolbox.com/ip-ingress-protection-d_452.html": "IP Ingress Protection",
                "https://www.engineeringtoolbox.com/electrical-formulas-d_455.html": "Electrical Formulas",
            },
        },
        "hvac": {
            "pages": {
                "https://www.engineeringtoolbox.com/air-conditioning-d_72.html": "Air Conditioning Overview",
                "https://www.engineeringtoolbox.com/hvac-systems-d_67.html": "HVAC Systems",
                "https://www.engineeringtoolbox.com/cooling-loads-d_665.html": "Cooling Loads",
                "https://www.engineeringtoolbox.com/heating-systems-d_68.html": "Heating Systems",
                "https://www.engineeringtoolbox.com/heat-loss-buildings-d_113.html": "Heat Loss from Buildings",
                "https://www.engineeringtoolbox.com/ductwork-d_82.html": "Ductwork",
                "https://www.engineeringtoolbox.com/duct-sizing-d_1041.html": "Duct Sizing",
                "https://www.engineeringtoolbox.com/duct-velocity-d_1044.html": "Duct Air Velocity",
                "https://www.engineeringtoolbox.com/duct-friction-loss-d_1042.html": "Duct Friction Loss",
                "https://www.engineeringtoolbox.com/psychrometric-chart-d_816.html": "Psychrometric Chart",
                "https://www.engineeringtoolbox.com/psychrometric-terms-d_239.html": "Psychrometric Terms",
                "https://www.engineeringtoolbox.com/relative-humidity-air-d_687.html": "Relative Humidity of Air",
                "https://www.engineeringtoolbox.com/ventilation-rates-d_234.html": "Ventilation Rates",
                "https://www.engineeringtoolbox.com/air-change-rate-room-d_867.html": "Air Change Rate",
                "https://www.engineeringtoolbox.com/ashrae-62-ventilation-standard-d_60.html": "ASHRAE 62 Ventilation Standard",
                "https://www.engineeringtoolbox.com/indoor-air-quality-iaq-d_702.html": "Indoor Air Quality (IAQ)",
                "https://www.engineeringtoolbox.com/refrigerants-d_902.html": "Refrigerants",
                "https://www.engineeringtoolbox.com/refrigeration-cycle-d_1781.html": "Refrigeration Cycle",
                "https://www.engineeringtoolbox.com/cop-coefficient-of-performance-d_1075.html": "COP - Coefficient of Performance",
                "https://www.engineeringtoolbox.com/fan-laws-d_210.html": "Fan Laws",
                "https://www.engineeringtoolbox.com/fans-efficiency-power-d_197.html": "Fan Efficiency and Power",
            },
        },
        "materials": {
            "pages": {
                "https://www.engineeringtoolbox.com/young-modulus-d_417.html": "Young's Modulus of Elasticity",
                "https://www.engineeringtoolbox.com/poissons-ratio-d_1224.html": "Poisson's Ratio",
                "https://www.engineeringtoolbox.com/steel-properties-d_1601.html": "Steel Properties",
                "https://www.engineeringtoolbox.com/steel-yield-strength-d_2041.html": "Steel Yield Strength",
                "https://www.engineeringtoolbox.com/stainless-steel-properties-d_1604.html": "Stainless Steel Properties",
                "https://www.engineeringtoolbox.com/aluminum-properties-d_1602.html": "Aluminum Properties",
                "https://www.engineeringtoolbox.com/copper-alloys-properties-d_1606.html": "Copper Alloy Properties",
                "https://www.engineeringtoolbox.com/concrete-properties-d_1223.html": "Concrete Properties",
                "https://www.engineeringtoolbox.com/wood-density-d_40.html": "Wood Density",
                "https://www.engineeringtoolbox.com/wood-mechanical-properties-d_1789.html": "Wood Mechanical Properties",
                "https://www.engineeringtoolbox.com/plastic-properties-d_1222.html": "Plastic Properties",
                "https://www.engineeringtoolbox.com/melting-temperature-metals-d_860.html": "Melting Temperature of Metals",
                "https://www.engineeringtoolbox.com/density-solids-d_1265.html": "Density of Solids",
                "https://www.engineeringtoolbox.com/corrosion-metals-d_907.html": "Corrosion of Metals",
                "https://www.engineeringtoolbox.com/galvanic-corrosion-d_394.html": "Galvanic Corrosion",
                "https://www.engineeringtoolbox.com/coefficient-thermal-expansion-d_1278.html": "Coefficient of Thermal Expansion",
                "https://www.engineeringtoolbox.com/material-properties-t_24.html": "Material Properties Overview",
            },
        },
        "piping": {
            "pages": {
                "https://www.engineeringtoolbox.com/nominal-pipe-sizes-d_42.html": "Nominal Pipe Sizes",
                "https://www.engineeringtoolbox.com/steel-pipes-dimensions-d_43.html": "Steel Pipe Dimensions",
                "https://www.engineeringtoolbox.com/pvc-cpvc-pipes-dimensions-d_470.html": "PVC and CPVC Pipe Dimensions",
                "https://www.engineeringtoolbox.com/copper-tube-sizes-d_44.html": "Copper Tube Sizes",
                "https://www.engineeringtoolbox.com/pipe-schedules-d_380.html": "Pipe Schedules",
                "https://www.engineeringtoolbox.com/ansi-steel-flanges-background-d_841.html": "ANSI Steel Flanges",
                "https://www.engineeringtoolbox.com/flange-bolt-pattern-d_2048.html": "Flange Bolt Patterns",
                "https://www.engineeringtoolbox.com/flanged-fittings-pressure-temperature-d_340.html": "Flanged Fittings - Pressure Temperature",
                "https://www.engineeringtoolbox.com/pipe-fittings-losses-d_1070.html": "Pipe Fittings Losses",
                "https://www.engineeringtoolbox.com/resistance-equivalent-length-d_192.html": "Resistance and Equivalent Length of Fittings",
                "https://www.engineeringtoolbox.com/pipe-expansion-joints-d_463.html": "Pipe Expansion Joints",
                "https://www.engineeringtoolbox.com/pipe-support-spacing-d_481.html": "Pipe Support Spacing",
                "https://www.engineeringtoolbox.com/pipe-insulation-thickness-d_1227.html": "Pipe Insulation Thickness",
                "https://www.engineeringtoolbox.com/thermal-expansion-pipes-d_275.html": "Thermal Expansion of Pipes",
                "https://www.engineeringtoolbox.com/pipe-color-codes-d_626.html": "Pipe Color Codes",
                "https://www.engineeringtoolbox.com/gate-valve-d_483.html": "Gate Valves",
                "https://www.engineeringtoolbox.com/globe-valve-d_484.html": "Globe Valves",
                "https://www.engineeringtoolbox.com/ball-valve-d_485.html": "Ball Valves",
                "https://www.engineeringtoolbox.com/butterfly-valve-d_486.html": "Butterfly Valves",
            },
        },
        "structural": {
            "pages": {
                "https://www.engineeringtoolbox.com/beam-stress-deflection-d_1312.html": "Beam Stress and Deflection",
                "https://www.engineeringtoolbox.com/beam-loads-d_702.html": "Beam Loads",
                "https://www.engineeringtoolbox.com/stress-strain-d_950.html": "Stress and Strain",
                "https://www.engineeringtoolbox.com/area-moment-inertia-d_1328.html": "Area Moment of Inertia",
                "https://www.engineeringtoolbox.com/section-modulus-d_1334.html": "Section Modulus",
                "https://www.engineeringtoolbox.com/euler-column-formula-d_1813.html": "Euler Column Formula",
                "https://www.engineeringtoolbox.com/w-steel-beams-d_1320.html": "W Steel Beams",
                "https://www.engineeringtoolbox.com/american-wide-flange-steel-beams-d_1318.html": "American Wide Flange Steel Beams",
                "https://www.engineeringtoolbox.com/steel-channels-american-standard-d_1322.html": "Steel Channels - American Standard",
                "https://www.engineeringtoolbox.com/steel-angles-d_1323.html": "Steel Angles",
                "https://www.engineeringtoolbox.com/structural-steel-hss-d_1650.html": "Structural Steel HSS",
                "https://www.engineeringtoolbox.com/floor-live-loads-d_1607.html": "Floor Live Loads",
                "https://www.engineeringtoolbox.com/wind-load-d_1620.html": "Wind Load",
                "https://www.engineeringtoolbox.com/snow-load-d_1621.html": "Snow Load",
                "https://www.engineeringtoolbox.com/bolts-tensile-proof-loads-d_2055.html": "Bolts - Tensile and Proof Loads",
                "https://www.engineeringtoolbox.com/bolt-torque-d_2058.html": "Bolt Torque",
            },
        },
        "hydraulics": {
            "pages": {
                "https://www.engineeringtoolbox.com/hydraulic-systems-d_224.html": "Hydraulic Systems",
                "https://www.engineeringtoolbox.com/hydraulic-force-d_1720.html": "Hydraulic Force",
                "https://www.engineeringtoolbox.com/hydraulic-cylinders-d_1695.html": "Hydraulic Cylinders",
                "https://www.engineeringtoolbox.com/hydraulic-pumps-d_1694.html": "Hydraulic Pumps",
                "https://www.engineeringtoolbox.com/hydraulic-accumulators-d_1719.html": "Hydraulic Accumulators",
                "https://www.engineeringtoolbox.com/hydraulic-fluids-d_1696.html": "Hydraulic Fluids",
                "https://www.engineeringtoolbox.com/hydraulic-hose-d_1698.html": "Hydraulic Hose",
                "https://www.engineeringtoolbox.com/hydraulic-seals-d_1699.html": "Hydraulic Seals",
                "https://www.engineeringtoolbox.com/pascals-law-d_1460.html": "Pascal's Law",
                "https://www.engineeringtoolbox.com/hydrostatic-pressure-d_1294.html": "Hydrostatic Pressure",
                "https://www.engineeringtoolbox.com/buoyancy-d_1339.html": "Buoyancy",
            },
        },
        "unit-conversion": {
            "pages": {
                "https://www.engineeringtoolbox.com/si-unit-system-d_30.html": "SI Unit System",
                "https://www.engineeringtoolbox.com/length-units-d_1702.html": "Length Units",
                "https://www.engineeringtoolbox.com/area-units-d_1704.html": "Area Units",
                "https://www.engineeringtoolbox.com/volume-units-d_1706.html": "Volume Units",
                "https://www.engineeringtoolbox.com/mass-weight-units-d_1707.html": "Mass and Weight Units",
                "https://www.engineeringtoolbox.com/force-units-d_1708.html": "Force Units",
                "https://www.engineeringtoolbox.com/pressure-units-d_11.html": "Pressure Units",
                "https://www.engineeringtoolbox.com/temperature-units-d_1709.html": "Temperature Units",
                "https://www.engineeringtoolbox.com/energy-work-d_1867.html": "Energy and Work Units",
                "https://www.engineeringtoolbox.com/power-units-d_1710.html": "Power Units",
                "https://www.engineeringtoolbox.com/flow-units-d_1712.html": "Flow Units",
                "https://www.engineeringtoolbox.com/velocity-units-d_1714.html": "Velocity Units",
                "https://www.engineeringtoolbox.com/conversion-factors-d_702.html": "Conversion Factors",
                "https://www.engineeringtoolbox.com/temperature-conversion-d_63.html": "Temperature Conversion",
                "https://www.engineeringtoolbox.com/pressure-conversion-d_64.html": "Pressure Conversion",
            },
        },
        "water-systems": {
            "pages": {
                "https://www.engineeringtoolbox.com/water-supply-d_46.html": "Water Supply Systems",
                "https://www.engineeringtoolbox.com/water-demand-d_1181.html": "Water Demand",
                "https://www.engineeringtoolbox.com/water-storage-tanks-d_483.html": "Water Storage Tanks",
                "https://www.engineeringtoolbox.com/water-distribution-d_47.html": "Water Distribution",
                "https://www.engineeringtoolbox.com/sewage-systems-d_68.html": "Sewage Systems",
                "https://www.engineeringtoolbox.com/sewage-pipe-size-d_1207.html": "Sewage Pipe Sizing",
                "https://www.engineeringtoolbox.com/water-treatment-d_70.html": "Water Treatment",
                "https://www.engineeringtoolbox.com/water-quality-d_601.html": "Water Quality",
                "https://www.engineeringtoolbox.com/water-hardness-d_1206.html": "Water Hardness",
                "https://www.engineeringtoolbox.com/fire-sprinkler-systems-d_94.html": "Fire Sprinkler Systems",
                "https://www.engineeringtoolbox.com/fire-hydrant-flow-d_1780.html": "Fire Hydrant Flow",
                "https://www.engineeringtoolbox.com/plumbing-fixtures-d_476.html": "Plumbing Fixtures",
                "https://www.engineeringtoolbox.com/water-pipe-dimensions-d_532.html": "Water Pipe Dimensions",
                "https://www.engineeringtoolbox.com/hot-water-systems-d_49.html": "Hot Water Systems",
            },
        },
        "acoustics": {
            "pages": {
                "https://www.engineeringtoolbox.com/decibel-d_59.html": "Decibel (dB)",
                "https://www.engineeringtoolbox.com/sound-level-d_58.html": "Sound Level",
                "https://www.engineeringtoolbox.com/noise-sources-d_62.html": "Noise Sources",
                "https://www.engineeringtoolbox.com/sound-power-level-d_58.html": "Sound Power Level",
                "https://www.engineeringtoolbox.com/noise-reduction-d_348.html": "Noise Reduction",
                "https://www.engineeringtoolbox.com/noise-control-d_59.html": "Noise Control",
                "https://www.engineeringtoolbox.com/room-acoustics-d_61.html": "Room Acoustics",
                "https://www.engineeringtoolbox.com/reverberation-time-d_472.html": "Reverberation Time",
                "https://www.engineeringtoolbox.com/sound-transmission-class-d_349.html": "Sound Transmission Class (STC)",
                "https://www.engineeringtoolbox.com/sound-absorption-coefficients-d_714.html": "Sound Absorption Coefficients",
                "https://www.engineeringtoolbox.com/noise-criteria-nc-d_725.html": "Noise Criteria (NC)",
                "https://www.engineeringtoolbox.com/speed-sound-d_82.html": "Speed of Sound",
            },
        },
        "gases": {
            "pages": {
                "https://www.engineeringtoolbox.com/ideal-gas-law-d_157.html": "Ideal Gas Law",
                "https://www.engineeringtoolbox.com/gas-laws-d_1426.html": "Gas Laws",
                "https://www.engineeringtoolbox.com/gas-density-d_158.html": "Gas Density",
                "https://www.engineeringtoolbox.com/specific-heat-ratio-d_608.html": "Specific Heat Ratio",
                "https://www.engineeringtoolbox.com/molecular-weight-gas-vapor-d_1156.html": "Molecular Weight of Gases",
                "https://www.engineeringtoolbox.com/gas-viscosity-d_156.html": "Gas Viscosity",
                "https://www.engineeringtoolbox.com/compressed-air-d_199.html": "Compressed Air Overview",
                "https://www.engineeringtoolbox.com/compressed-air-pipe-line-d_614.html": "Compressed Air Pipe Lines",
                "https://www.engineeringtoolbox.com/compressed-air-pressure-drop-d_795.html": "Compressed Air Pressure Drop",
                "https://www.engineeringtoolbox.com/compressed-air-storage-d_838.html": "Compressed Air Storage",
                "https://www.engineeringtoolbox.com/natural-gas-d_1127.html": "Natural Gas Properties",
                "https://www.engineeringtoolbox.com/methane-d_1420.html": "Methane Properties",
                "https://www.engineeringtoolbox.com/nitrogen-d_1421.html": "Nitrogen Properties",
                "https://www.engineeringtoolbox.com/oxygen-d_1422.html": "Oxygen Properties",
                "https://www.engineeringtoolbox.com/carbon-dioxide-d_1000.html": "Carbon Dioxide Properties",
                "https://www.engineeringtoolbox.com/hydrogen-d_1419.html": "Hydrogen Properties",
                "https://www.engineeringtoolbox.com/helium-d_1418.html": "Helium Properties",
                "https://www.engineeringtoolbox.com/argon-d_1413.html": "Argon Properties",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"engineering-toolbox-{source_key}" if source_key else "engineering-toolbox"
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
            for suffix in [' - Engineering ToolBox']:
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
                        "category": f"engineering-toolbox-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)

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
            self.log.info(f"=== Scraping engineering-toolbox/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    EngineeringToolboxScraper(base, source_key).run()
