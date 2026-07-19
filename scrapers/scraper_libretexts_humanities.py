#!/usr/bin/env python3
"""Humanities & Social Sciences LibreTexts scraper.

Covers:
  - History (human.libretexts.org): World History, US History, Western Civilization
  - Social Sciences (socialsci.libretexts.org): Psychology, Sociology,
    Political Science, Economics
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class LibreTextsHumanitiesScraper(BaseScraper):
    """Scrape LibreTexts humanities and social sciences content."""

    SOURCES = {
        "world-history": {
            "pages": {
                # Ancient Civilizations
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/01%3A_Prehistory": "Prehistory",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/02%3A_Early_Middle_Eastern_and_Northeast_African_Civilizations": "Early Middle Eastern and Northeast African Civilizations",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/03%3A_Ancient_and_Medieval_India": "Ancient and Medieval India",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/04%3A_China_and_East_Asia_to_the_Ming_Dynasty": "China and East Asia to the Ming Dynasty",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/05%3A_The_Greek_World_from_Bronze_Age_to_Roman_Conquest": "The Greek World from Bronze Age to Roman Conquest",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/06%3A_The_Roman_World_from_753_BCE_to_500_BCE": "The Roman World",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/07%3A_Western_Europe_and_Byzantium_circa_500-1000_CE": "Western Europe and Byzantium 500-1000 CE",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/08%3A_Islam_to_the_Mamluks": "Islam to the Mamluks",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/09%3A_Africa_to_the_Fifteenth_Century": "Africa to the Fifteenth Century",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/10%3A_The_Americas": "The Americas (Pre-Columbian)",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_World_History_-_Cultures_States_and_Societies_to_1500_(Berger_et_al.)/11%3A_Central_and_Eastern_Europe_and_Western_Asia_circa_1000-1500_CE": "Central and Eastern Europe 1000-1500 CE",
                # Modern World History
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/12%3A_The_Renaissance": "The Renaissance",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/13%3A_The_Protestant_Reformation": "The Protestant Reformation",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_II_(Brooks)/01%3A_The_Age_of_Exploration": "The Age of Exploration",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_II_(Brooks)/02%3A_The_Scientific_Revolution": "The Scientific Revolution",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_II_(Brooks)/03%3A_The_Enlightenment": "The Enlightenment",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_II_(Brooks)/04%3A_The_French_Revolution": "The French Revolution",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_II_(Brooks)/05%3A_Napoleon": "Napoleon",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_II_(Brooks)/06%3A_The_Industrial_Revolution": "The Industrial Revolution",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_II_(Brooks)/07%3A_Political_Revolutions_and_Nationalism": "Political Revolutions and Nationalism",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_II_(Brooks)/08%3A_Imperialism": "Imperialism",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_III_(Brooks)/01%3A_World_War_I": "World War I",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_III_(Brooks)/02%3A_The_Interwar_Period": "The Interwar Period",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_III_(Brooks)/03%3A_World_War_II": "World War II",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_III_(Brooks)/04%3A_The_Cold_War": "The Cold War",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_III_(Brooks)/05%3A_Decolonization": "Decolonization",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_III_(Brooks)/06%3A_The_End_of_the_Cold_War_and_the_Emergence_of_a_New_Europe": "End of the Cold War and New Europe",
            },
        },
        "us-history": {
            "pages": {
                # Colonial and Revolution
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/03%3A_Creating_New_Social_Orders-_Colonial_Societies_(1500-1700)": "Colonial Societies 1500-1700",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/04%3A_Rule_Britannia!_The_English_Empire_(1660-1763)": "The English Empire 1660-1763",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/05%3A_Imperial_Reforms_and_Colonial_Protests_(1763-1774)": "Imperial Reforms and Colonial Protests 1763-1774",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/06%3A_America's_War_for_Independence_(1775-1783)": "War for Independence 1775-1783",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/07%3A_Creating_Republican_Governments_(1776-1790)": "Creating Republican Governments 1776-1790",
                # Early Republic
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/08%3A_Growing_Pains-_The_New_Republic_(1790-1820)": "The New Republic 1790-1820",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/09%3A_Industrial_Transformation_in_the_North_(1800-1850)": "Industrial Transformation 1800-1850",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/10%3A_Jacksonian_Democracy_(1820-1840)": "Jacksonian Democracy 1820-1840",
                # Antebellum and Civil War
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/11%3A_A_Nation_on_the_Move-_Westward_Expansion_(1800-1860)": "Westward Expansion 1800-1860",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/12%3A_Cotton_is_King-_The_Antebellum_South_(1800-1860)": "The Antebellum South 1800-1860",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/13%3A_Antebellum_Idealism_and_Reform_Impulses_(1820-1860)": "Antebellum Idealism and Reform 1820-1860",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/14%3A_Troubled_Times-_the_Tumultuous_1850s": "The Tumultuous 1850s",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/15%3A_The_Civil_War_(1860-1865)": "The Civil War 1860-1865",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/16%3A_The_Era_of_Reconstruction_(1865-1877)": "Reconstruction 1865-1877",
                # Gilded Age to Progressive Era
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/17%3A_Go_West_Young_Man!_Westward_Expansion_(1840-1900)": "Westward Expansion 1840-1900",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/18%3A_Industrialization_and_the_Rise_of_Big_Business_(1870-1900)": "Rise of Big Business 1870-1900",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/19%3A_The_Growing_Pains_of_Urbanization_(1870-1900)": "Urbanization 1870-1900",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/20%3A_Politics_in_the_Gilded_Age_(1870-1900)": "Gilded Age Politics 1870-1900",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/21%3A_Leading_the_Way-_The_Progressive_Movement_(1890-1920)": "The Progressive Movement 1890-1920",
                # WWI through WWII
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/22%3A_Age_of_Empire-_American_Foreign_Policy_(1890-1914)": "American Foreign Policy 1890-1914",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/23%3A_Americans_and_the_Great_War_(1914-1919)": "Americans and the Great War 1914-1919",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/24%3A_The_Jazz_Age-_Redefining_the_Nation_(1919-1929)": "The Jazz Age 1919-1929",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/25%3A_Brother_Can_You_Spare_a_Dime_The_Great_Depression_(1929-1932)": "The Great Depression 1929-1932",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/26%3A_Franklin_Roosevelt_and_the_New_Deal_(1932-1941)": "FDR and the New Deal 1932-1941",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/27%3A_Fighting_the_Good_Fight_in_World_War_II_(1941-1945)": "World War II 1941-1945",
                # Cold War through Modern
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/28%3A_Post-War_Prosperity_and_Cold_War_Fears_(1945-1960)": "Post-War Prosperity and Cold War 1945-1960",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/29%3A_Contesting_Futures-_America_in_the_1960s": "America in the 1960s",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/30%3A_Political_Storms_at_Home_and_Abroad_(1968-1980)": "Political Storms 1968-1980",
                "https://human.libretexts.org/Bookshelves/History/National_History/Book%3A_U.S._History_(OpenStax)/31%3A_From_Partners_to_Partisanship_(1980-Present)": "Partners to Partisanship 1980-Present",
            },
        },
        "western-civ": {
            "pages": {
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/01%3A_The_Origins_of_Western_Civilization_in_the_Ancient_Near_East": "Origins of Western Civilization",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/02%3A_Ancient_Egypt": "Ancient Egypt",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/03%3A_Ancient_Greece": "Ancient Greece",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/04%3A_The_Greek_World_After_Alexander": "The Greek World After Alexander",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/05%3A_The_Roman_Republic": "The Roman Republic",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/06%3A_The_Roman_Empire": "The Roman Empire",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/07%3A_The_Late_Roman_Empire_and_the_Early_Middle_Ages": "Late Roman Empire and Early Middle Ages",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/08%3A_Islam_and_the_Caliphates": "Islam and the Caliphates",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/09%3A_The_High_Middle_Ages": "The High Middle Ages",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/10%3A_The_Crusades": "The Crusades",
                "https://human.libretexts.org/Bookshelves/History/World_History/Book%3A_Western_Civilization_-_A_Concise_History_I_(Brooks)/11%3A_The_Late_Middle_Ages": "The Late Middle Ages",
            },
        },
        "psychology": {
            "pages": {
                # Introduction to Psychology
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/01%3A_The_Science_of_Psychology": "The Science of Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/02%3A_The_Brain_and_Behavior": "The Brain and Behavior",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/03%3A_Sensation_and_Perception": "Sensation and Perception",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/04%3A_Learning": "Learning (Psychology)",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/05%3A_Memory": "Memory",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/06%3A_Language_and_Thinking": "Language and Thinking",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/07%3A_Intelligence_and_Individual_Differences": "Intelligence and Individual Differences",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/08%3A_Motivation_and_Emotion": "Motivation and Emotion",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/09%3A_Lifespan_Development": "Lifespan Development",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/10%3A_Personality": "Personality",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/11%3A_Social_Psychology": "Social Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/12%3A_Psychological_Disorders": "Psychological Disorders",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/13%3A_Therapy": "Therapy",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Introductory_Psychology/Book%3A_Introductory_Psychology_(CCBY)/14%3A_Health_Psychology_Stress_and_Coping": "Health Psychology Stress and Coping",
                # Research Methods
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Book%3A_Research_Methods_in_Psychology_(Jhangiani_Chiang_Cuttler_and_Leighton)/01%3A_The_Science_of_Psychology": "Research Methods - Science of Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Book%3A_Research_Methods_in_Psychology_(Jhangiani_Chiang_Cuttler_and_Leighton)/02%3A_Getting_Started_in_Research": "Getting Started in Research",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Book%3A_Research_Methods_in_Psychology_(Jhangiani_Chiang_Cuttler_and_Leighton)/03%3A_Research_Ethics": "Research Ethics",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Book%3A_Research_Methods_in_Psychology_(Jhangiani_Chiang_Cuttler_and_Leighton)/05%3A_Experimental_Research": "Experimental Research",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Book%3A_Research_Methods_in_Psychology_(Jhangiani_Chiang_Cuttler_and_Leighton)/06%3A_Non-Experimental_Research": "Non-Experimental Research",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Book%3A_Research_Methods_in_Psychology_(Jhangiani_Chiang_Cuttler_and_Leighton)/07%3A_Survey_Research": "Survey Research",
                # Developmental Psychology
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/01%3A_Introduction_to_Lifespan_Development": "Introduction to Lifespan Development",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/02%3A_Heredity_Prenatal_Development_and_Birth": "Heredity Prenatal Development and Birth",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/03%3A_Infancy_and_Toddlerhood": "Infancy and Toddlerhood",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/04%3A_Early_Childhood": "Early Childhood Development",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/05%3A_Middle_and_Late_Childhood": "Middle and Late Childhood",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/06%3A_Adolescence": "Adolescence",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/07%3A_Emerging_and_Early_Adulthood": "Emerging and Early Adulthood",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/08%3A_Middle_Adulthood": "Middle Adulthood",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/09%3A_Late_Adulthood": "Late Adulthood",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Developmental_Psychology/Book%3A_Lifespan_Development_-_A_Psychological_Perspective_(Lally_and_Valentine-French)/10%3A_Death_and_Dying": "Death and Dying",
                # Cognitive Psychology
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Cognitive_Psychology/Book%3A_Cognitive_Psychology_(Andrade_and_Walker)/01%3A_Introduction_to_Cognitive_Psychology": "Introduction to Cognitive Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Cognitive_Psychology/Book%3A_Cognitive_Psychology_(Andrade_and_Walker)/02%3A_Perception": "Perception",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Cognitive_Psychology/Book%3A_Cognitive_Psychology_(Andrade_and_Walker)/03%3A_Attention": "Attention",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Cognitive_Psychology/Book%3A_Cognitive_Psychology_(Andrade_and_Walker)/04%3A_Memory": "Memory (Cognitive)",
                # Abnormal Psychology
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/01%3A_What_is_Abnormal_Psychology": "What is Abnormal Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/02%3A_Models_of_Abnormal_Psychology": "Models of Abnormal Psychology",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/03%3A_Clinical_Assessment_Diagnosis_and_Treatment": "Clinical Assessment Diagnosis and Treatment",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/04%3A_Anxiety_Disorders": "Anxiety Disorders",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/05%3A_Obsessive-Compulsive_and_Related_Disorders": "Obsessive-Compulsive Disorders",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/06%3A_Trauma-_and_Stressor-Related_Disorders": "Trauma and Stressor-Related Disorders",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/07%3A_Mood_Disorders": "Mood Disorders",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/08%3A_Schizophrenia_Spectrum_and_Other_Psychotic_Disorders": "Schizophrenia Spectrum Disorders",
                "https://socialsci.libretexts.org/Bookshelves/Psychology/Psychological_Disorders/Book%3A_Essentials_of_Abnormal_Psychology_(Bridley_and_Daffin)/09%3A_Personality_Disorders": "Personality Disorders",
            },
        },
        "sociology": {
            "pages": {
                # Introduction to Sociology
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/01%3A_Sociology": "Introduction to Sociology",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/02%3A_Sociological_Research": "Sociological Research",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/03%3A_Culture": "Culture",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/04%3A_Society_and_Social_Interaction": "Society and Social Interaction",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/05%3A_Socialization": "Socialization",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/06%3A_Social_Groups_and_Organization": "Social Groups and Organization",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/07%3A_Deviance_Social_Control_and_Crime": "Deviance Social Control and Crime",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/08%3A_Social_Stratification_in_the_United_States": "Social Stratification in the US",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/09%3A_Global_Stratification_and_Inequality": "Global Stratification and Inequality",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/10%3A_Race_and_Ethnicity": "Race and Ethnicity",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/11%3A_Gender_Sex_and_Sexuality": "Gender Sex and Sexuality",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/12%3A_Aging_and_the_Elderly": "Aging and the Elderly",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/13%3A_Marriage_and_Family": "Marriage and Family",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/14%3A_Religion": "Religion",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/15%3A_Education": "Education",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/16%3A_Government_and_Politics": "Government and Politics",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/17%3A_Work_and_the_Economy": "Work and the Economy",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/18%3A_Health_and_Medicine": "Health and Medicine",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/19%3A_Population_Urbanization_and_the_Environment": "Population Urbanization and the Environment",
                "https://socialsci.libretexts.org/Bookshelves/Sociology/Introduction_to_Sociology/Book%3A_Sociology_(Boundless)/20%3A_Social_Movements_and_Social_Change": "Social Movements and Social Change",
            },
        },
        "political-science": {
            "pages": {
                # American Government
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/01%3A_American_Government_and_Civic_Engagement": "American Government and Civic Engagement",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/02%3A_The_Constitution_and_Its_Origins": "The Constitution and Its Origins",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/03%3A_American_Federalism": "American Federalism",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/04%3A_Civil_Liberties": "Civil Liberties",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/05%3A_Civil_Rights": "Civil Rights",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/06%3A_The_Politics_of_Public_Opinion": "The Politics of Public Opinion",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/07%3A_Voting_and_Elections": "Voting and Elections",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/08%3A_The_Media": "The Media",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/09%3A_Political_Parties": "Political Parties",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/10%3A_Interest_Groups_and_Lobbying": "Interest Groups and Lobbying",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/11%3A_Congress": "Congress",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/12%3A_The_Presidency": "The Presidency",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/13%3A_The_Courts": "The Courts",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/14%3A_State_and_Local_Government": "State and Local Government",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/15%3A_The_Bureaucracy": "The Bureaucracy",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/16%3A_Domestic_Policy": "Domestic Policy",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_American_Government_3e_(OpenStax)/17%3A_Foreign_Policy": "Foreign Policy",
                # International Relations
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_Introduction_to_International_Relations_(Lumen)/01%3A_Why_Study_International_Relations": "Why Study International Relations",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_Introduction_to_International_Relations_(Lumen)/02%3A_Historical_Context": "IR Historical Context",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_Introduction_to_International_Relations_(Lumen)/03%3A_Theories": "IR Theories",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_Introduction_to_International_Relations_(Lumen)/04%3A_Foreign_Policy": "Foreign Policy (IR)",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_Introduction_to_International_Relations_(Lumen)/05%3A_War_and_Security": "War and Security",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_Introduction_to_International_Relations_(Lumen)/06%3A_International_Organizations": "International Organizations",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_Introduction_to_International_Relations_(Lumen)/07%3A_International_Law_and_Human_Rights": "International Law and Human Rights",
                "https://socialsci.libretexts.org/Bookshelves/Political_Science_and_Civics/Book%3A_Introduction_to_International_Relations_(Lumen)/08%3A_International_Political_Economy": "International Political Economy",
            },
        },
        "economics": {
            "pages": {
                # Principles of Economics
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/01%3A_Economics-_The_Study_of_Choice": "Economics - The Study of Choice",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/02%3A_Confronting_Scarcity-_Choices_in_Production": "Confronting Scarcity - Choices in Production",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/03%3A_Demand_and_Supply": "Demand and Supply",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/04%3A_Applications_of_Demand_and_Supply": "Applications of Demand and Supply",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/05%3A_Elasticity-_A_Measure_of_Response": "Elasticity - A Measure of Response",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/06%3A_Markets_Maximizers_and_Efficiency": "Markets Maximizers and Efficiency",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/07%3A_The_Analysis_of_Consumer_Choice": "The Analysis of Consumer Choice",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/08%3A_Production_and_Cost": "Production and Cost",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/09%3A_Competitive_Markets_for_Goods_and_Services": "Competitive Markets for Goods and Services",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/10%3A_Monopoly": "Monopoly (Economics)",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Principles_of_Economics/Book%3A_Principles_of_Economics_(Libretexts)/11%3A_The_World_of_Imperfect_Competition": "The World of Imperfect Competition",
                # Macroeconomics
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/01%3A_Macroeconomics-_The_Big_Picture": "Macroeconomics - The Big Picture",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/02%3A_Measuring_Total_Output_and_Income": "Measuring Total Output and Income",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/03%3A_Unemployment_and_Inflation": "Unemployment and Inflation",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/04%3A_Economic_Growth": "Economic Growth",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/05%3A_Aggregate_Demand_and_Aggregate_Supply": "Aggregate Demand and Aggregate Supply",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/06%3A_Fiscal_Policy": "Fiscal Policy (Macro)",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/07%3A_Money_and_Banking": "Money and Banking",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/08%3A_Monetary_Policy": "Monetary Policy (Macro)",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/09%3A_International_Trade": "International Trade (Macro)",
                "https://socialsci.libretexts.org/Bookshelves/Economics/Macroeconomics/Book%3A_Macroeconomics_(Libretexts)/10%3A_Open_Economy_Macroeconomics": "Open Economy Macroeconomics",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"libretexts-humanities-{source_key}" if source_key else "libretexts-humanities"
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
            for suffix in [
                ' - LibreTexts',
                ' - Humanities LibreTexts',
                ' - Social Sci LibreTexts',
            ]:
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
                        "category": "libretexts-humanities",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(1.5)  # Respectful rate limit

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
            self.log.info(f"=== Scraping libretexts-humanities/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    LibreTextsHumanitiesScraper(base, source_key).run()
