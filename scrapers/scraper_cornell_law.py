#!/usr/bin/env python3
"""Cornell Law Institute scraper.

Covers:
  - Wex Legal Encyclopedia: major legal topics and definitions
  - Constitution: articles, amendments, and commentary
  - Supreme Court: landmark cases overview pages
  - UCC: Uniform Commercial Code articles overview
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class CornellLawScraper(BaseScraper):
    """Scrape Cornell Law Institute Wex encyclopedia, Constitution, and landmark cases."""

    SOURCES = {
        "wex-contracts": {
            "pages": {
                "https://www.law.cornell.edu/wex/contract": "Contract",
                "https://www.law.cornell.edu/wex/consideration": "Consideration",
                "https://www.law.cornell.edu/wex/offer": "Offer",
                "https://www.law.cornell.edu/wex/acceptance": "Acceptance",
                "https://www.law.cornell.edu/wex/breach_of_contract": "Breach of Contract",
                "https://www.law.cornell.edu/wex/damages": "Damages",
                "https://www.law.cornell.edu/wex/specific_performance": "Specific Performance",
                "https://www.law.cornell.edu/wex/statute_of_frauds": "Statute of Frauds",
                "https://www.law.cornell.edu/wex/promissory_estoppel": "Promissory Estoppel",
                "https://www.law.cornell.edu/wex/unconscionability": "Unconscionability",
                "https://www.law.cornell.edu/wex/capacity": "Capacity",
                "https://www.law.cornell.edu/wex/duress": "Duress",
                "https://www.law.cornell.edu/wex/undue_influence": "Undue Influence",
                "https://www.law.cornell.edu/wex/fraud": "Fraud",
                "https://www.law.cornell.edu/wex/misrepresentation": "Misrepresentation",
                "https://www.law.cornell.edu/wex/condition": "Condition (Contract Law)",
                "https://www.law.cornell.edu/wex/assignment": "Assignment",
                "https://www.law.cornell.edu/wex/third_party_beneficiary": "Third Party Beneficiary",
                "https://www.law.cornell.edu/wex/parol_evidence_rule": "Parol Evidence Rule",
                "https://www.law.cornell.edu/wex/liquidated_damages": "Liquidated Damages",
                "https://www.law.cornell.edu/wex/covenant_not_to_compete": "Covenant Not to Compete",
                "https://www.law.cornell.edu/wex/quasi-contract": "Quasi-Contract",
                "https://www.law.cornell.edu/wex/unjust_enrichment": "Unjust Enrichment",
            },
        },
        "wex-torts": {
            "pages": {
                "https://www.law.cornell.edu/wex/tort": "Tort",
                "https://www.law.cornell.edu/wex/negligence": "Negligence",
                "https://www.law.cornell.edu/wex/duty_of_care": "Duty of Care",
                "https://www.law.cornell.edu/wex/proximate_cause": "Proximate Cause",
                "https://www.law.cornell.edu/wex/strict_liability": "Strict Liability",
                "https://www.law.cornell.edu/wex/product_liability": "Product Liability",
                "https://www.law.cornell.edu/wex/defamation": "Defamation",
                "https://www.law.cornell.edu/wex/libel": "Libel",
                "https://www.law.cornell.edu/wex/slander": "Slander",
                "https://www.law.cornell.edu/wex/intentional_tort": "Intentional Tort",
                "https://www.law.cornell.edu/wex/battery": "Battery",
                "https://www.law.cornell.edu/wex/assault": "Assault",
                "https://www.law.cornell.edu/wex/trespass": "Trespass",
                "https://www.law.cornell.edu/wex/nuisance": "Nuisance",
                "https://www.law.cornell.edu/wex/conversion": "Conversion",
                "https://www.law.cornell.edu/wex/negligence_per_se": "Negligence Per Se",
                "https://www.law.cornell.edu/wex/contributory_negligence": "Contributory Negligence",
                "https://www.law.cornell.edu/wex/comparative_negligence": "Comparative Negligence",
                "https://www.law.cornell.edu/wex/assumption_of_risk": "Assumption of Risk",
                "https://www.law.cornell.edu/wex/respondeat_superior": "Respondeat Superior",
                "https://www.law.cornell.edu/wex/wrongful_death": "Wrongful Death",
                "https://www.law.cornell.edu/wex/malpractice": "Malpractice",
            },
        },
        "wex-property": {
            "pages": {
                "https://www.law.cornell.edu/wex/property": "Property",
                "https://www.law.cornell.edu/wex/real_property": "Real Property",
                "https://www.law.cornell.edu/wex/personal_property": "Personal Property",
                "https://www.law.cornell.edu/wex/deed": "Deed",
                "https://www.law.cornell.edu/wex/easement": "Easement",
                "https://www.law.cornell.edu/wex/eminent_domain": "Eminent Domain",
                "https://www.law.cornell.edu/wex/adverse_possession": "Adverse Possession",
                "https://www.law.cornell.edu/wex/landlord-tenant_law": "Landlord-Tenant Law",
                "https://www.law.cornell.edu/wex/lease": "Lease",
                "https://www.law.cornell.edu/wex/zoning": "Zoning",
                "https://www.law.cornell.edu/wex/mortgage": "Mortgage",
                "https://www.law.cornell.edu/wex/lien": "Lien",
                "https://www.law.cornell.edu/wex/title": "Title",
                "https://www.law.cornell.edu/wex/fixture": "Fixture",
                "https://www.law.cornell.edu/wex/covenant": "Covenant",
            },
        },
        "wex-criminal": {
            "pages": {
                "https://www.law.cornell.edu/wex/criminal_law": "Criminal Law",
                "https://www.law.cornell.edu/wex/felony": "Felony",
                "https://www.law.cornell.edu/wex/misdemeanor": "Misdemeanor",
                "https://www.law.cornell.edu/wex/mens_rea": "Mens Rea",
                "https://www.law.cornell.edu/wex/actus_reus": "Actus Reus",
                "https://www.law.cornell.edu/wex/homicide": "Homicide",
                "https://www.law.cornell.edu/wex/murder": "Murder",
                "https://www.law.cornell.edu/wex/manslaughter": "Manslaughter",
                "https://www.law.cornell.edu/wex/robbery": "Robbery",
                "https://www.law.cornell.edu/wex/burglary": "Burglary",
                "https://www.law.cornell.edu/wex/larceny": "Larceny",
                "https://www.law.cornell.edu/wex/arson": "Arson",
                "https://www.law.cornell.edu/wex/conspiracy": "Conspiracy",
                "https://www.law.cornell.edu/wex/self-defense": "Self-Defense",
                "https://www.law.cornell.edu/wex/insanity_defense": "Insanity Defense",
                "https://www.law.cornell.edu/wex/entrapment": "Entrapment",
                "https://www.law.cornell.edu/wex/double_jeopardy": "Double Jeopardy",
                "https://www.law.cornell.edu/wex/plea_bargain": "Plea Bargain",
                "https://www.law.cornell.edu/wex/sentencing": "Sentencing",
                "https://www.law.cornell.edu/wex/probation": "Probation",
                "https://www.law.cornell.edu/wex/parole": "Parole",
                "https://www.law.cornell.edu/wex/habeas_corpus": "Habeas Corpus",
                "https://www.law.cornell.edu/wex/exclusionary_rule": "Exclusionary Rule",
                "https://www.law.cornell.edu/wex/miranda_warning": "Miranda Warning",
            },
        },
        "wex-constitutional": {
            "pages": {
                "https://www.law.cornell.edu/wex/constitutional_law": "Constitutional Law",
                "https://www.law.cornell.edu/wex/due_process": "Due Process",
                "https://www.law.cornell.edu/wex/equal_protection": "Equal Protection",
                "https://www.law.cornell.edu/wex/commerce_clause": "Commerce Clause",
                "https://www.law.cornell.edu/wex/separation_of_powers": "Separation of Powers",
                "https://www.law.cornell.edu/wex/federalism": "Federalism",
                "https://www.law.cornell.edu/wex/judicial_review": "Judicial Review",
                "https://www.law.cornell.edu/wex/first_amendment": "First Amendment",
                "https://www.law.cornell.edu/wex/freedom_of_speech": "Freedom of Speech",
                "https://www.law.cornell.edu/wex/freedom_of_religion": "Freedom of Religion",
                "https://www.law.cornell.edu/wex/establishment_clause": "Establishment Clause",
                "https://www.law.cornell.edu/wex/free_exercise_clause": "Free Exercise Clause",
                "https://www.law.cornell.edu/wex/freedom_of_the_press": "Freedom of the Press",
                "https://www.law.cornell.edu/wex/right_to_assemble": "Right to Assemble",
                "https://www.law.cornell.edu/wex/second_amendment": "Second Amendment",
                "https://www.law.cornell.edu/wex/fourth_amendment": "Fourth Amendment",
                "https://www.law.cornell.edu/wex/search_and_seizure": "Search and Seizure",
                "https://www.law.cornell.edu/wex/fifth_amendment": "Fifth Amendment",
                "https://www.law.cornell.edu/wex/self-incrimination": "Self-Incrimination",
                "https://www.law.cornell.edu/wex/sixth_amendment": "Sixth Amendment",
                "https://www.law.cornell.edu/wex/right_to_counsel": "Right to Counsel",
                "https://www.law.cornell.edu/wex/eighth_amendment": "Eighth Amendment",
                "https://www.law.cornell.edu/wex/cruel_and_unusual_punishment": "Cruel and Unusual Punishment",
                "https://www.law.cornell.edu/wex/fourteenth_amendment": "Fourteenth Amendment",
                "https://www.law.cornell.edu/wex/privileges_and_immunities_clause": "Privileges and Immunities Clause",
                "https://www.law.cornell.edu/wex/supremacy_clause": "Supremacy Clause",
                "https://www.law.cornell.edu/wex/standing": "Standing",
                "https://www.law.cornell.edu/wex/strict_scrutiny": "Strict Scrutiny",
                "https://www.law.cornell.edu/wex/rational_basis_test": "Rational Basis Test",
                "https://www.law.cornell.edu/wex/intermediate_scrutiny": "Intermediate Scrutiny",
            },
        },
        "wex-procedure": {
            "pages": {
                "https://www.law.cornell.edu/wex/civil_procedure": "Civil Procedure",
                "https://www.law.cornell.edu/wex/jurisdiction": "Jurisdiction",
                "https://www.law.cornell.edu/wex/personal_jurisdiction": "Personal Jurisdiction",
                "https://www.law.cornell.edu/wex/subject_matter_jurisdiction": "Subject Matter Jurisdiction",
                "https://www.law.cornell.edu/wex/diversity_jurisdiction": "Diversity Jurisdiction",
                "https://www.law.cornell.edu/wex/federal_question_jurisdiction": "Federal Question Jurisdiction",
                "https://www.law.cornell.edu/wex/venue": "Venue",
                "https://www.law.cornell.edu/wex/complaint": "Complaint",
                "https://www.law.cornell.edu/wex/answer": "Answer",
                "https://www.law.cornell.edu/wex/discovery": "Discovery",
                "https://www.law.cornell.edu/wex/deposition": "Deposition",
                "https://www.law.cornell.edu/wex/summary_judgment": "Summary Judgment",
                "https://www.law.cornell.edu/wex/class_action": "Class Action",
                "https://www.law.cornell.edu/wex/res_judicata": "Res Judicata",
                "https://www.law.cornell.edu/wex/collateral_estoppel": "Collateral Estoppel",
                "https://www.law.cornell.edu/wex/statute_of_limitations": "Statute of Limitations",
                "https://www.law.cornell.edu/wex/injunction": "Injunction",
                "https://www.law.cornell.edu/wex/appeal": "Appeal",
                "https://www.law.cornell.edu/wex/evidence": "Evidence",
                "https://www.law.cornell.edu/wex/hearsay": "Hearsay",
                "https://www.law.cornell.edu/wex/relevance": "Relevance",
                "https://www.law.cornell.edu/wex/privilege": "Privilege",
                "https://www.law.cornell.edu/wex/burden_of_proof": "Burden of Proof",
                "https://www.law.cornell.edu/wex/preponderance_of_the_evidence": "Preponderance of the Evidence",
                "https://www.law.cornell.edu/wex/beyond_a_reasonable_doubt": "Beyond a Reasonable Doubt",
            },
        },
        "wex-specialized": {
            "pages": {
                # Administrative Law
                "https://www.law.cornell.edu/wex/administrative_law": "Administrative Law",
                "https://www.law.cornell.edu/wex/administrative_agency": "Administrative Agency",
                "https://www.law.cornell.edu/wex/rulemaking": "Rulemaking",
                "https://www.law.cornell.edu/wex/adjudication": "Adjudication",
                # Bankruptcy
                "https://www.law.cornell.edu/wex/bankruptcy": "Bankruptcy",
                "https://www.law.cornell.edu/wex/chapter_7": "Chapter 7 Bankruptcy",
                "https://www.law.cornell.edu/wex/chapter_11": "Chapter 11 Bankruptcy",
                "https://www.law.cornell.edu/wex/chapter_13": "Chapter 13 Bankruptcy",
                # Tax Law
                "https://www.law.cornell.edu/wex/tax": "Tax Law",
                "https://www.law.cornell.edu/wex/income_tax": "Income Tax",
                "https://www.law.cornell.edu/wex/tax_deduction": "Tax Deduction",
                "https://www.law.cornell.edu/wex/tax_credit": "Tax Credit",
                # Immigration
                "https://www.law.cornell.edu/wex/immigration": "Immigration Law",
                "https://www.law.cornell.edu/wex/visa": "Visa",
                "https://www.law.cornell.edu/wex/asylum": "Asylum",
                "https://www.law.cornell.edu/wex/deportation": "Deportation",
                "https://www.law.cornell.edu/wex/naturalization": "Naturalization",
                # Environmental Law
                "https://www.law.cornell.edu/wex/environmental_law": "Environmental Law",
                # Intellectual Property
                "https://www.law.cornell.edu/wex/intellectual_property": "Intellectual Property",
                "https://www.law.cornell.edu/wex/copyright": "Copyright",
                "https://www.law.cornell.edu/wex/trademark": "Trademark",
                "https://www.law.cornell.edu/wex/patent": "Patent",
                "https://www.law.cornell.edu/wex/trade_secret": "Trade Secret",
                "https://www.law.cornell.edu/wex/fair_use": "Fair Use",
                # Labor and Employment
                "https://www.law.cornell.edu/wex/employment_law": "Employment Law",
                "https://www.law.cornell.edu/wex/labor_law": "Labor Law",
                "https://www.law.cornell.edu/wex/employment_discrimination": "Employment Discrimination",
                "https://www.law.cornell.edu/wex/at-will_employment": "At-Will Employment",
                "https://www.law.cornell.edu/wex/workers_compensation": "Workers Compensation",
                "https://www.law.cornell.edu/wex/minimum_wage": "Minimum Wage",
                # Family Law
                "https://www.law.cornell.edu/wex/family_law": "Family Law",
                "https://www.law.cornell.edu/wex/marriage": "Marriage",
                "https://www.law.cornell.edu/wex/divorce": "Divorce",
                "https://www.law.cornell.edu/wex/child_custody": "Child Custody",
                "https://www.law.cornell.edu/wex/child_support": "Child Support",
                "https://www.law.cornell.edu/wex/adoption": "Adoption",
                # International Law
                "https://www.law.cornell.edu/wex/international_law": "International Law",
                "https://www.law.cornell.edu/wex/treaty": "Treaty",
                "https://www.law.cornell.edu/wex/extradition": "Extradition",
                # Securities
                "https://www.law.cornell.edu/wex/securities": "Securities Law",
                "https://www.law.cornell.edu/wex/securities_fraud": "Securities Fraud",
                "https://www.law.cornell.edu/wex/insider_trading": "Insider Trading",
                # Antitrust
                "https://www.law.cornell.edu/wex/antitrust": "Antitrust Law",
                "https://www.law.cornell.edu/wex/monopoly": "Monopoly (Law)",
                "https://www.law.cornell.edu/wex/price_fixing": "Price Fixing",
                # Health Law
                "https://www.law.cornell.edu/wex/health_law": "Health Law",
                "https://www.law.cornell.edu/wex/hipaa": "HIPAA",
                # Cyber Law
                "https://www.law.cornell.edu/wex/internet_law": "Internet Law",
                "https://www.law.cornell.edu/wex/privacy": "Privacy Law",
            },
        },
        "constitution": {
            "pages": {
                # Articles
                "https://www.law.cornell.edu/constitution/articlei": "Constitution Article I - Legislative Branch",
                "https://www.law.cornell.edu/constitution/articleii": "Constitution Article II - Executive Branch",
                "https://www.law.cornell.edu/constitution/articleiii": "Constitution Article III - Judicial Branch",
                "https://www.law.cornell.edu/constitution/articleiv": "Constitution Article IV - States",
                "https://www.law.cornell.edu/constitution/articlev": "Constitution Article V - Amendment Process",
                "https://www.law.cornell.edu/constitution/articlevi": "Constitution Article VI - Supremacy Clause",
                "https://www.law.cornell.edu/constitution/articlevii": "Constitution Article VII - Ratification",
                # Bill of Rights (Amendments 1-10)
                "https://www.law.cornell.edu/constitution/billofrights": "Bill of Rights",
                "https://www.law.cornell.edu/constitution/first_amendment": "First Amendment",
                "https://www.law.cornell.edu/constitution/second_amendment": "Second Amendment",
                "https://www.law.cornell.edu/constitution/third_amendment": "Third Amendment",
                "https://www.law.cornell.edu/constitution/fourth_amendment": "Fourth Amendment",
                "https://www.law.cornell.edu/constitution/fifth_amendment": "Fifth Amendment",
                "https://www.law.cornell.edu/constitution/sixth_amendment": "Sixth Amendment",
                "https://www.law.cornell.edu/constitution/seventh_amendment": "Seventh Amendment",
                "https://www.law.cornell.edu/constitution/eighth_amendment": "Eighth Amendment",
                "https://www.law.cornell.edu/constitution/ninth_amendment": "Ninth Amendment",
                "https://www.law.cornell.edu/constitution/tenth_amendment": "Tenth Amendment",
                # Later Amendments
                "https://www.law.cornell.edu/constitution/amendmentxi": "Eleventh Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxii": "Twelfth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxiii": "Thirteenth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxiv": "Fourteenth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxv": "Fifteenth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxvi": "Sixteenth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxvii": "Seventeenth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxviii": "Eighteenth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxix": "Nineteenth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxx": "Twentieth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxxi": "Twenty-First Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxxii": "Twenty-Second Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxxiii": "Twenty-Third Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxxiv": "Twenty-Fourth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxxv": "Twenty-Fifth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxxvi": "Twenty-Sixth Amendment",
                "https://www.law.cornell.edu/constitution/amendmentxxvii": "Twenty-Seventh Amendment",
            },
        },
        "ucc": {
            "pages": {
                "https://www.law.cornell.edu/ucc": "Uniform Commercial Code - Overview",
                "https://www.law.cornell.edu/ucc/1": "UCC Article 1 - General Provisions",
                "https://www.law.cornell.edu/ucc/2": "UCC Article 2 - Sales",
                "https://www.law.cornell.edu/ucc/2A": "UCC Article 2A - Leases",
                "https://www.law.cornell.edu/ucc/3": "UCC Article 3 - Negotiable Instruments",
                "https://www.law.cornell.edu/ucc/4": "UCC Article 4 - Bank Deposits",
                "https://www.law.cornell.edu/ucc/4A": "UCC Article 4A - Funds Transfers",
                "https://www.law.cornell.edu/ucc/5": "UCC Article 5 - Letters of Credit",
                "https://www.law.cornell.edu/ucc/6": "UCC Article 6 - Bulk Transfers",
                "https://www.law.cornell.edu/ucc/7": "UCC Article 7 - Documents of Title",
                "https://www.law.cornell.edu/ucc/8": "UCC Article 8 - Investment Securities",
                "https://www.law.cornell.edu/ucc/9": "UCC Article 9 - Secured Transactions",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"cornell-law-wex-{source_key}" if source_key else "cornell-law-wex"
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
                ' | Wex',
                ' | Wex | US Law',
                ' | LII / Legal Information Institute',
                ' | Cornell Law School',
                ' | US Law',
                ' | LII',
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
                        "category": "cornell-law-wex",
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
            self.log.info(f"=== Scraping cornell-law-wex/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    CornellLawScraper(base, source_key).run()
