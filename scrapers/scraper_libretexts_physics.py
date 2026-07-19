#!/usr/bin/env python3
"""Physics LibreTexts scraper.

Covers:
  - University Physics I, II, III (OpenStax)
  - Classical Mechanics, Quantum Mechanics, Relativity
  - Nuclear & Particle Physics, Astronomy & Cosmology
  - Waves & Acoustics, Optics, Modern Physics
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class LibreTextsPhysicsScraper(BaseScraper):
    """Scrape Physics LibreTexts content."""

    # Base paths for University Physics (OpenStax)
    _UP1 = ("https://phys.libretexts.org/Bookshelves/University_Physics/"
            "University_Physics_(OpenStax)/"
            "Book%3A_University_Physics_I_-_Mechanics_Sound_Oscillations_and_Waves_(OpenStax)")
    _UP2 = ("https://phys.libretexts.org/Bookshelves/University_Physics/"
            "University_Physics_(OpenStax)/"
            "University_Physics_II_-_Thermodynamics_Electricity_and_Magnetism_(OpenStax)")
    _UP3 = ("https://phys.libretexts.org/Bookshelves/University_Physics/"
            "University_Physics_(OpenStax)/"
            "University_Physics_III_-_Optics_and_Modern_Physics_(OpenStax)")

    # Base paths for additional textbooks
    _CM_CLINE = ("https://phys.libretexts.org/Bookshelves/Classical_Mechanics/"
                 "Variational_Principles_in_Classical_Mechanics_(Cline)")
    _CM_DOUR = ("https://phys.libretexts.org/Bookshelves/Classical_Mechanics/"
                "Classical_Mechanics_(Dourmashkin)")
    _QM_FITZ = ("https://phys.libretexts.org/Bookshelves/Quantum_Mechanics/"
                "Introductory_Quantum_Mechanics_(Fitzpatrick)")
    _SR_CROW = "https://phys.libretexts.org/Bookshelves/Relativity/Special_Relativity_(Crowell)"
    _GR_CROW = "https://phys.libretexts.org/Bookshelves/Relativity/General_Relativity_(Crowell)"
    _NP_CAPP = ("https://phys.libretexts.org/Bookshelves/Nuclear_and_Particle_Physics/"
                "Introduction_to_Applied_Nuclear_Physics_(Cappellaro)")
    _NP_WAL = ("https://phys.libretexts.org/Bookshelves/Nuclear_and_Particle_Physics/"
               "Nuclear_and_Particle_Physics_(Walet)")
    _AS_OPEN = ("https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology/"
                "Astronomy_2e_(OpenStax)")
    _WV_GOER = ("https://phys.libretexts.org/Bookshelves/Waves_and_Acoustics/"
                "The_Physics_of_Waves_(Goergi)")
    _OP_GEO = "https://phys.libretexts.org/Bookshelves/Optics/Geometric_Optics_(Tatum)"
    _OP_PHY = "https://phys.libretexts.org/Bookshelves/Optics/Physical_Optics_(Tatum)"
    _MP_SPIR = ("https://phys.libretexts.org/Bookshelves/Modern_Physics/"
                "Spiral_Modern_Physics_(D'Alessandris)")

    SOURCES = {
        # ── University Physics I: Mechanics, Sound, Oscillations & Waves ──
        "mechanics": {
            "pages": {
                f"{_UP1}/01%3A_Units_and_Measurement": "Units and Measurement",
                f"{_UP1}/02%3A_Vectors": "Vectors",
                f"{_UP1}/03%3A_Motion_Along_a_Straight_Line": "Motion Along a Straight Line",
                f"{_UP1}/04%3A_Motion_in_Two_and_Three_Dimensions": "Motion in Two and Three Dimensions",
                f"{_UP1}/05%3A_Newton's_Laws_of_Motion": "Newton's Laws of Motion",
                f"{_UP1}/06%3A_Applications_of_Newton's_Laws": "Applications of Newton's Laws",
                f"{_UP1}/07%3A_Work_and_Kinetic_Energy": "Work and Kinetic Energy",
                f"{_UP1}/08%3A_Potential_Energy_and_Conservation_of_Energy": "Potential Energy and Conservation of Energy",
                f"{_UP1}/09%3A_Linear_Momentum_and_Collisions": "Linear Momentum and Collisions",
                f"{_UP1}/10%3A_Fixed-Axis_Rotation__Introduction": "Fixed-Axis Rotation",
                f"{_UP1}/11%3A__Angular_Momentum": "Angular Momentum",
                f"{_UP1}/12%3A_Static_Equilibrium_and_Elasticity": "Static Equilibrium and Elasticity",
                f"{_UP1}/13%3A_Gravitation": "Gravitation",
                f"{_UP1}/14%3A_Fluid_Mechanics": "Fluid Mechanics",
                f"{_UP1}/15%3A_Oscillations": "Oscillations",
                f"{_UP1}/16%3A_Waves": "Waves",
                f"{_UP1}/17%3A_Sound": "Sound",
            },
        },
        # ── University Physics II: Thermodynamics, Electricity & Magnetism ──
        "thermo-em": {
            "pages": {
                f"{_UP2}/01%3A_Temperature_and_Heat": "Temperature and Heat",
                f"{_UP2}/02%3A_The_Kinetic_Theory_of_Gases": "The Kinetic Theory of Gases",
                f"{_UP2}/03%3A_The_First_Law_of_Thermodynamics": "The First Law of Thermodynamics",
                f"{_UP2}/04%3A_The_Second_Law_of_Thermodynamics": "The Second Law of Thermodynamics",
                f"{_UP2}/05%3A_Electric_Charges_and_Fields": "Electric Charges and Fields",
                f"{_UP2}/06%3A_Gauss's_Law": "Gauss's Law",
                f"{_UP2}/07%3A_Electric_Potential": "Electric Potential",
                f"{_UP2}/08%3A_Capacitance": "Capacitance",
                f"{_UP2}/09%3A_Current_and_Resistance": "Current and Resistance",
                f"{_UP2}/10%3A_Direct-Current_Circuits": "Direct-Current Circuits",
                f"{_UP2}/11%3A_Magnetic_Forces_and_Fields": "Magnetic Forces and Fields",
                f"{_UP2}/12%3A_Sources_of_Magnetic_Fields": "Sources of Magnetic Fields",
                f"{_UP2}/13%3A_Electromagnetic_Induction": "Electromagnetic Induction",
                f"{_UP2}/14%3A_Inductance": "Inductance",
                f"{_UP2}/15%3A_Alternating-Current_Circuits": "Alternating-Current Circuits",
                f"{_UP2}/16%3A_Electromagnetic_Waves": "Electromagnetic Waves",
            },
        },
        # ── University Physics III: Optics & Modern Physics ──
        "optics-modern": {
            "pages": {
                f"{_UP3}/01%3A_The_Nature_of_Light": "The Nature of Light",
                f"{_UP3}/02%3A_Geometric_Optics_and_Image_Formation": "Geometric Optics and Image Formation",
                f"{_UP3}/03%3A_Interference": "Interference",
                f"{_UP3}/04%3A_Diffraction": "Diffraction",
                f"{_UP3}/05%3A__Relativity": "Relativity",
                f"{_UP3}/06%3A_Photons_and_Matter_Waves": "Photons and Matter Waves",
                f"{_UP3}/07%3A_Quantum_Mechanics": "Quantum Mechanics",
                f"{_UP3}/08%3A_Atomic_Structure": "Atomic Structure",
                f"{_UP3}/09%3A_Condensed_Matter_Physics": "Condensed Matter Physics",
                f"{_UP3}/10%3A__Nuclear_Physics": "Nuclear Physics",
                f"{_UP3}/11%3A_Particle_Physics_and_Cosmology": "Particle Physics and Cosmology",
            },
        },
        # ── Classical Mechanics ──
        "classical-mechanics": {
            "pages": {
                # Bookshelf landing
                "https://phys.libretexts.org/Bookshelves/Classical_Mechanics": "Classical Mechanics Bookshelf",
                # Variational Principles in Classical Mechanics (Cline)
                f"{_CM_CLINE}": "Variational Principles in Classical Mechanics",
                f"{_CM_CLINE}/02%3A_Review_of_Newtonian_Mechanics": "Review of Newtonian Mechanics",
                f"{_CM_CLINE}/03%3A_Linear_Oscillators": "Linear Oscillators",
                f"{_CM_CLINE}/04%3A_Nonlinear_Systems_and_Chaos": "Nonlinear Systems and Chaos",
                f"{_CM_CLINE}/05%3A_Calculus_of_Variations": "Calculus of Variations",
                f"{_CM_CLINE}/06%3A_Lagrangian_Dynamics": "Lagrangian Dynamics",
                f"{_CM_CLINE}/07%3A_Symmetries_Invariance_and_the_Hamiltonian": "Symmetries, Invariance and the Hamiltonian",
                f"{_CM_CLINE}/08%3A_Hamiltonian_Mechanics": "Hamiltonian Mechanics",
                f"{_CM_CLINE}/09%3A_Hamilton's_Action_Principle": "Hamilton's Action Principle",
                f"{_CM_CLINE}/11%3A_Conservative_two-body_Central_Forces": "Conservative Two-Body Central Forces",
                f"{_CM_CLINE}/12%3A_Non-inertial_Reference_Frames": "Non-inertial Reference Frames",
                f"{_CM_CLINE}/13%3A_Rigid-body_Rotation": "Rigid-Body Rotation",
                f"{_CM_CLINE}/10%3A_Nonconservative_Systems": "Nonconservative Systems",
                f"{_CM_CLINE}/14%3A_Coupled_Linear_Oscillators": "Coupled Linear Oscillators",
                f"{_CM_CLINE}/15%3A_Advanced_Hamiltonian_Mechanics": "Advanced Hamiltonian Mechanics",
                f"{_CM_CLINE}/17%3A_Relativistic_Mechanics": "Relativistic Mechanics",
                # Classical Mechanics (Dourmashkin)
                f"{_CM_DOUR}": "Classical Mechanics (Dourmashkin)",
                f"{_CM_DOUR}/07%3A_Newtons_Laws_of_Motion": "Newton's Laws of Motion (Dourmashkin)",
                f"{_CM_DOUR}/13%3A_Energy_Kinetic_Energy_and_Work": "Energy, Kinetic Energy, and Work",
                f"{_CM_DOUR}/06%3A_Circular_Motion": "Circular Motion",
                f"{_CM_DOUR}/15%3A_Collision_Theory": "Collision Theory",
                f"{_CM_DOUR}/19%3A_Angular_Momentum": "Angular Momentum (Dourmashkin)",
                f"{_CM_DOUR}/25%3A_Celestial_Mechanics": "Celestial Mechanics",
                # Other textbooks
                "https://phys.libretexts.org/Bookshelves/Classical_Mechanics/Classical_Mechanics_(Tatum)": "Classical Mechanics (Tatum)",
                "https://phys.libretexts.org/Bookshelves/Classical_Mechanics/Graduate_Classical_Mechanics_(Fowler)": "Graduate Classical Mechanics (Fowler)",
                "https://phys.libretexts.org/Bookshelves/Classical_Mechanics/Essential_Graduate_Physics_-_Classical_Mechanics_(Likharev)": "Essential Graduate Physics - Classical Mechanics (Likharev)",
            },
        },
        # ── Quantum Mechanics ──
        "quantum": {
            "pages": {
                # Bookshelf landing
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics": "Quantum Mechanics Bookshelf",
                # Introductory Quantum Mechanics (Fitzpatrick)
                f"{_QM_FITZ}": "Introductory Quantum Mechanics (Fitzpatrick)",
                f"{_QM_FITZ}/02%3A_Wave-Particle_Duality": "Wave-Particle Duality",
                f"{_QM_FITZ}/03%3A_Fundamentals_of_Quantum_Mechanics": "Fundamentals of Quantum Mechanics",
                f"{_QM_FITZ}/04%3A_One-Dimensional_Potentials": "One-Dimensional Potentials",
                f"{_QM_FITZ}/05%3A_Multi-Particle_Systems": "Multi-Particle Systems",
                f"{_QM_FITZ}/06%3A_Three-Dimensional_Quantum_Mechanics": "Three-Dimensional Quantum Mechanics",
                f"{_QM_FITZ}/07%3A_Orbital_Angular_Momentum": "Orbital Angular Momentum",
                f"{_QM_FITZ}/08%3A_Central_Potentials": "Central Potentials",
                f"{_QM_FITZ}/09%3A_Spin_Angular_Momentum": "Spin Angular Momentum",
                f"{_QM_FITZ}/10%3A_Addition_of_Angular_Momentum": "Addition of Angular Momentum",
                f"{_QM_FITZ}/11%3A_Time-Independent_Perturbation_Theory": "Time-Independent Perturbation Theory",
                f"{_QM_FITZ}/12%3A_Time-Dependent_Perturbation_Theory": "Time-Dependent Perturbation Theory",
                f"{_QM_FITZ}/13%3A_Variational_Methods": "Variational Methods",
                f"{_QM_FITZ}/01%3A_Probability_Theory": "Probability Theory",
                f"{_QM_FITZ}/14%3A_Scattering_Theory": "Scattering Theory",
                # Other textbooks
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics/Quantum_Mechanics_(Fowler)": "Quantum Mechanics (Fowler)",
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics/Quantum_Mechanics_(Walet)": "Quantum Mechanics (Walet)",
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics/Quantum_Physics_(Ackland)": "Quantum Physics (Ackland)",
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics/Introduction_to_the_Physics_of_Atoms_Molecules_and_Photons_(Benedict)": "Physics of Atoms, Molecules and Photons (Benedict)",
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics/Advanced_Quantum_Mechanics_(Kok)": "Advanced Quantum Mechanics (Kok)",
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics/Quantum_Mechanics_III_(Chong)": "Quantum Mechanics III (Chong)",
                "https://phys.libretexts.org/Bookshelves/Quantum_Mechanics/Essential_Graduate_Physics_-_Quantum_Mechanics_(Likharev)": "Essential Graduate Physics - Quantum Mechanics (Likharev)",
            },
        },
        # ── Relativity ──
        "relativity": {
            "pages": {
                # Bookshelf landing
                "https://phys.libretexts.org/Bookshelves/Relativity": "Relativity Bookshelf",
                # Special Relativity (Crowell)
                f"{_SR_CROW}": "Special Relativity (Crowell)",
                f"{_SR_CROW}/01%3A_Spacetime": "Spacetime",
                f"{_SR_CROW}/02%3A_Foundations": "Foundations of Special Relativity",
                f"{_SR_CROW}/03%3A_Kinematics": "Relativistic Kinematics",
                f"{_SR_CROW}/04%3A_Dynamics": "Relativistic Dynamics",
                f"{_SR_CROW}/05%3A_Inertia": "Inertia",
                f"{_SR_CROW}/06%3A_Waves": "Waves and Relativity",
                f"{_SR_CROW}/08%3A_Rotation": "Rotation",
                f"{_SR_CROW}/10%3A_Electromagnetism": "Electromagnetism and Relativity",
                # General Relativity (Crowell)
                f"{_GR_CROW}": "General Relativity (Crowell)",
                f"{_GR_CROW}/01%3A_Geometric_Theory_of_Spacetime": "Geometric Theory of Spacetime",
                f"{_GR_CROW}/03%3A_Differential_Geometry": "Differential Geometry",
                f"{_GR_CROW}/05%3A_Curvature": "Curvature",
                f"{_GR_CROW}/06%3A_Vacuum_Solutions": "Vacuum Solutions",
                f"{_GR_CROW}/09%3A_Gravitational_Waves": "Gravitational Waves",
                # Other textbooks
                "https://phys.libretexts.org/Bookshelves/Relativity/Spacetime_Physics_(Taylor_and_Wheeler)": "Spacetime Physics (Taylor and Wheeler)",
                "https://phys.libretexts.org/Bookshelves/Relativity/Supplemental_Modules_(Relativity)": "Supplemental Modules (Relativity)",
                "https://phys.libretexts.org/Bookshelves/Relativity/Book%3A_Relativity_Lite_-_A_Pictorial_Translation_of_Einsteins_Theories_of_Motion_and_Gravity_(Straton)": "Relativity Lite (Straton)",
            },
        },
        # ── Nuclear and Particle Physics ──
        "nuclear": {
            "pages": {
                # Bookshelf landing
                "https://phys.libretexts.org/Bookshelves/Nuclear_and_Particle_Physics": "Nuclear and Particle Physics Bookshelf",
                # Introduction to Applied Nuclear Physics (Cappellaro)
                f"{_NP_CAPP}/01%3A_Introduction_to_Nuclear_Physics": "Introduction to Nuclear Physics",
                f"{_NP_CAPP}/02%3A_Introduction_to_Quantum_Mechanics": "Introduction to Quantum Mechanics (Nuclear)",
                f"{_NP_CAPP}/03%3A_Radioactive_Decay_Part_I": "Radioactive Decay Part I",
                f"{_NP_CAPP}/04%3A_Energy_Levels": "Energy Levels",
                f"{_NP_CAPP}/05%3A_Nuclear_Structure": "Nuclear Structure",
                f"{_NP_CAPP}/06%3A_Time_Evolution_in_Quantum_Mechanics": "Time Evolution in Quantum Mechanics",
                f"{_NP_CAPP}/07%3A_Radioactive_Decay_Part_II": "Radioactive Decay Part II",
                f"{_NP_CAPP}/08%3A_Applications_of_Nuclear_Science_(PDF_-_1.4MB)": "Applications of Nuclear Science",
                # Nuclear and Particle Physics (Walet)
                f"{_NP_WAL}/01%3A_A_History_of_Particle_Physics": "A History of Particle Physics",
                f"{_NP_WAL}/02%3A__Experimental_Tools": "Experimental Tools",
                f"{_NP_WAL}/03%3A_Nuclear_Masses": "Nuclear Masses",
                f"{_NP_WAL}/04%3A_Nuclear_Models": "Nuclear Models",
                f"{_NP_WAL}/05%3A_Basic_Concepts_of_Theoretical_Particle_Physics": "Basic Concepts of Theoretical Particle Physics",
                f"{_NP_WAL}/06%3A_The_Four_Fundamental_Forces": "The Four Fundamental Forces",
                f"{_NP_WAL}/07%3A_Symmetries_and_Particle_Physics": "Symmetries and Particle Physics",
                f"{_NP_WAL}/08%3A_Symmetries_of_the_theory_of_strong_interactions": "Symmetries of the Theory of Strong Interactions",
            },
        },
        # ── Astronomy & Cosmology ──
        "astro": {
            "pages": {
                # Bookshelf landing
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology": "Astronomy and Cosmology Bookshelf",
                # Astronomy 2e (OpenStax)
                f"{_AS_OPEN}/01%3A_Science_and_the_Universe_-_A_Brief_Tour": "Science and the Universe - A Brief Tour",
                f"{_AS_OPEN}/03%3A_Orbits_and_Gravity": "Orbits and Gravity",
                f"{_AS_OPEN}/05%3A_Radiation_and_Spectra": "Radiation and Spectra",
                f"{_AS_OPEN}/06%3A_Astronomical_Instruments": "Astronomical Instruments",
                f"{_AS_OPEN}/07%3A_Other_Worlds_-_An_Introduction_to_the_Solar_System": "Introduction to the Solar System",
                f"{_AS_OPEN}/08%3A_Earth_as_a_Planet": "Earth as a Planet",
                f"{_AS_OPEN}/09%3A_Cratered_Worlds": "Cratered Worlds",
                f"{_AS_OPEN}/11%3A_The_Giant_Planets": "The Giant Planets",
                f"{_AS_OPEN}/13%3A_Comets_and_Asteroids_-_Debris_of_the_Solar_System": "Comets and Asteroids",
                f"{_AS_OPEN}/15%3A_The_Sun-_A_Garden-Variety_Star": "The Sun - A Garden-Variety Star",
                f"{_AS_OPEN}/16%3A_The_Sun-_A_Nuclear_Powerhouse": "The Sun - A Nuclear Powerhouse",
                f"{_AS_OPEN}/17%3A_Analyzing_Starlight": "Analyzing Starlight",
                f"{_AS_OPEN}/20%3A_Between_the_Stars_-_Gas_and_Dust_in_Space": "Between the Stars - Gas and Dust in Space",
                f"{_AS_OPEN}/21%3A_The_Birth_of_Stars_and_the_Discovery_of_Planets_outside_the_Solar_System": "The Birth of Stars",
                f"{_AS_OPEN}/23%3A_The_Death_of_Stars": "The Death of Stars",
                f"{_AS_OPEN}/24%3A_Black_Holes_and_Curved_Spacetime": "Black Holes and Curved Spacetime",
                f"{_AS_OPEN}/25%3A_The_Milky_Way_Galaxy": "The Milky Way Galaxy",
                f"{_AS_OPEN}/22%3A_Stars_from_Adolescence_to_Old_Age": "Stars from Adolescence to Old Age",
                f"{_AS_OPEN}/26%3A_Galaxies": "Galaxies",
                f"{_AS_OPEN}/27%3A_Active_Galaxies_Quasars_and_Supermassive_Black_Holes": "Active Galaxies, Quasars, and Supermassive Black Holes",
                f"{_AS_OPEN}/29%3A_The_Big_Bang": "The Big Bang",
                f"{_AS_OPEN}/30%3A_Life_in_the_Universe": "Life in the Universe",
                # Other textbooks
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology/Cosmology_(Knox)": "Cosmology (Knox)",
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology/Big_Ideas_in_Cosmology_(Coble_et_al.)": "Big Ideas in Cosmology (Coble et al.)",
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology/Stellar_Atmospheres_(Tatum)": "Stellar Atmospheres (Tatum)",
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology/Celestial_Mechanics_(Tatum)": "Celestial Mechanics (Tatum)",
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology/The_Fundamentals_of_Stellar_Astrophysics_(Collins)": "Fundamentals of Stellar Astrophysics (Collins)",
                "https://phys.libretexts.org/Bookshelves/Astronomy__Cosmology/Astrobiology_(Fischer_Sheffield_Tan_and_Zhao)": "Astrobiology (Fischer, Sheffield, Tan and Zhao)",
            },
        },
        # ── Waves & Acoustics ──
        "waves": {
            "pages": {
                # Bookshelf landing
                "https://phys.libretexts.org/Bookshelves/Waves_and_Acoustics": "Waves and Acoustics Bookshelf",
                # The Physics of Waves (Goergi)
                f"{_WV_GOER}": "The Physics of Waves (Goergi)",
                f"{_WV_GOER}/01%3A_Harmonic_Oscillation": "Harmonic Oscillation",
                f"{_WV_GOER}/02%3A_Forced_Oscillation_and_Resonance": "Forced Oscillation and Resonance",
                f"{_WV_GOER}/03%3A_Normal_Modes": "Normal Modes",
                f"{_WV_GOER}/05%3A_Waves": "Waves",
                f"{_WV_GOER}/06%3A_Continuum_Limit_and_Fourier_Series": "Continuum Limit and Fourier Series",
                f"{_WV_GOER}/07%3A_Longitudinal_Oscillations_and_Sound": "Longitudinal Oscillations and Sound",
                f"{_WV_GOER}/08%3A_Traveling_Waves": "Traveling Waves",
                f"{_WV_GOER}/10%3A_Signals_and_Fourier_Analysis": "Signals and Fourier Analysis",
                f"{_WV_GOER}/12%3A_Polarization": "Polarization",
                f"{_WV_GOER}/13%3A_Interference_and_Diffraction": "Interference and Diffraction",
                f"{_WV_GOER}/14%3A_Shocks_and_Wakes": "Shocks and Wakes",
                # Other textbooks
                "https://phys.libretexts.org/Bookshelves/Waves_and_Acoustics/Sound_-_An_Interactive_eBook_(Forinash_and_Christian)": "Sound - An Interactive eBook (Forinash and Christian)",
                "https://phys.libretexts.org/Bookshelves/Waves_and_Acoustics/Understanding_Sound_(Abbot)": "Understanding Sound (Abbot)",
                "https://phys.libretexts.org/Bookshelves/Waves_and_Acoustics/Waves%3A_An_Interactive_Tutorial_(Forinash_and_Christian)": "Waves: An Interactive Tutorial (Forinash and Christian)",
                "https://phys.libretexts.org/Bookshelves/Waves_and_Acoustics/Acoustics": "Acoustics",
            },
        },
        # ── Optics ──
        "optics": {
            "pages": {
                # Bookshelf landing
                "https://phys.libretexts.org/Bookshelves/Optics": "Optics Bookshelf",
                # Geometric Optics (Tatum)
                f"{_OP_GEO}": "Geometric Optics (Tatum)",
                f"{_OP_GEO}/01%3A_Reflection_and_Refraction": "Reflection and Refraction",
                f"{_OP_GEO}/02%3A_Lens_and_Mirror_Calculations": "Lens and Mirror Calculations",
                f"{_OP_GEO}/03%3A_Optical_Instruments": "Optical Instruments",
                f"{_OP_GEO}/04%3A_Optical_Aberrations": "Optical Aberrations",
                # Physical Optics (Tatum)
                f"{_OP_PHY}": "Physical Optics (Tatum)",
                f"{_OP_PHY}/01%3A_Reflection_and_Refraction_via_Fermat's_Principle_and_Huygens'_Construction": "Reflection and Refraction via Fermat's Principle",
                f"{_OP_PHY}/02%3A_Reflection_and_Transmission_at_Boundaries_and_the_Fresnel_Equations": "Fresnel Equations",
                f"{_OP_PHY}/03%3A_The_Cornu_Spiral": "The Cornu Spiral",
                f"{_OP_PHY}/04%3A_Stokes_Parameters_for_Describing_Polarized_Light": "Stokes Parameters for Polarized Light",
                # Other textbooks
                "https://phys.libretexts.org/Bookshelves/Optics/BSc_Optics_(Konijnenberg_Adam_and_Urbach)": "BSc Optics (Konijnenberg, Adam and Urbach)",
                "https://phys.libretexts.org/Bookshelves/Optics/Supplemental_Modules_(Components)": "Supplemental Modules (Optics)",
            },
        },
        # ── Modern Physics ──
        "modern": {
            "pages": {
                # Bookshelf landing
                "https://phys.libretexts.org/Bookshelves/Modern_Physics": "Modern Physics Bookshelf",
                # Spiral Modern Physics (D'Alessandris)
                f"{_MP_SPIR}": "Spiral Modern Physics (D'Alessandris)",
                f"{_MP_SPIR}/1%3A_The_Special_Theory_of_Relativity_-_Kinematics": "Special Relativity - Kinematics",
                f"{_MP_SPIR}/2%3A_The_Special_Theory_of_Relativity_-_Dynamics": "Special Relativity - Dynamics",
                f"{_MP_SPIR}/3%3A_Spacetime_and_General_Relativity": "Spacetime and General Relativity",
                f"{_MP_SPIR}/4%3A_The_Photon": "The Photon",
                f"{_MP_SPIR}/5%3A_Matter_Waves": "Matter Waves",
                f"{_MP_SPIR}/6%3A_The_Schrodinger_Equation": "The Schrodinger Equation",
                f"{_MP_SPIR}/7%3A_Nuclear_Physics": "Nuclear Physics (Modern)",
                f"{_MP_SPIR}/8%3A_Misc_-_Semiconductors_and_Cosmology": "Semiconductors and Cosmology",
                # Supplemental
                "https://phys.libretexts.org/Bookshelves/Modern_Physics/Supplemental_Modules_(Modern_Physics)": "Supplemental Modules (Modern Physics)",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"libretexts-physics-{source_key}" if source_key else "libretexts-physics"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
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
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            for suffix in [' - Physics LibreTexts', ' - LibreTexts', ' | LibreTexts']:
                if title.endswith(suffix):
                    title = title[:-len(suffix)].strip()
            return title
        return fallback

    def _scrape_source(self, source_key, config):
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
                        "category": f"libretexts-physics-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")
            time.sleep(1.5)
        return count

    def scrape(self):
        total = 0
        if self.source_key:
            if self.source_key not in self.SOURCES:
                self.log.error(f"Unknown source key: {self.source_key}. Available: {list(self.SOURCES.keys())}")
                return 0
            sources = {self.source_key: self.SOURCES[self.source_key]}
        else:
            sources = self.SOURCES
        for key, config in sources.items():
            if not self.running:
                break
            self.log.info(f"=== Scraping libretexts-physics/{key} ===")
            total += self._scrape_source(key, config)
        return total


if __name__ == "__main__":
    import os
    import sys
    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    LibreTextsPhysicsScraper(base, source_key).run()
