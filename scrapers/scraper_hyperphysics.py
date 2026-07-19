#!/usr/bin/env python3
"""HyperPhysics documentation scraper.

Covers:
  - Classical mechanics (Newton's laws, energy, momentum, rotation, fluids)
  - Waves and sound (wave types, harmonics, Doppler, acoustics)
  - Thermodynamics (heat, entropy, gas laws, engines)
  - Electricity and magnetism (circuits, fields, Maxwell's equations)
  - Light and optics (lenses, mirrors, diffraction, polarization)
  - Relativity (special and general)
  - Quantum mechanics (wave functions, uncertainty, atomic structure)
  - Nuclear and particle physics (decay, fission, fusion, Standard Model)
  - Astrophysics and cosmology (stellar evolution, Big Bang, dark matter)
  - Condensed matter (band theory, semiconductors, superconductivity)
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper

HP = "http://hyperphysics.phy-astr.gsu.edu/hbase"


class HyperPhysicsScraper(BaseScraper):
    """Scrape HyperPhysics physics encyclopaedia pages."""

    SOURCES = {
        "mechanics": {
            "pages": {
                f"{HP}/Newt.html": "Newton's Laws",
                f"{HP}/mot.html": "Motion Concepts",
                f"{HP}/vect.html": "Vectors",
                f"{HP}/vel2.html": "Velocity",
                f"{HP}/acc.html": "Acceleration",
                f"{HP}/proj.html": "Projectile Motion",
                f"{HP}/N2.html": "Newton's Second Law",
                f"{HP}/N3.html": "Newton's Third Law",
                f"{HP}/frict.html": "Friction",
                f"{HP}/incpl.html": "Inclined Plane",
                f"{HP}/work.html": "Work",
                f"{HP}/encon.html": "Energy Conservation",
                f"{HP}/ke.html": "Kinetic Energy",
                f"{HP}/pegrav.html": "Gravitational Potential Energy",
                f"{HP}/pow.html": "Power",
                f"{HP}/mom.html": "Momentum",
                f"{HP}/impulse.html": "Impulse",
                f"{HP}/col.html": "Collisions",
                f"{HP}/elacol.html": "Elastic Collisions",
                f"{HP}/cm.html": "Center of Mass",
                f"{HP}/rotq.html": "Rotation Concepts",
                f"{HP}/torq.html": "Torque",
                f"{HP}/mi.html": "Moment of Inertia",
                f"{HP}/amom.html": "Angular Momentum",
                f"{HP}/rotke.html": "Rotational Kinetic Energy",
                f"{HP}/grav.html": "Gravitation",
                f"{HP}/orbv.html": "Orbital Velocity",
                f"{HP}/kepler.html": "Kepler's Laws",
                f"{HP}/tide.html": "Tides",
                f"{HP}/pflu.html": "Fluid Pressure",
                f"{HP}/pasc.html": "Pascal's Principle",
                f"{HP}/pbuoy.html": "Buoyancy",
                f"{HP}/pfric.html": "Viscosity",
                f"{HP}/bern.html": "Bernoulli's Equation",
                f"{HP}/shm.html": "Simple Harmonic Motion",
                f"{HP}/pend.html": "Pendulum",
                f"{HP}/shm2.html": "SHM Applications",
                f"{HP}/resf.html": "Resonance",
                f"{HP}/hooke.html": "Hooke's Law",
                f"{HP}/elast.html": "Elasticity",
                f"{HP}/press.html": "Pressure",
            },
        },
        "waves": {
            "pages": {
                f"{HP}/Waves/wavsol.html": "Wave Equation",
                f"{HP}/Waves/wavtyp.html": "Wave Types",
                f"{HP}/Waves/standw.html": "Standing Waves",
                f"{HP}/Waves/superp.html": "Superposition",
                f"{HP}/Waves/string.html": "String Waves",
                f"{HP}/Waves/funhar.html": "Harmonics",
                f"{HP}/Waves/imgwav.html": "Interference",
            },
        },
        "sound": {
            "pages": {
                f"{HP}/Sound/soucon.html": "Sound Concepts",
                f"{HP}/Sound/souspe.html": "Speed of Sound",
                f"{HP}/Sound/souint.html": "Sound Intensity",
                f"{HP}/Sound/db.html": "Decibels",
                f"{HP}/Sound/dopple.html": "Doppler Effect",
                f"{HP}/Sound/rescon.html": "Resonance",
                f"{HP}/Sound/standw.html": "Standing Waves (Sound)",
                f"{HP}/Sound/beat.html": "Beats",
                f"{HP}/Sound/traject.html": "Sound Trajectories",
                f"{HP}/Music/musins.html": "Musical Instruments",
                f"{HP}/Music/mussca.html": "Musical Scales",
            },
        },
        "thermo": {
            "pages": {
                f"{HP}/thermo/temper.html": "Temperature",
                f"{HP}/thermo/therm.html": "Thermometers",
                f"{HP}/thermo/heat.html": "Heat",
                f"{HP}/thermo/spht.html": "Specific Heat",
                f"{HP}/thermo/phase.html": "Phase Changes",
                f"{HP}/thermo/heatra.html": "Heat Transfer",
                f"{HP}/thermo/conde.html": "Conduction",
                f"{HP}/thermo/convec.html": "Convection",
                f"{HP}/thermo/stefan.html": "Stefan-Boltzmann",
                f"{HP}/thermo/firlaw.html": "First Law of Thermodynamics",
                f"{HP}/thermo/seclaw.html": "Second Law of Thermodynamics",
                f"{HP}/thermo/thrlw.html": "Third Law of Thermodynamics",
                f"{HP}/thermo/entrop.html": "Entropy",
                f"{HP}/thermo/inteng.html": "Internal Energy",
                f"{HP}/Kinetic/kinthe.html": "Kinetic Theory",
                f"{HP}/Kinetic/idegas.html": "Ideal Gas Law",
                f"{HP}/Kinetic/molvel.html": "Molecular Velocities",
                f"{HP}/thermo/carnot.html": "Carnot Cycle",
                f"{HP}/thermo/heateng.html": "Heat Engines",
                f"{HP}/thermo/refrig.html": "Refrigerators",
                f"{HP}/thermo/thexp.html": "Thermal Expansion",
                f"{HP}/thermo/pvdiag.html": "PV Diagrams",
                f"{HP}/thermo/arone.html": "Adiabatic Process",
                f"{HP}/thermo/isoth.html": "Isothermal Process",
            },
        },
        "electric": {
            "pages": {
                f"{HP}/electric/elecur.html": "Electric Current",
                f"{HP}/electric/ohmlaw.html": "Ohm's Law",
                f"{HP}/electric/resis.html": "Resistance",
                f"{HP}/electric/elepow.html": "Electric Power",
                f"{HP}/electric/elefie.html": "Electric Field",
                f"{HP}/electric/elefor.html": "Coulomb's Law",
                f"{HP}/electric/gaulaw.html": "Gauss's Law",
                f"{HP}/electric/potpoi.html": "Electric Potential",
                f"{HP}/electric/capac.html": "Capacitance",
                f"{HP}/electric/pplate.html": "Parallel Plates",
                f"{HP}/electric/serpar.html": "Series and Parallel Circuits",
                f"{HP}/electric/dccirc.html": "DC Circuits",
                f"{HP}/electric/kirchh.html": "Kirchhoff's Rules",
                f"{HP}/electric/emf.html": "EMF",
                f"{HP}/electric/rcd.html": "RC Circuits",
                f"{HP}/magnetic/magfor.html": "Magnetic Force",
                f"{HP}/magnetic/magfie.html": "Magnetic Field",
                f"{HP}/magnetic/biosav.html": "Biot-Savart Law",
                f"{HP}/magnetic/amplaw.html": "Ampere's Law",
                f"{HP}/magnetic/solenoid.html": "Solenoid",
                f"{HP}/magnetic/induc.html": "Electromagnetic Induction",
                f"{HP}/magnetic/farlaw.html": "Faraday's Law",
                f"{HP}/magnetic/lenz.html": "Lenz's Law",
                f"{HP}/electric/intic.html": "Inductance",
                f"{HP}/electric/rlcser.html": "RLC Circuits",
                f"{HP}/electric/impcom.html": "Impedance",
                f"{HP}/electric/imgac.html": "AC Circuits",
                f"{HP}/electric/maxeq.html": "Maxwell's Equations",
                f"{HP}/Waves/emwv.html": "Electromagnetic Waves",
                f"{HP}/ems1.html": "Electromagnetic Spectrum",
                f"{HP}/electric/dielet.html": "Dielectrics",
                f"{HP}/electric/elewor.html": "Electric Work",
            },
        },
        "light": {
            "pages": {
                f"{HP}/geoopt/lenscon.html": "Lenses",
                f"{HP}/geoopt/mircon.html": "Mirrors",
                f"{HP}/geoopt/refr.html": "Refraction",
                f"{HP}/geoopt/reflect.html": "Reflection",
                f"{HP}/geoopt/snell.html": "Snell's Law",
                f"{HP}/geoopt/totint.html": "Total Internal Reflection",
                f"{HP}/geoopt/lenseq.html": "Lens Equation",
                f"{HP}/geoopt/mireq.html": "Mirror Equation",
                f"{HP}/geoopt/thinl.html": "Thin Lenses",
                f"{HP}/phyopt/interfcon.html": "Interference",
                f"{HP}/phyopt/youngs.html": "Young's Double Slit",
                f"{HP}/phyopt/difcon.html": "Diffraction Concepts",
                f"{HP}/phyopt/sinslit.html": "Single Slit Diffraction",
                f"{HP}/phyopt/grating.html": "Diffraction Grating",
                f"{HP}/phyopt/polcon.html": "Polarization",
                f"{HP}/phyopt/brewster.html": "Brewster's Angle",
                f"{HP}/phyopt/thinfilm.html": "Thin Film Interference",
                f"{HP}/optmod/fibopt.html": "Fiber Optics",
                f"{HP}/optmod/lascn.html": "Lasers",
                f"{HP}/vision/colcon.html": "Color",
                f"{HP}/vision/cie.html": "CIE Color",
                f"{HP}/vision/rodcone.html": "Rods and Cones",
                f"{HP}/geoopt/disper.html": "Dispersion",
                f"{HP}/geoopt/prism.html": "Prisms",
                f"{HP}/geoopt/telcon.html": "Telescopes",
                f"{HP}/geoopt/miccon.html": "Microscopes",
                f"{HP}/vision/bright.html": "Photometry",
            },
        },
        "relativ": {
            "pages": {
                f"{HP}/Relativ/relcon.html": "Relativity Concepts",
                f"{HP}/Relativ/ltrans.html": "Lorentz Transformation",
                f"{HP}/Relativ/tdil.html": "Time Dilation",
                f"{HP}/Relativ/lcont.html": "Length Contraction",
                f"{HP}/Relativ/relvel.html": "Relativistic Velocity",
                f"{HP}/Relativ/relmom.html": "Relativistic Momentum",
                f"{HP}/Relativ/releng.html": "Relativistic Energy",
                f"{HP}/Relativ/emc2.html": "E=mc2",
                f"{HP}/Relativ/twpar.html": "Twin Paradox",
                f"{HP}/Relativ/gravi.html": "General Relativity",
                f"{HP}/Relativ/grel.html": "General Relativity Concepts",
                f"{HP}/Relativ/gratim.html": "Gravitational Time Dilation",
                f"{HP}/Relativ/grelpr.html": "Equivalence Principle",
                f"{HP}/Relativ/bhole.html": "Black Holes",
                f"{HP}/Relativ/grvwav.html": "Gravitational Waves",
            },
        },
        "quantum": {
            "pages": {
                f"{HP}/quantum/quacon.html": "Quantum Concepts",
                f"{HP}/quantum/wvpart.html": "Wave-Particle Duality",
                f"{HP}/quantum/debrog.html": "de Broglie Wavelength",
                f"{HP}/quantum/uncer.html": "Uncertainty Principle",
                f"{HP}/quantum/schr.html": "Schrodinger Equation",
                f"{HP}/quantum/pbox.html": "Particle in a Box",
                f"{HP}/quantum/hosc.html": "Quantum Harmonic Oscillator",
                f"{HP}/quantum/barr.html": "Quantum Tunneling",
                f"{HP}/quantum/hydwf.html": "Hydrogen Wave Functions",
                f"{HP}/quantum/hydsch.html": "Hydrogen Schrodinger",
                f"{HP}/quantum/qnumb.html": "Quantum Numbers",
                f"{HP}/spin.html": "Electron Spin",
                f"{HP}/quantum/paulie.html": "Pauli Exclusion Principle",
                f"{HP}/quantum/atstruc.html": "Atomic Structure",
                f"{HP}/quantum/phtoel.html": "Photoelectric Effect",
                f"{HP}/quantum/comptint.html": "Compton Scattering",
                f"{HP}/quantum/bragg.html": "Bragg Diffraction",
                f"{HP}/quantum/planck.html": "Planck's Law",
                f"{HP}/mod6.html": "Bohr Model",
                f"{HP}/quantum/spectr.html": "Atomic Spectra",
                f"{HP}/quantum/Zeeman.html": "Zeeman Effect",
                f"{HP}/quantum/stark.html": "Stark Effect",
                f"{HP}/quantum/ferro.html": "Fermi-Dirac Statistics",
                f"{HP}/quantum/disbe.html": "Bose-Einstein Distribution",
                f"{HP}/quantum/disfd.html": "Fermi-Dirac Distribution",
            },
        },
        "nuclear": {
            "pages": {
                f"{HP}/Nuclear/nuccon.html": "Nuclear Concepts",
                f"{HP}/Nuclear/nucstr.html": "Nuclear Structure",
                f"{HP}/Nuclear/nucbin.html": "Binding Energy",
                f"{HP}/Nuclear/halfli2.html": "Half-Life",
                f"{HP}/Nuclear/radact.html": "Radioactivity",
                f"{HP}/Nuclear/alpdec.html": "Alpha Decay",
                f"{HP}/Nuclear/beta.html": "Beta Decay",
                f"{HP}/Nuclear/gamdec.html": "Gamma Decay",
                f"{HP}/Nuclear/fession.html": "Fission",
                f"{HP}/Nuclear/fusion.html": "Fusion",
                f"{HP}/Nuclear/nucrea.html": "Nuclear Reactions",
                f"{HP}/Nuclear/radser.html": "Radioactive Series",
                f"{HP}/Nuclear/carbon.html": "Carbon Dating",
                f"{HP}/Nuclear/reactor.html": "Nuclear Reactor",
                f"{HP}/Nuclear/nucmas.html": "Nuclear Mass",
                f"{HP}/Nuclear/liqdrop.html": "Liquid Drop Model",
                f"{HP}/Nuclear/shell.html": "Shell Model",
                f"{HP}/Nuclear/radeff.html": "Radiation Effects",
                f"{HP}/Nuclear/radinv.html": "Radiation Units",
                f"{HP}/Particles/parcon.html": "Particle Concepts",
                f"{HP}/Particles/quark.html": "Quarks",
                f"{HP}/Particles/lepton.html": "Leptons",
                f"{HP}/Particles/hadron.html": "Hadrons",
                f"{HP}/Forces/funfor.html": "Fundamental Forces",
                f"{HP}/Particles/expar.html": "Exchange Particles",
                f"{HP}/Particles/stdmod.html": "Standard Model",
            },
        },
        "astro": {
            "pages": {
                f"{HP}/Astro/astcon.html": "Astrophysics Concepts",
                f"{HP}/Astro/herrus.html": "HR Diagram",
                f"{HP}/Astro/stelar.html": "Stellar Structure",
                f"{HP}/Astro/strevl.html": "Stellar Evolution",
                f"{HP}/Astro/whdwf.html": "White Dwarfs",
                f"{HP}/Astro/neutst.html": "Neutron Stars",
                f"{HP}/Astro/blkhol.html": "Black Holes (Astrophysics)",
                f"{HP}/Astro/supnova.html": "Supernovae",
                f"{HP}/Astro/cosmo.html": "Cosmology",
                f"{HP}/Astro/hubble.html": "Hubble Law",
                f"{HP}/Astro/bbang.html": "Big Bang",
                f"{HP}/Astro/darmat.html": "Dark Matter",
                f"{HP}/Astro/dareng.html": "Dark Energy",
                f"{HP}/Astro/redshf.html": "Redshift",
                f"{HP}/Astro/cmbr.html": "CMB Radiation",
                f"{HP}/Astro/solsys.html": "Solar System",
                f"{HP}/Astro/suntic.html": "Sun",
                f"{HP}/Astro/galtic.html": "Galaxies",
                f"{HP}/Astro/milky.html": "Milky Way",
                f"{HP}/Astro/parallax.html": "Parallax",
                f"{HP}/Astro/magtic.html": "Magnitudes",
            },
        },
        "solids": {
            "pages": {
                f"{HP}/Solids/band.html": "Band Theory",
                f"{HP}/Solids/semipr.html": "Semiconductors",
                f"{HP}/Solids/intrin.html": "Intrinsic Semiconductors",
                f"{HP}/Solids/dope.html": "Doping",
                f"{HP}/Solids/pnjun.html": "PN Junction",
                f"{HP}/Solids/diod.html": "Diodes",
                f"{HP}/Solids/trans.html": "Transistors",
                f"{HP}/Solids/supcon.html": "Superconductivity",
                f"{HP}/Solids/bcs.html": "BCS Theory",
                f"{HP}/Solids/crystal.html": "Crystal Structure",
                f"{HP}/Solids/lattice.html": "Crystal Lattices",
                f"{HP}/Solids/xray.html": "X-Ray Diffraction",
                f"{HP}/Solids/metal.html": "Metals",
                f"{HP}/Solids/fermi.html": "Fermi Energy",
                f"{HP}/Solids/magnet.html": "Magnetism in Solids",
                f"{HP}/Solids/ferro.html": "Ferromagnetism",
                f"{HP}/Solids/piezo.html": "Piezoelectricity",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"hyperphysics-{source_key}" if source_key else "hyperphysics"
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
            for suffix in [' - HyperPhysics', ' - Encyclopaedia of Physics',
                           ' HyperPhysics']:
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
                        "category": f"hyperphysics-{source_key}",
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
            self.log.info(f"=== Scraping hyperphysics/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    HyperPhysicsScraper(base, source_key).run()
