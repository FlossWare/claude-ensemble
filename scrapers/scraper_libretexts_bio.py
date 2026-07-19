#!/usr/bin/env python3
"""Biology LibreTexts documentation scraper.

Covers:
  - General Biology (Boundless) - cell biology through ecology
  - Microbiology (Boundless) - prokaryotes, viruses, immunology
  - Cell and Molecular Biology (Wong) - membranes, DNA, signaling
  - Biochemistry (Jakubowski and Flatt) - structure, metabolism, info pathways
  - Genetics (Nickle and Barrette-Ng) - Mendelian through genomics
  - Ecology and Environmental Biology (Fisher) - ecosystems, conservation
  - Human Biology (Wakim and Grewal) - anatomy and physiology
  - Evolutionary Biology - natural selection, speciation, phylogenetics
  - Botany - plant structure, physiology, reproduction
  - Marine Biology - ocean ecosystems, marine organisms
  - Biotechnology - recombinant DNA, genomics, applications
  - Additional bookshelf landing pages for all major bio disciplines
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class LibreTextsBioScraper(BaseScraper):
    SOURCES = {
        "general-biology": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/01%3A_The_Study_of_Life": "The Study of Life",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/02%3A_The_Chemical_Foundation_of_Life": "The Chemical Foundation of Life",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/03%3A_Biological_Macromolecules": "Biological Macromolecules",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/04%3A_Cell_Structure": "Cell Structure",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/05%3A_Structure_and_Function_of_Plasma_Membranes": "Structure and Function of Plasma Membranes",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/06%3A_Metabolism": "Metabolism",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/07%3A_Cellular_Respiration": "Cellular Respiration",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/08%3A_Photosynthesis": "Photosynthesis",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/09%3A_Cell_Communication": "Cell Communication",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/10%3A_Cell_Reproduction": "Cell Reproduction",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/11%3A_Meiosis_and_Sexual_Reproduction": "Meiosis and Sexual Reproduction",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/12%3A_Mendel's_Experiments_and_Heredity": "Mendel's Experiments and Heredity",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/13%3A_Modern_Understandings_of_Inheritance": "Modern Understandings of Inheritance",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/14%3A_DNA_Structure_and_Function": "DNA Structure and Function",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/15%3A_Genes_and_Proteins": "Genes and Proteins",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/16%3A_Gene_Expression": "Gene Expression",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/17%3A_Biotechnology_and_Genomics": "Biotechnology and Genomics",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/18%3A_Evolution_and_the_Origin_of_Species": "Evolution and the Origin of Species",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/19%3A_The_Evolution_of_Populations": "The Evolution of Populations",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/20%3A_Phylogenies_and_the_History_of_Life": "Phylogenies and the History of Life",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/21%3A_Viruses": "Viruses",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/22%3A_Prokaryotes-_Bacteria_and_Archaea": "Prokaryotes: Bacteria and Archaea",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/23%3A_Protists": "Protists",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/24%3A_Fungi": "Fungi",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/25%3A_Seedless_Plants": "Seedless Plants",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/26%3A_Seed_Plants": "Seed Plants",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/27%3A_Introduction_to_Animal_Diversity": "Introduction to Animal Diversity",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/28%3A_Invertebrates": "Invertebrates",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/29%3A_Vertebrates": "Vertebrates",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/30%3A_Plant_Form_and_Physiology": "Plant Form and Physiology",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/31%3A_Soil_and_Plant_Nutrition": "Soil and Plant Nutrition",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/32%3A_Plant_Reproductive_Development_and_Structure": "Plant Reproductive Development and Structure",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/33%3A_The_Animal_Body-_Basic_Form_and_Function": "The Animal Body: Basic Form and Function",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/34%3A_Animal_Nutrition_and_the_Digestive_System": "Animal Nutrition and the Digestive System",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/35%3A_The_Nervous_System": "The Nervous System",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/36%3A_Sensory_Systems": "Sensory Systems",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/37%3A_The_Endocrine_System": "The Endocrine System",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/38%3A_The_Musculoskeletal_System": "The Musculoskeletal System",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/39%3A_The_Respiratory_System": "The Respiratory System",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/40%3A_The_Circulatory_System": "The Circulatory System",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/41%3A_Osmotic_Regulation_and_the_Excretory_System": "Osmotic Regulation and the Excretory System",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/42%3A_The_Immune_System": "The Immune System",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/43%3A_Animal_Reproduction_and_Development": "Animal Reproduction and Development",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/44%3A_Ecology_and_the_Biosphere": "Ecology and the Biosphere",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/45%3A_Population_and_Community_Ecology": "Population and Community Ecology",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/46%3A_Ecosystems": "Ecosystems",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/47%3A_Conservation_Biology_and_Biodiversity": "Conservation Biology and Biodiversity",
            },
        },
        "microbiology": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/01%3A_Introduction_to_Microbiology": "Introduction to Microbiology",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/02%3A_Chemistry": "Chemistry",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/03%3A_Microscopy": "Microscopy",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/04%3A_Cell_Structure_of_Bacteria_Archaea_and_Eukaryotes": "Cell Structure of Bacteria, Archaea, and Eukaryotes",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/05%3A_Microbial_Metabolism": "Microbial Metabolism",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/06%3A_Culturing_Microorganisms": "Culturing Microorganisms",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/07%3A_Microbial_Genetics": "Microbial Genetics",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/08%3A_Microbial_Evolution_Phylogeny_and_Diversity": "Microbial Evolution, Phylogeny, and Diversity",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/09%3A_Viruses": "Viruses",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/10%3A_Epidemiology": "Epidemiology",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/11%3A_Immunology": "Immunology",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/12%3A_Immunology_Applications": "Immunology Applications",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/13%3A_Antimicrobial_Drugs": "Antimicrobial Drugs",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/14%3A_Pathogenicity": "Pathogenicity",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/15%3A_Diseases": "Diseases",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/16%3A_Microbial_Ecology": "Microbial Ecology",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)/17%3A_Industrial_Microbiology": "Industrial Microbiology",
            },
        },
        "cell-biology": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/01%3A_Anatomy_of_a_Cell_-_A_Very_Brief_Overview": "Anatomy of a Cell",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/02%3A_Basic_Cell_Chemistry_-_Chemical_Compounds_and_their_Interactions": "Basic Cell Chemistry",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/03%3A_Bioenergetics_-_Thermodynamics_and_Enzymes": "Bioenergetics",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/04%3A_Membranes_-_Structure_Properties_and_Function": "Membranes",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/05%3A_Metabolism_I__Catabolic_Reactions": "Metabolism I: Catabolic Reactions",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/06%3A_Metabolism_II__Anabolic_Reactions": "Metabolism II: Anabolic Reactions",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/07%3A_DNA": "DNA",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/08%3A_Transcription": "Transcription",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/09%3A_Gene_Regulation": "Gene Regulation",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/10%3A_Translation": "Translation",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/11%3A_Protein_Modification_and_Trafficking": "Protein Modification and Trafficking",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/12%3A_Cytoskeleton": "Cytoskeleton",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/13%3A_Extracellular_Matrix_and_Cell_Adhesion": "Extracellular Matrix and Cell Adhesion",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/14%3A_Signal_Transduction": "Signal Transduction",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/15%3A_Cell_Cycle": "Cell Cycle",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)/16%3A_Viruses_Cancer_and_the_Immune_System": "Viruses, Cancer, and the Immune System",
            },
        },
        "biochemistry": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Biochemistry/Fundamentals_of_Biochemistry_(Jakubowski_and_Flatt)/01%3A_Unit_I-_Structure_and_Catalysis": "Structure and Catalysis",
                "https://bio.libretexts.org/Bookshelves/Biochemistry/Fundamentals_of_Biochemistry_(Jakubowski_and_Flatt)/02%3A_Unit_II-_Bioenergetics_and_Metabolism": "Bioenergetics and Metabolism",
                "https://bio.libretexts.org/Bookshelves/Biochemistry/Fundamentals_of_Biochemistry_(Jakubowski_and_Flatt)/03%3A_Unit_III-_Information_Pathway": "Information Pathways",
                "https://bio.libretexts.org/Bookshelves/Biochemistry/Fundamentals_of_Biochemistry_(Jakubowski_and_Flatt)/Unit_IV_-_Special_Topics": "Special Topics",
                "https://bio.libretexts.org/Bookshelves/Biochemistry": "Biochemistry Bookshelf",
            },
        },
        "genetics": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/01%3A_Overview_DNA_and_Genes": "Overview, DNA, and Genes",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/02%3A_Chromosomes_Mitosis_and_Meiosis": "Chromosomes, Mitosis, and Meiosis",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/03%3A_Genetic_Analysis_of_Single_Genes": "Genetic Analysis of Single Genes",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/04%3A_Mutation_and_Variation": "Mutation and Variation",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/05%3A_Pedigrees_and_Populations": "Pedigrees and Populations",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/06%3A_Genetic_Analysis_of_Multiple_Genes": "Genetic Analysis of Multiple Genes",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/07%3A_Linkage_and_Mapping": "Linkage and Mapping",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/08%3A_Techniques_of_Molecular_Genetics": "Techniques of Molecular Genetics",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/09%3A__Changes_in_Chromosome_Number_and_Structure": "Changes in Chromosome Number and Structure",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/10%3A__Molecular_Markers_and_Quantitative_Traits": "Molecular Markers and Quantitative Traits",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/11%3A_Genomics_and_Systems_Biology": "Genomics and Systems Biology",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/12%3A_Regulation_of_Gene_Expression": "Regulation of Gene Expression",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/13%3A_Cancer_Genetics": "Cancer Genetics",
                "https://bio.libretexts.org/Bookshelves/Genetics": "Genetics Bookshelf",
            },
        },
        "ecology": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/01%3A_Environmental_Science": "Environmental Science",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/02%3A_Matter_Energy__Life": "Matter, Energy, and Life",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/03%3A_Ecosystems_and_the_Biosphere": "Ecosystems and the Biosphere",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/04%3A_Community__Population_Ecology": "Community and Population Ecology",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/05%3A_Conservation__Biodiversity": "Conservation and Biodiversity",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/06%3A_Environmental_Hazards__Human_Health": "Environmental Hazards and Human Health",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/07%3A_Water_Availability_and_Use": "Water Availability and Use",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/08%3A_Food__Hunger": "Food and Hunger",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/09%3A_Conventional__Sustainable_Agriculture": "Conventional and Sustainable Agriculture",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/10%3A_Air_Pollution_Climate_Change__Ozone_Depletion": "Air Pollution, Climate Change, and Ozone Depletion",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)/11%3A_Conventional__Sustainable_Energy": "Conventional and Sustainable Energy",
                "https://bio.libretexts.org/Bookshelves/Ecology": "Ecology Bookshelf",
            },
        },
        "human-biology": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/01%3A_The_Nature_and_Process_of_Science": "The Nature and Process of Science",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/02%3A_Introduction_to_Human_Biology": "Introduction to Human Biology",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/03%3A_Chemistry_of_Life": "Chemistry of Life",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/04%3A_Nutrition": "Nutrition",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/05%3A_Cells": "Cells",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/06%3A_DNA_and_Protein_Synthesis": "DNA and Protein Synthesis",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/07%3A_Cell_Reproduction": "Cell Reproduction",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/08%3A_Inheritance": "Inheritance",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/09%3A_Biological_Evolution": "Biological Evolution",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/10%3A_Introduction_to_the_Human_Body": "Introduction to the Human Body",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/11%3A_Nervous_System": "Nervous System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/12%3A_Endocrine_System": "Endocrine System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/13%3A_Integumentary_System": "Integumentary System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/14%3A_Skeletal_System": "Skeletal System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/15%3A_Muscular_System": "Muscular System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/16%3A_Respiratory_System": "Respiratory System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/17%3A_Cardiovascular_System": "Cardiovascular System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/18%3A_Digestive_System": "Digestive System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/19%3A_Urinary_System": "Urinary System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/20%3A_Immune_System": "Immune System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/21%3A_Disease": "Disease",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/22%3A_Reproductive_System": "Reproductive System",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/23%3A_Human_Growth_and_Development": "Human Growth and Development",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/24%3A_Ecology": "Ecology",
                "https://bio.libretexts.org/Bookshelves/Human_Biology": "Human Biology Bookshelf",
            },
        },
        "evolution": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Evolutionary_Developmental_Biology": "Evolutionary Developmental Biology Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/18%3A_Evolution_and_the_Origin_of_Species": "Evolution and the Origin of Species",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/19%3A_The_Evolution_of_Populations": "The Evolution of Populations",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/20%3A_Phylogenies_and_the_History_of_Life": "Phylogenies and the History of Life",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/Book%3A_General_Biology_(Boundless)/18%3A_Evolution_and_the_Origin_of_Species": "Evolution (Alt)",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)/09%3A_Biological_Evolution": "Biological Evolution (Human Bio)",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)/05%3A_Pedigrees_and_Populations": "Population Genetics",
            },
        },
        "botany": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Botany": "Botany Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/25%3A_Seedless_Plants": "Seedless Plants (Botany)",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/26%3A_Seed_Plants": "Seed Plants (Botany)",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/30%3A_Plant_Form_and_Physiology": "Plant Form and Physiology (Botany)",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/31%3A_Soil_and_Plant_Nutrition": "Soil and Plant Nutrition (Botany)",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/32%3A_Plant_Reproductive_Development_and_Structure": "Plant Reproduction (Botany)",
                "https://bio.libretexts.org/Bookshelves/Agriculture_and_Horticulture": "Agriculture and Horticulture Bookshelf",
            },
        },
        "marine-biology": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Marine_Biology_and_Marine_Ecology": "Marine Biology and Marine Ecology Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Ecology/Fish_Fishing_and_Conservation": "Fish, Fishing, and Conservation",
                "https://bio.libretexts.org/Bookshelves/Ecology/Conservation_Biology_in_Sub-Saharan_Africa_(Wilson_and_Primack)": "Conservation Biology in Sub-Saharan Africa",
                "https://bio.libretexts.org/Bookshelves/Ecology/Biodiversity_(Bynum)": "Biodiversity",
                "https://bio.libretexts.org/Bookshelves/Ecology/Ecology_-_A_Guide_to_the_Study_of_Ecosystems_(Wikibooks)": "Ecology: A Guide to Ecosystems",
                "https://bio.libretexts.org/Bookshelves/Ecology/Applied_Ecology_(Wikibooks)": "Applied Ecology",
                "https://bio.libretexts.org/Bookshelves/Ecology/Book%3A_Quantitative_Ecology_-_A_New_Unified_Approach_(Lehman_Loberg_and_Clark)": "Quantitative Ecology",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Science_(Ha_and_Schleiger)": "Environmental Science (Ha and Schleiger)",
                "https://bio.libretexts.org/Bookshelves/Ecology/Monitoring_Animal_Populations_and_their_Habitats%3A_A_Practitioner's_Guide": "Monitoring Animal Populations",
            },
        },
        "biotechnology": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Biotechnology": "Biotechnology Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Computational_Biology": "Computational Biology Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Genetics/Genetics_Agriculture_and_Biotechnology_(Suza_and_Lee)": "Genetics, Agriculture, and Biotechnology",
                "https://bio.libretexts.org/Bookshelves/Genetics/Working_with_Molecular_Genetics_(Hardison)": "Working with Molecular Genetics",
                "https://bio.libretexts.org/Bookshelves/Genetics/Introduction_to_Genetics_(Singh)": "Introduction to Genetics",
                "https://bio.libretexts.org/Bookshelves/Genetics/Classical_Genetics_(Khan_Academy)": "Classical Genetics",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)/17%3A_Biotechnology_and_Genomics": "Biotechnology and Genomics",
            },
        },
        "bookshelves": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves": "Biology Bookshelves Home",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology": "Introductory and General Biology Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology": "Cell and Molecular Biology Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Microbiology": "Microbiology Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Entomology": "Entomology Bookshelf",
                "https://bio.libretexts.org/Bookshelves/Introductory_and_General_Biology/General_Biology_(Boundless)": "General Biology (Boundless) Landing",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(Boundless)": "Microbiology (Boundless) Landing",
                "https://bio.libretexts.org/Bookshelves/Cell_and_Molecular_Biology/Cells_-_Molecules_and_Mechanisms_(Wong)": "Cells: Molecules and Mechanisms Landing",
                "https://bio.libretexts.org/Bookshelves/Biochemistry/Fundamentals_of_Biochemistry_(Jakubowski_and_Flatt)": "Fundamentals of Biochemistry Landing",
                "https://bio.libretexts.org/Bookshelves/Genetics/Online_Open_Genetics_(Nickle_and_Barrette-Ng)": "Online Open Genetics Landing",
                "https://bio.libretexts.org/Bookshelves/Ecology/Environmental_Biology_(Fisher)": "Environmental Biology Landing",
                "https://bio.libretexts.org/Bookshelves/Human_Biology/Human_Biology_(Wakim_and_Grewal)": "Human Biology Landing",
                "https://bio.libretexts.org/Bookshelves/Biochemistry/Fundamentals_of_Biochemistry_(Jakubowski_and_Flatt)/Fundamentals_of_Biochemistry_Vol._V_-_Literature-based_Guided_Assessments_and_iCn3D_Molecular_Modeling_Tutorials": "Biochemistry Vol V - Assessments and Modeling",
            },
        },
        "microbiology-openstax": {
            "pages": {
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)": "Microbiology (OpenStax) Landing",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/01%3A_An_Invisible_World": "An Invisible World",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/02%3A_How_We_See_the_Invisible_World": "How We See the Invisible World",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/03%3A_The_Cell": "The Cell",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/04%3A_Prokaryotic_Diversity": "Prokaryotic Diversity",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/05%3A_The_Eukaryotes_of_Microbiology": "Eukaryotes of Microbiology",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/06%3A_Acellular_Pathogens": "Acellular Pathogens",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/07%3A_Microbial_Biochemistry": "Microbial Biochemistry",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/08%3A_Microbial_Metabolism": "Microbial Metabolism (OpenStax)",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/09%3A_Microbial_Growth": "Microbial Growth",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/10%3A_Biochemistry_of_the_Genome": "Biochemistry of the Genome",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/11%3A_Mechanisms_of_Microbial_Genetics": "Mechanisms of Microbial Genetics",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/12%3A_Modern_Applications_of_Microbial_Genetics": "Modern Applications of Microbial Genetics",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/13%3A_Control_of_Microbial_Growth": "Control of Microbial Growth",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/14%3A_Antimicrobial_Drugs": "Antimicrobial Drugs (OpenStax)",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/15%3A_Microbial_Mechanisms_of_Pathogenicity": "Microbial Mechanisms of Pathogenicity",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/16%3A_Disease_and_Epidemiology": "Disease and Epidemiology",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/17%3A_Innate_Nonspecific_Host_Defenses": "Innate Nonspecific Host Defenses",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/18%3A_Adaptive_Specific_Host_Defenses": "Adaptive Specific Host Defenses",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/19%3A_Diseases_of_the_Immune_System": "Diseases of the Immune System",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/20%3A_Laboratory_Analysis_of_the_Immune_Response": "Laboratory Analysis of the Immune Response",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/21%3A_Skin_and_Eye_Infections": "Skin and Eye Infections",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/22%3A_Respiratory_System_Infections": "Respiratory System Infections",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/23%3A_Urogenital_System_Infections": "Urogenital System Infections",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/24%3A_Digestive_System_Infections": "Digestive System Infections",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/25%3A_Circulatory_and_Lymphatic_System_Infections": "Circulatory and Lymphatic System Infections",
                "https://bio.libretexts.org/Bookshelves/Microbiology/Microbiology_(OpenStax)/26%3A_Nervous_System_Infections": "Nervous System Infections",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"libretexts-biology-{source_key}" if source_key else "libretexts-biology"
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
            for suffix in [' - Biology LibreTexts', ' - LibreTexts', ' | LibreTexts']:
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
                        "category": f"libretexts-biology-{source_key}",
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
            self.log.info(f"=== Scraping libretexts-biology/{key} ===")
            total += self._scrape_source(key, config)
        return total

if __name__ == "__main__":
    import os
    import sys
    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    LibreTextsBioScraper(base, source_key).run()
