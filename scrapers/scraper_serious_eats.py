#!/usr/bin/env python3
"""Serious Eats scraper for culinary techniques, food science, and recipes.

Covers:
  - Cooking techniques (knife skills, braising, grilling, sous-vide, etc.)
  - Food science (Maillard reaction, emulsions, gluten development, etc.)
  - Recipes (meat, vegetarian, baking, world cuisines)
  - Equipment reviews and ingredient guides
"""
import re
import time
import html as html_mod
from scraper_base import BaseScraper


class SeriousEatsScraper(BaseScraper):
    """Scrape Serious Eats documentation, recipes, and food science articles."""

    SOURCES = {
        "techniques": {
            "pages": {
                # Knife skills
                "https://www.seriouseats.com/knife-skills-how-to-cut-an-onion": "Knife Skills: How to Cut an Onion",
                "https://www.seriouseats.com/knife-skills-how-to-dice-an-onion": "Knife Skills: How to Dice an Onion",
                "https://www.seriouseats.com/knife-skills-how-to-mince-garlic": "Knife Skills: How to Mince Garlic",
                "https://www.seriouseats.com/knife-skills-how-to-mince-fresh-herbs": "Knife Skills: How to Mince Fresh Herbs",
                "https://www.seriouseats.com/knife-skills-how-to-mince-ginger": "Knife Skills: How to Mince Ginger",
                "https://www.seriouseats.com/knife-skills-how-to-dice-carrots": "Knife Skills: How to Dice Carrots",
                "https://www.seriouseats.com/knife-skills-how-to-dice-celery": "Knife Skills: How to Dice Celery",
                "https://www.seriouseats.com/knife-skills-how-to-dice-bell-peppers": "Knife Skills: How to Dice Bell Peppers",
                "https://www.seriouseats.com/knife-skills-how-to-dice-tomatoes": "Knife Skills: How to Dice Tomatoes",
                "https://www.seriouseats.com/knife-skills-how-to-dice-potatoes": "Knife Skills: How to Dice Potatoes",
                "https://www.seriouseats.com/knife-skills-how-to-chiffonade-basil": "Knife Skills: How to Chiffonade Basil",
                "https://www.seriouseats.com/knife-skills-how-to-julienne-vegetables": "Knife Skills: How to Julienne Vegetables",
                "https://www.seriouseats.com/knife-skills-how-to-brunoise-vegetables": "Knife Skills: How to Brunoise Vegetables",
                "https://www.seriouseats.com/knife-skills-how-to-cut-a-mango": "Knife Skills: How to Cut a Mango",
                "https://www.seriouseats.com/knife-skills-how-to-segment-citrus": "Knife Skills: How to Segment Citrus",
                "https://www.seriouseats.com/knife-skills-how-to-break-down-a-whole-chicken": "Knife Skills: How to Break Down a Whole Chicken",
                "https://www.seriouseats.com/knife-skills-how-to-sharpen-a-knife": "Knife Skills: How to Sharpen a Knife",
                "https://www.seriouseats.com/knife-skills-how-to-hone-a-knife": "Knife Skills: How to Hone a Knife",
                # Sous vide
                "https://www.seriouseats.com/the-food-lab-complete-guide-to-sous-vide-steak": "The Food Lab: Complete Guide to Sous Vide Steak",
                "https://www.seriouseats.com/sous-vide-chicken-breast-recipe": "Sous Vide Chicken Breast",
                "https://www.seriouseats.com/sous-vide-pork-chops-recipe": "Sous Vide Pork Chops",
                "https://www.seriouseats.com/sous-vide-salmon-recipe": "Sous Vide Salmon",
                "https://www.seriouseats.com/sous-vide-eggs-recipe": "Sous Vide Eggs",
                "https://www.seriouseats.com/sous-vide-lamb-chops-recipe": "Sous Vide Lamb Chops",
                "https://www.seriouseats.com/sous-vide-duck-breast-recipe": "Sous Vide Duck Breast",
                "https://www.seriouseats.com/sous-vide-burgers-recipe": "Sous Vide Burgers",
                "https://www.seriouseats.com/sous-vide-turkey-breast-recipe": "Sous Vide Turkey Breast",
                "https://www.seriouseats.com/sous-vide-short-ribs-recipe": "Sous Vide Short Ribs",
                "https://www.seriouseats.com/sous-vide-pork-belly-recipe": "Sous Vide Pork Belly",
                "https://www.seriouseats.com/sous-vide-equipment-guide-for-beginners": "Sous Vide Equipment Guide for Beginners",
                # Grilling
                "https://www.seriouseats.com/grilling-the-food-lab-how-to-grill-a-steak": "The Food Lab: How to Grill a Steak",
                "https://www.seriouseats.com/grilling-how-to-set-up-charcoal-grill": "How to Set Up a Charcoal Grill",
                "https://www.seriouseats.com/grilling-how-to-set-up-gas-grill": "How to Set Up a Gas Grill",
                "https://www.seriouseats.com/grilling-how-to-use-two-zone-fire": "How to Use a Two-Zone Fire",
                "https://www.seriouseats.com/grilling-chicken-thighs-recipe": "Grilling Chicken Thighs",
                "https://www.seriouseats.com/grilling-vegetables-guide": "Guide to Grilling Vegetables",
                "https://www.seriouseats.com/grilling-fish-guide": "Guide to Grilling Fish",
                "https://www.seriouseats.com/grilling-burgers-guide": "Guide to Grilling Burgers",
                "https://www.seriouseats.com/grilling-corn-on-the-cob-guide": "Guide to Grilling Corn on the Cob",
                "https://www.seriouseats.com/grilling-pizza-on-the-grill": "How to Grill Pizza",
                "https://www.seriouseats.com/grilling-lamb-chops-recipe": "Grilling Lamb Chops",
                # Braising
                "https://www.seriouseats.com/how-to-braise-why-what-braising": "How to Braise: Why and What",
                "https://www.seriouseats.com/braising-short-ribs-guide": "Braising Short Ribs Guide",
                "https://www.seriouseats.com/braising-chicken-thighs-guide": "Braising Chicken Thighs Guide",
                "https://www.seriouseats.com/braising-pork-shoulder-guide": "Braising Pork Shoulder Guide",
                "https://www.seriouseats.com/braising-lamb-shanks-guide": "Braising Lamb Shanks Guide",
                "https://www.seriouseats.com/braising-beef-chuck-roast-guide": "Braising Beef Chuck Roast Guide",
                "https://www.seriouseats.com/braising-vegetables-guide": "Braising Vegetables Guide",
                "https://www.seriouseats.com/braising-oxtails-guide": "Braising Oxtails Guide",
                # Frying
                "https://www.seriouseats.com/deep-frying-101": "Deep Frying 101",
                "https://www.seriouseats.com/frying-how-to-pan-fry-guide": "How to Pan Fry Guide",
                "https://www.seriouseats.com/frying-how-to-shallow-fry-guide": "How to Shallow Fry Guide",
                "https://www.seriouseats.com/frying-choosing-the-best-oil-for-deep-frying": "Choosing the Best Oil for Deep Frying",
                "https://www.seriouseats.com/frying-temperature-control-guide": "Frying Temperature Control Guide",
                "https://www.seriouseats.com/frying-how-to-make-tempura": "How to Make Tempura",
                "https://www.seriouseats.com/frying-how-to-make-fried-chicken": "How to Make Fried Chicken",
                "https://www.seriouseats.com/frying-stir-fry-technique-guide": "Stir-Fry Technique Guide",
                # Baking techniques
                "https://www.seriouseats.com/baking-how-to-cream-butter-and-sugar": "How to Cream Butter and Sugar",
                "https://www.seriouseats.com/baking-how-to-fold-batter": "How to Fold Batter",
                "https://www.seriouseats.com/baking-how-to-temper-chocolate": "How to Temper Chocolate",
                "https://www.seriouseats.com/baking-how-to-blind-bake-pie-crust": "How to Blind Bake Pie Crust",
                "https://www.seriouseats.com/baking-how-to-proof-yeast-dough": "How to Proof Yeast Dough",
                # Roasting
                "https://www.seriouseats.com/roasting-vegetables-guide": "Guide to Roasting Vegetables",
                "https://www.seriouseats.com/roasting-how-to-roast-a-chicken": "How to Roast a Chicken",
                "https://www.seriouseats.com/roasting-how-to-roast-beef-tenderloin": "How to Roast Beef Tenderloin",
                "https://www.seriouseats.com/roasting-how-to-roast-a-turkey": "How to Roast a Turkey",
                "https://www.seriouseats.com/roasting-how-to-roast-pork-loin": "How to Roast Pork Loin",
                "https://www.seriouseats.com/roasting-how-to-roast-potatoes": "How to Roast Potatoes",
                "https://www.seriouseats.com/roasting-how-to-roast-cauliflower": "How to Roast Cauliflower",
                "https://www.seriouseats.com/roasting-how-to-roast-brussels-sprouts": "How to Roast Brussels Sprouts",
                "https://www.seriouseats.com/roasting-how-to-roast-beets": "How to Roast Beets",
                # Smoking
                "https://www.seriouseats.com/how-to-smoke-ribs": "How to Smoke Ribs",
                "https://www.seriouseats.com/smoking-brisket-guide": "Smoking Brisket Guide",
                "https://www.seriouseats.com/smoking-pork-shoulder-guide": "Smoking Pork Shoulder Guide",
                "https://www.seriouseats.com/smoking-salmon-guide": "Smoking Salmon Guide",
                "https://www.seriouseats.com/smoking-chicken-guide": "Smoking Chicken Guide",
                "https://www.seriouseats.com/smoking-turkey-guide": "Smoking Turkey Guide",
                "https://www.seriouseats.com/smoking-wood-selection-guide": "Smoking Wood Selection Guide",
                "https://www.seriouseats.com/smoking-temperature-guide": "Smoking Temperature Guide",
                # Fermentation
                "https://www.seriouseats.com/fermentation-how-to-make-sauerkraut": "How to Make Sauerkraut",
                "https://www.seriouseats.com/fermentation-how-to-make-kimchi": "How to Make Kimchi",
                "https://www.seriouseats.com/fermentation-how-to-make-kombucha": "How to Make Kombucha",
                "https://www.seriouseats.com/fermentation-how-to-make-yogurt": "How to Make Yogurt",
                "https://www.seriouseats.com/fermentation-how-to-make-pickles": "How to Make Fermented Pickles",
                "https://www.seriouseats.com/fermentation-how-to-make-sourdough-starter": "How to Make Sourdough Starter",
                "https://www.seriouseats.com/fermentation-how-to-make-hot-sauce": "How to Make Fermented Hot Sauce",
                "https://www.seriouseats.com/fermentation-how-to-make-miso": "How to Make Miso",
                # Sauteing
                "https://www.seriouseats.com/sauteing-guide-how-to-saute": "Guide to Sauteing",
                "https://www.seriouseats.com/sauteing-mushrooms-guide": "How to Saute Mushrooms",
                "https://www.seriouseats.com/sauteing-greens-guide": "How to Saute Greens",
                "https://www.seriouseats.com/sauteing-shrimp-guide": "How to Saute Shrimp",
                # Blanching and poaching
                "https://www.seriouseats.com/blanching-vegetables-guide": "Guide to Blanching Vegetables",
                "https://www.seriouseats.com/blanching-and-shocking-guide": "Blanching and Shocking Guide",
                "https://www.seriouseats.com/poaching-eggs-guide": "Guide to Poaching Eggs",
                "https://www.seriouseats.com/poaching-chicken-breast-guide": "Poaching Chicken Breast Guide",
                "https://www.seriouseats.com/poaching-fish-guide": "Guide to Poaching Fish",
                "https://www.seriouseats.com/poaching-fruit-guide": "Guide to Poaching Fruit",
                # Steaming
                "https://www.seriouseats.com/steaming-vegetables-guide": "Guide to Steaming Vegetables",
                "https://www.seriouseats.com/steaming-fish-guide": "Guide to Steaming Fish",
                "https://www.seriouseats.com/steaming-dumplings-guide": "Guide to Steaming Dumplings",
                # Other techniques
                "https://www.seriouseats.com/how-to-make-stock-guide": "How to Make Stock",
                "https://www.seriouseats.com/how-to-deglaze-a-pan": "How to Deglaze a Pan",
                "https://www.seriouseats.com/how-to-emulsify-a-pan-sauce": "How to Emulsify a Pan Sauce",
                "https://www.seriouseats.com/how-to-dry-brine-meat": "How to Dry Brine Meat",
                "https://www.seriouseats.com/how-to-wet-brine-meat": "How to Wet Brine Meat",
                "https://www.seriouseats.com/how-to-reverse-sear-steak": "How to Reverse Sear a Steak",
                "https://www.seriouseats.com/how-to-rest-meat-after-cooking": "How to Rest Meat After Cooking",
                "https://www.seriouseats.com/how-to-marinate-meat-guide": "How to Marinate Meat",
                "https://www.seriouseats.com/how-to-caramelize-onions": "How to Caramelize Onions",
                "https://www.seriouseats.com/how-to-render-fat-guide": "How to Render Fat",
                "https://www.seriouseats.com/how-to-make-a-roux": "How to Make a Roux",
            },
        },
        "food-science": {
            "pages": {
                # Maillard reaction and browning
                "https://www.seriouseats.com/what-is-maillard-reaction-cooking-science": "What Is the Maillard Reaction",
                "https://www.seriouseats.com/the-food-lab-science-of-browning-meat": "The Science of Browning Meat",
                "https://www.seriouseats.com/the-food-lab-science-of-caramelization": "The Science of Caramelization",
                "https://www.seriouseats.com/the-food-lab-why-you-should-dry-your-meat": "Why You Should Dry Your Meat Before Cooking",
                "https://www.seriouseats.com/the-food-lab-science-of-searing": "The Science of Searing",
                # Emulsions and sauces
                "https://www.seriouseats.com/the-food-lab-science-of-emulsions": "The Science of Emulsions",
                "https://www.seriouseats.com/the-food-lab-science-of-mayonnaise": "The Science of Mayonnaise",
                "https://www.seriouseats.com/the-food-lab-science-of-hollandaise": "The Science of Hollandaise",
                "https://www.seriouseats.com/the-food-lab-science-of-vinaigrettes": "The Science of Vinaigrettes",
                "https://www.seriouseats.com/the-food-lab-science-of-cheese-sauces": "The Science of Cheese Sauces",
                # Baking science
                "https://www.seriouseats.com/the-science-of-the-best-chocolate-chip-cookies": "The Science of the Best Chocolate Chip Cookies",
                "https://www.seriouseats.com/the-food-lab-science-of-gluten-development": "The Science of Gluten Development",
                "https://www.seriouseats.com/the-food-lab-science-of-yeast-and-fermentation": "The Science of Yeast and Fermentation",
                "https://www.seriouseats.com/the-food-lab-science-of-leavening-agents": "The Science of Leavening Agents",
                "https://www.seriouseats.com/the-food-lab-science-of-baking-powder-vs-baking-soda": "Baking Powder vs Baking Soda",
                "https://www.seriouseats.com/the-food-lab-science-of-butter-in-baking": "The Science of Butter in Baking",
                "https://www.seriouseats.com/the-food-lab-science-of-sugar-in-baking": "The Science of Sugar in Baking",
                "https://www.seriouseats.com/the-food-lab-science-of-eggs-in-baking": "The Science of Eggs in Baking",
                # Proteins and meat science
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-steak": "The Science of Cooking Steak",
                "https://www.seriouseats.com/the-food-lab-science-of-brining-meat": "The Science of Brining Meat",
                "https://www.seriouseats.com/the-food-lab-science-of-slow-cooking-collagen": "The Science of Slow Cooking and Collagen",
                "https://www.seriouseats.com/the-food-lab-science-of-marinating": "The Science of Marinating",
                "https://www.seriouseats.com/the-food-lab-science-of-resting-meat": "The Science of Resting Meat",
                "https://www.seriouseats.com/the-food-lab-science-of-ground-beef": "The Science of Ground Beef",
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-chicken": "The Science of Cooking Chicken",
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-pork": "The Science of Cooking Pork",
                # Temperature and food safety
                "https://www.seriouseats.com/food-safety-and-handling": "Food Safety and Handling",
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-temperatures": "The Science of Cooking Temperatures",
                "https://www.seriouseats.com/the-food-lab-science-of-carryover-cooking": "The Science of Carryover Cooking",
                "https://www.seriouseats.com/the-food-lab-science-of-danger-zone-temperatures": "The Danger Zone: Food Safety Temperatures",
                "https://www.seriouseats.com/the-food-lab-science-of-pasteurization-time-temperature": "Pasteurization: Time and Temperature",
                "https://www.seriouseats.com/the-food-lab-internal-temperature-guide-meat": "Internal Temperature Guide for Meat",
                "https://www.seriouseats.com/the-food-lab-science-of-freezing-and-thawing": "The Science of Freezing and Thawing",
                # Eggs
                "https://www.seriouseats.com/the-food-lab-science-of-boiling-eggs": "The Science of Boiling Eggs",
                "https://www.seriouseats.com/the-food-lab-science-of-scrambled-eggs": "The Science of Scrambled Eggs",
                "https://www.seriouseats.com/the-food-lab-science-of-poached-eggs": "The Science of Poached Eggs",
                "https://www.seriouseats.com/the-food-lab-science-of-egg-proteins": "The Science of Egg Proteins",
                "https://www.seriouseats.com/the-food-lab-science-of-custards-and-curds": "The Science of Custards and Curds",
                # Starches and grains
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-rice": "The Science of Cooking Rice",
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-pasta": "The Science of Cooking Pasta",
                "https://www.seriouseats.com/the-food-lab-science-of-starch-gelatinization": "The Science of Starch Gelatinization",
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-potatoes": "The Science of Cooking Potatoes",
                "https://www.seriouseats.com/the-food-lab-science-of-thickening-with-starch": "Thickening with Starch",
                # Vegetables and fruits
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-green-vegetables": "The Science of Cooking Green Vegetables",
                "https://www.seriouseats.com/the-food-lab-science-of-roasting-vegetables": "The Science of Roasting Vegetables",
                "https://www.seriouseats.com/the-food-lab-science-of-enzymatic-browning": "The Science of Enzymatic Browning",
                "https://www.seriouseats.com/the-food-lab-science-of-pectin-in-fruit": "The Science of Pectin in Fruit",
                # Fats and oils
                "https://www.seriouseats.com/the-food-lab-science-of-cooking-fats-and-oils": "The Science of Cooking Fats and Oils",
                "https://www.seriouseats.com/the-food-lab-science-of-smoke-points": "The Science of Smoke Points",
                "https://www.seriouseats.com/the-food-lab-science-of-deep-frying": "The Science of Deep Frying",
                "https://www.seriouseats.com/the-food-lab-science-of-saturated-vs-unsaturated-fats": "Saturated vs Unsaturated Fats",
                # Flavor and seasoning
                "https://www.seriouseats.com/the-food-lab-science-of-salt-and-seasoning": "The Science of Salt and Seasoning",
                "https://www.seriouseats.com/the-food-lab-science-of-umami": "The Science of Umami",
                "https://www.seriouseats.com/the-food-lab-science-of-acid-in-cooking": "The Science of Acid in Cooking",
                "https://www.seriouseats.com/the-food-lab-science-of-spice-and-heat": "The Science of Spice and Heat",
                "https://www.seriouseats.com/the-food-lab-science-of-flavor-pairing": "The Science of Flavor Pairing",
                "https://www.seriouseats.com/the-food-lab-science-of-msg": "The Science of MSG",
                # Water and heat transfer
                "https://www.seriouseats.com/the-food-lab-science-of-boiling-and-simmering": "The Science of Boiling and Simmering",
                "https://www.seriouseats.com/the-food-lab-science-of-convection-vs-conduction": "Convection vs Conduction in Cooking",
                "https://www.seriouseats.com/the-food-lab-science-of-steam-in-cooking": "The Science of Steam in Cooking",
                "https://www.seriouseats.com/the-food-lab-science-of-wok-hei": "The Science of Wok Hei",
                # Dairy science
                "https://www.seriouseats.com/the-food-lab-science-of-melting-cheese": "The Science of Melting Cheese",
                "https://www.seriouseats.com/the-food-lab-science-of-whipping-cream": "The Science of Whipping Cream",
                "https://www.seriouseats.com/the-food-lab-science-of-ice-cream": "The Science of Ice Cream",
                "https://www.seriouseats.com/the-food-lab-science-of-cultured-dairy": "The Science of Cultured Dairy",
                # Fermentation science
                "https://www.seriouseats.com/the-food-lab-science-of-lacto-fermentation": "The Science of Lacto-Fermentation",
                "https://www.seriouseats.com/the-food-lab-science-of-sourdough": "The Science of Sourdough",
                "https://www.seriouseats.com/the-food-lab-science-of-pickling": "The Science of Pickling",
                # Chocolate and sugar
                "https://www.seriouseats.com/the-food-lab-science-of-tempering-chocolate": "The Science of Tempering Chocolate",
                "https://www.seriouseats.com/the-food-lab-science-of-sugar-stages": "The Science of Sugar Stages",
                "https://www.seriouseats.com/the-food-lab-science-of-candy-making": "The Science of Candy Making",
                # Miscellaneous science
                "https://www.seriouseats.com/the-food-lab-science-of-pressure-cooking": "The Science of Pressure Cooking",
                "https://www.seriouseats.com/the-food-lab-science-of-microwave-cooking": "The Science of Microwave Cooking",
                "https://www.seriouseats.com/the-food-lab-science-of-dehydration": "The Science of Dehydration",
                "https://www.seriouseats.com/the-food-lab-science-of-osmosis-in-cooking": "The Science of Osmosis in Cooking",
                "https://www.seriouseats.com/the-food-lab-science-of-gelatin": "The Science of Gelatin",
            },
        },
        "recipes-meat": {
            "pages": {
                # Beef
                "https://www.seriouseats.com/the-best-slow-cooked-beef-chili-recipe": "The Best Slow-Cooked Beef Chili",
                "https://www.seriouseats.com/perfect-pan-seared-steaks-recipe": "Perfect Pan-Seared Steaks",
                "https://www.seriouseats.com/slow-roasted-prime-rib-recipe": "Slow-Roasted Prime Rib",
                "https://www.seriouseats.com/the-best-beef-stew-recipe": "The Best Beef Stew",
                "https://www.seriouseats.com/beef-bourguignon-recipe": "Beef Bourguignon",
                "https://www.seriouseats.com/braised-short-ribs-red-wine-recipe": "Braised Short Ribs in Red Wine",
                "https://www.seriouseats.com/the-best-meatloaf-recipe": "The Best Meatloaf",
                "https://www.seriouseats.com/smash-burger-recipe": "Smash Burgers",
                "https://www.seriouseats.com/the-best-beef-tacos-recipe": "The Best Beef Tacos",
                "https://www.seriouseats.com/beef-stroganoff-recipe": "Beef Stroganoff",
                "https://www.seriouseats.com/beef-pot-roast-recipe": "Beef Pot Roast",
                "https://www.seriouseats.com/the-best-bolognese-sauce-recipe": "The Best Bolognese Sauce",
                "https://www.seriouseats.com/grilled-flank-steak-recipe": "Grilled Flank Steak",
                "https://www.seriouseats.com/beef-bulgogi-recipe": "Beef Bulgogi",
                "https://www.seriouseats.com/carne-asada-recipe": "Carne Asada",
                "https://www.seriouseats.com/beef-brisket-oven-recipe": "Oven-Braised Beef Brisket",
                "https://www.seriouseats.com/corned-beef-and-cabbage-recipe": "Corned Beef and Cabbage",
                "https://www.seriouseats.com/philly-cheesesteak-recipe": "Philly Cheesesteak",
                "https://www.seriouseats.com/beef-and-broccoli-stir-fry-recipe": "Beef and Broccoli Stir-Fry",
                "https://www.seriouseats.com/meatballs-and-red-sauce-recipe": "Meatballs in Red Sauce",
                # Pork
                "https://www.seriouseats.com/the-best-pulled-pork-recipe": "The Best Pulled Pork",
                "https://www.seriouseats.com/crispy-pork-belly-recipe": "Crispy Pork Belly",
                "https://www.seriouseats.com/pan-roasted-pork-chops-recipe": "Pan-Roasted Pork Chops",
                "https://www.seriouseats.com/carnitas-recipe": "Carnitas",
                "https://www.seriouseats.com/char-siu-chinese-bbq-pork-recipe": "Char Siu Chinese BBQ Pork",
                "https://www.seriouseats.com/crispy-pan-fried-pork-cutlets-recipe": "Crispy Pan-Fried Pork Cutlets",
                "https://www.seriouseats.com/roasted-pork-tenderloin-recipe": "Roasted Pork Tenderloin",
                "https://www.seriouseats.com/glazed-ham-recipe": "Glazed Ham",
                "https://www.seriouseats.com/pork-ragu-recipe": "Pork Ragu",
                "https://www.seriouseats.com/pork-schnitzel-recipe": "Pork Schnitzel",
                "https://www.seriouseats.com/baby-back-ribs-oven-recipe": "Oven Baby Back Ribs",
                "https://www.seriouseats.com/pork-shoulder-braised-recipe": "Braised Pork Shoulder",
                "https://www.seriouseats.com/tonkatsu-japanese-fried-pork-cutlet-recipe": "Tonkatsu Japanese Fried Pork Cutlet",
                "https://www.seriouseats.com/pork-stir-fry-with-green-beans-recipe": "Pork Stir-Fry with Green Beans",
                "https://www.seriouseats.com/sausage-and-peppers-recipe": "Sausage and Peppers",
                # Chicken
                "https://www.seriouseats.com/the-best-roast-chicken-recipe": "The Best Roast Chicken",
                "https://www.seriouseats.com/the-best-buttermilk-fried-chicken-recipe": "The Best Buttermilk Fried Chicken",
                "https://www.seriouseats.com/chicken-parmesan-recipe": "Chicken Parmesan",
                "https://www.seriouseats.com/chicken-marsala-recipe": "Chicken Marsala",
                "https://www.seriouseats.com/chicken-pot-pie-recipe": "Chicken Pot Pie",
                "https://www.seriouseats.com/butter-chicken-recipe": "Butter Chicken",
                "https://www.seriouseats.com/chicken-adobo-recipe": "Chicken Adobo",
                "https://www.seriouseats.com/chicken-cacciatore-recipe": "Chicken Cacciatore",
                "https://www.seriouseats.com/teriyaki-chicken-recipe": "Teriyaki Chicken",
                "https://www.seriouseats.com/lemon-herb-roasted-chicken-thighs-recipe": "Lemon Herb Roasted Chicken Thighs",
                "https://www.seriouseats.com/chicken-shawarma-recipe": "Chicken Shawarma",
                "https://www.seriouseats.com/chicken-wings-crispy-baked-recipe": "Crispy Baked Chicken Wings",
                "https://www.seriouseats.com/general-tsos-chicken-recipe": "General Tso's Chicken",
                "https://www.seriouseats.com/chicken-tortilla-soup-recipe": "Chicken Tortilla Soup",
                "https://www.seriouseats.com/chicken-satay-with-peanut-sauce-recipe": "Chicken Satay with Peanut Sauce",
                "https://www.seriouseats.com/chicken-thighs-braised-with-olives-recipe": "Braised Chicken Thighs with Olives",
                "https://www.seriouseats.com/chicken-katsu-curry-recipe": "Chicken Katsu Curry",
                "https://www.seriouseats.com/grilled-chicken-breast-recipe": "Grilled Chicken Breast",
                # Lamb
                "https://www.seriouseats.com/roasted-leg-of-lamb-recipe": "Roasted Leg of Lamb",
                "https://www.seriouseats.com/braised-lamb-shanks-recipe": "Braised Lamb Shanks",
                "https://www.seriouseats.com/lamb-chops-grilled-recipe": "Grilled Lamb Chops",
                "https://www.seriouseats.com/lamb-kofta-recipe": "Lamb Kofta",
                "https://www.seriouseats.com/lamb-ragu-pasta-recipe": "Lamb Ragu with Pasta",
                "https://www.seriouseats.com/lamb-curry-recipe": "Lamb Curry",
                "https://www.seriouseats.com/lamb-gyros-recipe": "Lamb Gyros",
                "https://www.seriouseats.com/lamb-tagine-recipe": "Lamb Tagine",
                "https://www.seriouseats.com/rack-of-lamb-recipe": "Rack of Lamb",
                # Seafood
                "https://www.seriouseats.com/pan-seared-salmon-recipe": "Pan-Seared Salmon",
                "https://www.seriouseats.com/the-best-shrimp-scampi-recipe": "The Best Shrimp Scampi",
                "https://www.seriouseats.com/grilled-swordfish-recipe": "Grilled Swordfish",
                "https://www.seriouseats.com/fish-tacos-recipe": "Fish Tacos",
                "https://www.seriouseats.com/beer-battered-fish-and-chips-recipe": "Beer-Battered Fish and Chips",
                "https://www.seriouseats.com/clam-chowder-new-england-recipe": "New England Clam Chowder",
                "https://www.seriouseats.com/shrimp-pad-thai-recipe": "Shrimp Pad Thai",
                "https://www.seriouseats.com/lobster-bisque-recipe": "Lobster Bisque",
                "https://www.seriouseats.com/miso-glazed-cod-recipe": "Miso-Glazed Cod",
                "https://www.seriouseats.com/cioppino-seafood-stew-recipe": "Cioppino Seafood Stew",
                "https://www.seriouseats.com/garlic-butter-shrimp-recipe": "Garlic Butter Shrimp",
                "https://www.seriouseats.com/tuna-poke-bowl-recipe": "Tuna Poke Bowl",
                "https://www.seriouseats.com/seared-scallops-recipe": "Seared Scallops",
                "https://www.seriouseats.com/steamed-mussels-white-wine-recipe": "Steamed Mussels in White Wine",
                "https://www.seriouseats.com/blackened-catfish-recipe": "Blackened Catfish",
                "https://www.seriouseats.com/cajun-shrimp-and-grits-recipe": "Cajun Shrimp and Grits",
                "https://www.seriouseats.com/baked-salmon-with-dill-recipe": "Baked Salmon with Dill",
                # Game and other
                "https://www.seriouseats.com/roasted-duck-breast-recipe": "Roasted Duck Breast",
                "https://www.seriouseats.com/duck-confit-recipe": "Duck Confit",
                "https://www.seriouseats.com/turkey-meatballs-recipe": "Turkey Meatballs",
                "https://www.seriouseats.com/ground-turkey-tacos-recipe": "Ground Turkey Tacos",
                "https://www.seriouseats.com/venison-stew-recipe": "Venison Stew",
                "https://www.seriouseats.com/rabbit-braised-recipe": "Braised Rabbit",
                "https://www.seriouseats.com/cornish-game-hen-roasted-recipe": "Roasted Cornish Game Hen",
            },
        },
        "recipes-vegetarian": {
            "pages": {
                # Tofu and tempeh
                "https://www.seriouseats.com/crispy-tofu-recipe": "Crispy Tofu",
                "https://www.seriouseats.com/mapo-tofu-recipe": "Mapo Tofu",
                "https://www.seriouseats.com/general-tsos-tofu-recipe": "General Tso's Tofu",
                "https://www.seriouseats.com/baked-tofu-recipe": "Baked Tofu",
                "https://www.seriouseats.com/tofu-stir-fry-with-vegetables-recipe": "Tofu Stir-Fry with Vegetables",
                "https://www.seriouseats.com/tofu-scramble-recipe": "Tofu Scramble",
                "https://www.seriouseats.com/crispy-tempeh-recipe": "Crispy Tempeh",
                "https://www.seriouseats.com/tempeh-tacos-recipe": "Tempeh Tacos",
                # Beans and legumes
                "https://www.seriouseats.com/the-best-vegetarian-chili-recipe": "The Best Vegetarian Chili",
                "https://www.seriouseats.com/pasta-e-ceci-italian-pasta-chickpeas-recipe": "Pasta e Ceci (Italian Pasta with Chickpeas)",
                "https://www.seriouseats.com/the-best-black-bean-soup-recipe": "The Best Black Bean Soup",
                "https://www.seriouseats.com/falafel-recipe": "Falafel",
                "https://www.seriouseats.com/dal-tadka-recipe": "Dal Tadka",
                "https://www.seriouseats.com/refried-beans-recipe": "Refried Beans",
                "https://www.seriouseats.com/white-bean-and-escarole-soup-recipe": "White Bean and Escarole Soup",
                "https://www.seriouseats.com/chickpea-curry-chana-masala-recipe": "Chana Masala (Chickpea Curry)",
                "https://www.seriouseats.com/hummus-recipe": "Hummus",
                "https://www.seriouseats.com/lentil-soup-recipe": "Lentil Soup",
                "https://www.seriouseats.com/three-bean-salad-recipe": "Three Bean Salad",
                "https://www.seriouseats.com/black-eyed-peas-recipe": "Black-Eyed Peas",
                # Grains and rice
                "https://www.seriouseats.com/mushroom-risotto-recipe": "Mushroom Risotto",
                "https://www.seriouseats.com/fried-rice-vegetable-recipe": "Vegetable Fried Rice",
                "https://www.seriouseats.com/quinoa-salad-recipe": "Quinoa Salad",
                "https://www.seriouseats.com/polenta-creamy-recipe": "Creamy Polenta",
                "https://www.seriouseats.com/tabbouleh-salad-recipe": "Tabbouleh Salad",
                "https://www.seriouseats.com/farro-salad-roasted-vegetables-recipe": "Farro Salad with Roasted Vegetables",
                "https://www.seriouseats.com/grain-bowl-recipe": "Grain Bowl",
                # Pasta
                "https://www.seriouseats.com/cacio-e-pepe-recipe": "Cacio e Pepe",
                "https://www.seriouseats.com/aglio-olio-e-peperoncino-recipe": "Aglio e Olio",
                "https://www.seriouseats.com/pasta-alla-norma-recipe": "Pasta alla Norma",
                "https://www.seriouseats.com/pasta-primavera-recipe": "Pasta Primavera",
                "https://www.seriouseats.com/mac-and-cheese-stovetop-recipe": "Stovetop Mac and Cheese",
                "https://www.seriouseats.com/baked-ziti-recipe": "Baked Ziti",
                "https://www.seriouseats.com/penne-arrabbiata-recipe": "Penne Arrabbiata",
                "https://www.seriouseats.com/mushroom-pasta-recipe": "Mushroom Pasta",
                "https://www.seriouseats.com/spinach-ricotta-stuffed-shells-recipe": "Spinach Ricotta Stuffed Shells",
                "https://www.seriouseats.com/homemade-fresh-pasta-recipe": "Homemade Fresh Pasta",
                # Vegetables
                "https://www.seriouseats.com/roasted-cauliflower-steaks-recipe": "Roasted Cauliflower Steaks",
                "https://www.seriouseats.com/eggplant-parmesan-recipe": "Eggplant Parmesan",
                "https://www.seriouseats.com/stuffed-bell-peppers-rice-recipe": "Stuffed Bell Peppers with Rice",
                "https://www.seriouseats.com/ratatouille-recipe": "Ratatouille",
                "https://www.seriouseats.com/roasted-sweet-potatoes-recipe": "Roasted Sweet Potatoes",
                "https://www.seriouseats.com/creamy-mashed-potatoes-recipe": "Creamy Mashed Potatoes",
                "https://www.seriouseats.com/sauteed-green-beans-recipe": "Sauteed Green Beans",
                "https://www.seriouseats.com/roasted-broccoli-recipe": "Roasted Broccoli",
                "https://www.seriouseats.com/glazed-carrots-recipe": "Glazed Carrots",
                "https://www.seriouseats.com/grilled-portobello-mushroom-burgers-recipe": "Grilled Portobello Mushroom Burgers",
                "https://www.seriouseats.com/loaded-baked-potatoes-recipe": "Loaded Baked Potatoes",
                "https://www.seriouseats.com/zucchini-fritters-recipe": "Zucchini Fritters",
                "https://www.seriouseats.com/corn-on-the-cob-butter-recipe": "Corn on the Cob with Butter",
                "https://www.seriouseats.com/crispy-roasted-potatoes-recipe": "Crispy Roasted Potatoes",
                "https://www.seriouseats.com/creamed-spinach-recipe": "Creamed Spinach",
                # Salads
                "https://www.seriouseats.com/classic-caesar-salad-recipe": "Classic Caesar Salad",
                "https://www.seriouseats.com/greek-salad-recipe": "Greek Salad",
                "https://www.seriouseats.com/caprese-salad-recipe": "Caprese Salad",
                "https://www.seriouseats.com/fattoush-salad-recipe": "Fattoush Salad",
                "https://www.seriouseats.com/kale-salad-with-tahini-dressing-recipe": "Kale Salad with Tahini Dressing",
                "https://www.seriouseats.com/potato-salad-recipe": "Potato Salad",
                "https://www.seriouseats.com/coleslaw-recipe": "Coleslaw",
                "https://www.seriouseats.com/panzanella-bread-salad-recipe": "Panzanella Bread Salad",
                # Soups
                "https://www.seriouseats.com/tomato-soup-recipe": "Tomato Soup",
                "https://www.seriouseats.com/minestrone-soup-recipe": "Minestrone Soup",
                "https://www.seriouseats.com/french-onion-soup-recipe": "French Onion Soup",
                "https://www.seriouseats.com/butternut-squash-soup-recipe": "Butternut Squash Soup",
                "https://www.seriouseats.com/gazpacho-recipe": "Gazpacho",
                "https://www.seriouseats.com/mushroom-soup-creamy-recipe": "Creamy Mushroom Soup",
                "https://www.seriouseats.com/corn-chowder-recipe": "Corn Chowder",
                # Eggs (vegetarian)
                "https://www.seriouseats.com/shakshuka-recipe": "Shakshuka",
                "https://www.seriouseats.com/spanish-tortilla-recipe": "Spanish Tortilla",
                "https://www.seriouseats.com/frittata-with-vegetables-recipe": "Vegetable Frittata",
                "https://www.seriouseats.com/quiche-lorraine-vegetarian-recipe": "Vegetarian Quiche",
            },
        },
        "baking": {
            "pages": {
                # Cookies
                "https://www.seriouseats.com/the-food-lab-best-chocolate-chip-cookie-recipe": "The Best Chocolate Chip Cookies",
                "https://www.seriouseats.com/chewy-sugar-cookies-recipe": "Chewy Sugar Cookies",
                "https://www.seriouseats.com/double-chocolate-cookies-recipe": "Double Chocolate Cookies",
                "https://www.seriouseats.com/oatmeal-raisin-cookies-recipe": "Oatmeal Raisin Cookies",
                "https://www.seriouseats.com/peanut-butter-cookies-recipe": "Peanut Butter Cookies",
                "https://www.seriouseats.com/snickerdoodles-recipe": "Snickerdoodles",
                "https://www.seriouseats.com/shortbread-cookies-recipe": "Shortbread Cookies",
                "https://www.seriouseats.com/gingerbread-cookies-recipe": "Gingerbread Cookies",
                "https://www.seriouseats.com/macarons-recipe": "Macarons",
                "https://www.seriouseats.com/biscotti-recipe": "Biscotti",
                "https://www.seriouseats.com/thumbprint-cookies-recipe": "Thumbprint Cookies",
                "https://www.seriouseats.com/linzer-cookies-recipe": "Linzer Cookies",
                # Bread
                "https://www.seriouseats.com/easy-no-knead-bread-recipe": "Easy No-Knead Bread",
                "https://www.seriouseats.com/sourdough-bread-recipe": "Sourdough Bread",
                "https://www.seriouseats.com/focaccia-recipe": "Focaccia",
                "https://www.seriouseats.com/challah-bread-recipe": "Challah Bread",
                "https://www.seriouseats.com/brioche-bread-recipe": "Brioche",
                "https://www.seriouseats.com/ciabatta-bread-recipe": "Ciabatta",
                "https://www.seriouseats.com/banana-bread-recipe": "Banana Bread",
                "https://www.seriouseats.com/cornbread-recipe": "Cornbread",
                "https://www.seriouseats.com/dinner-rolls-recipe": "Dinner Rolls",
                "https://www.seriouseats.com/cinnamon-rolls-recipe": "Cinnamon Rolls",
                "https://www.seriouseats.com/naan-bread-recipe": "Naan Bread",
                "https://www.seriouseats.com/pita-bread-recipe": "Pita Bread",
                "https://www.seriouseats.com/flour-tortillas-recipe": "Flour Tortillas",
                "https://www.seriouseats.com/pretzels-soft-recipe": "Soft Pretzels",
                "https://www.seriouseats.com/english-muffins-recipe": "English Muffins",
                "https://www.seriouseats.com/whole-wheat-bread-recipe": "Whole Wheat Bread",
                # Pies and tarts
                "https://www.seriouseats.com/bravetart-easy-homemade-pie-dough": "BraveTart Easy Homemade Pie Dough",
                "https://www.seriouseats.com/apple-pie-recipe": "Apple Pie",
                "https://www.seriouseats.com/pumpkin-pie-recipe": "Pumpkin Pie",
                "https://www.seriouseats.com/pecan-pie-recipe": "Pecan Pie",
                "https://www.seriouseats.com/cherry-pie-recipe": "Cherry Pie",
                "https://www.seriouseats.com/blueberry-pie-recipe": "Blueberry Pie",
                "https://www.seriouseats.com/lemon-meringue-pie-recipe": "Lemon Meringue Pie",
                "https://www.seriouseats.com/key-lime-pie-recipe": "Key Lime Pie",
                "https://www.seriouseats.com/tarte-tatin-recipe": "Tarte Tatin",
                "https://www.seriouseats.com/chocolate-tart-recipe": "Chocolate Tart",
                "https://www.seriouseats.com/fruit-galette-recipe": "Fruit Galette",
                "https://www.seriouseats.com/quiche-recipe": "Quiche",
                # Cakes
                "https://www.seriouseats.com/chocolate-layer-cake-recipe": "Chocolate Layer Cake",
                "https://www.seriouseats.com/vanilla-birthday-cake-recipe": "Vanilla Birthday Cake",
                "https://www.seriouseats.com/carrot-cake-recipe": "Carrot Cake",
                "https://www.seriouseats.com/red-velvet-cake-recipe": "Red Velvet Cake",
                "https://www.seriouseats.com/cheesecake-new-york-recipe": "New York Cheesecake",
                "https://www.seriouseats.com/pound-cake-recipe": "Pound Cake",
                "https://www.seriouseats.com/angel-food-cake-recipe": "Angel Food Cake",
                "https://www.seriouseats.com/lemon-cake-recipe": "Lemon Cake",
                "https://www.seriouseats.com/coffee-cake-recipe": "Coffee Cake",
                "https://www.seriouseats.com/german-chocolate-cake-recipe": "German Chocolate Cake",
                "https://www.seriouseats.com/tres-leches-cake-recipe": "Tres Leches Cake",
                "https://www.seriouseats.com/tiramisu-recipe": "Tiramisu",
                "https://www.seriouseats.com/olive-oil-cake-recipe": "Olive Oil Cake",
                # Pastries
                "https://www.seriouseats.com/croissants-recipe": "Croissants",
                "https://www.seriouseats.com/danish-pastry-recipe": "Danish Pastry",
                "https://www.seriouseats.com/cream-puffs-choux-pastry-recipe": "Cream Puffs (Choux Pastry)",
                "https://www.seriouseats.com/puff-pastry-recipe": "Puff Pastry",
                "https://www.seriouseats.com/eclairs-recipe": "Eclairs",
                "https://www.seriouseats.com/scones-recipe": "Scones",
                "https://www.seriouseats.com/blueberry-muffins-recipe": "Blueberry Muffins",
                "https://www.seriouseats.com/pancakes-fluffy-recipe": "Fluffy Pancakes",
                "https://www.seriouseats.com/waffles-recipe": "Waffles",
                "https://www.seriouseats.com/creme-brulee-recipe": "Creme Brulee",
                "https://www.seriouseats.com/panna-cotta-recipe": "Panna Cotta",
                "https://www.seriouseats.com/chocolate-mousse-recipe": "Chocolate Mousse",
                "https://www.seriouseats.com/brownies-recipe": "Brownies",
                "https://www.seriouseats.com/lemon-bars-recipe": "Lemon Bars",
                # Frostings and toppings
                "https://www.seriouseats.com/buttercream-frosting-recipe": "Buttercream Frosting",
                "https://www.seriouseats.com/cream-cheese-frosting-recipe": "Cream Cheese Frosting",
                "https://www.seriouseats.com/chocolate-ganache-recipe": "Chocolate Ganache",
                "https://www.seriouseats.com/whipped-cream-recipe": "Whipped Cream",
                "https://www.seriouseats.com/caramel-sauce-recipe": "Caramel Sauce",
            },
        },
        "cuisines": {
            "pages": {
                # Italian
                "https://www.seriouseats.com/the-best-cacio-e-pepe-recipe": "The Best Cacio e Pepe",
                "https://www.seriouseats.com/pasta-carbonara-recipe": "Pasta Carbonara",
                "https://www.seriouseats.com/pasta-amatriciana-recipe": "Pasta all'Amatriciana",
                "https://www.seriouseats.com/lasagna-recipe": "Lasagna",
                "https://www.seriouseats.com/pizza-margherita-recipe": "Pizza Margherita",
                "https://www.seriouseats.com/pizza-dough-recipe": "Pizza Dough",
                "https://www.seriouseats.com/osso-buco-recipe": "Osso Buco",
                "https://www.seriouseats.com/risotto-milanese-recipe": "Risotto Milanese",
                "https://www.seriouseats.com/gnocchi-recipe": "Gnocchi",
                "https://www.seriouseats.com/pesto-genovese-recipe": "Pesto Genovese",
                "https://www.seriouseats.com/bruschetta-recipe": "Bruschetta",
                # Mexican
                "https://www.seriouseats.com/chicken-enchiladas-recipe": "Chicken Enchiladas",
                "https://www.seriouseats.com/tamales-recipe": "Tamales",
                "https://www.seriouseats.com/pozole-rojo-recipe": "Pozole Rojo",
                "https://www.seriouseats.com/chiles-rellenos-recipe": "Chiles Rellenos",
                "https://www.seriouseats.com/guacamole-recipe": "Guacamole",
                "https://www.seriouseats.com/salsa-verde-recipe": "Salsa Verde",
                "https://www.seriouseats.com/pico-de-gallo-recipe": "Pico de Gallo",
                "https://www.seriouseats.com/mole-negro-recipe": "Mole Negro",
                "https://www.seriouseats.com/churros-recipe": "Churros",
                "https://www.seriouseats.com/birria-tacos-recipe": "Birria Tacos",
                "https://www.seriouseats.com/elote-mexican-street-corn-recipe": "Elote Mexican Street Corn",
                # Chinese
                "https://www.seriouseats.com/real-deal-kung-pao-chicken-recipe": "Real-Deal Kung Pao Chicken",
                "https://www.seriouseats.com/dan-dan-noodles-recipe": "Dan Dan Noodles",
                "https://www.seriouseats.com/chinese-scallion-pancakes-recipe": "Chinese Scallion Pancakes",
                "https://www.seriouseats.com/chinese-pork-dumplings-recipe": "Chinese Pork Dumplings",
                "https://www.seriouseats.com/hot-and-sour-soup-recipe": "Hot and Sour Soup",
                "https://www.seriouseats.com/ma-po-tofu-recipe": "Ma Po Tofu",
                "https://www.seriouseats.com/chinese-fried-rice-recipe": "Chinese Fried Rice",
                "https://www.seriouseats.com/sweet-and-sour-pork-recipe": "Sweet and Sour Pork",
                "https://www.seriouseats.com/chinese-steamed-fish-recipe": "Chinese Steamed Fish",
                "https://www.seriouseats.com/chinese-braised-pork-belly-recipe": "Chinese Braised Pork Belly",
                "https://www.seriouseats.com/xiao-long-bao-soup-dumplings-recipe": "Xiao Long Bao Soup Dumplings",
                # Japanese
                "https://www.seriouseats.com/tonkotsu-ramen-recipe": "Tonkotsu Ramen",
                "https://www.seriouseats.com/miso-ramen-recipe": "Miso Ramen",
                "https://www.seriouseats.com/sushi-rice-recipe": "Sushi Rice",
                "https://www.seriouseats.com/gyoza-japanese-dumplings-recipe": "Gyoza Japanese Dumplings",
                "https://www.seriouseats.com/japanese-curry-recipe": "Japanese Curry",
                "https://www.seriouseats.com/okonomiyaki-japanese-pancake-recipe": "Okonomiyaki Japanese Pancake",
                "https://www.seriouseats.com/takoyaki-octopus-balls-recipe": "Takoyaki Octopus Balls",
                "https://www.seriouseats.com/tempura-vegetables-recipe": "Tempura Vegetables",
                "https://www.seriouseats.com/miso-soup-recipe": "Miso Soup",
                "https://www.seriouseats.com/japanese-chicken-karaage-recipe": "Japanese Chicken Karaage",
                "https://www.seriouseats.com/yakitori-recipe": "Yakitori",
                # Thai
                "https://www.seriouseats.com/pad-thai-recipe": "Pad Thai",
                "https://www.seriouseats.com/thai-green-curry-recipe": "Thai Green Curry",
                "https://www.seriouseats.com/thai-red-curry-recipe": "Thai Red Curry",
                "https://www.seriouseats.com/tom-yum-soup-recipe": "Tom Yum Soup",
                "https://www.seriouseats.com/thai-basil-chicken-pad-krapow-recipe": "Thai Basil Chicken (Pad Krapow)",
                "https://www.seriouseats.com/thai-larb-recipe": "Thai Larb",
                "https://www.seriouseats.com/thai-peanut-noodles-recipe": "Thai Peanut Noodles",
                "https://www.seriouseats.com/thai-mango-sticky-rice-recipe": "Thai Mango Sticky Rice",
                "https://www.seriouseats.com/thai-papaya-salad-som-tum-recipe": "Thai Papaya Salad (Som Tum)",
                "https://www.seriouseats.com/massaman-curry-recipe": "Massaman Curry",
                # Indian
                "https://www.seriouseats.com/chicken-tikka-masala-recipe": "Chicken Tikka Masala",
                "https://www.seriouseats.com/palak-paneer-recipe": "Palak Paneer",
                "https://www.seriouseats.com/aloo-gobi-recipe": "Aloo Gobi",
                "https://www.seriouseats.com/tandoori-chicken-recipe": "Tandoori Chicken",
                "https://www.seriouseats.com/biryani-recipe": "Biryani",
                "https://www.seriouseats.com/samosa-recipe": "Samosa",
                "https://www.seriouseats.com/chicken-vindaloo-recipe": "Chicken Vindaloo",
                "https://www.seriouseats.com/dal-makhani-recipe": "Dal Makhani",
                "https://www.seriouseats.com/naan-garlic-recipe": "Garlic Naan",
                "https://www.seriouseats.com/raita-recipe": "Raita",
                # French
                "https://www.seriouseats.com/coq-au-vin-recipe": "Coq au Vin",
                "https://www.seriouseats.com/french-onion-soup-gratinee-recipe": "French Onion Soup Gratinee",
                "https://www.seriouseats.com/ratatouille-french-recipe": "French Ratatouille",
                "https://www.seriouseats.com/beef-daube-provencal-recipe": "Beef Daube Provencal",
                "https://www.seriouseats.com/duck-confit-french-recipe": "French Duck Confit",
                "https://www.seriouseats.com/cassoulet-recipe": "Cassoulet",
                "https://www.seriouseats.com/quiche-lorraine-recipe": "Quiche Lorraine",
                "https://www.seriouseats.com/bearnaise-sauce-recipe": "Bearnaise Sauce",
                "https://www.seriouseats.com/bechamel-sauce-recipe": "Bechamel Sauce",
                "https://www.seriouseats.com/souffle-recipe": "Souffle",
                # Korean
                "https://www.seriouseats.com/kimchi-jjigae-kimchi-stew-recipe": "Kimchi Jjigae (Kimchi Stew)",
                "https://www.seriouseats.com/bibimbap-recipe": "Bibimbap",
                "https://www.seriouseats.com/korean-fried-chicken-recipe": "Korean Fried Chicken",
                "https://www.seriouseats.com/japchae-korean-glass-noodles-recipe": "Japchae Korean Glass Noodles",
                "https://www.seriouseats.com/korean-pancakes-pajeon-recipe": "Korean Pancakes (Pajeon)",
                "https://www.seriouseats.com/tteokbokki-spicy-rice-cakes-recipe": "Tteokbokki Spicy Rice Cakes",
                "https://www.seriouseats.com/galbi-korean-short-ribs-recipe": "Galbi Korean Short Ribs",
                "https://www.seriouseats.com/korean-army-stew-budae-jjigae-recipe": "Korean Army Stew (Budae Jjigae)",
                # Middle Eastern
                "https://www.seriouseats.com/shawarma-spiced-lamb-recipe": "Shawarma-Spiced Lamb",
                "https://www.seriouseats.com/baba-ganoush-recipe": "Baba Ganoush",
                "https://www.seriouseats.com/tabbouleh-recipe": "Tabbouleh",
                "https://www.seriouseats.com/labneh-recipe": "Labneh",
                "https://www.seriouseats.com/kibbeh-recipe": "Kibbeh",
                "https://www.seriouseats.com/muhammara-recipe": "Muhammara",
                "https://www.seriouseats.com/baklava-recipe": "Baklava",
                "https://www.seriouseats.com/manakish-zaatar-flatbread-recipe": "Manakish Zaatar Flatbread",
                "https://www.seriouseats.com/kofta-kebab-recipe": "Kofta Kebab",
                # Vietnamese
                "https://www.seriouseats.com/pho-bo-vietnamese-beef-noodle-soup-recipe": "Pho Bo Vietnamese Beef Noodle Soup",
                "https://www.seriouseats.com/banh-mi-vietnamese-sandwich-recipe": "Banh Mi Vietnamese Sandwich",
                "https://www.seriouseats.com/vietnamese-spring-rolls-recipe": "Vietnamese Spring Rolls",
                "https://www.seriouseats.com/bun-cha-vietnamese-grilled-pork-recipe": "Bun Cha Vietnamese Grilled Pork",
            },
        },
        "equipment": {
            "pages": {
                # Knives
                "https://www.seriouseats.com/the-best-chefs-knives-equipment-review": "The Best Chef's Knives",
                "https://www.seriouseats.com/best-paring-knives-review": "Best Paring Knives",
                "https://www.seriouseats.com/best-bread-knives-review": "Best Bread Knives",
                "https://www.seriouseats.com/best-santoku-knives-review": "Best Santoku Knives",
                "https://www.seriouseats.com/best-knife-sharpeners-review": "Best Knife Sharpeners",
                "https://www.seriouseats.com/best-cutting-boards-review": "Best Cutting Boards",
                "https://www.seriouseats.com/best-knife-sets-review": "Best Knife Sets",
                "https://www.seriouseats.com/best-honing-steels-review": "Best Honing Steels",
                # Pans and cookware
                "https://www.seriouseats.com/best-cast-iron-skillets": "Best Cast Iron Skillets",
                "https://www.seriouseats.com/best-nonstick-pans-review": "Best Nonstick Pans",
                "https://www.seriouseats.com/best-stainless-steel-skillets-review": "Best Stainless Steel Skillets",
                "https://www.seriouseats.com/best-dutch-ovens-review": "Best Dutch Ovens",
                "https://www.seriouseats.com/best-carbon-steel-pans-review": "Best Carbon Steel Pans",
                "https://www.seriouseats.com/best-saucepans-review": "Best Saucepans",
                "https://www.seriouseats.com/best-stockpots-review": "Best Stockpots",
                "https://www.seriouseats.com/best-woks-review": "Best Woks",
                "https://www.seriouseats.com/best-sheet-pans-review": "Best Sheet Pans",
                "https://www.seriouseats.com/best-roasting-pans-review": "Best Roasting Pans",
                "https://www.seriouseats.com/best-cookware-sets-review": "Best Cookware Sets",
                # Grills and outdoor
                "https://www.seriouseats.com/best-charcoal-grills-review": "Best Charcoal Grills",
                "https://www.seriouseats.com/best-gas-grills-review": "Best Gas Grills",
                "https://www.seriouseats.com/best-smokers-review": "Best Smokers",
                "https://www.seriouseats.com/best-grill-accessories-review": "Best Grill Accessories",
                "https://www.seriouseats.com/best-chimney-starters-review": "Best Chimney Starters",
                # Thermometers and measurement
                "https://www.seriouseats.com/best-instant-read-thermometers": "Best Instant Read Thermometers",
                "https://www.seriouseats.com/best-oven-thermometers-review": "Best Oven Thermometers",
                "https://www.seriouseats.com/best-kitchen-scales-review": "Best Kitchen Scales",
                "https://www.seriouseats.com/best-measuring-cups-review": "Best Measuring Cups",
                "https://www.seriouseats.com/best-measuring-spoons-review": "Best Measuring Spoons",
                "https://www.seriouseats.com/best-leave-in-probe-thermometers-review": "Best Leave-In Probe Thermometers",
                # Appliances
                "https://www.seriouseats.com/best-food-processors-review": "Best Food Processors",
                "https://www.seriouseats.com/best-stand-mixers-review": "Best Stand Mixers",
                "https://www.seriouseats.com/best-blenders-review": "Best Blenders",
                "https://www.seriouseats.com/best-immersion-blenders-review": "Best Immersion Blenders",
                "https://www.seriouseats.com/best-sous-vide-circulators-review": "Best Sous Vide Circulators",
                "https://www.seriouseats.com/best-pressure-cookers-review": "Best Pressure Cookers",
                "https://www.seriouseats.com/best-slow-cookers-review": "Best Slow Cookers",
                "https://www.seriouseats.com/best-air-fryers-review": "Best Air Fryers",
                "https://www.seriouseats.com/best-toaster-ovens-review": "Best Toaster Ovens",
                "https://www.seriouseats.com/best-rice-cookers-review": "Best Rice Cookers",
                "https://www.seriouseats.com/best-coffee-grinders-review": "Best Coffee Grinders",
                "https://www.seriouseats.com/best-espresso-machines-review": "Best Espresso Machines",
                # Utensils and tools
                "https://www.seriouseats.com/best-spatulas-review": "Best Spatulas",
                "https://www.seriouseats.com/best-tongs-review": "Best Tongs",
                "https://www.seriouseats.com/best-whisks-review": "Best Whisks",
                "https://www.seriouseats.com/best-wooden-spoons-review": "Best Wooden Spoons",
                "https://www.seriouseats.com/best-ladles-review": "Best Ladles",
                "https://www.seriouseats.com/best-peelers-review": "Best Peelers",
                "https://www.seriouseats.com/best-colanders-review": "Best Colanders",
                "https://www.seriouseats.com/best-mixing-bowls-review": "Best Mixing Bowls",
                "https://www.seriouseats.com/best-rolling-pins-review": "Best Rolling Pins",
                "https://www.seriouseats.com/best-can-openers-review": "Best Can Openers",
                "https://www.seriouseats.com/best-kitchen-shears-review": "Best Kitchen Shears",
                # Bakeware
                "https://www.seriouseats.com/best-baking-sheets-review": "Best Baking Sheets",
                "https://www.seriouseats.com/best-pie-dishes-review": "Best Pie Dishes",
                "https://www.seriouseats.com/best-cake-pans-review": "Best Cake Pans",
                "https://www.seriouseats.com/best-muffin-pans-review": "Best Muffin Pans",
                "https://www.seriouseats.com/best-loaf-pans-review": "Best Loaf Pans",
                "https://www.seriouseats.com/best-cooling-racks-review": "Best Cooling Racks",
            },
        },
        "ingredients": {
            "pages": {
                # Guides and pantry staples
                "https://www.seriouseats.com/what-are-the-best-tomatoes-to-buy": "What Are the Best Tomatoes to Buy",
                "https://www.seriouseats.com/essential-pantry-staples": "Essential Pantry Staples",
                "https://www.seriouseats.com/fish-sauce-guide": "Fish Sauce Guide",
                "https://www.seriouseats.com/soy-sauce-guide": "Soy Sauce Guide",
                "https://www.seriouseats.com/vinegar-guide": "Vinegar Guide",
                "https://www.seriouseats.com/olive-oil-guide": "Olive Oil Guide",
                "https://www.seriouseats.com/salt-guide-types-and-uses": "Salt Guide: Types and Uses",
                "https://www.seriouseats.com/pepper-guide-types-and-uses": "Pepper Guide: Types and Uses",
                "https://www.seriouseats.com/butter-guide-salted-vs-unsalted": "Butter Guide: Salted vs Unsalted",
                "https://www.seriouseats.com/flour-guide-types-and-uses": "Flour Guide: Types and Uses",
                "https://www.seriouseats.com/sugar-guide-types-and-uses": "Sugar Guide: Types and Uses",
                "https://www.seriouseats.com/rice-guide-types-and-cooking-methods": "Rice Guide: Types and Cooking Methods",
                "https://www.seriouseats.com/dried-pasta-guide-shapes-and-sauces": "Dried Pasta Guide: Shapes and Sauces",
                # Spices and herbs
                "https://www.seriouseats.com/spice-guide-cumin": "Spice Guide: Cumin",
                "https://www.seriouseats.com/spice-guide-coriander": "Spice Guide: Coriander",
                "https://www.seriouseats.com/spice-guide-turmeric": "Spice Guide: Turmeric",
                "https://www.seriouseats.com/spice-guide-paprika": "Spice Guide: Paprika",
                "https://www.seriouseats.com/spice-guide-cinnamon": "Spice Guide: Cinnamon",
                "https://www.seriouseats.com/spice-guide-chili-peppers": "Spice Guide: Chili Peppers",
                "https://www.seriouseats.com/fresh-herbs-guide-storage-and-use": "Fresh Herbs Guide: Storage and Use",
                "https://www.seriouseats.com/dried-herbs-guide": "Dried Herbs Guide",
                "https://www.seriouseats.com/curry-powder-guide": "Curry Powder Guide",
                "https://www.seriouseats.com/five-spice-powder-guide": "Five Spice Powder Guide",
                # Produce
                "https://www.seriouseats.com/seasonal-produce-guide-spring": "Seasonal Produce Guide: Spring",
                "https://www.seriouseats.com/seasonal-produce-guide-summer": "Seasonal Produce Guide: Summer",
                "https://www.seriouseats.com/seasonal-produce-guide-fall": "Seasonal Produce Guide: Fall",
                "https://www.seriouseats.com/seasonal-produce-guide-winter": "Seasonal Produce Guide: Winter",
                "https://www.seriouseats.com/mushroom-guide-varieties-and-uses": "Mushroom Guide: Varieties and Uses",
                "https://www.seriouseats.com/onion-guide-types-and-uses": "Onion Guide: Types and Uses",
                "https://www.seriouseats.com/garlic-guide-buying-and-storing": "Garlic Guide: Buying and Storing",
                "https://www.seriouseats.com/avocado-guide-how-to-pick-and-store": "Avocado Guide: How to Pick and Store",
                "https://www.seriouseats.com/citrus-guide-types-and-uses": "Citrus Guide: Types and Uses",
                "https://www.seriouseats.com/chili-pepper-guide-heat-scale": "Chili Pepper Guide: Heat Scale",
                "https://www.seriouseats.com/leafy-greens-guide": "Leafy Greens Guide",
                "https://www.seriouseats.com/squash-guide-varieties-and-cooking": "Squash Guide: Varieties and Cooking",
                "https://www.seriouseats.com/potato-guide-varieties-and-uses": "Potato Guide: Varieties and Uses",
                # Sauces and condiments
                "https://www.seriouseats.com/hot-sauce-guide": "Hot Sauce Guide",
                "https://www.seriouseats.com/mustard-guide-types-and-uses": "Mustard Guide: Types and Uses",
                "https://www.seriouseats.com/miso-paste-guide": "Miso Paste Guide",
                "https://www.seriouseats.com/tahini-guide": "Tahini Guide",
                "https://www.seriouseats.com/oyster-sauce-guide": "Oyster Sauce Guide",
                "https://www.seriouseats.com/hoisin-sauce-guide": "Hoisin Sauce Guide",
                "https://www.seriouseats.com/worcestershire-sauce-guide": "Worcestershire Sauce Guide",
                "https://www.seriouseats.com/sambal-oelek-guide": "Sambal Oelek Guide",
                "https://www.seriouseats.com/gochujang-guide": "Gochujang Guide",
                # Proteins
                "https://www.seriouseats.com/beef-cuts-guide": "Beef Cuts Guide",
                "https://www.seriouseats.com/pork-cuts-guide": "Pork Cuts Guide",
                "https://www.seriouseats.com/chicken-cuts-guide": "Chicken Cuts Guide",
                "https://www.seriouseats.com/seafood-buying-guide-fresh-fish": "Seafood Buying Guide: Fresh Fish",
                "https://www.seriouseats.com/tofu-guide-types-and-uses": "Tofu Guide: Types and Uses",
                # Dairy and cheese
                "https://www.seriouseats.com/cheese-guide-types-and-uses": "Cheese Guide: Types and Uses",
                "https://www.seriouseats.com/parmesan-guide-parmigiano-reggiano": "Parmesan Guide: Parmigiano-Reggiano",
                "https://www.seriouseats.com/cream-guide-types-and-uses": "Cream Guide: Types and Uses",
                "https://www.seriouseats.com/yogurt-guide-types-and-uses": "Yogurt Guide: Types and Uses",
                # Baking ingredients
                "https://www.seriouseats.com/chocolate-guide-types-and-percentages": "Chocolate Guide: Types and Percentages",
                "https://www.seriouseats.com/vanilla-extract-guide": "Vanilla Extract Guide",
                "https://www.seriouseats.com/cocoa-powder-guide-dutch-vs-natural": "Cocoa Powder Guide: Dutch vs Natural",
                "https://www.seriouseats.com/yeast-guide-active-dry-vs-instant": "Yeast Guide: Active Dry vs Instant",
                "https://www.seriouseats.com/nuts-guide-types-toasting-storing": "Nuts Guide: Types, Toasting, Storing",
            },
        },
    }

    def __init__(self, base_dir, source_key=None):
        name = f"serious-eats-{source_key}" if source_key else "serious-eats"
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
            for suffix in [' | Serious Eats', ' - Serious Eats']:
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
                        "category": f"serious-eats-{source_key}",
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
            self.log.info(f"=== Scraping serious-eats/{key} ===")
            total += self._scrape_source(key, config)

        return total


if __name__ == "__main__":
    import os
    import sys

    base = os.path.expanduser("~")
    source_key = sys.argv[1] if len(sys.argv) > 1 else None
    SeriousEatsScraper(base, source_key).run()
