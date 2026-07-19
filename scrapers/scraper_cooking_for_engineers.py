#!/usr/bin/env python3
"""Cooking For Engineers scraper.

Covers:
  - Recipes (engineering-style recipe matrices)
  - Food science articles
  - Equipment reviews
  - Technique guides
  - Ingredient guides
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class CookingForEngineersScraper(BaseScraper):
    """Scrape Cooking For Engineers recipes, food science, and guides."""

    SOURCES = {
        "recipes": {
            "pages": {
                "http://www.cookingforengineers.com/recipe/1/Lemon-Bars": "Lemon Bars",
                "http://www.cookingforengineers.com/recipe/2/Brownies": "Brownies",
                "http://www.cookingforengineers.com/recipe/3/Meatloaf": "Meatloaf",
                "http://www.cookingforengineers.com/recipe/4/Banana-Bread": "Banana Bread",
                "http://www.cookingforengineers.com/recipe/5/Chocolate-Chip-Cookies": "Chocolate Chip Cookies",
                "http://www.cookingforengineers.com/recipe/6/Apple-Pie": "Apple Pie",
                "http://www.cookingforengineers.com/recipe/7/Blueberry-Muffins": "Blueberry Muffins",
                "http://www.cookingforengineers.com/recipe/8/Pancakes": "Pancakes",
                "http://www.cookingforengineers.com/recipe/9/Waffles": "Waffles",
                "http://www.cookingforengineers.com/recipe/10/French-Toast": "French Toast",
                "http://www.cookingforengineers.com/recipe/11/Macaroni-and-Cheese": "Macaroni and Cheese",
                "http://www.cookingforengineers.com/recipe/12/Chicken-Noodle-Soup": "Chicken Noodle Soup",
                "http://www.cookingforengineers.com/recipe/13/Beef-Stew": "Beef Stew",
                "http://www.cookingforengineers.com/recipe/14/Chili-Con-Carne": "Chili Con Carne",
                "http://www.cookingforengineers.com/recipe/15/Lasagna": "Lasagna",
                "http://www.cookingforengineers.com/recipe/16/Pizza-Dough": "Pizza Dough",
                "http://www.cookingforengineers.com/recipe/17/Focaccia": "Focaccia",
                "http://www.cookingforengineers.com/recipe/18/Cinnamon-Rolls": "Cinnamon Rolls",
                "http://www.cookingforengineers.com/recipe/19/Dinner-Rolls": "Dinner Rolls",
                "http://www.cookingforengineers.com/recipe/20/Cornbread": "Cornbread",
                "http://www.cookingforengineers.com/recipe/21/Pot-Roast": "Pot Roast",
                "http://www.cookingforengineers.com/recipe/22/Roast-Chicken": "Roast Chicken",
                "http://www.cookingforengineers.com/recipe/23/Fried-Chicken": "Fried Chicken",
                "http://www.cookingforengineers.com/recipe/24/Chicken-Parmesan": "Chicken Parmesan",
                "http://www.cookingforengineers.com/recipe/25/Beef-Stroganoff": "Beef Stroganoff",
                "http://www.cookingforengineers.com/recipe/26/Shepherds-Pie": "Shepherds Pie",
                "http://www.cookingforengineers.com/recipe/27/Fish-and-Chips": "Fish and Chips",
                "http://www.cookingforengineers.com/recipe/28/Shrimp-Scampi": "Shrimp Scampi",
                "http://www.cookingforengineers.com/recipe/29/Pad-Thai": "Pad Thai",
                "http://www.cookingforengineers.com/recipe/30/Chicken-Curry": "Chicken Curry",
                "http://www.cookingforengineers.com/recipe/31/Beef-Tacos": "Beef Tacos",
                "http://www.cookingforengineers.com/recipe/32/Enchiladas": "Enchiladas",
                "http://www.cookingforengineers.com/recipe/33/Pulled-Pork": "Pulled Pork",
                "http://www.cookingforengineers.com/recipe/34/BBQ-Ribs": "BBQ Ribs",
                "http://www.cookingforengineers.com/recipe/35/Grilled-Salmon": "Grilled Salmon",
                "http://www.cookingforengineers.com/recipe/36/Pan-Seared-Steak": "Pan Seared Steak",
                "http://www.cookingforengineers.com/recipe/37/Risotto": "Risotto",
                "http://www.cookingforengineers.com/recipe/38/Fettuccine-Alfredo": "Fettuccine Alfredo",
                "http://www.cookingforengineers.com/recipe/39/Carbonara": "Carbonara",
                "http://www.cookingforengineers.com/recipe/40/Bolognese": "Bolognese",
                "http://www.cookingforengineers.com/recipe/41/Minestrone": "Minestrone",
                "http://www.cookingforengineers.com/recipe/42/French-Onion-Soup": "French Onion Soup",
                "http://www.cookingforengineers.com/recipe/43/Clam-Chowder": "Clam Chowder",
                "http://www.cookingforengineers.com/recipe/44/Tomato-Soup": "Tomato Soup",
                "http://www.cookingforengineers.com/recipe/45/Caesar-Salad": "Caesar Salad",
                "http://www.cookingforengineers.com/recipe/46/Coleslaw": "Coleslaw",
                "http://www.cookingforengineers.com/recipe/47/Potato-Salad": "Potato Salad",
                "http://www.cookingforengineers.com/recipe/48/Deviled-Eggs": "Deviled Eggs",
                "http://www.cookingforengineers.com/recipe/49/Guacamole": "Guacamole",
                "http://www.cookingforengineers.com/recipe/50/Hummus": "Hummus",
                "http://www.cookingforengineers.com/recipe/51/Quiche-Lorraine": "Quiche Lorraine",
                "http://www.cookingforengineers.com/recipe/52/Eggs-Benedict": "Eggs Benedict",
                "http://www.cookingforengineers.com/recipe/53/Frittata": "Frittata",
                "http://www.cookingforengineers.com/recipe/54/Shakshuka": "Shakshuka",
                "http://www.cookingforengineers.com/recipe/55/Crepes": "Crepes",
                "http://www.cookingforengineers.com/recipe/56/Scones": "Scones",
                "http://www.cookingforengineers.com/recipe/57/Biscuits": "Biscuits",
                "http://www.cookingforengineers.com/recipe/58/Sourdough-Bread": "Sourdough Bread",
                "http://www.cookingforengineers.com/recipe/59/Challah": "Challah",
                "http://www.cookingforengineers.com/recipe/60/Brioche": "Brioche",
                "http://www.cookingforengineers.com/recipe/61/Croissants": "Croissants",
                "http://www.cookingforengineers.com/recipe/62/Pretzels": "Pretzels",
                "http://www.cookingforengineers.com/recipe/63/Bagels": "Bagels",
                "http://www.cookingforengineers.com/recipe/64/Pita-Bread": "Pita Bread",
                "http://www.cookingforengineers.com/recipe/65/Naan": "Naan",
                "http://www.cookingforengineers.com/recipe/66/Chicken-Pot-Pie": "Chicken Pot Pie",
                "http://www.cookingforengineers.com/recipe/67/Beef-Wellington": "Beef Wellington",
                "http://www.cookingforengineers.com/recipe/68/Lamb-Chops": "Lamb Chops",
                "http://www.cookingforengineers.com/recipe/69/Pork-Tenderloin": "Pork Tenderloin",
                "http://www.cookingforengineers.com/recipe/70/Honey-Glazed-Ham": "Honey Glazed Ham",
                "http://www.cookingforengineers.com/recipe/71/Teriyaki-Chicken": "Teriyaki Chicken",
                "http://www.cookingforengineers.com/recipe/72/Kung-Pao-Chicken": "Kung Pao Chicken",
                "http://www.cookingforengineers.com/recipe/73/Sweet-and-Sour-Pork": "Sweet and Sour Pork",
                "http://www.cookingforengineers.com/recipe/74/Fried-Rice": "Fried Rice",
                "http://www.cookingforengineers.com/recipe/75/Lo-Mein": "Lo Mein",
                "http://www.cookingforengineers.com/recipe/76/Ramen": "Ramen",
                "http://www.cookingforengineers.com/recipe/77/Pho": "Pho",
                "http://www.cookingforengineers.com/recipe/78/Tom-Yum-Soup": "Tom Yum Soup",
                "http://www.cookingforengineers.com/recipe/79/Green-Curry": "Green Curry",
                "http://www.cookingforengineers.com/recipe/80/Tikka-Masala": "Tikka Masala",
                "http://www.cookingforengineers.com/recipe/81/Biryani": "Biryani",
                "http://www.cookingforengineers.com/recipe/82/Falafel": "Falafel",
                "http://www.cookingforengineers.com/recipe/83/Gyros": "Gyros",
                "http://www.cookingforengineers.com/recipe/84/Moussaka": "Moussaka",
                "http://www.cookingforengineers.com/recipe/85/Paella": "Paella",
                "http://www.cookingforengineers.com/recipe/86/Jambalaya": "Jambalaya",
                "http://www.cookingforengineers.com/recipe/87/Gumbo": "Gumbo",
                "http://www.cookingforengineers.com/recipe/88/Crab-Cakes": "Crab Cakes",
                "http://www.cookingforengineers.com/recipe/89/Fish-Tacos": "Fish Tacos",
                "http://www.cookingforengineers.com/recipe/90/Lobster-Bisque": "Lobster Bisque",
                "http://www.cookingforengineers.com/recipe/91/Shrimp-and-Grits": "Shrimp and Grits",
                "http://www.cookingforengineers.com/recipe/92/Ceviche": "Ceviche",
                "http://www.cookingforengineers.com/recipe/93/Poke-Bowl": "Poke Bowl",
                "http://www.cookingforengineers.com/recipe/94/Sushi-Rice": "Sushi Rice",
                "http://www.cookingforengineers.com/recipe/95/Tempura": "Tempura",
                "http://www.cookingforengineers.com/recipe/96/Spring-Rolls": "Spring Rolls",
                "http://www.cookingforengineers.com/recipe/97/Dumplings": "Dumplings",
                "http://www.cookingforengineers.com/recipe/98/Potstickers": "Potstickers",
                "http://www.cookingforengineers.com/recipe/99/Samosas": "Samosas",
                "http://www.cookingforengineers.com/recipe/100/Empanadas": "Empanadas",
                "http://www.cookingforengineers.com/recipe/101/Pierogi": "Pierogi",
                "http://www.cookingforengineers.com/recipe/102/Gnocchi": "Gnocchi",
                "http://www.cookingforengineers.com/recipe/103/Ravioli": "Ravioli",
                "http://www.cookingforengineers.com/recipe/104/Tortellini": "Tortellini",
                "http://www.cookingforengineers.com/recipe/105/Pesto": "Pesto",
                "http://www.cookingforengineers.com/recipe/106/Marinara-Sauce": "Marinara Sauce",
                "http://www.cookingforengineers.com/recipe/107/Bechamel-Sauce": "Bechamel Sauce",
                "http://www.cookingforengineers.com/recipe/108/Hollandaise-Sauce": "Hollandaise Sauce",
                "http://www.cookingforengineers.com/recipe/109/Chimichurri": "Chimichurri",
                "http://www.cookingforengineers.com/recipe/110/Tzatziki": "Tzatziki",
                "http://www.cookingforengineers.com/recipe/111/Chocolate-Cake": "Chocolate Cake",
                "http://www.cookingforengineers.com/recipe/112/Carrot-Cake": "Carrot Cake",
                "http://www.cookingforengineers.com/recipe/113/Cheesecake": "Cheesecake",
                "http://www.cookingforengineers.com/recipe/114/Tiramisu": "Tiramisu",
                "http://www.cookingforengineers.com/recipe/115/Creme-Brulee": "Creme Brulee",
                "http://www.cookingforengineers.com/recipe/116/Panna-Cotta": "Panna Cotta",
                "http://www.cookingforengineers.com/recipe/117/Pecan-Pie": "Pecan Pie",
                "http://www.cookingforengineers.com/recipe/118/Key-Lime-Pie": "Key Lime Pie",
                "http://www.cookingforengineers.com/recipe/119/Pavlova": "Pavlova",
                "http://www.cookingforengineers.com/recipe/120/Baklava": "Baklava",
            },
        },
        "food-science": {
            "pages": {
                "http://www.cookingforengineers.com/article/1/Maillard-Reaction": "Maillard Reaction",
                "http://www.cookingforengineers.com/article/2/Gluten-Development": "Gluten Development",
                "http://www.cookingforengineers.com/article/3/Caramelization": "Caramelization",
                "http://www.cookingforengineers.com/article/4/Emulsification": "Emulsification",
                "http://www.cookingforengineers.com/article/5/Leavening-Agents": "Leavening Agents",
                "http://www.cookingforengineers.com/article/6/Egg-Coagulation": "Egg Coagulation",
                "http://www.cookingforengineers.com/article/7/Gelatin-Science": "Gelatin Science",
                "http://www.cookingforengineers.com/article/8/Osmosis-and-Brining": "Osmosis and Brining",
                "http://www.cookingforengineers.com/article/9/Smoke-Chemistry": "Smoke Chemistry",
                "http://www.cookingforengineers.com/article/10/Fermentation-Basics": "Fermentation Basics",
                "http://www.cookingforengineers.com/article/11/Starch-Gelatinization": "Starch Gelatinization",
                "http://www.cookingforengineers.com/article/12/Fat-Rendering": "Fat Rendering",
                "http://www.cookingforengineers.com/article/13/Acid-Base-Reactions": "Acid Base Reactions",
                "http://www.cookingforengineers.com/article/14/Protein-Denaturation": "Protein Denaturation",
                "http://www.cookingforengineers.com/article/15/Enzymatic-Browning": "Enzymatic Browning",
                "http://www.cookingforengineers.com/article/16/Crystallization-in-Candy": "Crystallization in Candy",
                "http://www.cookingforengineers.com/article/17/Water-Activity": "Water Activity",
                "http://www.cookingforengineers.com/article/18/Collagen-Conversion": "Collagen Conversion",
                "http://www.cookingforengineers.com/article/19/Heat-Transfer-Methods": "Heat Transfer Methods",
                "http://www.cookingforengineers.com/article/20/Convection-Currents": "Convection Currents",
                "http://www.cookingforengineers.com/article/21/Conduction-in-Cooking": "Conduction in Cooking",
                "http://www.cookingforengineers.com/article/22/Radiation-and-Broiling": "Radiation and Broiling",
                "http://www.cookingforengineers.com/article/23/Phase-Transitions": "Phase Transitions",
                "http://www.cookingforengineers.com/article/24/Flavor-Compounds": "Flavor Compounds",
                "http://www.cookingforengineers.com/article/25/Volatile-Aromatics": "Volatile Aromatics",
                "http://www.cookingforengineers.com/article/26/Sous-Vide-Science": "Sous Vide Science",
                "http://www.cookingforengineers.com/article/27/Pressure-Cooking-Science": "Pressure Cooking Science",
                "http://www.cookingforengineers.com/article/28/Microwave-Science": "Microwave Science",
                "http://www.cookingforengineers.com/article/29/Yeast-Biology": "Yeast Biology",
                "http://www.cookingforengineers.com/article/30/Bacteria-and-Fermentation": "Bacteria and Fermentation",
            },
        },
        "equipment-reviews": {
            "pages": {
                "http://www.cookingforengineers.com/article/50/Kitchen-Scale-Review": "Kitchen Scale Review",
                "http://www.cookingforengineers.com/article/51/Thermometer-Comparison": "Thermometer Comparison",
                "http://www.cookingforengineers.com/article/52/Knife-Review": "Knife Review",
                "http://www.cookingforengineers.com/article/53/Cutting-Board-Guide": "Cutting Board Guide",
                "http://www.cookingforengineers.com/article/54/Food-Processor-Review": "Food Processor Review",
                "http://www.cookingforengineers.com/article/55/Stand-Mixer-Comparison": "Stand Mixer Comparison",
                "http://www.cookingforengineers.com/article/56/Immersion-Blender-Review": "Immersion Blender Review",
                "http://www.cookingforengineers.com/article/57/Cast-Iron-Skillet-Guide": "Cast Iron Skillet Guide",
                "http://www.cookingforengineers.com/article/58/Non-Stick-Pan-Review": "Non Stick Pan Review",
                "http://www.cookingforengineers.com/article/59/Baking-Sheet-Comparison": "Baking Sheet Comparison",
                "http://www.cookingforengineers.com/article/60/Dutch-Oven-Review": "Dutch Oven Review",
                "http://www.cookingforengineers.com/article/61/Pressure-Cooker-Guide": "Pressure Cooker Guide",
                "http://www.cookingforengineers.com/article/62/Slow-Cooker-Review": "Slow Cooker Review",
                "http://www.cookingforengineers.com/article/63/Mandoline-Guide": "Mandoline Guide",
                "http://www.cookingforengineers.com/article/64/Microplane-Review": "Microplane Review",
                "http://www.cookingforengineers.com/article/65/Silicone-Spatula-Review": "Silicone Spatula Review",
                "http://www.cookingforengineers.com/article/66/Whisk-Guide": "Whisk Guide",
                "http://www.cookingforengineers.com/article/67/Tongs-Review": "Tongs Review",
                "http://www.cookingforengineers.com/article/68/Measuring-Cup-Review": "Measuring Cup Review",
                "http://www.cookingforengineers.com/article/69/Rolling-Pin-Guide": "Rolling Pin Guide",
            },
        },
        "technique-guides": {
            "pages": {
                "http://www.cookingforengineers.com/article/80/How-to-Saute": "How to Saute",
                "http://www.cookingforengineers.com/article/81/How-to-Braise": "How to Braise",
                "http://www.cookingforengineers.com/article/82/How-to-Roast": "How to Roast",
                "http://www.cookingforengineers.com/article/83/How-to-Grill": "How to Grill",
                "http://www.cookingforengineers.com/article/84/How-to-Deep-Fry": "How to Deep Fry",
                "http://www.cookingforengineers.com/article/85/How-to-Poach": "How to Poach",
                "http://www.cookingforengineers.com/article/86/How-to-Steam": "How to Steam",
                "http://www.cookingforengineers.com/article/87/How-to-Blanch": "How to Blanch",
                "http://www.cookingforengineers.com/article/88/How-to-Deglaze": "How to Deglaze",
                "http://www.cookingforengineers.com/article/89/How-to-Reduce": "How to Reduce",
                "http://www.cookingforengineers.com/article/90/How-to-Temper-Chocolate": "How to Temper Chocolate",
                "http://www.cookingforengineers.com/article/91/How-to-Proof-Yeast": "How to Proof Yeast",
                "http://www.cookingforengineers.com/article/92/How-to-Knead-Dough": "How to Knead Dough",
                "http://www.cookingforengineers.com/article/93/How-to-Fold-Egg-Whites": "How to Fold Egg Whites",
                "http://www.cookingforengineers.com/article/94/How-to-Caramelize-Onions": "How to Caramelize Onions",
                "http://www.cookingforengineers.com/article/95/How-to-Make-Roux": "How to Make Roux",
                "http://www.cookingforengineers.com/article/96/How-to-Truss-a-Chicken": "How to Truss a Chicken",
                "http://www.cookingforengineers.com/article/97/How-to-Fillet-a-Fish": "How to Fillet a Fish",
                "http://www.cookingforengineers.com/article/98/How-to-Sharpen-Knives": "How to Sharpen Knives",
            },
        },
        "ingredient-guides": {
            "pages": {
                "http://www.cookingforengineers.com/article/100/Guide-to-Flour-Types": "Guide to Flour Types",
                "http://www.cookingforengineers.com/article/101/Guide-to-Cooking-Oils": "Guide to Cooking Oils",
                "http://www.cookingforengineers.com/article/102/Guide-to-Salt-Types": "Guide to Salt Types",
                "http://www.cookingforengineers.com/article/103/Guide-to-Sugar-Types": "Guide to Sugar Types",
                "http://www.cookingforengineers.com/article/104/Guide-to-Vinegars": "Guide to Vinegars",
                "http://www.cookingforengineers.com/article/105/Guide-to-Rice-Varieties": "Guide to Rice Varieties",
                "http://www.cookingforengineers.com/article/106/Guide-to-Pasta-Shapes": "Guide to Pasta Shapes",
                "http://www.cookingforengineers.com/article/107/Guide-to-Chili-Peppers": "Guide to Chili Peppers",
                "http://www.cookingforengineers.com/article/108/Guide-to-Mushrooms": "Guide to Mushrooms",
                "http://www.cookingforengineers.com/article/109/Guide-to-Cheese": "Guide to Cheese",
                "http://www.cookingforengineers.com/article/110/Guide-to-Herbs": "Guide to Herbs",
                "http://www.cookingforengineers.com/article/111/Guide-to-Spices": "Guide to Spices",
                "http://www.cookingforengineers.com/article/112/Guide-to-Chocolate": "Guide to Chocolate",
                "http://www.cookingforengineers.com/article/113/Guide-to-Cuts-of-Beef": "Guide to Cuts of Beef",
                "http://www.cookingforengineers.com/article/114/Guide-to-Cuts-of-Pork": "Guide to Cuts of Pork",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"cooking-for-engineers-{source_key}" if source_key else "cooking-for-engineers"
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
            for suffix in [' - Cooking For Engineers', ' | Cooking For Engineers']:
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
                        "category": f"cooking-for-engineers-{source_key}",
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
            self.log.info(f"=== Scraping cooking-for-engineers/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    CookingForEngineersScraper(base, source_key).run()
