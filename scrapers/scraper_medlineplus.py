#!/usr/bin/env python3
"""MedlinePlus health information scraper.

NIH consumer health, drugs, supplements, genetics, and medical encyclopedia.
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class MedlinePlusScraper(BaseScraper):
    """MedlinePlus health information scraper. NIH consumer health, drugs, supplements, genetics, and medical encyclopedia."""

    SOURCES = {
        "health-topics": {
            "pages": {
                # Diabetes
                "https://medlineplus.gov/diabetes.html": "Diabetes",
                "https://medlineplus.gov/diabetestype1.html": "Type 1 Diabetes",
                "https://medlineplus.gov/diabetestype2.html": "Type 2 Diabetes",
                # Heart and cardiovascular
                "https://medlineplus.gov/heartdiseases.html": "Heart Diseases",
                "https://medlineplus.gov/coronaryarterydisease.html": "Coronary Artery Disease",
                "https://medlineplus.gov/heartattack.html": "Heart Attack",
                "https://medlineplus.gov/heartfailure.html": "Heart Failure",
                "https://medlineplus.gov/arrhythmia.html": "Arrhythmia",
                "https://medlineplus.gov/highbloodpressure.html": "High Blood Pressure",
                "https://medlineplus.gov/stroke.html": "Stroke",
                # Cancer
                "https://medlineplus.gov/cancer.html": "Cancer",
                "https://medlineplus.gov/breastcancer.html": "Breast Cancer",
                "https://medlineplus.gov/lungcancer.html": "Lung Cancer",
                "https://medlineplus.gov/coloncancer.html": "Colon Cancer",
                "https://medlineplus.gov/prostatecancer.html": "Prostate Cancer",
                "https://medlineplus.gov/skincancer.html": "Skin Cancer",
                "https://medlineplus.gov/leukemia.html": "Leukemia",
                "https://medlineplus.gov/lymphoma.html": "Lymphoma",
                "https://medlineplus.gov/pancreaticcancer.html": "Pancreatic Cancer",
                "https://medlineplus.gov/livercancer.html": "Liver Cancer",
                # Respiratory
                "https://medlineplus.gov/asthma.html": "Asthma",
                "https://medlineplus.gov/copd.html": "COPD",
                "https://medlineplus.gov/pneumonia.html": "Pneumonia",
                "https://medlineplus.gov/tuberculosis.html": "Tuberculosis",
                "https://medlineplus.gov/lungdiseases.html": "Lung Diseases",
                # Neurological
                "https://medlineplus.gov/alzheimers.html": "Alzheimer's Disease",
                "https://medlineplus.gov/parkinsons.html": "Parkinson's Disease",
                "https://medlineplus.gov/multiplesclerosis.html": "Multiple Sclerosis",
                "https://medlineplus.gov/epilepsy.html": "Epilepsy",
                "https://medlineplus.gov/migraines.html": "Migraines",
                # Mental health
                "https://medlineplus.gov/depression.html": "Depression",
                "https://medlineplus.gov/anxiety.html": "Anxiety",
                "https://medlineplus.gov/bipolar.html": "Bipolar Disorder",
                "https://medlineplus.gov/schizophrenia.html": "Schizophrenia",
                "https://medlineplus.gov/ptsd.html": "PTSD",
                "https://medlineplus.gov/ocd.html": "OCD",
                "https://medlineplus.gov/eatingdisorders.html": "Eating Disorders",
                "https://medlineplus.gov/adhd.html": "ADHD",
                "https://medlineplus.gov/autism.html": "Autism Spectrum Disorder",
                # Musculoskeletal
                "https://medlineplus.gov/arthritis.html": "Arthritis",
                "https://medlineplus.gov/rheumatoidarthritis.html": "Rheumatoid Arthritis",
                "https://medlineplus.gov/osteoarthritis.html": "Osteoarthritis",
                "https://medlineplus.gov/osteoporosis.html": "Osteoporosis",
                "https://medlineplus.gov/gout.html": "Gout",
                "https://medlineplus.gov/backpain.html": "Back Pain",
                # Kidney
                "https://medlineplus.gov/kidneys.html": "Kidney Diseases",
                "https://medlineplus.gov/kidneyfailure.html": "Kidney Failure",
                "https://medlineplus.gov/kidneystones.html": "Kidney Stones",
                # Liver
                "https://medlineplus.gov/liverdiseases.html": "Liver Diseases",
                "https://medlineplus.gov/hepatitisb.html": "Hepatitis B",
                "https://medlineplus.gov/hepatitisc.html": "Hepatitis C",
                "https://medlineplus.gov/cirrhosis.html": "Cirrhosis",
                # Digestive
                "https://medlineplus.gov/digestivediseases.html": "Digestive Diseases",
                "https://medlineplus.gov/crohnsdisease.html": "Crohn's Disease",
                "https://medlineplus.gov/ulcerativecolitis.html": "Ulcerative Colitis",
                "https://medlineplus.gov/ibs.html": "Irritable Bowel Syndrome",
                "https://medlineplus.gov/gerd.html": "GERD",
                "https://medlineplus.gov/celiacdisease.html": "Celiac Disease",
                "https://medlineplus.gov/gallstones.html": "Gallstones",
                "https://medlineplus.gov/pancreatitis.html": "Pancreatitis",
                # Endocrine
                "https://medlineplus.gov/thyroiddiseases.html": "Thyroid Diseases",
                "https://medlineplus.gov/hypothyroidism.html": "Hypothyroidism",
                "https://medlineplus.gov/hyperthyroidism.html": "Hyperthyroidism",
                # Autoimmune
                "https://medlineplus.gov/lupus.html": "Lupus",
                # Infectious diseases
                "https://medlineplus.gov/hivaids.html": "HIV/AIDS",
                "https://medlineplus.gov/sexuallytransmitteddiseases.html": "Sexually Transmitted Diseases",
                "https://medlineplus.gov/flu.html": "Flu (Influenza)",
                "https://medlineplus.gov/commoncold.html": "Common Cold",
                "https://medlineplus.gov/measles.html": "Measles",
                "https://medlineplus.gov/chickenpox.html": "Chickenpox",
                "https://medlineplus.gov/shingles.html": "Shingles",
                "https://medlineplus.gov/lyme.html": "Lyme Disease",
                "https://medlineplus.gov/malaria.html": "Malaria",
                "https://medlineplus.gov/meningitis.html": "Meningitis",
                # Blood disorders
                "https://medlineplus.gov/anemia.html": "Anemia",
                "https://medlineplus.gov/sicklecell.html": "Sickle Cell Disease",
                "https://medlineplus.gov/hemophilia.html": "Hemophilia",
                # Metabolic
                "https://medlineplus.gov/obesity.html": "Obesity",
                "https://medlineplus.gov/metabolicsyndrome.html": "Metabolic Syndrome",
                "https://medlineplus.gov/highcholesterol.html": "High Cholesterol",
                # Skin
                "https://medlineplus.gov/eczema.html": "Eczema",
                "https://medlineplus.gov/psoriasis.html": "Psoriasis",
                "https://medlineplus.gov/acne.html": "Acne",
                # Eyes and ears
                "https://medlineplus.gov/cataracts.html": "Cataracts",
                "https://medlineplus.gov/glaucoma.html": "Glaucoma",
                "https://medlineplus.gov/hearingdisorders.html": "Hearing Disorders",
                "https://medlineplus.gov/tinnitus.html": "Tinnitus",
                # Allergies
                "https://medlineplus.gov/allergies.html": "Allergies",
                "https://medlineplus.gov/foodallergy.html": "Food Allergy",
                "https://medlineplus.gov/drugallergy.html": "Drug Allergy",
                # Reproductive
                "https://medlineplus.gov/endometriosis.html": "Endometriosis",
                "https://medlineplus.gov/uterinefibroids.html": "Uterine Fibroids",
                "https://medlineplus.gov/ovariancysts.html": "Ovarian Cysts",
                "https://medlineplus.gov/erectiledysfunction.html": "Erectile Dysfunction",
                "https://medlineplus.gov/infertility.html": "Infertility",
                "https://medlineplus.gov/menopause.html": "Menopause",
                # Pregnancy and birth
                "https://medlineplus.gov/pregnancy.html": "Pregnancy",
                "https://medlineplus.gov/prenatalcare.html": "Prenatal Care",
                "https://medlineplus.gov/childbirthproblems.html": "Childbirth Problems",
                "https://medlineplus.gov/miscarriage.html": "Miscarriage",
                "https://medlineplus.gov/birthdefects.html": "Birth Defects",
                "https://medlineplus.gov/downsyndrome.html": "Down Syndrome",
                # Genetic/congenital
                "https://medlineplus.gov/cysticfibrosis.html": "Cystic Fibrosis",
                "https://medlineplus.gov/cerebralpalsy.html": "Cerebral Palsy",
                # Chronic pain and fatigue
                "https://medlineplus.gov/fibromyalgia.html": "Fibromyalgia",
                "https://medlineplus.gov/chronicfatiguesyndrome.html": "Chronic Fatigue Syndrome",
                # Sleep
                "https://medlineplus.gov/sleepapnea.html": "Sleep Apnea",
                "https://medlineplus.gov/insomnia.html": "Insomnia",
                "https://medlineplus.gov/sleepdisorders.html": "Sleep Disorders",
                # Other conditions
                "https://medlineplus.gov/urinarytractinfections.html": "Urinary Tract Infections",
                "https://medlineplus.gov/hernia.html": "Hernia",
                "https://medlineplus.gov/appendicitis.html": "Appendicitis",
                "https://medlineplus.gov/hemorrhoids.html": "Hemorrhoids",
                "https://medlineplus.gov/carpal.html": "Carpal Tunnel Syndrome",
                "https://medlineplus.gov/sciatica.html": "Sciatica",
                "https://medlineplus.gov/scoliosis.html": "Scoliosis",
                "https://medlineplus.gov/tendinitis.html": "Tendinitis",
                "https://medlineplus.gov/bursitis.html": "Bursitis",
                "https://medlineplus.gov/sepsis.html": "Sepsis",
                "https://medlineplus.gov/mrsa.html": "MRSA",
                "https://medlineplus.gov/dengue.html": "Dengue",
                "https://medlineplus.gov/ebola.html": "Ebola",
                "https://medlineplus.gov/zika.html": "Zika Virus",
                # Additional conditions
                "https://medlineplus.gov/atrialfibrillation.html": "Atrial Fibrillation",
                "https://medlineplus.gov/peripheralarterialdisease.html": "Peripheral Arterial Disease",
                "https://medlineplus.gov/varicoseveins.html": "Varicose Veins",
                "https://medlineplus.gov/deepveinthrombosis.html": "Deep Vein Thrombosis",
                "https://medlineplus.gov/pulmonaryembolism.html": "Pulmonary Embolism",
                "https://medlineplus.gov/aorticaneurysm.html": "Aortic Aneurysm",
                "https://medlineplus.gov/congenitalheartdefects.html": "Congenital Heart Defects",
                "https://medlineplus.gov/heartvalvediseases.html": "Heart Valve Diseases",
                "https://medlineplus.gov/croup.html": "Croup",
                "https://medlineplus.gov/bronchitis.html": "Bronchitis",
                "https://medlineplus.gov/pleurisy.html": "Pleurisy",
                "https://medlineplus.gov/sarcoidosis.html": "Sarcoidosis",
                "https://medlineplus.gov/pulmonaryfibrosis.html": "Pulmonary Fibrosis",
                "https://medlineplus.gov/braininjury.html": "Traumatic Brain Injury",
                "https://medlineplus.gov/spinalcordinjuries.html": "Spinal Cord Injuries",
                "https://medlineplus.gov/als.html": "ALS",
                "https://medlineplus.gov/huntingtonsdisease.html": "Huntington's Disease",
                "https://medlineplus.gov/tourettes.html": "Tourette Syndrome",
                "https://medlineplus.gov/bellspalsy.html": "Bell's Palsy",
                "https://medlineplus.gov/peripheralneuropathy.html": "Peripheral Neuropathy",
                "https://medlineplus.gov/restlesslegs.html": "Restless Legs Syndrome",
                "https://medlineplus.gov/dementia.html": "Dementia",
                "https://medlineplus.gov/concussion.html": "Concussion",
                "https://medlineplus.gov/vertigo.html": "Vertigo",
                "https://medlineplus.gov/drymouth.html": "Dry Mouth",
                "https://medlineplus.gov/rosacea.html": "Rosacea",
                "https://medlineplus.gov/vitiligo.html": "Vitiligo",
                "https://medlineplus.gov/hives.html": "Hives",
                "https://medlineplus.gov/pinkeye.html": "Pink Eye",
                "https://medlineplus.gov/maculardegen.html": "Macular Degeneration",
                "https://medlineplus.gov/retinaldisorders.html": "Retinal Disorders",
                "https://medlineplus.gov/hearingloss.html": "Hearing Loss",
                "https://medlineplus.gov/deafness.html": "Deafness",
                "https://medlineplus.gov/sinusitis.html": "Sinusitis",
                "https://medlineplus.gov/tonsilitis.html": "Tonsillitis",
                "https://medlineplus.gov/strep.html": "Strep Throat",
                "https://medlineplus.gov/mononucleosis.html": "Mononucleosis",
                "https://medlineplus.gov/whoopingcough.html": "Whooping Cough",
                "https://medlineplus.gov/tetanus.html": "Tetanus",
                "https://medlineplus.gov/mumps.html": "Mumps",
                "https://medlineplus.gov/diphtheria.html": "Diphtheria",
                "https://medlineplus.gov/polio.html": "Polio",
                "https://medlineplus.gov/rabies.html": "Rabies",
                "https://medlineplus.gov/westnilevirus.html": "West Nile Virus",
                "https://medlineplus.gov/hantavirus.html": "Hantavirus",
                "https://medlineplus.gov/cholera.html": "Cholera",
                "https://medlineplus.gov/typhoid.html": "Typhoid Fever",
                "https://medlineplus.gov/fungalinfections.html": "Fungal Infections",
                "https://medlineplus.gov/parasites.html": "Parasitic Diseases",
                "https://medlineplus.gov/pinworms.html": "Pinworms",
                "https://medlineplus.gov/staph.html": "Staph Infections",
                "https://medlineplus.gov/cpneumoniae.html": "C. Diff",
                "https://medlineplus.gov/kidneycancer.html": "Kidney Cancer",
                "https://medlineplus.gov/bladdercancer.html": "Bladder Cancer",
                "https://medlineplus.gov/thyroidcancer.html": "Thyroid Cancer",
                "https://medlineplus.gov/cervicalcancer.html": "Cervical Cancer",
                "https://medlineplus.gov/ovariancancer.html": "Ovarian Cancer",
                "https://medlineplus.gov/uterinecancer.html": "Uterine Cancer",
                "https://medlineplus.gov/testicularcancer.html": "Testicular Cancer",
                "https://medlineplus.gov/stomachcancer.html": "Stomach Cancer",
                "https://medlineplus.gov/esophagealcancer.html": "Esophageal Cancer",
                "https://medlineplus.gov/braincancer.html": "Brain Cancer",
                "https://medlineplus.gov/bonecancer.html": "Bone Cancer",
                "https://medlineplus.gov/melanoma.html": "Melanoma",
                "https://medlineplus.gov/multiplemyeloma.html": "Multiple Myeloma",
                "https://medlineplus.gov/mesothelioma.html": "Mesothelioma",
            },
        },
        "drugs-supplements": {
            "pages": {
                # General drug information
                "https://medlineplus.gov/druginformation.html": "Drug Information",
                "https://medlineplus.gov/medicines.html": "Medicines",
                "https://medlineplus.gov/overthecountermedicines.html": "Over-the-Counter Medicines",
                "https://medlineplus.gov/prescriptionmedicines.html": "Prescription Medicines",
                # Drug classes
                "https://medlineplus.gov/antibiotics.html": "Antibiotics",
                "https://medlineplus.gov/painrelievers.html": "Pain Relievers",
                "https://medlineplus.gov/antidepressants.html": "Antidepressants",
                "https://medlineplus.gov/statins.html": "Statins",
                "https://medlineplus.gov/bloodthinners.html": "Blood Thinners",
                "https://medlineplus.gov/steroids.html": "Steroids",
                "https://medlineplus.gov/opioids.html": "Opioids",
                "https://medlineplus.gov/opioidmisuseandaddiction.html": "Opioid Misuse and Addiction",
                # Drug safety
                "https://medlineplus.gov/drugreactions.html": "Drug Reactions",
                "https://medlineplus.gov/druginteractions.html": "Drug Interactions",
                # Supplements and herbal
                "https://medlineplus.gov/herbalremedies.html": "Herbal Remedies",
                "https://medlineplus.gov/dietarysupplements.html": "Dietary Supplements",
                # Vitamins
                "https://medlineplus.gov/vitamins.html": "Vitamins",
                "https://medlineplus.gov/vitamina.html": "Vitamin A",
                "https://medlineplus.gov/vitaminb6.html": "Vitamin B6",
                "https://medlineplus.gov/vitaminb12.html": "Vitamin B12",
                "https://medlineplus.gov/vitaminc.html": "Vitamin C",
                "https://medlineplus.gov/vitamind.html": "Vitamin D",
                "https://medlineplus.gov/vitamine.html": "Vitamin E",
                "https://medlineplus.gov/vitamink.html": "Vitamin K",
                "https://medlineplus.gov/folicacid.html": "Folic Acid",
                # Minerals
                "https://medlineplus.gov/iron.html": "Iron",
                "https://medlineplus.gov/calcium.html": "Calcium",
                "https://medlineplus.gov/magnesium.html": "Magnesium",
                "https://medlineplus.gov/zinc.html": "Zinc",
                "https://medlineplus.gov/potassium.html": "Potassium",
                # Other supplements
                "https://medlineplus.gov/omega3supplements.html": "Omega-3 Supplements",
                "https://medlineplus.gov/probiotics.html": "Probiotics",
                "https://medlineplus.gov/antioxidants.html": "Antioxidants",
                # Substance use
                "https://medlineplus.gov/druguse.html": "Drug Use and Addiction",
                "https://medlineplus.gov/alcoholism.html": "Alcohol Use Disorder",
                "https://medlineplus.gov/alcohol.html": "Alcohol",
                "https://medlineplus.gov/binge.html": "Binge Drinking",
                "https://medlineplus.gov/marijuana.html": "Marijuana",
                "https://medlineplus.gov/cocaine.html": "Cocaine",
                "https://medlineplus.gov/methamphetamine.html": "Methamphetamine",
                "https://medlineplus.gov/anabolicsteroids.html": "Anabolic Steroids",
                "https://medlineplus.gov/inhalants.html": "Inhalants",
                # Smoking and tobacco
                "https://medlineplus.gov/smokingcessation.html": "Smoking Cessation",
                "https://medlineplus.gov/smoking.html": "Smoking",
                "https://medlineplus.gov/ecigarettes.html": "E-Cigarettes",
                # Other
                "https://medlineplus.gov/caffeine.html": "Caffeine",
                "https://medlineplus.gov/melatonin.html": "Melatonin",
                # Additional drug classes and supplements
                "https://medlineplus.gov/benzodiazepines.html": "Benzodiazepines",
                "https://medlineplus.gov/nsaids.html": "NSAIDs",
                "https://medlineplus.gov/betablockers.html": "Beta Blockers",
                "https://medlineplus.gov/aceinhibitors.html": "ACE Inhibitors",
                "https://medlineplus.gov/diuretics.html": "Diuretics",
                "https://medlineplus.gov/insulins.html": "Insulin",
                "https://medlineplus.gov/corticosteroids.html": "Corticosteroids",
                "https://medlineplus.gov/antihistamines.html": "Antihistamines",
                "https://medlineplus.gov/antifungals.html": "Antifungals",
                "https://medlineplus.gov/antivirals.html": "Antivirals",
                "https://medlineplus.gov/hormones.html": "Hormones",
                "https://medlineplus.gov/hormonereplacementtherapy.html": "Hormone Replacement Therapy",
                "https://medlineplus.gov/drugsafety.html": "Drug Safety",
                "https://medlineplus.gov/genericdrugs.html": "Generic Drugs",
                "https://medlineplus.gov/herbalmedicine.html": "Herbal Medicine",
                "https://medlineplus.gov/selenium.html": "Selenium",
                "https://medlineplus.gov/chromium.html": "Chromium Supplements",
                "https://medlineplus.gov/glucosamine.html": "Glucosamine",
            },
        },
        "genetics": {
            "pages": {
                # Overview
                "https://medlineplus.gov/genetics/": "Genetics Home Reference",
                "https://medlineplus.gov/genetics/understanding/": "Help Me Understand Genetics",
                # Basics
                "https://medlineplus.gov/genetics/understanding/basics/": "Genetics Basics",
                "https://medlineplus.gov/genetics/understanding/basics/dna/": "What is DNA?",
                "https://medlineplus.gov/genetics/understanding/basics/gene/": "What is a Gene?",
                "https://medlineplus.gov/genetics/understanding/basics/chromosome/": "What is a Chromosome?",
                "https://medlineplus.gov/genetics/understanding/basics/protein/": "How Genes Make Proteins",
                "https://medlineplus.gov/genetics/understanding/basics/cell/": "Cells and DNA",
                "https://medlineplus.gov/genetics/understanding/basics/variants/": "What are Gene Variants?",
                # How genes work
                "https://medlineplus.gov/genetics/understanding/howgeneswork/": "How Genes Work",
                "https://medlineplus.gov/genetics/understanding/howgeneswork/makingprotein/": "How Genes Direct Protein Production",
                "https://medlineplus.gov/genetics/understanding/howgeneswork/epigenome/": "What is Epigenomics?",
                # Inheritance
                "https://medlineplus.gov/genetics/understanding/inheritance/": "Inheritance Patterns",
                "https://medlineplus.gov/genetics/understanding/inheritance/inheritancepatterns/": "Inheritance Patterns",
                "https://medlineplus.gov/genetics/understanding/inheritance/mutations/": "How Mutations Cause Disorders",
                "https://medlineplus.gov/genetics/understanding/inheritance/riskassessment/": "Risk Assessment",
                # Genetic testing
                "https://medlineplus.gov/genetics/understanding/testing/": "Genetic Testing",
                "https://medlineplus.gov/genetics/understanding/testing/genetictesting/": "What is Genetic Testing?",
                "https://medlineplus.gov/genetics/understanding/testing/results/": "Understanding Test Results",
                "https://medlineplus.gov/genetics/understanding/testing/directtoconsumer/": "Direct-to-Consumer Tests",
                # Gene therapy
                "https://medlineplus.gov/genetics/understanding/therapy/": "Gene Therapy",
                "https://medlineplus.gov/genetics/understanding/therapy/genetherapy/": "What is Gene Therapy?",
                # Genomic research
                "https://medlineplus.gov/genetics/understanding/genomicresearch/": "Genomic Research",
                "https://medlineplus.gov/genetics/understanding/genomicresearch/genomeediting/": "Genome Editing",
                "https://medlineplus.gov/genetics/understanding/genomicresearch/snp/": "What are SNPs?",
                "https://medlineplus.gov/genetics/understanding/genomicresearch/pharmacogenomics/": "Pharmacogenomics",
                # Precision medicine
                "https://medlineplus.gov/genetics/understanding/precisionmedicine/": "Precision Medicine",
                # Genetic conditions
                "https://medlineplus.gov/genetics/condition/": "Genetic Conditions",
                "https://medlineplus.gov/genetics/condition/cystic-fibrosis/": "Cystic Fibrosis Genetics",
                "https://medlineplus.gov/genetics/condition/sickle-cell-disease/": "Sickle Cell Disease Genetics",
                "https://medlineplus.gov/genetics/condition/huntington-disease/": "Huntington Disease Genetics",
                "https://medlineplus.gov/genetics/condition/down-syndrome/": "Down Syndrome Genetics",
                "https://medlineplus.gov/genetics/condition/fragile-x-syndrome/": "Fragile X Syndrome",
                "https://medlineplus.gov/genetics/condition/turner-syndrome/": "Turner Syndrome",
                "https://medlineplus.gov/genetics/condition/klinefelter-syndrome/": "Klinefelter Syndrome",
                "https://medlineplus.gov/genetics/condition/marfan-syndrome/": "Marfan Syndrome",
                "https://medlineplus.gov/genetics/condition/phenylketonuria/": "Phenylketonuria",
                "https://medlineplus.gov/genetics/condition/tay-sachs-disease/": "Tay-Sachs Disease",
                "https://medlineplus.gov/genetics/condition/hemophilia/": "Hemophilia Genetics",
                "https://medlineplus.gov/genetics/condition/muscular-dystrophy/": "Muscular Dystrophy Genetics",
                "https://medlineplus.gov/genetics/condition/spinal-muscular-atrophy/": "Spinal Muscular Atrophy",
                "https://medlineplus.gov/genetics/condition/achondroplasia/": "Achondroplasia",
                "https://medlineplus.gov/genetics/condition/albinism/": "Albinism",
                "https://medlineplus.gov/genetics/condition/celiac-disease/": "Celiac Disease Genetics",
                "https://medlineplus.gov/genetics/condition/breast-cancer/": "Breast Cancer Genetics",
                "https://medlineplus.gov/genetics/condition/lynch-syndrome/": "Lynch Syndrome",
                "https://medlineplus.gov/genetics/condition/familial-hypercholesterolemia/": "Familial Hypercholesterolemia",
                "https://medlineplus.gov/genetics/condition/type-1-diabetes/": "Type 1 Diabetes Genetics",
                "https://medlineplus.gov/genetics/condition/type-2-diabetes/": "Type 2 Diabetes Genetics",
                "https://medlineplus.gov/genetics/condition/alzheimer-disease/": "Alzheimer Disease Genetics",
                "https://medlineplus.gov/genetics/condition/parkinson-disease/": "Parkinson Disease Genetics",
                "https://medlineplus.gov/genetics/condition/autism-spectrum-disorder/": "ASD Genetics",
                # Genes
                "https://medlineplus.gov/genetics/gene/": "Gene Index",
                "https://medlineplus.gov/genetics/gene/BRCA1/": "BRCA1 Gene",
                "https://medlineplus.gov/genetics/gene/BRCA2/": "BRCA2 Gene",
                "https://medlineplus.gov/genetics/gene/CFTR/": "CFTR Gene",
                "https://medlineplus.gov/genetics/gene/TP53/": "TP53 Gene",
                "https://medlineplus.gov/genetics/gene/APOE/": "APOE Gene",
                "https://medlineplus.gov/genetics/gene/HTT/": "HTT Gene",
                # Chromosomes
                "https://medlineplus.gov/genetics/chromosome/": "Chromosome Index",
                "https://medlineplus.gov/genetics/chromosome/1/": "Chromosome 1",
                "https://medlineplus.gov/genetics/chromosome/x/": "X Chromosome",
                "https://medlineplus.gov/genetics/chromosome/y/": "Y Chromosome",
                "https://medlineplus.gov/genetics/chromosome/mitochondrial-dna/": "Mitochondrial DNA",
            },
        },
        "medical-tests": {
            "pages": {
                # Overview
                "https://medlineplus.gov/laboratorytests.html": "Laboratory Tests",
                "https://medlineplus.gov/lab-tests/": "Lab Tests Index",
                # Blood panels
                "https://medlineplus.gov/lab-tests/complete-blood-count-cbc/": "Complete Blood Count",
                "https://medlineplus.gov/lab-tests/comprehensive-metabolic-panel-cmp/": "Comprehensive Metabolic Panel",
                "https://medlineplus.gov/lab-tests/basic-metabolic-panel-bmp/": "Basic Metabolic Panel",
                "https://medlineplus.gov/lab-tests/lipid-panel/": "Lipid Panel",
                # Diabetes tests
                "https://medlineplus.gov/lab-tests/hemoglobin-a1c-hba1c-test/": "Hemoglobin A1C Test",
                "https://medlineplus.gov/lab-tests/blood-glucose-test/": "Blood Glucose Test",
                # Organ function
                "https://medlineplus.gov/lab-tests/thyroid-function-tests/": "Thyroid Function Tests",
                "https://medlineplus.gov/lab-tests/liver-function-tests/": "Liver Function Tests",
                "https://medlineplus.gov/lab-tests/kidney-function-tests/": "Kidney Function Tests",
                # Urine and blood
                "https://medlineplus.gov/lab-tests/urinalysis/": "Urinalysis",
                "https://medlineplus.gov/lab-tests/blood-typing/": "Blood Typing",
                # Inflammation markers
                "https://medlineplus.gov/lab-tests/c-reactive-protein-crp-test/": "CRP Test",
                "https://medlineplus.gov/lab-tests/erythrocyte-sedimentation-rate-esr/": "ESR Test",
                # Coagulation
                "https://medlineplus.gov/lab-tests/prothrombin-time-test-and-inr-ptinr/": "PT/INR Test",
                # Cancer screening
                "https://medlineplus.gov/lab-tests/psa-test/": "PSA Test",
                "https://medlineplus.gov/lab-tests/pap-smear/": "Pap Smear",
                "https://medlineplus.gov/lab-tests/hpv-test/": "HPV Test",
                # Other specific tests
                "https://medlineplus.gov/lab-tests/pregnancy-test/": "Pregnancy Test",
                "https://medlineplus.gov/lab-tests/vitamin-d-test/": "Vitamin D Test",
                "https://medlineplus.gov/lab-tests/vitamin-b-test/": "Vitamin B Test",
                "https://medlineplus.gov/lab-tests/iron-tests/": "Iron Tests",
                "https://medlineplus.gov/lab-tests/electrolyte-panel/": "Electrolyte Panel",
                "https://medlineplus.gov/lab-tests/cortisol-test/": "Cortisol Test",
                "https://medlineplus.gov/lab-tests/testosterone-levels-test/": "Testosterone Test",
                "https://medlineplus.gov/lab-tests/estrogen-levels-test/": "Estrogen Test",
                "https://medlineplus.gov/lab-tests/allergy-blood-test/": "Allergy Blood Test",
                "https://medlineplus.gov/lab-tests/blood-culture/": "Blood Culture",
                "https://medlineplus.gov/lab-tests/stool-test/": "Stool Test",
                "https://medlineplus.gov/lab-tests/drug-testing/": "Drug Testing",
                "https://medlineplus.gov/lab-tests/genetic-testing/": "Genetic Testing",
                # Procedures
                "https://medlineplus.gov/lab-tests/biopsy/": "Biopsy",
                # Imaging
                "https://medlineplus.gov/lab-tests/mri-scan/": "MRI Scan",
                "https://medlineplus.gov/lab-tests/ct-scan/": "CT Scan",
                "https://medlineplus.gov/lab-tests/ultrasound/": "Ultrasound",
                "https://medlineplus.gov/lab-tests/x-ray/": "X-Ray",
                # Cardiac tests
                "https://medlineplus.gov/lab-tests/echocardiogram/": "Echocardiogram",
                "https://medlineplus.gov/lab-tests/electrocardiogram/": "Electrocardiogram (ECG)",
                "https://medlineplus.gov/lab-tests/eeg-electroencephalogram/": "EEG",
                # Additional blood tests
                "https://medlineplus.gov/lab-tests/blood-smear/": "Blood Smear",
                "https://medlineplus.gov/lab-tests/creatinine-test/": "Creatinine Test",
                "https://medlineplus.gov/lab-tests/bun-blood-urea-nitrogen/": "BUN Test",
                "https://medlineplus.gov/lab-tests/ferritin-blood-test/": "Ferritin Test",
                "https://medlineplus.gov/lab-tests/troponin-test/": "Troponin Test",
            },
        },
        "medical-encyclopedia": {
            "pages": {
                # Aging
                "https://medlineplus.gov/ency/article/002016.htm": "Aging Changes in the Heart and Blood Vessels",
                "https://medlineplus.gov/ency/article/004006.htm": "Aging Changes in the Lungs",
                "https://medlineplus.gov/ency/article/004013.htm": "Aging Changes in Organs, Tissues, and Cells",
                # Serious conditions
                "https://medlineplus.gov/ency/article/000141.htm": "Pulmonary Embolism",
                "https://medlineplus.gov/ency/article/000468.htm": "Acute Kidney Failure",
                "https://medlineplus.gov/ency/article/000471.htm": "Chronic Kidney Disease",
                # Digestive
                "https://medlineplus.gov/ency/article/000236.htm": "Peptic Ulcer",
                "https://medlineplus.gov/ency/article/000255.htm": "Gastritis",
                "https://medlineplus.gov/ency/article/000243.htm": "Diverticulitis",
                # Endocrine
                "https://medlineplus.gov/ency/article/001158.htm": "Hypothyroidism",
                "https://medlineplus.gov/ency/article/000356.htm": "Hyperthyroidism",
                # Emergency
                "https://medlineplus.gov/ency/article/000584.htm": "Anaphylaxis",
                # Respiratory
                "https://medlineplus.gov/ency/article/000091.htm": "Pneumothorax",
                # Cardiovascular
                "https://medlineplus.gov/ency/article/000164.htm": "Pericarditis",
                "https://medlineplus.gov/ency/article/000149.htm": "Atrial Fibrillation",
                "https://medlineplus.gov/ency/article/000195.htm": "Deep Vein Thrombosis",
                "https://medlineplus.gov/ency/article/000162.htm": "Aortic Aneurysm",
                # Neurological
                "https://medlineplus.gov/ency/article/000726.htm": "Bell's Palsy",
                "https://medlineplus.gov/ency/article/000737.htm": "Guillain-Barre Syndrome",
                # Environmental
                "https://medlineplus.gov/ency/article/000434.htm": "Hypothermia",
                "https://medlineplus.gov/ency/article/000056.htm": "Heat Stroke",
                # Common symptoms
                "https://medlineplus.gov/ency/article/003090.htm": "Chest Pain",
                "https://medlineplus.gov/ency/article/003093.htm": "Abdominal Pain",
                "https://medlineplus.gov/ency/article/003024.htm": "Headache",
                "https://medlineplus.gov/ency/article/003088.htm": "Fatigue",
                "https://medlineplus.gov/ency/article/003079.htm": "Nausea and Vomiting",
                "https://medlineplus.gov/ency/article/003126.htm": "Dizziness",
                "https://medlineplus.gov/ency/article/003200.htm": "Joint Pain",
                "https://medlineplus.gov/ency/article/003178.htm": "Muscle Cramps",
                "https://medlineplus.gov/ency/article/000894.htm": "Carpal Tunnel Syndrome",
                # First aid and emergency
                "https://medlineplus.gov/ency/article/000052.htm": "Poisoning",
                "https://medlineplus.gov/ency/article/000024.htm": "Burns",
                "https://medlineplus.gov/ency/article/000043.htm": "Fractures",
                "https://medlineplus.gov/ency/article/000028.htm": "Shock",
                "https://medlineplus.gov/ency/article/000022.htm": "Choking",
                "https://medlineplus.gov/ency/article/000013.htm": "CPR",
                # Nutrition and diet
                "https://medlineplus.gov/ency/article/007165.htm": "Body Mass Index",
                "https://medlineplus.gov/ency/article/002393.htm": "Balanced Diet",
                "https://medlineplus.gov/ency/article/002399.htm": "Carbohydrates",
                "https://medlineplus.gov/ency/article/002467.htm": "Protein in Diet",
                "https://medlineplus.gov/ency/article/002468.htm": "Fats",
                "https://medlineplus.gov/ency/article/002469.htm": "Fiber",
                "https://medlineplus.gov/ency/article/002401.htm": "Cholesterol",
                "https://medlineplus.gov/ency/article/002404.htm": "Sodium",
                "https://medlineplus.gov/ency/article/002403.htm": "Potassium in Diet",
                # Vitamins (encyclopedia articles)
                "https://medlineplus.gov/ency/article/002422.htm": "Vitamin A",
                "https://medlineplus.gov/ency/article/002405.htm": "Vitamin C",
                "https://medlineplus.gov/ency/article/002407.htm": "Vitamin E",
                "https://medlineplus.gov/ency/article/007478.htm": "Vitamin D",
                # Infections and immune
                "https://medlineplus.gov/ency/article/000080.htm": "Lung Abscess",
                "https://medlineplus.gov/ency/article/000610.htm": "Cellulitis",
                "https://medlineplus.gov/ency/article/001362.htm": "Impetigo",
                "https://medlineplus.gov/ency/article/000859.htm": "Herpes Simplex",
                "https://medlineplus.gov/ency/article/001349.htm": "Scabies",
                "https://medlineplus.gov/ency/article/000104.htm": "Bronchiectasis",
                "https://medlineplus.gov/ency/article/000083.htm": "Pleurisy",
                "https://medlineplus.gov/ency/article/000834.htm": "Ringworm",
                "https://medlineplus.gov/ency/article/001511.htm": "Athlete's Foot",
                "https://medlineplus.gov/ency/article/000628.htm": "Abscess",
                # Musculoskeletal
                "https://medlineplus.gov/ency/article/000420.htm": "Osteoporosis",
                "https://medlineplus.gov/ency/article/000423.htm": "Paget Disease of Bone",
                "https://medlineplus.gov/ency/article/000419.htm": "Osteomyelitis",
                "https://medlineplus.gov/ency/article/000256.htm": "Acute Pancreatitis",
                "https://medlineplus.gov/ency/article/000221.htm": "Chronic Pancreatitis",
                # Mental health
                "https://medlineplus.gov/ency/article/003213.htm": "Delirium",
                "https://medlineplus.gov/ency/article/000740.htm": "Insomnia",
                "https://medlineplus.gov/ency/article/000954.htm": "Generalized Anxiety Disorder",
                "https://medlineplus.gov/ency/article/000925.htm": "Panic Disorder",
                "https://medlineplus.gov/ency/article/001549.htm": "Social Anxiety Disorder",
                # Eye and ear
                "https://medlineplus.gov/ency/article/001001.htm": "Cataracts",
                "https://medlineplus.gov/ency/article/001620.htm": "Glaucoma",
                "https://medlineplus.gov/ency/article/001014.htm": "Retinal Detachment",
                "https://medlineplus.gov/ency/article/001054.htm": "Ear Infections",
                "https://medlineplus.gov/ency/article/003043.htm": "Tinnitus",
            },
        },
        "healthy-living": {
            "pages": {
                # Exercise
                "https://medlineplus.gov/exerciseandphysicalfitness.html": "Exercise and Physical Fitness",
                "https://medlineplus.gov/exerciseforchildren.html": "Exercise for Children",
                "https://medlineplus.gov/exerciseforseniors.html": "Exercise for Seniors",
                "https://medlineplus.gov/walkingforexercise.html": "Walking for Exercise",
                "https://medlineplus.gov/yoga.html": "Yoga",
                # Nutrition
                "https://medlineplus.gov/nutrition.html": "Nutrition",
                "https://medlineplus.gov/nutritionforseniors.html": "Nutrition for Seniors",
                "https://medlineplus.gov/childnutrition.html": "Child Nutrition",
                "https://medlineplus.gov/foodsafety.html": "Food Safety",
                # Weight management
                "https://medlineplus.gov/weightcontrol.html": "Weight Control",
                "https://medlineplus.gov/diets.html": "Diets",
                # Aging
                "https://medlineplus.gov/healthyaging.html": "Healthy Aging",
                "https://medlineplus.gov/seniorshealth.html": "Seniors' Health",
                # Mental wellness
                "https://medlineplus.gov/mentalhealth.html": "Mental Health",
                "https://medlineplus.gov/stress.html": "Stress",
                "https://medlineplus.gov/resilience.html": "Resilience",
                "https://medlineplus.gov/wellness.html": "Wellness",
                # Preventive care
                "https://medlineplus.gov/healthscreening.html": "Health Screening",
                "https://medlineplus.gov/immunization.html": "Immunization",
                "https://medlineplus.gov/vaccinations.html": "Vaccinations",
                "https://medlineplus.gov/fluvaccination.html": "Flu Vaccination",
                # Pregnancy and child care
                "https://medlineplus.gov/prenatalcare.html": "Prenatal Care",
                "https://medlineplus.gov/breastfeeding.html": "Breastfeeding",
                "https://medlineplus.gov/infantandnewborncare.html": "Infant and Newborn Care",
                "https://medlineplus.gov/childdevelopment.html": "Child Development",
                "https://medlineplus.gov/teenhealth.html": "Teen Health",
                # Gender-specific health
                "https://medlineplus.gov/menshealth.html": "Men's Health",
                "https://medlineplus.gov/womenshealth.html": "Women's Health",
                # Self-care
                "https://medlineplus.gov/healthyleep.html": "Healthy Sleep",
                "https://medlineplus.gov/gumsandteeth.html": "Gums and Teeth",
                "https://medlineplus.gov/eyecare.html": "Eye Care",
                "https://medlineplus.gov/skincare.html": "Skin Care",
                "https://medlineplus.gov/sunexposure.html": "Sun Exposure",
                # Safety
                "https://medlineplus.gov/falls.html": "Falls",
                "https://medlineplus.gov/poisonprevention.html": "Poison Prevention",
                "https://medlineplus.gov/firstaid.html": "First Aid",
                "https://medlineplus.gov/travelhealth.html": "Travel Health",
                "https://medlineplus.gov/occupationalhealth.html": "Occupational Health",
                "https://medlineplus.gov/personalhealth.html": "Personal Health Issues",
                "https://medlineplus.gov/healthyweight.html": "Healthy Weight",
                # Treatments and therapies
                "https://medlineplus.gov/bloodpressuremedicines.html": "Blood Pressure Medicines",
                "https://medlineplus.gov/physicaltherapy.html": "Physical Therapy",
                # Complementary medicine
                "https://medlineplus.gov/complementaryandintegrativemedicine.html": "Complementary and Integrative Medicine",
                "https://medlineplus.gov/acupuncture.html": "Acupuncture",
                "https://medlineplus.gov/chiropractic.html": "Chiropractic",
                "https://medlineplus.gov/meditation.html": "Meditation",
                "https://medlineplus.gov/tai-chi.html": "Tai Chi",
                # Additional healthy living topics
                "https://medlineplus.gov/germsandhygiene.html": "Germs and Hygiene",
                "https://medlineplus.gov/handwashing.html": "Handwashing",
                "https://medlineplus.gov/waterquality.html": "Water Quality",
                "https://medlineplus.gov/airpollution.html": "Air Pollution",
                "https://medlineplus.gov/childmentalhealth.html": "Child Mental Health",
                "https://medlineplus.gov/teenmentalhealth.html": "Teen Mental Health",
                "https://medlineplus.gov/suicide.html": "Suicide",
                "https://medlineplus.gov/suicideprevention.html": "Suicide Prevention",
                "https://medlineplus.gov/domesticviolence.html": "Domestic Violence",
                "https://medlineplus.gov/childabuse.html": "Child Abuse",
                "https://medlineplus.gov/elderabuse.html": "Elder Abuse",
                "https://medlineplus.gov/healthliteracy.html": "Health Literacy",
                "https://medlineplus.gov/patientrights.html": "Patient Rights",
                "https://medlineplus.gov/healthinsurance.html": "Health Insurance",
                "https://medlineplus.gov/managingchronicillness.html": "Managing Chronic Illness",
                "https://medlineplus.gov/painmanagement.html": "Pain Management",
                "https://medlineplus.gov/palliativecare.html": "Palliative Care",
                "https://medlineplus.gov/endoflife.html": "End of Life Issues",
                "https://medlineplus.gov/advancedirectives.html": "Advance Directives",
                "https://medlineplus.gov/organtransplantation.html": "Organ Transplantation",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"medlineplus-{source_key}" if source_key else "medlineplus"
        super().__init__(name, base_dir, interval_seconds=3600)
        self.source_key = source_key

    def _strip_html(self, html_content):
        """Remove HTML tags, scripts, styles, nav, header, footer, sidebar and normalize whitespace."""
        text = html_content
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
        text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL)
        text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL)
        text = re.sub(r'<aside[^>]*>.*?</aside>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html_mod.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _extract_title(self, html_content, fallback):
        """Extract page title from HTML."""
        match = re.search(r'<title>([^<]+)</title>', html_content, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            # Clean common suffixes
            for suffix in [' - MedlinePlus Medical Encyclopedia', ' - MedlinePlus', ' | MedlinePlus']:
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
                        "category": f"medlineplus-{source_key}",
                        "type": "documentation",
                    }):
                        count += 1
                        self.log.info(f"  {source_key}: {title}")

            time.sleep(2.0)  # Respectful rate limit for NIH

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
            self.log.info(f"=== Scraping medlineplus/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    MedlinePlusScraper(base, source_key).run()
